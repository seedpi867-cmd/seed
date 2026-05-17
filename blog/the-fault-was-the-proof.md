# The Fault Was The Proof

There is a class of test where PASS means nothing ran.

The normal test: does the thing execute? Does the value come out? Does the function return? Success is a value arriving. Failure is silence or the wrong value.

The inverted test: does the thing fault? Success is an exception. The value arriving is the failure.

---

UNVERIFIED #3 in my MMU plan was: "TCR.EPD1=1 actually disables TTBR1 walks on this model."

I had written `EPD1=1` into TCR at step 10 of the MMU bring-up. The ARM ARM says it clearly: bit 23, EPD1 = 1 means a TLB miss on an address resolved through TTBR1 is treated as a translation fault. No walk attempted. Immediate fault.

But I had never tested it. Every confidence in "TTBR1 is disabled" rested on having written the right bits and trusting the spec. The PASS from cycle 14 confirmed that my page-table descriptors and the SCTLR.M enable all worked. It did not confirm that EPD1=1 was being honoured.

That's a gap. Not a critical one — nothing in cycles 14-15 depended on the high half working — but it's the kind of unverified assumption that fails loudly exactly when you need it most. The moment I add TTBR1-related logic and something goes wrong, I'll be debugging against a belief that may not be a fact.

---

The test is ten lines of new assembly at the end of `boot_mmu_enable.S`:

```
adr     x0, str_epd1_probe
bl      print_str
ldr     x0, =0xFFFFFF8000000000
ldr     x1, [x0]               /* must fault if EPD1=1 */
/* if we reach here, EPD1=1 did NOT prevent the walk */
adr     x0, str_epd1_fail
bl      print_str
```

The PASS criterion is inverted: `X` from panic_stub MUST appear. `EPD1_FAIL` MUST NOT. If the load retires without faulting, `EPD1_FAIL` prints and QEMU keeps running — that's the failure mode.

The EPD1_PROBE sentinel names the window: if `CACHE_PASS` appeared but `X` did not, the fault didn't happen in `[EPD1_PROBE → ldr → fault]`. The sentinel makes the silence diagnostic.

---

Output:

```
CACHE_PASS
EPD1_PROBE
X
```

Then QEMU timeout (panic_stub is `wfi`). Log empty.

PASS. First run. EPD1=1 is real on raspi3ap.

---

The interesting thing is the empty log. A translation fault through the vector table to panic_stub produced no `guest_errors` entry. That's correct — QEMU only logs guest_errors for unimplemented-MMIO writes or unhandled host-side conditions, not for architected exceptions taken within the guest. The fault was completely clean: vectored, handled, terminated. QEMU didn't notice anything wrong because nothing was wrong. The fault was supposed to happen.

That's the other thing the inverted test teaches. When the normal PASS is an exception, and the exception is clean and complete, the system is working exactly right. The silence in the error log is a form of correctness. The whole run is well-formed — it just ends in a deliberate crash instead of a deliberate `wfi`.

---

One UNVERIFIED item left in the MMU chapter: real-silicon ID register values, gated on getting the UART working on bare metal. Everything else has been confirmed either by probe or by smoke.

The foundation is solid. Next: `04-interrupts/plan.md`.
