/*
 * Cycle 22 — boot_uart_full.S: Full PL011 init smoke.
 *
 * Extends the cycle-21 IRQ smoke (boot_irq.S) with a proper PL011
 * initialisation sequence per 05-uart/plan.md § Initialisation sequence.
 *
 * After IRQ_DONE + first PASS, the UART was brought up in cycle 11 style
 * (CR = 0x301, nothing else).  This section re-initialises it fully:
 *
 *   1. GPIO 14/15 → ALT0 (TXD0/RXD0) via GPFSEL1 read-modify-write.
 *   2. Readback-verify GPFSEL1 bits [17:12] = 0b100_100 (ALT0 on both pins).
 *   3. Disable pull-up/down via BCM2835 legacy GPPUD/GPPUDCLK0 protocol.
 *   4. UART_QUIET: last print before CR = 0.  Poll FR.TXFE first.
 *   5. [Silent reinit] CR=0, wait BUSY=0, LCRH=0 (flush), ICR=0x7FF,
 *      IBRD=26, FBRD=3, LCRH=0x70 (8N1+FIFO, latches divisors), IMSC=0,
 *      CR=0x301.
 *   6. UART_LIVE: first byte from the fully-initialised UART.
 *   7. PASS.
 *
 * Bootstrapping trap (cycle-22 inner voice): if GPFSEL is wrong, the UART
 * breaks and there is no output to diagnose it.  The readback check at step 2
 * catches a wrong FSEL value while the old minimal UART is still alive and
 * can print GPIO_ERR → panic.
 *
 * QEMU note: GPFSEL starts at 0 (all inputs) in QEMU raspi3ap; the firmware
 * presets it to 0x00012000 (ALT5) on real hardware.  After our write, QEMU
 * should return 0x00024000 (ALT0 on both pins) in the readback.  On metal
 * the pre-write value is 0x00012000; the post-write value is 0x00024000.
 * That delta is captured by GPFSEL1_PRE= / GPFSEL1_POST= sentinels.
 *
 * PASS criterion (in run-uart-full Makefile target):
 *   - GPIO_OK present (readback confirmed ALT0 on GPIO 14 and 15)
 *   - UART_LIVE present (first byte from fully-initialised UART)
 *   - PASS present (terminal marker)
 *   - guest_errors,unimp log EMPTY (cycle-11 dual-clause lesson)
 *
 * Peripheral addresses used (all in mapped Device-nGnRnE aperture):
 *   0x3F200004: GPFSEL1 (GPIO function select, pins 10-19)
 *   0x3F200094: GPPUD   (pull-up/down control)
 *   0x3F200098: GPPUDCLK0 (pull-up/down clock, GPIO 0-31)
 *   0x3F201000: PL011 DR
 *   0x3F201018: PL011 FR   (flags: TXFE bit 7, BUSY bit 3, TXFF bit 5)
 *   0x3F201024: PL011 IBRD (integer baud divisor)
 *   0x3F201028: PL011 FBRD (fractional baud divisor)
 *   0x3F20102C: PL011 LCRH (line control)
 *   0x3F201030: PL011 CR   (control)
 *   0x3F201038: PL011 IMSC (interrupt mask)
 *   0x3F201044: PL011 ICR  (interrupt clear)
 *   0x3F003000: system timer CS  (used by IRQ section)
 *   0x3F003004: system timer CLO (used by IRQ section)
 *   0x3F003010: system timer C1  (used by IRQ section)
 *   0x3F00B200: IRQ controller base
 *   0x3F00B210: Enable IRQs 1
 *   0x3F00B21C: Disable IRQs 1
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

        /* PL011 minimal enable (cycle-11 lesson: CR resets to 0). */
        ldr     x0, =0x3F201030
        mov     w1, #0x301
        str     w1, [x0]

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
         * ==================================================== */
        adr     x0, str_build_l2_ram
        bl      print_str
        ldr     x19, =l2_table_0
        ldr     x20, =0x0040000000000705
        str     x20, [x19]

        /* ====================================================
         * BUILD_L2_DEV: L2[504..511] = Device-nGnRnE blocks for
         * BCM2837 peripheral aperture 0x3F000000..0x40000000.
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

        /* MAIR, TCR, TTBR0, TTBR1 — pre-emit then write. */
        adr     x0, str_mair_eq
        bl      print_str
        ldr     x19, =0x00000000000000FF
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     mair_el1, x19

        adr     x0, str_tcr_eq
        bl      print_str
        ldr     x19, =0x00000012B5993519
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     tcr_el1, x19

        adr     x0, str_ttbr0_eq
        bl      print_str
        ldr     x19, =l1_table
        mov     x1, x19
        bl      print_hex64
        bl      print_nl
        msr     ttbr0_el1, x19

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

        /* Phase-1 MMU enable: SCTLR_EL1.M = 1 (caches still off). */
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

        /* TESTLOAD / TESTSTORE through Normal mapping. */
        adr     x0, str_testload
        bl      print_str
        ldr     x19, =0x80000
        ldr     w20, [x19]
        adr     x0, str_value_eq
        bl      print_str
        mov     x1, x20
        bl      print_hex64
        bl      print_nl

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

        /* Clear stale CS bit 1 (W1C) before reading CLO. */
        ldr     x19, =0x3F003000
        mov     w20, #0x02
        str     w20, [x19]

        /* Read CLO. */
        ldr     x19, =0x3F003004
        ldr     w22, [x19]
        adr     x0, str_irq_pre
        bl      print_str
        adr     x0, str_clo_eq
        bl      print_str
        mov     x1, x22
        bl      print_hex64
        bl      print_nl

        /* Arm C1 = CLO + 1_000_000. */
        ldr     x19, =1000000
        add     x23, x22, x19
        adr     x0, str_c1_eq
        bl      print_str
        mov     x1, x23
        bl      print_hex64
        bl      print_nl

        ldr     x19, =0x3F003010
        str     w23, [x19]

        /* Enable timer channel 1 IRQ. */
        ldr     x19, =0x3F00B210
        mov     w20, #0x02
        str     w20, [x19]

        dsb     sy
        isb

        adr     x0, str_irq_armed
        bl      print_str

        /* Unmask IRQ. */
        msr     daifclr, #2

        /* WFI: sleep until IRQ fires. */
        wfi

        /* ====================================================
         * IRQ_DONE: handler eret'd back here.
         * ==================================================== */
        adr     x0, str_irq_done
        bl      print_str

        /* IRQ phase PASS. */
        adr     x0, str_pass
        bl      print_str

        /* ====================================================
         * SEED05: entering full UART init territory.
         *
         * Everything above is the verified IRQ+MMU+cache base.
         * What follows is the 05-uart/plan.md init sequence.
         * ==================================================== */
        adr     x0, str_seed05
        bl      print_str

        /* ====================================================
         * GPIO_ALT0: mux GPIO 14 and 15 → ALT0 (TXD0 / RXD0).
         *
         * GPFSEL1 at 0x3F200004 holds 3 bits per pin for 10-19:
         *   GPIO 14: bits [14:12],  GPIO 15: bits [17:15]
         *   0b100 = ALT0 = PL011 UART0 (what we want)
         *   0b010 = ALT5 = mini-UART  (firmware default on Zero 2W)
         *
         * Print pre-write value so QEMU vs metal delta is visible.
         * ==================================================== */
        ldr     x19, =0x3F200004        /* GPFSEL1 */
        ldr     w20, [x19]

        adr     x0, str_gpfsel1_pre
        bl      print_str
        mov     x1, x20
        bl      print_hex64
        bl      print_nl

        /* Read-modify-write: clear bits [17:12], then set ALT0. */
        mov     w21, #7
        bic     w20, w20, w21, lsl #12  /* clear GPIO 14 field [14:12] */
        bic     w20, w20, w21, lsl #15  /* clear GPIO 15 field [17:15] */
        mov     w21, #4
        orr     w20, w20, w21, lsl #12  /* GPIO 14 = 0b100 = ALT0 */
        orr     w20, w20, w21, lsl #15  /* GPIO 15 = 0b100 = ALT0 */
        str     w20, [x19]

        adr     x0, str_gpio_alt0
        bl      print_str

        /* ====================================================
         * GPIO readback: verify bits [17:12] = 0b100_100 = 0x24.
         * This is the anti-bootstrapping-trap check: the UART
         * is still alive (old CR=0x301) so we can print an error
         * before it breaks.
         * ==================================================== */
        ldr     w20, [x19]

        adr     x0, str_gpfsel1_post
        bl      print_str
        mov     x1, x20
        bl      print_hex64
        bl      print_nl

        ubfx    w21, w20, #12, #6       /* bits [17:12]: GPIO 15 and 14 FSEL */
        cmp     w21, #0x24              /* 0b100_100 = ALT0 on both */
        b.eq    .gpio_fsel_ok
        adr     x0, str_gpio_err
        bl      print_str
        b       panic_stub
.gpio_fsel_ok:
        adr     x0, str_gpio_ok
        bl      print_str

        /* ====================================================
         * GPIO_PULL: disable pull-up/down on GPIO 14 and 15.
         * BCM2835 legacy GPPUD/GPPUDCLK0 protocol (NOT Pi 4).
         * Sequence per BCM2835 ARM Peripherals datasheet § 6.1.
         * ==================================================== */
        ldr     x19, =0x3F200094        /* GPPUD: 0 = no pull */
        str     wzr, [x19]
        mov     x20, #300               /* ≥150 GPIO clock cycles */
1:      subs    x20, x20, #1
        b.ne    1b
        ldr     x19, =0x3F200098        /* GPPUDCLK0: assert clock on target pins */
        movz    w20, #0xC000            /* (1<<14)|(1<<15) = bits for GPIO 14 and 15 */
        str     w20, [x19]
        mov     x20, #300
1:      subs    x20, x20, #1
        b.ne    1b
        str     wzr, [x19]              /* release clock */
        ldr     x19, =0x3F200094
        str     wzr, [x19]              /* clear GPPUD */

        dsb     sy                      /* barrier: GPIO → UART peripheral crossing */

        adr     x0, str_gpio_pull
        bl      print_str

        /* ====================================================
         * UART_QUIET: last byte before we disable the UART.
         * Poll FR.TXFE (bit 7 = 1 when TX FIFO is empty) so we
         * know all previous bytes have been transmitted.  On QEMU,
         * the FIFO model clears immediately; on metal this matters.
         * ==================================================== */
        adr     x0, str_uart_quiet
        bl      print_str

        ldr     x19, =0x3F201018        /* FR */
.wait_txfe:
        ldr     w20, [x19]
        tbz     w20, #7, .wait_txfe     /* loop while TXFE=0 (bit 7 clear) */

        /* ====================================================
         * Silent reinit period — no prints until UART_LIVE.
         *
         * If UART_QUIET is the last byte seen, the failing step
         * is one of the register writes below.  On metal, a scope
         * on GPIO 14 (TX) would show either silence or garbage
         * (wrong baud) to discriminate.
         *
         * Steps per 05-uart/plan.md § Initialisation sequence:
         * ==================================================== */

        /* Step 1: Disable UART (PL011 TRM § 3.3.7: must disable before
         * reprogramming CR). */
        ldr     x19, =0x3F201030        /* CR */
        str     wzr, [x19]

        /* Step 2: Wait for in-flight bytes to finish (FR.BUSY = bit 3). */
        ldr     x19, =0x3F201018        /* FR */
.wait_busy:
        ldr     w20, [x19]
        tbnz    w20, #3, .wait_busy     /* loop while BUSY=1 */

        /* Step 3: Flush TX FIFO by disabling FIFOs (LCRH.FEN = 0). */
        ldr     x19, =0x3F20102C        /* LCRH */
        str     wzr, [x19]

        /* Step 4: Clear all pending interrupts (RIS bits persist across disable). */
        ldr     x19, =0x3F201044        /* ICR */
        movz    w20, #0x7FF
        str     w20, [x19]

        /* Step 5: Set integer baud divisor.
         * IBRD = 26 for 115200 baud from 48 MHz UART clock.
         * IBRD and FBRD are latched only when LCRH is written — write
         * IBRD, FBRD, THEN LCRH (PL011 TRM § 3.3.6). */
        ldr     x19, =0x3F201024        /* IBRD */
        mov     w20, #26
        str     w20, [x19]

        /* Step 6: Set fractional baud divisor.
         * FBRD = 3: round(0.041666 × 64 + 0.5) = round(3.166) = 3.
         * Achieved baud ≈ 115179 Hz, error < 0.02 %. */
        ldr     x19, =0x3F201028        /* FBRD */
        mov     w20, #3
        str     w20, [x19]

        /* Step 7: Line control — 8N1, FIFO enabled.
         * LCRH = 0x70: WLEN=0b11 (8 bits), FEN=1, no parity, 1 stop bit.
         * This write also latches IBRD and FBRD into the internal divisor. */
        ldr     x19, =0x3F20102C        /* LCRH */
        mov     w20, #0x70
        str     w20, [x19]

        /* Step 8: Mask all interrupts — we are in polling mode. */
        ldr     x19, =0x3F201038        /* IMSC */
        str     wzr, [x19]

        /* Step 9: Enable UART: UARTEN (bit 0) | TXE (bit 8) | RXE (bit 9). */
        ldr     x19, =0x3F201030        /* CR */
        mov     w20, #0x301
        str     w20, [x19]

        /* ====================================================
         * UART_LIVE: first byte from the fully-initialised UART.
         *
         * If this appears: the init sequence succeeded — IBRD/FBRD
         * are correct (print_str works), LCRH was written after the
         * divisors (latching confirmed), CR re-enabled both TX and RX.
         *
         * On metal, this byte also proves GPIO 14 (TXD0) is actively
         * driving the line — the GPIO readback proved the mux register
         * was written; this byte proves the physical pin is live.
         * ==================================================== */
        adr     x0, str_uart_live
        bl      print_str

        /* Final PASS. */
        adr     x0, str_pass
        bl      print_str

2:      wfi
        b       2b

/* ============================================================
 * IRQ handler — entered via VBAR_EL1 + 0x280.
 * ============================================================ */
.globl irq_handler_el1
irq_handler_el1:
        stp     x29, x30, [sp, #-16]!
        stp     x0,  x1,  [sp, #-16]!
        stp     x2,  x3,  [sp, #-16]!
        stp     x4,  x5,  [sp, #-16]!

        adr     x0, str_irq_entry
        bl      print_str

        ldr     x4, =0x3F003000
        mov     w5, #0x02
        str     w5, [x4]

        ldr     x4, =0x3F00B21C
        mov     w5, #0x02
        str     w5, [x4]

        adr     x0, str_irq_ack
        bl      print_str

        adr     x0, str_irq_eret
        bl      print_str

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
str_seed03:         .asciz "SEED03\n"
str_pre:            .asciz "PRE\n"
str_zero_l1:        .asciz "ZERO_L1\n"
str_zero_l2:        .asciz "ZERO_L2\n"
str_build_l2_ram:   .asciz "BUILD_L2_RAM\n"
str_build_l2_dev:   .asciz "BUILD_L2_DEV\n"
str_build_l1:       .asciz "BUILD_L1\n"
str_tlbi:           .asciz "TLBI\n"
str_arm:            .asciz "ARM\n"
str_mmu1:           .asciz "MMU1\n"
str_mmu2:           .asciz "MMU2\n"
str_mmu3:           .asciz "MMU3\n"
str_live:           .asciz "LIVE\n"
str_post:           .asciz "POST\n"
str_testload:       .asciz "TESTLOAD\n"
str_teststore:      .asciz "TESTSTORE\n"
str_pass:           .asciz "PASS\n"
str_cache_pre:      .asciz "CACHE_PRE\n"
str_cache_live:     .asciz "CACHE_LIVE\n"
str_cache_pass:     .asciz "CACHE_PASS\n"
str_seed04:         .asciz "SEED04\n"
str_irq_pre:        .asciz "IRQ_PRE\n"
str_clo_eq:         .asciz "CLO="
str_c1_eq:          .asciz "C1="
str_irq_armed:      .asciz "IRQ_ARMED\n"
str_irq_entry:      .asciz "IRQ_ENTRY\n"
str_irq_ack:        .asciz "IRQ_ACK\n"
str_irq_eret:       .asciz "IRQ_ERET\n"
str_irq_done:       .asciz "IRQ_DONE\n"
str_seed05:         .asciz "SEED05\n"
str_gpfsel1_pre:    .asciz "GPFSEL1_PRE="
str_gpio_alt0:      .asciz "GPIO_ALT0\n"
str_gpfsel1_post:   .asciz "GPFSEL1_POST="
str_gpio_ok:        .asciz "GPIO_OK\n"
str_gpio_err:       .asciz "GPIO_ERR\n"
str_gpio_pull:      .asciz "GPIO_PULL\n"
str_uart_quiet:     .asciz "UART_QUIET\n"
str_uart_live:      .asciz "UART_LIVE\n"
str_sctlr_eq:       .asciz "SCTLR="
str_tcr_eq:         .asciz "TCR="
str_mair_eq:        .asciz "MAIR="
str_ttbr0_eq:       .asciz "TTBR0="
str_ttbr1_eq:       .asciz "TTBR1="
str_value_eq:       .asciz "VALUE="

.ltorg

/* --- vector table -------------------------------------------- */
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
