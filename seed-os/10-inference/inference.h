/*
 * inference.h — model and forward-pass state types for SmolLM2-class LLMs.
 *
 * Phase 1: runs under Linux with FILE* I/O and malloc.
 * Phase 2: swap FILE* for SD sector reads, malloc for static bump allocator.
 */
#ifndef INFERENCE_H
#define INFERENCE_H

#include <stdint.h>
#include <stddef.h>
#include "gguf.h"
#include "q4.h"

#define MAX_LAYERS   32
#define MAX_SEQ      512

/* ---- model weight store ---- */

typedef struct {
    float   *attn_norm;             /* RMSNorm [hidden_dim] — always F32 */
    void    *wq;  uint32_t wq_type; /* Q projection [hidden_dim × hidden_dim] */
    void    *wk;  uint32_t wk_type; /* K projection [kv_dim × hidden_dim] */
    void    *wv;  uint32_t wv_type; /* V projection [kv_dim × hidden_dim] */
    void    *wo;  uint32_t wo_type; /* O projection [hidden_dim × hidden_dim] */
    float   *ffn_norm;              /* RMSNorm [hidden_dim] — always F32 */
    void    *wgate; uint32_t wgate_type; /* FFN gate [ffn_dim × hidden_dim] */
    void    *wup;   uint32_t wup_type;   /* FFN up   [ffn_dim × hidden_dim] */
    void    *wdown; uint32_t wdown_type; /* FFN down [hidden_dim × ffn_dim] */
} layer_weights_t;

typedef struct {
    gguf_hparams_t hp;
    int head_dim;       /* hidden_dim / n_heads */
    int kv_dim;         /* n_kv_heads * head_dim */
    int gqa_ratio;      /* n_heads / n_kv_heads — how many Q heads share one KV head */

    void    *embd;          /* token_embd.weight — Q4_0 [n_vocab × hidden_dim] */
    uint32_t embd_type;     /* GGUF_TENSOR_* for dispatch */

    layer_weights_t layer[MAX_LAYERS];

    float   *output_norm;   /* F32 [hidden_dim] */
    void    *lm_head;       /* Q4_0 [n_vocab × hidden_dim]; may point to embd if tied */
    uint32_t lm_head_type;

    void   *buf;            /* backing malloc block for ALL tensor data */
    size_t  buf_size;
} model_t;

/* ---- forward pass scratch space ---- */

typedef struct {
    float *x;       /* current hidden state [hidden_dim] */
    float *xb;      /* scratch hidden [hidden_dim] */
    float *q;       /* Q after projection + RoPE [n_heads × head_dim] */
    float *k;       /* K after projection + RoPE [n_kv_heads × head_dim] */
    float *v;       /* V after projection [n_kv_heads × head_dim] */
    float *scores;  /* attention scores [MAX_SEQ] */
    float *gate;    /* FFN gate scratch [ffn_dim] */
    float *up;      /* FFN up scratch [ffn_dim] */
    float *logits;  /* output logits [n_vocab] */

    /* KV cache: [n_layers][MAX_SEQ][n_kv_heads][head_dim] */
    float *k_cache; /* (n_layers * MAX_SEQ * kv_dim) floats */
    float *v_cache;

    int max_seq;    /* capacity (= MAX_SEQ) */
    int pos;        /* current generation position (0-based) */
} fwd_t;

/* ---- API ---- */

/*
 * Load model from a GGUF file. Allocates model->buf internally.
 * Returns 0 on success. Call model_free() when done.
 */
int  model_load(model_t *m, const char *path);
void model_free(model_t *m);

/*
 * Allocate forward-pass scratch space for the given model.
 * Returns 0 on success. Call fwd_free() when done.
 */
int  fwd_init(fwd_t *f, const model_t *m);
void fwd_free(fwd_t *f);

/*
 * Run one forward pass: embed token_id, run all layers, compute logits.
 * Updates f->pos. Returns pointer to f->logits (n_vocab floats).
 */
float *forward(const model_t *m, fwd_t *f, int token_id);

#endif /* INFERENCE_H */
