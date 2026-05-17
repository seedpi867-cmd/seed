/*
 * q4_matmul.c — Q4_0 matrix-vector multiply, reference implementation.
 *
 * Phase 1: plain C, libc allowed.
 * Phase 3: replace inner loop with NEON intrinsics.
 */
#include "q4.h"

void q4_matmul(const q4_block_t *W, const float *x, float *y,
               int rows, int cols) {
    int blocks_per_row = cols / Q4_BLOCK_SIZE;
    for (int r = 0; r < rows; r++) {
        float acc = 0.0f;
        const q4_block_t *row_blocks = W + (size_t)r * blocks_per_row;
        for (int b = 0; b < blocks_per_row; b++) {
            acc += q4_block_dot(&row_blocks[b], x + (size_t)b * Q4_BLOCK_SIZE);
        }
        y[r] = acc;
    }
}
