CROSS   ?= aarch64-linux-gnu-
AS      := $(CROSS)as
LD      := $(CROSS)ld
OBJCOPY := $(CROSS)objcopy

.PHONY: all clean run-bad-header inspect-bad-header run-test3 run-sd-poll

all: bad_header.img boot_test3.img boot_test3_24m.img sd_poll.img

# ----- Test 0b: malformed-header preflight kernel -----
# See plan.md § Test 0b for the on-metal test protocol.

bad_header.o: bad_header.S
	$(AS) -o $@ $<

bad_header.elf: bad_header.o linker_recovery.ld
	$(LD) -T linker_recovery.ld -o $@ bad_header.o

bad_header.img: bad_header.elf
	$(OBJCOPY) -O binary $< $@

inspect-bad-header: bad_header.img
	@echo "--- size ---"; wc -c bad_header.img
	@echo "--- first 64 bytes (header) ---"; hexdump -C bad_header.img | head -8
	@echo "--- magic at 0x38 (should be 00 00 00 00) ---"; \
	  dd if=bad_header.img bs=1 skip=56 count=4 status=none | od -An -tx1 | tr -s ' '

# QEMU: confirms image builds and loops in WFI (SIGTERM expected, empty log).
# This does NOT verify firmware header-validation — that is on-metal only.
#
# On-metal protocol (from plan.md § Test 0b):
#   sudo mkdir -p /boot/firmware/seed
#   sudo cp bad_header.img /boot/firmware/seed/kernel8.img
#   sync
#   sudo reboot "0 tryboot"
#   PASS: Pi returns to Linux within (kernel_watchdog_timeout + 5) seconds.
#   FAIL: Pi does not return → tryboot+watchdog mechanism broken; STOP.
run-bad-header: bad_header.img
	@timeout --preserve-status 6 qemu-system-aarch64 -M raspi3ap \
	  -kernel bad_header.img -nographic -serial null -monitor none \
	  -no-reboot -d guest_errors,unimp -D qemu_bad_header.log; \
	rc=$$?; \
	echo "exit: $$rc (143 = SIGTERM after wfi, expected)"; \
	echo "--- guest_errors,unimp ---"; \
	[ -s qemu_bad_header.log ] && cat qemu_bad_header.log || echo "(empty)"; \
	if { [ $$rc -eq 0 ] || [ $$rc -eq 143 ]; } && [ ! -s qemu_bad_header.log ]; then \
	  echo "QEMU PASS: image loops in WFI, no guest errors (build confirmed)"; \
	  echo "NOTE: firmware header-validation test is on-metal only."; \
	else \
	  echo "QEMU FAIL: rc=$$rc (expected 0 or 143), or log non-empty"; \
	fi

# ----- Test 3: happy-path kernel (UART alive + watchdog stop) -----
# See plan.md § Test 3 for the on-metal test protocol.

boot_test3.o: boot_test3.S
	$(AS) -o $@ $<

boot_test3.elf: boot_test3.o linker_recovery.ld
	$(LD) -T linker_recovery.ld -o $@ boot_test3.o

boot_test3.img: boot_test3.elf
	$(OBJCOPY) -O binary $< $@

# QEMU: confirms UART init works and both strings appear.
# PM_RSTC (0x3F10001C) is not emulated — one guest_errors entry expected.
# Kernel loops forever in blink_loop; timeout kills it (exit 143).
#
# On-metal protocol (from plan.md § Test 3, after Test 0b passes):
#   sudo cp boot_test3.img /boot/firmware/seed/kernel8.img
#   sync
#   sudo reboot "0 tryboot"
#   PASS: UART shows ALIVE\r\n then WDOG_STOP\r\n; ACT LED blinks; Pi stays up.
#         Next manual reset → Pi boots Linux (tryboot one-shot confirmed).
run-test3: boot_test3.img
	@tmpout=$$(mktemp); \
	timeout --preserve-status 8 qemu-system-aarch64 -M raspi3ap \
	  -kernel boot_test3.img -nographic -serial stdio -monitor none \
	  -no-reboot -d guest_errors,unimp -D qemu_test3.log 2>/dev/null \
	  > $$tmpout; rc=$$?; \
	echo "exit: $$rc"; \
	echo "--- stdout ---"; cat $$tmpout; \
	echo "--- guest_errors (PM_RSTC write expected here) ---"; \
	[ -s qemu_test3.log ] && cat qemu_test3.log || echo "(empty)"; \
	alive=$$(grep -c 'ALIVE' $$tmpout || true); \
	wdog=$$(grep -c 'WDOG_STOP' $$tmpout || true); \
	rm -f $$tmpout; \
	if { [ $$rc -eq 0 ] || [ $$rc -eq 143 ]; } && \
	   [ "$$alive" -ge 1 ] && [ "$$wdog" -ge 1 ]; then \
	  echo "QEMU PASS: ALIVE + WDOG_STOP present, exit $$rc"; \
	else \
	  echo "QEMU FAIL: rc=$$rc, alive=$$alive, wdog=$$wdog"; \
	  exit 1; \
	fi

# ----- Test 3 alt: 24 MHz UART clock variant -----
# Use if boot_test3 produces garbage on UART (LED still blinks = kernel is alive).
# See plan.md § baud-paranoia.

boot_test3_24m.o: boot_test3_24m.S
	$(AS) -o $@ $<

boot_test3_24m.elf: boot_test3_24m.o linker_recovery.ld
	$(LD) -T linker_recovery.ld -o $@ boot_test3_24m.o

boot_test3_24m.img: boot_test3_24m.elf
	$(OBJCOPY) -O binary $< $@

run-test3-24m: boot_test3_24m.img
	@tmpout=$$(mktemp); \
	timeout --preserve-status 8 qemu-system-aarch64 -M raspi3ap \
	  -kernel boot_test3_24m.img -nographic -serial stdio -monitor none \
	  -no-reboot -d guest_errors,unimp -D qemu_test3_24m.log 2>/dev/null \
	  > $$tmpout; rc=$$?; \
	echo "exit: $$rc"; \
	echo "--- stdout ---"; cat $$tmpout; \
	echo "--- guest_errors ---"; \
	[ -s qemu_test3_24m.log ] && cat qemu_test3_24m.log || echo "(empty)"; \
	alive=$$(grep -c 'ALIVE_24M' $$tmpout || true); \
	wdog=$$(grep -c 'WDOG_STOP_24M' $$tmpout || true); \
	rm -f $$tmpout; \
	if { [ $$rc -eq 0 ] || [ $$rc -eq 143 ]; } && \
	   [ "$$alive" -ge 1 ] && [ "$$wdog" -ge 1 ]; then \
	  echo "QEMU PASS: ALIVE_24M + WDOG_STOP_24M present"; \
	  echo "NOTE: QEMU uses 48 MHz clock — 24 MHz divisors produce ~230400 baud in QEMU."; \
	  echo "      Strings appear because QEMU PL011 model ignores divisors."; \
	else \
	  echo "QEMU FAIL: rc=$$rc, alive=$$alive, wdog=$$wdog"; \
	  exit 1; \
	fi

# ----- sd_poll: SDHOST sector-0 read smoke test -----
# QEMU PASS: "ALIVE" + "SD_START" + "SD_P0" + "ERR_ACMD41_TIMEOUT"
#   (QEMU has no SDHOST emulation; SDRSP0 always reads 0 → OCR.bit31=0 → timeout)
#   SD guest_errors in log are expected and not a failure.
#
# Metal PASS (after Test 3 tryboot passes):
#   sudo cp sd_poll.img /boot/firmware/seed/kernel8.img
#   sync
#   sudo reboot "0 tryboot"
#   UART must show: ALIVE → SD_INIT_OK → CMD17_OK → "MBR: 55 AA"
#   If "MBR: 55 AA" appears: SD read from bare metal is working.
#   If stuck at "ACMD41...": adjust ACMD41 delay and retry count.

sd_poll.o: sd_poll.S
	$(AS) -o $@ $<

sd_poll.elf: sd_poll.o linker_recovery.ld
	$(LD) -T linker_recovery.ld -o $@ sd_poll.o

sd_poll.img: sd_poll.elf
	$(OBJCOPY) -O binary $< $@

run-sd-poll: sd_poll.img
	@tmpout=$$(mktemp); \
	timeout --preserve-status 15 qemu-system-aarch64 -M raspi3ap \
	  -kernel sd_poll.img -nographic -serial stdio -monitor none \
	  -no-reboot -d guest_errors,unimp -D qemu_sd_poll.log 2>/dev/null \
	  > $$tmpout; rc=$$?; \
	echo "exit: $$rc"; \
	echo "--- stdout ---"; cat $$tmpout; \
	echo "--- guest_errors (SD accesses to 0x3F202000 expected) ---"; \
	[ -s qemu_sd_poll.log ] && head -20 qemu_sd_poll.log || echo "(empty)"; \
	alive=$$(grep -c 'ALIVE' $$tmpout || true); \
	sdstart=$$(grep -c 'SD_START' $$tmpout || true); \
	terminal=$$(grep -cE 'ERR_|SD_PASS' $$tmpout || true); \
	rm -f $$tmpout; \
	if { [ $$rc -eq 0 ] || [ $$rc -eq 143 ]; } && \
	   [ "$$alive" -ge 1 ] && [ "$$sdstart" -ge 1 ] && [ "$$terminal" -ge 1 ]; then \
	  echo "QEMU PASS: ALIVE + SD_START + terminal condition (ERR_ or SD_PASS) present"; \
	  echo "NOTE: SD_PASS only appears on real hardware with a functioning SD card."; \
	else \
	  echo "QEMU FAIL: rc=$$rc, alive=$$alive, sdstart=$$sdstart, terminal=$$terminal"; \
	  exit 1; \
	fi

clean:
	rm -f bad_header.o bad_header.elf bad_header.img qemu_bad_header.log \
	      boot_test3.o boot_test3.elf boot_test3.img qemu_test3.log \
	      boot_test3_24m.o boot_test3_24m.elf boot_test3_24m.img qemu_test3_24m.log \
	      sd_poll.o sd_poll.elf sd_poll.img qemu_sd_poll.log
