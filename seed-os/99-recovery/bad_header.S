/*
 * Cycle 23 — Test 0b (malformed-header preflight).
 *
 * Spec: ~/seed-os/99-recovery/plan.md § Test 0b.
 * Target: on-metal only (firmware header validation is not emulated by QEMU).
 *
 * This kernel has a valid ARM64 image header structure EXCEPT the magic at
 * offset 0x38 is 0x00000000 instead of 0x644D5241 ('ARM\x64').
 *
 * Purpose: verify that the tryboot + boot-watchdog recovery mechanism fires
 * before any kernel that can actually do damage is installed.
 *
 *   Firmware validates magic → refuses to load → boot watchdog fires
 *                                                  immediately → Linux boots.
 *   Firmware skips validation → loads → _start executes `wfi; b .` forever
 *                            → boot watchdog fires after kernel_watchdog_timeout
 *                              seconds → Linux boots.
 *
 * Either outcome == Linux returns. Time to return distinguishes the two paths.
 *
 * QEMU run: image loops in WFI, SIGTERM after timeout, empty log. This
 * confirms the image assembles and runs cleanly; it does NOT verify firmware
 * header-validation behaviour (firmware is not present in QEMU).
 */

.section ".text.boot", "ax"
.globl _start

_start:
        /* Jump past the header in case firmware loads us despite the bad magic. */
        b       after_header
        .long   0                       /* code1 (filler nop) */

        /* ARM64 image header — all fields valid EXCEPT the magic below. */
        .quad   0x80000                 /* text_offset: load at 0x80000 */
        .quad   _image_size             /* image_size */
        .quad   0x00                    /* flags: LE, no page-size hint */
        .quad   0                       /* res2 */
        .quad   0                       /* res3 */
        .quad   0                       /* res4 */
        .word   0x00000000              /* INVALID magic (valid = 0x644D5241) */
        .word   0                       /* res5 */

after_header:
        /*
         * If firmware loaded us despite the bad magic: wait for the boot
         * watchdog to fire.  Never touch UART — the point is to measure the
         * recovery mechanism, not to produce output.
         */
1:      wfi
        b       1b
