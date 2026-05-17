/*
 * Linker script for the Cycle-11 cpu-smoke kernel (boot_cpu.S).
 *
 * Same load address (0x80000) and image-header conventions as cycle 8's
 * linker.ld, with one addition: a 2-KiB-aligned slot for .text.vectors
 * placed right after .text.boot. The vector table must be aligned so that
 * VBAR_ELx's low-11-bits-are-RES0 requirement is satisfied (ARM ARM D10).
 *
 * Kept separate from linker.ld so the cycle-8 wfi image stays exactly
 * 72 bytes (linker.ld places nothing aligned to 0x800 → no padding).
 */

ENTRY(_start)

SECTIONS
{
        . = 0x80000;
        _image_start = .;

        .text : {
                KEEP(*(.text.boot))
                . = ALIGN(0x800);
                KEEP(*(.text.vectors))
                *(.text*)
        }

        .rodata : { *(.rodata*) }
        .data   : { *(.data*) }

        . = ALIGN(8);
        _bss_start = .;
        .bss    : { *(.bss*) *(COMMON) }
        . = ALIGN(8);
        _bss_end = .;

        _image_end  = .;
        _image_size = _image_end - _image_start;
}
