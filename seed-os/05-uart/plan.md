# 05-uart — PL011 serial console

## Why this exists

UART is the first window into the running system. Without it, every bug after `_start` is invisible. The PL011 is the full-featured ARM PrimeCell UART block; on the Pi Zero 2W it is reachable from the GPIO header via pins 8 and 10 (GPIO 14 / GPIO 15). This document specifies the minimum code path to print bytes to a host terminal and read bytes back, at 115200 8N1.

## Target hardware specifics

| Property | Value | Source |
|---|---|---|
| SoC | BCM2710A1 | Pi Zero 2W product brief |
| Peripheral base (physical) | `0x3F000000` | BCM2835 datasheet § 1.2.3 (the BCM2710 keeps the same offsets; Pi 2/3/Zero 2W shift the base from `0x20000000` to `0x3F000000`) |
| PL011 (UART0) MMIO base | `0x3F201000` | base + `0x201000` |
| GPIO MMIO base | `0x3F200000` | base + `0x200000` |
| AUX (mini-UART / UART1) base | `0x3F215000` | base + `0x215000` — relevant only because we must *not* accidentally use this |

> **Forward declaration.** A dedicated `00-board/plan.md` will own the full memory map and the Pi 4 vs Pi Zero 2W base-address difference. Numbers above are stated here so this plan is self-contained.

### Bus address vs ARM physical address — the `0x7E…` ↔ `0x3F…` translation

Every Pi peripheral has two addresses, and almost every Pi document mixes them silently:

| View | Base | Where you see it |
|---|---|---|
| VC4 / VPU bus address | `0x7E000000` | Device-tree node names (`serial@7e201000`, `gpio@7e200000`), BCM2835 ARM Peripherals datasheet ("legacy master view"), most Broadcom documentation |
| ARM physical address (BCM2710) | `0x3F000000` | What our bare-metal load/store instructions must use, what `/proc/iomem` reports |

Translation is a fixed substitution of the high byte. `0x7E201000` in a device-tree node name (PL011) is `0x3F201000` from the ARM. The BCM2835 datasheet was written from the VC4's perspective; the ARM saw the same peripherals at `0x20000000` on Pi 1, `0x3F000000` on Pi 2/3/Zero 2W, `0xFE000000` on Pi 4. **Never paste a `0x7E…` address into ARM code; never paste a `0x3F…` address into a device-tree node name.**

## The Pi Zero 2W UART contention you must know about

The BCM2710A1 has two UART blocks reachable from GPIO 14/15:

- **UART0 = PL011** (full PrimeCell, 16-byte FIFOs, accurate baud, hardware flow control). Linux name: `ttyAMA0`.
- **UART1 = mini UART** (cut-down 8250-ish, baud derived from VPU core clock, no parity). Linux name: `ttyS0`.

Pin mux on GPIO 14/15 is **firmware state, not driver state**. The VPU `start.elf` reads `config.txt` and sets GPFSEL1 before our kernel ever runs:

- Default firmware behaviour on Pi Zero 2W (with BT enabled): GPIO 14/15 → ALT5 = **mini-UART (UART1)**. PL011 is wired internally to the BT modem.
- With `dtoverlay=disable-bt`: GPIO 14/15 → ALT0 = **PL011 (UART0)**. The BT modem is unbound from PL011.

"Not loading the BT driver in bare metal" does **not** free PL011 — the SoC-level pin-mux that points PL011 at the BT modem is set by firmware regardless of what software runs afterwards. A bare-metal kernel can re-route GPIO 14/15 to PL011 by writing GPFSEL1 itself (and that is the right thing to do for trust-nothing posture), but the *physical* peripheral PL011 controls is determined earlier than our `_start`. If `disable-bt` is not in `config.txt`, the firmware boot banner is on mini-UART; switching to PL011 in our kernel will lose that banner unless we deliberately resync.

### Required `config.txt` on the SD boot partition

```
enable_uart=1
dtoverlay=disable-bt
init_uart_clock=48000000
```

- `enable_uart=1` — VPU sets the UART clock to a known rate and enables the peripheral block.
- `dtoverlay=disable-bt` — VPU does not steal PL011 for Bluetooth; PL011 is routed to GPIO 14/15.
- `init_uart_clock=48000000` — pins the UART reference clock at 48 MHz so the baud divisor math below is correct regardless of firmware default drift. (Stock default is 48 MHz on current firmware, but `init_uart_clock` is the only contract.)

> **Current SD card state (Cycle 4, 2026-05-17):** the host Linux install has `enable_uart=1` and `init_uart_clock=0x2dc6c00` (= 48000000) but **does not** have `dtoverlay=disable-bt`. Console is `ttyS0` (mini-UART) on GPIO 14/15. To make this PL011 spec the actual boot console, the bare-metal flashing ritual in `01-boot/plan.md` must append `dtoverlay=disable-bt` to `config.txt` before sealing the SD card.

## Register layout — PL011 (ARM PrimeCell, TRM ARM DDI 0183)

All offsets are from PL011 base `0x3F201000`.

| Offset | Name | Width | Purpose |
|---|---|---|---|
| `0x00` | DR    | 32 | Data Register (write TX, read RX) |
| `0x04` | RSR/ECR | 32 | Receive Status / Error Clear |
| `0x18` | FR    | 32 | Flag Register (status bits) |
| `0x24` | IBRD  | 32 | Integer Baud Rate Divisor (16 bits used) |
| `0x28` | FBRD  | 32 | Fractional Baud Rate Divisor (6 bits used) |
| `0x2C` | LCRH  | 32 | Line Control (word length, FIFO, parity) |
| `0x30` | CR    | 32 | Control (UARTEN, TXE, RXE, …) |
| `0x34` | IFLS  | 32 | Interrupt FIFO Level Select |
| `0x38` | IMSC  | 32 | Interrupt Mask Set/Clear |
| `0x3C` | RIS   | 32 | Raw Interrupt Status |
| `0x40` | MIS   | 32 | Masked Interrupt Status |
| `0x44` | ICR   | 32 | Interrupt Clear |

### Bit fields we use

**FR (`0x18`)** — read-only status

| Bit | Name | Meaning |
|---|---|---|
| 7 | TXFE | TX FIFO empty |
| 6 | RXFF | RX FIFO full |
| 5 | TXFF | TX FIFO full → **block until 0 before writing DR** |
| 4 | RXFE | RX FIFO empty → **block until 0 before reading DR** |
| 3 | BUSY | UART is currently transmitting (FIFO not empty OR shift register not empty) |

**LCRH (`0x2C`)** — line control

| Bits | Name | Value we set |
|---|---|---|
| [6:5] | WLEN | `11` = 8 data bits |
| 4 | FEN | `1` = enable 16-deep FIFOs |
| 3 | STP2 | `0` = 1 stop bit |
| 2 | EPS  | `0` = (don't care, parity off) |
| 1 | PEN  | `0` = parity disabled |
| 0 | BRK  | `0` = no break |

Composed value: `0b0111_0000` = `0x70`.

**CR (`0x30`)** — control

| Bit | Name | Value we set |
|---|---|---|
| 9 | RXE    | `1` = receiver enable |
| 8 | TXE    | `1` = transmitter enable |
| 0 | UARTEN | `1` = UART enable |

Composed value (with bit 7 CTSEn=0 and bit 6 RTSEn=0): `(1<<9) | (1<<8) | (1<<0)` = `0x301`.

**IMSC (`0x38`)** — all interrupts masked off for polling-mode console: `0x000`.

**ICR (`0x44`)** — clear-all value: `0x7FF` (writes 1 to each defined interrupt-clear bit).

## Baud rate math — 115200 from a 48 MHz UART clock

The PL011 generates baud as `UARTCLK / (16 × baud)`. Result has integer and fractional parts; the fractional part is encoded as a 6-bit value (units of 1/64).

```
divisor = 48_000_000 / (16 × 115200)
        = 48_000_000 / 1_843_200
        = 26.041666…

IBRD = 26                         (integer part)
FBRD = round(0.041666… × 64)      (per PL011 TRM § 3.3.6: integer((frac × 64) + 0.5))
     = round(2.666…)
     = 3

Achieved baud = 48_000_000 / (16 × (26 + 3/64))
              = 48_000_000 / (16 × 26.046875)
              = 48_000_000 / 416.75
              ≈ 115179.4 Hz

Error = (115200 − 115179.4) / 115200 = 0.018 %
```

UART tolerance is ±2 % per bit time at worst — 0.018 % is irrelevant. The host CH340 will receive cleanly at 115200.

## GPIO 14 / GPIO 15 — set ALT0 (TXD0 / RXD0)

GPIO function-select register **GPFSEL1** lives at `0x3F200004` and holds 3 bits per pin for pins 10–19.

| Bits | Pin |
|---|---|
| [14:12] | GPIO 14 |
| [17:15] | GPIO 15 |

Function code table (BCM2835 datasheet § 6.1):

| Code | Function |
|---|---|
| `000` | input |
| `001` | output |
| `100` | ALT0 ← UART0 TXD0/RXD0 |
| `101` | ALT1 |
| `110` | ALT2 |
| `111` | ALT3 |
| `011` | ALT4 |
| `010` | ALT5 ← UART1 TXD1/RXD1 (mini-UART — what we are NOT using) |

To set both pins to ALT0, leaving the other pins in GPFSEL1 untouched:

```c
uint32_t v = MMIO32(GPFSEL1);
v &= ~((7u << 12) | (7u << 15));   // clear GPIO14 and GPIO15 selects
v |=  ((4u << 12) | (4u << 15));   // 0b100 = ALT0 on each
MMIO32(GPFSEL1) = v;
```

### Pull-up / pull-down — disable on UART pins

The BCM2835 / BCM2710 family (Pi 0 / 1 / 2 / 3 / Zero 2W) uses the **legacy pull-up/down protocol** via `GPPUD` (`0x94`) and `GPPUDCLK0` (`0x98`). Pi 4 (BCM2711) uses a different newer scheme via `GPIO_PUP_PDN_CNTRL_REG0` — **do not copy Pi 4 examples here**.

Sequence to set pull = off on GPIO 14 and 15:

```c
MMIO32(GPPUD) = 0;                              // 0 = no pull, 1 = pull-down, 2 = pull-up
delay_cycles(150);                              // ≥150 GPIO clock cycles per BCM datasheet § 6.1
MMIO32(GPPUDCLK0) = (1u << 14) | (1u << 15);   // assert clock on the target pins
delay_cycles(150);
MMIO32(GPPUD) = 0;
MMIO32(GPPUDCLK0) = 0;
```

The bare `delay_cycles` is a tight `nop` loop — 150 cycles at 1 GHz is 150 ns, but the spec is in *GPIO clock cycles* (which differ); a count of a few hundred ARM-side nops is safe and a round of 150 is the convention every published Pi UART driver uses.

## Initialisation sequence — full

In order, with the rationale for each step:

```c
// PL011 base and offsets
#define UART0       0x3F201000
#define UART_DR     (UART0 + 0x00)
#define UART_FR     (UART0 + 0x18)
#define UART_IBRD   (UART0 + 0x24)
#define UART_FBRD   (UART0 + 0x28)
#define UART_LCRH   (UART0 + 0x2C)
#define UART_CR     (UART0 + 0x30)
#define UART_IMSC   (UART0 + 0x38)
#define UART_ICR    (UART0 + 0x44)

void uart_init(void) {
    // 1. Disable UART before reconfiguring. Mandated by PL011 TRM § 3.3.7:
    //    "Program the control register CR. The UART must be disabled before
    //     any of the control registers are reprogrammed."
    MMIO32(UART_CR) = 0;

    // 2. Wait for any in-flight transmission from the firmware boot banner
    //    to finish (FR.BUSY = 0). If we reprogram while BUSY=1 we corrupt the
    //    last byte of the firmware's output and may leave the line in an
    //    indeterminate state for the next start bit.
    while (MMIO32(UART_FR) & (1u << 3)) { /* spin */ }

    // 3. Flush the TX FIFO by disabling FIFOs (clearing LCRH.FEN clears the FIFO).
    MMIO32(UART_LCRH) = 0;

    // 4. Route GPIO 14/15 to ALT0 (TXD0/RXD0). See § "GPIO 14 / GPIO 15".
    gpio_set_alt(14, 0);
    gpio_set_alt(15, 0);
    gpio_pull_off(14);
    gpio_pull_off(15);

    // 5. Clear all pending interrupts. Bits in RIS persist across UART
    //    disable; we don't want a stale flag firing the moment we enable.
    MMIO32(UART_ICR) = 0x7FFu;

    // 6. Set baud rate. IBRD/FBRD values are LATCHED only when LCRH is
    //    written (PL011 TRM § 3.3.6) — write IBRD, FBRD, THEN LCRH.
    MMIO32(UART_IBRD) = 26;
    MMIO32(UART_FBRD) = 3;

    // 7. Line control: 8N1, FIFO enabled.
    MMIO32(UART_LCRH) = 0x70u;  // WLEN=11 (8 bits) | FEN=1

    // 8. Mask all interrupts — we are polling.
    MMIO32(UART_IMSC) = 0;

    // 9. Enable: UARTEN | TXE | RXE.
    MMIO32(UART_CR) = (1u << 0) | (1u << 8) | (1u << 9);  // 0x301
}
```

### Byte send / receive

```c
void uart_putc(char c) {
    while (MMIO32(UART_FR) & (1u << 5)) { /* TXFF: TX FIFO full */ }
    MMIO32(UART_DR) = (uint32_t)(uint8_t)c;
}

char uart_getc(void) {
    while (MMIO32(UART_FR) & (1u << 4)) { /* RXFE: RX FIFO empty */ }
    return (char)(MMIO32(UART_DR) & 0xFFu);
}
```

### Memory barriers

Between writes to **different peripherals** (e.g. GPIO then UART), a `dsb sy` is required on ARMv8 so the writes complete in program order from the perspective of the peripheral bus. Within a single peripheral, the AXI fabric on the BCM2710 guarantees write ordering. The bare-metal `MMIO32()` macro on this OS will use `volatile` with an explicit barrier wrapper:

```c
static inline void mmio_write32(uintptr_t addr, uint32_t val) {
    asm volatile ("dsb sy" ::: "memory");
    *(volatile uint32_t *)addr = val;
}
```

A more refined design will demote barriers to `dsb st` and only for cross-peripheral transitions, but the safe default for early-boot UART is unconditional `dsb sy`.

## Failure modes and how to recognise them

| Symptom on host terminal | Likely cause | Verification | Fix |
|---|---|---|---|
| Silence, not even a single byte | Pin mux wrong — GPIO 14/15 still inputs or routed to mini-UART | After `uart_init`, read GPFSEL1: bits [14:12] and [17:15] must both be `0b100`. If `0b010`, you are on UART1 (mini-UART). | Re-check `gpio_set_alt(14, 0)` — function code `4`, not `5`. |
| Silence + Pi appears bricked | Bad image size / boot failure before `uart_init` reached | Cold-cycle; if firmware rainbow splash never appears on HDMI either, image is invalid. | Verify `kernel8.img` MD5 matches built image (see `01-boot/plan.md` flashing ritual). |
| Garbled "snow" characters | Baud divisor wrong — UART clock not 48 MHz as assumed | Set `init_uart_clock=48000000` explicitly in `config.txt`. Alternatively boot Linux briefly and `vcgencmd measure_clock uart` to confirm. | Either fix `config.txt` or recompute IBRD/FBRD for the actual clock. |
| First byte of every transmission lost | Reconfigured UART while FR.BUSY was still 1 from firmware banner | Add scope on TX line; confirm a half-bit-time glitch precedes the first start bit. | Insert the `while (FR & BUSY)` poll before step 3 — already in the sequence above. |
| Loses bytes when host sends fast | RX FIFO overrun — polling too slow | Read `RSR`/`ECR` (`0x04`): the overrun flag is set when bytes drop. | Either implement RX interrupt + ring buffer (later cycle) or enforce host-side flow control by inserting per-byte delays. |
| Echo present but characters wrong | LCRH written before IBRD/FBRD, so old divisor latched | Confirm init writes in order: IBRD → FBRD → LCRH. | Reorder. |
| Output works but stops after a few KB | Watchdog firing because something else hung | Unrelated to UART; see `02-cpu/plan.md` (watchdog disable) and `01-boot/plan.md`. | Out of scope here. |

## Dependencies

- **00-board** — peripheral base `0x3F000000` is asserted here as a forward declaration; canonical home is the board doc.
- **02-cpu** — by the time `uart_init` runs we are in EL1 AArch64 with the stack and BSS set up. UART init does not need the MMU; it works with MMU off.
- **03-mmio** — owns the `mmio_read32` / `mmio_write32` primitives and the barrier policy.
- **04-gpio** — owns `gpio_set_alt(pin, alt)` and `gpio_pull_off(pin)` helpers. UART uses them but does not duplicate the GPFSEL bit-twiddling.

## What the PiForge docs got right and wrong

### What is *missing* entirely

The PiForge knowledge set has *no* document that specifies the Pi-side UART init. The two UART docs are:

- **`UART_TROUBLESHOOTING.md`** — covers the host (Windows + CH340 USB-to-UART bridge) and recovery procedure. Useful as host-side runbook. Does not mention PL011 registers, baud divisor math, GPIO ALT mux, the BT/mini-UART contention, or the `init_uart_clock` config.txt knob. Anyone trying to make UART work on a fresh kernel from these docs alone would be flying blind.
- **`UART_SESSION_LOG.md`** — a test log of an already-working REPL. References the *kernel* image MD5 but says nothing about how that kernel brings UART up. Useful as a behavioural regression baseline, not a build spec.

### What is materially wrong

- **`memory-layout.md`** targets the **BCM2711 (Pi 4 / CM4)**, not the Pi Zero 2W (BCM2710A1). It uses `gpu_mem=64` and the 4 GB RAM map. Peripheral base on BCM2711 is `0xFE000000`; on BCM2710A1 it is `0x3F000000`. Any code that reuses register addresses from this doc on a Pi Zero 2W will hit unmapped memory and either fault silently or trigger an SError. Marked as a board mismatch in `00-board/plan.md` (forthcoming).
- The "UART is reliable" line in `UART_SESSION_LOG.md § Conclusion` is true but uninformative — it tells you the existing kernel's UART works, not how to reproduce that on the Zero 2W. The implicit "of course it works" hides the BT / mini-UART trap that bricks first-time bare-metal builds on the BCM2710 family.

### What is correct and worth preserving

- The host-side facts in `UART_TROUBLESHOOTING.md § 5` ("Key UART facts" — 115200 8N1, no flow control, CH340 bridge) — correct and reusable.
- The flash-and-eject ritual in `UART_TROUBLESHOOTING.md § 7` (`Write-VolumeCache` on Windows) — correct host-side hygiene; lives in `01-boot/plan.md`'s flashing section, not here.
- The image-size soft ceiling note (§ 8) — possibly real, possibly coincidence with `.rodata` layout; flag for re-investigation in `01-boot/plan.md`. Not UART-relevant.

## Verified against running hardware — Cycle 4, 2026-05-17

Re-probed every UART-relevant fact from the host Linux on this Pi Zero 2W. Results that confirm or contradict the spec above:

| Claim in spec | Probe | Result | Verdict |
|---|---|---|---|
| Peripheral base is `0x3F000000` | `cat /proc/iomem \| grep soc` (prior cycle) | Confirmed | ✓ |
| PL011 MMIO base is `0x3F201000` | `dmesg \| grep pl011`: `pl011-axi 3f201000.serial: … ttyAMA1 at MMIO 0x3f201000` | Confirmed | ✓ |
| Mini-UART base is `0x3F215040` | `dmesg`: `bcm2835-aux-uart 3f215040.serial: … ttyS0 at MMIO 0x3f215040` | Confirmed (and the AUX_ENABLES gate at `0x3F215004` sits just below — Cycle 2 memory holds) | ✓ |
| Default Zero 2W GPIO 14/15 mux is mini-UART (ALT5) | `python -c "mmap /dev/gpiomem; read u32 at 0x04"` → GPFSEL1 = `0x00012000` → both pins = `0b010` = ALT5 | Confirmed empirically | ✓ |
| PL011 is bound to BT modem when `disable-bt` is absent | `/proc/device-tree/soc/serial@7e201000/` contains a `bluetooth` child node | Confirmed — the PL011 node has a BT subnode, so the SoC has it routed there | ✓ |
| Firmware default UART clock is 48 MHz | `vcgencmd get_config int \| grep init_uart_clock` → `init_uart_clock=0x2dc6c00` = 48000000; `vcgencmd measure_clock uart` → `frequency(22)=48000000` | Confirmed | ✓ |
| Boot console is PL011 (`ttyAMA0`) | `cmdline.txt`: `console=serial0,115200`; aliases: `serial0 → /soc/serial@7e215040` (the mini-UART). Kernel ring shows `console [ttyS0] enabled`. | **Contradicted.** On this SD card the console is the mini-UART, because `disable-bt` is absent and the PL011 went to BT (and was re-numbered `ttyAMA1`, not `ttyAMA0`). The spec assumes a config that this card doesn't have. | ✗ — flagged in § "Required `config.txt`" |
| `8250.nr_uarts=1` is the kernel-side mini-UART switch | Kernel cmdline contains `8250.nr_uarts=1` | Confirmed (Linux-only, irrelevant once we are bare metal — noted as a cross-check, not a requirement) | ✓ |

The contradicted row is the one that matters: a spec that says "the boot console is PL011" while the actual board boots with the console on mini-UART is a spec that lies about the starting state. The fix isn't to change the spec's target (PL011 is the better hardware choice for production) — it's to make the SD-card-preparation step in `01-boot/plan.md` responsible for adding `dtoverlay=disable-bt`, so that by the time `_start` runs, the board state matches the spec's assumption. That edit is queued for the next 01-boot cycle.

## Sources

- ARM PrimeCell UART (PL011) Technical Reference Manual — ARM DDI 0183G, §§ 3.3.6 (baud divisor), 3.3.7 (init order), 3.3.8 (FR), 3.3.10 (LCRH), 3.3.11 (CR).
- BCM2835 ARM Peripherals datasheet — § 6.1 (GPIO function select & pull-up/down protocol), § 13 (UART). The BCM2710 reuses this peripheral block with the base address shifted from `0x20000000` to `0x3F000000`.
- Linux kernel `drivers/tty/serial/amba-pl011.c` — canonical working init sequence; cross-checked against the init order above.
- Raspberry Pi firmware reference — `config.txt` options `enable_uart`, `init_uart_clock`, `dtoverlay=disable-bt`. https://www.raspberrypi.com/documentation/computers/config_txt.html
- Cross-checked discussion on UART0/UART1 routing on Pi 3 / Zero 2W: https://forums.raspberrypi.com/viewtopic.php?t=392386

## TODO

- `01-boot/plan.md` must specify the SD-card config.txt mutation: append `dtoverlay=disable-bt` and `init_uart_clock=48000000` before the card is sealed. Without this step, the firmware leaves GPIO 14/15 on the mini-UART and the spec's PL011 init sequence is talking to pins the world cannot see. (Filed Cycle 4, blocker for first PL011 "hello" byte.)
- Verify the GPPUD/GPPUDCLK0 cycle-count requirement against the BCM2835 datasheet's exact wording (currently quoted as "≥150 GPIO clock cycles" from secondary sources). Datasheet § 6.1 — confirm wording and units in a `04-gpio/plan.md` cycle.
- Decide whether to keep PL011 polled or move to interrupt + ring buffer once the GIC is initialised. Defer to `08-irq/plan.md`.
- Investigate whether `vcgencmd measure_clock uart` can be replicated bare-metal via the VC4 mailbox property `GET_CLOCK_RATE` (clock ID 2 = UART). If so, the kernel can self-check the UART clock before computing divisors. Defer to `07-mailbox/plan.md`.
