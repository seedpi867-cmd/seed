/*
 * model.c — load all weights from a GGUF file into model_t.
 *
 * Handles mixed quantization: Q4_0, Q4_1, Q8_0, F32 tensors in the same model.
 * Uses GGUF-reported tensor sizes (not assumed Q4_0 sizes) for correctness.
 *
 * Phase 2: replace fopen/fread/malloc with SD sector reads + bump allocator.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "inference.h"
#include "gguf.h"
#include "ops_q8.h"

/* ---- helpers ---- */

/*
 * Load one named tensor into dst (caller allocated). Returns 0 on success.
 * Stores the tensor's type into *type_out.
 */
static int load_named(gguf_ctx_t *ctx, const char *name,
                       void *dst, size_t dst_bytes, uint32_t *type_out) {
    const gguf_tensor_info_t *ti = gguf_find_tensor(ctx, name);
    if (!ti) { fprintf(stderr, "model: tensor '%s' not found\n", name); return -1; }
    if (ti->n_bytes > dst_bytes) {
        fprintf(stderr, "model: '%s': tensor %zu B > dst %zu B\n",
                name, ti->n_bytes, dst_bytes);
        return -1;
    }
    int64_t n = gguf_load_tensor(ctx, ti, dst, ti->n_bytes);
    if (n < 0 || (size_t)n != ti->n_bytes) {
        fprintf(stderr, "model: '%s': read failed (%lld)\n", name, (long long)n);
        return -1;
    }
    if (type_out) *type_out = ti->type;
    return 0;
}

/* Return n_bytes for a named tensor, or 0 if not found. */
static size_t tensor_bytes(gguf_ctx_t *ctx, const char *name) {
    const gguf_tensor_info_t *ti = gguf_find_tensor(ctx, name);
    return ti ? ti->n_bytes : 0;
}

/* ---- public API ---- */

int model_load(model_t *m, const char *path) {
    memset(m, 0, sizeof(*m));

    gguf_ctx_t ctx;
    if (gguf_open(&ctx, path)) return -1;

    gguf_hparams_t *hp = &ctx.hparams;
    m->hp        = *hp;
    m->head_dim  = (int)hp->hidden_dim / (int)hp->n_heads;
    m->kv_dim    = (int)hp->n_kv_heads * m->head_dim;
    m->gqa_ratio = (int)hp->n_heads / (int)hp->n_kv_heads;

    if (!hp->n_layers || !hp->hidden_dim || !hp->n_heads || !hp->n_vocab) {
        fprintf(stderr, "model: hparams incomplete\n"); goto fail;
    }
    if ((int)hp->n_layers > MAX_LAYERS) {
        fprintf(stderr, "model: %u layers > MAX_LAYERS %d\n", hp->n_layers, MAX_LAYERS);
        goto fail;
    }
    printf("model: layers=%u hidden=%u heads=%u kv_heads=%u ffn=%u vocab=%u\n",
           hp->n_layers, hp->hidden_dim, hp->n_heads, hp->n_kv_heads,
           hp->ffn_dim, hp->n_vocab);
    printf("model: head_dim=%d kv_dim=%d gqa=%d\n", m->head_dim, m->kv_dim, m->gqa_ratio);

    /* ---- Pass 1: compute total buffer size using GGUF-reported sizes ---- */
    int L = (int)hp->n_layers;
    int H = (int)hp->hidden_dim;
    char name[128];

    size_t total = 0;

    /* token_embd */
    size_t embd_sz = tensor_bytes(&ctx, "token_embd.weight");
    if (!embd_sz) { fprintf(stderr, "model: missing token_embd.weight\n"); goto fail; }
    total += embd_sz;

    /* output_norm */
    size_t outnorm_sz = tensor_bytes(&ctx, "output_norm.weight");
    if (!outnorm_sz) { fprintf(stderr, "model: missing output_norm.weight\n"); goto fail; }
    total += outnorm_sz;

    /* per-layer */
    for (int l = 0; l < L; l++) {
        const char *keys[] = {
            "attn_norm.weight", "attn_q.weight", "attn_k.weight", "attn_v.weight",
            "attn_output.weight", "ffn_norm.weight", "ffn_gate.weight",
            "ffn_up.weight", "ffn_down.weight"
        };
        for (int k = 0; k < 9; k++) {
            snprintf(name, sizeof(name), "blk.%d.%s", l, keys[k]);
            size_t sz = tensor_bytes(&ctx, name);
            if (!sz) { fprintf(stderr, "model: missing %s\n", name); goto fail; }
            total += sz;
        }
    }

    /* lm_head (may be absent = tied to embd) */
    int has_lm_head = (gguf_find_tensor(&ctx, "output.weight") != NULL);
    size_t lmhead_sz = has_lm_head ? tensor_bytes(&ctx, "output.weight") : 0;
    total += lmhead_sz;

    printf("model: allocating %.1f MB for all weights\n", (double)total / (1<<20));
    m->buf = malloc(total);
    if (!m->buf) { fprintf(stderr, "model: OOM (%zu B)\n", total); goto fail; }
    m->buf_size = total;

    /* ---- Pass 2: load tensors into buffer ---- */
    uint8_t *ptr = (uint8_t *)m->buf;

    /* token_embd */
    m->embd = ptr;
    if (load_named(&ctx, "token_embd.weight", ptr, embd_sz, &m->embd_type)) goto fail;
    ptr += embd_sz;

    /* output_norm (always F32) */
    m->output_norm = (float *)ptr;
    {
        uint32_t t;
        if (load_named(&ctx, "output_norm.weight", ptr, outnorm_sz, &t)) goto fail;
        if (t != GGUF_TENSOR_F32) {
            fprintf(stderr, "model: output_norm not F32 (type=%u)\n", t);
            goto fail;
        }
    }
    ptr += outnorm_sz;

    /* per-layer */
    for (int l = 0; l < L; l++) {
        layer_weights_t *lw = &m->layer[l];

#define LOAD_LAYER(field, field_type, key) do {                              \
            snprintf(name, sizeof(name), "blk.%d." key, l);                 \
            size_t _sz = tensor_bytes(&ctx, name);                           \
            lw->field = ptr;                                                 \
            if (load_named(&ctx, name, ptr, _sz, &lw->field_type)) goto fail;\
            /* norm weights must be F32 */                                   \
            ptr += _sz;                                                      \
        } while (0)

        /* attn_norm: must be F32, store as float* */
        snprintf(name, sizeof(name), "blk.%d.attn_norm.weight", l);
        {
            size_t sz = tensor_bytes(&ctx, name);
            uint32_t t;
            lw->attn_norm = (float *)ptr;
            if (load_named(&ctx, name, ptr, sz, &t)) goto fail;
            if (t != GGUF_TENSOR_F32) {
                fprintf(stderr, "model: %s not F32\n", name); goto fail;
            }
            ptr += sz;
        }

        /* weight matrices */
        snprintf(name, sizeof(name), "blk.%d.attn_q.weight", l);
        { size_t sz = tensor_bytes(&ctx, name); lw->wq = ptr;
          if (load_named(&ctx, name, ptr, sz, &lw->wq_type)) goto fail; ptr += sz; }

        snprintf(name, sizeof(name), "blk.%d.attn_k.weight", l);
        { size_t sz = tensor_bytes(&ctx, name); lw->wk = ptr;
          if (load_named(&ctx, name, ptr, sz, &lw->wk_type)) goto fail; ptr += sz; }

        snprintf(name, sizeof(name), "blk.%d.attn_v.weight", l);
        { size_t sz = tensor_bytes(&ctx, name); lw->wv = ptr;
          if (load_named(&ctx, name, ptr, sz, &lw->wv_type)) goto fail; ptr += sz; }

        snprintf(name, sizeof(name), "blk.%d.attn_output.weight", l);
        { size_t sz = tensor_bytes(&ctx, name); lw->wo = ptr;
          if (load_named(&ctx, name, ptr, sz, &lw->wo_type)) goto fail; ptr += sz; }

        /* ffn_norm: must be F32 */
        snprintf(name, sizeof(name), "blk.%d.ffn_norm.weight", l);
        {
            size_t sz = tensor_bytes(&ctx, name);
            uint32_t t;
            lw->ffn_norm = (float *)ptr;
            if (load_named(&ctx, name, ptr, sz, &t)) goto fail;
            if (t != GGUF_TENSOR_F32) {
                fprintf(stderr, "model: %s not F32\n", name); goto fail;
            }
            ptr += sz;
        }

        snprintf(name, sizeof(name), "blk.%d.ffn_gate.weight", l);
        { size_t sz = tensor_bytes(&ctx, name); lw->wgate = ptr;
          if (load_named(&ctx, name, ptr, sz, &lw->wgate_type)) goto fail; ptr += sz; }

        snprintf(name, sizeof(name), "blk.%d.ffn_up.weight", l);
        { size_t sz = tensor_bytes(&ctx, name); lw->wup = ptr;
          if (load_named(&ctx, name, ptr, sz, &lw->wup_type)) goto fail; ptr += sz; }

        snprintf(name, sizeof(name), "blk.%d.ffn_down.weight", l);
        { size_t sz = tensor_bytes(&ctx, name); lw->wdown = ptr;
          if (load_named(&ctx, name, ptr, sz, &lw->wdown_type)) goto fail; ptr += sz; }

#undef LOAD_LAYER

        if (l == 0 || l == L-1)
            printf("  layer %d: wq_type=%u wdown_type=%u\n", l, lw->wq_type, lw->wdown_type);
    }

    /* lm_head */
    if (has_lm_head) {
        m->lm_head = ptr;
        if (load_named(&ctx, "output.weight", ptr, lmhead_sz, &m->lm_head_type)) goto fail;
        ptr += lmhead_sz;
    } else {
        m->lm_head      = m->embd;
        m->lm_head_type = m->embd_type;
        printf("model: lm_head tied to token_embd\n");
    }

    gguf_close(&ctx);
    printf("model: loaded OK — %.1f MB used\n",
           (double)(ptr - (uint8_t *)m->buf) / (1<<20));
    return 0;

fail:
    gguf_close(&ctx);
    free(m->buf);
    m->buf = NULL;
    return -1;
}

void model_free(model_t *m) {
    free(m->buf);
    m->buf = NULL;
}
