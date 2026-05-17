/*
 * tokenizer.h — vocabulary loading and token-to-string decoding.
 *
 * Phase 1: loads vocab strings from GGUF metadata (second pass over file).
 * Phase 2: on bare metal, vocab is embedded in the binary or loaded from SD.
 *
 * SmolLM2 uses GPT-2 BPE with byte-level fallback encoding:
 *   special bytes are encoded as Ġ (U+0120 = Ċ prefix), e.g. space → 'Ġ'
 *   newline → 'Ċ', etc. We decode these back to raw bytes on output.
 */
#ifndef TOKENIZER_H
#define TOKENIZER_H

#include <stdint.h>
#include <stddef.h>

typedef struct {
    char     *strbuf;      /* all token strings concatenated, null-terminated */
    uint32_t *offsets;     /* offsets[i] = byte offset of token i in strbuf */
    uint32_t  n_vocab;
} vocab_t;

/*
 * Load vocabulary from a GGUF file.
 * Does a second sequential scan of the metadata section.
 * Returns 0 on success. Call vocab_free() when done.
 */
int  vocab_load(vocab_t *v, const char *gguf_path);
void vocab_free(vocab_t *v);

/*
 * Return the raw token string for token id.
 * May contain Ġ/Ċ byte-encoding characters (GPT-2 style).
 * Returns "<unk>" for out-of-range ids.
 */
const char *vocab_token_raw(const vocab_t *v, int id);

/*
 * Decode a token string to its actual bytes (UTF-8 text).
 * Writes decoded bytes to buf (max buf_len bytes, null-terminated).
 * Handles GPT-2 Ġ/Ċ byte encoding → raw ASCII.
 */
void vocab_token_decode(const vocab_t *v, int id, char *buf, size_t buf_len);

/*
 * Print decoded token text directly to stdout (no newline).
 * Flushes stdout so tokens appear as they are generated.
 */
void vocab_print_token(const vocab_t *v, int id);

/*
 * Simple tokenizer: find the token ID matching an exact string.
 * Returns -1 if not found. Used for building pre-tokenized prompts.
 */
int vocab_find(const vocab_t *v, const char *str);

#endif /* TOKENIZER_H */
