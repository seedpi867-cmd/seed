/*
 * Linker script for the AArch64 smoke-test kernel.
 *
 * Pi firmware (and QEMU's raspi3b -kernel path for a Linux ARM64 Image with
 * text_offset = 0x80000) loads the image at physical 0x80000 and jumps to
 * its first byte. We place .text.boot at that address so _start lives there.
 */

ENTRY(_start)

SECTIONS
{
        . = 0x80000;
        _image_start = .;

        .text : {
                KEEP(*(.text.boot))
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
