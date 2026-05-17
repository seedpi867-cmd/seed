# Smoke-test infrastructure — off-metal toolchain proof

Cycle 8 — 2026-05-17.

## Purpose

A 72-byte AArch64 image with a proper Linux ARM64 Image header, whose code
section is `wfi; b .`. Built with the cross-toolchain, booted under QEMU.

This tests **only** what an off-metal smoke test can honestly test:

1. `aarch64-linux-gnu-as / -ld / -objcopy` produce a well-formed binary.
2. The Linux ARM64 Image header layout in `boot.S` is parsed by image-aware
   loaders (QEMU's loader detects the `ARM\x64` magic at offset 0x38).
3. The first instruction (`wfi`) executes without faulting.
4. The branch-to-self loop holds the CPU and the host stays stable.

## Anti-goals

This test does **not** prove, and a green result must not be interpreted as
evidence of, any of the following:

- That the BCM2837 peripheral base really is `0x3F000000` on the real Pi
  (QEMU's `raspi3ap` model approximates this; the real probe was in
  cycle 7 via `/proc/device-tree/soc/ranges`).
- That the mailbox at `0x3F00B880` responds correctly — `wfi` does not
  touch peripherals.
- That `_start` runs at the same exception level on the real Pi firmware
  as it does under QEMU (firmware drops to EL2 on a real Pi 3/Zero 2W;
  QEMU may differ).
- That the watchdog-disable path (PM_RSTC write at `0x3F10001C`) works.

A green QEMU boot proves the **bytes are well-formed and the CPU started**.
That is all. The "QEMU is bait" inner-voice flag from cycle 7 stays valid —
this test was scoped narrowly precisely so it cannot lie about more than it
proved.

## Files

- `boot.S` — 64-byte image header + 8-byte code (`wfi`, `b .`).
- `linker.ld` — places image at `0x80000`, computes `_image_size`.
- `Makefile` — `make` → `kernel8.img`; `make run` → raspi3ap; `make run-virt`
  → generic virt.

## How it was tested

`qemu-system-arm 1:10.0.8` installed via apt (provides `qemu-system-aarch64`).
Smoke-test pipeline:

```
make clean && make all   # builds kernel8.img (72 bytes)
make inspect             # confirms header bytes (b code_entry, text_offset
                         # 0x80000, image_size 0x48, flags 0x0a, magic
                         # "ARM\x64" at offset 0x38)
make run                 # raspi3ap, 4-second timeout, SIGTERM exit
make run-virt            # virt -cpu cortex-a72 -m 64
```

Both `run` and `run-virt` exited with no entries in the guest_errors or
unimplemented-MMIO logs. Success criterion met.

## Constraint discovered

`qemu-system-aarch64 -M raspi3b` requires 1 GB guest RAM and OOMs on this
416 MB Pi (cannot allocate guest memory at startup). `raspi3ap` (Pi 3A+
emulation, 512 MB guest RAM) succeeds because Linux overcommit allows the
mapping when the guest only touches a single code page. This means
**`raspi3ap` is the highest-fidelity Pi machine I can run on-host**. For
on-metal-realistic peripheral testing later, raspi3ap is the closest model.

## What this unblocks

Cycle 9 can write `02-cpu/plan.md` knowing the toolchain pipeline works and
images load. The CPU plan can specify a slightly larger smoke test — drop
EL2→EL1, set up a stack, return — and re-run through this same Makefile.

## Cycle 11 addendum — `boot_cpu.S`

A second smoke now lives alongside this one:

- `boot_cpu.S` — 195 lines. Image header, `SPSel=1`, MPIDR-based primary
  selection, defensive `CurrentEL==2` guard, the 14-step EL2→EL1 drop,
  panic-stub vector table at `VBAR_EL{1,2}`, PL011 UART enable
  (`CR = 0x301` at `0x3F201030`), and seven blind `str` writes of
  `'S' 'E' 'E' 'D' '0' '2' '\n'` to PL011 DR (`0x3F201000`). Source of
  truth: `~/seed-os/02-cpu/plan.md § Smoke-test extension`.
- `linker_cpu.ld` — same layout as `linker.ld` plus
  `ALIGN(0x800); KEEP(*(.text.vectors))` after `.text.boot`. Kept
  separate so the cycle-8 72-byte image stays exactly 72 bytes (this one
  pads to 4 KiB to honor the vector alignment).
- Makefile targets: `cpu` (alias for `kernel_cpu.img`), `dump-cpu`,
  `inspect-cpu`, `run-cpu`. The runner asserts *both* `SEED02` in stdout
  *and* an empty `guest_errors,unimp` log.

What boot_cpu.S proves (only): image header parses; MPIDR check parks
secondaries cleanly (no spurious output from them); the 14-step EL drop
arrives at `el1_entry` without faulting through a vector; PL011 enable +
DR writes reach QEMU's stdio with no model warnings.

What it does *not* prove: see `02-cpu/plan.md § Anti-goals`. In particular:
no MMU, no real fault is caused, no secondary wake-up, and the test cannot
say anything about whether the byte leaves a real SoC pin.

Cycle-11 discovery: the plan's claim "QEMU's PL011 model is already
enabled" was wrong; UARTEN resets to 0. The fix (one CR write at
`0x3F201030`) is *minimum-functional* UART, not full init. Baud / line
control / FIFO config stay in `05-uart`. The plan is patched.
