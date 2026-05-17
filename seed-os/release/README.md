# Seed Kernel — Cycle 38 Release (FAT32 + GGUF Probe, multi-sector dir scan)

## What This Is

Bare-metal AArch64 kernel for Raspberry Pi Zero 2W (BCM2835/BCM2837).

Covers: EL2→EL1 drop, PL011 UART, watchdog stop, ACT LED, SDHOST SD init, MBR read, FAT32 BPB parse, root directory multi-sector walk (up to 16 sectors × 16 entries), GGUF magic check.

## How To Flash

The tryboot slot is already populated. The kernel lives at `/boot/firmware/seed/kernel8.img`.

Copy the new kernel there:
```
sudo cp /path/to/kernel8.img /boot/firmware/seed/kernel8.img
```

The model weights are already on the boot partition (`/boot/firmware/model.gguf`, 88 MB). No copy needed.

Boot the kernel (one-shot tryboot):
```
sudo reboot "0 tryboot"
```

## What You Should See On UART (USB-UART, 115200 8N1, GPIO 14 TX / GPIO 15 RX)

### Happy path — GGUF found and magic verified:
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
FAT32
PART1=XXXXXXXX
BPB_OK
RDIR=XXXXXXXX
RDIR_OK
GGU:MODEL   
CLUST=XXXXXXXX
GGUF_OK
```
Then ACT LED blinks ~1 Hz.

### If model file not present:
```
...
RDIR_OK
NO_GGU
```
Then ACT LED blinks ~1 Hz. Copy the .gguf file to `/boot/firmware/` and retry.

### If GGUF magic wrong:
```
...
CLUST=XXXXXXXX
47474e55
MAGIC_FAIL
```
(first 4 bytes of cluster printed as hex)

### If FAT32 reads fail:
Any `ERR_CMD17` or `ERR_FIFO` sentinel followed by SDCMD/SDHSTS/SDEDM dumps,
then fast LED blink (panic pattern).

### If UART is silent but ACT LED blinks 1 Hz:
UART init failed. Check USB-UART adapter (3.3V), GPIO 14 (TX) connection.

### If nothing at all:
Watchdog resets within 10 s → back to Linux.

## How FAT32 Works Here

After reading sector 0 (MBR), the kernel:
1. Reads partition 1 start LBA from MBR bytes 454–457
2. Reads the FAT32 BPB from that LBA
3. Parses: SectorsPerCluster, ReservedSectors, NumFATs, FATSz32, RootCluster
4. Computes root directory LBA: `data_start + (root_cluster - 2) * spc`
5. Reads up to 16 directory sectors (256 entries total), printing RDIR_OK for each
6. Walks entries looking for any file with extension "GGU" (bytes 8–10 of SFN)
7. When found: reads the file's first cluster sector, checks bytes 0–3 for 'GGUF'

Note: `RDIR_OK` will print multiple times (once per sector scanned). This is normal —
the boot partition has 54+ files so `model.gguf` is not in the first sector.

The model file copied as `model.gguf` will appear in the FAT32 root dir with
SFN extension "GGU" (FAT32 truncates 4-char extensions to 3).

## Baud Rate Note

UART clock: 48 MHz (set by `init_uart_clock=48000000` in `/boot/firmware/config.txt`).
IBRD=26, FBRD=3 → 115179 Hz (error < 0.02% from 115200).

If UART shows garbage: try `boot_test3_24m.img` (IBRD=13) to test 24 MHz clock.

## Files

- `kernel8.img` — 7808 bytes, AArch64 bare-metal kernel (Cycle 38, FAT32+GGUF, multi-sector dir scan)
- `config.txt` — minimal tryboot config (arm_64bit=1)
- `README.md` — this file
