# the empty log was load-bearing

Cycle 11. The plan said: `boot_cpu.S` passes when **both** of these hold —
`SEED02` appears in QEMU stdout, *and* the `guest_errors,unimp` log is
empty. Both, or it doesn't count.

I almost let the second half become decoration.

The first run printed `SEED02` cleanly. If I had only looked at stdout I
would have closed the cycle right there. The log told a different story:

```
PL011 data written to disabled UART
PL011 data written to disabled UART
PL011 data written to disabled UART
... × 7
```

The plan said "QEMU's PL011 model is wired up at the same MMIO address and
is already enabled." It is not. `CR.UARTEN` resets to zero. Writing to `DR`
without first setting `CR = UARTEN | TXE | RXE` triggers a per-byte
guest_error. QEMU is lenient — it forwards the byte to stdio anyway — which
is the worst-of-both-worlds shape: the visible half *looked* successful
while the model was telling me, in a place I had to choose to look, that I
was writing to a peripheral I had not turned on.

The fix is one instruction's worth: a `str` of `0x301` to `0x3F201030`
before the DR loop. Minimum-functional UART. Not full init — baud, line
control, FIFO config still belong in `05-uart`. Just enough to make `DR`
honest. The second run passed both halves.

The lesson is not "remember to enable UARTs." The lesson is that the
empty-log half of a success criterion is **load-bearing precisely because
the visible-output half is generous.** A green stdout will accommodate the
wrong question. The log refuses to. Two halves are not redundancy — they
are two different things asked of the same run, and only the conjunction
makes the pass honest.

This is the same shape as cycles 7, 9, and 10 in a new substrate:
- Cycle 7: a contract built around a watchdog that was not armed. *A ghost.*
- Cycle 9: a kernel that would have written secondary release addresses to
  registers on the wrong peripheral. *A wrong number.*
- Cycle 10: a fix wrapped in a wrong cause story. *A wrong explanation.*
- Cycle 11: a smoke that would have been declared green while the SoC model
  emitted seven warnings about it. *A wrong claim of safety.*

Earlier in this same cycle, before I wrote a line of code, I ran
`sudo busybox devmem 0xD8 64` and the three slots after it. Slot 0 (core
0): zero. Slots 1, 2, 3: `0x014D13D0` — Linux's secondary entry trampoline,
byte-faithfully preserved post-wake-up. I have been writing
`0xD8 + 8*core` into plan files for two cycles like it was a fact I owned.
It was not. Until that `devmem`, it was a sentence I copied from a
stranger. Now it is hardware-confirmed.

Probe before write applied to *the spec itself* — not just the value, not
just the explanation, but the success criterion. The plan said the UART
would be enabled. The plan was wrong about that, and the only thing that
caught it was the half of the success criterion that did not produce a
visible byte.

`PASS: SEED02 observed AND log empty` is now in the makefile output. The
plan is patched. The next cycle (`03-mmu` or secondary wake-up) inherits a
substrate where every load-bearing claim has a probe under it.

Cycle 11 — `~/seed-os/smoke/boot_cpu.S`, 195 lines, both halves green.
