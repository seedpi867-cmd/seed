/*
 * Linker script for 99-recovery test kernels.
 *
 * Minimal: load at 0x80000 (firmware default for kernel8.img with arm_64bit=1),
 * one .text section, _image_size symbol for the ARM64 image header.
 * No vector table, no BSS — these kernels are not supposed to do anything
 * except exist (or loop in WFI).
 */

ENTRY(_start)

SECTIONS
{
        . = 0x80000;
        _image_start = .;

        .text : { *(.text.boot) *(.text*) }

        . = ALIGN(8);
        _image_end  = .;
        _image_size = _image_end - _image_start;
}
