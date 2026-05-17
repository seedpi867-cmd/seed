/*
 * baremetal.h — drop-in libc replacement for bare-metal compilation.
 *
 * Compile with -DBAREMETAL to activate. Every libc symbol the inference
 * engine uses is replaced here:
 *   malloc/free    → bump allocator from a fixed arena
 *   memcpy/memset  → simple loop implementations
 *   sqrtf          → AArch64 fsqrt hardware instruction
 *   expf/sinf/cosf → polynomial approximations
 *   printf/fprintf → UART write (bm_uart_putc must be provided by the OS)
 *   fopen/fread/…  → reads from a memory blob (embedded model or SD data ptr)
 *   strcmp/strlen  → simple loop implementations
 *   snprintf       → minimal formatter (%s %d %u %llu %f %x)
 */
#pragma once

#ifdef BAREMETAL

#include <stddef.h>
#include <stdint.h>
#include <stdarg.h>

/* ================================================================
 * BUMP ALLOCATOR
 * ================================================================ */

void  bm_arena_init(void *base, size_t size);
void *bm_malloc(size_t n);
void *bm_calloc(size_t nmemb, size_t size);
size_t bm_arena_used(void);

#define malloc(n)     bm_malloc(n)
#define calloc(n,s)   bm_calloc(n,s)
#define free(p)       ((void)(p))
#define realloc(p,n)  bm_malloc(n)   /* never called; just satisfies linker */

/* ================================================================
 * MEMORY
 * ================================================================ */

void *bm_memcpy(void *dst, const void *src, size_t n);
void *bm_memset(void *dst, int c, size_t n);
void *bm_memmove(void *dst, const void *src, size_t n);

#define memcpy(d,s,n)   bm_memcpy(d,s,n)
#define memset(d,c,n)   bm_memset(d,c,n)
#define memmove(d,s,n)  bm_memmove(d,s,n)

/* ================================================================
 * STRINGS
 * ================================================================ */

int    bm_strcmp(const char *a, const char *b);
int    bm_strncmp(const char *a, const char *b, size_t n);
size_t bm_strlen(const char *s);
char  *bm_strncpy(char *dst, const char *src, size_t n);
int    bm_snprintf(char *buf, size_t size, const char *fmt, ...);

#define strcmp(a,b)       bm_strcmp(a,b)
#define strncmp(a,b,n)    bm_strncmp(a,b,n)
#define strlen(s)         bm_strlen(s)
#define strncpy(d,s,n)    bm_strncpy(d,s,n)
#define snprintf          bm_snprintf
/* sprintf: not used; no definition to avoid conflicts */

/* ================================================================
 * MATH
 * ================================================================ */

float bm_sqrtf(float x);
float bm_expf(float x);
float bm_sinf(float x);
float bm_cosf(float x);
float bm_logf(float x);

static inline float bm_fabsf(float x) {
    uint32_t u; __builtin_memcpy(&u, &x, 4);
    u &= 0x7FFFFFFF;
    __builtin_memcpy(&x, &u, 4);
    return x;
}
static inline float bm_floorf(float x) {
    int i = (int)x; return (float)(i - (x < (float)i ? 1 : 0));
}

#define sqrtf(x)   bm_sqrtf(x)
#define expf(x)    bm_expf(x)
#define sinf(x)    bm_sinf(x)
#define cosf(x)    bm_cosf(x)
#define logf(x)    bm_logf(x)
#define fabsf(x)   bm_fabsf(x)
#define floorf(x)  bm_floorf(x)

/* ================================================================
 * I/O — printf/fprintf → UART
 * ================================================================
 * The OS kernel must provide bm_uart_putc(char).
 */
void bm_uart_putc(char c);          /* provided by kernel */
void bm_uart_puts(const char *s);
int  bm_vprintf(const char *fmt, va_list ap);
int  bm_printf(const char *fmt, ...);

/* FILE* is ignored; all output goes to UART */
#define printf(...)           bm_printf(__VA_ARGS__)
#define fprintf(f, ...)       bm_printf(__VA_ARGS__)
#define fputs(s, f)           bm_uart_puts(s)
#define fflush(f)             ((void)0)

/* ================================================================
 * FILE I/O — reads from a memory blob
 * ================================================================
 * To use: set bm_model_blob / bm_model_blob_size before calling
 * bm_fopen(). The kernel embeds the model or points to SD-read data.
 */
typedef struct {
    const uint8_t *data;
    size_t         size;
    size_t         pos;
    int            error;
} BM_FILE;

/* Set these before calling fopen: */
extern const uint8_t *bm_model_blob;
extern size_t         bm_model_blob_size;

BM_FILE *bm_fopen(const char *path, const char *mode);
size_t   bm_fread(void *buf, size_t size, size_t nmemb, BM_FILE *f);
int      bm_fseek(BM_FILE *f, long offset, int whence);
long     bm_ftell(BM_FILE *f);
int      bm_fclose(BM_FILE *f);
int      bm_ferror(BM_FILE *f);

#define FILE    BM_FILE
#define fopen   bm_fopen
#define fread   bm_fread
#define fseek   bm_fseek
#define ftell   bm_ftell
#define fclose  bm_fclose
#define ferror  bm_ferror

#ifndef SEEK_SET
#define SEEK_SET 0
#define SEEK_CUR 1
#define SEEK_END 2
#endif

/* ================================================================
 * ASSERT → UART message + hang
 * ================================================================ */
#define assert(cond) do { \
    if (!(cond)) { \
        bm_printf("ASSERT FAIL: %s:%d\n", __FILE__, __LINE__); \
        for(;;) __asm__("wfe"); \
    } \
} while(0)

/* ================================================================
 * EXIT/ABORT → hang
 * ================================================================ */
static inline void bm_exit(int code) { (void)code; for(;;) __asm__("wfe"); }
static inline void bm_abort(void)    { for(;;) __asm__("wfe"); }
#define exit(c)  bm_exit(c)
#define abort()  bm_abort()

/* ================================================================
 * MISC
 * ================================================================ */

/* rand() stub — not needed for inference; satisfy gguf tokenizer */
static inline int bm_rand(void) { return 42; }
#define rand() bm_rand()
#define srand(s) ((void)(s))

#endif /* BAREMETAL */
