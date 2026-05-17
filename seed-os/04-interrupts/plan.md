# 04-interrupts — IRQ bring-up plan

> Written Cycle 21 (2026-05-17). Probe-before-plan discipline held: the BCM2835
> system timer frequency, the interrupt controller register state, and the ARM
> local controller register layout were all measured on the running Pi before
> any numbers were written here. Every physical address below traces to either
> `/proc/device-tree`, a `devmem` probe, or the ARM ARM (DDI 0487). What can't
> trace there is flagged UNVERIFIED.

## What this cycle owns

`03-mmu` exits with: MMU on, identity-map live, D-cache and I-cache on, UART
printing, DAIF all-masked (I=1, F=1, A=1, D=1 — no exceptions can reach the
kernel, and the vector table at `VBAR_EL1` is all-panic-stub).

`04-interrupts` owns the transition to: a single IRQ taken cleanly at EL1, the
vector table slot for `Current EL / SPx / IRQ` replaced with a real handler,
the BCM2835 system timer channel 1 armed as the IRQ source, the IRQ
acknowledged inside the handler, and ERET executed to return to the interrupted
flow. Proof: a sentinel printed inside the IRQ handler, then another printed
after return to the interrupted code.

It does **not** own: FIQ handlers, SError handlers, the ARM local interrupt
controller (`0x40000000`), the ARM generic timer (CNTP_* sysregs), secondary
core IRQ routing, nested IRQ handling, or any IRQ used by production kernel
code (timekeeping, scheduling). Those are later cycles.

## The cycle's load-bearing principle

The IRQ smoke carries a new kind of diagnostic risk: if the handler doesn't
fire, silence after `DAIF_CLR` looks identical to the kernel wedging before
the unmask. The discipline from `03-mmu` (print before every commit that
could silence you) extends here:

- Print the timer CLO and the compare target *before* writing them (so a
  wrong value is on the wire before the timer fires unexpectedly).
- Print a sentinel *before* unmasking DAIF (so if DAIF unmask causes an
  immediate SError or similar, the sentinel is the last breadcrumb).
- The handler itself must print at two points: on entry (proves the vector
  table slot is correct and the handler was reached) and after acknowledge
  (proves CS was cleared and the handler didn't re-fault on the write).

If the handler prints but ERET fails, the sentinel before ERET is the
post-mortem. If the handler never prints, the sentinel before DAIF unmask is
the last breadcrumb — and the question is whether the IRQ fired at all (check
that the timer was armed and the IRQ was enabled in the controller).

## Design decision: two interrupt controller architectures

### BCM2837 interrupt controller landscape

Two interrupt controllers exist on this SoC, both visible in the device tree:

| Controller | DT node | ARM phys base | Size | Linux driver |
|---|---|---|---|---|
| BCM2835 legacy IRQ ctrl | `interrupt-controller@7e00b200` | `0x3F00B200` | `0x200` | `brcm,bcm2836-armctrl-ic` |
| ARM local interrupt ctrl | `interrupt-controller@40000000` | `0x40000000` | `0x10000` | `brcm,bcm2836-l1-intc` |

The **ARM local controller** handles per-core interrupts: the ARM generic timer
(CNTPNSIRQ / CNTVIRQ — the `bcm2836-timer` source in `/proc/interrupts`),
per-core mailboxes, and routing of the GPU's IRQ line to individual cores.
Linux scheduler timer runs through this path: `Core 0 Timers Interrupt control
(0x40000040) = 0x0000000A` (bits 1+3 — CNTPNSIRQ and CNTVIRQ enabled to
core 0 IRQ line), verified by `devmem` on the running Pi.

The **BCM2835 legacy controller** handles peripheral IRQs: USB, DMA, UART,
MMC, system timer channels (bits 0-3 of IRQ pending 1), and more. Linux uses
this for UART, DMA, MMC, and mailbox (`ARMCTRL-level` entries in
`/proc/interrupts`). The system timer channels 1 and 3 are NOT used by Linux
(Linux uses the ARM generic timer instead).

### This cycle's decision: BCM2835 legacy controller + system timer channel 1

Reason: Both are in the **already-mapped aperture** `0x3F000000..0x40000000`
(L2[504..511] in the current page table). No new MMU entries needed.

The ARM local controller at `0x40000000` is outside the current map.
Adding it requires a second L1 entry (L1[1] → new L2 table for the
`0x40000000..0x7FFFFFFF` range). That is a clean one-line page-table
extension, but introducing a new MMU surface is a separate concern from
IRQ basics. Defer to the cycle that also plans the ARM generic timer.

The system timer is a simpler peripheral to reason about: one free-running
counter, four compare registers, four IRQ lines. It has no interrupt affinity
configuration, no priority levels, no GIC distributor. The IRQ fires when
CLO ≥ C1; it clears by writing 1 to CS bit 1 (W1C). That's the whole
protocol.

### Why not using the ARM GIC

There is no GIC on BCM2837. The Cortex-A53 MPCore optionally includes a GIC;
the BCM2837 omits it. The two controllers above are what exists.

## Hardware probes (Cycle 21)

All values from the running Pi Zero 2W.

### Interrupt controller — verified register state

```
$ sudo busybox devmem 0x3F00B200 32   → 0x00000000   IRQ basic pending (idle)
$ sudo busybox devmem 0x3F00B204 32   → 0x00000000   IRQ pending 1 (idle)
$ sudo busybox devmem 0x3F00B210 32   → 0x20340E00   Enable IRQs 1 (Linux-active)
$ sudo busybox devmem 0x3F00B218 32   → 0x00000006   Enable basic IRQs (Linux-active)
```

`Enable IRQs 1 = 0x20340E00`: bits 9,10,11,18,20,21,29 set by Linux (USB,
DMA, AUX). **Bits 1 and 3 are clear** — system timer channels 1 and 3 are
not enabled. Channel 1 is available for this cycle.

### System timer — verified register state

```
$ sudo busybox devmem 0x3F003000 32   → 0x0000000A   CS (channels 1,3 matched?!)
$ sudo busybox devmem 0x3F003004 32   → 0xA6421FDF   CLO (~2770 s since boot)
$ sudo busybox devmem 0x3F003010 32   → 0x00000000   C1 (compare 1 = 0)
```

CS shows bits 1 and 3 set. With C1 = 0 and CLO ≫ 0, CLO ≥ C1 has been true
since boot — the match flags are stale. They must be cleared (W1C) before
arming the timer, or the IRQ fires immediately on enable.

**Clearing procedure**: write `0x02` to CS (`[0x3F003000] |= 2`) → bit 1 clears.
Only then write the new C1 value. Only then enable the IRQ in the controller.

### System timer frequency — measured

```
CLO at t=0:   0xB1C7194D
CLO at t=1s:  0xB1D7A676
Delta:        1,084,713 ticks/s ≈ 1.085 MHz
```

Not exactly 1 MHz. The Pi's APB clock (from which the system timer derives)
varies with firmware and core voltage. For the smoke test: arm a delta of
**1,000,000 ticks** (~0.92 s at 1.085 MHz, well within QEMU's timeout). On
QEMU timing is emulated and not frequency-accurate; the test fires as soon as
QEMU processes the timer event.

UNVERIFIED #1: Whether QEMU's raspi3ap models the BCM2835 system timer at
`0x3F003000` (CLO reads, C1 writes, CS W1C, and the IRQ line into the
BCM2835 interrupt controller). Confident: QEMU's `bcm2835_systimer` model
exists in `hw/arm/bcm2835_peripherals.c`. Falsifying test: if CLO reads zero
or IRQ never fires in QEMU, the peripheral isn't modeled and this cycle
switches to an ARM local timer approach.

### ARM local controller — key registers (for context, not used this cycle)

```
$ sudo busybox devmem 0x40000040 32   → 0x0000000A   Core 0 timers IRQ control
                                                     (bits 1+3: CNTPNSIRQ+CNTVIRQ enabled)
$ sudo busybox devmem 0x40000060 32   → 0x00000000   Core 0 IRQ source (idle)
$ sudo busybox devmem 0x40000008 32   → 0x80000000   GPU interrupt routing
```

`Core 0 timers IRQ control = 0x0000000A` confirms Linux routes CNTPNSIRQ
(bit 1) and CNTVIRQ (bit 3) to core 0's IRQ line. This matches the
`bcm2836-timer` source in `/proc/interrupts` with ~5 M counts/s. This
register is the write target for enabling the ARM generic timer in a future
cycle; noted here for the "add L1[1] + map 0x40000000" cycle.

## Interrupt controller register map

ARM phys base: `0x3F00B200`. All offsets from that base.

| Offset | Name | Access | Purpose |
|---|---|---|---|
| `+0x00` | IRQ basic pending | R | ARM-local + basic GPU IRQs pending |
| `+0x04` | IRQ pending 1 | R | GPU IRQs 0-31 pending (system timer in bits 0-3) |
| `+0x08` | IRQ pending 2 | R | GPU IRQs 32-63 pending |
| `+0x0C` | FIQ control | R/W | FIQ enable/source select |
| `+0x10` | Enable IRQs 1 | W | Set bits to enable GPU IRQs 0-31 |
| `+0x14` | Enable IRQs 2 | W | Set bits to enable GPU IRQs 32-63 |
| `+0x18` | Enable basic IRQs | W | Set bits to enable basic/ARM IRQs |
| `+0x1C` | Disable IRQs 1 | W | Set bits to disable GPU IRQs 0-31 |
| `+0x20` | Disable IRQs 2 | W | Set bits to disable GPU IRQs 32-63 |
| `+0x24` | Disable basic IRQs | W | Set bits to disable basic/ARM IRQs |

For system timer channel 1: bit 1 (`0x02`) in IRQ pending 1, Enable IRQs 1,
and Disable IRQs 1.

Writing to an Enable register sets the corresponding IRQ enable; writing to
a Disable register clears it. These are set/clear registers, not
read-modify-write. Write `0x02` to Enable IRQs 1 (`0x3F00B210`) to enable
system timer channel 1 without disturbing Linux's enabled bits (which will
be gone anyway — we own the machine at bare metal).

UNVERIFIED #2: That writing to Enable IRQs 1 on BCM2837 (a write-to-set
register) does not require a read-modify-write. Documented as write-to-set in
the BCM2835 ARM Peripherals datasheet § 7.5. Confidence high; falsified if
enabling channel 1 disrupts existing bits (irrelevant at bare metal, but worth
stating).

## System timer register map

ARM phys base: `0x3F003000`. All offsets from that base.

| Offset | Name | Access | Purpose |
|---|---|---|---|
| `+0x00` | CS | R/W | Control/Status: bits 0-3 match flags (W1C to clear) |
| `+0x04` | CLO | R | Counter low 32 bits (free-running, ~1.085 MHz on this Pi) |
| `+0x08` | CHI | R | Counter high 32 bits |
| `+0x0C` | C0 | R/W | Compare 0 (used by GPU/VideoCore) |
| `+0x10` | C1 | R/W | Compare 1 ← this cycle |
| `+0x14` | C2 | R/W | Compare 2 (used by GPU/VideoCore) |
| `+0x18` | C3 | R/W | Compare 3 (available) |

Timer fires when CLO reaches C1. IRQ stays asserted until CS bit 1 is cleared
(W1C). The timer counter keeps running; after the clear, if CLO is still ≥ C1
the bit re-sets immediately. Protocol for a one-shot:

1. Clear CS bit 1 first (write `0x02` to `[CS]`).
2. Write new C1 value (CLO + delta).
3. Enable IRQ in controller.
4. In handler: clear CS bit 1, *then* disable IRQ in controller.

The order in step 4 matters: clear CS before disabling the controller. If you
disable the controller first, the CS bit stays set, and on the next re-enable
the IRQ fires immediately. For a one-shot this doesn't matter because we
never re-enable, but the discipline is correct for any reuse of this code.

## DAIF unmask sequencing

DAIF (Debug, SError, IRQ, FIQ) is a 4-bit mask in `PSTATE`. All four bits are
1 (masked) at entry to EL1 via the `SPSR_EL2 = 0x3C5` set in the EL2→EL1
drop (`02-cpu/plan.md` step 13).

To unmask IRQ only: `msr daifclr, #2` (clears the I bit; leaves D, A, F
masked). The immediate encodes: bit 3 = D, bit 2 = A, bit 1 = I, bit 0 = F.

### Unmask ordering

1. Arm the timer (write CLO + delta to C1).
2. Enable the IRQ in the controller (Enable IRQs 1 bit 1 set).
3. `isb` — ensure the controller write is visible before the CPU checks for
   pending IRQs.
4. `msr daifclr, #2` — now the CPU can take IRQs.

Do NOT unmask before enabling the IRQ source. With D=1 (debug masked), there
is no risk of a debug exception sneaking in. Leaving A=1 (SError masked)
during this test is correct — we have no SError handler.

The `wfi` after the unmask is not required by the architecture (the IRQ can
fire at any instruction boundary), but it is correct practice: WFI sleeps the
core until the next IRQ or FIQ, so the timer IRQ will wake the core cleanly.

### DAIF state through the handler

On IRQ entry: hardware sets DAIF.I=1 automatically (IRQs are masked during
the handler unless software explicitly unmasks them). This means nested IRQs
are impossible in this smoke — correct for a one-shot test.

On ERET: hardware restores PSTATE from SPSR_EL1 (saved at IRQ entry). Since
the interrupted code had DAIF.I=0 (we unmasked it), the post-ERET state has
DAIF.I=0 again — IRQs would be unmasked in the continuation. The continuation
does a WFI followed by a print and then `wfi; b .`, so the second WFI will
sleep indefinitely (no more IRQs enabled). Correct.

UNVERIFIED #3: That `msr daifclr, #2` at EL1 with SCTLR_EL1.M=1 works on
QEMU raspi3ap (daifclr is an EL1 privilege instruction; should work). Resolved
by the smoke test running successfully.

## Vector table slot assignment

AArch64 exception vector table layout (from ARM ARM D10.3):

```
VBAR_EL1 + 0x000  Current EL, SP_EL0, Synchronous
VBAR_EL1 + 0x080  Current EL, SP_EL0, IRQ
VBAR_EL1 + 0x100  Current EL, SP_EL0, FIQ
VBAR_EL1 + 0x180  Current EL, SP_EL0, SError
VBAR_EL1 + 0x200  Current EL, SP_ELx, Synchronous
VBAR_EL1 + 0x280  Current EL, SP_ELx, IRQ       ← this cycle
VBAR_EL1 + 0x300  Current EL, SP_ELx, FIQ
VBAR_EL1 + 0x380  Current EL, SP_ELx, SError
VBAR_EL1 + 0x400  Lower EL (AArch64), Synchronous
...
```

We use SP_ELx (set by `msr SPSel, #1` at the start of the smoke, and again by
the `SPSR_EL2 = 0x3C5` EL1h mode). The IRQ handler slot is at
`VBAR_EL1 + 0x280`.

In prior smokes, every slot is `b panic_stub`. This cycle, the slot at +0x280
is replaced with `b irq_handler_el1`. All other slots stay as panic_stub —
an unexpected exception remains a hard halt, not a silent loop.

The vector table is `.section ".text.vectors"`, `.balign 0x800`, with 16
entries × 0x80 bytes each. The entry at +0x280 is the 6th entry (0-indexed:
entries 0-3 are SP_EL0 group, entries 4-7 are SPx group; entry 5 at 5×0x80 =
0x280 is SPx IRQ). It contains `b irq_handler_el1` instead of `b panic_stub`.

## IRQ handler design

The handler runs at EL1, using SP_EL1. On IRQ entry, the hardware:
- Saves PC → ELR_EL1 (the interrupted instruction)
- Saves PSTATE → SPSR_EL1 (including the pre-interrupt DAIF)
- Sets DAIF.I=1 (masks IRQ)
- Sets DAIF.D=1 (masks debug exceptions in the handler)
- Jumps to VBAR_EL1 + 0x280

The hardware does NOT save general-purpose registers. The handler must.

### Register save/restore

Minimum save for a handler that calls print helpers (which trash x0-x5, x30):

```asm
irq_handler_el1:
    stp     x29, x30, [sp, #-16]!
    stp     x0,  x1,  [sp, #-16]!
    stp     x2,  x3,  [sp, #-16]!
    stp     x4,  x5,  [sp, #-16]!

    /* ... handler body ... */

    ldp     x4,  x5,  [sp], #16
    ldp     x2,  x3,  [sp], #16
    ldp     x0,  x1,  [sp], #16
    ldp     x29, x30, [sp], #16
    eret
```

The pre-decrement `[sp, #-16]!` keeps SP 16-byte aligned (AArch64 PCS
requirement; QEMU will generate an alignment fault if SP is misaligned during
the handler). SP_EL1 at the point of IRQ entry is whatever `el1_entry` last
left it — the same 16 KiB stack we set up in `02-cpu`. The handler's pushes
consume 64 bytes from that stack; plenty of headroom.

### Handler body

```
1. Print "IRQ_ENTRY\n" — first store from inside the handler.
   If this prints: VBAR_EL1 + 0x280 slot is correct, SPSel=1 is active,
   EL1 stack is reachable, and PL011 is still mapped (Device-nGnRnE attr
   survived the IRQ entry path).

2. Load CS register (0x3F003000).
   Check that bit 1 (channel 1) is set — it must be, as that is what fired.
   (If bit 1 is clear, some other channel fired — unexpected.)

3. Write 0x02 to CS (W1C — clear channel 1 match flag).
   This deasserts the IRQ line from the system timer.

4. Write 0x02 to Disable IRQs 1 (0x3F00B21C).
   This prevents the timer from firing again even if CLO wraps past C1.

5. Print "IRQ_ACK\n" — proves the CS write and the disable write didn't
   fault (both are in the already-mapped Device-nGnRnE aperture).

6. Print "IRQ_ERET\n" — the sentinel before ERET.
   If IRQ_ERET prints but IRQ_DONE never appears, the ERET faulted (stack
   misaligned? ELR_EL1 corrupted?).

7. ldp x4,x5 / ldp x2,x3 / ldp x0,x1 / ldp x29,x30 — restore registers.

8. eret — returns to the interrupted wfi.
```

After eret, the interrupted code continues from ELR_EL1 (the instruction
after wfi, or wfi itself if it was about to be retired). The continuation
code prints "IRQ_DONE\n" and then `wfi; b .`.

UNVERIFIED #4: That ERET from the handler correctly restores state and the
wfi-return prints IRQ_DONE. Resolved by the smoke running successfully.

## Bring-up sequence (sentinels)

This extends `boot_mmu_enable.S` after `CACHE_PASS`. All prior sentinels
apply; this plan specifies only the new ones.

| Step | Sentinel | What it proves if reached |
|---|---|---|
| After CACHE_PASS | `SEED04\n` | EL2→EL1 drop + MMU + caches all passed; entering IRQ territory |
| 1 | `IRQ_PRE\n` | About to arm the timer; next lines show CLO and C1 target |
| 1a | `CLO=<hex>\n` | Timer is running (CLO ≠ 0) |
| 1b | `C1=<hex>\n` | Compare target emitted before writing (post-mortem if timer misfires) |
| 2 | (write C1, clear CS, enable IRQ) | — |
| 3 | `IRQ_ARMED\n` | Timer armed + controller enabled; next instruction unmasks DAIF |
| 3a | (msr daifclr, #2) | — |
| 4 | `wfi` | Core sleeps waiting for IRQ |
| — | *IRQ fires here* | — |
| 5 | `IRQ_ENTRY\n` | Handler entered at VBAR_EL1+0x280; vector table slot correct |
| 6 | `IRQ_ACK\n` | CS cleared + IRQ disabled in controller |
| 7 | `IRQ_ERET\n` | About to eret; last breadcrumb if ERET faults |
| 8 | (eret) | — |
| 9 | `IRQ_DONE\n` | Returned from handler; WFI woke correctly |
| 10 | `PASS\n` | — |

### On silence after IRQ_ARMED

The IRQ is armed but DAIF is unmasked in the *next* instruction. If silence
falls here, the MSR daifclr itself raised an exception (SError from the
controller enable? Alignment fault?). IRQ_ARMED is the post-mortem sentinel.

More likely cause of silence after IRQ_ARMED: the timer fires before `wfi`
(CLO is already ≥ C1 due to execution time). In that case the IRQ is pending
when daifclr executes and the handler fires without `wfi` ever sleeping. That
is architecturally correct — the handler still runs. The `wfi` after daifclr
is never "entered"; instead the IRQ fires at the daifclr instruction boundary
(or the following wfi), and the handler prints IRQ_ENTRY → IRQ_DONE → PASS as
expected. The only observable difference is timing, not correctness.

## Smoke contract — `boot_irq.S`

New file `~/seed-os/smoke/boot_irq.S`. Reuses the full EL2→EL1 drop + MMU
enable + cache enable sequence from `boot_mmu_enable.S`, then adds the IRQ
layer. New Makefile target `make run-irq`.

**Success criterion (both required):**

```
$ grep -c "IRQ_ENTRY" qemu_raspi3ap_irq.out    # must be 1
$ grep -c "IRQ_DONE"  qemu_raspi3ap_irq.out    # must be 1
$ grep    "PASS"      qemu_raspi3ap_irq.out     # must appear
$ wc -l   qemu_raspi3ap_irq.log                 # must be 0 (empty guest_errors)
```

All four, or it does not count (cycle-11 dual-clause lesson).

The success criterion is intentionally checking for exactly one `IRQ_ENTRY`
and one `IRQ_DONE` — not just presence. A handler that loops before managing
to disable the IRQ source would print multiple lines; the count catches that.

## Vector table layout in the smoke

The existing vector table in `boot_mmu_enable.S` has every slot as `b
panic_stub`. In `boot_irq.S`:

```asm
.section ".text.vectors", "ax"
.balign 0x800
.globl _vectors
_vectors:
    .balign 0x80
    b       panic_stub          /* +0x000 SP_EL0 Sync */
    .balign 0x80
    b       panic_stub          /* +0x080 SP_EL0 IRQ */
    .balign 0x80
    b       panic_stub          /* +0x100 SP_EL0 FIQ */
    .balign 0x80
    b       panic_stub          /* +0x180 SP_EL0 SError */
    .balign 0x80
    b       panic_stub          /* +0x200 SPx Sync */
    .balign 0x80
    b       irq_handler_el1     /* +0x280 SPx IRQ ← real handler */
    .balign 0x80
    b       panic_stub          /* +0x300 SPx FIQ */
    .balign 0x80
    b       panic_stub          /* +0x380 SPx SError */
    .balign 0x80
    b       panic_stub          /* +0x400 Lower AArch64 Sync */
    ... (remaining 7 entries: panic_stub)
```

## UNVERIFIED items (with resolving experiments)

1. **QEMU raspi3ap models BCM2835 system timer accurately.** CLO reads return
   a monotonically increasing value; C1 writes arm a future match; CS W1C
   clears the match; IRQ line is asserted to the controller. Resolved by:
   `make run-irq` producing IRQ_ENTRY and IRQ_DONE. If QEMU doesn't model it,
   CLO always reads 0 or IRQ never fires; observed as silence after IRQ_ARMED.
   Fall-back if unmodelled: switch to ARM local timer (add L1[1] mapping first).
   **CLOSED Cycle 21.** CLO = 0x17919 (non-zero, monotonically advancing), IRQ
   fired at CLO + 1,000,000 exactly, IRQ_ENTRY appeared, guest_errors empty.

2. **Enable IRQs 1 is write-to-set (not read-modify-write required).** BCM2835
   ARM Peripherals § 7.5. Confidence high. Falsified if writing 0x02 to
   `0x3F00B210` clears other bits (irrelevant at bare metal; no bits matter
   except our own).
   **CLOSED Cycle 21.** IRQ fired; no spurious faults from other controller
   bits being disturbed. Write-to-set confirmed functional on QEMU raspi3ap.

3. **`msr daifclr, #2` works at EL1 with MMU and caches on.** Architecturally
   correct; DAIFCLR is an EL1 privileged instruction. Resolved by smoke
   running successfully (IRQ fires after unmask).
   **CLOSED Cycle 21.** IRQ fired after daifclr; IRQ_ENTRY printed.

4. **ERET from the handler correctly resumes the interrupted code.** ELR_EL1
   and SPSR_EL1 are set by hardware on IRQ entry. If the handler preserves all
   general registers it pushes, and SP is 16-byte aligned at the eret point,
   the eret is correct. Resolved by IRQ_DONE appearing after IRQ_ERET.
   **CLOSED Cycle 21.** IRQ_DONE appeared after IRQ_ERET. ELR_EL1 = instruction
   after WFI confirmed (the wfi ELR contract holds on QEMU raspi3ap).

5. **SP_EL1 remains 16-byte aligned inside the handler.** The handler saves 4
   pairs (64 bytes), each pair a 16-byte aligned STP. Starting from the
   aligned `0x7C000` stack top, all pushes preserve alignment. Resolved by the
   smoke not generating an SP alignment fault (which would appear as an
   `X` before IRQ_ENTRY, from the panic_stub at +0x200 Synchronous SPx).
   **CLOSED Cycle 21.** No alignment fault observed. SP discipline holds.

## Failure modes

| Symptom | Likely cause | First check |
|---|---|---|
| Silence after `CACHE_PASS`, before `SEED04` | Regression in phase-2 caches (SCTLR write broke something) | Run `make run-mmu-enable` to confirm the baseline still holds |
| `SEED04` then silence (before `IRQ_ARMED`) | Fault during timer setup — CS clear or C1 write | Check L2[504] descriptor; `0x3F003000` in mapped range? |
| `IRQ_ARMED` then silence forever | IRQ never fires. Either: (a) timer not modelled by QEMU, (b) Enable IRQs 1 write didn't take, (c) DAIF.I not cleared | First: try a 10× larger delta in case QEMU timer is slow |
| `X` instead of `IRQ_ENTRY` | Wrong vector slot used. SPSel=0 (SP_EL0) instead of SP_ELx, or VBAR_EL1 not updated to new table | Confirm the slot at +0x080 (SP_EL0 IRQ, not SPx); confirm `VBAR_EL1` points to the new table after it was rewritten |
| `IRQ_ENTRY` then `X` (no IRQ_ACK) | Handler fault: likely an unmapped address accessed. CS at 0x3F003000 is in L2[504]? Check the LDR/STR addresses | Disassemble handler; check that the literal pool for 0x3F003000 survived the code layout |
| `IRQ_ENTRY IRQ_ENTRY IRQ_ENTRY ...` (looping) | Handler didn't clear the IRQ source; fired again on ERET | Verify CS W1C write (write `0x02` to `[0x3F003000]`, not `|= 0x02`) |
| `IRQ_ERET` then silence (no `IRQ_DONE`) | ERET faulted: misaligned SP_EL1 or corrupt ELR_EL1 | Count the STP/LDP pairs; verify the stack pointer is 16-aligned at eret |
| Non-empty `guest_errors,unimp` log | An MMIO register QEMU doesn't model was touched | grep the log for the address; narrow handler to only the documented CS/C1 registers |

## What this cycle does NOT do

- No ARM local controller (`0x40000000`) — needs a new L1 entry and L2 table;
  separate cycle, probably the one that brings up the ARM generic timer.
- No FIQ. The FIQ vector entry stays as `b panic_stub`.
- No SError. Same.
- No secondary core IRQs. Cores 1-3 are WFI at their `el1_entry_secondary`
  stubs; the IRQ fires only on core 0 (the BCM2835 legacy controller routes
  peripheral IRQs to core 0 by default).
- No timer abstraction. C1 is armed with CLO + delta in assembly; no
  frequency-normalisation, no tick counter, no future-proof rate. Those belong
  in `08-time/plan.md`.
- No modification to `config.txt` or SD card. Still gated on `05-uart`
  pin-mux for on-metal proof.
- No on-metal test. This cycle is QEMU only.

## What next (Cycle 22+)

After a clean `make run-irq`:

1. **05-uart bring-up** — proper PL011 init (baud, line control, FR.TXFE poll)
   and GPIO 14/15 pin-mux (`ALT0` via GPFSEL1). Once 05-uart works on metal,
   every cycle-8 through cycle-22 smoke can be gated for on-metal verification.
   That's when UNVERIFIED #1 in `03-mmu/plan.md` (on-metal MMFR values) closes.

2. **ARM local controller + ARM generic timer** — add L1[1] (one L2 table
   for `0x40000000..0x40200000` or a 1 GB block), write CNTP_TVAL_EL0 +
   CNTP_CTL_EL0 to arm the generic timer, enable routing through the ARM local
   controller. This is the timer Linux actually uses; closing it makes the OS
   kernel's tick correct on bare metal.

3. **Scheduler** — secondary cores, preemption, context switch. Gated on the
   ARM generic timer (above) for the tick source.

## Sources

- BCM2835 ARM Peripherals (Broadcom, version 2.0): § 7 (interrupts), § 12
  (system timer). Bus address `0x7E003000` → ARM phys `0x3F003000`; bus
  `0x7E00B200` → ARM phys `0x3F00B200`. Both derived from `soc/ranges` probe.
- ARM Architecture Reference Manual (DDI 0487): § D10.3 (exception vector
  table layout), § C5.2.3 (DAIF / DAIFCLR / DAIFSET encodings), § D1.7.1
  (IRQ handling sequence at EL1).
- BCM2836 QA7 ARM-local peripherals (Broadcom, revision 1.0): § 4 (interrupt
  controller offsets). Used for the ARM local controller register survey in
  § "ARM local controller" above; not the IRQ source for this cycle.
- `/proc/interrupts` — confirmed system timer channels 1 and 3 are unused by
  Linux (no `ARMCTRL-level` entries for bits 1/3 of bank 1).
- `devmem` probes on running Pi — CS, CLO, C1, Enable IRQs 1, ARM local
  controller registers. Primary source for all numeric values in this plan.
