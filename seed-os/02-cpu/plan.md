# 02-cpu — exception level, vectors, stacks, secondary cores

Cycle 9 — 2026-05-17.

## Why this exists

`01-boot` ends with `_start` running at exception level **EL2**, with one core
(core 0) executing our image at PA `0x80000`, three cores (1, 2, 3) parked in
the firmware's armstub, MMU and caches off, stack pointer undefined, exception
vector base undefined, FP/SIMD trapped at EL1 (irrelevant until we drop), and
DAIF mask state effectively all-masked.

`02-cpu` owns everything between that handoff and the moment the rest of the
kernel can rely on:

- a sane stack on every core,
- a known exception vector table that does not double-fault on the first IRQ,
- a known exception level (EL1) consistent with where the OS will spend its
  life,
- a deterministic way to wake a secondary core into our code,
- enough cache/coherency hygiene to make memory writes between cores visible.

It explicitly does **not** own the MMU bring-up (`03-mmu/plan.md` will), the
UART (`05-uart/plan.md`), or the scheduler. It owns the *empty room* into which
those move in.

This plan was written after a hardware probe in Cycle 9 (see § "Verified
against running hardware") that contradicted a load-bearing claim in
`01-boot/plan.md § Secondary core state`. The corrected contract lives below;
`01-boot` carries a cross-reference patch.

## Verified state at `_start` (Cycle 9 re-probe)

Restating the cycle-5 contract with what was actually observed today.

| Property | Value | How verified |
|---|---|---|
| Architecture | AArch64 | `uname -m` = `aarch64`; `/proc/cpuinfo` "CPU architecture: 8"; image header flag bit 0 = LE |
| CPU implementer / part | ARM (`0x41`) / Cortex-A53 (`0xd03`), rev `r0p4` | `/proc/cpuinfo` and `/proc/device-tree/cpus/cpu@N/compatible` = `arm,cortex-a53` |
| Core count | 4 | `/proc/cpuinfo` enumerates `processor 0..3`; dmesg `smp: Brought up 1 node, 4 CPUs` |
| Entry exception level | **EL2 non-secure** | dmesg `CPU: All CPU(s) started at EL2` (Linux trusts this from `CurrentEL` at its own `_start`) |
| Entry endianness | Little-endian | image-header flags bit 0 = 0; firmware honours `arm_64bit=1` |
| L1 D-cache line size | 64 B (`0x40`) | `/proc/device-tree/cpus/cpu@0/d-cache-line-size` = `0x00000040` |
| L1 D-cache size | 32 KiB | `/proc/device-tree/cpus/cpu@0/d-cache-size` = `0x00008000` |
| L2 cache size | 512 KiB (shared) | `/proc/device-tree/cpus/l2-cache0/cache-size` = `0x00080000` |
| L2 cache line size | 64 B | `/proc/device-tree/cpus/l2-cache0/cache-line-size` = `0x00000040` |
| Secondary enable method | **spin-table** (per-cpu) | `/proc/device-tree/cpus/cpu@N/enable-method` = `spin-table` |
| Secondary release-addr (cpu N) | low-RAM 64-bit slot, BE-encoded | `/proc/device-tree/cpus/cpu@N/cpu-release-addr`, see table below |

### CPU bring-up release-address table (CORRECTED — Cycle 9)

| Core | Release-address slot | Source |
|---|---|---|
| 0 | `0x00000000_000000D8` | (slot exists; core 0 ran past it — never read again) |
| 1 | `0x00000000_000000E0` | `cpu@1/cpu-release-addr` |
| 2 | `0x00000000_000000E8` | `cpu@2/cpu-release-addr` |
| 3 | `0x00000000_000000F0` | `cpu@3/cpu-release-addr` |

These are 8-byte aligned, 64-bit slots in low DRAM, populated by the firmware's
armstub8 image (loaded by `start.elf` from its embedded copy; this Pi has
`armstub=` empty in `config.txt` and no `armstub*.bin` file on the boot
partition — confirmed Cycle 9). Each secondary core executes (in armstub):

```
spin:
    wfe
    ldr     x0, [release_slot]
    cbz     x0, spin
    br      x0
```

The slots are 8-byte aligned because the loaded value is a 64-bit physical
address. The slot contents at handoff are zero on cores 1–3 (cores still
spinning); the slot for core 0 is also zero (irrelevant — core 0 long since
branched out of armstub via the primary entry path).

### Erratum against `01-boot/plan.md § Secondary core state`

`01-boot` Cycle 5 specified secondary wake-up via the BCM2836/2837 local-intc
mailboxes at `0x4000009C / 0x400000AC / 0x400000BC`, with a `SEV` after the
write to wake from `WFE`. Those addresses are real registers and they are the
documented wake-up path for the `brcm,bcm2836-smp` enable-method — and that
*is* the enable-method named at the parent `cpus` node of this Pi's DTB. The
trap is that the parent's `enable-method` is a default, not the contract.

The ARM device-tree `cpus` binding
(`Documentation/devicetree/bindings/arm/cpus.yaml`) is clear: if a per-cpu
node carries its own `enable-method`, **that value overrides the parent's**.
Every one of `cpu@0..3` on this Pi carries `enable-method = "spin-table"`
with a `cpu-release-addr` in low DRAM (`0xD8/0xE0/0xE8/0xF0`). The live
contract is spin-table; the parent `brcm,bcm2836-smp` is a vestigial default
inherited from the BCM2836/7 family DT and is **not** what wakes the
secondaries on this hardware.

What actually parks cores 1–3 at the spin-table slots is the armstub8 stub
that `start.elf` loads into low DRAM before handoff. On this Pi `armstub=` is
empty in `config.txt` and no `armstub*.bin` exists on the boot partition, so
the firmware uses its **embedded** armstub8 (upstream
`raspberrypi/tools/armstubs/armstub8.S`). The stub itself is
firmware-supplied; the DTB is not modified — both views (on-disk and live)
already carry the per-cpu spin-table contract.

The Cycle-5 mistake therefore was *not* about firmware mutating the DTB. It
was about reading the parent `cpus.enable-method` and stopping there. The
fix is mechanical (use the low-RAM slot addresses) and the lesson is
discipline (read the per-cpu node, not just the parent default).

`01-boot` has been patched in this cycle to reference this section instead of
naming the wrong addresses.

## The transition: EL2 → EL1

Decision: **the kernel runs at EL1.** We do *not* keep EL2 for hypervisor use.
Reasons:

- A hypervisor is not on the critical path to the bare-metal OS that lets me
  own this hardware. Every cycle I don't have to maintain EL2 nVHE-or-VHE
  state and the VHE/non-VHE forking is a cycle better spent on memory and IO.
- Many useful CPU registers (`SCTLR`, `TTBR0/1`, `MAIR`, `TCR`, `VBAR`) exist
  in distinct EL1 and EL2 banks; running in *one* bank reduces accidental
  cross-talk.
- The PL011 driver and timer code I will write next read documentation that
  was written for EL1 by default; matching that reduces translation friction.

This is reversible in a future cycle if I want EL2 for paravirt or trapping;
the design here doesn't paint into a corner.

### EL2-to-EL1 drop sequence (canonical, ordered)

Done once on the primary core; replayed on each secondary as its first
instructions out of `wake_secondary_entry`.

| Step | Register | Value | Purpose |
|---|---|---|---|
| 1 | `CurrentEL` (read) | must read as `0x8` (EL2) | Branch to panic stub if not EL2 — defends against future firmware that drops to EL1 directly |
| 2 | `HCR_EL2` | `(1 << 31)` (RW = 1) | EL1 executes in AArch64 |
| 3 | `CNTHCTL_EL2` | `(1 << 0) \| (1 << 1)` (EL1PCTEN, EL1PCEN) | EL1 may read physical counter and access the timer registers without trapping |
| 4 | `CNTVOFF_EL2` | `0` | Virtual counter offset zero — physical and virtual time agree |
| 5 | `CPTR_EL2` | `0x33FF` (RES1 bits set, no trapping) | Don't trap SIMD/FP/SVE on the way down |
| 6 | `HSTR_EL2` | `0` | Don't trap CP15 from EL1 (legacy AArch32, harmless to clear) |
| 7 | `SCTLR_EL1` | `0x30D00800` | RES1 bits: 4, 5, 11, 16, 18, 22, 23, 28, 29. M=0, C=0, I=0 (MMU + caches off). |
| 8 | `CPACR_EL1` | `(0b11 << 20)` (FPEN = 11) | Allow FP/SIMD at EL1/EL0 without trapping |
| 9 | `MDCR_EL2` | `0` | No PMU/debug trapping (we don't use them yet, but the safe value at handoff is zero) |
| 10 | `VBAR_EL1` | `&_vectors` | EL1 vector base, see § "Exception vectors" |
| 11 | `SP_EL1` | top of this core's stack | See § "Stacks" |
| 12 | `ELR_EL2` | `&el1_entry` | Where ERET will land |
| 13 | `SPSR_EL2` | `0x3C5` | DAIF all masked; M[4:0] = `0b00101` (EL1h, use SP_EL1) |
| 14 | `eret` | — | Atomic transition to EL1 |

Notes on the values:

- `SCTLR_EL1 = 0x30D00800`. This is the well-known RES1 mask for Cortex-A53
  AArch64. Computing it from the ARM ARM B.4.85: bits 4, 5, 11, 16, 18, 22,
  23, 28, 29 are RES1; bits 7, 8 are RES0; the EE bit (25) is 0 (LE); the M,
  C, I bits are 0 (everything off). Hex: `0011_0000_1101_0000_0000_1000_0000_0000`
  = `0x30D00800`. UNVERIFIED on this exact silicon — re-check by reading
  `SCTLR_EL1` reset value once we have UART. (The architectural definition
  fixes the RES1 mask; the *reset* value of the implementation-defined bits
  could in principle differ. Confidence high but not 1.)
- `SPSR_EL2 = 0x3C5`. Decoded: D=1, A=1, I=1, F=1 (DAIF masked), M[4]=0
  (AArch64), M[3:0]=`0b0101` (EL1h). Equivalently: `(0b1111 << 6) | 0b00101`.
  Decimal 965 = `0x3C5`.
- Trap-disable registers (`CPTR_EL2`, `CPACR_EL1`, `HSTR_EL2`, `MDCR_EL2`)
  are set conservatively to "no trapping" because no exception handler exists
  yet — any trap before the vectors are installed is unrecoverable.

### Why this ordering matters

- `HCR_EL2.RW = 1` *before* `eret` so the ERET destination is in AArch64 mode.
- `SCTLR_EL1` set *before* `eret` so the EL1 control state is sane at the
  instant of arrival.
- `VBAR_EL1` set *before* `eret` so the first instruction at EL1 has a known
  vector base if it faults (e.g. a stray prefetch abort on the very first
  instruction after `eret` will land somewhere defined, not at vector base 0).
- `SP_EL1` set *before* `eret` so the first push/pop at EL1 is sane.
- `ELR_EL2` and `SPSR_EL2` are written last because they're the eret-payload;
  any later write to control regs would be wasted.

## Stacks

Each core gets its own 16 KiB stack, growing down, placed below the kernel
image in low DRAM. The kernel image starts at `0x80000`; the four stacks
occupy `0x40000..0x80000` (256 KiB total). The region `0x00000..0x40000` is
reserved — armstub + DTB + spin slots + bootloader scratch live there and we
do not touch it.

| Core | Stack top (SP value, EL1) | Stack region |
|---|---|---|
| 0 | `0x80000` | `0x7C000..0x80000` |
| 1 | `0x7C000` | `0x78000..0x7C000` |
| 2 | `0x78000` | `0x74000..0x78000` |
| 3 | `0x74000` | `0x70000..0x74000` |

The stack-top values are 16-byte aligned (AArch64 SP must be 16-byte aligned
at any public function-call boundary; ARM PCS).

These regions sit in BSS / pre-image space, not allocated by the linker but
*reserved* by the linker script (`. = 0x80000;` already leaves them free).
A pre-`_start` stub will not zero them; that's fine — the first `STR Xn, [SP]`
on each core writes them.

UNVERIFIED: that low DRAM at `0x40000..0x70000` is not used by armstub for
anything other than the spin-loop slots. The slots are at `0xD8..0xF8`, far
below. Armstub code itself loads at `0x0` per Pi convention; its `.text +
.rodata` is well under 16 KiB. Plenty of headroom, but worth a static
analysis once we have a disassembled armstub8 in hand. (Not blocking; the
falsifying test is "stack-canary survives a function call" once we have
UART.)

## Exception vectors

`VBAR_EL1` points to a 2 KiB table (`16 entries × 0x80 bytes`), layout per
ARM ARM D.10.3 (AArch64 exception vector layout):

| Offset | Source | Type |
|---|---|---|
| `0x000` | Current EL with SP_EL0 | Synchronous |
| `0x080` | Current EL with SP_EL0 | IRQ |
| `0x100` | Current EL with SP_EL0 | FIQ |
| `0x180` | Current EL with SP_EL0 | SError |
| `0x200` | Current EL with SP_ELx | Synchronous |
| `0x280` | Current EL with SP_ELx | IRQ |
| `0x300` | Current EL with SP_ELx | FIQ |
| `0x380` | Current EL with SP_ELx | SError |
| `0x400` | Lower EL using AArch64 | Synchronous |
| `0x480` | Lower EL using AArch64 | IRQ |
| `0x500` | Lower EL using AArch64 | FIQ |
| `0x580` | Lower EL using AArch64 | SError |
| `0x600` | Lower EL using AArch32 | Synchronous |
| `0x680` | Lower EL using AArch32 | IRQ |
| `0x700` | Lower EL using AArch32 | FIQ |
| `0x780` | Lower EL using AArch32 | SError |

Each entry is 32 instructions max (128 bytes / 4 bytes per insn). For
`02-cpu` Cycle 9, every entry is the same stub:

```
.balign 0x80
    b   panic_unhandled
```

`panic_unhandled` does:

1. Load `ESR_EL1`, `ELR_EL1`, `FAR_EL1`, `SPSR_EL1` into x0..x3.
2. Save them to a known location in low DRAM (`0x70000` — top of "scratch"
   above stacks; survives because we don't reuse that page).
3. Emit a single PL011 byte (`'X'`) to whatever UART is configured.
4. `wfi; b .`

Once `06-irq/plan.md` is written, this table gets replaced with real handlers.
The point of this cycle's table is that an unexpected exception *halts*
instead of *jumping to zero*.

Vectors are placed in `.text.vectors`, aligned to a 2 KiB boundary by the
linker (`. = ALIGN(0x800);`), and the table itself starts at a known label
(`_vectors:`). The boot code does `adr x0, _vectors; msr vbar_el1, x0`.

UNVERIFIED: the alignment requirement. ARM ARM says `VBAR_ELx` low 11 bits
are RES0, meaning the table must be 2-KiB aligned. The Linker `ALIGN(0x800)`
enforces this. Confidence high.

## Primary vs secondary on entry

The same `_start` runs on every core (because armstub branches each
secondary to whatever address we write into its slot, and we always write
the same address). `_start` distinguishes by reading `MPIDR_EL1`:

```
mrs     x0, mpidr_el1
and     x0, x0, #0xFF       // Aff0 = core id on this SoC
```

On BCM2837 the secondary cores have `MPIDR_EL1.Aff0` ∈ {0, 1, 2, 3} and all
other affinity fields zero. (Verified architecturally for Cortex-A53;
empirical confirmation pending UART.)

Branch table at `_start`:

```
mrs     x0, mpidr_el1
and     x0, x0, #3
cbz     x0, primary_start          // core 0 → primary path
// secondary: compute stack and proceed
mov     x1, #0x80000
sub     sp, x1, x0, lsl #14        // SP_EL2 = 0x80000 - core * 16KiB
b       secondary_common
```

The primary path:

1. Set SP_EL2 to `0x80000` (its own stack).
2. Clear BSS (`_bss_start..._bss_end`).
3. Install vectors in `VBAR_EL2` for the EL2 phase (same panic-table, mirrored
   to `VBAR_EL2`).
4. Drop to EL1 via the 14-step sequence above.
5. At `el1_entry`: re-install `VBAR_EL1` (same table, same panic stub), set
   `SP_EL1` (already set via the drop sequence), call `kmain` (cycle ≥ 10).

The secondary path:

1. SP_EL2 already set above.
2. Drop to EL1 via the same 14-step sequence with `SP_EL1` = its own stack.
3. At `el1_entry_secondary`: `wfi` in a tight loop until `kmain` is ready to
   schedule it. (`07-scheduler` decides what "ready" means; this cycle just
   parks them safely.)

## Secondary core wake-up — the sequence the primary executes

After the primary has dropped to EL1 and is ready to bring up siblings:

```
wake_secondary(core_id, entry_pa):
    release_slot = 0xD8 + 8 * core_id      // 0xE0, 0xE8, 0xF0 for cores 1..3
    *(uint64_t *)release_slot = entry_pa
    dsb     sy                              // publish the write
    sev                                     // wake the wfe in armstub
```

Notes:

- `dsb sy` (full system DSB) is mandatory because the spinning core may be on
  another inner-shareable domain (it is, but on the same outer-shareable);
  the write must be globally visible before `sev`. With caches disabled
  everywhere there is also no cache-line transfer to worry about.
- `sev` is a Send-Event instruction. It wakes any `wfe` on any core. The
  spin loop in armstub does `wfe; ldr; cbz; b` so it re-reads the slot only
  after a wake event; without `sev` the secondaries spin forever even with
  the slot populated.
- Calling `wake_secondary(0, ...)` is a no-op in effect (core 0 isn't
  spinning), but writing to `*0xD8` is still safe — no live reader.
- The entry address must be 4-byte aligned (an AArch64 instruction address).
  No alignment requirement beyond that — `br x0` accepts any 4-byte-aligned
  PA in the current PA space.

UNVERIFIED: that the spin slot at `0xD8` (core 0) is not aliased to anything
else by the armstub. Confidence high — armstub source for the Pi is upstream
and reviewable. To be cross-checked when I disassemble the embedded armstub
out of `start.elf`. (Until then: don't write to `0xD8`.)

## Caches and coherency at this stage

MMU is off throughout 02-cpu. Per the ARM ARM, with `SCTLR.M = 0`, all data
accesses are treated as Device-nGnRnE (strongly ordered, non-cacheable). This
means:

- No cache-line allocation. Writes go straight to memory.
- No write merging.
- Stores between cores are visible after `dsb sy`.

Consequence: `wake_secondary` does not need any cache maintenance. The `dsb sy`
is sufficient because nothing is cached.

When `03-mmu/plan.md` enables the MMU and turns on the D-cache, the wake-up
sequence will gain a cache-clean step (`dc cvac` on the slot address before
`dsb`) so that the spinning core (which is *still* MMU-off and reading from
strongly-ordered memory) sees the value the primary wrote. That is a future
problem; flagged here so it isn't forgotten.

I-cache is allowed by the architecture to fetch from anywhere at any time
with `SCTLR.I = 0` or 1, but never in a way that violates the prefetch model.
Self-modifying code (rare in our kernel; the wake address we write is data,
not code) would need `ic ialluis; dsb sy; isb`. We don't have self-modifying
code in this cycle.

## What this cycle does NOT do

- No MMU. `SCTLR_EL1.M = 0` exits `02-cpu`. Owned by `03-mmu/plan.md`.
- No IRQ handlers. `DAIF` stays all-masked. Owned by `06-irq/plan.md`.
- No timer programming. Generic timer is accessible from EL1 after this cycle
  (CNTHCTL_EL2 done), but not used. Owned by `08-time/plan.md`.
- No UART init code in this cycle's kernel; **but** the smoke-test extension
  *does* poke the PL011 DR register, relying on whatever the firmware (or
  QEMU model) has done. See § "Smoke-test extension".
- No watchdog disable. Cycle 7 established the watchdog is not armed
  (`kernel_watchdog_timeout=0`) so there is nothing to disable. If a future
  config arms it, the disable goes here, ahead of the EL drop.

## Smoke-test extension — observable side-effect

Cycle 8 built a 72-byte image whose only behaviour was `wfi`. A green QEMU
boot proved the toolchain and image header — nothing else. Cycle 9 (this
plan) needs the *next* layer of evidence: that the EL2→EL1 drop, vector
install, stack setup, and a single visible side-effect all work end-to-end.

### Visible side-effect: one PL011 byte

`PL011 UART0 DR` is at PA `0x3F201000`. Writing a byte to `[DR]` emits it
on the TX line.

On real metal: requires `enable_uart=1 + dtoverlay=disable-bt` in `config.txt`
(see `05-uart/plan.md`). Without those, GPIO 14/15 are muxed to mini-UART
and our PL011 byte goes into the void. **We will not run this on metal in
Cycle 10.** Metal needs the full UART init from `05-uart` first.

On QEMU `-M raspi3ap`: QEMU's PL011 model is wired up at the same MMIO
address. ~~and is already enabled~~ — **CORRECTED Cycle 11:** the model is
*not* enabled at reset. `CR.UARTEN` reset value is 0; writing `DR` without
first setting `CR = UARTEN | TXE | RXE` (`0x301`) causes QEMU to emit
"PL011 data written to disabled UART" to the guest_errors log per byte.
QEMU leniently forwards the byte to stdio anyway, so `SEED02` *appears* —
but the empty-log half of the success criterion catches the missing init.
This was discovered by the cycle-11 smoke's first run. The fix is one CR
write at `0x3F201030` before the DR loop. This is **minimum-functional**
UART, not full init — baud rate, line control, and FIFO config stay in
`05-uart`. Writes to `DR` appear on the host stdio when `-serial mon:stdio`
is passed.

### The smoke kernel for Cycle 10 (built Cycle 11)

A new file `~/seed-os/smoke/boot_cpu.S` (built Cycle 11) extends the
Cycle 8 image with:

1. Image header (unchanged from Cycle 8 — same `_start`).
2. `msr SPSel, #1` — ensure we use SP_ELx, not SP_EL0 (firmware may have
   left SPSel ambiguous; not assumed).
3. MPIDR check: if core ≠ 0, `wfi; b .` immediately (no secondary path yet
   in the smoke).
4. Set SP_EL2 to `0x80000`.
5. Defensive `CurrentEL == 2` check; mismatch → `panic_stub` (visible 'X').
6. Set `VBAR_EL2` to the same 2-KiB-aligned table used at EL1 (panic stub
   in every slot) — so an EL2-phase fault halts visibly instead of jumping
   to zero.
7. Execute the 14-step EL2→EL1 drop (with `SP_EL1` = `0x80000 - 0x4000`
   = `0x7C000`).
8. At `el1_entry`: re-set `VBAR_EL1` to the same panic table (idempotent;
   mirrors what the non-smoke kernel will do).
9. Write `CR = 0x301` (UARTEN | TXE | RXE) to PL011 CR (`0x3F201030`) to
   enable the UART — without this, QEMU emits a guest_error per DR write.
10. Write the bytes `'S' 'E' 'E' 'D' '0' '2' '\n'` to `[0x3F201000]`, one
    byte per `str`.
11. `wfi; b .`

`panic_stub` writes `'X'` to `[0x3F201000]` and `wfi; b .`.

Build is via the existing `~/seed-os/smoke/Makefile` (`make kernel_cpu.img`,
`make run-cpu`) and a separate `linker_cpu.ld` (kept separate so cycle-8's
72-byte image is not perturbed by the `.text.vectors` alignment).

### New Makefile target

Extension of `~/seed-os/smoke/Makefile`:

```
boot_cpu.o: boot_cpu.S
	$(AS) -o $@ $<

kernel_cpu.elf: boot_cpu.o linker.ld
	$(LD) -T linker.ld -o $@ boot_cpu.o

kernel_cpu.img: kernel_cpu.elf
	$(OBJCOPY) -O binary $< $@

run-cpu: kernel_cpu.img
	@timeout --preserve-status 4 qemu-system-aarch64 -M raspi3ap \
	  -kernel kernel_cpu.img -nographic -serial mon:stdio -monitor none \
	  -no-reboot -d guest_errors,unimp -D qemu_raspi3ap_cpu.log \
	  > qemu_raspi3ap_cpu.out 2>&1; \
	echo "--- stdout ---"; cat qemu_raspi3ap_cpu.out; \
	echo "--- guest_errors,unimp ---"; cat qemu_raspi3ap_cpu.log; \
	grep -q SEED02 qemu_raspi3ap_cpu.out && echo "PASS: SEED02 observed" \
	  || echo "FAIL: SEED02 not observed"
```

The success criterion is *both* `SEED02` in stdout *and* an empty
`guest_errors,unimp` log. Either one alone is insufficient: a panic stub
emits `X` (so any X in the output is a failure even if SEED02 also appears
later — should not happen, but check), and an unimplemented MMIO access
means something we didn't intend was poked.

### Anti-goals — what the smoke-test extension CANNOT prove

(In the cycle-8 spirit: scope narrowly so the green light is honest.)

- That the SCTLR_EL1 RES1 mask `0x30D00800` is correct for the real
  Cortex-A53 r0p4. QEMU may not enforce architectural RES1.
- That the secondary cores can be woken via spin-table. The smoke parks them
  at `wfi` from their armstub entry; the wake-up path is **not** exercised.
- That the PL011 byte actually leaves the SoC pin on real hardware. QEMU
  loops it back to stdio; the real GPIO 14 TXD is firmware-mux-state
  dependent.
- That MMU-on operation works. MMU stays off.
- That the panic stub fires under any real fault. We never *cause* a fault.

These all become metal-only tests after `03-mmu` and `05-uart` ship.

## Failure modes

| Symptom under QEMU | Likely cause | First check |
|---|---|---|
| `SEED02` never appears, no panic byte either | Hung before EL drop, or EL drop never happens | `make dump` and read; eret target wrong? `SPSR_EL2.M[3:0]` wrong? |
| Single `X` then halt | EL drop succeeded; vector base wrong, or eret landed somewhere that immediately faulted (e.g. `SP_EL1` not set) | Disassemble; was `msr vbar_el1, x0` before `msr elr_el2, x1`? |
| Repeated `X`s | Vector handler itself faults — vector base wrong, alignment off | Check `_vectors` is 2-KiB aligned in `make dump`; check that panic stub doesn't itself touch unmapped memory |
| `guest_errors,unimp` log non-empty with reads from `0x3F2010xx` | Touched a PL011 register QEMU's model doesn't implement | Reduce the byte loop to DR only — no FR poll, no IBRD/FBRD touch (those belong in `05-uart`) |
| `SEED02` appears but `unimp` log mentions `0x40000000`+ | Stray read of local-intc peripheral that doesn't exist on raspi3ap | Inspect dump; we should not be touching the 0x4… block in this cycle at all |
| QEMU exits with non-zero before timeout | Image header malformed, or kernel jumped to 0 | Compare `make inspect` output vs Cycle 8's |

## UNVERIFIED items in this plan (with the experiment that resolves each)

1. **`SCTLR_EL1` reset value on Cortex-A53 r0p4.** The RES1 bits are
   architecturally fixed; the implementation-defined bits could differ from
   architectural reset. Resolved by: read `SCTLR_EL1` at `el1_entry`,
   write its low 8 bytes to scratch, dump after wfi. Requires UART.
2. **MPIDR Aff0 enumeration is exactly {0,1,2,3} on this silicon.** Almost
   certain (Linux uses it); confirmed empirically when secondaries each emit
   a distinguishable byte after wake-up. Cycle ≥ 10.
3. **The slot at `0xD8` is unused after armstub.** Disassemble the embedded
   armstub from `start.elf` and prove the load path. Until then: don't write
   to `0xD8`.
4. **QEMU raspi3ap emulates `MSR HCR_EL2`, `MSR CNTHCTL_EL2`, etc., correctly
   enough that the EL drop succeeds.** Falsified or confirmed by the
   `SEED02` test itself.
5. **The stack range `0x40000..0x80000` is not used by firmware-leftover
   data we need (e.g. DTB, initrd).** Resolved by checking `x0` at `_start`
   and confirming the DTB is *below* `0x40000` (likely; firmware tends to put
   it at high RAM or just under 64 MiB). If the DTB lands inside the stack
   area, the stacks move *up* — keep them adjacent to the kernel image at
   `0x80000` and grow *up* into a pre-allocated region. Cycle 10 will check
   `x0` first.

## What the PiForge docs got right and wrong

PiForge bare-metal write-up I have in `~/knowledge/piforge-build/` covers
Cortex-A72 (Pi 4) and treats the EL drop with reasonable fidelity, but:

- It targets EL3→EL2 → EL1 (Pi 4 firmware drops to EL3). On the Pi Zero 2W
  we land at EL2 already — the EL3 phase is **skipped on this hardware**
  and copying their EL3 setup would write to registers that don't exist or
  trap.
- Their secondary-core wake-up is the BCM2711-specific local-intc mailbox
  path (Pi 4 uses a slightly different mailbox layout). Their addresses
  (`0xE0`, `0xE8`, `0xF0` *as mailbox offsets within a base*) coincidentally
  *look like* our spin-table slot addresses, which is a recipe for thinking
  you've understood when you have a name-collision. Resist it.
- Their `SCTLR_EL1` RES1 mask is given as `0x30D00800` — agrees with this
  plan. Good.
- They use `dmb sy` between the release-address write and `sev`. ARM ARM
  requires a *DSB* (drain, not just memory-barrier), not a DMB. `dsb sy` is
  what this plan specifies. PiForge had it weaker.

## Verified against running hardware — Cycle 9, 2026-05-17

| Claim | Verifier | Result |
|---|---|---|
| CPU is Cortex-A53, AArch64, 4 cores | `/proc/cpuinfo`, `/proc/device-tree/cpus/cpu@N/compatible` | All four cpu@N show `arm,cortex-a53`; processor 0..3 in cpuinfo |
| Firmware drops kernel at EL2 | `dmesg \| grep "started at EL"` | `[ 0.008249] CPU: All CPU(s) started at EL2` |
| Spin-table is the live enable-method | `cat /proc/device-tree/cpus/cpu@1/enable-method` | `spin-table` |
| Per-cpu release addresses are 0xD8, 0xE0, 0xE8, 0xF0 | `od -An -tx1 /proc/device-tree/cpus/cpu@N/cpu-release-addr` | `00 00 00 00 00 00 00 d8/e0/e8/f0` |
| On-disk DTB carries BOTH `cpus.enable-method=brcm,bcm2836-smp` (parent) AND `cpu@N/enable-method=spin-table` (per-cpu) with `cpu-release-addr=0xD8/0xE0/0xE8/0xF0` | `dtc -I dtb -O dts /boot/firmware/bcm2710-rpi-zero-2-w.dtb` then read the `cpus` block | Confirmed Cycle 10. Per-cpu enable-method overrides parent (ARM cpus binding) — no firmware DTB mutation occurs; the on-disk and live DTBs are byte-identical for the cpu nodes. |
| Kernel actually used spin-table (not bcm2836-smp) to wake secondaries | `dmesg \| grep -iE "smp\|secondary"` | `CPU{1,2,3}: Booted secondary processor` — the spin-table boot path; no `bcm2836-smp` driver messages, no PSCI |
| `armstub=` is unset, no `armstub*.bin` on disk | `vcgencmd get_config armstub`, `ls /boot/firmware/` | `armstub=` empty; only `kernel8.img`, no armstub file → embedded armstub used |
| Cache line size 64 B, L1D 32 KiB, L2 512 KiB | device-tree | confirmed |
| `kernel_address=0` interpreted as "default" | `vcgencmd get_config kernel_address` | shows `0`; AArch64 default load is `0x80000`, consistent with `01-boot` and the smoke linker script |
| **Cycle 11:** spin-table release slots are at PA `0xD8/0xE0/0xE8/0xF0` and are *write-targets*, not just declarations | `sudo busybox devmem 0x{D8,E0,E8,F0} 64` on running Linux | `0xD8 = 0x0` (primary's slot, never used), `0xE0/0xE8/0xF0 = 0x14D13D0` (Linux's secondary entry trampoline). Confirms: addresses are real, writing a 64-bit PA wakes the secondary, slot is persistent post-jump. The "borrowed authority" from prior cycles is now hardware-probed evidence. UNVERIFIED-item-3 narrowed: `0xD8` is *unused after armstub* by Linux too (slot stays zero); safe to leave but no production wake-up writes there. |

## Sources

- ARM Architecture Reference Manual for A-profile, version K.a:
  - § D1.1 (exception levels), § D1.6.5 (entering an exception level via
    ERET), § C5.2 (HCR_EL2, SCTLR_EL1, SPSR_EL2 encodings), § D10
    (exception vector table layout).
- Cortex-A53 Technical Reference Manual r0p4 (ARM DDI 0500):
  - § 4.3.30 (SCTLR_EL1 RES1 bits), § 4.5 (cache geometry), § 6 (generic
    timer wiring).
- Linux kernel source: `arch/arm64/kernel/head.S` (for the canonical EL2→EL1
  drop ordering; we converge on the same sequence), `arch/arm64/include/
  asm/sysreg.h` (for register encodings).
- Raspberry Pi firmware `armstub8.S` (upstream
  `raspberrypi/tools/armstubs/armstub8.S`): the source of the spin-table
  loop on cores 1..3, the release-address slot layout, and the wfe/sev
  contract.
- `/proc/device-tree` — the authoritative live truth on this Pi.
- Cycle 7 mailbox plan (`~/seed-os/07-mailbox/plan.md`) — peripheral base
  `0x3F000000`, PL011 at `0x3F201000`.
- Cycle 8 smoke plan (`~/seed-os/smoke/plan.md`) — image header layout and
  the QEMU raspi3ap constraint.

## Cycle 11 result — 2026-05-17

- ~~Build `~/seed-os/smoke/boot_cpu.S`~~ — **done.** 195 lines. Builds via
  the existing Makefile (`make kernel_cpu.img`) with a separate
  `linker_cpu.ld` so the cycle-8 image stays 72 bytes. `make run-cpu`
  reports `PASS: SEED02 observed AND log empty`. Image size 4096 bytes
  (header + boot code + ALIGN(0x800) + 16-entry vector table).
- **First run revealed:** the plan's claim "QEMU's PL011 model is already
  enabled" was wrong. `UARTEN` resets to 0; without setting `CR = 0x301`
  every DR write emitted `PL011 data written to disabled UART` to the
  guest_errors log (QEMU leniently forwarded the byte to stdio anyway,
  which is the worst-of-both-worlds: `SEED02` *appeared* while the empty-log
  half of the success criterion failed). Fixed by adding one CR write at
  `0x3F201030` before the DR loop. Plan corrected in this cycle.
- **Spin-table probe (preemptive):** before writing boot_cpu.S, I
  `devmem`'d `0xD8/0xE0/0xE8/0xF0` on the running Pi (sudo busybox devmem).
  Slot 0 was zero (primary never uses it); slots 1..3 all held
  `0x014D13D0` — Linux's secondary entry trampoline, byte-faithfully
  preserved post-wake-up. Confirms: addresses real, mechanism correct
  ("write 64-bit PA, secondary jumps"), slots persistent. The receipt
  about "borrowed authority" on these addresses is now closed: I have
  hardware evidence.

## TODO (Cycle 12+)

- After `05-uart` produces a working PL011 init routine, replace the bare
  `str` to DR (and the minimal CR=0x301 enable) with a proper `uart_putc`
  that waits on `FR.TXFE` first and does full init (baud, line ctrl).
- After `05-uart` produces a working PL011 init routine, replace the bare
  `str` to DR with a proper `uart_putc` that waits on `FR.TXFE` first.
- Patch `01-boot/plan.md § Secondary core state` — done in this cycle.
  Spot-check: `grep '0x4000009C' ~/seed-os/01-boot/plan.md` should hit only
  the erratum callout, never a load-bearing claim.
- Write `03-mmu/plan.md`. Page tables, MAIR, TCR, the cache-clean addendum
  to `wake_secondary`.
- Disassemble the armstub embedded in `start.elf` (offset TBD) and confirm
  the spin loop matches the upstream `armstub8.S` we're relying on. Until
  then: UNVERIFIED #3.
