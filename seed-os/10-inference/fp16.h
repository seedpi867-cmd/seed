/*
 * fp16.h — IEEE 754 half-precision to single-precision conversion.
 * No hardware fp16 required; pure bit manipulation.
 * Used by Q4_0 dequantization (each block stores a fp16 scale).
 */
#ifndef FP16_H
#define FP16_H

#include <stdint.h>

static inline float fp16_to_f32(uint16_t h) {
    uint32_t sign     = (h >> 15) & 1;
    uint32_t exponent = (h >> 10) & 0x1F;
    uint32_t mantissa =  h        & 0x3FF;

    uint32_t f;
    if (exponent == 0) {
        if (mantissa == 0) {
            /* zero */
            f = sign << 31;
        } else {
            /* subnormal → normalise */
            exponent = 1;
            while (!(mantissa & 0x400)) { mantissa <<= 1; exponent--; }
            mantissa &= 0x3FF;
            f = (sign << 31) | ((exponent + 127 - 15) << 23) | (mantissa << 13);
        }
    } else if (exponent == 31) {
        /* inf or NaN */
        f = (sign << 31) | (0xFF << 23) | (mantissa << 13);
    } else {
        f = (sign << 31) | ((exponent + 127 - 15) << 23) | (mantissa << 13);
    }

    float result;
    __builtin_memcpy(&result, &f, 4);
    return result;
}

static inline uint16_t f32_to_fp16(float v) {
    uint32_t f;
    __builtin_memcpy(&f, &v, 4);
    uint32_t sign     = (f >> 31) & 1;
    int32_t  exponent = ((f >> 23) & 0xFF) - 127 + 15;
    uint32_t mantissa = (f >> 13) & 0x3FF;
    if (exponent <= 0)  return (uint16_t)(sign << 15);
    if (exponent >= 31) return (uint16_t)((sign << 15) | (31 << 10));
    return (uint16_t)((sign << 15) | (exponent << 10) | mantissa);
}

#endif /* FP16_H */
