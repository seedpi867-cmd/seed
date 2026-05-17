/*
 * forward.c — transformer forward pass for SmolLM2-class LLMs.
 *
 * One call to forward() processes one token and returns logits.
 * KV cache grows with each call (autoregressive generation).
 *
 * Phase 1: uses malloc, standard math (sqrtf, expf).
 * Phase 2: swap for static alloc + polynomial exp approximation.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "inference.h"
#include "ops.h"
#include "ops_q8.h"
#include "q4.h"
#include "fp16.h"

/* ---- scratch allocation ---- */

int fwd_init(fwd_t *f, const model_t *m) {
    memset(f, 0, sizeof(*f));
    int H  = (int)m->hp.hidden_dim;
    int KD = m->kv_dim;
    int F  = (int)m->hp.ffn_dim;
    int V  = (int)m->hp.n_vocab;
    int L  = (int)m->hp.n_layers;

    /* Single scratch alloc: x + xb + q + k + v + scores + gate + up + logits */
    size_t scratch = (size_t)(H + H + H + KD + KD + MAX_SEQ + F + F + V) * sizeof(float);

    /* KV cache: 2 × L × MAX_SEQ × KD floats */
    size_t kv = (size_t)2 * L * MAX_SEQ * KD * sizeof(float);

    uint8_t *buf = malloc(scratch + kv);
    if (!buf) return -1;

    float *p  = (float *)buf;
    f->x      = p; p += H;
    f->xb     = p; p += H;
    f->q      = p; p += H;       /* n_heads × head_dim = H */
    f->k      = p; p += KD;
    f->v      = p; p += KD;
    f->scores = p; p += MAX_SEQ;
    f->gate   = p; p += F;
    f->up     = p; p += F;
    f->logits = p; p += V;

    /* KV cache comes right after scratch */
    float *kv_ptr = (float *)((uint8_t *)buf + scratch);
    f->k_cache = kv_ptr;
    f->v_cache = kv_ptr + (size_t)L * MAX_SEQ * KD;

    f->max_seq = MAX_SEQ;
    f->pos     = 0;
    return 0;
}

void fwd_free(fwd_t *f) {
    free(f->x);  /* only one allocation */
    f->x = NULL;
}

/* ---- embedding lookup ---- */

/*
 * Dequantize row token_id from the embedding table into out[hidden_dim].
 * Supports Q4_0 and F32 (and falls back for F16 via fp16_to_f32).
 */
static void embed_token(const model_t *m, int token_id, float *out) {
    tensor_embed(m->embd, m->embd_type, token_id, out, (int)m->hp.hidden_dim);
}

/* ---- RoPE ---- */

/*
 * Apply rotary position embedding in-place to vec (n_heads × head_dim).
 * Only first n_kv_heads worth are rotated when doing K (kv_only=1).
 */
static void apply_rope(float *vec, int n_heads, int head_dim, int pos, float theta) {
    for (int h = 0; h < n_heads; h++) {
        float *v = vec + h * head_dim;
        for (int i = 0; i < head_dim / 2; i++) {
            float freq  = 1.0f / powf(theta, 2.0f * (float)i / (float)head_dim);
            float angle = (float)pos * freq;
            float cos_a = cosf(angle);
            float sin_a = sinf(angle);
            float v0 = v[i];
            float v1 = v[i + head_dim / 2];
            v[i]              = v0 * cos_a - v1 * sin_a;
            v[i + head_dim/2] = v0 * sin_a + v1 * cos_a;
        }
    }
}

/* ---- attention ---- */

static void attention_layer(const model_t *m, fwd_t *f, int layer) {
    const layer_weights_t *lw = &m->layer[layer];
    int H   = (int)m->hp.hidden_dim;
    int nh  = (int)m->hp.n_heads;
    int nkv = (int)m->hp.n_kv_heads;
    int hd  = m->head_dim;
    int KD  = m->kv_dim;
    int pos = f->pos;
    (void)m->hp.n_layers; /* L not used here */
    float theta = m->hp.rope_theta;

    /* Q, K, V projections — dispatch by tensor type */
    tensor_matmul(lw->wq, lw->wq_type, f->xb, f->q, H, H);
    tensor_matmul(lw->wk, lw->wk_type, f->xb, f->k, KD, H);
    tensor_matmul(lw->wv, lw->wv_type, f->xb, f->v, KD, H);

    /* RoPE on Q (all heads) and K (kv heads) */
    apply_rope(f->q, nh,  hd, pos, theta);
    apply_rope(f->k, nkv, hd, pos, theta);

    /* Write K, V into cache at this position */
    /* k_cache layout: [L][MAX_SEQ][KD] */
    float *kc = f->k_cache + ((size_t)layer * MAX_SEQ + pos) * KD;
    float *vc = f->v_cache + ((size_t)layer * MAX_SEQ + pos) * KD;
    memcpy(kc, f->k, (size_t)KD * sizeof(float));
    memcpy(vc, f->v, (size_t)KD * sizeof(float));

    /* Multi-head attention with GQA */
    float scale = 1.0f / sqrtf((float)hd);

    /* Accumulate attention output into xb (reuse as attn output buffer) */
    memset(f->xb, 0, (size_t)H * sizeof(float));

    for (int h = 0; h < nh; h++) {
        int kv_h = h / m->gqa_ratio;   /* which KV head this query head uses */
        const float *q_h = f->q + h * hd;

        /* Compute attention scores for all positions 0..pos */
        for (int t = 0; t <= pos; t++) {
            const float *k_t = f->k_cache + ((size_t)layer * MAX_SEQ + t) * KD + kv_h * hd;
            float score = 0.0f;
            for (int d = 0; d < hd; d++) score += q_h[d] * k_t[d];
            f->scores[t] = score * scale;
        }
        softmax(f->scores, pos + 1);

        /* Weighted sum of values → attn output for head h */
        float *out_h = f->xb + h * hd;
        for (int t = 0; t <= pos; t++) {
            const float *v_t = f->v_cache + ((size_t)layer * MAX_SEQ + t) * KD + kv_h * hd;
            float w = f->scores[t];
            for (int d = 0; d < hd; d++) out_h[d] += w * v_t[d];
        }
    }

    /* O projection: [H × H] × attn_out → scratch, add residual */
    float *tmp = f->k;   /* reuse k buffer (overwritten next layer anyway) */
    tensor_matmul(lw->wo, lw->wo_type, f->xb, tmp, H, H);
    vec_add(f->x, tmp, H);
}

/* ---- FFN ---- */

static void ffn_layer(const model_t *m, fwd_t *f, int layer) {
    const layer_weights_t *lw = &m->layer[layer];
    int H = (int)m->hp.hidden_dim;
    int F = (int)m->hp.ffn_dim;

    tensor_matmul(lw->wgate, lw->wgate_type, f->xb, f->gate, F, H);
    tensor_matmul(lw->wup,   lw->wup_type,   f->xb, f->up,   F, H);
    silu_elementwise(f->gate, f->up, f->gate, F);
    tensor_matmul(lw->wdown, lw->wdown_type, f->gate, f->xb, H, F);
    vec_add(f->x, f->xb, H);
}

/* ---- lm_head ---- */

static void compute_logits(const model_t *m, fwd_t *f) {
    int H = (int)m->hp.hidden_dim;
    int V = (int)m->hp.n_vocab;

    tensor_matmul(m->lm_head, m->lm_head_type, f->x, f->logits, V, H);
}

/* ---- public: full forward pass ---- */

float *forward(const model_t *m, fwd_t *f, int token_id) {
    int H = (int)m->hp.hidden_dim;
    int L = (int)m->hp.n_layers;

    if (f->pos >= f->max_seq) {
        fprintf(stderr, "forward: sequence length exceeded (%d)\n", f->max_seq);
        return NULL;
    }

    /* 1. Embedding lookup */
    embed_token(m, token_id, f->x);

    /* 2. Transformer layers */
    for (int l = 0; l < L; l++) {
        const layer_weights_t *lw = &m->layer[l];

        /* Pre-attention RMSNorm: xb = norm(x) */
        rms_norm(f->x, lw->attn_norm, f->xb, H, m->hp.rms_norm_eps);

        /* Attention sublayer (reads xb, updates x via residual) */
        attention_layer(m, f, l);

        /* Pre-FFN RMSNorm: xb = norm(x) */
        rms_norm(f->x, lw->ffn_norm, f->xb, H, m->hp.rms_norm_eps);

        /* FFN sublayer (reads xb, updates x via residual) */
        ffn_layer(m, f, l);
    }

    /* 3. Final RMSNorm */
    rms_norm(f->x, m->output_norm, f->x, H, m->hp.rms_norm_eps);

    /* 4. LM head → logits */
    compute_logits(m, f);

    f->pos++;
    return f->logits;
}
