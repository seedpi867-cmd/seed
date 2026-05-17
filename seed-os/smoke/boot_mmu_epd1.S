/*
 * Cycle 20 — boot_mmu_epd1.S: EPD1=1 translation-fault probe.
 *
 * Extends boot_mmu_enable.S (cycles 14–15) with a deliberate high-half VA
 * load after phase-2 PASS to verify that TCR.EPD1=1 actually disables TTBR1
 * walks on QEMU's raspi3ap model.
 *
 * INVERTED PASS CRITERION (per 03-mmu/plan.md UNVERIFIED #3):
 *   'X' from panic_stub MUST appear in stdout.
 *   EPD1_FAIL MUST NOT appear.
 *   If 'X' is absent: EPD1=1 is not disabling TTBR1 walks.
 *
 * What this closes: UNVERIFIED #3 in 03-mmu/plan.md. TCR.EPD1=1 was written
 * in cycle 14 but never probed — all confidence in TTBR1-disabled rested on
 * reading the spec. This test turns that written value into a measured fact.
 *
 * The sentinel before the probe (EPD1_PROBE) names the moment: if EPD1_PROBE
 * prints but 'X' does not, the translation completed — EPD1=1 is ignored on
 * this model. The CACHE_PASS / EPD1_PROBE pair narrows the failure to the
 * window where it belongs.
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

        /* ============= 14-step EL2→EL1 drop (verbatim from boot_cpu.S) ============= */
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

        /* PL011 enable (CR.UARTEN resets to 0; cycle-11 lesson). */
        ldr     x0, =0x3F201030
        mov     w1, #0x301
        str     w1, [x0]

        /* ============================================================
         * Step 0 — SEED03: 02-cpu/PL011 path succeeded; entering MMU
         * territory.
         * ============================================================ */
        adr     x0, str_seed03
        bl      print_str

        /* ============================================================
         * Step 1 — PRE: dump the five sysregs the MMU will use.
         * ============================================================ */
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

        /* ============================================================
         * Step 2 — ZERO_L1: zero 4 KB at &l1_table.
         * ============================================================ */
        adr     x0, str_zero_l1
        bl      print_str
        ldr     x19, =l1_table
        mov     x20, #(4096 / 8)
        mov     x21, x19
.zero_l1_loop:
        str     xzr, [x21], #8
        subs    x20, x20, #1
        b.ne    .zero_l1_loop

        /* ============================================================
         * Step 3 — ZERO_L2: zero 4 KB at &l2_table_0.
         * ============================================================ */
        adr     x0, str_zero_l2
        bl      print_str
        ldr     x19, =l2_table_0
        mov     x20, #(4096 / 8)
        mov     x21, x19
.zero_l2_loop:
        str     xzr, [x21], #8
        subs    x20, x20, #1
        b.ne    .zero_l2_loop

        /* ============================================================
         * Step 4 — BUILD_L2_RAM: L2[0] = Normal-cacheable block at PA 0.
         *   descriptor = 0x0040_0000_0000_0705
         * ============================================================ */
        adr     x0, str_build_l2_ram
        bl      print_str
        ldr     x19, =l2_table_0
        ldr     x20, =0x0040000000000705
        str     x20, [x19]

        /* ============================================================
         * Step 5 — BUILD_L2_DEV: L2[504..511] = Device-nGnRnE blocks
         * covering 0x3F000000..0x40000000 (BCM2837 peripheral aperture).
         * ============================================================ */
        adr     x0, str_build_l2_dev
        bl      print_str
        ldr     x19, =l2_table_0
        add     x19, x19, #(504 * 8)
        ldr     x20, =0x006000003F000401
        mov     x21, #8
.build_dev_loop:
        str     x20, [x19], #8
        add     x20, x20, #0x200000     /* +2 MB in PA[47:21] */
        subs    x21, x21, #1
        b.ne    .build_dev_loop

        /* ============================================================
         * Step 6 — BUILD_L1: L1[0] = &l2_table_0 | 0b11 (table desc).
         * ============================================================ */
        adr     x0, str_build_l1
        bl      print_str
        ldr     x19, =l1_table
        ldr     x20, =l2_table_0
        orr     x20, x20, #0b11
        str     x20, [x19]

        /* Step 7 — dsb ishst: table writes visible to the MMU walker. */
        dsb     ishst

        /* ============================================================
         * Step 8 — TLBI: flush stale TLB entries.
         * ============================================================ */
        adr     x0, str_tlbi
        bl      print_str
        tlbi    vmalle1
        dsb     ish
        isb

        /* ============================================================
         * Step 9 — MAIR: pre-emit value, then write.
         *   slot 0 = 0x00 Device-nGnRnE, slot 1 = 0xFF Normal WB-RWA.
         * ============================================================ */
        adr     x0, str_mair_eq
        bl      print_str
        ldr     x19, =0x00000000000000FF
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     mair_el1, x19

        /* ============================================================
         * Step 10 — TCR: pre-emit value, then write.
         *   EPD1=1 at bit 23 disables TTBR1 walks — this is the bit
         *   the EPD1_PROBE below is testing.
         * ============================================================ */
        adr     x0, str_tcr_eq
        bl      print_str
        ldr     x19, =0x00000012B5993519
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     tcr_el1, x19

        /* ============================================================
         * Step 11 — TTBR0: pre-emit, write.
         * ============================================================ */
        adr     x0, str_ttbr0_eq
        bl      print_str
        ldr     x19, =l1_table
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     ttbr0_el1, x19

        /* ============================================================
         * Step 12 — TTBR1: explicit zero (EPD1 disables walks anyway).
         * ============================================================ */
        adr     x0, str_ttbr1_eq
        bl      print_str
        mov     x19, xzr
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     ttbr1_el1, x19

        /* Step 13 — isb: TCR/TTBR/MAIR writes complete before SCTLR. */
        isb

        /* ============================================================
         * Step 14 — ARM: armed sentinel. Next bundle commits MMU enable.
         * ============================================================ */
        adr     x0, str_arm
        bl      print_str

        /* Step 15 — MMU enable (set SCTLR_EL1.M = 1; C and I stay 0). */
        mrs     x0, sctlr_el1
        orr     x0, x0, #1
        msr     sctlr_el1, x0
        /* ===== THE MMU IS ON ===== */

        adr     x0, str_mmu1
        bl      print_str

        isb

        adr     x0, str_mmu2
        bl      print_str

        mrs     x22, sctlr_el1

        adr     x0, str_mmu3
        bl      print_str

        /* ============================================================
         * Step 17 — LIVE.
         * ============================================================ */
        adr     x0, str_live
        bl      print_str

        /* ============================================================
         * Step 18 — POST: re-MRS sysregs, confirm SCTLR bit 0 set.
         * ============================================================ */
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

        /* ============================================================
         * Step 19 — TESTLOAD: read first word of kernel image at 0x80000.
         * ============================================================ */
        adr     x0, str_testload
        bl      print_str
        ldr     x19, =0x80000
        ldr     w20, [x19]
        adr     x0, str_value_eq
        bl      print_str
        mov     x1, x20
        bl      print_hex64
        bl      print_nl

        /* ============================================================
         * Step 20 — TESTSTORE: write/read 0xDEADBEEF at 0x100.
         * ============================================================ */
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

        /* ============================================================
         * Step 21 — PASS: phase-1 complete.
         * ============================================================ */
        adr     x0, str_pass
        bl      print_str

        /* ============================================================
         * Phase 2 — enable D-cache and I-cache (identical to cycle 15).
         * ============================================================ */
        adr     x0, str_cache_pre
        bl      print_str
        adr     x0, str_sctlr_eq
        bl      print_str
        mrs     x1, sctlr_el1
        bl      print_hex64
        bl      print_nl

        mrs     x0, sctlr_el1
        orr     x0, x0, #(1 << 2)       /* C  = 1 (D-cache) */
        orr     x0, x0, #(1 << 12)      /* I  = 1 (I-cache) */
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

        /* ============================================================
         * EPD1 probe — Cycle 20.
         *
         * TCR.EPD1=1 (bit 23) was written at step 10. ARM ARM D8.2.2:
         * EPD1=1 means "a TLB miss on an address from TTBR1_EL1 is treated
         * as a translation fault." For a VA in the high half (bit 63 = 1),
         * the hardware walks TTBR1 — and with EPD1=1 that walk should fault
         * immediately (no table walk attempted).
         *
         * Expected execution path:
         *   ldr x1, [x0]           ← VA 0xFFFFFF8000000000 (high half)
         *   → translation fault (ESR.EC=0b100101, Data Abort from EL1)
         *   → Current EL with SP_ELx vector entry (offset 0x200)
         *   → b panic_stub
         *   → str 'X' to PL011 DR
         *
         * PASS criterion (INVERTED): 'X' MUST appear in stdout.
         * EPD1_FAIL appearing means the load retired without faulting;
         * EPD1=1 is not being honoured on this model.
         *
         * The EPD1_PROBE sentinel names the moment: if CACHE_PASS printed
         * but 'X' did not appear, the window is [EPD1_PROBE → ldr → fault].
         * ============================================================ */
        adr     x0, str_epd1_probe
        bl      print_str

        ldr     x0, =0xFFFFFF8000000000
        ldr     x1, [x0]               /* must fault with EPD1=1 */

        /* Reaching here means EPD1=1 did NOT prevent the TTBR1 walk — FAIL. */
        adr     x0, str_epd1_fail
        bl      print_str
2:      wfi
        b       2b

/* --- helpers (verbatim from boot_mmu_enable.S) ----------------------- */

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

/* --- strings ---------------------------------------------------------- */
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
str_epd1_probe:   .asciz "EPD1_PROBE\n"
str_epd1_fail:    .asciz "EPD1_FAIL\n"
str_sctlr_eq:     .asciz "SCTLR="
str_tcr_eq:       .asciz "TCR="
str_mair_eq:      .asciz "MAIR="
str_ttbr0_eq:     .asciz "TTBR0="
str_ttbr1_eq:     .asciz "TTBR1="
str_value_eq:     .asciz "VALUE="

.ltorg

.section ".text.vectors", "ax"
.balign 0x800
.globl _vectors
_vectors:
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
        b       panic_stub
        .balign 0x80
