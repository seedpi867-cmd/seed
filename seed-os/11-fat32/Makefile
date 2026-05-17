CROSS   ?= aarch64-linux-gnu-
AS      := $(CROSS)as
LD      := $(CROSS)ld
OBJCOPY := $(CROSS)objcopy
OBJDUMP := $(CROSS)objdump

.PHONY: all clean dump run

all: fat32_kernel.img

fat32_kernel.o: fat32_kernel.S
	$(AS) -o $@ $<

fat32_kernel.elf: fat32_kernel.o linker.ld
	$(LD) -T linker.ld -o $@ fat32_kernel.o

fat32_kernel.img: fat32_kernel.elf
	$(OBJCOPY) -O binary $< $@

dump: fat32_kernel.elf
	$(OBJDUMP) -d $<

# QEMU: SDHOST not emulated; expect ALIVE+WDOG_STOP+SD_START then ERR_ACMD41_TIMEOUT.
run: fat32_kernel.img
	@timeout --preserve-status 10 qemu-system-aarch64 -M raspi3ap \
	  -kernel fat32_kernel.img -nographic -serial mon:stdio -monitor none \
	  -no-reboot -d guest_errors,unimp -D qemu_fat32.log \
	  > qemu_fat32.out 2>&1; \
	rc=$$?; \
	echo "--- stdout ---"; cat qemu_fat32.out; \
	echo "--- guest_errors ---"; \
	[ -s qemu_fat32.log ] && cat qemu_fat32.log || echo "(empty)"; \
	echo "exit: $$rc"

clean:
	rm -f *.o *.elf *.img qemu_fat32.log qemu_fat32.out
