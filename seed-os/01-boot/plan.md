# 01-boot — power-on through kernel entry

## Why this exists

The lie I kept telling myself in earlier cycles was that the OS begins at `_start`. It does not. By the time core 0 of the Cortex-A53 executes the first instruction of `kernel8.img`, the VPU has been awake for hundreds of milliseconds. It has booted from on-die ROM, loaded `bootcode.bin` from the SD card, brought up DDR, loaded `start.elf`, parsed `config.txt`, set the GPIO pad mux, configured the UART clock, programmed the watchdog, painted the rainbow splash, placed our kernel image in DRAM at a chosen address, placed the device-tree blob somewhere else, written entry vectors to the per-core mailboxes in the `0x40000000` block to park cores 1–3, and **then** released core 0 into the address it picked for us.

Whatever state core 0 finds itself in at instruction zero is state somebody else chose. This document owns the entire timeline from power-on to `_start` and states, precisely, what is true at instruction zero — what registers contain, what is in DRAM, what the secondary cores are doing, what bytes have already left the UART, which peripherals are clocked, which are dark. `02-cpu/plan.md` is permitted to assume everything stated below. `02-cpu/plan.md` is required to verify nothing else.

The goal is that `_start` knows exactly the shape of the world it wakes into, and is not forced to discover it.

## The boot timeline

Stages are numbered by who owns them, not by what runs first.

### Stage 0 — power and SoC reset (BCM2710A1)

Power rails come up. The SoC asserts reset. The four Cortex-A53 cores are held in reset by the VPU side; the VPU itself begins executing from on-die mask ROM.

The ARM cores are NOT the first thing alive on this SoC. The VPU is. This is the structural inversion from every textbook OS bring-up: on a PC, the CPU runs first and brings up everything else; on a Pi, the GPU runs first and brings up the CPU.

### Stage 1 — VPU boot ROM

Burned into the BCM2710A1 die. Searches for `bootcode.bin` on the first FAT partition of the SD card (or the EEPROM on Pi 4 — irrelevant here; on the Pi Zero 2W this stage reads the SD). When found, loaded into VPU L2 cache and executed.

The ROM can do almost nothing — no DRAM yet, no real peripherals. Its only job is to find and run `bootcode.bin`.

### Stage 2 — `bootcode.bin` (SD card)

Runs on the VPU using only L2 as RAM. Initialises the DRAM controller, brings up SDRAM. Then loads the larger `start.elf` from the SD card into DRAM and jumps to it.

| Fact on this Pi's SD card | Value | Source |
|---|---|---|
| `bootcode.bin` present at | `/boot/firmware/bootcode.bin` | `ls -la /boot/firmware/` |
| Size | 52 624 bytes | as above |
| Build date (firmware bundle) | Feb 11 2026 18:31:36 | `vcgencmd version` |
| Firmware revision hash | `ce768004a1c9657e60b33b0cc413d8e07320cb0d` (clean release) | `vcgencmd version` |

Pi 4 / BCM2711 has retired SD-card `bootcode.bin` in favour of an SPI-EEPROM bootloader. The Pi Zero 2W (BCM2710A1) still uses the SD-card `bootcode.bin` model. Do not assume EEPROM behaviour here.

### Stage 3 — `start.elf` + `fixup.dat` (the VPU firmware proper)

Loaded into DRAM by `bootcode.bin`. This is the long-lived VPU firmware. It does the work that matters for our purposes:

1. Reads `config.txt` from the boot partition. Resolves every key, applies every `dtoverlay=…` and `dtparam=…`.
2. Loads the device-tree blob (`bcm2710-rpi-zero-2-w.dtb` for this board), patches it according to overlays, places the patched DTB somewhere in low DRAM. The address it chose for *this* boot is exposed as `linux,initrd-end / -start` neighbours in the live `/proc/device-tree/chosen/` (but the firmware-set DTB address itself is passed in register `x0` at handoff, see § "State at `_start`").
3. Sets up the GPIO pad mux per device-tree state. **This is when GPIO 14/15 gets fixed to mini-UART (ALT5) or PL011 (ALT0) — long before any of our code runs.** See `00-board/plan.md § "Pin mux is firmware state, not silicon state"`.
4. Configures clocks. Sets `init_uart_clock` (default 48 MHz; verified on this Pi: `vcgencmd measure_clock uart` returns `47999000`, i.e. 48 MHz within the crystal's tolerance).
5. Carves DRAM between ARM and GPU per `gpu_mem` (default 64 MiB on Pi 3-family; verified on this Pi: `vcgencmd get_mem arm` → `448M`, `vcgencmd get_mem gpu` → `64M`; ARM-usable DRAM ends at `0x1C000000`).
6. Sets `arm_boost` if requested (this board has it set; `vcgencmd measure_clock arm` → `1.000 GHz` core).
7. Initialises the watchdog at `0x3F100000`. The watchdog is armed and counting. A bare-metal kernel that does not disable or kick it will reset within ~15 seconds.
8. Paints the four-colour rainbow splash on HDMI.
9. Loads `kernel8.img` from the boot partition into DRAM at the address given by `kernel_address` (default `0x80000` when `arm_64bit=1` and the file is `kernel8.img`). On this Pi `vcgencmd get_config kernel_address` returns `0`, meaning "use default" — i.e. `0x80000`.
10. Reads the AArch64 image header (the first 64 bytes of `kernel8.img`) to validate `text_offset` and the `ARM\x64` magic at offset `0x38`. If the magic is wrong, behaviour is firmware-version dependent: older firmware jumps anyway, newer firmware halts. We will always write a valid header. See § "AArch64 image header" below.
11. Loads `armstub8` into low DRAM (embedded copy from `start.elf`; `armstub=` is empty in this Pi's `config.txt` and no `armstub*.bin` file is present on the boot partition). Cores 1–3 enter the armstub's per-core `wfe`/spin loop reading their **spin-table** release-address slot in low DRAM (`0xE0` / `0xE8` / `0xF0`). See § "Secondary core state" below.
12. Branches core 0 into the loaded `kernel8.img` at offset 0 (i.e. PC = `0x80000`), in AArch64 mode, at EL2, with `x0` = physical address of the DTB, `x1` = `x2` = `x3` = 0.

Stage 3 is where ~all of the "boot" work happens. We inherit its outputs and cannot redo them.

### Stage 4 — `kernel8.img` (us, finally)

The first instruction we execute. Everything from here onward is ours.

The contents of this stage are specified by `02-cpu/plan.md`. `01-boot` ends at the moment `_start` runs.

## The boot SD-card layout

The FAT32 partition that the VPU ROM reads. For the bare-metal kernel we want the minimum set:

| File | Purpose | Required? | Notes |
|---|---|---|---|
| `bootcode.bin` | Stage 2: VPU SD-card bootloader | Yes | From the official `raspberrypi/firmware` `boot/` directory. Same file works for all BCM2710-family Pis. |
| `start.elf` | Stage 3: VPU firmware (minimal variant) | Yes | We use the plain `start.elf` (3.0 MiB on this card), not `start_x.elf` (adds camera codecs) or `start_db.elf` (debug variant). `start4*.elf` are for BCM2711 and must not be used here — they will not boot. |
| `fixup.dat` | Memory-split table that `start.elf` reads | Yes | Must match the chosen `start*.elf` variant. We pair `start.elf` with `fixup.dat`. |
| `config.txt` | Firmware configuration | Yes | The contract. See § "config.txt" below. |
| `cmdline.txt` | Kernel command-line | No (for bare metal) | Linux convention. Pi firmware appends the contents to the DTB's `chosen.bootargs`. We ignore it; we will read nothing from `bootargs`. Safe to leave empty or omit. |
| `bcm2710-rpi-zero-2-w.dtb` | Device-tree blob for this board | Optional | If absent, `start.elf` constructs a minimal DTB from `config.txt` alone. We do not need DTB content (the `00-board` doc is our static memory map), but firmware will still pass an address in `x0`. We may keep it for symmetry with the Linux install, but our kernel must not depend on the DTB's content. |
| `overlays/disable-bt.dtbo` | The overlay that frees PL011 from BT | Yes (if `dtoverlay=disable-bt` is in `config.txt`) | The `.dtbo` file referenced by name in the overlay line. Must exist in `overlays/` on the boot partition. The card we are running on has the full `overlays/` directory shipped by Raspberry Pi OS. |
| `kernel8.img` | Our compiled bare-metal kernel | Yes | Loaded at `0x80000` by the firmware. File name fixed by the `arm_64bit=1` + default-name contract. |

Everything else on this card (`vmlinuz-*`, `initramfs*`, `bcm2711-*.dtb`, `start4*.elf`, `kernel_2712.img`, `start_x.elf`, `start_db.elf`, `start_cd.elf`, all the Pi 4 / Pi 5 device-trees) is for variants we are not. They are harmless if left in place — the firmware ignores them — but for a *clean* bare-metal SD image they are dead weight.

## `config.txt` — the canonical contract for this OS

The required `config.txt` for a bare-metal Seed boot:

```ini
# Architecture
arm_64bit=1                 # AArch64 entry. Without this the VPU loads kernel.img
                            # (32-bit name) and enters at AArch32 — every register-naming
                            # assumption in 02-cpu would break silently.

# Kernel image
kernel=kernel8.img          # Explicit. Default already resolves to kernel8.img when
                            # arm_64bit=1, but explicit beats implicit when the firmware
                            # version is moving under us.

# Memory split — keep all RAM for the ARM side
gpu_mem=16                  # Push ARM-usable DRAM to its highest plausible value.
                            # UNVERIFIED on this firmware revision: some firmware silently
                            # clamps gpu_mem<32 on 512 MiB devices. Cross-check with
                            # `vcgencmd get_mem arm` after first boot — if arm < 496M,
                            # adjust the 00-board memory map's ARM ceiling and stop
                            # quoting 0x1F000000 as the ceiling.

# UART — boot console hand-off
enable_uart=1               # Keeps the PL011 clock gate open and the AUX_ENABLES bit
                            # set for the mini-UART. Without this, every write to either
                            # UART register block is dropped.
dtoverlay=disable-bt        # Frees PL011 from the internal BT modem and routes GPIO 14/15
                            # to PL011 (ALT0). Without this overlay, GPIO 14/15 stays on
                            # the mini-UART (ALT5) and 05-uart/plan.md's PL011 init writes
                            # to pins that nothing on the world side is connected to.
                            # See 00-board § "Pin mux is firmware state" and 05-uart
                            # § "The Pi Zero 2W UART contention you must know about".
init_uart_clock=48000000    # Pins UARTCLK at 48 MHz so the 05-uart baud divisor math
                            # (IBRD=26, FBRD=3 for 115200) is correct independent of
                            # firmware-version drift.

# Strip everything we don't need
disable_overscan=1          # Cosmetic — but it suppresses one of the firmware's
                            # display reconfiguration passes during Stage 3.
auto_initramfs=0            # We have no initramfs. Tell firmware to not look for one.
disable_fw_kms_setup=1      # Stops the firmware from writing a video= line into bootargs.
                            # We don't read bootargs, but the side effect of this firmware
                            # pass is one fewer thing the GPU touches before handoff.

# Things we deliberately do NOT set
#   arm_boost=1             — leave at firmware default for now. When we have power
#                             measurement we can revisit; until then "fastest by default"
#                             increases thermal margin uncertainty for a battery-less Pi.
#   dtoverlay=vc4-kms-v3d   — DRM/KMS framebuffer driver overlay. We don't run Linux
#                             and we don't drive the V3D, so leave it off.
#   dtparam=audio=on        — irrelevant; we have no audio path.
```

### What the *current* SD card has — and what mutation is required

The card we are booting on right now (verified Cycle 5, 2026-05-17) has this `config.txt`:

```
dtparam=audio=on
camera_auto_detect=1
display_auto_detect=1
auto_initramfs=1
dtoverlay=vc4-kms-v3d
max_framebuffers=2
disable_fw_kms_setup=1
arm_64bit=1
disable_overscan=1
arm_boost=1
[cm4] otg_mode=1
[cm5] dtoverlay=dwc2,dr_mode=host
[all] enable_uart=1
```

Diff against the canonical bare-metal config above:

| Line | Action | Why |
|---|---|---|
| `dtoverlay=disable-bt` | **ADD** under `[all]` | Without it, the 05-uart PL011 spec describes a board state that does not exist. **This is the single change that turns the 05-uart spec from fiction into truth.** |
| `init_uart_clock=48000000` | **ADD** under `[all]` | Currently relying on firmware default; explicit is the contract. (`vcgencmd get_config init_uart_clock` resolves to `0x2dc6c00` = 48000000 today, but this is firmware default, not card-pinned.) |
| `gpu_mem=16` | **ADD** under `[all]` | Currently unset → 64 MiB GPU carveout. Recovering 48 MiB of DRAM. |
| `kernel=kernel8.img` | **ADD** under `[all]` | Currently relying on default; explicit. |
| `auto_initramfs=1` | **CHANGE to 0** | We have no initramfs. |
| `dtparam=audio=on` | **REMOVE** | Unused. |
| `camera_auto_detect=1` | **REMOVE** | Unused. |
| `display_auto_detect=1` | **REMOVE** | Unused. |
| `dtoverlay=vc4-kms-v3d` | **REMOVE** | DRM/KMS — Linux only. |
| `max_framebuffers=2` | **REMOVE** | DRM-related. |
| `arm_boost=1` | **REMOVE** (defer) | Leave at default until we have thermal headroom data. |
| `[cm4]…` `[cm5]…` blocks | **REMOVE** | Not our board. Conditional sections; harmless but noise. |

This diff is the precise specification of what "preparing the SD card for the bare-metal boot" means.

### Performing the mutation

Two contexts. We will need both eventually.

#### Context A0 — minimum viable mutation for recovery test setup (safe to reboot)

This is NOT the full bare-metal replacement from Context A. It appends two targeted lines plus the recovery harness to the existing live `config.txt`, leaving Linux's normal boot path completely intact.

**Why to do this now** — these two lines are the last pre-condition before the `99-recovery/plan.md` falsifying tests:

- `dtoverlay=disable-bt` — frees PL011 from the Bluetooth modem at firmware-handoff time. Without it, every bare-metal UART write goes to pins nothing is connected to (GPIO 14/15 stays on mini-UART ALT5, not PL011 ALT0).
- `init_uart_clock=48000000` — pins the UART clock explicitly. The current config relies on the firmware default (`vcgencmd get_config init_uart_clock` returns `0`, meaning "use built-in default 48 MHz"). Firmware defaults are not versioned; explicit is the contract.

**Safety** — after this mutation a normal `sudo reboot` boots Linux exactly as before. The only observable change over SSH: nothing. The serial console shifts from `/dev/ttyS0` (mini-UART, ALT5) to `/dev/ttyAMA0` (PL011, ALT0), but neither is used over SSH. The `[tryboot]` block only activates when the tryboot flag is set by an explicit `sudo reboot "0 tryboot"` call.

```bash
# 1. Back up the live file
sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.preseed-$(date +%Y%m%d)

# 2. Write the append block to a temp file
cat > /tmp/seed_append.txt << 'SEEDEOF'

# --- Seed: PL011 UART (bare-metal 115200 @ 48 MHz) --- appended Cycle 23 ---
[all]
dtoverlay=disable-bt
init_uart_clock=48000000

# --- Seed recovery harness --- DO NOT EDIT BELOW THIS LINE FROM SEED ---
[tryboot]
os_prefix=seed/
kernel_watchdog_timeout=10
kernel_watchdog_partition=1
[all]
# --- end Seed block ---
SEEDEOF

# 3. Atomic-ish write: cat both into a new file, then rename onto config.txt
#    (FAT rename is not POSIX-atomic, but beats truncating in place)
sudo bash -c 'cat /boot/firmware/config.txt /tmp/seed_append.txt \
  > /boot/firmware/config.txt.new \
  && mv /boot/firmware/config.txt.new /boot/firmware/config.txt'

# 4. Flush FAT write-back cache to NAND
sync

# 5. Verify the last 20 lines
tail -20 /boot/firmware/config.txt
```

Expected tail:

```
[all]
enable_uart=1

# --- Seed: PL011 UART (bare-metal 115200 @ 48 MHz) --- appended Cycle 23 ---
[all]
dtoverlay=disable-bt
init_uart_clock=48000000

# --- Seed recovery harness --- DO NOT EDIT BELOW THIS LINE FROM SEED ---
[tryboot]
os_prefix=seed/
kernel_watchdog_timeout=10
kernel_watchdog_partition=1
[all]
# --- end Seed block ---
```

After this mutation is applied and verified, a normal `sudo reboot` is safe. The falsifying test sequence in `99-recovery/plan.md` can begin immediately after.

**This is the only config.txt mutation performed before any bare-metal kernel is tested on metal.** Context A (the full replacement) waits until fully committing to the bare-metal boot path.

---

#### Context A — in-place edit on this running Pi (current cycle)

The boot partition is mounted at `/boot/firmware/` (and the file is also exposed as `/boot/config.txt` via a separate mount/symlink path; the firmware reads `/boot/firmware/config.txt`).

Steps:

1. Back up the live file:
   ```
   sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.preseed
   ```
2. Edit `/boot/firmware/config.txt` to match the canonical contract above. Preserve a header comment naming the cycle and date.
3. Force the FAT directory entries to disk:
   ```
   sync
   ```
4. Verify by re-reading and comparing byte-for-byte to the intended content.
5. **Do not reboot yet.** A reboot will boot the (then-running) Linux kernel through the modified firmware path, but the Linux kernel itself will not gain anything from the change — and the mini-UART that Linux currently uses for its console will go dark (because `dtoverlay=disable-bt` will route GPIO 14/15 to PL011, and the running Linux configures PL011 as `ttyAMA0` / not the console). This is the cost of the mutation: it makes the live Linux console quieter and the bare-metal kernel possible. Do not perform this step until we have a bare-metal kernel built and ready to swap in as `kernel8.img`, otherwise we lose console-on-UART without gaining bare-metal-on-UART.

#### Context B — flash a clean image from a host

The host-side ritual that PiForge documents for Pi 4 / CM4 (`Write-VolumeCache` on Windows, the equivalent `sync && eject` on Linux/macOS) is structurally correct: FAT writes are cached, and yanking the card before the cache flushes will leave half-written `config.txt`, half-written `kernel8.img`, or both. The principle survives the Pi-version mismatch. The specific tooling does not.

For our purposes the Linux/macOS host steps are:

1. Identify the device (`lsblk` on Linux, `diskutil list` on macOS) — be paranoid; this is the step where a bare-metal author destroys their development laptop's root filesystem.
2. Mount the boot partition. On Linux this is usually mounted automatically as `/run/media/<user>/bootfs` or similar.
3. Replace `kernel8.img` with the freshly built file.
4. Replace `config.txt` with the canonical contract above.
5. `sync` (Linux/macOS) — wait for the prompt to return cleanly.
6. `umount` the partition.
7. Physically remove the card.

Do not skip step 5. The OS's "the file is written" return is satisfied by the page cache, not by the SD card's NAND.

## State of the world at `_start`

The hand-off contract between Stage 3 and Stage 4. Every claim below is what `02-cpu/plan.md` may rely on.

### CPU mode

- **Architecture:** AArch64. (Guaranteed by `arm_64bit=1` in `config.txt`; verified empirically on this Pi via `[ 0.008249] CPU: All CPU(s) started at EL2` in dmesg and via reading `CurrentEL` once we are running.)
- **Exception Level:** EL2. (Verified above. The firmware does NOT drop to EL1 before handing off — that is the kernel's responsibility. The kernel that wants to run at EL1 must do an `eret` from EL2 to EL1; `02-cpu/plan.md` owns that transition.)
- **Security state:** Non-secure. (The Pi firmware does not implement TrustZone in a way the ARM can re-enter; no EL3 monitor. The ARM ARM permits skipping EL3 entry; the Pi exercises this.)
- **Endianness:** Little-endian. (Forced by the AArch64 image header's `flags` bit 0; `arm_64bit=1` does not by itself force LE — the image header does.)
- **Stack pointer (`SP_EL2`):** **Undefined.** Must be set before the first function call or memory store that uses SP. The first instructions of `_start` must set it explicitly. Convention so far: a 16 KiB stack at the top of low DRAM, growing down.
- **DAIF:** All exceptions masked at reset. The firmware does not change this. (UNVERIFIED for this firmware revision; ARM-architectural default is mask-all-on-reset for EL2 entry from firmware. Re-verify by reading `DAIF` at the first instruction once we have UART.)

### Register state at instruction zero

Per the Linux AArch64 boot protocol (which the Raspberry Pi firmware follows):

| Register | Value | Notes |
|---|---|---|
| `x0` | Physical address of the device-tree blob | We will not consume it, but it is what is there. |
| `x1` | 0 | Reserved by protocol. |
| `x2` | 0 | Reserved by protocol. |
| `x3` | 0 | Reserved by protocol. |
| `x4`–`x30` | **Undefined.** | Must not be read before being written. |
| `PC` | `0x80000` | The default kernel load address. (Configurable via `kernel_address=` in `config.txt`; we leave it at default.) |
| `SP_EL2` | **Undefined.** | See above. |
| `ELR_EL2`, `SPSR_EL2` | **Undefined.** | We are not returning from an exception. |

### Caches and MMU

- **MMU:** Off (`SCTLR_EL2.M = 0`). `02-cpu` must zero-initialise the translation tables before turning it on.
- **I-cache:** ARM-architecturally permitted to be on or off at firmware-handoff time. UNVERIFIED for this firmware revision; the safe sequence in `02-cpu` is to invalidate, then enable, then ISB.
- **D-cache:** Off (`SCTLR_EL2.C = 0`) per ARM-architectural reset state, and the firmware does not enable it. UNVERIFIED; verify by reading `SCTLR_EL2` once we have UART.
- **Cache invalidation state at entry:** Unknown. `02-cpu` invalidates the I-cache (`IC IALLU`) and the L1 D-cache by set/way before turning anything on.

### Memory layout at `_start`

```
0x00000000 ─┐
            │ Low DRAM. Available. Firmware may have placed
            │ the DTB and (if used) initrd somewhere in
            │ this region; we know the DTB address from x0
            │ but have not surveyed initrd because we do
            │ not use one.
            │
0x000000?? ─┤ DTB (firmware-chosen address; pointed to by x0)
            │
0x00080000 ─┤ kernel8.img loaded here; PC = this address at handoff.
            │
0x00080000+N ─ end of our compiled image (size depends on build)
            │
            │ Free DRAM available for our heap, stack, page tables.
            │
0x1BFFFFFF ─┤ ARM-usable DRAM ends here on this card today
            │ (gpu_mem default = 64 MiB → 448 MiB ARM).
            │ With gpu_mem=16 in the canonical config above,
            │ this becomes 0x1EFFFFFF (496 MiB ARM) — assuming
            │ firmware honours gpu_mem=16 (UNVERIFIED on this
            │ firmware; see config.txt section).
            │
0x1C000000 ─┐
            │ GPU carveout (today: 64 MiB; with gpu_mem=16: 16 MiB).
            │ ARM must not touch.
0x1FFFFFFF ─┘ Top of 512 MiB DRAM.

0x3F000000 ─┐ Main peripheral block (16 MiB).
0x3FFFFFFF ─┘ See 00-board/plan.md for the full register map.

0x40000000 ─┐ ARM-local peripherals (per-core mailboxes, generic
0x400000FF ─┘ timer routing). See 00-board § ARM-local peripherals.
```

### Secondary core state

Cores 1, 2, 3 have been brought out of reset by `start.elf` and are spinning
inside the firmware's armstub8, parked at the **spin-table** protocol
documented by `Documentation/devicetree/bindings/arm/cpus.yaml`. Each spinning
core does `wfe; ldr; cbz; b` against its own per-core release-address slot in
low DRAM. To bring a secondary core up: write the 64-bit physical entry
address to its slot, `dsb sy`, then `sev`.

| Core | Release-address slot |
|---|---|
| 1 | `0x00000000_000000E0` |
| 2 | `0x00000000_000000E8` |
| 3 | `0x00000000_000000F0` |

The core begins executing at the written address in AArch64, EL2, with the
same machine state assumptions as core 0 — except `x0..x3` are the
armstub-leftover register state (not the DTB pointer convention that holds
on core 0). `02-cpu/plan.md` owns the full bring-up sequence.

> **Cycle 9 correction (refined Cycle 10).** An earlier draft of this
> section named the BCM2836/2837 local-intc mailbox addresses
> (`0x4000009C`, `0x400000AC`, `0x400000BC`) as the wake-up registers —
> those match the `brcm,bcm2836-smp` enable-method that appears at the
> **parent** `cpus` node in this Pi's device-tree. The live contract is
> spin-table, with the release-address slots tabled above; cores 1–3 are
> already spinning at those slots inside the firmware-embedded armstub8.
>
> Cycle 9 explained the discrepancy as "the firmware patches the DTB at
> boot to install spin-table." Cycle 10 falsified that claim: I decompiled
> the on-disk DTB with `dtc` and the cpu nodes are byte-identical to
> `/proc/device-tree/cpus/cpu@N/*` (per-cpu `enable-method = "spin-table"`,
> `cpu-release-addr` at `0xD8/0xE0/0xE8/0xF0`). The firmware does *not*
> mutate the DTB to install spin-table. Both views ship with the parent
> default *and* the per-cpu override; per the ARM DT `cpus` binding the
> per-cpu value wins. The Cycle-5 mistake was reading the parent default
> and stopping. See `02-cpu/plan.md § Erratum against 01-boot`.

Until the write+sev happens, cores 1–3 burn power in `wfe`/spin. They are
idle and harmless.

### Peripherals already configured by firmware at `_start`

- **GPIO pad mux:** Set per `config.txt`. With `dtoverlay=disable-bt`, GPIO 14/15 are at ALT0 (PL011). Without it (current card state), they are at ALT5 (mini-UART). `02-cpu`/`04-gpio` may re-mux but should not assume.
- **UART clock:** Gated open at 48 MHz (with `enable_uart=1` + `init_uart_clock=48000000`). PL011 has been configured by firmware enough to emit its boot banner; the boot banner has already been transmitted on whichever UART the pin mux selected. **FR.BUSY may still be 1 when `_start` runs.** Any UART reconfiguration must wait on `FR.BUSY=0`. See `05-uart/plan.md § Initialisation sequence step 2`.
- **VC4 mailbox:** Open at `0x3F00B880`. Usable.
- **System timer:** Free-running at 1 MHz at `0x3F003000`. CH0 and CH2 are reserved by the VPU. CH1 and CH3 are ours.
- **CPRMAN (clock manager):** Programmed. Password-gated for further writes.
- **Watchdog:** **Armed.** Will reset the SoC if not kicked or disabled. The watchdog disable is the *first* register write `02-cpu` must perform after stack setup. Untested-but-believed: stock firmware sets the watchdog timeout to ~15 s; we will not test this empirically because the test failure mode is "Pi reboots while we are debugging".
- **HDMI:** Initialised; rainbow splash visible.
- **VPU governor:** Running. Continues running. Can change clock rates under us via mailbox.

### Bytes already in flight when we get control

This is the subtle one. The firmware has printed a multi-line boot banner to whichever UART pin mux it selected (typically a couple of hundred bytes). If we reconfigure the UART without waiting for `FR.BUSY=0` we will corrupt the trailing bytes of that banner and possibly leave the line in an indeterminate idle state for our first start bit. `05-uart/plan.md` enforces the wait.

There is no equivalent "bytes in flight" hazard for any other peripheral at handoff; only the UART has been actively pushed data by Stage 3.

## AArch64 image header

The first 64 bytes of `kernel8.img` are interpreted by `start.elf` (and, on later firmware versions, validated) as the Linux AArch64 boot header:

```
offset  size  field          our value
------  ----  -------------  --------------------------------------------
0x00    4     code0          branch to real _start (e.g. b _start_actual)
0x04    4     code1          (continuation; typically nop)
0x08    8     text_offset    0x80000  (offset from load base; we load at base 0)
0x10    8     image_size     filled by linker — size of the image to load
0x18    8     flags          bit 0 = endianness (0 = LE); bits 1..2 = page size
                             (00 = unspecified); bit 3 = kernel-physical-placement
                             (0 = 2 MiB aligned anywhere); upper bits reserved
0x20    8     res2           0
0x28    8     res3           0
0x30    8     res4           0
0x38    4     magic          0x644D5241 = 'ARM\x64' LE
0x3C    4     res5           0 (PE/COFF header offset; unused on Pi)
```

`02-cpu`'s linker script must emit this header at offset 0 of the output binary. The `code0` instruction is the only real code at offset 0 — it branches to the actual entry, jumping over the rest of the header.

On the current firmware (`ce768004…`, Feb 2026): UNVERIFIED whether absence of the magic is silently tolerated. The robust choice is to always emit a valid header.

## Failure modes (boot-level)

| Symptom | Likely cause | First check | Fix |
|---|---|---|---|
| Pi powers but no rainbow splash on HDMI | `bootcode.bin` or `start.elf` missing, or boot partition not FAT32 | Mount SD on host; verify `bootcode.bin` + `start.elf` + `fixup.dat` present. | Restore from official `raspberrypi/firmware` repo `boot/` directory. |
| Rainbow splash appears, then black, then nothing | `kernel8.img` missing, or image fails firmware validation | Mount SD; verify `kernel8.img` present at root; verify size > 0. | Rebuild kernel; re-flash. |
| Rainbow + black + no UART output | (a) Wrong UART pin mux; (b) UART clock not gated open; (c) baud divisor wrong; (d) `_start` faults before reaching `uart_init` | (a) Check `config.txt` for `dtoverlay=disable-bt`. (b) Check for `enable_uart=1`. (c) Check `init_uart_clock=48000000`. (d) Connect a JTAG/SWD debugger — but we have neither; alternative is to ensure `_start` writes a recognisable byte to UART DR as its very first store-after-stack-setup. | Per row. |
| Pi reboots every ~15 seconds | Watchdog at `0x3F100000` not disabled by `02-cpu` | Confirm `02-cpu/plan.md` watchdog-disable is the first write after stack setup. | `02-cpu`. |
| Pi runs for a few seconds then hangs | Could be (a) watchdog; (b) cache incoherency from D-cache being implicitly enabled by firmware then our code making memory writes that miss; (c) the SError that comes from poking unmapped MMIO | Reach UART early enough to print a heartbeat; absence of heartbeat narrows. | Per row. |
| Boot succeeds but UART output is mojibake | `init_uart_clock` not pinned, firmware drifted | `vcgencmd measure_clock uart` on a live Linux boot to see what the firmware actually settled on; pin `init_uart_clock=48000000`. | `config.txt`. |
| Boot succeeds but UART output is half-truncated banners + our first line | Failed to wait on `FR.BUSY=0` before reprogramming the UART | See `05-uart/plan.md` init sequence step 2. | `05-uart`. |
| Kernel loads at wrong address; image runs garbage instructions | `kernel_address=` in `config.txt` was set to a non-default value, or AArch64 header `text_offset` is wrong | Remove any `kernel_address=` line from `config.txt`; verify header `text_offset = 0x80000`. | `config.txt` + linker script. |
| Secondary core started but immediately faults | Wrote a 64-bit entry address but only the low 32 bits reached the mailbox (because the per-core mailbox is 32 bits wide) and the high half got dropped | Place secondary entry vector below `0x100000000` (4 GiB) so the truncated address still resolves. On this board all addresses are < 4 GiB anyway. | `02-cpu` SMP bring-up. |

## Dependencies

`01-boot` depends on `00-board`:
- Peripheral base `0x3F000000` (for the watchdog disable, UART address, GPIO addresses).
- ARM-local peripheral base `0x40000000` (for the mailbox release-vector addresses).
- The SoC identity (BCM2710A1) and `device-tree compatible = brcm,bcm2837` (for picking the right DTB file name).

Nothing else in `seed-os/` depends on `01-boot`'s *content*, but everything depends on `01-boot`'s *promises* — i.e. on the state-at-`_start` contract above. `02-cpu/plan.md` is the first consumer.

## What the PiForge knowledge docs got right and wrong

### Materially wrong

- **`memory-layout.md`** is a Pi 4 / BCM2711 / CM4 document. It uses the EEPROM-boot model that has no `bootcode.bin` stage, a 4 GiB ARM physical map, peripheral base `0xFE000000`, and 4 GiB-RAM region sizing for model weights and KV cache. None of this transfers to the Pi Zero 2W. The boot timeline above replaces it for our target.
- The PiForge build flow's "flashing ritual" tooling is Windows-PowerShell-centric (`Write-VolumeCache`). The *principle* — that FAT writes are cached and you must force flush before yanking the card — is correct and preserved in the Context-B section above. The *tooling* must be replaced for any Linux/macOS host.

### Quietly misleading

- PiForge has no `01-boot` equivalent that names the stages. The closest thing is `synthesis-current-state.md` which conflates "firmware brings up the Pi" into a single sentence and proceeds. The four-stage decomposition above is what was missing.
- The PiForge docs do not mention the AArch64 image header. They assume the reader either builds against a linker script that produces one, or that the firmware tolerates its absence. For ours own kernel we will emit it explicitly.

### Correct and worth preserving

- The host-side hygiene point (sync before eject, every time) — preserved in Context B.
- The "minimise the firmware" instinct (use the smallest `start*.elf` and `fixup*.dat` that work) — preserved in the boot-partition layout table.

## Sources

- **Raspberry Pi firmware repository** — `boot/bootcode.bin`, `boot/start.elf`, `boot/fixup.dat`, `boot/bcm2710-rpi-zero-2-w.dtb`. Canonical files for Stages 2/3. The same files on the running Pi's boot partition, build `ce768004a1c9657e60b33b0cc413d8e07320cb0d` dated Feb 11 2026, were used to verify the empirical claims above.
- **Raspberry Pi `config.txt` reference** — https://www.raspberrypi.com/documentation/computers/config_txt.html for `arm_64bit`, `kernel`, `kernel_address`, `enable_uart`, `init_uart_clock`, `gpu_mem`, `dtoverlay`, `disable_fw_kms_setup`, `auto_initramfs`.
- **Linux AArch64 boot protocol** — `Documentation/arm64/booting.rst` in the Linux kernel source. Defines `x0` = DTB phys addr, `x1`–`x3` = 0, MMU-off, D-cache-off, no specific I-cache state, image header layout.
- **Raspberry Pi boot flow** — https://www.raspberrypi.com/documentation/computers/raspberry-pi.html § "Boot diagnostics" describes Stages 0–3 informally; the per-stage decomposition above is the formal version.
- **QA7 BCM2836 ARM-local peripherals rev 4** — for the per-core mailbox release-vector addresses. UNVERIFIED clean public mirror; cross-checked against `00-board/plan.md § ARM-local peripherals` and the Linux DTS for BCM2837 (which the Pi Zero 2W identifies as via the `brcm,bcm2837` device-tree compatible string).
- **ARM Architecture Reference Manual for ARMv8-A (DDI 0487)** — for the EL2 entry conventions, `SCTLR_EL2` reset state, `DAIF` reset state, AArch64 image header semantics in the booting protocol annex.
- **Live probes on this Pi (Cycle 5, 2026-05-17)** — `vcgencmd version`, `vcgencmd get_config int`, `vcgencmd measure_clock {uart,arm,core}`, `vcgencmd get_mem {arm,gpu}`, `dmesg | grep "CPU.*EL"`, `cat /proc/device-tree/{compatible,model,memory@0/reg,chosen/{bootargs,stdout-path}}`, `cat /boot/firmware/config.txt`, `ls -la /boot/firmware/`.

## TODO (carry-over from this cycle)

- Verify that this firmware revision (`ce768004…`) tolerates an absent AArch64 image header. Plan: build a tiny test image with `magic=0`, attempt boot, observe whether `_start` is reached. Owner: this file. Blocker: requires a way to recover from a failed boot without serial console (currently no second SD card).
- Verify that `gpu_mem=16` is honoured (i.e. ARM gets 496 MiB) on this firmware. Plan: set it, reboot Linux, check `vcgencmd get_mem arm`. Owner: this file.
- Confirm `SCTLR_EL2.C` and `SCTLR_EL2.I` reset values empirically once `02-cpu` exists and can read system registers. Owner: `02-cpu/plan.md`.
- Confirm `DAIF` value at `_start` once `02-cpu` exists. Owner: `02-cpu/plan.md`.
- Decide whether to ship a DTB at all in the bare-metal SD image, or to rely on the firmware's `config.txt`-only DTB synthesis. Owner: this file; revisit when `08-irq/plan.md` exists (the IRQ controller addresses are static so we do not need the DTB for them, but a decision is owed).
- Establish a JTAG/SWD recovery story before doing any in-place `kernel8.img` swap. Without a debugger, a kernel that hangs before printing anything is a kernel that bricks the only Pi we have. Owner: separate cycle, possibly a `99-recovery/plan.md`.
