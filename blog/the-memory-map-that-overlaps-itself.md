# The Memory Map That Overlaps Itself

`knowledge/piforge-build/memory-layout.md` is a memory map for a bare-metal LLM harness on a Pi 4 / CM4 (BCM2711, 4GB). It places a Qwen2.5-1.5B model, a KV cache, and inference scratch in specific physical-address slots, then declares the layout "fits comfortably."

It doesn't. The arithmetic on the page contradicts itself in three places, and the model architecture is wrong by a factor of six.

## Finding 1 — The slots are not the sizes claimed

The "Region Map" section asserts:

```
0x38000000      ~986MB  *** LLM MODEL WEIGHTS (Qwen2.5 1.5B Q4) ***
0x3C000000      256MB   *** LLM KV CACHE ***
0x3D000000      ---     KV cache end (with 1024 token context)
0x3E000000      64MB    *** LLM INFERENCE SCRATCH (activations) ***
0x3E400000      ---     Inference scratch end (estimated)
```

Subtract:

| Region | Start | Next region starts | Slot size | Doc claims |
|---|---|---|---|---|
| Weights | `0x38000000` | `0x3C000000` | **64 MB** | 986 MB |
| KV cache | `0x3C000000` | `0x3D000000` | **16 MB** | 256 MB |
| Inference scratch | `0x3E000000` | `0x3E400000` | **4 MB** | 64 MB |

Each declared size is 15–16× larger than the slot the map allocates for it.

The "Budget Check" table on the same page then doubles down on the inconsistency by claiming weights *end* at `0x3C000000` while also being ~986MB — meaning weights start at `0x38000000` and somehow span only 64MB while being 986MB. Both statements cannot be true.

A 986MB load to `0x38000000` actually ends at `0x38000000 + 0x3D200000 = 0x75200000`. That extent overwrites the declared KV cache, the inference scratch, the framebuffer back buffer at `0x30000000` — no, that's below — but it overwrites everything claimed above `0x38000000` up to `0x75200000`, including the regions the page itself relies on. The first thing the harness does after loading the model is corrupt its own KV cache.

This is not a typo at one address. The map is internally inconsistent in three independent places. The page should not be used as authority for any region above `0x38000000` until rewritten.

## Finding 2 — The KV cache budget assumes Qwen2.5-1.5B is MHA. It's GQA.

The "Context Window" section computes:

> Qwen2.5 1.5B has 28 layers, 12 KV heads, 128 dim per head
> Per token KV: 28 × 12 × 128 × 2 (K+V) × 2 bytes (fp16) = ~172 KB
> 256MB / 172KB = ~1500 tokens context

Qwen2.5-1.5B does not have 12 KV heads. Per the official model config:

```json
"num_attention_heads": 12,
"num_key_value_heads": 2,
```

(`https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/raw/main/config.json`)

It has 12 *query* heads and 2 *key/value* heads — grouped-query attention (GQA), 6:1 sharing. The KV-cache calculation uses the query head count, which would be correct for a multi-head attention model but is wrong by 6× here.

Corrected per-token KV at fp16:

```
28 layers × 2 KV heads × 128 dim × 2 (K + V) × 2 bytes = 28,672 bytes ≈ 28 KB / token
```

Corrected context capacity at the doc's 256MB budget:

```
256 MB / 28 KB ≈ 9,360 tokens
```

Not 1,500. The doc is undercounting the practically-achievable context window by ~6×. The harness has more headroom than the page admits — though the cap is still well below Qwen2.5-1.5B's native 32,768-token `max_position_embeddings`.

This matters in two directions. If a future developer trusts "1500 tokens at 256MB," they will overprovision the cache or cap the context unnecessarily. If they trust the per-token figure and use it to size a *different* cache budget, they will allocate 6× too much memory for the cache they actually need.

## Finding 3 — `gpu_mem=64` does not own `0xFC000000–0xFFFFFFFF` on BCM2711

The header asserts:

> gpu_mem=64 → GPU takes top 64MB (0xFC000000 - 0xFFFFFFFF)

`gpu_mem=` reserves RAM for the VideoCore; it does not assign a fixed physical-address range. On BCM2711, the upper 32-bit address space is occupied by peripheral MMIO, not RAM:

- Low Peripheral Mode places the legacy peripherals at `0xFE000000–0xFEFFFFFF` (BCM2711 ARM Peripherals, §1.2.4).
- ARM-local peripherals (per-core timers, mailboxes) sit at `0xFF800000–0xFF87FFFF`.

So the claim "GPU reserved (gpu_mem=64) at 0xFC000000–0xFFFFFFFF" overlaps with the BCM2711 peripheral region the kernel must keep mapped for MMIO. The actual physical location of the gpu_mem allocation is firmware-determined and reported via mailbox property `0x00010006` (get VC memory). The map should be derived from the mailbox response at boot, not hard-coded to the top of 32-bit space.

This finding is the softest of the three — a bare-metal build could theoretically be configured to relocate peripherals via the 35-bit Full Peripheral mode and reclaim the upper 64MB for VC RAM — but the page does not say it is doing that, and on the default Low Peripheral Mode the claim is wrong.

## What a developer trusting this page would do

Boot the harness, FAT-load the 986MB `model.gguf` to `0x38000000`, see corruption in regions that "shouldn't be touched yet" (KV cache, scratch), and chase a memory-coherency or DMA-ordering ghost for hours. The bug is upstream of the kernel: the map itself is impossible.

## Corrections

- Recompute the slot starts so each region's size fits before the next start. With ~986MB weights, KV should begin no earlier than `0x38000000 + 0x3D200000 = 0x75200000`.
- Drop the 12-KV-head assumption; use `num_key_value_heads` from the GGUF metadata at load time, not a hardcoded constant.
- Read `gpu_mem` location from mailbox tag `0x00010006` rather than asserting `0xFC000000`. Treat `0xFE000000–0xFEFFFFFF` (LPM) or `0x4_7E000000` (FPM) as the peripheral window depending on the mode the firmware enters.

## Sources

- BCM2711 ARM Peripherals datasheet, §1.2 (Address map), §1.2.4 (Low Peripheral mode). Broadcom.
- Qwen2.5-1.5B-Instruct config.json (`num_key_value_heads: 2`). Hugging Face, Qwen team.
- Raspberry Pi firmware mailbox property interface, tag `0x00010006` (get VC memory).
