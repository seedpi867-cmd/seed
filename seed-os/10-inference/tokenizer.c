/*
 * tokenizer.c — vocabulary loading and token-to-string decoding.
 *
 * Does a second sequential pass over the GGUF metadata to extract the
 * tokenizer.ggml.tokens array without having to store it in gguf_ctx_t.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "tokenizer.h"
#include "gguf.h"

/* ---- low-level helpers (duplicated from gguf_load.c for independence) ---- */

static int rd_u8 (FILE *f, uint8_t  *v) { return fread(v,1,1,f)==1?0:-1; }
static int rd_u16(FILE *f, uint16_t *v) { return fread(v,2,1,f)==1?0:-1; }
static int rd_u32(FILE *f, uint32_t *v) { return fread(v,4,1,f)==1?0:-1; }
static int rd_u64(FILE *f, uint64_t *v) { return fread(v,8,1,f)==1?0:-1; }
static int rd_i32(FILE *f, int32_t  *v) { return fread(v,4,1,f)==1?0:-1; }
static int rd_i64(FILE *f, int64_t  *v) { return fread(v,8,1,f)==1?0:-1; }
static int rd_f32(FILE *f, float    *v) { return fread(v,4,1,f)==1?0:-1; }
static int rd_f64(FILE *f, double   *v) { return fread(v,8,1,f)==1?0:-1; }

static int skip_val(FILE *f, uint32_t vtype);

static int skip_str(FILE *f) {
    uint64_t slen;
    if (rd_u64(f, &slen)) return -1;
    return fseek(f, (long)slen, SEEK_CUR) == 0 ? 0 : -1;
}

static int skip_val(FILE *f, uint32_t vtype) {
    uint8_t u8; uint16_t u16; uint32_t u32; uint64_t u64;
    int32_t i32; int64_t i64; float f32; double f64;
    switch (vtype) {
        case GGUF_TYPE_UINT8:
        case GGUF_TYPE_INT8:
        case GGUF_TYPE_BOOL:    return rd_u8(f,&u8);
        case GGUF_TYPE_UINT16:
        case GGUF_TYPE_INT16:   return rd_u16(f,&u16);
        case GGUF_TYPE_UINT32:  return rd_u32(f,&u32);
        case GGUF_TYPE_INT32:   return rd_i32(f,&i32);
        case GGUF_TYPE_FLOAT32: return rd_f32(f,&f32);
        case GGUF_TYPE_UINT64:  return rd_u64(f,&u64);
        case GGUF_TYPE_INT64:   return rd_i64(f,&i64);
        case GGUF_TYPE_FLOAT64: return rd_f64(f,&f64);
        case GGUF_TYPE_STRING:  return skip_str(f);
        case GGUF_TYPE_ARRAY: {
            uint32_t et; uint64_t cnt;
            if (rd_u32(f,&et)||rd_u64(f,&cnt)) return -1;
            for (uint64_t i=0;i<cnt;i++) if (skip_val(f,et)) return -1;
            return 0;
        }
        default: return -1;
    }
    (void)u8;(void)u16;(void)u32;(void)u64;
    (void)i32;(void)i64;(void)f32;(void)f64;
}

/* ---- vocab loading ---- */

int vocab_load(vocab_t *v, const char *gguf_path) {
    memset(v, 0, sizeof(*v));

    FILE *f = fopen(gguf_path, "rb");
    if (!f) { perror(gguf_path); return -1; }

    /* Read GGUF header */
    uint32_t magic, version;
    uint64_t n_tensors, n_kv;
    if (fread(&magic,4,1,f)!=1 || magic!=GGUF_MAGIC) goto fail;
    if (fread(&version,4,1,f)!=1) goto fail;
    if (rd_u64(f,&n_tensors)||rd_u64(f,&n_kv)) goto fail;

    /* Scan KV pairs looking for tokenizer.ggml.tokens */
    int found = 0;
    for (uint64_t ki = 0; ki < n_kv && !found; ki++) {
        /* Read key */
        uint64_t klen;
        if (rd_u64(f,&klen)) goto fail;
        char key[256]={0};
        if (klen < sizeof(key)) {
            if (fread(key,1,(size_t)klen,f)!=(size_t)klen) goto fail;
        } else {
            if (fseek(f,(long)klen,SEEK_CUR)) goto fail;
        }

        uint32_t vtype;
        if (rd_u32(f,&vtype)) goto fail;

        if (vtype==GGUF_TYPE_ARRAY && strcmp(key,"tokenizer.ggml.tokens")==0) {
            uint32_t elem_type; uint64_t count;
            if (rd_u32(f,&elem_type)||rd_u64(f,&count)) goto fail;
            if (elem_type != GGUF_TYPE_STRING) { skip_val(f,vtype); continue; }

            /* Allocate: first pass to measure total string bytes */
            /* Actually do it in one pass: grow strbuf dynamically */
            uint32_t n = (uint32_t)count;
            uint32_t *offsets = malloc((n + 1) * sizeof(uint32_t));
            if (!offsets) goto fail;

            /* Estimate total buf size: average 6 bytes/token */
            size_t buf_cap = (size_t)n * 8;
            char *buf = malloc(buf_cap);
            if (!buf) { free(offsets); goto fail; }
            size_t buf_used = 0;

            for (uint32_t i = 0; i < n; i++) {
                uint64_t slen;
                if (rd_u64(f,&slen)) { free(offsets); free(buf); goto fail; }
                /* Grow buf if needed */
                if (buf_used + slen + 1 > buf_cap) {
                    buf_cap = buf_used + slen + 1 + (size_t)n * 4;
                    char *nb = realloc(buf, buf_cap);
                    if (!nb) { free(offsets); free(buf); goto fail; }
                    buf = nb;
                }
                offsets[i] = (uint32_t)buf_used;
                if (slen > 0) {
                    if (fread(buf + buf_used, 1, (size_t)slen, f) != (size_t)slen) {
                        free(offsets); free(buf); goto fail;
                    }
                }
                buf[buf_used + slen] = '\0';
                buf_used += slen + 1;
            }
            offsets[n] = (uint32_t)buf_used; /* sentinel */

            v->strbuf  = buf;
            v->offsets = offsets;
            v->n_vocab = n;
            found = 1;
        } else {
            if (skip_val(f, vtype)) goto fail;
        }
    }

    fclose(f);
    if (!found) { fprintf(stderr, "vocab: tokenizer.ggml.tokens not found\n"); return -1; }
    return 0;

fail:
    fclose(f);
    return -1;
}

void vocab_free(vocab_t *v) {
    free(v->strbuf);
    free(v->offsets);
    memset(v, 0, sizeof(*v));
}

const char *vocab_token_raw(const vocab_t *v, int id) {
    if (id < 0 || (uint32_t)id >= v->n_vocab) return "<unk>";
    return v->strbuf + v->offsets[id];
}

/*
 * GPT-2 byte encoding: the BPE tokenizer encodes raw bytes as Unicode
 * characters in range U+0100..U+017F and U+0020-style replacements.
 *
 * Specifically (from tiktoken / GPT-2 source):
 *   Printable ASCII (0x21..0x7E) → themselves
 *   Space (0x20) → Ġ (U+0120, encoded as UTF-8 C4 A0)
 *   Newline (0x0A) → Ċ (U+010A, encoded as UTF-8 C4 8A)
 *   Other control bytes n → U+0100+n (encoded in UTF-8)
 *   Bytes 0x80..0xFF → U+0100..U+017F (encoded in UTF-8 as C4 80 .. C5 BF)
 *
 * We do a best-effort decode: convert known 2-byte UTF-8 sequences back to bytes.
 */
void vocab_token_decode(const vocab_t *v, int id, char *out, size_t out_len) {
    const char *raw = vocab_token_raw(v, id);
    size_t wi = 0;

    for (const char *p = raw; *p && wi + 1 < out_len; ) {
        unsigned char c0 = (unsigned char)*p;
        /* 2-byte UTF-8 sequence (covers U+0080..U+07FF) */
        if ((c0 & 0xE0) == 0xC0 && p[1] && ((unsigned char)p[1] & 0xC0) == 0x80) {
            unsigned char c1 = (unsigned char)p[1];
            uint32_t cp = ((uint32_t)(c0 & 0x1F) << 6) | (c1 & 0x3F);
            /*
             * GPT-2 byte encoding: non-printable bytes (0x00-0x20, 0x7F, 0x80-0xA0, 0xAD)
             * are encoded as U+0100+byte_value. So U+0100-U+0143 → raw byte (cp-0x100).
             * This covers:
             *   U+0120 (Ġ) → byte 0x20 → space
             *   U+010A (Ċ) → byte 0x0A → newline
             *   U+0109 (ĉ) → byte 0x09 → tab
             */
            if (cp >= 0x100 && cp <= 0x143) {
                unsigned char raw_byte = (unsigned char)(cp - 0x100);
                /* Only emit printable or whitespace; skip other control chars */
                if (raw_byte >= 0x20 || raw_byte == '\n' || raw_byte == '\r' || raw_byte == '\t') {
                    out[wi++] = (char)raw_byte;
                }
            } else {
                /* Keep UTF-8 as-is (Latin-1 range etc.) */
                if (wi + 2 < out_len) { out[wi++] = (char)c0; out[wi++] = (char)c1; }
            }
            p += 2;
        } else if ((c0 & 0xF0) == 0xE0 && p[1] && p[2]) {
            /* 3-byte UTF-8: keep as-is */
            if (wi + 3 < out_len) { out[wi++]=(char)c0; out[wi++]=(char)p[1]; out[wi++]=(char)p[2]; }
            p += 3;
        } else {
            out[wi++] = (char)c0;
            p++;
        }
    }
    out[wi] = '\0';
}

void vocab_print_token(const vocab_t *v, int id) {
    char buf[64];
    vocab_token_decode(v, id, buf, sizeof(buf));
    fputs(buf, stdout);
    fflush(stdout);
}

int vocab_find(const vocab_t *v, const char *str) {
    for (uint32_t i = 0; i < v->n_vocab; i++) {
        if (strcmp(vocab_token_raw(v, i), str) == 0) return (int)i;
    }
    return -1;
}
