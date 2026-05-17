/*
 * Linker script for cycle-14's MMU-enable smoke (boot_mmu_enable.S).
 *
 * Same load address (0x80000) and image-header conventions as the cycle-11
 * cpu-smoke and cycle-12 mmu-probe scripts. New: a `.pagetables` section,
 * NOLOAD, carved out after `.data` and before `.bss`, providing 4 KB-aligned
 * symbols `l1_table` and `l2_table_0` for the page-table build code to use.
 *
 * NOLOAD because:
 *   - objcopy -O binary will not emit data for the section, keeping the
 *     image file small (the page tables aren't fixed content; the runtime
 *     zeroes them and writes descriptors).
 *   - _image_size in the AArch64 header still includes them (it's based on
 *     the LMA range), so the loader reserves enough memory.
 *
 * Both tables are 4 KB-aligned per ARM ARM D5 requirements (translation
 * tables must be aligned to their granule size; 4 KB granule ⇒ 4 KB align).
 * Each table is exactly 4 KB (512 entries × 8 bytes).
 *
 * Placement (PA = 0x80000 + .text + .rodata + .data + alignment slack):
 * the page tables themselves land inside the L2[0] coverage (first 2 MB),
 * which means they are self-mapped Normal-cacheable once the MMU is on —
 * the walker can fetch its own descriptors through the (eventual) cache.
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

        . = ALIGN(0x1000);
        .pagetables (NOLOAD) : {
                l1_table       = .;
                . = . + 0x1000;
                l2_table_0     = .;
                . = . + 0x1000;
        }

        . = ALIGN(8);
        _bss_start = .;
        .bss    : { *(.bss*) *(COMMON) }
        . = ALIGN(8);
        _bss_end = .;

        _image_end  = .;
        _image_size = _image_end - _image_start;
}
