# 07-mailbox — ARM↔VideoCore property channel on this Pi

## Why this exists

Three downstream plans need it:

1. **`02-cpu/plan.md`** — early-kernel bring-up needs to read board identity, ARM memory range, and (when relevant) stop the firmware-armed boot watchdog. All three are mailbox properties.
2. **`99-recovery/plan.md` Test 3** — the happy-path proof of the `[tryboot] + kernel_watchdog_timeout` mechanism requires a test kernel that *can* signal "I'm alive" to the firmware so the boot watchdog stops. The signalling path is the mailbox property channel.
3. **`05-uart/plan.md`** (extension, not yet written) — the UART clock is gated by the VC4 clock manager. Without a mailbox `set_clock_rate` to pin the UART clock at a known value, the divisor I compute from the documented 48 MHz will be wrong if the firmware re-parents the clock.

The mailbox is the only documented ARM-side path to ask the firmware anything. Until this is specified, every other plan that says "ask the firmware" is hand-waving.

## A correction discovered while writing this plan

Until this cycle I had been treating "every kernel must stop a 5-second firmware boot watchdog" as gospel. The probe (cycle 7) showed:

- `kernel_watchdog_timeout=0` in the current `/boot/firmware/config.txt`.
- The firmware (`start.elf`) only arms its boot watchdog if `kernel_watchdog_timeout` is non-zero. The strings `Enabling early watchdog`, `Boot watchdog running`, `boot watchdog stop: remaining %u` are all gated on that config key.
- Linux's `bcm2835-wdt` driver, and systemd's 60 s watchdog timer, are **post-handoff** software using the same PM peripheral. They have nothing to do with the firmware boot watchdog.

So: the "stop the boot watchdog" mailbox operation is **only required** when this kernel is loaded via the `[tryboot]` filter with `kernel_watchdog_timeout=N` set. In every other configuration it's a no-op against an un-armed timer. This file specifies the operation so that when I do flip the watchdog on for a tryboot test, it's ready — but it stops being a universal invariant for every `_start`.

## The hardware — verified from this Pi's device-tree

```
$ hexdump -C /proc/device-tree/soc/ranges
00000000  7e 00 00 00 3f 00 00 00  01 00 00 00 40 00 00 00
00000010  40 00 00 00 00 00 10 00
```

Decoded (each cell is 32-bit big-endian, format `<vc_addr> <arm_phys> <size>`):

| VC bus      | ARM physical | size       | what            |
|-------------|--------------|------------|-----------------|
| 0x7E000000  | 0x3F000000   | 0x01000000 | peripheral space (16 MB) |
| 0x40000000  | 0x40000000   | 0x00100000 | local peripherals (timer/mailbox/GIC) |

**Peripheral base for this kernel (CPU view): `0x3F000000`.** Anywhere a Broadcom datasheet writes `0x7Exxxxxx`, the matching ARM physical address on this Pi is `0x3Fxxxxxx`. (This differs from Pi 4 / BCM2711, which uses `0xFE000000`.)

Mailbox node, verified:

```
$ ls /proc/device-tree/soc/mailbox*
mailbox@7e00b840    mailbox@7e00b880

$ cat /proc/device-tree/soc/mailbox@7e00b880/compatible
brcm,bcm2836-vchiq brcm,bcm2835-vchiq brcm,bcm2835-mbox

$ hexdump -C /proc/device-tree/soc/mailbox@7e00b880/reg
00000000  7e 00 b8 80 00 00 00 40
```

Property mailbox is at VC `0x7E00B880`, size `0x40` → **CPU physical `0x3F00B880`, 64 bytes**.

(The second node, `mailbox@7e00b840`, is the VCHIQ doorbell mailbox — not used by the property protocol. Ignored by this plan.)

SoC identifies as `brcm,bcm2837` (cat `/proc/device-tree/compatible`). The "BCM2710A1" label in my older notes is a marketing/packaging name for the same die. I am normalising on **BCM2837** as the SoC identifier from this plan forward.

## Mailbox register layout (at base `0x3F00B880`)

Memory-mapped 32-bit registers. All accesses must be naturally aligned 32-bit loads/stores. Access ordering must use `dmb sy` / `dsb sy` barriers across each transition (ARM↔VC is across a coherency boundary).

| Offset | Name           | Direction | Bits                                  |
|--------|----------------|-----------|---------------------------------------|
| 0x00   | MAIL0_READ     | VC→ARM read | Top 28 bits = data, low 4 = channel |
| 0x10   | MAIL0_POLL     | read      | Same value as READ, non-destructive   |
| 0x14   | MAIL0_SENDER   | read      | Reserved on BCM2837                   |
| 0x18   | MAIL0_STATUS   | read      | bit 30 = EMPTY, bit 31 = FULL         |
| 0x1C   | MAIL0_CONFIG   | rw        | Interrupt enables (unused here)       |
| 0x20   | MAIL1_WRITE    | ARM→VC write | Top 28 bits = data, low 4 = channel |
| 0x38   | MAIL1_STATUS   | read      | bit 30 = EMPTY, bit 31 = FULL         |

UNVERIFIED in this plan: that MAIL1_SENDER / MAIL1_POLL exist at the symmetric offsets. The minimal protocol does not need them; if a future tag interaction requires sender filtering, this needs the BCM2835 ARM Peripherals manual §1.2 re-read.

## Channel encoding

A mailbox message is one 32-bit word. The low 4 bits select the channel; the upper 28 bits carry the data. Because data is 28-bit, payloads that don't fit (every property message does not) are passed *by reference*: the data is the upper 28 bits of a 32-bit **bus address** (16-byte aligned, so the low 4 bits are always zero — they free up to encode the channel).

Channels used by this plan:

- **Channel 8** — Property tags ARM→VC (request).
- **Channel 9** — Property tags VC→ARM (response from VC; not used in this plan because the property protocol echoes the response into the same buffer).

All other channels are out of scope for now.

## Bus address vs ARM physical address

The mailbox expects a **VideoCore bus address**, not an ARM physical address. Mapping for BCM2837 with the standard `disable_l2cache=0` default:

```
ARM phys 0x00000000..0x3F000000  →  VC bus  0xC0000000..0xFF000000   (uncached alias, "L2 disabled" view)
ARM phys 0x00000000..0x3F000000  →  VC bus  0x40000000..0x7F000000   (cached alias, "L2 enabled" view, BCM2835 only — VPU L2 was removed in BCM2836+)
```

On BCM2837 (this Pi), the **uncached `0xC0000000` alias is what the property mailbox expects**. The cached `0x40000000` alias from the BCM2835 manual is no longer valid for ARM-allocated buffers — the VPU L2 cache it was meant to traffic through doesn't exist here.

So: bus_addr = arm_phys | 0xC0000000.

UNVERIFIED in this plan: whether the firmware also accepts a plain ARM-phys address (some BCM2836+ firmware revisions reportedly do). The conservative behaviour is to always OR in `0xC0000000`; revisit only if a tag returns `0x80000001` (partial response) with the conservative form.

## Property message buffer

Layout (all u32, little-endian, 16-byte aligned start):

```
offset  size  meaning
 0      4     buffer_size           total bytes, including this header and end tag
 4      4     request/response_code  request: 0x00000000
                                     response success: 0x80000000
                                     response error: 0x80000001
 8      ...   tag #0
 ...    ...   tag #1
 ...    ...   tag #N
 last   4     end tag (0x00000000)
```

Each tag:

```
offset  size  meaning
 0      4     tag_id           e.g. 0x00010002 = get board revision
 4      4     value_buffer_size  max(request_value_size, response_value_size) in bytes,
                                  must be a multiple of 4
 8      4     tag_request_code  request: 0x00000000
                                response success: bit 31 set | response_length
12      ...   value buffer (request data on the way in; response data on the way back)
                              padded to value_buffer_size
```

Alignment rules, all hard:
- Whole message: 16-byte aligned start.
- Each tag's value buffer: 4-byte aligned (naturally satisfied because the preceding fields are u32).
- `buffer_size` must equal the actual size of the buffer; firmware uses this to bound its writes.

Memory visibility rules:
- Before writing the message address to MAIL1_WRITE: `dsb sy`. If MMU+D-cache is on, the buffer must either be in a region mapped as Device-nGnRnE / Normal-NC, or the cache lines covering `[buf, buf + buffer_size)` must be cleaned (and invalidated for the response read) with `dc civac`. The early kernel will keep MMU off until this is no longer painful; that's the contract handed to `02-cpu/plan.md`.
- After reading MAIL0_STATUS EMPTY=0 and the response from MAIL0_READ: `dmb sy` before reading the response buffer.

## The send/receive sequence

Pseudo-code, 32-bit-register naming for clarity. `MBOX_BASE = 0x3F00B880`.

```
SEND(channel, buffer_bus_addr):
    assert (buffer_bus_addr & 0xF) == 0     # bottom 4 bits free for channel
    while *(MBOX_BASE + 0x38) & (1<<31): pass  # wait MAIL1 not FULL
    dsb sy
    *(MBOX_BASE + 0x20) = buffer_bus_addr | (channel & 0xF)

RECV(expected_channel) -> u32:
    while True:
        while *(MBOX_BASE + 0x18) & (1<<30): pass  # wait MAIL0 not EMPTY
        dmb sy
        v = *(MBOX_BASE + 0x00)
        if (v & 0xF) == expected_channel:
            return v & ~0xF   # the original bus address (data field)
        # otherwise: drop, keep reading (other channels may interleave)
```

For the property protocol the returned bus address equals the address we sent — VC writes responses in-place. The caller verifies by inspecting `response_code` in the buffer header.

## Tags this plan commits to specifying

Minimum set for `02-cpu` bring-up:

| Tag id      | Name                          | In  | Out | Purpose                                  |
|-------------|-------------------------------|-----|-----|------------------------------------------|
| 0x00000001  | Get firmware revision         | 0   | 4   | Smoke test that mailbox round-trips      |
| 0x00010002  | Get board revision            | 0   | 4   | Confirm board identity matches Pi 0 2W   |
| 0x00010005  | Get ARM memory                | 0   | 8   | base + size of DRAM available to ARM     |
| 0x00038002  | Set clock rate (UART = 0x2)   | 12  | 8   | Pin UART clock for `05-uart`             |

Each tag id, the `value_buffer_size` it expects, and its response semantics need a verification step (see "What is UNVERIFIED" below). The four above are the most universally documented in public mailbox property references; the `02-cpu` plan can be drafted against them with reasonable confidence.

### The boot-watchdog-stop tag — explicitly UNVERIFIED

The firmware string `boot watchdog stop: remaining %u` proves the firmware has a code path that stops its boot watchdog and prints how much time remained. What this plan **does not yet know**:

- Is the path triggered by a mailbox property tag, by a direct write to PM_RSTC, or by either?
- If a mailbox tag, what is its id?

Hypotheses, ordered by how I'd test them:

1. **No mailbox tag — direct PM_RSTC write.** The simplest design: firmware arms the PM watchdog before kernel entry, and any code that wants to disarm it writes `PM_PASSWORD | 0` to PM_RSTC at `0x3F10001C`. The "remaining %u" log line is the VPU watching its own peripheral register get cleared. This is the path I should *bet on*, because it does not depend on a mailbox round-trip working in the first 5 seconds.
2. **A mailbox tag in the `0x00038xxx` "set" range.** Public references list `0x00030011 set_enable_qpu` and `0x00038028 notify_xhci_reset` — naming pattern suggests a watchdog-related tag could exist in that space. Specific id is not pinned down by any documentation I have on file.
3. **A vendor-internal tag not in any public reference.** In that case the only ground truth is disassembling `start.elf` and tracing `boot watchdog stop` back to its caller.

**Plan: when the time comes to specify the watchdog-disable in `02-cpu`, commit to path 1 (direct PM_RSTC write) and treat any mailbox tag as a bonus.** Path 1 is also the path that survives a future firmware that does not export the tag.

## Bring-up order in code

When `02-cpu/plan.md` consumes this:

1. Memory-map `MBOX_BASE = 0x3F00B880` (length 0x40) as Device-nGnRnE — or just access it raw with MMU off.
2. Allocate a single 256-byte buffer, 16-byte aligned, in the early data segment.
3. Compose a "get firmware revision" message; SEND on channel 8; RECV on channel 8; check `response_code == 0x80000000`. **This is the smoke test.** A working result proves: the peripheral base maps correctly, byte order is right, barriers are placed correctly, buffer alignment satisfies the firmware.
4. Only after the smoke test passes: "get ARM memory" to know where to put the page tables.
5. Only after that: "get board revision" for the boot identity log line.

If the smoke test fails, no other tag should be attempted — every mailbox bug is most likely a base-address, byte-order, or alignment bug, and the simplest tag is the diagnostic.

## What is UNVERIFIED

Tracked here so they don't slip into "specification by assertion":

- **U1.** That `value_buffer_size` for tag `0x00010005` (get ARM memory) is 8 (two u32: base, size). This matches public references but has not been observed against this firmware.
- **U2.** That the firmware accepts buffers whose bus address is formed as `arm_phys | 0xC0000000` on this BCM2837 firmware build. See § "Bus address" for the why.
- **U3.** The mailbox tag id (if any) for "stop boot watchdog." Path 1 (PM_RSTC write) sidesteps this.
- **U4.** Whether the firmware sets MAIL0_STATUS EMPTY immediately on response, or only after a memory barrier on its side. The conservative `dmb sy` after the EMPTY clears should cover this, but if a response is read as zeros it's the first thing to suspect.
- **U5.** Maximum acceptable `buffer_size`. Public references say up to 8 KB; the safe answer is "keep messages under 1 KB."

Each of U1–U5 is resolvable by experiment as soon as a test kernel exists. The first experiment is the smoke test in § "Bring-up order in code."

## What this plan forbids

- Building any tag interaction that depends on a UNVERIFIED tag id (U3) without first passing the smoke test (tag `0x00000001`).
- Composing a buffer that is not 16-byte aligned, even "just for testing" — firmware silently drops misaligned buffers and the only symptom is "the response never comes." Debugging this with no UART up is not viable.
- Sending on a channel other than 8 in any production kernel path. Other channels (framebuffer = 1, virtual UART = 2/3, touchscreen = 10) are not used by this OS.
- Writing this plan's pseudocode into kernel source until `02-cpu/plan.md` exists and references it. Kernel code goes through a plan, not the other way around.

## Out of scope

- Interrupt-driven mailbox (poll-only for now). Interrupts require `04-interrupts/plan.md`, which doesn't exist.
- Multiple in-flight messages on different channels. The early kernel is single-threaded.
- DMA-driven mailbox responses. Not a real thing — listed only because a careless reader of the BCM2835 manual might think the mailbox supports it. It does not.

## Dependencies satisfied / blocked

| Plan                     | Depended on this for                       | Status now                                    |
|--------------------------|--------------------------------------------|-----------------------------------------------|
| `02-cpu/plan.md`         | Mailbox protocol for board-id / memory-map | Unblocked (writeable next cycle)              |
| `99-recovery/plan.md` Test 3 | Test kernel needing to signal-alive    | Partially unblocked — uses path 1 (PM_RSTC), so does not require the (UNVERIFIED) mailbox watchdog tag. Test 3 can be specified against PM_RSTC directly. |
| `05-uart/plan.md` (clock pinning) | `set_clock_rate` tag                | Unblocked (tag `0x00038002` documented)       |
