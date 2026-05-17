/*
 * Cycle 26 — sd_poll.S
 *
 * Extends boot_test3 (UART alive + watchdog stop) with a full BCM2835 SDHOST
 * init sequence and a single-sector read of sector 0 (MBR).
 *
 * On-metal PASS criteria:
 *   UART shows, in order:
 *     ALIVE\r\n
 *     WDOG_STOP\r\n
 *     SD_START\r\n
 *     SD_P0\r\n          (Phase 0: controller reset complete)
 *     CMD0_OK\r\n
 *     CMD8_RSP=000001AA  (must equal 000001AA for SDHC/SDXC)
 *     CMD8_OK\r\n
 *     ACMD41_RDY\r\n
 *     CCS=1\r\n           (SDHC/SDXC; CCS=0 means SDSC — rare for 119GB card)
 *     CMD2_OK\r\n
 *     RCA=XXXX\r\n        (any non-zero RCA)
 *     CMD7_OK\r\n
 *     CLK_HI\r\n
 *     SD_INIT_OK\r\n
 *     CMD17_OK\r\n
 *     MBR: 55 AA\r\n     (MBR signature at bytes 510-511)
 *     SD_PASS\r\n
 *   ACT LED blinks ~1 Hz.
 *
 * QEMU PASS criteria (QEMU has no SDHOST emulation):
 *   UART shows ALIVE\r\n + WDOG_STOP\r\n + SD_START\r\n + SD_P0\r\n
 *   followed eventually by ERR_ACMD41_TIMEOUT\r\n
 *   (SDRSP0 always reads 0 → OCR.bit31=0 → retry exhausted)
 *   Exit 143 (SIGTERM) after timeout; SD guest_errors in log are expected.
 *
 * On-metal error paths:
 *   Any ERR_ message followed by:
 *     SDCMD=XXXXXXXX\r\n   (raw SDCMD register at time of error)
 *     SDHSTS=XXXXXXXX\r\n  (raw SDHSTS register at time of error)
 *   Then ACT LED fast-blinks (panic pattern).
 *
 * Register conventions:
 *   x19 = SDHOST base (0x3F202000), set in el1_entry and preserved throughout.
 *   x20 = RCA[15:0], set after CMD3 response.
 *   x21 = CCS flag (1 = SDHC/SDXC, 0 = SDSC).
 *   x22 = polling loop counter (caller owns, no save expected).
 *   x23 = ACMD41 retry counter.
 *   x24 = sector buffer pointer during FIFO drain.
 *   x30 = LR; saved on stack by any function that calls another.
 *
 * Peripheral addresses:
 *   SDHOST base:  0x3F202000
 *   PL011 base:   0x3F201000
 *   GPIO base:    0x3F200000
 *   PM_RSTC:      0x3F10001C
 */

/* ---- SDHOST register offsets (from base 0x3F202000) ---- */
.equ SDCMD_OFF,  0x00   /* command + flag bits */
.equ SDARG_OFF,  0x04   /* command argument */
.equ SDTOUT_OFF, 0x08   /* data timeout */
.equ SDCDIV_OFF, 0x0C   /* clock divider: SD_clk = 250MHz / (CDIV+2) */
.equ SDRSP0_OFF, 0x10   /* response word 0 [31:0] */
.equ SDRSP1_OFF, 0x14   /* response word 1 [63:32] */
.equ SDRSP2_OFF, 0x18   /* response word 2 [95:64] */
.equ SDRSP3_OFF, 0x1C   /* response word 3 [127:96] */
.equ SDHSTS_OFF, 0x20   /* host status: errors + interrupt flags */
.equ SDVDD_OFF,  0x30   /* VDD control: 1 = 3.3V on */
.equ SDEDM_OFF,  0x34   /* emergency debug mode */
.equ SDHCFG_OFF, 0x38   /* host config: IRQ enables, bus width */
.equ SDHBCT_OFF, 0x3C   /* block byte count */
.equ SDDATA_OFF, 0x40   /* data FIFO */
.equ SDHBLC_OFF, 0x50   /* block count */

/* ---- SDCMD flag bits (ORed into command word before writing) ---- */
.equ CMD_NEW,    0x8000  /* bit15: write 1 to submit; hardware clears when done */
.equ CMD_FAIL,   0x4000  /* bit14: read-only; set by hardware on error */
.equ CMD_BUSY,   0x0800  /* bit11: R1b — wait for card to deassert DAT0 busy */
.equ CMD_NORESP, 0x0400  /* bit10: no response expected (CMD0) */
.equ CMD_LONG,   0x0200  /* bit9:  128-bit response (CMD2 CID) */
.equ CMD_READ,   0x0040  /* bit6:  data read direction */

/* ---- SDHSTS flag bits ---- */
.equ HST_BUSY,   0x0400  /* bit10: card released busy (R1b done) */
.equ HST_BLOCK,  0x0200  /* bit9:  block transfer complete */
.equ HST_RWTOUT, 0x0080  /* bit7:  read/write data timeout */
.equ HST_CMDTOU, 0x0040  /* bit6:  command response timeout */
.equ HST_CRC7,   0x0020  /* bit5:  CRC7 error in command response */
.equ HST_CRC16,  0x0010  /* bit4:  CRC16 error in data */
.equ HST_FIFO,   0x0008  /* bit3:  FIFO over/underrun */
.equ HST_DATA,   0x0001  /* bit0:  data available in FIFO */

/* ============================================================
 * ARM64 Linux image header (valid magic for tryboot).
 * ============================================================ */
.section ".text.boot", "ax"
.globl _start

_start:
        b       code_entry
        .long   0
        .quad   0x80000                 /* text_offset */
        .quad   _image_size             /* image_size */
        .quad   0x0A                    /* flags: LE */
        .quad   0
        .quad   0
        .quad   0
        .ascii  "ARM\x64"              /* magic */
        .long   0

/* ============================================================
 * Entry: park secondaries, EL2 check.
 * ============================================================ */
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

        /* EL2 → EL1 drop (14-step sequence, per 02-cpu/plan.md). */
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

/* ============================================================
 * EL1 entry: full PL011 UART init, then SD init + sector read.
 * ============================================================ */
el1_entry:
        adr     x0, _vectors
        msr     vbar_el1, x0
        isb

        /* Minimal UART enable so we can print during GPIO setup. */
        ldr     x0, =0x3F201030         /* PL011 CR */
        mov     w1, #0x301
        str     w1, [x0]

        /* GPIO 14/15 → ALT0 (PL011 TXD0/RXD0). */
        ldr     x19, =0x3F200004        /* GPFSEL1 */
        ldr     w0, [x19]
        ldr     w1, =0x000FC000
        bic     w0, w0, w1
        ldr     w1, =0x00024000
        orr     w0, w0, w1
        str     w0, [x19]
        ldr     w0, [x19]               /* readback verify */
        ldr     w1, =0x000FC000
        and     w0, w0, w1
        ldr     w1, =0x00024000
        cmp     w0, w1
        b.ne    gpio_error

        /* Pull-up/down off on GPIO 14, 15 (BCM2835 legacy GPPUD protocol). */
        ldr     x0, =0x3F200094         /* GPPUD */
        str     wzr, [x0]
        mov     w2, #1000
.gppud_d1:
        subs    w2, w2, #1
        b.ne    .gppud_d1
        ldr     x0, =0x3F200098         /* GPPUDCLK0 */
        ldr     w1, =(3 << 14)
        str     w1, [x0]
        mov     w2, #1000
.gppud_d2:
        subs    w2, w2, #1
        b.ne    .gppud_d2
        str     wzr, [x0]
        ldr     x0, =0x3F200094
        str     wzr, [x0]

        /* Full PL011 reinit: 115200 @ 48 MHz (IBRD=26, FBRD=3). */
        ldr     x1, =0x3F201018         /* FR */
.wait_txfe:
        ldr     w0, [x1]
        tbz     w0, #7, .wait_txfe
.wait_busy:
        ldr     w0, [x1]
        tbnz    w0, #3, .wait_busy
        ldr     x0, =0x3F201030
        str     wzr, [x0]               /* CR = 0: disable */
        ldr     x0, =0x3F20102C
        str     wzr, [x0]               /* LCRH = 0: disable FIFOs (flush) */
        ldr     x0, =0x3F201044
        ldr     w1, =0x7FF
        str     w1, [x0]                /* ICR: clear all interrupts */
        ldr     x0, =0x3F201024
        mov     w1, #26
        str     w1, [x0]                /* IBRD = 26 */
        ldr     x0, =0x3F201028
        mov     w1, #3
        str     w1, [x0]                /* FBRD = 3 */
        ldr     x0, =0x3F20102C
        mov     w1, #0x70
        str     w1, [x0]                /* LCRH: 8N1 + FIFO enable */
        ldr     x0, =0x3F201038
        str     wzr, [x0]               /* IMSC: mask all interrupts */
        ldr     x0, =0x3F201030
        mov     w1, #0x301
        str     w1, [x0]                /* CR: UARTEN | TXE | RXE */

        adr     x0, str_alive
        bl      print_str

        /* Stop firmware watchdog (PM_PASSWORD | WRCFG=0). */
        ldr     x0, =0x3F10001C
        ldr     w1, =0x5A000000
        str     w1, [x0]
        dsb     sy
        adr     x0, str_wdog_stop
        bl      print_str

        /* ============================================================
         * SD init: x19 = SDHOST base throughout.
         * ============================================================ */
        ldr     x19, =0x3F202000

        adr     x0, str_sd_start
        bl      print_str

        /* ---- Phase 0: controller reset ---- */
        /*
         * Snapshot SDHSTS before touching anything — forensic record of whatever
         * Linux left latched. Print it, THEN clear it.
         * SDHSTS is write-1-to-clear; writing 0x7FF clears all defined bits.
         * Without clearing, a stale BUSY_IRPT (bit10) from Linux's last CMD7
         * could make our CMD7 busy-poll return immediately with a false positive.
         */
        ldr     w9, [x19, #SDHSTS_OFF]  /* snapshot before touching anything */
        adr     x0, str_sdhsts_pre
        bl      print_str
        mov     w0, w9
        bl      print_hex32
        ldr     w1, =0x7FF
        str     w1, [x19, #SDHSTS_OFF]  /* now clear */
        dsb     sy

        mov     w1, #1
        str     w1, [x19, #SDVDD_OFF]   /* 3.3V on */

        /* ~7ms delay for VDD to settle. */
        ldr     w22, =0x00100000
.delay_vdd:
        subs    w22, w22, #1
        b.ne    .delay_vdd

        str     wzr, [x19, #SDCMD_OFF]  /* flush any pending command */
        str     wzr, [x19, #SDARG_OFF]
        str     wzr, [x19, #SDHCFG_OFF] /* polling mode, 1-bit bus, no IRQs */
        str     wzr, [x19, #SDHBCT_OFF]
        str     wzr, [x19, #SDHBLC_OFF]

        /* Init clock: CDIV=623 → 250MHz/(623+2) = ~400 kHz. */
        ldr     w1, =623
        str     w1, [x19, #SDCDIV_OFF]

        /* ~1ms clock settle. */
        ldr     w22, =200000
.delay_clk0:
        subs    w22, w22, #1
        b.ne    .delay_clk0

        adr     x0, str_sd_p0
        bl      print_str

        /* ---- CMD0: GO_IDLE_STATE ---- */
        str     wzr, [x19, #SDARG_OFF]
        ldr     w1, =(CMD_NEW | CMD_NORESP | 0)
        str     w1, [x19, #SDCMD_OFF]

        ldr     w22, =100000
.cmd0_poll:
        ldr     w0, [x19, #SDCMD_OFF]
        tbz     w0, #15, .cmd0_ok       /* NEW_FLAG cleared → done */
        subs    w22, w22, #1
        b.ne    .cmd0_poll
        adr     x0, str_err_cmd0
        b       sd_dump_err

.cmd0_ok:
        adr     x0, str_cmd0_ok
        bl      print_str

        /* ---- CMD8: SEND_IF_COND (VHS=3.3V, check=0xAA) ---- */
        ldr     w1, =0x000001AA
        str     w1, [x19, #SDARG_OFF]
        ldr     w1, =(CMD_NEW | 8)
        str     w1, [x19, #SDCMD_OFF]

        ldr     w22, =100000
.cmd8_poll:
        ldr     w0, [x19, #SDCMD_OFF]
        tbz     w0, #15, .cmd8_chk
        subs    w22, w22, #1
        b.ne    .cmd8_poll
        adr     x0, str_err_cmd8
        b       sd_dump_err

.cmd8_chk:
        ldr     w0, [x19, #SDCMD_OFF]
        tbnz    w0, #14, .cmd8_fail      /* FAIL_FLAG: timeout or CRC error */
        ldr     w0, [x19, #SDRSP0_OFF]  /* should echo 0x000001AA */

        /* Print response value before checking. */
        stp     x30, x0, [sp, #-16]!
        adr     x0, str_cmd8_rsp
        bl      print_str
        ldp     x30, x0, [sp], #16
        stp     x30, xzr, [sp, #-16]!
        bl      print_hex32
        ldp     x30, xzr, [sp], #16

        ldr     w0, [x19, #SDRSP0_OFF]
        ldr     w1, =0x000001AA
        cmp     w0, w1
        b.ne    .cmd8_volt_err
        adr     x0, str_cmd8_ok
        bl      print_str
        b       .acmd41_loop_start

.cmd8_fail:
        adr     x0, str_err_cmd8
        b       sd_dump_err

.cmd8_volt_err:
        adr     x0, str_err_cmd8_volt
        b       sd_dump_err

        /* ---- ACMD41 loop: CMD55 + ACMD41, up to 1000 retries ---- */
        /*
         * ACMD41 response is R3 (OCR register). R3 has no CRC7 — the SDHOST
         * will set SDHSTS.CRC7_ERROR (bit5) and possibly SDCMD.FAIL_FLAG.
         * We clear SDHSTS after ACMD41 and do NOT check FAIL_FLAG for it.
         * We only check SDRSP0.bit31 (0=busy, 1=ready) and SDHSTS.CMD_TIMEOUT.
         */
.acmd41_loop_start:
        mov     w23, #1000              /* retry counter */

.acmd41_retry:
        /* CMD55 APP_CMD (prefix; RCA=0 during init). */
        str     wzr, [x19, #SDARG_OFF]
        ldr     w1, =(CMD_NEW | 55)
        str     w1, [x19, #SDCMD_OFF]

        ldr     w22, =100000
.cmd55_poll:
        ldr     w0, [x19, #SDCMD_OFF]
        tbz     w0, #15, .cmd55_chk
        subs    w22, w22, #1
        b.ne    .cmd55_poll
        adr     x0, str_err_cmd55
        b       sd_dump_err

.cmd55_chk:
        ldr     w0, [x19, #SDCMD_OFF]
        tbnz    w0, #14, .cmd55_fail

        /* Clear SDHSTS before ACMD41. */
        ldr     w0, [x19, #SDHSTS_OFF]
        str     w0, [x19, #SDHSTS_OFF]

        /* ACMD41: SDARG=0x40FF8000 (HCS=1, no S18R, full voltage window). */
        ldr     w1, =0x40FF8000
        str     w1, [x19, #SDARG_OFF]
        ldr     w1, =(CMD_NEW | 41)
        str     w1, [x19, #SDCMD_OFF]

        ldr     w22, =100000
.acmd41_poll:
        ldr     w0, [x19, #SDCMD_OFF]
        tbz     w0, #15, .acmd41_chk
        subs    w22, w22, #1
        b.ne    .acmd41_poll
        /* Controller timed out — likely QEMU or stuck hardware. */
        b       .acmd41_timeout

.acmd41_chk:
        /* Clear SDHSTS — CRC7_ERROR is normal for R3, don't fault on it. */
        ldr     w0, [x19, #SDHSTS_OFF]
        /* Check CMD_TIMEOUT (bit6) only — that's a real error. */
        tbnz    w0, #6, .acmd41_card_err
        str     w0, [x19, #SDHSTS_OFF]  /* write-1-to-clear */

        /* Read OCR. bit31=0 → card still initialising, retry. */
        ldr     w0, [x19, #SDRSP0_OFF]
        tbz     w0, #31, .acmd41_not_ready

        /* bit31=1 → card ready. Capture CCS (bit30). */
        mov     w21, wzr
        tbnz    w0, #30, .acmd41_sdhc
        b       .acmd41_done

.acmd41_sdhc:
        mov     w21, #1                 /* SDHC/SDXC: sector-addressed */
        b       .acmd41_done

.acmd41_not_ready:
        /* Card still powering up. ~1ms delay, then retry. */
        ldr     w22, =200000
.acmd41_delay:
        subs    w22, w22, #1
        b.ne    .acmd41_delay
        subs    w23, w23, #1
        b.ne    .acmd41_retry
        /* Retry counter exhausted. */

.acmd41_timeout:
        adr     x0, str_err_acmd41_timeout
        bl      print_str
        b       sd_halt

.acmd41_card_err:
        adr     x0, str_err_acmd41
        b       sd_dump_err

.cmd55_fail:
        adr     x0, str_err_cmd55
        b       sd_dump_err

.acmd41_done:
        adr     x0, str_acmd41_rdy
        bl      print_str

        /* Print CCS. */
        adr     x0, str_ccs
        bl      print_str
        mov     x0, x21
        stp     x30, xzr, [sp, #-16]!
        bl      print_hex32
        ldp     x30, xzr, [sp], #16

        /* ---- CMD2: ALL_SEND_CID (moves card to identification state) ---- */
        str     wzr, [x19, #SDARG_OFF]
        ldr     w1, =(CMD_NEW | CMD_LONG | 2)
        str     w1, [x19, #SDCMD_OFF]

        ldr     w22, =100000
.cmd2_poll:
        ldr     w0, [x19, #SDCMD_OFF]
        tbz     w0, #15, .cmd2_chk
        subs    w22, w22, #1
        b.ne    .cmd2_poll
        adr     x0, str_err_cmd2
        b       sd_dump_err

.cmd2_chk:
        ldr     w0, [x19, #SDCMD_OFF]
        tbnz    w0, #14, .cmd2_fail
        adr     x0, str_cmd2_ok
        bl      print_str
        b       .cmd3_start

.cmd2_fail:
        adr     x0, str_err_cmd2
        b       sd_dump_err

        /* ---- CMD3: SEND_RELATIVE_ADDR (card moves to standby, gives us RCA) ---- */
.cmd3_start:
        str     wzr, [x19, #SDARG_OFF]
        ldr     w1, =(CMD_NEW | 3)
        str     w1, [x19, #SDCMD_OFF]

        ldr     w22, =100000
.cmd3_poll:
        ldr     w0, [x19, #SDCMD_OFF]
        tbz     w0, #15, .cmd3_chk
        subs    w22, w22, #1
        b.ne    .cmd3_poll
        adr     x0, str_err_cmd3
        b       sd_dump_err

.cmd3_chk:
        ldr     w0, [x19, #SDCMD_OFF]
        tbnz    w0, #14, .cmd3_fail
        ldr     w0, [x19, #SDRSP0_OFF]
        lsr     w20, w0, #16            /* RCA = SDRSP0[31:16] */

        adr     x0, str_rca
        bl      print_str
        mov     x0, x20
        stp     x30, xzr, [sp, #-16]!
        bl      print_hex32
        ldp     x30, xzr, [sp], #16
        b       .cmd7_start

.cmd3_fail:
        adr     x0, str_err_cmd3
        b       sd_dump_err

        /* ---- CMD7: SELECT_CARD (standby → transfer state, R1b) ---- */
.cmd7_start:
        lsl     w1, w20, #16            /* SDARG = RCA << 16 */
        str     w1, [x19, #SDARG_OFF]
        ldr     w1, =(CMD_NEW | CMD_BUSY | 7)
        str     w1, [x19, #SDCMD_OFF]

        /* Wait for command phase (response received). */
        ldr     w22, =500000
.cmd7_poll:
        ldr     w0, [x19, #SDCMD_OFF]
        tbz     w0, #15, .cmd7_resp
        subs    w22, w22, #1
        b.ne    .cmd7_poll
        adr     x0, str_err_cmd7
        b       sd_dump_err

.cmd7_resp:
        ldr     w0, [x19, #SDCMD_OFF]
        tbnz    w0, #14, .cmd7_fail

        /*
         * CMD7 is R1b: after the response, the card asserts DAT0 busy while it
         * transitions to transfer state. SDHOST sets SDHSTS.BUSY_IRPT (bit10)
         * when DAT0 deasserts. Poll for it with a generous timeout.
         */
        ldr     w22, =0x00800000        /* ~2s at uncached loop speed */
.cmd7_busy_poll:
        ldr     w0, [x19, #SDHSTS_OFF]
        tbnz    w0, #10, .cmd7_ok       /* BUSY_IRPT set → card in transfer state */
        subs    w22, w22, #1
        b.ne    .cmd7_busy_poll
        adr     x0, str_err_cmd7_busy
        b       sd_dump_err

.cmd7_ok:
        /* Clear SDHSTS (including BUSY_IRPT). */
        ldr     w0, [x19, #SDHSTS_OFF]
        str     w0, [x19, #SDHSTS_OFF]
        adr     x0, str_cmd7_ok
        bl      print_str
        b       .clk_hi

.cmd7_fail:
        adr     x0, str_err_cmd7
        b       sd_dump_err

        /* ---- Switch to high-speed clock ---- */
        /* CDIV=8 → 250MHz/(8+2) = 25 MHz. */
.clk_hi:
        mov     w1, #8
        str     w1, [x19, #SDCDIV_OFF]
        ldr     w22, =200000
.delay_clk_hi:
        subs    w22, w22, #1
        b.ne    .delay_clk_hi
        adr     x0, str_clk_hi
        bl      print_str

        adr     x0, str_sd_init_ok
        bl      print_str

        /* ============================================================
         * Phase 3: CMD17 READ_SINGLE_BLOCK — sector 0.
         * ============================================================ */

        /* Set up transfer parameters BEFORE writing SDCMD. */
        str     wzr, [x19, #SDARG_OFF]  /* sector address = 0 */
        mov     w1, #512
        str     w1, [x19, #SDHBCT_OFF]  /* 512 bytes per block */
        str     wzr, [x19, #SDHBLC_OFF] /* single block */
        ldr     w1, =0x00F00000
        str     w1, [x19, #SDTOUT_OFF]  /* data timeout (per Linux driver) */
        ldr     w1, =(CMD_NEW | CMD_READ | 17)
        str     w1, [x19, #SDCMD_OFF]

        /* Wait for CMD17 command phase. */
        ldr     w22, =500000
.cmd17_poll:
        ldr     w0, [x19, #SDCMD_OFF]
        tbz     w0, #15, .cmd17_chk
        subs    w22, w22, #1
        b.ne    .cmd17_poll
        adr     x0, str_err_cmd17
        b       sd_dump_err

.cmd17_chk:
        ldr     w0, [x19, #SDCMD_OFF]
        tbnz    w0, #14, .cmd17_fail

        /* Drain 512 bytes (128 × 32-bit words) from FIFO into sector0_buf. */
        ldr     x24, =sector0_buf
        mov     w22, #128

.fifo_loop:
        /* Poll DATA_FLAG (bit0), abort on timeout or error. */
        ldr     w4, =0x00300000         /* per-word timeout (~several ms) */
.fifo_poll:
        ldr     w0, [x19, #SDHSTS_OFF]
        /* Abort on REW_TIME_OUT (bit7), CRC16 (bit4), FIFO_ERROR (bit3). */
        ldr     w5, =(HST_RWTOUT | HST_CRC16 | HST_FIFO)
        tst     w0, w5
        b.ne    .fifo_err
        tbnz    w0, #0, .fifo_read      /* DATA_FLAG set → word ready */
        subs    w4, w4, #1
        b.ne    .fifo_poll
        adr     x0, str_err_fifo_timeout
        b       sd_dump_err

.fifo_read:
        ldr     w0, [x19, #SDDATA_OFF]
        str     w0, [x24], #4
        subs    w22, w22, #1
        b.ne    .fifo_loop

        /* All 512 bytes read. Clear SDHSTS. */
        ldr     w0, [x19, #SDHSTS_OFF]
        str     w0, [x19, #SDHSTS_OFF]

        adr     x0, str_cmd17_ok
        bl      print_str

        /* Print bytes 510–511 (MBR signature). */
        adr     x0, str_mbr
        bl      print_str

        ldr     x24, =sector0_buf
        ldrb    w0, [x24, #510]
        bl      print_byte_hex

        /* space */
        ldr     x0, =0x3F201000         /* PL011 DR */
        mov     w1, #' '
.sp_wait:
        ldr     x2, =0x3F201018         /* FR */
        ldr     w2, [x2]
        tbnz    w2, #5, .sp_wait
        str     w1, [x0]

        ldrb    w0, [x24, #511]
        bl      print_byte_hex

        /* \r\n */
        ldr     x0, =0x3F201000
        mov     w1, #'\r'
.mbr_cr:
        ldr     x2, =0x3F201018
        ldr     w2, [x2]
        tbnz    w2, #5, .mbr_cr
        str     w1, [x0]
        mov     w1, #'\n'
.mbr_lf:
        ldr     x2, =0x3F201018
        ldr     w2, [x2]
        tbnz    w2, #5, .mbr_lf
        str     w1, [x0]

        adr     x0, str_sd_pass
        bl      print_str

        /* SD_PASS: enter FAT32 phase. */
        b       fat32_start

.cmd17_fail:
        adr     x0, str_err_cmd17
        b       sd_dump_err

.fifo_err:
        adr     x0, str_err_fifo
        b       sd_dump_err

/* ============================================================
 * gpio_error / panic_stub.
 * ============================================================ */
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

/* ============================================================
 * sd_read_single: issue CMD17 to read one 512-byte sector.
 *
 * Input:  w0 = LBA,  x1 = destination buffer (512 bytes)
 * Output: buffer filled.
 * Preserves: x19 (SDHOST base), x20 (RCA), x21 (CCS), x30.
 * Clobbers: x0-x7, w4 (counter).
 * On error: tail-calls sd_dump_err (non-return).
 * ============================================================ */
sd_read_single:
        stp     x30, xzr, [sp, #-16]!
        mov     x2, x1                  /* save buf ptr in x2 */

        /* CCS=1 (SDHC/SDXC): SDARG = LBA directly.
         * CCS=0 (SDSC):        SDARG = LBA * 512 (byte address). */
        tbz     x21, #0, .srs_sdsc
        str     w0, [x19, #SDARG_OFF]
        b       .srs_setup
.srs_sdsc:
        lsl     x0, x0, #9
        str     w0, [x19, #SDARG_OFF]
.srs_setup:
        mov     w1, #512
        str     w1, [x19, #SDHBCT_OFF]
        str     wzr, [x19, #SDHBLC_OFF]
        ldr     w1, =0x00F00000
        str     w1, [x19, #SDTOUT_OFF]
        ldr     w1, =(CMD_NEW | CMD_READ | 17)
        str     w1, [x19, #SDCMD_OFF]

        /* Wait for CMD17 command phase (bit15 clears when done). */
        ldr     w4, =500000
.srs_cmd_poll:
        ldr     w5, [x19, #SDCMD_OFF]
        tbz     w5, #15, .srs_cmd_done
        subs    w4, w4, #1
        b.ne    .srs_cmd_poll
        adr     x0, str_err_cmd17
        b       sd_dump_err
.srs_cmd_done:
        ldr     w5, [x19, #SDCMD_OFF]
        tbnz    w5, #14, .srs_fail      /* CMD_FAIL bit14 set → error */

        /* Drain 128 × 32-bit words (512 bytes) from FIFO. */
        mov     x3, x2                  /* x3 = current drain ptr */
        mov     w4, #128
.srs_fifo:
        ldr     w5, =0x00300000         /* per-word poll timeout */
.srs_fw_poll:
        ldr     w6, [x19, #SDHSTS_OFF]
        ldr     w7, =(HST_RWTOUT | HST_CRC16 | HST_FIFO)
        tst     w6, w7
        b.ne    .srs_fifo_err
        tbnz    w6, #0, .srs_fw_read    /* DATA_FLAG bit0 = word ready */
        subs    w5, w5, #1
        b.ne    .srs_fw_poll
        adr     x0, str_err_fifo_timeout
        b       sd_dump_err
.srs_fw_read:
        ldr     w6, [x19, #SDDATA_OFF]
        str     w6, [x3], #4
        subs    w4, w4, #1
        b.ne    .srs_fifo
        /* Clear SDHSTS. */
        ldr     w6, [x19, #SDHSTS_OFF]
        str     w6, [x19, #SDHSTS_OFF]
        ldp     x30, xzr, [sp], #16
        ret
.srs_fail:
        adr     x0, str_err_cmd17
        b       sd_dump_err
.srs_fifo_err:
        adr     x0, str_err_fifo
        b       sd_dump_err

/* ============================================================
 * fat32_start: parse FAT32, walk root directory, find .GGU file,
 * read first sector, verify GGUF magic.
 *
 * Called after SD_PASS.
 * Register state on entry:
 *   x19 = SDHOST base   x20 = RCA   x21 = CCS flag
 *   sector0_buf has MBR (sector 0) already loaded.
 *
 * Register usage inside fat32_start:
 *   w22 = part1_lba → then repurposed as dir-entry counter
 *   w23 = root_dir_lba
 *   x24 = current dir-entry pointer
 *   w25 = first_cluster (of found file)
 *   w26 = sectors_per_cluster
 *   w27 = data_start_lba
 * ============================================================ */
fat32_start:
        adr     x0, str_fat32
        bl      print_str

        /* ── MBR: parse partition 1 start LBA (bytes 454–457, LE) ── */
        /* offset 454 = 0x1C6 is not 4-byte aligned; use add+ldr. */
        ldr     x0, =sector0_buf
        add     x0, x0, #454
        ldr     w22, [x0]               /* w22 = part1_lba (unaligned OK: SCTLR.A=0) */
        adr     x0, str_part1
        bl      print_str
        mov     w0, w22
        bl      print_hex32             /* prints "XXXXXXXX\r\n" */

        /* ── Read BPB (partition 1, sector 0 relative) ── */
        mov     w0, w22
        ldr     x1, =fat32_buf
        bl      sd_read_single
        adr     x0, str_bpb_ok
        bl      print_str

        /* ── Parse BPB fields (all from fat32_buf) ── */
        ldr     x0, =fat32_buf

        /* SectorsPerCluster @ BPB+13 (uint8) */
        ldrb    w26, [x0, #13]          /* w26 = secs_per_clust */

        /* ReservedSectors @ BPB+14 (uint16 LE) */
        ldrh    w1, [x0, #14]           /* w1 = reserved_secs */

        /* NumFATs @ BPB+16 (uint8) */
        ldrb    w2, [x0, #16]           /* w2 = num_fats */

        /* FATSz32 @ BPB+36 (uint32 LE) */
        ldr     w3, [x0, #36]           /* w3 = fat_sz_secs */

        /* RootCluster @ BPB+44 (uint32 LE) */
        ldr     w4, [x0, #44]           /* w4 = root_cluster */

        /* fat_start = part1_lba + reserved_secs */
        add     w1, w22, w1             /* w1 = fat_start */

        /* data_start = fat_start + num_fats * fat_sz */
        mul     w2, w2, w3
        add     w27, w1, w2             /* w27 = data_start_lba */

        /* root_dir_lba = data_start + (root_cluster - 2) * secs_per_clust */
        sub     w4, w4, #2
        mul     w4, w4, w26
        add     w23, w27, w4            /* w23 = root_dir_lba */

        adr     x0, str_rdir
        bl      print_str
        mov     w0, w23
        bl      print_hex32

        /* ── Scan root directory: up to 16 sectors × 16 entries each ── */
        mov     w28, #0                 /* w28 = directory sector offset */

.dir_sector:
        add     w0, w23, w28            /* LBA = root_dir_lba + sector_offset */
        ldr     x1, =fat32_buf
        bl      sd_read_single
        adr     x0, str_rdir_ok
        bl      print_str

        ldr     x24, =fat32_buf
        mov     w22, #16

.dir_walk:
        ldrb    w0, [x24]               /* entry[0] = status byte */
        cbz     w0, .dir_not_found      /* 0x00 = true end of directory */
        cmp     w0, #0xE5
        b.eq    .dir_next               /* deleted entry */

        ldrb    w0, [x24, #11]          /* attributes byte */
        cmp     w0, #0x0F
        b.eq    .dir_next               /* LFN entry */
        tst     w0, #0x18               /* bit4=dir, bit3=volume */
        b.ne    .dir_next               /* skip dirs and volume labels */

        /* Regular file: check extension bytes [8..10] for "GGU" */
        ldrb    w0, [x24, #8]
        cmp     w0, #'G'
        b.ne    .dir_next
        ldrb    w0, [x24, #9]
        cmp     w0, #'G'
        b.ne    .dir_next
        ldrb    w0, [x24, #10]
        cmp     w0, #'U'
        b.ne    .dir_next

        /* ── Found .GGU file: print 8-char SFN name ── */
        adr     x0, str_ggu_found
        bl      print_str

        /* print 8 filename chars (bytes 0-7 of entry) */
        mov     x0, x24
        mov     w1, #8
.fname_byte:
        ldrb    w2, [x0], #1
.fname_txff:
        ldr     x3, =0x3F201018
        ldr     w3, [x3]
        tbnz    w3, #5, .fname_txff
        ldr     x3, =0x3F201000
        str     w2, [x3]
        subs    w1, w1, #1
        b.ne    .fname_byte

        /* \r\n after filename */
        mov     w2, #'\r'
.fname_cr:
        ldr     x3, =0x3F201018
        ldr     w3, [x3]
        tbnz    w3, #5, .fname_cr
        ldr     x3, =0x3F201000
        str     w2, [x3]
        mov     w2, #'\n'
.fname_lf:
        ldr     x3, =0x3F201018
        ldr     w3, [x3]
        tbnz    w3, #5, .fname_lf
        ldr     x3, =0x3F201000
        str     w2, [x3]

        /* ── Get first cluster number ── */
        /* high 16 bits @ entry+20, low 16 bits @ entry+26 */
        ldrh    w0, [x24, #20]
        ldrh    w1, [x24, #26]
        orr     w25, w1, w0, lsl #16    /* w25 = first_cluster */

        adr     x0, str_clust
        bl      print_str
        mov     w0, w25
        bl      print_hex32

        /* ── Compute cluster LBA and read first sector ── */
        /* cluster_lba = data_start + (cluster - 2) * secs_per_clust */
        sub     w0, w25, #2
        mul     w0, w0, w26
        add     w0, w27, w0             /* w0 = cluster_lba */
        ldr     x1, =fat32_buf
        bl      sd_read_single

        /* ── Check GGUF magic: bytes 0-3 = 'G','G','U','F' ── */
        ldr     x0, =fat32_buf
        ldrb    w1, [x0]
        cmp     w1, #0x47               /* 'G' */
        b.ne    .magic_fail
        ldrb    w1, [x0, #1]
        cmp     w1, #0x47               /* 'G' */
        b.ne    .magic_fail
        ldrb    w1, [x0, #2]
        cmp     w1, #0x55               /* 'U' */
        b.ne    .magic_fail
        ldrb    w1, [x0, #3]
        cmp     w1, #0x46               /* 'F' */
        b.ne    .magic_fail

        adr     x0, str_gguf_ok
        bl      print_str
        b       blink_loop

.magic_fail:
        /* Print first 4 bytes as hex to diagnose */
        ldr     x4, =fat32_buf
        ldrb    w0, [x4]
        bl      print_byte_hex
        ldrb    w0, [x4, #1]
        bl      print_byte_hex
        ldrb    w0, [x4, #2]
        bl      print_byte_hex
        ldrb    w0, [x4, #3]
        bl      print_byte_hex
        adr     x0, str_magic_fail
        bl      print_str
        b       blink_loop

.dir_next:
        add     x24, x24, #32           /* advance to next entry */
        subs    w22, w22, #1
        b.ne    .dir_walk
        /* sector exhausted without finding file — try next sector */
        add     w28, w28, #1
        cmp     w28, #16                /* scan at most 16 sectors (256 entries) */
        b.lo    .dir_sector

.dir_not_found:
        adr     x0, str_no_ggu
        bl      print_str
        b       blink_loop

/* ============================================================
 * blink_loop: ACT LED (GPIO 29) ~1 Hz.
 * ============================================================ */
blink_loop:
        ldr     x0, =0x3F200008         /* GPFSEL2 */
        ldr     w1, [x0]
        ldr     w2, =0x38000000
        bic     w1, w1, w2
        ldr     w2, =0x08000000
        orr     w1, w1, w2
        str     w1, [x0]
.bl_on:
        ldr     x0, =0x3F20001C         /* GPSET0 */
        ldr     w1, =0x20000000
        str     w1, [x0]
        ldr     w2, =0x04000000
.bl_on_dly:
        subs    w2, w2, #1
        b.ne    .bl_on_dly
        ldr     x0, =0x3F200028         /* GPCLR0 */
        ldr     w1, =0x20000000
        str     w1, [x0]
        ldr     w2, =0x04000000
.bl_off_dly:
        subs    w2, w2, #1
        b.ne    .bl_off_dly
        b       .bl_on

/* ============================================================
 * sd_halt: fast LED blink (panic / SD error).
 * ============================================================ */
sd_halt:
        ldr     x0, =0x3F200008
        ldr     w1, [x0]
        ldr     w2, =0x38000000
        bic     w1, w1, w2
        ldr     w2, =0x08000000
        orr     w1, w1, w2
        str     w1, [x0]
.sh_on:
        ldr     x0, =0x3F20001C
        ldr     w1, =0x20000000
        str     w1, [x0]
        ldr     w2, =0x00300000
.sh_on_dly:
        subs    w2, w2, #1
        b.ne    .sh_on_dly
        ldr     x0, =0x3F200028
        ldr     w1, =0x20000000
        str     w1, [x0]
        ldr     w2, =0x00300000
.sh_off_dly:
        subs    w2, w2, #1
        b.ne    .sh_off_dly
        b       .sh_on

/* ============================================================
 * sd_dump_err: print error label + SDCMD + SDHSTS, then sd_halt.
 * x0 = pointer to error string.
 * Saves x30 and x19 (SDHOST base) around nested bl calls.
 * ============================================================ */
sd_dump_err:
        stp     x30, x19, [sp, #-16]!
        bl      print_str

        adr     x0, str_sdcmd_label
        bl      print_str
        ldr     x9, [sp, #8]            /* restore x19 = SDHOST base */
        ldr     w0, [x9, #SDCMD_OFF]
        bl      print_hex32

        adr     x0, str_sdhsts_label
        bl      print_str
        ldr     x9, [sp, #8]
        ldr     w0, [x9, #SDHSTS_OFF]
        bl      print_hex32

        /*
         * SDEDM bits[3:0] = internal state machine state:
         *   0=idle, 1=wait_crc, 2=wait_resp, 3=data_rx, 4=data_tx, ...
         * Printing this pins exactly where the controller froze.
         */
        adr     x0, str_sdedm_label
        bl      print_str
        ldr     x9, [sp, #8]
        ldr     w0, [x9, #SDEDM_OFF]
        bl      print_hex32

        ldp     x30, x19, [sp], #16
        b       sd_halt

/* ============================================================
 * print_str: print null-terminated string at x0 to PL011.
 * Polls FR.TXFF (bit5) before each byte.
 * Clobbers x0, x1, x2, w3.
 * ============================================================ */
print_str:
        mov     x1, x0
        ldr     x2, =0x3F201000         /* PL011 DR */
.ps_loop:
        ldrb    w3, [x1], #1
        cbz     w3, .ps_done
.ps_txff:
        ldr     x0, =0x3F201018
        ldr     w0, [x0]
        tbnz    w0, #5, .ps_txff
        str     w3, [x2]
        b       .ps_loop
.ps_done:
        ret

/* ============================================================
 * print_hex32: print w0 as 8 uppercase hex digits + \r\n.
 * Saves x30 and x19 (to preserve caller's SDHOST base).
 * ============================================================ */
print_hex32:
        stp     x30, x19, [sp, #-16]!
        mov     w19, w0                 /* value to print */
        mov     w3, #28                 /* MSB nibble shift */
.ph32_nibble:
        lsr     w4, w19, w3            /* shift nibble to bits [3:0] */
        and     w4, w4, #0xF
        add     w4, w4, #'0'
        cmp     w4, #58                 /* 58 = ':' = '9'+1 */
        b.lt    .ph32_ch
        add     w4, w4, #39            /* 39 = 'a'-'0'-10; maps 10→'a' etc. */
.ph32_ch:
        ldr     x5, =0x3F201000
.ph32_txff:
        ldr     x0, =0x3F201018
        ldr     w0, [x0]
        tbnz    w0, #5, .ph32_txff
        str     w4, [x5]
        subs    w3, w3, #4
        b.pl    .ph32_nibble

        /* \r\n */
        ldr     x5, =0x3F201000
        mov     w4, #'\r'
.ph32_cr:
        ldr     x0, =0x3F201018
        ldr     w0, [x0]
        tbnz    w0, #5, .ph32_cr
        str     w4, [x5]
        mov     w4, #'\n'
.ph32_lf:
        ldr     x0, =0x3F201018
        ldr     w0, [x0]
        tbnz    w0, #5, .ph32_lf
        str     w4, [x5]
        ldp     x30, x19, [sp], #16
        ret

/* ============================================================
 * print_byte_hex: print w0[7:0] as 2 hex digits (no newline).
 * Clobbers w0-w5.
 * ============================================================ */
print_byte_hex:
        and     w1, w0, #0xFF
        /* High nibble */
        lsr     w2, w1, #4
        add     w2, w2, #'0'
        cmp     w2, #58
        b.lt    .pbh_hi
        add     w2, w2, #39
.pbh_hi:
        ldr     x3, =0x3F201000
.pbh_hi_ff:
        ldr     x4, =0x3F201018
        ldr     w4, [x4]
        tbnz    w4, #5, .pbh_hi_ff
        str     w2, [x3]
        /* Low nibble */
        and     w2, w1, #0xF
        add     w2, w2, #'0'
        cmp     w2, #58
        b.lt    .pbh_lo
        add     w2, w2, #39
.pbh_lo:
        ldr     x3, =0x3F201000
.pbh_lo_ff:
        ldr     x4, =0x3F201018
        ldr     w4, [x4]
        tbnz    w4, #5, .pbh_lo_ff
        str     w2, [x3]
        ret

/* ============================================================
 * Vector table: 2 KiB aligned, 128-byte entries.
 * All entries jump to panic_stub.
 * ============================================================ */
.balign 2048
_vectors:
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
str_sd_start:
        .ascii  "SD_START\r\n\0"
str_sd_p0:
        .ascii  "SD_P0\r\n\0"
str_cmd0_ok:
        .ascii  "CMD0_OK\r\n\0"
str_cmd8_rsp:
        .ascii  "CMD8_RSP=\0"
str_cmd8_ok:
        .ascii  "CMD8_OK\r\n\0"
str_acmd41_rdy:
        .ascii  "ACMD41_RDY\r\n\0"
str_ccs:
        .ascii  "CCS=\0"
str_cmd2_ok:
        .ascii  "CMD2_OK\r\n\0"
str_rca:
        .ascii  "RCA=\0"
str_cmd7_ok:
        .ascii  "CMD7_OK\r\n\0"
str_clk_hi:
        .ascii  "CLK_HI\r\n\0"
str_sd_init_ok:
        .ascii  "SD_INIT_OK\r\n\0"
str_cmd17_ok:
        .ascii  "CMD17_OK\r\n\0"
str_mbr:
        .ascii  "MBR: \0"
str_sd_pass:
        .ascii  "SD_PASS\r\n\0"
str_sdhsts_pre:
        .ascii  "SDHSTS_PRE=\0"
str_sdcmd_label:
        .ascii  "SDCMD=\0"
str_sdhsts_label:
        .ascii  "SDHSTS=\0"
str_sdedm_label:
        .ascii  "SDEDM=\0"
str_err_cmd0:
        .ascii  "ERR_CMD0_TIMEOUT\r\n\0"
str_err_cmd8:
        .ascii  "ERR_CMD8_TIMEOUT\r\n\0"
str_err_cmd8_volt:
        .ascii  "ERR_CMD8_VOLT\r\n\0"
str_err_cmd55:
        .ascii  "ERR_CMD55\r\n\0"
str_err_acmd41:
        .ascii  "ERR_ACMD41\r\n\0"
str_err_acmd41_timeout:
        .ascii  "ERR_ACMD41_TIMEOUT\r\n\0"
str_err_cmd2:
        .ascii  "ERR_CMD2\r\n\0"
str_err_cmd3:
        .ascii  "ERR_CMD3\r\n\0"
str_err_cmd7:
        .ascii  "ERR_CMD7\r\n\0"
str_err_cmd7_busy:
        .ascii  "ERR_CMD7_BUSY\r\n\0"
str_err_cmd17:
        .ascii  "ERR_CMD17\r\n\0"
str_err_fifo:
        .ascii  "ERR_FIFO\r\n\0"
str_err_fifo_timeout:
        .ascii  "ERR_FIFO_TIMEOUT\r\n\0"

/* FAT32 phase strings */
str_fat32:
        .ascii  "FAT32\r\n\0"
str_part1:
        .ascii  "PART1=\0"
str_bpb_ok:
        .ascii  "BPB_OK\r\n\0"
str_rdir:
        .ascii  "RDIR=\0"
str_rdir_ok:
        .ascii  "RDIR_OK\r\n\0"
str_ggu_found:
        .ascii  "GGU:\0"
str_clust:
        .ascii  "CLUST=\0"
str_gguf_ok:
        .ascii  "GGUF_OK\r\n\0"
str_magic_fail:
        .ascii  "\r\nMAGIC_FAIL\r\n\0"
str_no_ggu:
        .ascii  "NO_GGU\r\n\0"

/* 512-byte buffer for sector 0 (MBR). Lives in .text (loaded by firmware). */
.balign 4
sector0_buf:
        .space  512

/* 512-byte buffer for FAT32 BPB, directory sectors, cluster data. */
.balign 4
fat32_buf:
        .space  512

.end
