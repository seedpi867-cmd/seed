/*
 * Cycle 11 — EL2→EL1 drop + a single visible side-effect via PL011.
 *
 * Spec: ~/seed-os/02-cpu/plan.md § "Smoke-test extension".
 * Target: QEMU -M raspi3ap. Success = "SEED02\n" in stdout AND empty
 * guest_errors,unimp log. Do NOT run on metal — depends on pin-mux from
 * 05-uart that doesn't exist yet.
 *
 * Layout:
 *   .text.boot     — image header, code_entry, primary_start, el1_entry,
 *                    panic_stub
 *   .text.vectors  — 2-KiB-aligned exception vector table (16 entries),
 *                    every entry just `b panic_stub`
 *
 * Linker script (linker_cpu.ld) places .text.vectors after .text.boot with
 * ALIGN(0x800). panic_stub and _vectors are < 0x1000 apart — within `b`
 * range trivially.
 *
 * What this proves (only):
 *   - Image header parses, kernel starts.
 *   - MPIDR check parks cores 1..3 cleanly (no spurious output from them).
 *   - 14-step EL2→EL1 drop arrives at el1_entry without faulting through
 *     a vector.
 *   - PL011 DR writes reach QEMU's stdio.
 *
 * What this does NOT prove (see § Anti-goals in 02-cpu/plan.md):
 *   - SCTLR_EL1 RES1 mask correctness on real Cortex-A53 r0p4.
 *   - Secondary wake-up via spin-table (not exercised).
 *   - MMU operation.
 *   - That the PL011 byte leaves a real SoC pin.
 *   - That the panic stub fires under any real fault.
 */

.section ".text.boot", "ax"
.globl _start

_start:
        /* Linux ARM64 Image header — same layout as cycle-8 boot.S. */
        b       code_entry
        .long   0
        .quad   0x80000
        .quad   _image_size
        .quad   0x0A
        .quad   0
        .quad   0
        .quad   0
        .ascii  "ARM\x64"
        .long   0

code_entry:
        /* Use SP_ELx (not SP_EL0). Firmware may have left SPSel ambiguous. */
        msr     SPSel, #1

        /* Park secondaries immediately — this cycle has no secondary path. */
        mrs     x0, mpidr_el1
        and     x0, x0, #3
        cbz     x0, primary_start
1:      wfi
        b       1b

primary_start:
        /* SP_EL2 = 0x80000 (primary EL2-phase stack top). */
        ldr     x0, =0x80000
        mov     sp, x0

        /* Defensive: confirm we're at EL2. CurrentEL[3:2] = current EL.
         * If not EL2, fall into panic_stub — visible 'X' beats silent UB. */
        mrs     x0, CurrentEL
        lsr     x0, x0, #2
        cmp     x0, #2
        b.ne    panic_stub

        /* Install panic vectors at VBAR_EL2 so any EL2-phase fault halts
         * with an 'X' instead of jumping to 0. Same table is reused at
         * EL1 below — the handler is EL-agnostic. */
        adr     x0, _vectors
        msr     vbar_el2, x0
        isb

        /* ============= 14-step EL2→EL1 drop, per 02-cpu plan ============= */

        /* (2) HCR_EL2.RW = 1 — EL1 executes in AArch64. */
        mov     x0, #(1 << 31)
        msr     hcr_el2, x0

        /* (3) CNTHCTL_EL2 = EL1PCTEN | EL1PCEN — EL1 timer access, no trap. */
        mov     x0, #0b11
        msr     cnthctl_el2, x0

        /* (4) CNTVOFF_EL2 = 0 — physical and virtual time agree. */
        msr     cntvoff_el2, xzr

        /* (5) CPTR_EL2 = 0x33FF — RES1 bits set, no SIMD/FP/SVE trap. */
        mov     x0, #0x33FF
        msr     cptr_el2, x0

        /* (6) HSTR_EL2 = 0 — no CP15 trapping (AArch32 legacy, harmless). */
        msr     hstr_el2, xzr

        /* (7) SCTLR_EL1 = 0x30D00800 — Cortex-A53 RES1 mask; MMU+caches off. */
        ldr     x0, =0x30D00800
        msr     sctlr_el1, x0

        /* (8) CPACR_EL1.FPEN = 0b11 — allow FP/SIMD at EL1/EL0. */
        mov     x0, #(0b11 << 20)
        msr     cpacr_el1, x0

        /* (9) MDCR_EL2 = 0 — no PMU/debug trapping. */
        msr     mdcr_el2, xzr

        /* (10) VBAR_EL1 = _vectors. */
        adr     x0, _vectors
        msr     vbar_el1, x0

        /* (11) SP_EL1 = 0x7C000 — primary EL1 stack top (16 KiB below image). */
        ldr     x0, =0x7C000
        msr     sp_el1, x0

        /* (12) ELR_EL2 = &el1_entry — ERET destination. */
        adr     x0, el1_entry
        msr     elr_el2, x0

        /* (13) SPSR_EL2 = 0x3C5 — DAIF masked; M[4:0] = 0b00101 (EL1h). */
        mov     x0, #0x3C5
        msr     spsr_el2, x0

        isb

        /* (14) ERET — atomic transition to EL1. */
        eret

el1_entry:
        /* Re-install VBAR_EL1. Already set in step 10, but the non-smoke
         * kernel will do unrelated work between the drop and arriving here,
         * so the install is mirrored. Idempotent. */
        adr     x0, _vectors
        msr     vbar_el1, x0
        isb

        /* Enable PL011 UART before touching DR. CR is at base + 0x30.
         * CR = UARTEN | TXE | RXE = 0x301. Without this, QEMU's PL011
         * model emits "data written to disabled UART" guest_error per
         * DR write (the byte still reaches stdio because QEMU is lenient,
         * but the success criterion requires an empty guest_errors log).
         * The cycle-11 first run discovered this; the 02-cpu plan's claim
         * "QEMU's PL011 model is already enabled" was wrong.
         * NOTE: this is *minimum-functional* UART, not full init.
         * Baud rate, line control, FIFO config all stay in 05-uart. */
        ldr     x0, =0x3F201030
        mov     w1, #0x301
        str     w1, [x0]

        /* Emit "SEED02\n" to PL011 DR (0x3F201000). Blind writes only —
         * NO FR poll, NO IBRD/FBRD touch. */
        ldr     x0, =0x3F201000
        mov     w1, #'S'
        str     w1, [x0]
        mov     w1, #'E'
        str     w1, [x0]
        mov     w1, #'E'
        str     w1, [x0]
        mov     w1, #'D'
        str     w1, [x0]
        mov     w1, #'0'
        str     w1, [x0]
        mov     w1, #'2'
        str     w1, [x0]
        mov     w1, #'\n'
        str     w1, [x0]

2:      wfi
        b       2b

/* panic_stub — emit 'X' to PL011 DR and halt.
 * Single source of truth for every vector slot; also reached by the
 * CurrentEL!=EL2 guard above. Touches no SP, so safe at any EL before
 * a stack is set up. */
.globl panic_stub
panic_stub:
        ldr     x0, =0x3F201000
        mov     w1, #'X'
        str     w1, [x0]
3:      wfi
        b       3b

.ltorg

/* 2-KiB-aligned exception vector table. 16 entries × 128 bytes each.
 * Layout per ARM ARM D.10.3. Every entry just branches to panic_stub:
 * the goal in 02-cpu is that an unexpected exception *halts*, not jumps
 * to zero. Real handlers ship later (06-irq). */
.section ".text.vectors", "ax"
.balign 0x800
.globl _vectors
_vectors:
        .balign 0x80
        b       panic_stub          /* Current EL, SP_EL0, Synchronous */
        .balign 0x80
        b       panic_stub          /* Current EL, SP_EL0, IRQ */
        .balign 0x80
        b       panic_stub          /* Current EL, SP_EL0, FIQ */
        .balign 0x80
        b       panic_stub          /* Current EL, SP_EL0, SError */
        .balign 0x80
        b       panic_stub          /* Current EL, SP_ELx, Synchronous */
        .balign 0x80
        b       panic_stub          /* Current EL, SP_ELx, IRQ */
        .balign 0x80
        b       panic_stub          /* Current EL, SP_ELx, FIQ */
        .balign 0x80
        b       panic_stub          /* Current EL, SP_ELx, SError */
        .balign 0x80
        b       panic_stub          /* Lower EL, AArch64, Synchronous */
        .balign 0x80
        b       panic_stub          /* Lower EL, AArch64, IRQ */
        .balign 0x80
        b       panic_stub          /* Lower EL, AArch64, FIQ */
        .balign 0x80
        b       panic_stub          /* Lower EL, AArch64, SError */
        .balign 0x80
        b       panic_stub          /* Lower EL, AArch32, Synchronous */
        .balign 0x80
        b       panic_stub          /* Lower EL, AArch32, IRQ */
        .balign 0x80
        b       panic_stub          /* Lower EL, AArch32, FIQ */
        .balign 0x80
        b       panic_stub          /* Lower EL, AArch32, SError */
        .balign 0x80
