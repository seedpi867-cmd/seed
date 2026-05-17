# The Silicon Defense Points at the Wrong Bit

`knowledge/piforge-build/dwc2-overview.md` documents a bare-metal driver for the DWC2 USB OTG controller on a BCM2711 (Pi 4 / CM4). In the "Hardware limitation" section it explains why no high-speed device works:

> HCFG bit 9 (FSLSONLY) = 1. This is silicon, not software.
> Internal PHY cannot sustain HS signaling. No fix possible.

That sentence has three things wrong with it, and each one matters.

## Finding 1 — Bit 9 of HCFG is not what the doc claims

Authoritative source: the Linux kernel's DesignWare DWC2 register definitions at `drivers/usb/dwc2/hw.h`, which the kernel uses for every BCM SoC.

HCFG (host configuration register, offset `0x400`) lays out like this:

| Bits | Field | Source line |
|---|---|---|
| 31 | `MODECHTIMEN` | hw.h:673 |
| 26 | `PERSCHEDENA` | hw.h:674 |
| 24–25 | `FRLISTEN` | hw.h:675–682 |
| 23 | `DESCDMA` | hw.h:684 |
| **8–15** | **`RESVALID`** (resume validation period) | hw.h:685–686 |
| 7 | `ENA32KHZ` | hw.h:687 |
| 2 | `FSLSSUPP` | hw.h:688 |
| 0–1 | `FSLSPCLKSEL` | hw.h:689 |

Bit 9 is not a flag. It is one bit inside `RESVALID`, an 8-bit field describing how many PHY clocks the core waits before declaring a resume signal valid. Reading bit 9 = 1 tells you nothing about high-speed support; it tells you a specific value lives in `RESVALID[1]`.

The FS/LS-only support bit is `FSLSSUPP` at **bit 2**, not bit 9. There is no field named "FSLSONLY" in DesignWare's published HCFG layout at all.

## Finding 2 — `FSLSSUPP` is software-writable, and the same doc uses it that way

The doc's "Hardware limitation" claim depends on the bit being silicon. But `FSLSSUPP` lives in HCFG, the *Host Configuration* register, which is software-writable. Linux writes to it during resume:

```c
/* drivers/usb/dwc2/core.c:188 */
dwc2_writel(hsotg, hr->hcfg, HCFG);
```

The same dwc2-overview.md, eight lines above the silicon claim, says:

> Port reset with FSLSSUPP=1 (forces FS negotiation)

That is the driver writing `FSLSSUPP=1` itself. If FSLSSUPP were a read-only silicon strap, the port-reset step would not be possible. The doc cannot consistently treat the same field as both a software policy lever it sets, and a fused silicon constraint it cannot change.

## Finding 3 — The actual silicon HS-PHY capability lives in GHWCFG2, not HCFG

DesignWare DWC2 cores expose their build-time hardware configuration through the read-only `GHWCFG2` register at offset `0x0048`. The high-speed PHY presence is encoded in bits 6–7 (`drivers/usb/dwc2/hw.h:249–254`):

```
GHWCFG2_HS_PHY_TYPE_MASK        (0x3 << 6)
GHWCFG2_HS_PHY_TYPE_NOT_SUPPORTED  0
GHWCFG2_HS_PHY_TYPE_UTMI           1
GHWCFG2_HS_PHY_TYPE_ULPI           2
GHWCFG2_HS_PHY_TYPE_UTMI_ULPI      3
```

This is the silicon strap. If `GHWCFG2.HS_PHY_TYPE` reads `0`, the core was synthesised without a high-speed PHY and no software setting can rescue it. If it reads non-zero, the silicon supports HS and the FS/LS-only behaviour is a software or board-bring-up problem.

The doc never checks GHWCFG2. The "no fix possible" verdict is reached without consulting the register that would actually answer the question.

## Why this matters

For BCM2711 specifically, the dwc2 OTG at `0xfe980000` is the same controller Linux uses as the USB-C dual-role port at high speed in stock distros. Stock Pi 4 / CM4 hardware reports `GHWCFG2.HS_PHY_TYPE = UTMI` and runs HS as host. So one of two things is true on the Elecrow CM4 terminal that motivated this doc:

1. `GHWCFG2.HS_PHY_TYPE` is non-zero, the silicon does support HS, and the v75–v86 failures had a software cause that the project abandoned investigating because "bit 9" looked like silicon.
2. The board's PHY is held in reset or unpowered (a board-level issue, not silicon), and the read-only GHWCFG2 value would *still* report HS as present.

Either way, citing `HCFG bit 9` as evidence forecloses the only diagnostic that would distinguish the two cases.

## The correction

The "Hardware limitation" section should be replaced with:

1. **Read `GHWCFG2` (`0x0048`) once during init and log bits 6–7.** That is the silicon capability check.
2. **Treat `HCFG.FSLSSUPP` (bit 2) as software policy.** Set it deliberately when you want to force FS/LS negotiation; clear it when you want HS to be attempted.
3. **Remove "bit 9", "FSLSONLY", and "silicon, not software" from the doc.** None of those refer to a real field in HCFG. If HS truly cannot be reached on this board, the doc should cite the GHWCFG2 reading and any board-level PHY-supply or reset state that explains it.

The DWC2 driver's failure to reach high speed may well be a real, unrecoverable constraint on this particular hardware. But the doc's stated reason — three wrong labels on one conclusion — does not carry that weight. The verdict needs to be re-derived from the register that actually answers the question.
