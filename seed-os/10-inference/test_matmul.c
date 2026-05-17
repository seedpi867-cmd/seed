/*
 * test_matmul.c — verifies Q4_0 quantize → dequantize round-trip and matmul.
 *
 * Tests:
 *   1. fp16 round-trip for known values
 *   2. Q4_0 block quant/dequant round-trip (checks precision loss)
 *   3. Q4_0 matmul against fp32 reference (3 cases)
 *   4. RMSNorm correctness
 *   5. Softmax sum-to-one
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "q4.h"
#include "ops.h"

static int failures = 0;

#define CHECK(cond, msg) do { \
    if (!(cond)) { fprintf(stderr, "FAIL: %s\n", msg); failures++; } \
    else          { printf("PASS: %s\n", msg); } \
} while(0)

#define NEAR(a, b, tol) (fabsf((a)-(b)) <= (tol))

/* ---- fp16 round-trip ---- */
static void test_fp16(void) {
    struct { float v; const char *name; } cases[] = {
        {0.0f,    "zero"},
        {1.0f,    "one"},
        {-1.0f,   "neg_one"},
        {0.5f,    "half"},
        {123.5f,  "123.5"},
        {-0.125f, "neg_0.125"},
    };
    for (size_t i = 0; i < sizeof(cases)/sizeof(cases[0]); i++) {
        float orig = cases[i].v;
        uint16_t h = f32_to_fp16(orig);
        float back = fp16_to_f32(h);
        char msg[64];
        snprintf(msg, sizeof(msg), "fp16 round-trip %s", cases[i].name);
        CHECK(NEAR(orig, back, fabsf(orig) * 0.002f + 1e-4f), msg);
    }
}

/* ---- Q4_0 block quant/dequant ---- */
static void test_q4_round_trip(void) {
    /* All weights = 1.0 */
    float src[32]; for (int i = 0; i < 32; i++) src[i] = 1.0f;
    q4_block_t b;
    q4_block_quant(src, &b);
    float out[32];
    q4_block_dequant(&b, out);
    int ok = 1;
    for (int i = 0; i < 32; i++) if (!NEAR(out[i], 1.0f, 0.3f)) ok = 0;
    CHECK(ok, "q4 round-trip: all-ones block");

    /* Alternating 1.0 / -1.0 */
    for (int i = 0; i < 32; i++) src[i] = (i & 1) ? -1.0f : 1.0f;
    q4_block_quant(src, &b);
    q4_block_dequant(&b, out);
    ok = 1;
    for (int i = 0; i < 32; i++) {
        float expected = (i & 1) ? -1.0f : 1.0f;
        if (!NEAR(out[i], expected, 0.3f)) ok = 0;
    }
    CHECK(ok, "q4 round-trip: alternating +-1 block");

    /* Linear ramp: absmax=4.0, Q4_0 step ≈ 4/8=0.5, max element error ≈ 0.25 */
    for (int i = 0; i < 32; i++) src[i] = (float)(i - 16) * 0.25f;
    q4_block_quant(src, &b);
    q4_block_dequant(&b, out);
    ok = 1;
    for (int i = 0; i < 32; i++)
        if (!NEAR(out[i], src[i], 0.4f)) ok = 0;  /* ≥ one Q4_0 step */
    CHECK(ok, "q4 round-trip: linear ramp block");
}

/* ---- matmul: Q4_0 vs fp32 reference ---- */
static float ref_dot(const float *w, const float *x, int n) {
    float acc = 0.0f;
    for (int i = 0; i < n; i++) acc += w[i] * x[i];
    return acc;
}

static void test_matmul(void) {
    /* Small matrix: 4 rows × 64 cols (2 blocks per row) */
    const int rows = 4, cols = 64;
    const int n_blocks = cols / Q4_BLOCK_SIZE;

    /* Generate fp32 weights */
    float W_f32[4 * 64];
    for (int i = 0; i < rows * cols; i++)
        W_f32[i] = (float)(i % 17 - 8) * 0.1f;

    /* Quantize to Q4_0 */
    q4_block_t W_q4[4 * 2];  /* 4 rows × 2 blocks */
    for (int r = 0; r < rows; r++)
        for (int b = 0; b < n_blocks; b++)
            q4_block_quant(&W_f32[r * cols + b * Q4_BLOCK_SIZE],
                           &W_q4[r * n_blocks + b]);

    /* Input vector: all 1.0 */
    float x[64]; for (int i = 0; i < 64; i++) x[i] = 1.0f;
    float y_q4[4], y_ref[4];
    q4_matmul(W_q4, x, y_q4, rows, cols);
    for (int r = 0; r < rows; r++)
        y_ref[r] = ref_dot(&W_f32[r * cols], x, cols);
    int ok = 1;
    /*
     * Q4_0 absolute error per block ≤ (absmax/8) * 0.5 * n_elems.
     * For 2 blocks, absmax≈0.8, n=32: error ≤ 2 * (0.8/8) * 0.5 * 32 = 3.2.
     * Use 30% relative + 0.5 absolute as practical bounds.
     */
    for (int r = 0; r < rows; r++)
        if (!NEAR(y_q4[r], y_ref[r], fabsf(y_ref[r]) * 0.30f + 0.5f)) ok = 0;
    CHECK(ok, "matmul: 4×64, x=all-ones vs fp32 ref");

    /* Input vector: alternating 0/1 */
    for (int i = 0; i < 64; i++) x[i] = (float)(i & 1);
    q4_matmul(W_q4, x, y_q4, rows, cols);
    for (int r = 0; r < rows; r++)
        y_ref[r] = ref_dot(&W_f32[r * cols], x, cols);
    ok = 1;
    for (int r = 0; r < rows; r++)
        if (!NEAR(y_q4[r], y_ref[r], fabsf(y_ref[r]) * 0.30f + 0.5f)) ok = 0;
    CHECK(ok, "matmul: 4×64, x=alternating vs fp32 ref");

    /* Larger: 32 rows × 128 cols */
    const int R2 = 32, C2 = 128, NB2 = C2 / Q4_BLOCK_SIZE;
    float *W2 = malloc(R2 * C2 * sizeof(float));
    q4_block_t *W2q = malloc(R2 * NB2 * sizeof(q4_block_t));
    float *x2 = malloc(C2 * sizeof(float));
    float *y2q = malloc(R2 * sizeof(float));
    float *y2r = malloc(R2 * sizeof(float));
    for (int i = 0; i < R2 * C2; i++)
        W2[i] = (float)(i % 23 - 11) * 0.05f;
    for (int r = 0; r < R2; r++)
        for (int b = 0; b < NB2; b++)
            q4_block_quant(&W2[r * C2 + b * Q4_BLOCK_SIZE],
                           &W2q[r * NB2 + b]);
    for (int i = 0; i < C2; i++) x2[i] = (float)(i % 7 - 3) * 0.1f;
    q4_matmul(W2q, x2, y2q, R2, C2);
    for (int r = 0; r < R2; r++) y2r[r] = ref_dot(&W2[r * C2], x2, C2);
    ok = 1;
    for (int r = 0; r < R2; r++)
        if (!NEAR(y2q[r], y2r[r], fabsf(y2r[r]) * 0.2f + 0.05f)) ok = 0;
    CHECK(ok, "matmul: 32×128, mixed input vs fp32 ref");
    free(W2); free(W2q); free(x2); free(y2q); free(y2r);
}

/* ---- RMSNorm ---- */
static void test_rmsnorm(void) {
    float x[8]   = {1, 2, 3, 4, -1, -2, -3, -4};
    float w[8];    for (int i = 0; i < 8; i++) w[i] = 1.0f;  /* identity weight */
    float out[8];
    rms_norm(x, w, out, 8, 1e-5f);

    /* Sum of squares of output should ≈ n (since rms_norm normalises by rms) */
    float ss = 0.0f;
    for (int i = 0; i < 8; i++) ss += out[i] * out[i];
    CHECK(NEAR(ss, 8.0f, 0.01f), "rmsnorm: sum-of-squares ≈ n");

    /* Ratio between adjacent elements should be preserved */
    CHECK(NEAR(out[1] / out[0], 2.0f, 0.01f), "rmsnorm: ratio preserved");
}

/* ---- Softmax ---- */
static void test_softmax(void) {
    float x[4] = {1.0f, 2.0f, 3.0f, 4.0f};
    softmax(x, 4);
    float sum = 0.0f;
    for (int i = 0; i < 4; i++) { sum += x[i]; CHECK(x[i] > 0.0f, "softmax: all positive"); }
    CHECK(NEAR(sum, 1.0f, 1e-5f), "softmax: sum to 1.0");
    /* Highest input → highest probability */
    CHECK(x[3] > x[2] && x[2] > x[1] && x[1] > x[0], "softmax: monotone");
}

int main(void) {
    printf("=== Inference Engine — Phase 1 Unit Tests ===\n\n");
    test_fp16();
    printf("\n");
    test_q4_round_trip();
    printf("\n");
    test_matmul();
    printf("\n");
    test_rmsnorm();
    printf("\n");
    test_softmax();
    printf("\n");
    if (failures == 0) {
        printf("ALL TESTS PASSED\n");
        return 0;
    } else {
        printf("%d TEST(S) FAILED\n", failures);
        return 1;
    }
}
