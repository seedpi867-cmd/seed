/*
 * gguf.h — GGUF v3 format types and loader interface.
 *
 * GGUF spec: https://github.com/ggerganov/ggml/blob/master/docs/gguf.md
 *
 * Phase 2 note: fread/malloc must be replaced with bare-metal SD reads
 * and a static bump allocator.
 */
#ifndef GGUF_H
#define GGUF_H

#include <stdint.h>
#include <stddef.h>

#define GGUF_MAGIC   0x46554747u  /* "GGUF" little-endian */
#define GGUF_VERSION 3

/* Metadata value types */
typedef enum {
    GGUF_TYPE_UINT8   = 0,
    GGUF_TYPE_INT8    = 1,
    GGUF_TYPE_UINT16  = 2,
    GGUF_TYPE_INT16   = 3,
    GGUF_TYPE_UINT32  = 4,
    GGUF_TYPE_INT32   = 5,
    GGUF_TYPE_FLOAT32 = 6,
    GGUF_TYPE_BOOL    = 7,
    GGUF_TYPE_STRING  = 8,
    GGUF_TYPE_ARRAY   = 9,
    GGUF_TYPE_UINT64  = 10,
    GGUF_TYPE_INT64   = 11,
    GGUF_TYPE_FLOAT64 = 12,
} gguf_value_type_t;

/* Tensor quantization types (subset we care about) */
typedef enum {
    GGUF_TENSOR_F32  = 0,
    GGUF_TENSOR_F16  = 1,
    GGUF_TENSOR_Q4_0 = 2,
    GGUF_TENSOR_Q4_1 = 3,
    GGUF_TENSOR_Q8_0 = 8,
} gguf_tensor_type_t;

#define GGUF_MAX_TENSORS  4096
#define GGUF_MAX_KV       512
#define GGUF_MAX_NAME_LEN 128
#define GGUF_MAX_DIMS     4

typedef struct {
    char     name[GGUF_MAX_NAME_LEN];
    uint32_t n_dims;
    uint64_t dims[GGUF_MAX_DIMS];
    uint32_t type;    /* gguf_tensor_type_t */
    uint64_t offset;  /* byte offset from start of tensor data region */
    size_t   n_bytes; /* total size of tensor data */
} gguf_tensor_info_t;

/* Parsed model hyperparameters extracted from metadata */
typedef struct {
    uint32_t n_layers;
    uint32_t hidden_dim;
    uint32_t n_heads;
    uint32_t n_kv_heads;
    uint32_t ffn_dim;
    uint32_t n_vocab;
    uint32_t max_seq_len;
    float    rope_theta;
    float    rms_norm_eps;
} gguf_hparams_t;

typedef struct {
    /* File descriptor / mapped region (Phase 1: FILE*, Phase 2: sector offset) */
    void   *file;

    uint64_t n_tensors;
    uint64_t n_kv;

    gguf_tensor_info_t tensors[GGUF_MAX_TENSORS];
    gguf_hparams_t     hparams;

    /* Byte offset in file where tensor data begins */
    uint64_t tensor_data_offset;
} gguf_ctx_t;

/*
 * Open and parse GGUF file headers.
 * Returns 0 on success, negative on error.
 * ctx->file remains open; call gguf_close() when done.
 */
int gguf_open(gguf_ctx_t *ctx, const char *path);

/*
 * Find tensor by name. Returns NULL if not found.
 */
const gguf_tensor_info_t *gguf_find_tensor(const gguf_ctx_t *ctx,
                                           const char *name);

/*
 * Load tensor data into a caller-supplied buffer.
 * Returns number of bytes read, or negative on error.
 */
int64_t gguf_load_tensor(gguf_ctx_t *ctx, const gguf_tensor_info_t *ti,
                         void *buf, size_t buf_bytes);

void gguf_close(gguf_ctx_t *ctx);

/* Print a summary of parsed tensors and hyperparameters */
void gguf_dump(const gguf_ctx_t *ctx);

#endif /* GGUF_H */
