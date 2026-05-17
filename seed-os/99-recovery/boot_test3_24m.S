/*
 * Cycle 25 — boot_test3_24m.S: Test 3 alternate (24 MHz UART clock variant).
 *
 * IDENTICAL to boot_test3.S except:
 *   - IBRD = 13, FBRD = 1   (115200 baud assuming UARTCLK = 24 MHz)
 *   - str_alive prints "ALIVE_24M\r\n" to distinguish on a terminal
 *
 * WHY: init_uart_clock=48000000 should deliver 48 MHz, but if the firmware
 * halves the clock (e.g. because of a silent /2 divider, firmware bug, or
 * misconfiguration) the actual UARTCLK is 24 MHz.  At 48 MHz divisors the
 * human would see garbage; this binary tries 24 MHz divisors instead.
 *
 * Protocol:
 *   1. Try boot_test3.img (48 MHz) first.  Connect UART adapter at 115200.
 *      - PASS: see "ALIVE" then "WDOG_STOP" → clock is 48 MHz, done.
 *      - FAIL: garbage on UART but ACT LED blinks → clock may be 24 MHz.
 *   2. If FAIL, copy this binary to seed/kernel8.img and retry.
 *      - PASS: see "ALIVE_24M" then "WDOG_STOP_24M" → clock confirmed 24 MHz.
 *        Update goals.md: use IBRD=13,FBRD=1 in all future kernels.
 *
 * Baud math:
 *   UARTCLK=24 MHz: BAUDDIV = 24000000 / (16 * 115200) = 13.02
 *   IBRD = 13, FBRD = round(0.02 * 64) = 1.
 *
 * Everything else (EL2→EL1 drop, GPIO mux, watchdog stop, LED blink)
 * is unchanged from boot_test3.S.
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

        /* Step 0: minimal enable (use whatever divisors firmware left). */
        ldr     x0, =0x3F201030
        mov     w1, #0x301
        str     w1, [x0]

        /* Step 1: GPIO 14/15 → ALT0. */
        ldr     x19, =0x3F200004
        ldr     w0, [x19]
        ldr     w1, =0x000FC000
        bic     w0, w0, w1
        ldr     w1, =0x00024000
        orr     w0, w0, w1
        str     w0, [x19]

        ldr     w0, [x19]
        ldr     w1, =0x000FC000
        and     w0, w0, w1
        ldr     w1, =0x00024000
        cmp     w0, w1
        b.ne    gpio_error

        /* Step 2: disable pull-up/down on GPIO 14/15. */
        ldr     x0, =0x3F200094
        str     wzr, [x0]
        mov     w2, #1000
.gppud_delay1:
        subs    w2, w2, #1
        b.ne    .gppud_delay1

        ldr     x0, =0x3F200098
        ldr     w1, =(3 << 14)
        str     w1, [x0]
        mov     w2, #1000
.gppud_delay2:
        subs    w2, w2, #1
        b.ne    .gppud_delay2

        str     wzr, [x0]
        ldr     x0, =0x3F200094
        str     wzr, [x0]

        /* Step 3: PL011 reinit for 115200 @ 24 MHz. */
        ldr     x1, =0x3F201018
.wait_txfe:
        ldr     w0, [x1]
        tbz     w0, #7, .wait_txfe

.wait_busy:
        ldr     w0, [x1]
        tbnz    w0, #3, .wait_busy

        ldr     x0, =0x3F201030
        str     wzr, [x0]

        ldr     x0, =0x3F20102C
        str     wzr, [x0]

        ldr     x0, =0x3F201044
        ldr     w1, =0x7FF
        str     w1, [x0]

        /* IBRD=13, FBRD=1: 115200 baud @ 24 MHz.
         * 24000000 / (16 * 115200) = 13.02 → IBRD=13, FBRD=round(0.02*64)=1. */
        ldr     x0, =0x3F201024
        mov     w1, #13
        str     w1, [x0]

        ldr     x0, =0x3F201028
        mov     w1, #1
        str     w1, [x0]

        ldr     x0, =0x3F20102C
        mov     w1, #0x70
        str     w1, [x0]

        ldr     x0, =0x3F201038
        str     wzr, [x0]

        ldr     x0, =0x3F201030
        mov     w1, #0x301
        str     w1, [x0]

        adr     x0, str_alive
        bl      print_str

        /* Stop watchdog. */
        ldr     x0, =0x3F10001C
        ldr     w1, =0x5A000000
        str     w1, [x0]
        dsb     sy

        adr     x0, str_wdog_stop
        bl      print_str

        /* ACT LED blink (GPIO 29). */
        ldr     x0, =0x3F200008
        ldr     w1, [x0]
        ldr     w2, =0x38000000
        bic     w1, w1, w2
        ldr     w2, =0x08000000
        orr     w1, w1, w2
        str     w1, [x0]

blink_loop:
        ldr     x0, =0x3F20001C
        ldr     w1, =0x20000000
        str     w1, [x0]
        ldr     w2, =0x04000000
.blink_delay_on:
        subs    w2, w2, #1
        b.ne    .blink_delay_on

        ldr     x0, =0x3F200028
        ldr     w1, =0x20000000
        str     w1, [x0]
        ldr     w2, =0x04000000
.blink_delay_off:
        subs    w2, w2, #1
        b.ne    .blink_delay_off

        b       blink_loop

gpio_error:
        adr     x0, str_gpio_err
        bl      print_str

panic_stub:
        ldr     x0, =0x3F201030
        mov     w1, #0x301
        str     w1, [x0]
        ldr     x0, =0x3F201000
        mov     w1, #'X'
        str     w1, [x0]
.panic_halt:
        wfi
        b       .panic_halt

print_str:
        mov     x1, x0
        ldr     x2, =0x3F201000
.print_loop:
        ldrb    w3, [x1], #1
        cbz     w3, .print_done
.txff_poll:
        ldr     x0, =0x3F201018
        ldr     w0, [x0]
        tbnz    w0, #5, .txff_poll
        str     w3, [x2]
        b       .print_loop
.print_done:
        ret

.balign 2048
_vectors:
.set voff, 0
.rept 16
        .balign 128
        b       panic_stub
.endr

str_alive:
        .ascii  "ALIVE_24M\r\n\0"

str_wdog_stop:
        .ascii  "WDOG_STOP_24M\r\n\0"

str_gpio_err:
        .ascii  "GPIO_ERR_24M\r\n\0"

.end
