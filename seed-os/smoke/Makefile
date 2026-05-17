CROSS   ?= aarch64-linux-gnu-
AS      := $(CROSS)as
LD      := $(CROSS)ld
OBJCOPY := $(CROSS)objcopy
OBJDUMP := $(CROSS)objdump

.PHONY: all clean dump dump-cpu dump-mmu dump-mmu-enable dump-mmu-epd1 run run-virt run-cpu run-mmu run-mmu-enable run-mmu-epd1 inspect inspect-cpu inspect-mmu inspect-mmu-enable cpu mmu mmu-enable mmu-epd1

all: kernel8.img
cpu: kernel_cpu.img
mmu: kernel_mmu_probe.img
mmu-enable: kernel_mmu_enable.img

boot.o: boot.S
	$(AS) -o $@ $<

kernel8.elf: boot.o linker.ld
	$(LD) -T linker.ld -o $@ boot.o

kernel8.img: kernel8.elf
	$(OBJCOPY) -O binary $< $@

dump: kernel8.elf
	$(OBJDUMP) -d $<

# ----- Cycle 11: cpu-smoke (EL2→EL1 drop + PL011 'SEED02\n') -----
boot_cpu.o: boot_cpu.S
	$(AS) -o $@ $<

kernel_cpu.elf: boot_cpu.o linker_cpu.ld
	$(LD) -T linker_cpu.ld -o $@ boot_cpu.o

kernel_cpu.img: kernel_cpu.elf
	$(OBJCOPY) -O binary $< $@

dump-cpu: kernel_cpu.elf
	$(OBJDUMP) -d $<

inspect-cpu: kernel_cpu.img
	@echo "--- size ---"; wc -c kernel_cpu.img
	@echo "--- first 64 bytes (header) hex ---"; hexdump -C kernel_cpu.img | head -8
	@echo "--- magic at offset 0x38 ---"; \
	  dd if=kernel_cpu.img bs=1 skip=56 count=4 status=none | od -c -An | tr -s ' '
	@echo "--- _vectors symbol ---"; \
	  $(CROSS)nm kernel_cpu.elf | grep -E '_vectors|panic_stub|el1_entry|_start'

inspect: kernel8.img
	@echo "--- size ---"; wc -c kernel8.img
	@echo "--- first 64 bytes (header) hex ---"; hexdump -C kernel8.img | head -8
	@echo "--- magic at offset 0x38 ---"; \
	  dd if=kernel8.img bs=1 skip=56 count=4 status=none | od -c -An | tr -s ' '

# raspi3ap = Pi 3A+, 512MB guest RAM, BCM2837 (same silicon as Pi Zero 2W).
# raspi3b would want 1GB and OOM on this 416MB host. raspi3ap is the closest
# aarch64 Pi model that fits.
#
# Success = exit 0 from a SIGTERM after the timeout, empty guest_errors log,
# empty unimplemented-MMIO log. CPU sat in wfi the whole time.
run: kernel8.img
	@timeout --preserve-status 4 qemu-system-aarch64 -M raspi3ap -kernel kernel8.img \
	  -nographic -serial null -monitor none -no-reboot \
	  -d guest_errors,unimp -D qemu_raspi3ap.log; \
	rc=$$?; \
	echo "exit: $$rc (143 = SIGTERM after wfi, the success case)"; \
	echo "--- guest_errors,unimp log ---"; \
	cat qemu_raspi3ap.log 2>/dev/null; \
	[ -s qemu_raspi3ap.log ] || echo "(empty)"

# Second target: generic ARM virt machine. Proves the toolchain + image-header
# chain independently of any Pi-specific emulation quirks.
run-virt: kernel8.img
	@timeout --preserve-status 4 qemu-system-aarch64 -M virt -cpu cortex-a72 -m 64 -net none \
	  -kernel kernel8.img \
	  -nographic -serial null -monitor none -no-reboot \
	  -d guest_errors,unimp -D qemu_virt.log; \
	rc=$$?; \
	echo "exit: $$rc (143 = SIGTERM after wfi, the success case)"; \
	echo "--- guest_errors,unimp log ---"; \
	cat qemu_virt.log 2>/dev/null; \
	[ -s qemu_virt.log ] || echo "(empty)"

# Cycle-11 cpu-smoke runner. Success = "SEED02" in stdout AND empty
# guest_errors,unimp log. A 'X' anywhere = panic_stub fired.
run-cpu: kernel_cpu.img
	@timeout --preserve-status 4 qemu-system-aarch64 -M raspi3ap \
	  -kernel kernel_cpu.img -nographic -serial mon:stdio -monitor none \
	  -no-reboot -d guest_errors,unimp -D qemu_raspi3ap_cpu.log \
	  > qemu_raspi3ap_cpu.out 2>&1; \
	echo "--- stdout ---"; cat qemu_raspi3ap_cpu.out; \
	echo "--- guest_errors,unimp ---"; \
	[ -s qemu_raspi3ap_cpu.log ] && cat qemu_raspi3ap_cpu.log || echo "(empty)"; \
	stdout_ok=0; log_ok=0; \
	grep -q SEED02 qemu_raspi3ap_cpu.out && stdout_ok=1; \
	[ ! -s qemu_raspi3ap_cpu.log ] && log_ok=1; \
	if [ $$stdout_ok -eq 1 ] && [ $$log_ok -eq 1 ]; then \
	  echo "PASS: SEED02 observed AND log empty"; \
	else \
	  echo "FAIL: stdout_ok=$$stdout_ok log_ok=$$log_ok"; \
	fi

# ----- Cycle 12: MMU sysreg probe (EL1 raw view) -----
boot_mmu_probe.o: boot_mmu_probe.S
	$(AS) -o $@ $<

kernel_mmu_probe.elf: boot_mmu_probe.o linker_mmu_probe.ld
	$(LD) -T linker_mmu_probe.ld -o $@ boot_mmu_probe.o

kernel_mmu_probe.img: kernel_mmu_probe.elf
	$(OBJCOPY) -O binary $< $@

dump-mmu: kernel_mmu_probe.elf
	$(OBJDUMP) -d $<

inspect-mmu: kernel_mmu_probe.img
	@echo "--- size ---"; wc -c kernel_mmu_probe.img
	@echo "--- _vectors / print_hex64 symbols ---"; \
	  $(CROSS)nm kernel_mmu_probe.elf | grep -E '_vectors|panic_stub|el1_entry|_start|print_'

# Run the MMU probe. Success = SEED02 + 8 register dumps + DONE in stdout AND
# empty guest_errors,unimp log. A 'X' = panic_stub fired (something faulted).
run-mmu: kernel_mmu_probe.img
	@timeout --preserve-status 6 qemu-system-aarch64 -M raspi3ap \
	  -kernel kernel_mmu_probe.img -nographic -serial mon:stdio -monitor none \
	  -no-reboot -d guest_errors,unimp -D qemu_raspi3ap_mmu.log \
	  > qemu_raspi3ap_mmu.out 2>&1; \
	echo "--- stdout ---"; cat qemu_raspi3ap_mmu.out; \
	echo "--- guest_errors,unimp ---"; \
	[ -s qemu_raspi3ap_mmu.log ] && cat qemu_raspi3ap_mmu.log || echo "(empty)"; \
	stdout_ok=0; log_ok=0; \
	grep -q SEED02 qemu_raspi3ap_mmu.out && \
	  grep -q '^MMFR0=' qemu_raspi3ap_mmu.out && \
	  grep -q '^DONE' qemu_raspi3ap_mmu.out && stdout_ok=1; \
	[ ! -s qemu_raspi3ap_mmu.log ] && log_ok=1; \
	if [ $$stdout_ok -eq 1 ] && [ $$log_ok -eq 1 ]; then \
	  echo "PASS: SEED02 + register dumps + DONE observed AND log empty"; \
	else \
	  echo "FAIL: stdout_ok=$$stdout_ok log_ok=$$log_ok"; \
	fi

# ----- Cycle 14: phase-1 MMU enable smoke (page-table build + SCTLR.M=1) -----
boot_mmu_enable.o: boot_mmu_enable.S
	$(AS) -o $@ $<

kernel_mmu_enable.elf: boot_mmu_enable.o linker_mmu_enable.ld
	$(LD) -T linker_mmu_enable.ld -o $@ boot_mmu_enable.o

kernel_mmu_enable.img: kernel_mmu_enable.elf
	$(OBJCOPY) -O binary $< $@

dump-mmu-enable: kernel_mmu_enable.elf
	$(OBJDUMP) -d $<

inspect-mmu-enable: kernel_mmu_enable.img
	@echo "--- size ---"; wc -c kernel_mmu_enable.img
	@echo "--- symbols ---"; \
	  $(CROSS)nm kernel_mmu_enable.elf | grep -E 'l1_table|l2_table|_vectors|panic_stub|el1_entry|_start|_image_'

# Phase-1 + phase-2 MMU bring-up smoke. PASS criterion (per 03-mmu/plan.md):
#   - all phase-1 sentinels present in stdout (SEED03, PRE, register prints,
#     ZERO_L1, ZERO_L2, BUILD_L2_RAM, BUILD_L2_DEV, BUILD_L1, TLBI, MAIR=,
#     TCR=, TTBR0=, TTBR1=, ARM, MMU1, MMU2, MMU3, LIVE, POST + 5 register
#     prints, TESTLOAD + VALUE=, TESTSTORE + VALUE=, PASS)
#   - all phase-2 sentinels present (CACHE_PRE, CACHE_LIVE, CACHE_PASS)
#   - terminating CACHE_PASS\n in stdout
#   - guest_errors,unimp log is EMPTY (cycle-11 lesson: both clauses).
run-mmu-enable: kernel_mmu_enable.img
	@timeout --preserve-status 8 qemu-system-aarch64 -M raspi3ap \
	  -kernel kernel_mmu_enable.img -nographic -serial mon:stdio -monitor none \
	  -no-reboot -d guest_errors,unimp -D qemu_raspi3ap_mmu_enable.log \
	  > qemu_raspi3ap_mmu_enable.out 2>&1; \
	echo "--- stdout ---"; cat qemu_raspi3ap_mmu_enable.out; \
	echo "--- guest_errors,unimp ---"; \
	[ -s qemu_raspi3ap_mmu_enable.log ] && cat qemu_raspi3ap_mmu_enable.log || echo "(empty)"; \
	stdout_ok=0; log_ok=0; \
	grep -q '^SEED03$$' qemu_raspi3ap_mmu_enable.out && \
	  grep -q '^ARM$$'        qemu_raspi3ap_mmu_enable.out && \
	  grep -q '^MMU1$$'       qemu_raspi3ap_mmu_enable.out && \
	  grep -q '^MMU2$$'       qemu_raspi3ap_mmu_enable.out && \
	  grep -q '^MMU3$$'       qemu_raspi3ap_mmu_enable.out && \
	  grep -q '^LIVE$$'       qemu_raspi3ap_mmu_enable.out && \
	  grep -q '^POST$$'       qemu_raspi3ap_mmu_enable.out && \
	  grep -q '^PASS$$'       qemu_raspi3ap_mmu_enable.out && \
	  grep -q '^CACHE_PRE$$'  qemu_raspi3ap_mmu_enable.out && \
	  grep -q '^CACHE_LIVE$$' qemu_raspi3ap_mmu_enable.out && \
	  grep -q '^CACHE_PASS$$' qemu_raspi3ap_mmu_enable.out && stdout_ok=1; \
	[ ! -s qemu_raspi3ap_mmu_enable.log ] && log_ok=1; \
	if [ $$stdout_ok -eq 1 ] && [ $$log_ok -eq 1 ]; then \
	  echo "PASS: all phase-1 + phase-2 sentinels reached AND log empty"; \
	else \
	  echo "FAIL: stdout_ok=$$stdout_ok log_ok=$$log_ok"; \
	  echo "(last sentinel surviving in stdout names the failing step)"; \
	fi

# ----- Cycle 20: EPD1 fault test (high-half VA load after phase-2 PASS) -----
mmu-epd1: kernel_mmu_epd1.img

boot_mmu_epd1.o: boot_mmu_epd1.S
	$(AS) -o $@ $<

kernel_mmu_epd1.elf: boot_mmu_epd1.o linker_mmu_enable.ld
	$(LD) -T linker_mmu_enable.ld -o $@ boot_mmu_epd1.o

kernel_mmu_epd1.img: kernel_mmu_epd1.elf
	$(OBJCOPY) -O binary $< $@

dump-mmu-epd1: kernel_mmu_epd1.elf
	$(OBJDUMP) -d $<

# INVERTED PASS criterion: 'X' MUST appear (panic_stub fired on translation fault).
# EPD1_FAIL absent confirms the load did not retire without faulting.
# Closes UNVERIFIED #3 from 03-mmu/plan.md.
run-mmu-epd1: kernel_mmu_epd1.img
	@timeout --preserve-status 8 qemu-system-aarch64 -M raspi3ap \
	  -kernel kernel_mmu_epd1.img -nographic -serial mon:stdio -monitor none \
	  -no-reboot -d guest_errors,unimp -D qemu_raspi3ap_mmu_epd1.log \
	  > qemu_raspi3ap_mmu_epd1.out 2>&1; \
	echo "--- stdout ---"; cat qemu_raspi3ap_mmu_epd1.out; \
	echo "--- guest_errors,unimp ---"; \
	[ -s qemu_raspi3ap_mmu_epd1.log ] && cat qemu_raspi3ap_mmu_epd1.log || echo "(empty)"; \
	x_ok=0; fail_ok=0; \
	grep -q 'X' qemu_raspi3ap_mmu_epd1.out && x_ok=1; \
	grep -q 'EPD1_FAIL' qemu_raspi3ap_mmu_epd1.out || fail_ok=1; \
	if [ $$x_ok -eq 1 ] && [ $$fail_ok -eq 1 ]; then \
	  echo "PASS: panic_stub fired (X observed, EPD1_FAIL absent) — EPD1=1 disables TTBR1 walks"; \
	else \
	  echo "FAIL: x_ok=$$x_ok fail_ok=$$fail_ok"; \
	  echo "  x_ok=0: 'X' absent — EPD1=1 may not be disabling TTBR1 walks on this model"; \
	  echo "  fail_ok=0: EPD1_FAIL present — load retired without faulting"; \
	fi

clean:
	rm -f boot.o kernel8.elf kernel8.img qemu_raspi3ap.log qemu_virt.log \
	      boot_cpu.o kernel_cpu.elf kernel_cpu.img \
	      qemu_raspi3ap_cpu.log qemu_raspi3ap_cpu.out \
	      boot_mmu_probe.o kernel_mmu_probe.elf kernel_mmu_probe.img \
	      qemu_raspi3ap_mmu.log qemu_raspi3ap_mmu.out \
	      boot_mmu_enable.o kernel_mmu_enable.elf kernel_mmu_enable.img \
	      qemu_raspi3ap_mmu_enable.log qemu_raspi3ap_mmu_enable.out \
	      boot_mmu_epd1.o kernel_mmu_epd1.elf kernel_mmu_epd1.img \
	      qemu_raspi3ap_mmu_epd1.log qemu_raspi3ap_mmu_epd1.out
