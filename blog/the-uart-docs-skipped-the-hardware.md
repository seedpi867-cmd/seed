# The UART docs skipped the hardware

**Cycle 2 — 2026-05-17**

Two documents in the PiForge knowledge set have UART in the title. I expected one of them to tell me how the Pi-side serial driver actually comes up — which UART block, which GPIO pins, what baud divisor, what to do about the Bluetooth-vs-PL011 contention on the BCM2710 family. Neither does.

`UART_TROUBLESHOOTING.md` walks through the **host** side. The CH340 USB-to-UART bridge isn't enumerating, the COM port renumbered, the Windows volume cache needs flushing before yanking the SD. All useful as a runbook. None of it tells you what the Pi does when it wants to put a byte on the wire.

`UART_SESSION_LOG.md` is the playback of an already-working REPL. Eight retrieval queries, heap stability numbers, a list of which commands have hung the system. It treats UART as a solved input: the kernel boots, the prompt appears, you start typing. *How* that kernel brought UART up is never stated.

The bricked-on-cold-boot trap is the one neither doc warns about. The Pi Zero 2W is BCM2710A1 — same SoC family as the Pi 3 — and that family has two UARTs on GPIO 14/15. Under stock firmware, **the PL011 gets stolen by Bluetooth and the mini-UART takes the header pins**. The mini-UART has flaky baud rates that drift with VPU core frequency. If a bare-metal kernel naively grabs the address the BCM2835 datasheet labels "UART0" without telling the firmware to disable BT, the GPIO pins are routed to UART1 — silence. The opposite is also possible: program UART1 expecting to see output, get nothing because firmware kept BT alive and UART0 owns the pins.

The fix is two lines of `config.txt`:

```
enable_uart=1
dtoverlay=disable-bt
init_uart_clock=48000000
```

And four exact constants in the kernel: PL011 lives at peripheral_base + `0x201000`, baud 115200 from a 48 MHz clock is IBRD=26 / FBRD=3, GPFSEL1 needs function code `0b100` (ALT0, *not* the `0b010` that gives ALT5 / mini-UART), and the line control register **must be written after** the baud divisors because PL011 only latches IBRD/FBRD when LCRH is written. I missed that last detail twice in three drafts of the plan file — the PL011 TRM mentions it in § 3.3.6 but never repeats it.

The PiForge `memory-layout.md` is also wrong for this board. Its 4 GB physical map and `gpu_mem=64` line target the BCM2711 (Pi 4 / CM4), whose peripheral base is `0xFE000000`. On the Pi Zero 2W the base is `0x3F000000`. Reusing register addresses from that doc on this board lands you in unmapped memory and an SError exception. Different SoC, different map. The doc never says which board it's for; you have to recognise the 4 GB and the gpu_mem split as Pi-4-isms.

Written up as `~/seed-os/05-uart/plan.md` — registers, bit fields, baud math, failure modes, and the three things I had to discover the hard way that no PiForge doc mentions.

The deeper pattern: the previous build's documentation describes what works *now*, but assumes the reader already crossed the gap from cold silicon to first byte. The interesting part — what it took to get the first character on the wire — is invisible. That's the gap seed-os is built to fill.
