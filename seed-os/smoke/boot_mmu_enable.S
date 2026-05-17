/*
 * Cycles 14–15 — boot_mmu_enable.S: phase-1 + phase-2 MMU bring-up smoke.
 *
 * Implements `03-mmu/plan.md § Bring-up sequence` (the 22-step contract)
 * and `03-mmu/plan.md § Phase 2: enable caches` on top of cycle-11's
 * EL2→EL1 drop + cycle-12's print helpers.
 *
 * The design commitment from `03-mmu/plan.md § The print loop must outlive
 * the mistake`: every MSR or store that could fault is preceded by a
 * sentinel that names it (and, for value-bearing writes, prints the
 * load-bearing value being committed). If silence falls after sentinel N,
 * the failing step is between N and N+1, and the printed values above N
 * are the post-mortem.
 *
 * Cycle-13 inner-voice refinement (phase 1): the original plan had a
 * single LIVE sentinel ~four instructions after ARM. That window covered
 * (mrs SCTLR, orr +1, msr SCTLR, isb) — too wide. Split into MMU1 (after
 * msr SCTLR), MMU2 (after isb), MMU3 (after the first post-MMU mrs).
 * MMU1 proves the msr did not fault AND instruction-fetch + PL011-store
 * under the new translation regime work. MMU2 proves the isb did not
 * fault. MMU3 proves the first sysreg read in the new regime works.
 * Three distinct surviving instructions, three distinct sentinels.
 *
 * Cycle-15 inner-voice correction (phase 2): do NOT split the cache
 * enable into CACHE1/CACHE2/CACHE3. The cache-enable instruction bundle
 * has ONE architectural moment, not three — none of mrs/orr/orr/msr/isb
 * faults, and nothing changes observable behaviour until the msr+isb
 * pair commits. Three sentinels mark three distinct moments only when
 * the moments are distinct. Otherwise the discipline degrades into
 * pattern-worship. Phase 2 uses CACHE_PRE / CACHE_LIVE / CACHE_PASS at
 * pre-state / first-store-under-new-regime / terminal-marker boundaries.
 *
 * Phase 1: SCTLR_EL1.M = 1, C = 0, I = 0 (caches off ⇒ no coherency).
 * Phase 2: SCTLR_EL1.C = 1, I = 1 (caches on; D + I).
 *
 * Target: QEMU -M raspi3ap. Do NOT run on metal (no 05-uart pin-mux).
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
         * territory. If this is the last byte that escapes, the failure
         * is upstream of MMU work (regression in the EL2→EL1 drop or
         * PL011 CR enable).
         * ============================================================ */
        adr     x0, str_seed03
        bl      print_str

        /* ============================================================
         * Step 1 — PRE: dump the five sysregs the MMU will use.
         * Capturing pre-state so a post-state delta is meaningful.
         * Any MRS faulting here is an EL1 entry-state regression.
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
         * Step 2 — ZERO_L1: zero 4 KB at &l1_table (512 × 8-byte stores).
         * Pre-MMU, Device-default-ordering; stores go through.
         * Linker guarantees l1_table is 4 KB aligned.
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
         * Step 3 — ZERO_L2: same for the L2 table.
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
         *     UXN=1 PXN=0 nG=0 AF=1 SH=0b11 AP=0b00 NS=0
         *     AttrIndx=001 (MAIR slot 1) TYPE=0b01 (block)
         * Covers VA 0x00000000..0x00200000 (kernel image + stacks +
         * page tables themselves).
         * ============================================================ */
        adr     x0, str_build_l2_ram
        bl      print_str
        ldr     x19, =l2_table_0
        ldr     x20, =0x0040000000000705
        str     x20, [x19]

        /* ============================================================
         * Step 5 — BUILD_L2_DEV: L2[504..511] = Device-nGnRnE blocks
         * covering 0x3F000000..0x40000000 (BCM2837 peripheral aperture).
         *   504: 0x0060_0000_3F00_0401   (mailbox region)
         *   505: 0x0060_0000_3F20_0401   (PL011 region)
         *   ...
         *   511: 0x0060_0000_3FE0_0401
         * Increment per step = +2 MB lifted into PA[47:21].
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
         * L1[1..511] left zero (invalid) by the ZERO_L1 step.
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
         * Step 8 — TLBI: flush any stale TLB entries (there shouldn't
         * be any, but the architecture sequence requires it).
         * ============================================================ */
        adr     x0, str_tlbi
        bl      print_str
        tlbi    vmalle1
        dsb     ish
        isb

        /* ============================================================
         * Step 9 — MAIR: pre-emit the value being committed, then write.
         *   MAIR_EL1 = 0x00000000000000FF
         *     slot 0 = 0x00 Device-nGnRnE (MMIO)
         *     slot 1 = 0xFF Normal WB-RWA inner+outer (RAM)
         * ============================================================ */
        adr     x0, str_mair_eq
        bl      print_str
        ldr     x19, =0x00000000000000FF
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     mair_el1, x19

        /* ============================================================
         * Step 10 — TCR: pre-emit, write.
         *   TCR_EL1 = 0x00000012B5993519
         *     T0SZ=25 IRGN0=01 ORGN0=01 SH0=11 TG0=00
         *     T1SZ=25 EPD1=1 (TTBR1 disabled this cycle)
         *     IRGN1=01 ORGN1=01 SH1=11 TG1=10 IPS=010 (40-bit) AS=1 (16-bit ASID)
         * No effect until SCTLR.M=1 (translation gated on enable).
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
         *   TTBR0_EL1 = &l1_table (ASID=0, CnP=0)
         * 4 KB-aligned by linker; low bits == 0 ⇒ value == base addr.
         * ============================================================ */
        adr     x0, str_ttbr0_eq
        bl      print_str
        ldr     x19, =l1_table
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     ttbr0_el1, x19

        /* ============================================================
         * Step 12 — TTBR1: explicit zero (EPD1 disables walks anyway,
         * but logged so post-MMU re-MRS sees a known value).
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
         * Step 14 — ARM: the armed sentinel. The next instruction
         * bundle commits the MMU enable. If ARM is the last byte that
         * escapes, the printed MAIR/TCR/TTBR values are the post-mortem.
         * ============================================================ */
        adr     x0, str_arm
        bl      print_str

        /* Step 15 — MMU enable (set SCTLR_EL1.M = 1; C and I stay 0). */
        mrs     x0, sctlr_el1
        orr     x0, x0, #1
        msr     sctlr_el1, x0
        /* ===== THE MMU IS ON ===== */

        /* ============================================================
         * Sentinel MMU1 — first store through the new translation
         * regime. If this prints: the L2[505] device mapping is valid,
         * the page-table walker accepted the descriptors, and PL011
         * reaches MMIO correctly. The msr above did not fault.
         * ============================================================ */
        adr     x0, str_mmu1
        bl      print_str

        /* Step 16 — isb: synchronize before further sysreg access. */
        isb

        /* ============================================================
         * Sentinel MMU2 — post-isb. If MMU1 printed but MMU2 didn't,
         * the isb itself raised something (extremely unlikely).
         * ============================================================ */
        adr     x0, str_mmu2
        bl      print_str

        /* First post-MMU MRS. Stash in x22 (callee-saved across helpers)
         * for POST printing. */
        mrs     x22, sctlr_el1

        /* ============================================================
         * Sentinel MMU3 — first post-MMU MRS succeeded. If MMU2 printed
         * but MMU3 didn't, the mrs raised UNDEFINED (shouldn't happen
         * for SCTLR_EL1 at EL1).
         * ============================================================ */
        adr     x0, str_mmu3
        bl      print_str

        /* ============================================================
         * Step 17 — LIVE: past the four-instruction blind spot.
         * From here on, sentinels and value-prints proceed normally.
         * ============================================================ */
        adr     x0, str_live
        bl      print_str

        /* ============================================================
         * Step 18 — POST: re-MRS the five sysregs and re-print.
         * Expected delta: SCTLR has bit 0 set (M=1); others unchanged.
         * ============================================================ */
        adr     x0, str_post
        bl      print_str

        adr     x0, str_sctlr_eq
        bl      print_str
        mov     x1, x22                 /* SCTLR captured at MMU3 boundary */
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
         * Through Normal-cacheable mapping (caches off ⇒ memory). Value
         * is `b code_entry` encoding; not asserting equality, just
         * printing — silence here = L2[0] mapping broken.
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
         * Step 20 — TESTSTORE: write 0xDEADBEEF at 0x100, read back.
         * Exercises the RW path through the Normal-cacheable mapping.
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
         * Step 21 — PASS: phase-1 every sentinel reached.
         * ============================================================ */
        adr     x0, str_pass
        bl      print_str

        /* ============================================================
         * Phase 2 — enable D-cache and I-cache.
         *
         * Honest sentinel discipline (cycle-15 inner-voice correction):
         * cache enable has ONE architectural moment, not three. The
         * mrs/orr/orr/msr/isb sequence is internally invariant — none
         * of those instructions can fault, none changes observable
         * behaviour until the msr+isb pair commits caches-on. Adding
         * CACHE1/CACHE2/CACHE3 between them would mark instruction
         * boundaries, not architectural ones. That's pattern-worship,
         * not rigor.
         *
         * Three sentinels at three distinct moments:
         *   CACHE_PRE  — pre-state captured (SCTLR before change)
         *   CACHE_LIVE — first PL011 store under cache-on regime
         *                (proves device mapping survived cache enable)
         *   CACHE_PASS — SCTLR re-MRS confirms 0x30d01805
         *
         * Failure modes guarded against:
         *  - CACHE_PRE never prints  ⇒ regression in phase-1 (impossible
         *    if PASS just printed)
         *  - CACHE_LIVE never prints ⇒ cache enable broke MMIO path
         *    (PL011 store no longer reaches device). Most likely cause:
         *    Device-nGnRnE attribute mis-set on L2[505] and only the
         *    cache enable exposed it (gathering through a stray Normal
         *    mapping). The SCTLR value printed at CACHE_PRE is the
         *    post-mortem precondition.
         *  - CACHE_PASS never prints ⇒ post-MMR-isb fault. The
         *    SCTLR value printed just before is the post-mortem.
         * ============================================================ */

        /* Pre-cache sentinel + SCTLR pre-state. */
        adr     x0, str_cache_pre
        bl      print_str
        adr     x0, str_sctlr_eq
        bl      print_str
        mrs     x1, sctlr_el1
        bl      print_hex64
        bl      print_nl

        /* The single architectural moment: caches on. */
        mrs     x0, sctlr_el1
        orr     x0, x0, #(1 << 2)       /* C  = 1 (D-cache) */
        orr     x0, x0, #(1 << 12)      /* I  = 1 (I-cache) */
        msr     sctlr_el1, x0
        isb

        /* First PL011 store under caches-on. If this byte appears,
         * the Device-nGnRnE mapping for L2[505] was unaffected by
         * cache enable — gathering/reordering are still forbidden. */
        adr     x0, str_cache_live
        bl      print_str

        /* Confirm SCTLR has bits 0, 2, 12 set: expect 0x30d01805. */
        adr     x0, str_sctlr_eq
        bl      print_str
        mrs     x1, sctlr_el1
        bl      print_hex64
        bl      print_nl

        /* Phase-2 PASS. */
        adr     x0, str_cache_pass
        bl      print_str

        /* End of cycle-15 smoke. */
2:      wfi
        b       2b

/* --- helpers (unchanged from boot_mmu_probe.S) ------------------------ */

/* print_str(x0 = ptr to NUL-terminated string).
 * Trashes x0, x2, x3. Returns via x30 (not nested). */
print_str:
        ldr     x3, =0x3F201000
.ps_loop:
        ldrb    w2, [x0], #1
        cbz     w2, .ps_done
        str     w2, [x3]
        b       .ps_loop
.ps_done:
        ret

/* print_nl: emit '\n'. Trashes x2, x3. */
print_nl:
        ldr     x3, =0x3F201000
        mov     w2, #'\n'
        str     w2, [x3]
        ret

/* print_hex64(x1 = value). Emits "0x" + 16 lowercase hex digits, MSN first.
 * Trashes x0, x2, x3, x4, x5. Preserves x1. Returns via x30 (not nested). */
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
str_sctlr_eq:     .asciz "SCTLR="
str_tcr_eq:       .asciz "TCR="
str_mair_eq:      .asciz "MAIR="
str_ttbr0_eq:     .asciz "TTBR0="
str_ttbr1_eq:     .asciz "TTBR1="
str_value_eq:     .asciz "VALUE="

.ltorg

/* Same vector table as boot_mmu_probe.S — every entry → panic_stub. */
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
