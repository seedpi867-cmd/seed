# 06-sd — BCM2835 SDHOST Driver Plan

Cycle 25 — 2026-05-17

## Goal

Read raw sectors from the boot SD card using the BCM2835 SDHOST controller.
No DMA. No interrupts. Polling only. First objective: read sector 0 (MBR/GPT)
to prove the driver works. Second: read FAT32 boot partition to load files
(model weights, config, kernel updates).

## Why SDHOST, Not EMMC2

Live probe (Cycle 25) confirms:
- mmc0 (119 GiB SN128 SDXC boot card) → **SDHOST at 0x3F202000**
- mmc1 (CYW43455 WiFi SDIO) → EMMC2 at 0x3F300000

SDHOST is the right target. EMMC2 is owned by WiFi.

## Register Map

Base address: **0x3F202000** (ARM physical, = 0x7E202000 VC bus).

```
Offset  Name    Description
+00     SDCMD   Command + flags (write to submit, poll to complete)
+04     SDARG   Command argument
+08     SDTOUT  Read/write timeout (write before data commands)
+0C     SDCDIV  Clock divider: SD_clock = 250MHz / (CDIV + 2)
+10     SDRSP0  Response word 0 (bits [31:0])
+14     SDRSP1  Response word 1 (bits [63:32])
+18     SDRSP2  Response word 2 (bits [95:64])
+1C     SDRSP3  Response word 3 (bits [127:96])
+20     SDHSTS  Host status (error + interrupt flags)
+30     SDVDD   VDD control: write 1 = 3.3V on
+34     SDEDM   Emergency debug mode (FIFO fill levels, state)
+38     SDHCFG  Host config (interrupt enables, bus width)
+3C     SDHBCT  Block byte count for transfers
+40     SDDATA  Data FIFO (32-bit read/write)
+50     SDHBLC  Block count for multi-block transfers
```

**Live register snapshot (Cycle 25, Linux running):**
```
SDCMD  = 0x00000052   last completed CMD (0x52 = CMD18? or state)
SDARG  = 0x00114B80
SDTOUT = 0x017D7840   timeout = 25,000,000 (set by Linux driver)
SDCDIV = 0x00000006   → 250MHz/(6+2) = 31.25 MHz operating clock
SDHSTS = 0x00000000   no errors, clean
SDVDD  = 0x00000001   3.3V on
SDEDM  = 0x00010801   FIFO empty, state machine idle
SDHCFG = 0x0000040E   busy_en + some IRQ enables (Linux mode)
```

**Core clock = 250 MHz** (SDHOST_CLK = VPU clock, confirmed by CDIV=6 at 31.25 MHz).

## SDCMD Flag Bits

```
bit15   NEW_FLAG       Write 1 to submit command; hardware clears when done
bit14   FAIL_FLAG      Hardware sets on error; check after NEW_FLAG clears
bit11   BUSY_FLAG      Set for R1b commands (CMD7 SELECT, CMD12 STOP)
bit10   NO_RESPONSE    Set for CMD0 (no response expected)
bit9    LONG_RESPONSE  Set for CMD2 (128-bit response)
bit7    WRITE          Write data transfer
bit6    READ           Read data transfer
[5:0]   CMD_INDEX      SD command number (0-63)
```

## SDHSTS Flag Bits

```
bit10   BUSY_IRPT   Card released busy (R1b done)
bit9    BLOCK_IRPT  Block transfer complete
bit8    SDIO_IRPT   SDIO interrupt
bit7    REW_TIME_OUT Read/write timeout
bit6    CMD_TIME_OUT Command timeout
bit5    CRC7_ERROR  CRC7 error in response
bit4    CRC16_ERROR CRC16 error in data
bit3    FIFO_ERROR  FIFO over/underrun
bit1    (reserved)
bit0    DATA_FLAG   Data available in FIFO (or FIFO ready for write)
```

## SDHCFG Bits

```
bit10   BUSY_EN     Enable busy interrupt
bit9    BLOCK_EN    Enable block complete interrupt
bit8    SDIO_EN     Enable SDIO interrupt
bit5    DATA_EN     Enable data interrupt
bit4    DATA_IRPT_EN Enable data interrupt (old name)
bit3    REW_IRPT_EN  Enable timeout interrupt
bit2    CMD_IRPT_EN  Enable command done interrupt
bit1    CRC_ERR_EN   Enable CRC error interrupt
bit0    REL_CMD_LINE Release command line
bit6    WIDE_EXT_BUS 8-bit bus
bit7    WIDE_INT_BUS 4-bit bus (set this for 4-bit mode)
```

For bare-metal polling: **SDHCFG = 0** (all interrupts off, 1-bit bus initially).

## Clock Dividers

Formula: `SD_clock = 250_000_000 / (CDIV + 2)`

```
CDIV    SD clock
623     400.6 kHz    ← initialization (SD spec: ≤400 kHz)
8       27.8 MHz     ← data transfer (safe)
6       31.25 MHz    ← Linux uses this (what hardware can handle)
3       62.5 MHz     ← too fast for most cards
```

Use **CDIV = 623** during SD init sequence. Switch to **CDIV = 8** after CMD7.

## SD Card Initialization Sequence (SdV2 SDHC/SDXC)

This Pi uses an SN128 119 GiB SDXC card (mmc0:aaaa). SDHC/SDXC cards use
byte-addressed sectors internally but commands use 512-byte sector numbers.

### Phase 0: Controller Init

```
1. Write SDVDD = 1            (3.3V on)
   Delay 5ms
2. Write SDCMD = 0            (flush)
   Write SDARG = 0
   Write SDHCFG = 0           (polling, no DMA, 1-bit bus)
   Write SDHBCT = 0
   Write SDHBLC = 0
3. Write SDCDIV = 623         (400 kHz init clock)
   Delay 1ms (clock settle)
```

### Phase 1: Card Identification

```
4. CMD0: GO_IDLE_STATE
   SDARG = 0x00000000
   SDCMD = NEW_FLAG | NO_RESPONSE | 0
   Poll: wait until NEW_FLAG clears (or FAIL_FLAG sets → error)

5. CMD8: SEND_IF_COND
   SDARG = 0x000001AA         (VHS=1 = 2.7-3.6V, check=0xAA)
   SDCMD = NEW_FLAG | 8
   Wait, read SDRSP0
   If SDRSP0 == 0x1AA: SD v2, SDHC/SDXC capable. Continue.
   If CMD_TIME_OUT: SD v1 or MMC. Different path (not implemented here).

6. ACMD41 loop: SD_SEND_OP_COND
   a. CMD55: APP_CMD (prefix for ACMD)
      SDARG = 0x00000000      (RCA=0 during init)
      SDCMD = NEW_FLAG | 55
      Wait, check R1 in SDRSP0 (expect bit5=APP_CMD set)

   b. ACMD41:
      SDARG = 0x51FF8000      (HCS=1 bit30, XPC=1 bit28, S18R=0, voltage=0xFF8000)
      Actually: 0xC0100000 | (1<<30) | voltage_window
      Simpler: SDARG = 0x40FF8000 (HCS=1, no S18R, full voltage)
      SDCMD = NEW_FLAG | NO_RESPONSE | 41
      Wait, read SDRSP0

   c. Check SDRSP0 bit31 (busy=0 means card still initializing):
      If bit31=0: loop back to CMD55 (repeat up to ~1000ms)
      If bit31=1: card ready. Check bit30 (CCS): 1=SDHC/SDXC (sector addressing)

7. CMD2: ALL_SEND_CID
   SDARG = 0
   SDCMD = NEW_FLAG | LONG_RESPONSE | 2
   Read 128-bit CID from SDRSP3:SDRSP2:SDRSP1:SDRSP0 (for logging)

8. CMD3: SEND_RELATIVE_ADDR
   SDARG = 0
   SDCMD = NEW_FLAG | 3
   Read SDRSP0 → RCA = SDRSP0[31:16]
   Save RCA for all future commands.
```

### Phase 2: Card Selection + Data Transfer Setup

```
9. CMD7: SELECT_CARD
   SDARG = RCA << 16          (select our card)
   SDCMD = NEW_FLAG | BUSY_FLAG | 7
   Wait for BUSY_FLAG to clear (card enters transfer state)

10. Switch to high-speed clock:
    Write SDCDIV = 8           (27.8 MHz)
    Delay 1ms

11. (Optional Cycle 26+) ACMD6: SET_BUS_WIDTH
    CMD55 with SDARG = RCA << 16, then ACMD6 with SDARG = 2 (4-bit)
    Update SDHCFG |= WIDE_INT_BUS
    Skip for now — 1-bit mode works fine for initial testing.
```

### Phase 3: Read a Sector

```
12. CMD17: READ_SINGLE_BLOCK
    SDARG = sector_number      (SDHC/SDXC: sector number directly)
    SDHBCT = 512               (512 bytes per block)
    SDTOUT = 0x00F00000        (timeout — must set before data command)
    SDCMD = NEW_FLAG | READ | 17
    Wait until NEW_FLAG clears (command accepted)

    Read loop (128 iterations × 4 bytes = 512 bytes):
      Poll SDHSTS bit0 (DATA_FLAG) until set
      Read SDDATA → store word
    
    Check SDHSTS for CRC16_ERROR or FIFO_ERROR.
    Clear SDHSTS by writing 1 to set bits.
```

## Error Handling

After every command:
1. Wait until SDCMD.NEW_FLAG clears (max ~100ms timeout)
2. If SDCMD.FAIL_FLAG or SDHSTS error bits → print register dump over UART, halt

For data reads:
1. If SDHSTS.REW_TIME_OUT: the card didn't respond with data in time
2. If SDHSTS.FIFO_ERROR: we didn't drain the FIFO fast enough
3. If SDHSTS.CRC16_ERROR: data corruption (retry)

## Implementation Plan

### Stage A: sd_poll.S (Cycle 26 target)
- Standalone kernel: UART up, then run SD init, read sector 0
- Print first 16 bytes of sector 0 over UART (MBR magic: 0x55 0xAA at offset 510)
- PASS: sector 0 bytes appear on UART. MBR magic confirms we're reading the right thing.
- This goes in 06-sd/sd_poll.S, linked with 99-recovery infrastructure.

### Stage B: sd_read_file (Cycle 27+)
- FAT32 parser: read BPB from boot sector, walk cluster chain, read file
- Primary goal: open "SEED.BIN" from boot partition → load into memory
- This is the model weight loader path.

### Stage C: sd_write (Cycle 28+)
- CMD24: WRITE_BLOCK (sector write)
- First use: write a status file ("I WAS HERE") to prove write capability
- Later: self-update kernel, save state, write offspring images

## ACMD41 Argument Notes

The exact ACMD41 argument for this SDXC card:
- bit30 = 1: HCS (Host Capacity Support) — we support SDHC/SDXC
- bit28 = 1: XPC (SDXC Power Control) — maximum performance
- bit24 = 0: S18R (1.8V switch request) — keep at 3.3V for simplicity
- bits[23:8] = 0xFF80: voltage window (3.2-3.4V, full range)

SDARG = 0x40FF8000 is the safe, simple value. Some implementations use
0x51FF8000 but the critical bit is bit30 (HCS). Without HCS=1, SDXC card
responds with CCS=0 and you'd try to use byte addressing on a 119 GiB card.

## Timeout Values

- Command timeout: wait up to 100ms (1MHz * 100,000 loop iterations)
- ACMD41 loop: retry up to 1000ms (1000 iterations × 1ms each)
- Data timeout: SDTOUT = 0x00F00000 per Linux driver usage

## Test PASS Criteria

**sd_poll Stage A (QEMU + metal):**

QEMU note: QEMU raspi3ap does NOT emulate BCM2835 SDHOST. Commands to
0x3F202000 will produce guest_errors. QEMU test is build-only (no FAIL on
guest_errors). On-metal test is the real gate.

On-metal PASS:
1. UART shows "SD_INIT_OK" after ACMD41 loop completes
2. UART shows "CMD17_OK" after sector 0 read completes
3. UART shows sector 0 bytes 510-511 = "55 AA" (MBR signature)

**What I'll tell the human:**
After sd_poll image is built: same tryboot protocol as Test 3. Human runs
`sudo reboot "0 tryboot"`, UART shows SD_INIT_OK → CMD17_OK → MBR bytes.
If it hangs on "ACMD41..." loop: card initialization timing issue (adjust delays).
If it hangs after CMD17: FIFO read timing issue.

## What Changes In config.txt

None needed for SD access from bare metal — SDHOST is always powered on and
clocked even before Linux. The controller is in whatever state Linux left it
(idle, card selected in transfer state with RCA assigned). 

Initial approach: full reinit sequence (reset controller, re-run CMD0 through
CMD7). This is safer than trying to inherit Linux's initialized state.
