# 00-board — physical hardware, SoC identity, memory map

## Why this exists

Everything else in this OS asserts numeric addresses against this board. A wrong peripheral base, a copied-from-Pi4 register address, a hard-coded RAM ceiling that assumes 1 GB — any of those bricks the kernel before the first byte reaches the host terminal. `00-board` is where the *canonical* facts about the silicon live. Every higher-numbered `plan.md` either reads from this table or restates a single value as a forward declaration and points back here.

## The SoC

| Property | Value | Source |
|---|---|---|
| SoC marking on package | RP3A0-AU (Raspberry Pi-packaged) | Raspberry Pi Zero 2 W product page; element14 SKU `RPI-ZERO-W-V2` |
| Die identity | Broadcom BCM2710A1 | Raspberry Pi documentation "Processors" |
| Architecture family | BCM2710 (same peripheral block as BCM2837 used in Pi 3B/3B+) | BCM2835 ARM Peripherals datasheet preamble; OSDev "Detecting Raspberry Pi Board" |
| Core | 4× ARM Cortex-A53 | ARM Cortex-A53 TRM; Pi product brief |
| Instruction set | ARMv8-A, AArch64 capable; ARM also supports AArch32 mode | ARM ARMv8-A Architecture Reference Manual (DDI 0487) |
| Core clock (stock) | 1.0 GHz | Pi Zero 2 W product brief |
| L1 cache (per core) | 32 KB I + 32 KB D (Pi-shipped Cortex-A53 configuration) | Cortex-A53 TRM § 1.3 — configurable, Pi uses this size; cross-check via `/proc/cpuinfo` on a running stock Pi (TODO) |
| L2 cache (shared) | 512 KB | Pi Zero 2 W product brief; Cortex-A53 L2 controller TRM |
| RAM | 512 MB LPDDR2, PoP-stacked on the SoC package (RP3A0 carries the LPDDR2 die on top of the BCM2710A1) | Pi Zero 2 W product brief |

UNVERIFIED items, flagged for follow-up:
- The exact L1 I/D associativity and line size on this Pi-shipped Cortex-A53. Default per ARM TRM is 2-way set associative, 64-byte lines; assume that until measured. Owner: `02-cpu/plan.md`.
- Whether the L2 is configured for outer-shareable behaviour from reset (this matters when MMU is turned on). Owner: `02-cpu/plan.md`.

## ARM physical address map

The Cortex-A53 cluster sees one flat 32-bit physical address space (the Pi firmware never enables the upper 4 GB region that a Pi 4 / BCM2711 would offer in "full 35-bit" mode — BCM2710 has no such mode at all). The layout below is from the ARM CPU's perspective, not the VideoCore's:

```
0x00000000 ─┐
            │  512 MB main DRAM (LPDDR2 PoP)
0x1FFFFFFF ─┘

0x20000000 ─┐
            │  Reserved / unmapped from the ARM side.
            │  (The legacy BCM2835 peripheral base was 0x20000000 on Pi 1
            │  and the original Pi Zero. BCM2710 relocated it to
            │  0x3F000000; the old base is dead address space on this SoC.)
0x3EFFFFFF ─┘

0x3F000000 ─┐
            │  16 MB peripheral window (VC bus 0x7E000000 mapped here)
            │  GPIO, UART(s), system timer, mailbox, DMA, EMMC, etc.
0x3FFFFFFF ─┘

0x40000000 ─┐
            │  ARM-local peripherals (BCM2836-style block, present on
            │  BCM2836 / BCM2837 / BCM2710).
            │  Per-core mailboxes, generic-timer IRQ routing, core
            │  release vectors. Documented in QA7 "BCM2836 ARM-local
            │  peripherals" rev 4.
0x400000FF ─┘  (only the first ~256 bytes are populated; the rest is
                reserved within this 16 MB region.)

0x40010000 ─… reserved
0xFFFFFFFF ─┘
```

Notes:

- The 512 MB RAM ceiling is fixed by the LPDDR2 die in the RP3A0 package. There is no Pi Zero 2 W variant with a different RAM size.
- `gpu_mem=N` in `config.txt` carves the *top* of the 512 MB region for the VideoCore. With `gpu_mem=16` the ARM-usable RAM ends at `0x1F000000`. We will pin `gpu_mem=16` for this OS — the GPU is unused except as the boot loader. (UNVERIFIED: whether the firmware respects `gpu_mem=8` on 512 MB devices; some firmware versions silently clamp to 16. Owner: `01-boot/plan.md`.)
- The `0x40000000` ARM-local block is *not* part of the BCM2835 ARM Peripherals datasheet. It is a multi-core addition first documented in QA7 for the BCM2836 and inherited by the BCM2710. PiForge's reference docs do not mention it; any SMP work depends on this block.

## Peripheral register map (the 0x3F000000 window)

The VideoCore views these at the bus addresses shown in the leftmost column of the BCM2835 datasheet, beginning at `0x7E000000`. The ARM sees them at `0x3F000000 + (vc_bus_addr - 0x7E000000)`. The offset in column 2 is the form actually used in code on this OS.

| Offset (from `0x3F000000`) | ARM physical | Peripheral | Notes |
|---|---|---|---|
| `0x003000` | `0x3F003000` | System Timer | 64-bit free-running counter at 1 MHz; 4 compare channels (CH0/CH2 used by VPU — leave them alone). Owner: `06-timer/plan.md`. |
| `0x007000` | `0x3F007000` | DMA channels 0–14 | 0x100 stride per channel. Owner: `09-dma/plan.md` (forthcoming). |
| `0x00B000` | `0x3F00B000` | ARM control block | Includes IRQ controller (legacy, pre-GIC) and core control. The legacy IRQ controller is bypassed on multi-core kernels in favour of the `0x40000000` local block. |
| `0x00B880` | `0x3F00B880` | VC4 mailbox | 32 bytes — Read at +0x00, Status at +0x18, Write at +0x20. Used for firmware properties (clock rates, framebuffer setup). Owner: `07-mailbox/plan.md`. |
| `0x100000` | `0x3F100000` | Power management & watchdog | The watchdog WILL fire and reset the SoC if left at default after a few seconds of no kicks; `02-cpu/plan.md` must explicitly disable it on entry. |
| `0x101000` | `0x3F101000` | Clock manager (CPRMAN) | Reads and writes are passworded (`0x5A000000` in the top byte); silently ignored otherwise. |
| `0x200000` | `0x3F200000` | GPIO controller | GPFSELn at +0x00..+0x14, GPSET0 at +0x1C, GPCLR0 at +0x28, GPLEV0 at +0x34, GPPUD at +0x94, GPPUDCLK0 at +0x98. Legacy pull protocol (NOT Pi 4's GPIO_PUP_PDN_CNTRL). Owner: `04-gpio/plan.md`. |
| `0x201000` | `0x3F201000` | PL011 (UART0) | Full PrimeCell. By firmware default this is routed to the Bluetooth modem, not GPIO 14/15 — see § "Pin mux is firmware state" below. Owner: `05-uart/plan.md`. |
| `0x202000` | `0x3F202000` | SDHOST | Legacy SD controller (the GPU uses this to load `kernel8.img`). |
| `0x204000` | `0x3F204000` | SPI0 | Master, full-duplex. |
| `0x205000` | `0x3F205000` | BSC/I2C 0 | I2C controllers are at +0x205000, +0x205200, +0x205400 … +0x205E00 (eight slots, not all populated). |
| `0x215000` | `0x3F215000` | AUX shared registers | `AUX_IRQ` at +0x00, `AUX_ENABLES` at +0x04. **`AUX_ENABLES` is the gate for ALL three AUX peripherals (mini-UART, mini-SPI 1, mini-SPI 2).** Without setting the corresponding enable bit, reads of the mini-UART register block return 0 and writes are dropped — this is the most common "my mini-UART reads zero" trap. |
| `0x215040` | `0x3F215040` | mini-UART (UART1) | 8250-ish, baud derived from VPU core clock (NOT a fixed 48 MHz reference). By firmware default this IS the UART on GPIO 14/15. Owner: a future `0X-mini-uart/plan.md` if we ever ship a kernel that uses it; for now `05-uart/plan.md` deliberately steers around it. |
| `0x215080` | `0x3F215080` | mini-SPI 0 (AUX SPI 1) | |
| `0x2150C0` | `0x3F2150C0` | mini-SPI 1 (AUX SPI 2) | |
| `0x300000` | `0x3F300000` | EMMC/SDHCI | The "modern" SD controller — once `01-boot` hands off, this is the one the kernel uses for filesystem I/O. |

Sources: BCM2835 ARM Peripherals datasheet § 1.2.3 (peripheral base shift) and §§ 2 / 6 / 13 (AUX, GPIO, UART), cross-referenced against `librerpi/rpi-open-firmware` peripheral register map.

UNVERIFIED — I want to confirm against the BCM2837 ARM Peripherals errata (if Broadcom published one separate from BCM2835): whether `AUX_ENABLES` bit 0 gates *all* mini-UART register access (reads included) or only register *writes*. The BCM2835 datasheet § 2.1 says "If clear the mini UART is disabled. That also disables any mini UART register access" which reads as gating both — but the wording is loose enough that a reader could believe reads still go through. The 05-uart plan currently does not depend on the answer (we avoid mini-UART), but anything that ever does — including a fallback boot console — must clarify this. Owner: future mini-UART plan.

## ARM-local peripherals (the `0x40000000` block)

Inherited from BCM2836. The Pi Zero 2 W exposes the same per-core registers as a Pi 3B.

| Offset (from `0x40000000`) | Name | Purpose |
|---|---|---|
| `0x00` | CONTROL | Selects the core-timer reference (Crystal vs APB). Default Crystal at 19.2 MHz. |
| `0x40` | CORE0_TIMER_IRQCNTL | Routing of the ARMv8 generic timer per-core interrupt. |
| `0x50` | CORE0_MAILBOX_IRQCNTL | Per-core mailbox interrupt enables. |
| `0x60` | CORE0_IRQ_SOURCE | Pending IRQ source bits for core 0. Read this at every IRQ entry. |
| `0x80..0x8C` | CORE0..3_MBOX{0..3}_WSET | Mailbox 0–3 write-set registers per core; the canonical SMP wake-up vector lives in `CORE{1,2,3}_MBOX3_WSET`. |
| `0xC0..0xCC` | CORE0..3_MBOX{0..3}_RDCLR | Read-and-clear pair to `_WSET`. |

Why this block matters before we have SMP:
- The ARMv8 generic timer interrupt is delivered through this block, not through the legacy IRQ controller at `0x3F00B000`. Even a single-core polled-IO kernel that wants to use the generic timer reaches here.
- The firmware leaves cores 1, 2, 3 spinning on a `wfe`/`sev` loop checking `MBOX3` for a release address. The kernel brings them up by writing the entry-point address to that mailbox.

Source: QA7 "BCM2836 ARM-local peripherals" rev 4 (Broadcom). UNVERIFIED: I have not located a free public mirror with a verifiable hash — the only copy I can quickly retrieve is reproduced inside the OSDev wiki Raspberry Pi 3 article. Treat addresses above as "ready for cross-check against the QA7 doc as soon as I have a clean copy" — owner: `02-cpu/plan.md` for the wake-up sequence, `08-irq/plan.md` for routing.

## Pin mux is firmware state, not silicon state

This is the part of the board document that most published bare-metal tutorials get wrong, and that the PiForge knowledge set does not cover at all.

At reset the GPIO pad mux is *not* in a fixed configuration. The VideoCore firmware (`bootcode.bin` then `start.elf`) reads `config.txt`, applies device-tree overlays, and *sets up* the pad mux before handing off to the ARM. So which UART the ARM finds wired to GPIO 14/15 is a function of `config.txt`, not a function of the silicon.

Two relevant routings on the Pi Zero 2 W:

| `config.txt` overlay | GPIO 14/15 routed to | PL011 connected to |
|---|---|---|
| (default — no overlay, BT on) | mini-UART (UART1, ALT5) | Internal Bluetooth modem |
| `dtoverlay=disable-bt` | PL011 (UART0, ALT0) | (BT disabled; PL011 freed) |
| `dtoverlay=miniuart-bt` | mini-UART (UART1, ALT5) | Internal Bluetooth modem at a fixed baud rate |

For this OS we always assume `dtoverlay=disable-bt` because the bare-metal kernel never loads the BT firmware blob and we want the better UART. The boot SD card's `config.txt` MUST include:

```
arm_64bit=1
kernel=kernel8.img
enable_uart=1
dtoverlay=disable-bt
init_uart_clock=48000000
gpu_mem=16
```

- `arm_64bit=1` and `kernel=kernel8.img` together select the AArch64 entry path. Without them the firmware loads `kernel.img` and enters AArch32 — every register-naming assumption in `02-cpu` breaks silently.
- `enable_uart=1` makes the firmware leave PL011 powered and configured. With it off, the PL011 clock is gated and writes to its registers do nothing.
- `init_uart_clock=48000000` pins the UART reference clock so `05-uart`'s baud divisor math is correct. The default is 48 MHz in current firmware but this is the only documented contract.
- `gpu_mem=16` minimises the VPU carveout (firmware floor on a 512 MB device).

Anything that reads register addresses for GPIO 14/15 alternate-function bits without first establishing which device sits on those pins is reading a memory map that is **partially incorrect**. The plan files for `04-gpio`, `05-uart`, and (eventually) a mini-UART plan all reference this section.

Cross-reference: see `05-uart/plan.md § "The Pi Zero 2W UART contention you must know about"` for the ALT-code bit pattern.

## Why the VPU clock matters even to a bare-metal kernel

The VPU's clock state is established by `start.elf` from `config.txt` and (in stock Pi OS) by the on-die firmware governor. Two consequences for a bare-metal kernel:

1. **mini-UART baud divisor drifts** if a hardcoded `AUX_MU_BAUD` value is used, because the mini-UART derives baud from the VPU core clock (nominal 250 MHz scaled by `core_freq` and the governor). The PL011 does not — it runs off a separate UART reference clock that `init_uart_clock=48000000` pins.
2. **The mailbox `GET_CLOCK_RATE` property is the only runtime-truthful source for any of the derived clocks.** Anything that needs an accurate clock rate (mini-UART baud, SD-card divisor, V3D rate) must query the mailbox after boot rather than assume a value from the datasheet. Owner: `07-mailbox/plan.md`.

This is why `00-board` does not present a single "definitive" memory map and stops — half of the map is `config.txt`-dependent and the other half is governor-dependent.

## Failure modes (board-level)

| Symptom | Probable cause | First check |
|---|---|---|
| Pi powers but never produces firmware rainbow on HDMI | `kernel8.img` missing, miscapitalised, or `arm_64bit=1` absent. | Mount SD on host; verify file is present and `config.txt` contains both lines. |
| Firmware rainbow appears but no kernel output ever lands on UART | `enable_uart` not set, or kernel is writing to PL011 base while default routing has BT on PL011. | Verify `enable_uart=1` AND `dtoverlay=disable-bt`. |
| All accesses to `0x3F215040` return 0 (mini-UART) | `AUX_ENABLES` bit 0 not set. | Read `0x3F215004` — bit 0 should be 1 before any mini-UART register access. |
| Kernel writes to `0x20201000` cause a hang or SError | Pi 1 / original-Zero peripheral base copied onto BCM2710. | Replace base with `0x3F000000`; this OS is BCM2710-only. |
| Kernel writes to `0xFE201000` cause a hang or SError | Pi 4 peripheral base copied onto BCM2710. PiForge `memory-layout.md` is the usual source of this confusion. | Replace base with `0x3F000000`. |
| SMP cores never start | Per-core release mailbox at `0x4000009C` / `0x400000AC` / `0x400000BC` not written, or written with an AArch32 address. | Write the 64-bit physical entry point as a 32-bit truncated value (the firmware spin-loop in the secondary cores reads a 32-bit word; addresses must fit). |
| Watchdog resets the Pi a few seconds after `_start` | Watchdog at `0x3F100000` was not stopped on entry. | Disable in `02-cpu/plan.md` before any long-running initialisation. |

## Dependencies

`00-board` has none. Everything else in `seed-os/` depends on values stated here.

## What the PiForge docs got right and wrong

### Materially wrong

- **`memory-layout.md`** is a BCM2711 / Pi 4 / CM4 document. Peripheral base `0xFE000000`, 4 GB RAM map, `gpu_mem=64` ARM-usable ceiling at `0xFBFFFFFF`. Every numeric address in that file is wrong for the Pi Zero 2 W. The file's region map for LLM weights, KV cache, etc. is also sized against 4 GB RAM — the Pi Zero 2 W has 512 MB. Any kernel that ports this region map to the BCM2710 must downsize the model, the KV cache, and the scratch; it will not "just work" by changing the peripheral base.
- The "Low Peripheral mode" hand-wave that creeps into Pi 4 tutorials does not apply to the BCM2710. There is no high/low mode here. There is one map.

### Quietly misleading

- The PiForge knowledge set has *no* `00-board` equivalent. Several docs (`ARCHITECTURE.md`, `synthesis-current-state.md`, `runtime-overview.md`) assume the reader knows which SoC is being targeted — and the only place that fact is stated is buried in `memory-layout.md`'s opening line ("BCM2711 CM4, 4GB RAM"), where it doubles as a wrong assertion for a Pi Zero 2 W reader. A first-time bare-metal reader who lands on `ARCHITECTURE.md` cannot tell which Pi they're building for.

### Correct and worth preserving

- The PiForge build flow's separation of host-side flashing (PowerShell, `Write-VolumeCache`) from Pi-side runtime is a sound mental model. That correctness is independent of which Pi is the target. It lives in `01-boot/plan.md` once that file exists.

## Sources

- **BCM2835 ARM Peripherals datasheet** (Broadcom, 2012). §§ 1.2.3 (peripheral base & low-peripheral aliasing), 2.1 (AUX & `AUX_ENABLES`), 6.1 (GPIO function select & legacy pull protocol), 13 (UART0/PL011 register summary). Mirrored at https://datasheets.raspberrypi.com/bcm2835/bcm2835-peripherals.pdf (canonical) and https://www.scs.stanford.edu/~zyedidia/docs/arm/extras/annot/BCM2835-ARM-Peripherals.annot.PDF (annotated).
- **QA7 — BCM2836 ARM-local peripherals rev 4** (Broadcom). Local-peripheral block at `0x40000000`: per-core mailboxes, generic-timer routing. UNVERIFIED clean public mirror; cross-checked against Linux `arch/arm64/boot/dts/broadcom/bcm2837.dtsi` and OSDev wiki.
- **ARM Cortex-A53 Technical Reference Manual** (ARM DDI 0500). Cache structure, IMPLEMENTATION DEFINED options Broadcom selected. § 1.3 cache configuration.
- **ARM Architecture Reference Manual for ARMv8-A** (ARM DDI 0487). Exception levels, system registers, generic timer.
- **Raspberry Pi documentation: Processors** — confirms RP3A0 packaging and Cortex-A53 @ 1 GHz on Pi Zero 2 W. https://www.raspberrypi.com/documentation/computers/processors.html (returned 403 to a scripted fetch on 2026-05-17; content cross-checked via DigiKey product page SC1176 and element14 RPI-ZERO-W-V2 SKU).
- **Raspberry Pi firmware repository** — `boot/bcm2710-rpi-zero-2.dtb`, source DTS in `arch/arm/boot/dts/bcm2710-rpi-zero-2.dts` in the Pi-kernel fork. Confirms default peripheral routing (mini-UART on GPIO 14/15, PL011 on BT) and the `disable-bt` overlay behaviour.
- **`librerpi/rpi-open-firmware` peripheral register map** — independent reconstruction of the full peripheral table. Cross-validated the per-block offsets used above. https://deepwiki.com/librerpi/rpi-open-firmware/10.1-peripheral-register-map
- **Linux kernel** — `drivers/tty/serial/amba-pl011.c` (PL011 driver), `arch/arm64/boot/dts/broadcom/` (DTS hierarchy). Ground-truth working numbers.

## TODO (carry-over from this cycle)

- Verify Cortex-A53 L1/L2 cache parameters by reading the relevant ARM system registers on a stock Pi Zero 2 W (CCSIDR/CLIDR). Owner: `02-cpu/plan.md`.
- Locate and hash-verify a clean public copy of the QA7 BCM2836 ARM-local peripherals document. Owner: this file; resolve before any SMP work.
- Resolve `AUX_ENABLES`-gates-reads question against BCM2837 errata (if it exists) before any mini-UART code is written.
- Decide whether the `0x40000000` local-peripheral block deserves its own directory (e.g. `02-cpu/local-peripherals.md`) or whether `02-cpu` and `08-irq` each restate the registers they need. Lean toward the latter for now — the block is small enough that duplication is cheaper than a third cross-reference target.
