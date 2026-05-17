/*
 * Minimal AArch64 bare-metal smoke test.
 *
 * Goal: prove the toolchain (aarch64-linux-gnu-as / -ld / -objcopy) produces
 * a kernel8.img that qemu-system-aarch64 -M raspi3b will accept, parse as a
 * Linux ARM64 Image, and execute the first instruction.
 *
 * Does NOT prove peripheral layout, mailbox addresses, or anything about the
 * real BCM2837. QEMU's raspi3b model is an approximation — a green boot here
 * means "the bytes are well-formed and the CPU started," nothing more.
 *
 * Image header layout: Documentation/arm64/booting.rst (Linux kernel tree).
 */

.section ".text.boot", "ax"
.globl _start

_start:
        /* 0x00: code0 — branch to real entry */
        b       code_entry
        /* 0x04: code1 — reserved (executable, but we just zero it) */
        .long   0
        /* 0x08: text_offset — load offset from start of memory, LE */
        .quad   0x80000
        /* 0x10: image_size — effective image size, LE (filled by linker) */
        .quad   _image_size
        /* 0x18: flags
         *   bit 0   = endian (0 = LE)
         *   bit 1-2 = page size (01 = 4KB)
         *   bit 3   = placement (1 = anywhere in usable memory)
         */
        .quad   0x0A
        /* 0x20, 0x28, 0x30: reserved */
        .quad   0
        .quad   0
        .quad   0
        /* 0x38: magic — "ARM\x64", reads as 0x644D5241 LE */
        .ascii  "ARM\x64"
        /* 0x3C: reserved */
        .long   0

code_entry:
        /* Park the CPU. wfi halts until interrupt; we never enable any, so
         * this is effectively forever. QEMU's CPU goes idle, host stays sane.
         */
1:      wfi
        b       1b
