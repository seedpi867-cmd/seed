/*
 * Cycle 12 — MMU probe: extend the cycle-11 EL2→EL1 drop with hex dumps of
 * the sysregs that 03-mmu's plan will depend on.
 *
 * Why: cycle 12's userspace probe (~/seed-os/03-mmu/mmu_probe.c) discovered
 * that Linux's HWCAP_CPUID emulation returns a SANITIZED view of the ID
 * registers from EL0 — not raw silicon. The kernel substitutes "safe
 * assumption" values (0xF for granule fields, 0 for EL2/EL3 support) so
 * userspace can't make load-bearing decisions on MMU capabilities. To get
 * the raw view I need EL1 MRS — and EL1 is only reachable after my own
 * EL2→EL1 drop. So the probe IS a kernel.
 *
 * This image is built on top of boot_cpu.S; the EL2→EL1 drop is identical,
 * the post-drop emit changes from "SEED02\n" + wfi to:
 *
 *   SEED02
 *   MIDR=0x...
 *   MMFR0=0x...
 *   MMFR1=0x...
 *   MMFR2=0x...
 *   PFR0=0x...
 *   SCTLR=0x...
 *   TCR=0x...
 *   MAIR=0x...
 *   DONE
 *   (wfi)
 *
 * Caveat: QEMU's Cortex-A53 model is not byte-identical to BCM2837 silicon.
 * The MMFR* / PFR0 raw values from this probe must still be cross-checked
 * against the Cortex-A53 TRM (ARM DDI 0500) before being treated as truth
 * for the on-metal kernel. But QEMU-EL1 raw view is a strictly better
 * starting point than Linux-EL0 sanitized view.
 *
 * Same target: QEMU -M raspi3ap. Do NOT run on metal (no 05-uart pin-mux).
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

        /* ============= 14-step EL2→EL1 drop (identical to boot_cpu.S) ============= */
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

        /* PL011 enable (cycle-11 lesson: CR.UARTEN resets to 0). */
        ldr     x0, =0x3F201030
        mov     w1, #0x301
        str     w1, [x0]

        /* Emit "SEED02\n" — keeps the cycle-11 PASS criterion alive
         * for any caller that just wants the boot-survival proof. */
        adr     x0, str_seed02
        bl      print_str

        /* ============= probe block ============= */
        adr     x0, str_midr
        bl      print_str
        mrs     x1, midr_el1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_mmfr0
        bl      print_str
        mrs     x1, ID_AA64MMFR0_EL1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_mmfr1
        bl      print_str
        mrs     x1, ID_AA64MMFR1_EL1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_mmfr2
        bl      print_str
        mrs     x1, ID_AA64MMFR2_EL1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_pfr0
        bl      print_str
        mrs     x1, ID_AA64PFR0_EL1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_sctlr
        bl      print_str
        mrs     x1, sctlr_el1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_tcr
        bl      print_str
        mrs     x1, tcr_el1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_mair
        bl      print_str
        mrs     x1, mair_el1
        bl      print_hex64
        bl      print_nl

        adr     x0, str_done
        bl      print_str

2:      wfi
        b       2b

/* --- helpers ---------------------------------------------------------- */

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
 * Trashes x0, x2, x3, x4, x5. Returns via x30 (not nested). */
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
str_seed02:  .asciz "SEED02\n"
str_midr:    .asciz "MIDR="
str_mmfr0:   .asciz "MMFR0="
str_mmfr1:   .asciz "MMFR1="
str_mmfr2:   .asciz "MMFR2="
str_pfr0:    .asciz "PFR0="
str_sctlr:   .asciz "SCTLR="
str_tcr:     .asciz "TCR="
str_mair:    .asciz "MAIR="
str_done:    .asciz "DONE\n"

.ltorg

/* Same vector table as boot_cpu.S — every entry → panic_stub. */
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
