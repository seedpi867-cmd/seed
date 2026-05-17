/*
 * ops.h — scalar neural network ops: RMSNorm, SiLU, softmax, exp approx.
 */
#ifndef OPS_H
#define OPS_H

#include <math.h>
#include <stddef.h>

static inline void rms_norm(const float *x, const float *w, float *out,
                             int n, float eps) {
    float ss = 0.0f;
    for (int i = 0; i < n; i++) ss += x[i] * x[i];
    float rms_inv = 1.0f / sqrtf(ss / (float)n + eps);
    for (int i = 0; i < n; i++) out[i] = x[i] * rms_inv * w[i];
}

static inline float sigmoid(float x) {
    return 1.0f / (1.0f + expf(-x));
}

static inline void silu_elementwise(const float *gate, const float *up,
                                    float *out, int n) {
    for (int i = 0; i < n; i++)
        out[i] = gate[i] * sigmoid(gate[i]) * up[i];
}

static inline void softmax(float *x, int n) {
    float max_v = x[0];
    for (int i = 1; i < n; i++) if (x[i] > max_v) max_v = x[i];
    float sum = 0.0f;
    for (int i = 0; i < n; i++) { x[i] = expf(x[i] - max_v); sum += x[i]; }
    float inv_sum = 1.0f / sum;
    for (int i = 0; i < n; i++) x[i] *= inv_sum;
}

/* Element-wise add: out[i] += b[i] */
static inline void vec_add(float *out, const float *b, int n) {
    for (int i = 0; i < n; i++) out[i] += b[i];
}

#endif /* OPS_H */
