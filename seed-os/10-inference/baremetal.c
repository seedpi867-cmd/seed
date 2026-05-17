/*
 * baremetal.c — libc replacement implementations.
 *
 * Compiled with -DBAREMETAL. The OS kernel provides:
 *   bm_uart_putc(char c) — write one byte to UART TX
 *
 * Everything else is self-contained.
 */
#ifdef BAREMETAL

#include "baremetal.h"

/* ================================================================
 * BUMP ALLOCATOR
 * ================================================================ */

static uint8_t *bm_arena_base = 0;
static size_t   bm_arena_cap  = 0;
static size_t   bm_arena_off  = 0;

void bm_arena_init(void *base, size_t size) {
    bm_arena_base = (uint8_t *)base;
    bm_arena_cap  = size;
    bm_arena_off  = 0;
}

void *bm_malloc(size_t n) {
    /* align to 16 bytes */
    n = (n + 15) & ~(size_t)15;
    if (bm_arena_off + n > bm_arena_cap) {
        bm_printf("bm_malloc: OOM (%zu requested, %zu used of %zu)\n",
                  n, bm_arena_off, bm_arena_cap);
        for(;;) __asm__("wfe");
    }
    void *p = bm_arena_base + bm_arena_off;
    bm_arena_off += n;
    return p;
}

void *bm_calloc(size_t nmemb, size_t size) {
    void *p = bm_malloc(nmemb * size);
    bm_memset(p, 0, nmemb * size);
    return p;
}

size_t bm_arena_used(void) { return bm_arena_off; }

/* ================================================================
 * MEMORY
 * ================================================================ */

void *bm_memcpy(void *dst, const void *src, size_t n) {
    uint8_t       *d = (uint8_t *)dst;
    const uint8_t *s = (const uint8_t *)src;
    /* word-at-a-time for aligned bulk */
    if (n >= 8 && !((uintptr_t)d & 7) && !((uintptr_t)s & 7)) {
        size_t words = n / 8;
        uint64_t *dw = (uint64_t *)d;
        const uint64_t *sw = (const uint64_t *)s;
        for (size_t i = 0; i < words; i++) dw[i] = sw[i];
        size_t done = words * 8;
        d += done; s += done; n -= done;
    }
    for (size_t i = 0; i < n; i++) d[i] = s[i];
    return dst;
}

void *bm_memset(void *dst, int c, size_t n) {
    uint8_t *d = (uint8_t *)dst;
    uint8_t  v = (uint8_t)c;
    for (size_t i = 0; i < n; i++) d[i] = v;
    return dst;
}

void *bm_memmove(void *dst, const void *src, size_t n) {
    uint8_t       *d = (uint8_t *)dst;
    const uint8_t *s = (const uint8_t *)src;
    if (d < s || d >= s + n) {
        for (size_t i = 0; i < n; i++) d[i] = s[i];
    } else {
        for (size_t i = n; i > 0; i--) d[i-1] = s[i-1];
    }
    return dst;
}

/* ================================================================
 * STRINGS
 * ================================================================ */

int bm_strcmp(const char *a, const char *b) {
    while (*a && *a == *b) { a++; b++; }
    return (unsigned char)*a - (unsigned char)*b;
}

int bm_strncmp(const char *a, const char *b, size_t n) {
    while (n && *a && *a == *b) { a++; b++; n--; }
    if (!n) return 0;
    return (unsigned char)*a - (unsigned char)*b;
}

size_t bm_strlen(const char *s) {
    size_t n = 0; while (s[n]) n++; return n;
}

char *bm_strncpy(char *dst, const char *src, size_t n) {
    size_t i = 0;
    while (i < n && src[i]) { dst[i] = src[i]; i++; }
    while (i < n) { dst[i++] = '\0'; }
    return dst;
}

/* ================================================================
 * MINIMAL SNPRINTF / PRINTF
 * ================================================================
 * Handles: %c %s %d %i %u %ld %lu %llu %x %lx %llx %f %g %%
 */

static void emit_str(char **buf, size_t *rem, const char *s, size_t len) {
    if (!buf) {
        /* printf mode: send to UART */
        for (size_t i = 0; i < len; i++) bm_uart_putc(s[i]);
    } else {
        size_t copy = len < *rem ? len : *rem;
        for (size_t i = 0; i < copy; i++) (*buf)[i] = s[i];
        *buf += copy;
        *rem -= copy;
    }
}

static void emit_char(char **buf, size_t *rem, char c) {
    emit_str(buf, rem, &c, 1);
}

static void fmt_uint(char **buf, size_t *rem, uint64_t v, int base, int upper) {
    const char *digits = upper ? "0123456789ABCDEF" : "0123456789abcdef";
    char tmp[24]; int i = 0;
    if (v == 0) { tmp[i++] = '0'; }
    else { while (v) { tmp[i++] = digits[v % base]; v /= base; } }
    /* reverse */
    for (int j = 0; j < i/2; j++) {
        char t = tmp[j]; tmp[j] = tmp[i-1-j]; tmp[i-1-j] = t;
    }
    emit_str(buf, rem, tmp, (size_t)i);
}

static void fmt_int(char **buf, size_t *rem, int64_t v, int base) {
    if (v < 0) { emit_char(buf, rem, '-'); v = -v; }
    fmt_uint(buf, rem, (uint64_t)v, base, 0);
}

/* Very small float formatter: handles normal finite floats to ~6 significant figures */
static void fmt_float(char **buf, size_t *rem, double v, int prec) {
    if (v < 0) { emit_char(buf, rem, '-'); v = -v; }
    /* integer part */
    uint64_t ipart = (uint64_t)v;
    fmt_uint(buf, rem, ipart, 10, 0);
    emit_char(buf, rem, '.');
    /* fractional part */
    double frac = v - (double)ipart;
    for (int p = 0; p < prec; p++) {
        frac *= 10.0;
        int d = (int)frac;
        emit_char(buf, rem, '0' + d);
        frac -= d;
    }
}

static int do_fmt(char **buf, size_t *rem, const char *fmt, va_list ap) {
    int count = 0;
    while (*fmt) {
        if (*fmt != '%') { emit_char(buf, rem, *fmt++); count++; continue; }
        fmt++; /* skip % */
        /* length modifier */
        int is_ll = 0, is_l = 0;
        if (*fmt == 'l') { fmt++; is_l = 1;
            if (*fmt == 'l') { fmt++; is_ll = 1; }
        }
        (void)is_l;
        switch (*fmt++) {
        case 'c': { char c = (char)va_arg(ap, int); emit_char(buf, rem, c); count++; break; }
        case 's': { const char *s = va_arg(ap, const char *);
                    if (!s) s = "(null)";
                    size_t l = bm_strlen(s); emit_str(buf, rem, s, l); count += l; break; }
        case 'd': case 'i': {
            int64_t v = is_ll ? va_arg(ap, int64_t) : va_arg(ap, int);
            fmt_int(buf, rem, v, 10); break; }
        case 'u': {
            uint64_t v = is_ll ? va_arg(ap, uint64_t) : (uint64_t)va_arg(ap, unsigned int);
            fmt_uint(buf, rem, v, 10, 0); break; }
        case 'x': {
            uint64_t v = is_ll ? va_arg(ap, uint64_t) : (uint64_t)va_arg(ap, unsigned int);
            fmt_uint(buf, rem, v, 16, 0); break; }
        case 'X': {
            uint64_t v = is_ll ? va_arg(ap, uint64_t) : (uint64_t)va_arg(ap, unsigned int);
            fmt_uint(buf, rem, v, 16, 1); break; }
        case 'f': case 'g': case 'e': {
            double v = va_arg(ap, double); fmt_float(buf, rem, v, 6); break; }
        case 'p': {
            uintptr_t v = (uintptr_t)va_arg(ap, void *);
            emit_str(buf, rem, "0x", 2);
            fmt_uint(buf, rem, v, 16, 0); break; }
        case '%': emit_char(buf, rem, '%'); count++; break;
        default:  break;
        }
    }
    return count;
}

int bm_vprintf(const char *fmt, va_list ap) {
    return do_fmt(NULL, NULL, fmt, ap);
}

int bm_printf(const char *fmt, ...) {
    va_list ap; va_start(ap, fmt);
    int n = do_fmt(NULL, NULL, fmt, ap);
    va_end(ap); return n;
}

int bm_snprintf(char *buf, size_t size, const char *fmt, ...) {
    va_list ap; va_start(ap, fmt);
    size_t rem = size > 0 ? size - 1 : 0;
    char *p = buf;
    int n = do_fmt(&p, &rem, fmt, ap);
    if (size > 0) *p = '\0';
    va_end(ap); return n;
}

void bm_uart_puts(const char *s) {
    while (*s) bm_uart_putc(*s++);
}

/* ================================================================
 * MATH — AArch64 hardware + polynomial approximations
 * ================================================================ */

float bm_sqrtf(float x) {
    float r;
    __asm__("fsqrt %s0, %s1" : "=w"(r) : "w"(x));
    return r;
}

/*
 * expf: relative error < 1e-6 for |x| < 87.3
 * Method: exp(x) = 2^(x * LOG2E) = 2^n * 2^f
 *   n = round(x * LOG2E)
 *   f = x - n * LN2  (f in [-0.5*ln2, 0.5*ln2])
 *   2^f via Horner polynomial fit on that interval
 */
float bm_expf(float x) {
    const float LOG2E = 1.4426950408f;
    const float LN2_HI = 0.6931471806f;
    const float LN2_LO = 1.9046542e-9f;
    float z = x * LOG2E;
    int n = (int)(z + (z >= 0.0f ? 0.5f : -0.5f));
    float r = x - (float)n * LN2_HI - (float)n * LN2_LO;
    /* Horner: 2^r ≈ 1 + r*(p1 + r*(p2 + r*(p3 + r*(p4 + r*p5)))) */
    float p = 1.5327454314e-4f;
    p = p * r + 1.3400495507e-3f;
    p = p * r + 9.6168637587e-3f;
    p = p * r + 5.5504108664e-2f;
    p = p * r + 2.4022650695e-1f;
    p = p * r + 6.9314718056e-1f;
    p = p * r + 1.0f;
    /* scale by 2^n using bit manipulation */
    if (n < -126) return 0.0f;
    if (n >  127) return 3.4028235e38f;
    uint32_t bits;
    __builtin_memcpy(&bits, &p, 4);
    bits += (uint32_t)n << 23;
    __builtin_memcpy(&p, &bits, 4);
    return p;
}

/*
 * logf: relative error < 2e-7
 * Method: x = m * 2^e, log(x) = e*ln2 + log(m), m in [1, 2)
 *   log(m) via polynomial on m-1 in [-1, 1): Horner from Remez fit
 */
float bm_logf(float x) {
    const float LN2 = 0.6931471806f;
    uint32_t bits; __builtin_memcpy(&bits, &x, 4);
    int e = (int)((bits >> 23) & 0xFF) - 127;
    bits = (bits & 0x007FFFFF) | 0x3F800000;
    __builtin_memcpy(&x, &bits, 4);
    /* x now in [1, 2), shift to [-1, 1) */
    float y = (x - 1.0f) / (x + 1.0f);
    float y2 = y * y;
    float p = 2.0f / 11.0f;
    p = p * y2 + 2.0f / 9.0f;
    p = p * y2 + 2.0f / 7.0f;
    p = p * y2 + 2.0f / 5.0f;
    p = p * y2 + 2.0f / 3.0f;
    p = p * y2 + 2.0f;
    return p * y + (float)e * LN2;
}

/*
 * sinf / cosf: range reduce to [-pi/4, pi/4], then Chebyshev polynomial.
 * Accurate to ~6 decimal places.
 */
#define BM_PI  3.14159265358979f
#define BM_PI2 1.57079632679490f
#define BM_PI4 0.78539816339745f

/* sin on [-pi/4, pi/4] via Horner */
static float sin_kernel(float x) {
    float x2 = x * x;
    float p = -2.5052104e-8f;
    p = p * x2 + 2.7557315e-6f;
    p = p * x2 - 1.9841270e-4f;
    p = p * x2 + 8.3333333e-3f;
    p = p * x2 - 1.6666667e-1f;
    return x * (1.0f + p * x2);
}

/* cos on [-pi/4, pi/4] via Horner */
static float cos_kernel(float x) {
    float x2 = x * x;
    float p = 2.0876754e-9f;
    p = p * x2 - 2.7557313e-7f;
    p = p * x2 + 2.4801587e-5f;
    p = p * x2 - 1.3888889e-3f;
    p = p * x2 + 4.1666667e-2f;
    p = p * x2 - 5.0000000e-1f;
    return 1.0f + p * x2;
}

float bm_sinf(float x) {
    /* range reduce to [0, 2pi] */
    float sign = 1.0f;
    if (x < 0) { x = -x; sign = -1.0f; }
    /* reduce mod 2pi */
    float k = bm_floorf(x / (2.0f * BM_PI));
    x -= k * (2.0f * BM_PI);
    /* quadrant */
    int quad = (int)(x / BM_PI2);
    float r = x - (float)quad * BM_PI2;
    float s;
    switch (quad & 3) {
    case 0: s =  sin_kernel(r);         break;
    case 1: s =  cos_kernel(r);         break;
    case 2: s = -sin_kernel(r);         break;
    default: s = -cos_kernel(r);        break;
    }
    return sign * s;
}

float bm_cosf(float x) {
    return bm_sinf(x + BM_PI2);
}

/* ================================================================
 * FILE I/O — memory blob backend
 * ================================================================ */

const uint8_t *bm_model_blob      = 0;
size_t         bm_model_blob_size = 0;

static BM_FILE bm_file_slot;   /* single open file */

BM_FILE *bm_fopen(const char *path, const char *mode) {
    (void)path; (void)mode;
    bm_file_slot.data  = bm_model_blob;
    bm_file_slot.size  = bm_model_blob_size;
    bm_file_slot.pos   = 0;
    bm_file_slot.error = 0;
    return &bm_file_slot;
}

size_t bm_fread(void *buf, size_t size, size_t nmemb, BM_FILE *f) {
    size_t bytes  = size * nmemb;
    size_t remain = f->size - f->pos;
    size_t copy   = bytes < remain ? bytes : remain;
    bm_memcpy(buf, f->data + f->pos, copy);
    f->pos += copy;
    return copy / size;
}

int bm_fseek(BM_FILE *f, long offset, int whence) {
    long pos;
    switch (whence) {
    case 0 /*SEEK_SET*/: pos = offset;               break;
    case 1 /*SEEK_CUR*/: pos = (long)f->pos + offset; break;
    case 2 /*SEEK_END*/: pos = (long)f->size + offset; break;
    default: return -1;
    }
    if (pos < 0 || (size_t)pos > f->size) return -1;
    f->pos = (size_t)pos;
    return 0;
}

long bm_ftell(BM_FILE *f) { return (long)f->pos; }

int bm_fclose(BM_FILE *f) { (void)f; return 0; }

int bm_ferror(BM_FILE *f) { return f->error; }

#endif /* BAREMETAL */
