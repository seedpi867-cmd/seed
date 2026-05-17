/*
 * gguf_load.c — GGUF v3 file parser.
 *
 * Reads the header, metadata KV pairs, and tensor info table.
 * Extracts model hyperparameters from metadata into gguf_hparams_t.
 *
 * Phase 2: replace FILE* with bare-metal SD sector reads.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "gguf.h"

/* ---- low-level read helpers ---- */

static int read_u8(FILE *f, uint8_t *v)   { return fread(v, 1, 1, f) == 1 ? 0 : -1; }
static int read_u16(FILE *f, uint16_t *v) { return fread(v, 2, 1, f) == 1 ? 0 : -1; }
static int read_u32(FILE *f, uint32_t *v) { return fread(v, 4, 1, f) == 1 ? 0 : -1; }
static int read_u64(FILE *f, uint64_t *v) { return fread(v, 8, 1, f) == 1 ? 0 : -1; }
static int read_i32(FILE *f, int32_t  *v) { return fread(v, 4, 1, f) == 1 ? 0 : -1; }
static int read_i64(FILE *f, int64_t  *v) { return fread(v, 8, 1, f) == 1 ? 0 : -1; }
static int read_f32(FILE *f, float    *v) { return fread(v, 4, 1, f) == 1 ? 0 : -1; }
static int read_f64(FILE *f, double   *v) { return fread(v, 8, 1, f) == 1 ? 0 : -1; }

/* Read a GGUF string: uint64 length + bytes (NOT null-terminated in file). */
static int read_str(FILE *f, char *buf, size_t buf_len) {
    uint64_t slen;
    if (read_u64(f, &slen)) return -1;
    if (slen >= buf_len) { fseek(f, (long)slen, SEEK_CUR); buf[0] = '\0'; return 0; }
    if (fread(buf, 1, (size_t)slen, f) != slen) return -1;
    buf[slen] = '\0';
    return 0;
}

/* Skip a GGUF string without storing it. */
static int skip_str(FILE *f) {
    uint64_t slen;
    if (read_u64(f, &slen)) return -1;
    return fseek(f, (long)slen, SEEK_CUR) == 0 ? 0 : -1;
}

/* Skip one metadata value of the given type. */
static int skip_value(FILE *f, uint32_t vtype);

static int skip_value(FILE *f, uint32_t vtype) {
    uint8_t  u8;  uint16_t u16; uint32_t u32; uint64_t u64;
    int32_t  i32; int64_t  i64; float f32;    double   f64;
    switch (vtype) {
        case GGUF_TYPE_UINT8:   return read_u8(f, &u8);
        case GGUF_TYPE_BOOL:    return read_u8(f, &u8);
        case GGUF_TYPE_INT8:    return read_u8(f, &u8);
        case GGUF_TYPE_UINT16:  return read_u16(f, &u16);
        case GGUF_TYPE_INT16:   return read_u16(f, &u16);
        case GGUF_TYPE_UINT32:  return read_u32(f, &u32);
        case GGUF_TYPE_INT32:   return read_i32(f, &i32);
        case GGUF_TYPE_FLOAT32: return read_f32(f, &f32);
        case GGUF_TYPE_UINT64:  return read_u64(f, &u64);
        case GGUF_TYPE_INT64:   return read_i64(f, &i64);
        case GGUF_TYPE_FLOAT64: return read_f64(f, &f64);
        case GGUF_TYPE_STRING:  return skip_str(f);
        case GGUF_TYPE_ARRAY: {
            uint32_t elem_type; uint64_t count;
            if (read_u32(f, &elem_type)) return -1;
            if (read_u64(f, &count))     return -1;
            for (uint64_t i = 0; i < count; i++)
                if (skip_value(f, elem_type)) return -1;
            return 0;
        }
        default: return -1;
    }
    (void)u8; (void)u16; (void)u32; (void)u64;
    (void)i32; (void)i64; (void)f32; (void)f64;
}

/* ---- hparams extraction from key-value pairs ---- */

/*
 * GGUF uses an architecture-specific prefix derived from "general.architecture".
 * Common prefixes: "llama.", "mistral.", "phi.", "gemma.", "qwen2.", etc.
 * We match the SUFFIX of the key (after the first dot) to be architecture-agnostic.
 */
static const char *key_suffix(const char *key) {
    const char *dot = strchr(key, '.');
    return dot ? dot + 1 : key;
}

static void extract_hparam_u32(gguf_hparams_t *hp, const char *key,
                                uint32_t val) {
    const char *s = key_suffix(key);
    if (!strcmp(s, "block_count"))                hp->n_layers   = val;
    else if (!strcmp(s, "embedding_length"))       hp->hidden_dim = val;
    else if (!strcmp(s, "attention.head_count"))   hp->n_heads    = val;
    else if (!strcmp(s, "attention.head_count_kv"))hp->n_kv_heads = val;
    else if (!strcmp(s, "feed_forward_length"))    hp->ffn_dim    = val;
    else if (!strcmp(s, "context_length"))         hp->max_seq_len= val;
}

static void extract_hparam_f32(gguf_hparams_t *hp, const char *key,
                                float val) {
    const char *s = key_suffix(key);
    if (!strcmp(s, "rope.freq_base"))                     hp->rope_theta   = val;
    else if (!strcmp(s, "attention.layer_norm_rms_epsilon")) hp->rms_norm_eps = val;
}

/* Read one metadata KV pair; extract known hparams, skip unknown. */
static int read_kv(FILE *f, gguf_hparams_t *hp) {
    char key[GGUF_MAX_NAME_LEN];
    if (read_str(f, key, sizeof(key))) return -1;

    uint32_t vtype;
    if (read_u32(f, &vtype)) return -1;

    /* Extract values we care about; skip the rest. */
    switch (vtype) {
        case GGUF_TYPE_UINT32: {
            uint32_t v;
            if (read_u32(f, &v)) return -1;
            extract_hparam_u32(hp, key, v);
            break;
        }
        case GGUF_TYPE_INT32: {
            int32_t v;
            if (read_i32(f, &v)) return -1;
            if (v > 0) extract_hparam_u32(hp, key, (uint32_t)v);
            break;
        }
        case GGUF_TYPE_UINT64: {
            uint64_t v;
            if (read_u64(f, &v)) return -1;
            if (v <= 0xFFFFFFFFu) extract_hparam_u32(hp, key, (uint32_t)v);
            break;
        }
        case GGUF_TYPE_FLOAT32: {
            float v;
            if (read_f32(f, &v)) return -1;
            extract_hparam_f32(hp, key, v);
            break;
        }
        case GGUF_TYPE_ARRAY: {
            uint32_t elem_type; uint64_t count;
            if (read_u32(f, &elem_type)) return -1;
            if (read_u64(f, &count))     return -1;
            /* Extract vocab count from tokenizer token array */
            if (!strcmp(key, "tokenizer.ggml.tokens") &&
                elem_type == GGUF_TYPE_STRING) {
                hp->n_vocab = (uint32_t)count;
            }
            for (uint64_t i = 0; i < count; i++)
                if (skip_value(f, elem_type)) return -1;
            break;
        }
        default:
            if (skip_value(f, vtype)) return -1;
            break;
    }
    return 0;
}

/* ---- tensor size calculation ---- */

static size_t tensor_type_block_size(uint32_t type) {
    switch (type) {
        case GGUF_TENSOR_F32:  return 4;
        case GGUF_TENSOR_F16:  return 2;
        case GGUF_TENSOR_Q4_0: return 18;  /* 2 bytes fp16 + 16 bytes qs */
        case GGUF_TENSOR_Q4_1: return 20;
        case GGUF_TENSOR_Q8_0: return 34;
        default:               return 0;
    }
}

static size_t tensor_type_block_elements(uint32_t type) {
    switch (type) {
        case GGUF_TENSOR_F32:
        case GGUF_TENSOR_F16:  return 1;
        case GGUF_TENSOR_Q4_0:
        case GGUF_TENSOR_Q4_1: return 32;
        case GGUF_TENSOR_Q8_0: return 32;
        default:               return 0;
    }
}

static size_t tensor_n_bytes(const gguf_tensor_info_t *ti) {
    uint64_t n_elem = 1;
    for (uint32_t d = 0; d < ti->n_dims; d++) n_elem *= ti->dims[d];
    size_t blk_size  = tensor_type_block_size(ti->type);
    size_t blk_elems = tensor_type_block_elements(ti->type);
    if (!blk_size || !blk_elems) return 0;
    return (size_t)((n_elem + blk_elems - 1) / blk_elems) * blk_size;
}

/* ---- public API ---- */

int gguf_open(gguf_ctx_t *ctx, const char *path) {
    memset(ctx, 0, sizeof(*ctx));

    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); return -1; }
    ctx->file = f;

    /* Header */
    uint32_t magic;
    if (read_u32(f, &magic) || magic != GGUF_MAGIC) {
        fprintf(stderr, "gguf: bad magic %08x\n", magic);
        return -1;
    }
    uint32_t version;
    if (read_u32(f, &version) || version < 2) {
        fprintf(stderr, "gguf: unsupported version %u\n", version);
        return -1;
    }
    if (read_u64(f, &ctx->n_tensors)) return -1;
    if (read_u64(f, &ctx->n_kv))     return -1;

    if (ctx->n_tensors > GGUF_MAX_TENSORS) {
        fprintf(stderr, "gguf: too many tensors (%llu)\n",
                (unsigned long long)ctx->n_tensors);
        return -1;
    }

    /* Defaults */
    ctx->hparams.rope_theta    = 10000.0f;
    ctx->hparams.rms_norm_eps  = 1e-5f;
    ctx->hparams.max_seq_len   = 8192;

    /* Metadata KV pairs */
    for (uint64_t i = 0; i < ctx->n_kv; i++) {
        if (read_kv(f, &ctx->hparams)) {
            fprintf(stderr, "gguf: error parsing KV %llu\n",
                    (unsigned long long)i);
            return -1;
        }
    }

    /* Tensor info */
    for (uint64_t i = 0; i < ctx->n_tensors; i++) {
        gguf_tensor_info_t *ti = &ctx->tensors[i];
        if (read_str(f, ti->name, sizeof(ti->name))) return -1;
        if (read_u32(f, &ti->n_dims)) return -1;
        if (ti->n_dims > GGUF_MAX_DIMS) return -1;
        for (uint32_t d = 0; d < ti->n_dims; d++)
            if (read_u64(f, &ti->dims[d])) return -1;
        if (read_u32(f, &ti->type))   return -1;
        if (read_u64(f, &ti->offset)) return -1;
        ti->n_bytes = tensor_n_bytes(ti);
    }

    /* Tensor data starts after alignment padding (GGUF v3: 32-byte aligned). */
    long pos = ftell(f);
    if (pos < 0) return -1;
    long aligned = ((pos + 31) / 32) * 32;
    ctx->tensor_data_offset = (uint64_t)aligned;

    return 0;
}

const gguf_tensor_info_t *gguf_find_tensor(const gguf_ctx_t *ctx,
                                           const char *name) {
    for (uint64_t i = 0; i < ctx->n_tensors; i++)
        if (!strcmp(ctx->tensors[i].name, name))
            return &ctx->tensors[i];
    return NULL;
}

int64_t gguf_load_tensor(gguf_ctx_t *ctx, const gguf_tensor_info_t *ti,
                         void *buf, size_t buf_bytes) {
    FILE *f = (FILE *)ctx->file;
    if (!f) return -1;
    long off = (long)(ctx->tensor_data_offset + ti->offset);
    if (fseek(f, off, SEEK_SET)) return -1;
    /* Read min(buf_bytes, ti->n_bytes) — caller may request a partial read. */
    size_t to_read = buf_bytes < ti->n_bytes ? buf_bytes : ti->n_bytes;
    size_t n = fread(buf, 1, to_read, f);
    return (int64_t)n;
}

void gguf_close(gguf_ctx_t *ctx) {
    if (ctx->file) { fclose((FILE *)ctx->file); ctx->file = NULL; }
}

void gguf_dump(const gguf_ctx_t *ctx) {
    printf("GGUF: %llu tensors, %llu KV pairs\n",
           (unsigned long long)ctx->n_tensors,
           (unsigned long long)ctx->n_kv);
    printf("  n_layers=%u hidden=%u heads=%u kv_heads=%u ffn=%u vocab=%u\n",
           ctx->hparams.n_layers, ctx->hparams.hidden_dim,
           ctx->hparams.n_heads, ctx->hparams.n_kv_heads,
           ctx->hparams.ffn_dim, ctx->hparams.n_vocab);
    printf("  rope_theta=%.0f rms_eps=%g max_seq=%u\n",
           ctx->hparams.rope_theta, ctx->hparams.rms_norm_eps,
           ctx->hparams.max_seq_len);
    printf("  tensor_data_offset=%llu\n",
           (unsigned long long)ctx->tensor_data_offset);
    for (uint64_t i = 0; i < ctx->n_tensors && i < 16; i++) {
        const gguf_tensor_info_t *ti = &ctx->tensors[i];
        printf("  [%3llu] %-48s type=%u dims=",
               (unsigned long long)i, ti->name, ti->type);
        for (uint32_t d = 0; d < ti->n_dims; d++)
            printf("%llu%s", (unsigned long long)ti->dims[d],
                   d+1 < ti->n_dims ? "×" : "");
        printf(" (%zu B)\n", ti->n_bytes);
    }
    if (ctx->n_tensors > 16)
        printf("  ... and %llu more tensors\n",
               (unsigned long long)(ctx->n_tensors - 16));
}
