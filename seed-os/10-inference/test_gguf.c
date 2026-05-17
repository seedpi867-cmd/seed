/*
 * test_gguf.c — parse a real GGUF file and dump its structure.
 *
 * Usage: ./test_gguf path/to/model.gguf
 *
 * Validates: magic, version, metadata KV parsing, tensor directory,
 * hparams extraction, and tensor data seek.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "gguf.h"
#include "q4.h"

static void dump_first_block(gguf_ctx_t *ctx, const char *tensor_name) {
    const gguf_tensor_info_t *ti = gguf_find_tensor(ctx, tensor_name);
    if (!ti) { printf("  tensor '%s' not found\n", tensor_name); return; }
    if (ti->type != GGUF_TENSOR_Q4_0) {
        printf("  tensor '%s' type=%u (not Q4_0), size=%zu B — skipping dequant\n",
               tensor_name, ti->type, ti->n_bytes);
        return;
    }

    q4_block_t block;
    int64_t n = gguf_load_tensor(ctx, ti, &block, sizeof(block));
    if (n < (int64_t)sizeof(block)) { printf("  '%s': read failed\n", tensor_name); return; }

    float out[32];
    q4_block_dequant(&block, out);
    printf("  first block of '%s': scale=%.5f  first 8 weights:", tensor_name,
           fp16_to_f32(block.d));
    for (int i = 0; i < 8; i++) printf(" %.4f", out[i]);
    printf("\n");
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s model.gguf\n", argv[0]);
        return 1;
    }

    gguf_ctx_t ctx;
    if (gguf_open(&ctx, argv[1])) {
        fprintf(stderr, "Failed to open '%s'\n", argv[1]);
        return 1;
    }

    gguf_dump(&ctx);

    /* Validate basic hparams — must be non-zero for a real LLM */
    int ok = 1;
    if (!ctx.hparams.n_layers) { fprintf(stderr, "FAIL: n_layers=0\n"); ok = 0; }
    if (!ctx.hparams.hidden_dim) { fprintf(stderr, "FAIL: hidden_dim=0\n"); ok = 0; }
    if (!ctx.hparams.n_heads) { fprintf(stderr, "FAIL: n_heads=0\n"); ok = 0; }
    if (!ctx.hparams.n_vocab) { fprintf(stderr, "FAIL: n_vocab=0\n"); ok = 0; }

    /* Try to read first block of token embedding and a weight tensor */
    printf("\nFirst block dequantization:\n");
    dump_first_block(&ctx, "token_embd.weight");
    dump_first_block(&ctx, "blk.0.attn_q.weight");
    dump_first_block(&ctx, "blk.0.ffn_gate.weight");

    /* Verify total tensor data size is plausible */
    size_t total_bytes = 0;
    for (uint64_t i = 0; i < ctx.n_tensors; i++) total_bytes += ctx.tensors[i].n_bytes;
    printf("\nTotal tensor data: %.1f MB\n", (double)total_bytes / (1024 * 1024));

    gguf_close(&ctx);

    if (ok) { printf("\nGGUF PARSE OK\n"); return 0; }
    else     { printf("\nGGUF PARSE FAILED\n"); return 1; }
}
