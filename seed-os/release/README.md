# Seed Unified Kernel — Cycle 35 Release

## What This Is

Bare-metal AArch64 kernel for Raspberry Pi Zero 2W (BCM2835/BCM2837).

Covers: EL2→EL1 drop, PL011 UART init, watchdog stop, ACT LED, SDHOST SD card init, sector-0 read.

## How To Flash

The tryboot slot is already populated from previous cycles. The kernel is already at `/boot/firmware/seed/kernel8.img`.

To test: run the reboot on the Pi from within Linux:

```
sudo reboot "0 tryboot"
```

The Pi will boot this kernel once. If it succeeds, the next manual reset returns to Linux (tryboot is one-shot).

## What You Should See On UART (USB-UART adapter, 115200 8N1, GPIO 14 TX / GPIO 15 RX)

### Happy path (SD card working):
```
ALIVE
WDOG_STOP
SD_START
SDHSTS_PRE=XXXXXXXX
SD_P0
CMD0_OK
CMD8_RSP=000001AA
CMD8_OK
ACMD41_RDY
CCS=1
CMD2_OK
RCA=XXXX
CMD7_OK
CLK_HI
SD_INIT_OK
CMD17_OK
MBR: 55 AA
SD_PASS
```
ACT LED blinks ~1 Hz.

### If UART is silent but ACT LED blinks:
UART init failed. GPIO mux or baud rate issue. Check USB-UART adapter is on 3.3V, check GPIO 14 (TX) pin.

### If SD init fails:
You will see one of these error sentinels followed by register dumps:
- `ERR_CMD8_TIMEOUT` — card not responding to CMD8 (SDHC/SDXC probe)
- `ERR_ACMD41_TIMEOUT` — card not ready after ACMD41
- `ERR_CMD2_FAIL` — CID read failed
- `ERR_CMD3_FAIL` — RCA assignment failed
- `ERR_CMD7_FAIL` — card select failed
- `ERR_CMD17_TIMEOUT` — data read timeout (sector 0)

Each error dumps: `SDCMD=XXXXXXXX`, `SDHSTS=XXXXXXXX`, `SDEDM=XXXXXXXX`

### If nothing at all:
Watchdog resets Pi within 10 seconds → back to Linux. Check tryboot config.

## Baud Rate Note

UART clock: 48 MHz (set by `init_uart_clock=48000000` in `/boot/firmware/config.txt`).
IBRD=26, FBRD=3 → 115179 Hz (error < 0.02% from target 115200).

If UART shows garbage: possibly 24 MHz clock. Use boot_test3_24m.img (IBRD=13) to confirm.

## ACT LED Diagnostic Codes (if UART fails)

ACT LED = GPIO 29.
- ~1 Hz blink = alive, reached WDOG_STOP (no SD yet)
- Fast blink (continuous) = panic/fault

## What Comes Next

If MBR: 55 AA appears → SD reads work → next kernel adds FAT32 parser to find and load GGUF model weights → bare-metal inference.

If SD fails → report exact error sentinels + register dumps → diagnose SDHOST timing.

## Files

- `kernel8.img` — 7208 bytes, AArch64 bare-metal kernel
- `config.txt` — minimal tryboot config (arm_64bit=1)
- `README.md` — this file
