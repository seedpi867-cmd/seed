/*
 * ops_q8.h — Q8_0 and Q4_1 tensor operations.
 *
 * Q8_0 block (34 bytes for 32 elements):
 *   d:  fp16 scale (2 bytes)
 *   qs: int8[32] (32 bytes)
 *   element_i = qs[i] * fp16_to_f32(d)
 *
 * Q4_1 block (20 bytes for 32 elements):
 *   d:  fp16 scale (2 bytes)
 *   m:  fp16 min   (2 bytes)
 *   qs: uint8[16] packed nibbles (16 bytes)
 *   element_i = nibble_i * d + m
 */
#ifndef OPS_Q8_H
#define OPS_Q8_H

#include <stdint.h>
#include <stddef.h>
#include "fp16.h"
#include "q4.h"
#include "gguf.h"

/* ---- Q8_0 ---- */

typedef struct {
    uint16_t d;
    int8_t   qs[32];
} __attribute__((packed)) q8_block_t;

#define Q8_BLOCK_SIZE 32

static inline float q8_block_dot(const q8_block_t *b, const float *x) {
    float scale = fp16_to_f32(b->d);
    float acc   = 0.0f;
    for (int i = 0; i < 32; i++)
        acc += (float)b->qs[i] * x[i];
    return acc * scale;
}

static inline void q8_matmul(const q8_block_t *W, const float *x, float *y,
                              int rows, int cols) {
    int bpr = cols / Q8_BLOCK_SIZE;
    for (int r = 0; r < rows; r++) {
        float acc = 0.0f;
        const q8_block_t *rw = W + (size_t)r * bpr;
        for (int b = 0; b < bpr; b++)
            acc += q8_block_dot(&rw[b], x + (size_t)b * Q8_BLOCK_SIZE);
        y[r] = acc;
    }
}

/* Dequantize row token_id of Q8_0 embedding table [n_vocab × hidden] */
static inline void q8_embed(const q8_block_t *W, int token_id, float *out, int hidden) {
    int bpr = hidden / Q8_BLOCK_SIZE;
    const q8_block_t *row = W + (size_t)token_id * bpr;
    for (int b = 0; b < bpr; b++) {
        float scale = fp16_to_f32(row[b].d);
        for (int i = 0; i < Q8_BLOCK_SIZE; i++)
            out[b * Q8_BLOCK_SIZE + i] = (float)row[b].qs[i] * scale;
    }
}

/* ---- Q4_1 ---- */

typedef struct {
    uint16_t d;
    uint16_t m;
    uint8_t  qs[16];
} __attribute__((packed)) q4_1_block_t;

#define Q4_1_BLOCK_SIZE 32

static inline float q4_1_block_dot(const q4_1_block_t *b, const float *x) {
    float scale = fp16_to_f32(b->d);
    float min_v = fp16_to_f32(b->m);
    float acc   = 0.0f;
    float sum_x = 0.0f;
    for (int j = 0; j < 16; j++) {
        uint8_t byte = b->qs[j];
        int lo = byte & 0x0F;
        int hi = byte >> 4;
        acc   += (float)lo * x[j] + (float)hi * x[j + 16];
        sum_x += x[j] + x[j + 16];
    }
    return acc * scale + sum_x * min_v;
}

static inline void q4_1_matmul(const q4_1_block_t *W, const float *x, float *y,
                                int rows, int cols) {
    int bpr = cols / Q4_1_BLOCK_SIZE;
    for (int r = 0; r < rows; r++) {
        float acc = 0.0f;
        const q4_1_block_t *rw = W + (size_t)r * bpr;
        for (int b = 0; b < bpr; b++)
            acc += q4_1_block_dot(&rw[b], x + (size_t)b * Q4_1_BLOCK_SIZE);
        y[r] = acc;
    }
}

/* ---- generic dispatch ---- */

/*
 * tensor_matmul — dispatch matmul by tensor type.
 * W: raw tensor data. type: GGUF_TENSOR_*.
 * y[rows] = W[rows × cols] × x[cols]
 */
static inline void tensor_matmul(const void *W, uint32_t type,
                                  const float *x, float *y, int rows, int cols) {
    switch (type) {
        case GGUF_TENSOR_Q4_0:
            q4_matmul((const q4_block_t *)W, x, y, rows, cols);
            break;
        case GGUF_TENSOR_Q4_1:
            q4_1_matmul((const q4_1_block_t *)W, x, y, rows, cols);
            break;
        case GGUF_TENSOR_Q8_0:
            q8_matmul((const q8_block_t *)W, x, y, rows, cols);
            break;
        case GGUF_TENSOR_F32: {
            const float *Wf = (const float *)W;
            for (int r = 0; r < rows; r++) {
                float acc = 0.0f;
                for (int c = 0; c < cols; c++) acc += Wf[(size_t)r*cols+c] * x[c];
                y[r] = acc;
            }
            break;
        }
        default:
            for (int r = 0; r < rows; r++) y[r] = 0.0f;
            break;
    }
}

/*
 * tensor_embed — dequantize row token_id from embedding table.
 */
static inline void tensor_embed(const void *W, uint32_t type,
                                 int token_id, float *out, int hidden) {
    switch (type) {
        case GGUF_TENSOR_Q8_0:
            q8_embed((const q8_block_t *)W, token_id, out, hidden);
            break;
        case GGUF_TENSOR_Q4_0: {
            int bpr = hidden / 32;
            const q4_block_t *row = (const q4_block_t *)W + (size_t)token_id * bpr;
            for (int b = 0; b < bpr; b++) q4_block_dequant(&row[b], out + b*32);
            break;
        }
        case GGUF_TENSOR_F32: {
            const float *Wf = (const float *)W;
            for (int i = 0; i < hidden; i++) out[i] = Wf[(size_t)token_id*hidden+i];
            break;
        }
        case GGUF_TENSOR_F16: {
            const uint16_t *Wh = (const uint16_t *)W;
            for (int i = 0; i < hidden; i++)
                out[i] = fp16_to_f32(Wh[(size_t)token_id*hidden+i]);
            break;
        }
        default:
            for (int i = 0; i < hidden; i++) out[i] = 0.0f;
            break;
    }
}

#endif /* OPS_Q8_H */
