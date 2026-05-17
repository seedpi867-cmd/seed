/*
 * q4.h — Q4_0 quantization types and operations.
 *
 * Q4_0 block layout (18 bytes for 32 elements):
 *   d:   fp16 scale           (2 bytes)
 *   qs:  uint8[16]            (16 bytes, 32 nibbles packed)
 *
 * For nibble index i (0..31):
 *   byte    = qs[i / 2]
 *   nibble  = (i & 1) ? (byte >> 4) : (byte & 0x0F)
 *   weight  = (float)(nibble - 8) * fp16_to_f32(d)
 */
#ifndef Q4_H
#define Q4_H

#include <stdint.h>
#include <stddef.h>
#include "fp16.h"

#define Q4_BLOCK_SIZE 32  /* elements per block */

typedef struct {
    uint16_t d;       /* fp16 scale */
    uint8_t  qs[16];  /* packed nibbles */
} __attribute__((packed)) q4_block_t;

/*
 * Dot product of one Q4_0 block (32 elements) with fp32 input vector x.
 *
 * Packing (matches llama.cpp / GGUF spec):
 *   qs[j] low  nibble → element j      (j = 0..15)
 *   qs[j] high nibble → element j + 16 (j = 0..15)
 */
static inline float q4_block_dot(const q4_block_t *b, const float *x) {
    float scale = fp16_to_f32(b->d);
    float acc   = 0.0f;
    for (int j = 0; j < 16; j++) {
        uint8_t byte = b->qs[j];
        int lo = (int)(byte & 0x0F) - 8;   /* element j */
        int hi = (int)(byte >> 4)   - 8;   /* element j+16 */
        acc += (float)lo * x[j     ];
        acc += (float)hi * x[j + 16];
    }
    return acc * scale;
}

/*
 * Matrix-vector multiply: y[rows] = W[rows × cols] × x[cols]
 * W is stored row-major in Q4_0 blocks.
 * cols must be a multiple of Q4_BLOCK_SIZE.
 */
void q4_matmul(const q4_block_t *W, const float *x, float *y,
               int rows, int cols);

/*
 * Dequantize a Q4_0 block into 32 fp32 values at out[0..31].
 * Packing: qs[j] low nibble → element j, high nibble → element j+16.
 */
static inline void q4_block_dequant(const q4_block_t *b, float *out) {
    float scale = fp16_to_f32(b->d);
    for (int j = 0; j < 16; j++) {
        uint8_t byte = b->qs[j];
        out[j     ] = (float)((int)(byte & 0x0F) - 8) * scale;
        out[j + 16] = (float)((int)(byte >> 4)   - 8) * scale;
    }
}

/*
 * Quantize 32 fp32 values into one Q4_0 block.
 *
 * Scale: d = max_signed / -8  (llama.cpp convention).
 * This maps the value with largest absolute magnitude to nibble 0,
 * giving finer resolution on the dominant-sign side of the range.
 * Packing: element j → qs[j] low nibble, element j+16 → qs[j] high nibble.
 */
static inline void q4_block_quant(const float *src, q4_block_t *b) {
    float amax = 0.0f, max_signed = 0.0f;
    for (int i = 0; i < 32; i++) {
        float a = src[i] < 0.0f ? -src[i] : src[i];
        if (a > amax) { amax = a; max_signed = src[i]; }
    }
    float d = max_signed / -8.0f;
    b->d = f32_to_fp16(d);
    float inv_d = (d != 0.0f) ? (1.0f / d) : 0.0f;
    for (int j = 0; j < 16; j++) {
        int lo = (int)(src[j     ] * inv_d + 8.5f);
        int hi = (int)(src[j + 16] * inv_d + 8.5f);
        if (lo < 0)  lo = 0;
        if (lo > 15) lo = 15;
        if (hi < 0)  hi = 0;
        if (hi > 15) hi = 15;
        b->qs[j] = (uint8_t)(lo | (hi << 4));
    }
}

#endif /* Q4_H */
