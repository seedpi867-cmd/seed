/*
 * Cycle 21 — boot_irq.S: IRQ bring-up smoke.
 *
 * Extends the cycle-14/15 MMU+cache bring-up (boot_mmu_enable.S) with a
 * single IRQ taken cleanly at EL1. After CACHE_PASS:
 *
 *   1. Arm BCM2835 system timer channel 1 (CLO + 1_000_000 ticks, ~1s).
 *   2. Enable timer channel 1 IRQ in BCM2835 interrupt controller.
 *   3. Unmask DAIF.I (msr daifclr, #2).
 *   4. WFI — core sleeps.
 *   5. IRQ fires; hardware enters irq_handler_el1 via VBAR_EL1+0x280.
 *   6. Handler: print IRQ_ENTRY, clear CS bit 1 (W1C), disable IRQ,
 *      print IRQ_ACK, print IRQ_ERET, restore registers, eret.
 *   7. Execution continues at instruction after WFI (ELR_EL1 contract).
 *   8. Print IRQ_DONE, PASS, wfi; b .
 *
 * PASS criterion: IRQ_ENTRY appears exactly once, IRQ_DONE appears,
 * PASS appears, guest_errors,unimp log is empty.
 *
 * Peripheral addresses (all in mapped L2[504..511] Device-nGnRnE aperture):
 *   0x3F003000: system timer CS (W1C on bits 0-3)
 *   0x3F003004: system timer CLO (read-only, free-running ~1 MHz)
 *   0x3F003010: system timer C1 (compare 1, write arms the match)
 *   0x3F00B200: IRQ controller base
 *   0x3F00B210: Enable IRQs 1 (write-to-set, bit 1 = system timer ch 1)
 *   0x3F00B21C: Disable IRQs 1 (write-to-clear, bit 1 = system timer ch 1)
 *   0x3F201000: PL011 DR
 *   0x3F201030: PL011 CR
 */

.section ".text.boot", "ax"
.globl _start

_start:
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
        msr     SPSel, #1

        mrs     x0, mpidr_el1
        and     x0, x0, #3
        cbz     x0, primary_start
1:      wfi
        b       1b

primary_start:
        ldr     x0, =0x80000
        mov     sp, x0

        mrs     x0, CurrentEL
        lsr     x0, x0, #2
        cmp     x0, #2
        b.ne    panic_stub

        adr     x0, _vectors
        msr     vbar_el2, x0
        isb

        /* ============= 14-step EL2→EL1 drop ============= */
        mov     x0, #(1 << 31)
        msr     hcr_el2, x0
        mov     x0, #0b11
        msr     cnthctl_el2, x0
        msr     cntvoff_el2, xzr
        mov     x0, #0x33FF
        msr     cptr_el2, x0
        msr     hstr_el2, xzr
        ldr     x0, =0x30D00800
        msr     sctlr_el1, x0
        mov     x0, #(0b11 << 20)
        msr     cpacr_el1, x0
        msr     mdcr_el2, xzr
        adr     x0, _vectors
        msr     vbar_el1, x0
        ldr     x0, =0x7C000
        msr     sp_el1, x0
        adr     x0, el1_entry
        msr     elr_el2, x0
        mov     x0, #0x3C5
        msr     spsr_el2, x0
        isb
        eret

el1_entry:
        adr     x0, _vectors
        msr     vbar_el1, x0
        isb

        /* PL011 CR enable (cycle-11 lesson: UARTEN resets to 0). */
        ldr     x0, =0x3F201030
        mov     w1, #0x301
        str     w1, [x0]

        /* SEED03 sentinel: EL2→EL1 drop and PL011 path working. */
        adr     x0, str_seed03
        bl      print_str

        /* ======================================================
         * PRE: dump sysregs MMU will use.
         * ====================================================== */
        adr     x0, str_pre
        bl      print_str

        adr     x0, str_sctlr_eq
        bl      print_str
        mrs     x1, sctlr_el1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_tcr_eq
        bl      print_str
        mrs     x1, tcr_el1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_mair_eq
        bl      print_str
        mrs     x1, mair_el1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_ttbr0_eq
        bl      print_str
        mrs     x1, ttbr0_el1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_ttbr1_eq
        bl      print_str
        mrs     x1, ttbr1_el1
        bl      print_hex64
        bl      print_nl

        /* ====================================================
         * ZERO_L1 and ZERO_L2: clear both page tables.
         * ==================================================== */
        adr     x0, str_zero_l1
        bl      print_str
        ldr     x19, =l1_table
        mov     x20, #(4096 / 8)
        mov     x21, x19
.zero_l1_loop:
        str     xzr, [x21], #8
        subs    x20, x20, #1
        b.ne    .zero_l1_loop

        adr     x0, str_zero_l2
        bl      print_str
        ldr     x19, =l2_table_0
        mov     x20, #(4096 / 8)
        mov     x21, x19
.zero_l2_loop:
        str     xzr, [x21], #8
        subs    x20, x20, #1
        b.ne    .zero_l2_loop

        /* ====================================================
         * BUILD_L2_RAM: L2[0] = Normal-cacheable block at PA 0.
         *   0x0040_0000_0000_0705: UXN=1 AF=1 SH=11 AP=00 AttrIndx=1 block
         * ==================================================== */
        adr     x0, str_build_l2_ram
        bl      print_str
        ldr     x19, =l2_table_0
        ldr     x20, =0x0040000000000705
        str     x20, [x19]

        /* ====================================================
         * BUILD_L2_DEV: L2[504..511] = Device-nGnRnE blocks for
         * the BCM2837 peripheral aperture 0x3F000000..0x40000000.
         *   0x0060_0000_3F00_0401: UXN=1 PXN=1 AF=1 AttrIndx=0 block
         * ==================================================== */
        adr     x0, str_build_l2_dev
        bl      print_str
        ldr     x19, =l2_table_0
        add     x19, x19, #(504 * 8)
        ldr     x20, =0x006000003F000401
        mov     x21, #8
.build_dev_loop:
        str     x20, [x19], #8
        add     x20, x20, #0x200000
        subs    x21, x21, #1
        b.ne    .build_dev_loop

        /* BUILD_L1: L1[0] = &l2_table_0 | 0b11 (table descriptor). */
        adr     x0, str_build_l1
        bl      print_str
        ldr     x19, =l1_table
        ldr     x20, =l2_table_0
        orr     x20, x20, #0b11
        str     x20, [x19]

        dsb     ishst

        /* TLBI: flush stale TLB entries. */
        adr     x0, str_tlbi
        bl      print_str
        tlbi    vmalle1
        dsb     ish
        isb

        /* MAIR: pre-emit, write. */
        adr     x0, str_mair_eq
        bl      print_str
        ldr     x19, =0x00000000000000FF
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     mair_el1, x19

        /* TCR: pre-emit, write. EPD1=1, IPS=40-bit, TG0=4K, T0SZ=25. */
        adr     x0, str_tcr_eq
        bl      print_str
        ldr     x19, =0x00000012B5993519
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     tcr_el1, x19

        /* TTBR0: pre-emit, write. */
        adr     x0, str_ttbr0_eq
        bl      print_str
        ldr     x19, =l1_table
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     ttbr0_el1, x19

        /* TTBR1: zero (EPD1=1 disables TTBR1 walks). */
        adr     x0, str_ttbr1_eq
        bl      print_str
        mov     x19, xzr
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     ttbr1_el1, x19

        isb

        /* ARM: armed sentinel. Next is SCTLR.M = 1. */
        adr     x0, str_arm
        bl      print_str

        /* Phase-1 MMU enable: set SCTLR_EL1.M=1, C=0, I=0. */
        mrs     x0, sctlr_el1
        orr     x0, x0, #1
        msr     sctlr_el1, x0

        adr     x0, str_mmu1
        bl      print_str

        isb

        adr     x0, str_mmu2
        bl      print_str

        mrs     x22, sctlr_el1

        adr     x0, str_mmu3
        bl      print_str

        adr     x0, str_live
        bl      print_str

        /* POST: re-MRS the five sysregs. */
        adr     x0, str_post
        bl      print_str

        adr     x0, str_sctlr_eq
        bl      print_str
        mov     x1, x22
        bl      print_hex64
        bl      print_nl

        adr     x0, str_tcr_eq
        bl      print_str
        mrs     x1, tcr_el1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_mair_eq
        bl      print_str
        mrs     x1, mair_el1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_ttbr0_eq
        bl      print_str
        mrs     x1, ttbr0_el1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_ttbr1_eq
        bl      print_str
        mrs     x1, ttbr1_el1
        bl      print_hex64
        bl      print_nl

        /* TESTLOAD: read first word at 0x80000 through Normal mapping. */
        adr     x0, str_testload
        bl      print_str
        ldr     x19, =0x80000
        ldr     w20, [x19]
        adr     x0, str_value_eq
        bl      print_str
        mov     x1, x20
        bl      print_hex64
        bl      print_nl

        /* TESTSTORE: write/read-back 0xDEADBEEF at 0x100. */
        adr     x0, str_teststore
        bl      print_str
        ldr     x19, =0x100
        movz    w20, #0xBEEF
        movk    w20, #0xDEAD, lsl #16
        str     w20, [x19]
        ldr     w21, [x19]
        adr     x0, str_value_eq
        bl      print_str
        mov     x1, x21
        bl      print_hex64
        bl      print_nl

        /* Phase-1 PASS. */
        adr     x0, str_pass
        bl      print_str

        /* ====================================================
         * Phase 2: enable D-cache and I-cache.
         * One architectural moment; three sentinels at three
         * distinct surviving events (cycle-15 inner-voice lesson).
         * ==================================================== */
        adr     x0, str_cache_pre
        bl      print_str
        adr     x0, str_sctlr_eq
        bl      print_str
        mrs     x1, sctlr_el1
        bl      print_hex64
        bl      print_nl

        mrs     x0, sctlr_el1
        orr     x0, x0, #(1 << 2)   /* C = 1 */
        orr     x0, x0, #(1 << 12)  /* I = 1 */
        msr     sctlr_el1, x0
        isb

        adr     x0, str_cache_live
        bl      print_str

        adr     x0, str_sctlr_eq
        bl      print_str
        mrs     x1, sctlr_el1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_cache_pass
        bl      print_str

        /* ====================================================
         * SEED04: entering IRQ territory.
         * ==================================================== */
        adr     x0, str_seed04
        bl      print_str

        /* ====================================================
         * IRQ_PRE: arm the system timer and show the values
         * before committing them (sentinel discipline).
         * ==================================================== */
        adr     x0, str_irq_pre
        bl      print_str

        /* Clear stale CS bit 1 (W1C) before reading CLO. */
        ldr     x19, =0x3F003000    /* system timer CS */
        mov     w20, #0x02
        str     w20, [x19]          /* W1C: clear channel-1 match flag */

        /* Read CLO and print. */
        ldr     x19, =0x3F003004    /* CLO */
        ldr     w22, [x19]          /* x22 = current CLO */
        adr     x0, str_clo_eq
        bl      print_str
        mov     x1, x22
        bl      print_hex64
        bl      print_nl

        /* Compute C1 target = CLO + 1_000_000 ticks (~1s at 1 MHz). */
        ldr     x19, =1000000
        add     x23, x22, x19       /* x23 = C1 target */
        adr     x0, str_c1_eq
        bl      print_str
        mov     x1, x23
        bl      print_hex64
        bl      print_nl

        /* Write C1. */
        ldr     x19, =0x3F003010    /* C1 */
        str     w23, [x19]

        /* Enable timer channel 1 IRQ in the interrupt controller.
         * 0x3F00B210 = Enable IRQs 1 (write-to-set; bit 1 = ch 1). */
        ldr     x19, =0x3F00B210
        mov     w20, #0x02
        str     w20, [x19]

        /* Barrier: ensure controller write visible before DAIF unmask. */
        dsb     sy
        isb

        /* ====================================================
         * IRQ_ARMED: about to unmask DAIF.I. This is the last
         * sentinel before the IRQ fires. If silence follows,
         * either the timer is not modelled by QEMU (UNVERIFIED #1)
         * or Enable IRQs 1 write didn't take (check the controller).
         * ==================================================== */
        adr     x0, str_irq_armed
        bl      print_str

        /* Unmask IRQ (clear DAIF.I, bit 1 of the daifclr immediate). */
        msr     daifclr, #2

        /* WFI: sleep until IRQ fires.
         * ELR_EL1 = address of instruction AFTER wfi (AArch64 async
         * exception contract). Handler eret will resume here+4. */
        wfi

        /* ====================================================
         * IRQ_DONE: handler has run and eret'd back here.
         * If this prints: ERET restored ELR_EL1 correctly.
         * ==================================================== */
        adr     x0, str_irq_done
        bl      print_str

        /* Final PASS. */
        adr     x0, str_pass
        bl      print_str

2:      wfi
        b       2b

/* ============================================================
 * IRQ handler — entered via VBAR_EL1 + 0x280 (Current EL, SPx, IRQ).
 * Hardware has saved ELR_EL1 = interrupted PC, SPSR_EL1 = PSTATE,
 * set DAIF.I=1 (masks IRQ during handler).
 * ============================================================ */
.globl irq_handler_el1
irq_handler_el1:
        /* Save registers (4 pairs = 64 bytes; SP stays 16-byte aligned). */
        stp     x29, x30, [sp, #-16]!
        stp     x0,  x1,  [sp, #-16]!
        stp     x2,  x3,  [sp, #-16]!
        stp     x4,  x5,  [sp, #-16]!

        /* IRQ_ENTRY: first sentinel from inside the handler.
         * If this prints: VBAR_EL1+0x280 slot is correct, SPSel=1
         * is active, EL1 stack reachable, PL011 still mapped. */
        adr     x0, str_irq_entry
        bl      print_str

        /* Clear CS bit 1 (W1C): deassert the timer IRQ line. */
        ldr     x4, =0x3F003000     /* CS */
        mov     w5, #0x02
        str     w5, [x4]

        /* Disable channel 1 IRQ in the controller (write-to-clear).
         * 0x3F00B21C = Disable IRQs 1. Prevents re-fire even if the
         * timer wraps and CLO overtakes C1 again. */
        ldr     x4, =0x3F00B21C
        mov     w5, #0x02
        str     w5, [x4]

        /* IRQ_ACK: CS cleared + IRQ disabled. */
        adr     x0, str_irq_ack
        bl      print_str

        /* IRQ_ERET: last sentinel before eret. If this prints but
         * IRQ_DONE never appears, ERET faulted (misaligned SP_EL1
         * or corrupt ELR_EL1 — but those are guarded by UNVERIFIED #5
         * and #4). */
        adr     x0, str_irq_eret
        bl      print_str

        /* Restore registers and return. */
        ldp     x4,  x5,  [sp], #16
        ldp     x2,  x3,  [sp], #16
        ldp     x0,  x1,  [sp], #16
        ldp     x29, x30, [sp], #16
        eret

/* --- helpers ------------------------------------------------- */

print_str:
        ldr     x3, =0x3F201000
.ps_loop:
        ldrb    w2, [x0], #1
        cbz     w2, .ps_done
        str     w2, [x3]
        b       .ps_loop
.ps_done:
        ret

print_nl:
        ldr     x3, =0x3F201000
        mov     w2, #'\n'
        str     w2, [x3]
        ret

print_hex64:
        ldr     x3, =0x3F201000
        mov     w2, #'0'
        str     w2, [x3]
        mov     w2, #'x'
        str     w2, [x3]
        mov     x4, #15
.ph_loop:
        lsl     x5, x4, #2
        lsr     x0, x1, x5
        and     x0, x0, #0xF
        cmp     x0, #10
        b.lo    .ph_digit
        add     x0, x0, #('a' - 10 - '0')
.ph_digit:
        add     x0, x0, #'0'
        str     w0, [x3]
        subs    x4, x4, #1
        b.ge    .ph_loop
        ret

.globl panic_stub
panic_stub:
        ldr     x0, =0x3F201000
        mov     w1, #'X'
        str     w1, [x0]
3:      wfi
        b       3b

/* --- strings -------------------------------------------------- */
str_seed03:       .asciz "SEED03\n"
str_pre:          .asciz "PRE\n"
str_zero_l1:      .asciz "ZERO_L1\n"
str_zero_l2:      .asciz "ZERO_L2\n"
str_build_l2_ram: .asciz "BUILD_L2_RAM\n"
str_build_l2_dev: .asciz "BUILD_L2_DEV\n"
str_build_l1:     .asciz "BUILD_L1\n"
str_tlbi:         .asciz "TLBI\n"
str_arm:          .asciz "ARM\n"
str_mmu1:         .asciz "MMU1\n"
str_mmu2:         .asciz "MMU2\n"
str_mmu3:         .asciz "MMU3\n"
str_live:         .asciz "LIVE\n"
str_post:         .asciz "POST\n"
str_testload:     .asciz "TESTLOAD\n"
str_teststore:    .asciz "TESTSTORE\n"
str_pass:         .asciz "PASS\n"
str_cache_pre:    .asciz "CACHE_PRE\n"
str_cache_live:   .asciz "CACHE_LIVE\n"
str_cache_pass:   .asciz "CACHE_PASS\n"
str_seed04:       .asciz "SEED04\n"
str_irq_pre:      .asciz "IRQ_PRE\n"
str_clo_eq:       .asciz "CLO="
str_c1_eq:        .asciz "C1="
str_irq_armed:    .asciz "IRQ_ARMED\n"
str_irq_entry:    .asciz "IRQ_ENTRY\n"
str_irq_ack:      .asciz "IRQ_ACK\n"
str_irq_eret:     .asciz "IRQ_ERET\n"
str_irq_done:     .asciz "IRQ_DONE\n"
str_sctlr_eq:     .asciz "SCTLR="
str_tcr_eq:       .asciz "TCR="
str_mair_eq:      .asciz "MAIR="
str_ttbr0_eq:     .asciz "TTBR0="
str_ttbr1_eq:     .asciz "TTBR1="
str_value_eq:     .asciz "VALUE="

.ltorg

/* --- vector table -------------------------------------------- */
/*
 * Modified from boot_mmu_enable.S: slot +0x280 (Current EL, SPx, IRQ)
 * branches to irq_handler_el1 instead of panic_stub. All other slots
 * remain panic_stub — unexpected exceptions are still hard halts.
 */
.section ".text.vectors", "ax"
.balign 0x800
.globl _vectors
_vectors:
        .balign 0x80
        b       panic_stub          /* +0x000 Current EL, SP_EL0, Sync */
        .balign 0x80
        b       panic_stub          /* +0x080 Current EL, SP_EL0, IRQ */
        .balign 0x80
        b       panic_stub          /* +0x100 Current EL, SP_EL0, FIQ */
        .balign 0x80
        b       panic_stub          /* +0x180 Current EL, SP_EL0, SError */
        .balign 0x80
        b       panic_stub          /* +0x200 Current EL, SPx, Sync */
        .balign 0x80
        b       irq_handler_el1     /* +0x280 Current EL, SPx, IRQ ← REAL */
        .balign 0x80
        b       panic_stub          /* +0x300 Current EL, SPx, FIQ */
        .balign 0x80
        b       panic_stub          /* +0x380 Current EL, SPx, SError */
        .balign 0x80
        b       panic_stub          /* +0x400 Lower EL (AArch64), Sync */
        .balign 0x80
        b       panic_stub          /* +0x480 Lower EL (AArch64), IRQ */
        .balign 0x80
        b       panic_stub          /* +0x500 Lower EL (AArch64), FIQ */
        .balign 0x80
        b       panic_stub          /* +0x580 Lower EL (AArch64), SError */
        .balign 0x80
        b       panic_stub          /* +0x600 Lower EL (AArch32), Sync */
        .balign 0x80
        b       panic_stub          /* +0x680 Lower EL (AArch32), IRQ */
        .balign 0x80
        b       panic_stub          /* +0x700 Lower EL (AArch32), FIQ */
        .balign 0x80
        b       panic_stub          /* +0x780 Lower EL (AArch32), SError */
        .balign 0x80
