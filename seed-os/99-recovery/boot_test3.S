/*
 * Cycle 24 — boot_test3.S: Test 3 (happy path) from 99-recovery/plan.md.
 *
 * Spec: ~/seed-os/99-recovery/plan.md § Test 3.
 *
 * Purpose: prove that a bare-metal kernel can:
 *   1. Reach _start, drop to EL1, init UART over GPIO 14/15 ALT0.
 *   2. Print "ALIVE\n" — proof it ran and UART works.
 *   3. Stop the firmware boot-watchdog via PM_RSTC direct write.
 *   4. Print "WDOG_STOP\n" — proof it didn't hang stopping the watchdog.
 *   5. Run indefinitely (ACT LED blink) — proof it's alive, not pretending.
 *
 * After this test passes under tryboot, the Pi returns to Linux on the NEXT
 * manual reset (tryboot flag is one-shot).  That proves the round-trip.
 *
 * No MMU.  No IRQ.  Physical addresses only.  Less to go wrong.
 *
 * QEMU test (make run-test3):
 *   Prints ALIVE + WDOG_STOP then hangs in WFI blink loop.
 *   PASS criterion: both strings present in stdout AND log is empty
 *   (PM_RSTC write may appear in guest_errors — see QEMU note below).
 *
 * On-metal PASS criterion (99-recovery/plan.md § Test 3):
 *   - UART (3.3V TTL on GPIO 14 TXD / GPIO 15 RXD, 115200 8N1) shows:
 *       ALIVE\r\n
 *       WDOG_STOP\r\n
 *   - ACT LED (GPIO 29) blinks at ~1 Hz.
 *   - Pi does NOT reset on its own (watchdog was stopped).
 *   - After human-triggered reset: Pi boots Linux (tryboot flag gone).
 *
 * Peripheral addresses (all Device-nGnRnE, no MMU):
 *   0x3F200004  GPFSEL1   (GPIO function select for GPIO 10-19)
 *   0x3F200008  GPFSEL2   (GPIO function select for GPIO 20-29)
 *   0x3F200094  GPPUD     (pull-up/down control)
 *   0x3F200098  GPPUDCLK0 (pull-up/down clock for GPIO 0-31)
 *   0x3F20001C  GPSET0    (set GPIO 0-31)
 *   0x3F200028  GPCLR0    (clear GPIO 0-31)
 *   0x3F201000  PL011 DR  (data register)
 *   0x3F201018  PL011 FR  (flags: TXFF=bit5, TXFE=bit7, BUSY=bit3)
 *   0x3F201024  PL011 IBRD (integer baud divisor)
 *   0x3F201028  PL011 FBRD (fractional baud divisor)
 *   0x3F20102C  PL011 LCRH (line control: 8N1 + FIFO)
 *   0x3F201030  PL011 CR   (control: UARTEN|TXE|RXE)
 *   0x3F201038  PL011 IMSC (interrupt mask)
 *   0x3F201044  PL011 ICR  (interrupt clear)
 *   0x3F10001C  PM_RSTC   (watchdog: write PM_PASSWORD|0 to disarm)
 *
 * QEMU note: QEMU raspi3ap DOES model PM_RSTC (0x3F10001C) — it accepts the
 *   write silently (no guest_errors) and treats ANY write with PM_PASSWORD as
 *   a guest reset.  With -no-reboot, QEMU then exits 0.  This is QEMU-specific
 *   behaviour; on real hardware PM_PASSWORD|0 (WRCFG=0) stops the watchdog
 *   without resetting (per Linux bcm2835_wdt_stop() and BCM2835 §6.4).
 *   Empirically confirmed Cycle 24: bad_header.img (wfi loop, no PM_RSTC)
 *   times out at exit 124; boot_test3.img exits 0 before timeout, proving
 *   the PM_RSTC write caused the simulated reset.
 *   QEMU PASS criterion: both strings printed before exit; watchdog-stop
 *   effectiveness is verified on metal (Test 3 on-metal, not in QEMU).
 */

.section ".text.boot", "ax"
.globl _start

/* ============================================================
 * ARM64 Linux image header.  Valid magic = 0x644D5241 ('ARM\x64').
 * Firmware loads this at 0x80000 with arm_64bit=1.
 * ============================================================ */
_start:
        b       code_entry              /* code0: branch past header */
        .long   0                       /* code1 */
        .quad   0x80000                 /* text_offset */
        .quad   _image_size             /* image_size */
        .quad   0x0A                    /* flags: LE, no page-size hint */
        .quad   0                       /* res2 */
        .quad   0                       /* res3 */
        .quad   0                       /* res4 */
        .ascii  "ARM\x64"              /* magic: 0x644D5241 (valid) */
        .long   0                       /* res5 */

code_entry:
        /* Park secondary cores (MPIDR Aff0 != 0). */
        mrs     x0, mpidr_el1
        and     x0, x0, #3
        cbz     x0, primary_start
1:      wfi
        b       1b

/* ============================================================
 * Primary core: EL2 → EL1 drop, then bring up UART.
 * ============================================================ */
primary_start:
        /* Temporary stack at 512K (below our load address). */
        ldr     x0, =0x80000
        mov     sp, x0

        /* Must be at EL2 — firmware drops us here. */
        mrs     x0, CurrentEL
        lsr     x0, x0, #2
        cmp     x0, #2
        b.ne    panic_stub

        /* Install panic vector table at EL2 to catch unexpected faults. */
        adr     x0, _vectors
        msr     vbar_el2, x0
        isb

        /* === 14-step EL2 → EL1 drop (per 02-cpu/plan.md) === */

        /* 1. Route all exceptions to EL2, EL1 runs AArch64. */
        mov     x0, #(1 << 31)
        msr     hcr_el2, x0

        /* 2. Allow EL1 to access virtual counter. */
        mov     x0, #0b11
        msr     cnthctl_el2, x0

        /* 3. No virtual counter offset. */
        msr     cntvoff_el2, xzr

        /* 4. Don't trap FP/SIMD from EL1. */
        mov     x0, #0x33FF
        msr     cptr_el2, x0

        /* 5. Don't trap system registers from EL1. */
        msr     hstr_el2, xzr

        /* 6. EL1 SCTLR: caches off, MMU off, little-endian. */
        ldr     x0, =0x30D00800
        msr     sctlr_el1, x0

        /* 7. Full FP/SIMD at EL1. */
        mov     x0, #(0b11 << 20)
        msr     cpacr_el1, x0

        /* 8. No debug traps. */
        msr     mdcr_el2, xzr

        /* 9. EL1 vector table (same panic stub — no IRQs this kernel). */
        adr     x0, _vectors
        msr     vbar_el1, x0

        /* 10. EL1 SP at 496K. */
        ldr     x0, =0x7C000
        msr     sp_el1, x0

        /* 11/12. Return to el1_entry at EL1h. */
        adr     x0, el1_entry
        msr     elr_el2, x0
        mov     x0, #0x3C5
        msr     spsr_el2, x0
        isb
        eret

/* ============================================================
 * EL1 entry: full PL011 UART init, print ALIVE, stop watchdog.
 * ============================================================ */
el1_entry:
        /* Re-latch VBAR_EL1 from EL1. */
        adr     x0, _vectors
        msr     vbar_el1, x0
        isb

        /* Step 0: minimal enable so we can print during GPIO setup.
         * (Cycle-11 lesson: PL011 CR resets to 0, not pre-enabled.) */
        ldr     x0, =0x3F201030         /* PL011 CR */
        mov     w1, #0x301              /* UARTEN | TXE | RXE */
        str     w1, [x0]

        /* Step 1: GPIO 14/15 → ALT0 (TXD0/RXD0 via PL011).
         *
         * GPFSEL1 [14:12] = GPIO14, [17:15] = GPIO15.
         * ALT0 = 0b100 on both.
         * Result: 0b100_100 << 12 = 0x00024000.
         *
         * On real hardware firmware leaves GPFSEL1 = 0x00012000 (ALT5 / mini-UART).
         * We override.  In QEMU GPFSEL1 starts at 0.  Either way we read-modify-write.
         */
        ldr     x19, =0x3F200004        /* GPFSEL1 */
        ldr     w0, [x19]               /* read current */
        ldr     w1, =0x000FC000         /* clear bits [17:12] (both pins) */
        bic     w0, w0, w1
        ldr     w1, =0x00024000         /* ALT0 on GPIO14 and GPIO15 */
        orr     w0, w0, w1
        str     w0, [x19]               /* write back */

        /* Readback verify — if wrong, the UART init will silently fail.
         * Catching it while we still have the old minimal UART (step 0) alive. */
        ldr     w0, [x19]               /* re-read */
        ldr     w1, =0x000FC000         /* mask bits [17:12] */
        and     w0, w0, w1
        ldr     w1, =0x00024000         /* expected: ALT0 on both */
        cmp     w0, w1
        b.ne    gpio_error

        /* Step 2: Disable pull-up/down on GPIO 14 and 15.
         * BCM2835 legacy GPPUD/GPPUDCLK0 protocol (three phases). */
        ldr     x0, =0x3F200094         /* GPPUD */
        str     wzr, [x0]               /* phase 1: control = off (0) */
        /* 150+ cycle delay */
        mov     w2, #1000
.gppud_delay1:
        subs    w2, w2, #1
        b.ne    .gppud_delay1

        ldr     x0, =0x3F200098         /* GPPUDCLK0 */
        ldr     w1, =(3 << 14)          /* clock GPIO 14 and 15 */
        str     w1, [x0]               /* phase 2: assert clock */
        /* 150+ cycle delay */
        mov     w2, #1000
.gppud_delay2:
        subs    w2, w2, #1
        b.ne    .gppud_delay2

        /* Phase 3: deassert clock and control. */
        str     wzr, [x0]               /* GPPUDCLK0 = 0 */
        ldr     x0, =0x3F200094         /* GPPUD */
        str     wzr, [x0]               /* GPPUD = 0 */

        /* Step 3: Full PL011 reinitialisation for 115200 @ 48 MHz.
         * Must wait for in-flight bytes (firmware boot banner) to flush. */

        /* Wait for TX FIFO empty (TXFE = FR bit 7). */
        ldr     x1, =0x3F201018         /* FR */
.wait_txfe:
        ldr     w0, [x1]
        tbz     w0, #7, .wait_txfe      /* loop while TXFE=0 */

        /* Wait for no ongoing transmission (BUSY = FR bit 3 = 0). */
.wait_busy:
        ldr     w0, [x1]
        tbnz    w0, #3, .wait_busy      /* loop while BUSY=1 */

        ldr     x0, =0x3F201030         /* CR */
        str     wzr, [x0]               /* CR = 0: disable UART */

        ldr     x0, =0x3F20102C         /* LCRH */
        str     wzr, [x0]               /* LCRH = 0: disable FIFOs (flush) */

        ldr     x0, =0x3F201044         /* ICR */
        ldr     w1, =0x7FF
        str     w1, [x0]                /* clear all interrupts */

        /* Baud divisor for 115200 at UARTCLK=48 MHz:
         * BAUDDIV = 48000000 / (16 * 115200) = 26.0417
         * IBRD = 26, FBRD = round(0.0417 * 64) = 3. */
        ldr     x0, =0x3F201024         /* IBRD */
        mov     w1, #26
        str     w1, [x0]

        ldr     x0, =0x3F201028         /* FBRD */
        mov     w1, #3
        str     w1, [x0]

        /* LCRH = 0x70: FIFO enable (FEN=1), 8N1 (WLEN=11, STP2=0, PEN=0). */
        ldr     x0, =0x3F20102C         /* LCRH */
        mov     w1, #0x70
        str     w1, [x0]

        ldr     x0, =0x3F201038         /* IMSC */
        str     wzr, [x0]               /* mask all interrupts */

        ldr     x0, =0x3F201030         /* CR */
        mov     w1, #0x301              /* UARTEN | TXE | RXE */
        str     w1, [x0]

        /* ====================================================
         * ALIVE: UART is up. Print proof.
         * ==================================================== */
        adr     x0, str_alive
        bl      print_str

        /* ====================================================
         * Stop the firmware boot watchdog.
         *
         * The firmware armed kernel_watchdog_timeout=10 from config.txt.
         * If we don't stop it within 10s, the SoC resets and we return
         * to Linux.  For Test 3 we want to SURVIVE — so stop it now.
         *
         * Mechanism: write PM_PASSWORD (0x5A << 24) with WRCFG = 0 to
         * PM_RSTC (ARM phys 0x3F10001C).  WRCFG = 0 means no watchdog
         * reset type is selected, disarming the trigger.
         *
         * Source: BCM2835 ARM peripherals §6.4; Linux bcm2835_wdt_stop().
         * See also 99-recovery/plan.md § Cycle 7 corrigendum.
         *
         * QEMU: PM_RSTC is not emulated.  The write will be logged in
         * guest_errors (unimplemented access) but will not fault.
         * ==================================================== */
        ldr     x0, =0x3F10001C         /* PM_RSTC */
        ldr     w1, =0x5A000000         /* PM_PASSWORD | WRCFG=0 */
        str     w1, [x0]
        dsb     sy                      /* ensure write reaches peripheral */

        /* WDOG_STOP: print proof that we survived the watchdog-stop write. */
        adr     x0, str_wdog_stop
        bl      print_str

        /* ====================================================
         * ACT LED blink loop (GPIO 29).
         *
         * Configure GPIO 29 as output, then toggle at ~1 Hz.
         * This gives a visible heartbeat while the Pi runs bare-metal.
         * Without cache the delay loop runs slowly; adjust count if needed.
         * ==================================================== */

        /* GPFSEL2 [29:27] = FSEL29.  Output = 0b001 → bit 27 set.
         *   clear mask: 0b111 << 27 = 0x38000000
         *   set output: 0b001 << 27 = 0x08000000                       */
        ldr     x0, =0x3F200008         /* GPFSEL2 */
        ldr     w1, [x0]
        ldr     w2, =0x38000000         /* clear bits [29:27] (FSEL29) */
        bic     w1, w1, w2
        ldr     w2, =0x08000000         /* 0b001 << 27 = output */
        orr     w1, w1, w2
        str     w1, [x0]

blink_loop:
        /* LED on: GPSET0 bit 29. */
        ldr     x0, =0x3F20001C         /* GPSET0 */
        ldr     w1, =0x20000000         /* bit 29 */
        str     w1, [x0]
        /* Delay: uncached tight loop, ~500ms on real hardware at 1 GHz */
        ldr     w2, =0x04000000
.blink_delay_on:
        subs    w2, w2, #1
        b.ne    .blink_delay_on

        /* LED off: GPCLR0 bit 29. */
        ldr     x0, =0x3F200028         /* GPCLR0 */
        ldr     w1, =0x20000000         /* bit 29 */
        str     w1, [x0]
        /* Delay. */
        ldr     w2, =0x04000000
.blink_delay_off:
        subs    w2, w2, #1
        b.ne    .blink_delay_off

        b       blink_loop

/* ============================================================
 * gpio_error: GPIO readback mismatch.  Print sentinel and panic.
 * ============================================================ */
gpio_error:
        adr     x0, str_gpio_err
        bl      print_str
        /* fall through to panic_stub */

/* ============================================================
 * panic_stub: unexpected fault or explicit jump.
 * Prints 'X' and halts.  This is the tripwire — if 'X' appears
 * when it shouldn't, a fault occurred upstream.
 * ============================================================ */
panic_stub:
        ldr     x0, =0x3F201030         /* CR — re-enable UART in case it's off */
        mov     w1, #0x301
        str     w1, [x0]
        ldr     x0, =0x3F201000         /* DR */
        mov     w1, #'X'
        str     w1, [x0]
.panic_halt:
        wfi
        b       .panic_halt

/* ============================================================
 * print_str: print null-terminated string at x0 to PL011.
 * Polls FR.TXFF (bit 5) before each byte — writes when not full.
 * Clobbers x0, x1, x2, w3.
 * ============================================================ */
print_str:
        mov     x1, x0                  /* string pointer */
        ldr     x2, =0x3F201000         /* PL011 DR */
.print_loop:
        ldrb    w3, [x1], #1            /* load byte, advance pointer */
        cbz     w3, .print_done         /* stop at null terminator */
.txff_poll:
        ldr     x0, =0x3F201018         /* FR */
        ldr     w0, [x0]
        tbnz    w0, #5, .txff_poll      /* loop while TXFF (TX FIFO full) */
        str     w3, [x2]                /* write to DR */
        b       .print_loop
.print_done:
        ret

/* ============================================================
 * Vector table: 2 KiB aligned, 128-byte entries.
 * All entries jump to panic_stub — no IRQs in this kernel.
 * ============================================================ */
.balign 2048
_vectors:
.set voff, 0
.rept 16
        .balign 128
        b       panic_stub
.endr

/* ============================================================
 * String constants.
 * ============================================================ */
str_alive:
        .ascii  "ALIVE\r\n\0"

str_wdog_stop:
        .ascii  "WDOG_STOP\r\n\0"

str_gpio_err:
        .ascii  "GPIO_ERR\r\n\0"

.end
