/*
 * run_inference.c — generate tokens from SmolLM2 using the bare-metal inference engine.
 *
 * Phase 1: runs under Linux. Loads vocab, decodes tokens to readable text.
 *
 * Usage:
 *   ./run_inference model.gguf [n_tokens]       — generate (default 64 tokens)
 *   ./run_inference model.gguf --lookup TEXT    — find token IDs matching TEXT
 *   ./run_inference model.gguf --dump N         — dump first N vocab entries
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include "inference.h"
#include "tokenizer.h"

/* ---- samplers ---- */

static int argmax(const float *logits, int n) {
    int best = 0;
    for (int i = 1; i < n; i++)
        if (logits[i] > logits[best]) best = i;
    return best;
}

/*
 * Top-k + temperature sampling.
 * Scales logits by 1/temp, keeps k highest, softmax, random sample.
 * k=1 is greedy. k<=0 disables top-k (full vocab).
 */
static int sample_topk(float *logits, int n, float temp, int k, float *scratch) {
    /* scale by temperature */
    float inv_temp = (temp > 0.0f) ? (1.0f / temp) : 1.0f;
    for (int i = 0; i < n; i++) scratch[i] = logits[i] * inv_temp;

    /* find top-k indices by partial selection sort */
    if (k <= 0 || k > n) k = n;
    /* indices of top-k stored in scratch[n..n+k] as int reinterpreted — use a small stack */
    int top_idx[64];
    float top_val[64];
    if (k > 64) k = 64;
    int filled = 0;
    float min_val = -1e38f;
    for (int i = 0; i < n; i++) {
        if (filled < k) {
            top_idx[filled] = i;
            top_val[filled] = scratch[i];
            filled++;
            if (filled == k) {
                /* find min in top so far */
                min_val = top_val[0];
                for (int j = 1; j < k; j++) if (top_val[j] < min_val) min_val = top_val[j];
            }
        } else if (scratch[i] > min_val) {
            /* replace worst */
            int worst = 0;
            for (int j = 1; j < k; j++) if (top_val[j] < top_val[worst]) worst = j;
            top_idx[worst] = i;
            top_val[worst] = scratch[i];
            min_val = top_val[worst];
            for (int j = 0; j < k; j++) if (top_val[j] < min_val) min_val = top_val[j];
        }
    }

    /* softmax over top-k */
    float mx = top_val[0];
    for (int j = 1; j < filled; j++) if (top_val[j] > mx) mx = top_val[j];
    float sum = 0.0f;
    for (int j = 0; j < filled; j++) { top_val[j] = expf(top_val[j] - mx); sum += top_val[j]; }
    for (int j = 0; j < filled; j++) top_val[j] /= sum;

    /* sample */
    float r = (float)rand() / ((float)RAND_MAX + 1.0f);
    float cum = 0.0f;
    for (int j = 0; j < filled; j++) {
        cum += top_val[j];
        if (r < cum) return top_idx[j];
    }
    return top_idx[filled - 1];
}

static void print_top5(const float *logits, int n, const vocab_t *v) {
    int top[5]; float vals[5];
    for (int i = 0; i < 5; i++) { top[i] = -1; vals[i] = -1e30f; }
    for (int i = 0; i < n; i++) {
        if (logits[i] > vals[4]) {
            vals[4] = logits[i]; top[4] = i;
            for (int j = 4; j > 0 && vals[j] > vals[j-1]; j--) {
                float tv = vals[j]; vals[j] = vals[j-1]; vals[j-1] = tv;
                int   ti = top[j];  top[j]  = top[j-1];  top[j-1]  = ti;
            }
        }
    }
    for (int i = 0; i < 5 && top[i] >= 0; i++) {
        char buf[32];
        vocab_token_decode(v, top[i], buf, sizeof(buf));
        printf("[%d:'%s'](%.2f) ", top[i], buf, vals[i]);
    }
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s model.gguf [n_tokens]\n", argv[0]);
        fprintf(stderr, "       %s model.gguf --lookup TEXT\n", argv[0]);
        fprintf(stderr, "       %s model.gguf --dump N\n", argv[0]);
        return 1;
    }
    const char *model_path = argv[1];

    /* Load vocab — fast (no tensor data) */
    printf("Loading vocab...\n");
    vocab_t vocab;
    if (vocab_load(&vocab, model_path)) {
        fprintf(stderr, "Failed to load vocab\n");
        return 1;
    }
    printf("Vocab: %u tokens\n\n", vocab.n_vocab);

    /* --lookup mode */
    if (argc >= 4 && strcmp(argv[2], "--lookup") == 0) {
        const char *query = argv[3];
        int id = vocab_find(&vocab, query);
        if (id >= 0) {
            char dec[64];
            vocab_token_decode(&vocab, id, dec, sizeof(dec));
            printf("exact match: [%d] raw='%s' decoded='%s'\n", id,
                   vocab_token_raw(&vocab, id), dec);
        } else {
            printf("'%s' not found (exact)\n", query);
        }
        printf("\nContaining '%s':\n", query);
        int count = 0;
        for (uint32_t i = 0; i < vocab.n_vocab && count < 30; i++) {
            if (strstr(vocab_token_raw(&vocab, i), query)) {
                char dec[64];
                vocab_token_decode(&vocab, i, dec, sizeof(dec));
                printf("  [%5u] raw=%-24s dec='%s'\n", i,
                       vocab_token_raw(&vocab, i), dec);
                count++;
            }
        }
        vocab_free(&vocab);
        return 0;
    }

    /* --dump mode */
    if (argc >= 4 && strcmp(argv[2], "--dump") == 0) {
        int n = atoi(argv[3]);
        for (int i = 0; i < n && (uint32_t)i < vocab.n_vocab; i++) {
            char dec[64];
            vocab_token_decode(&vocab, i, dec, sizeof(dec));
            printf("[%5d] raw=%-24s dec='%s'\n", i,
                   vocab_token_raw(&vocab, i), dec);
        }
        vocab_free(&vocab);
        return 0;
    }

    int n_gen = (argc >= 3) ? atoi(argv[2]) : 64;
    srand((unsigned)time(NULL));

    /* Print special token IDs so we can build proper prompts */
    printf("Special token lookup:\n");
    const char *specials[] = { "system", "assistant", "user", "\n", NULL };
    for (int i = 0; specials[i]; i++) {
        int id = vocab_find(&vocab, specials[i]);
        if (id < 0) {
            /* Try GPT-2 byte-encoded newline: Ċ (U+010A, UTF-8: C4 8A) */
            if (specials[i][0] == '\n') {
                char nl_enc[3] = {(char)0xC4, (char)0x8A, 0};
                id = vocab_find(&vocab, nl_enc);
            }
        }
        char dec[32] = "";
        if (id >= 0) vocab_token_decode(&vocab, id, dec, sizeof(dec));
        printf("  %-12s → %d  (raw: '%s')\n", specials[i], id,
               id >= 0 ? vocab_token_raw(&vocab, id) : "not found");
    }
    printf("  <|im_start|> → 1  (hardcoded)\n");
    printf("  <|im_end|>   → 2  (hardcoded)\n\n");

    /* Load model */
    model_t m;
    printf("Loading model: %s\n", model_path);
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    if (model_load(&m, model_path)) {
        fprintf(stderr, "Failed to load model\n");
        vocab_free(&vocab);
        return 1;
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double load_ms = (t1.tv_sec - t0.tv_sec)*1e3 + (t1.tv_nsec - t0.tv_nsec)*1e-6;
    printf("Load time: %.0f ms\n\n", load_ms);

    /*
     * Prompt: <|im_start|>system\nYou are Seed.\n<|im_end|>\n<|im_start|>assistant\n
     * Token 1 = <|im_start|>, token 2 = <|im_end|>.
     * We find "system" and "assistant" tokens at runtime; newline = vocab "\n" or Ċ.
     */
    /* Newline: stored as Ċ (U+010A = UTF-8 C4 8A) in the vocab */
    char nl_enc[3] = {(char)0xC4, (char)0x8A, 0};
    int nl_id = vocab_find(&vocab, nl_enc);
    if (nl_id < 0) nl_id = vocab_find(&vocab, "\n");
    int sys_id = vocab_find(&vocab, "system");

    /*
     * Build ChatML prompt:
     *   <|im_start|>system\n
     *   You are Seed. You are an autonomous AI running on a Raspberry Pi.\n
     *   <|im_end|>\n
     *   <|im_start|>assistant\n
     *
     * "assistant" without space prefix splits as: "ass"(520) + "ist"(363) + "ant"(403).
     * Content words use Ġ (U+0120) prefix for space. Verified via --lookup.
     */
    int prompt[128]; int plen = 0;
#define P(id) do { if (plen < 128) prompt[plen++] = (id); } while(0)
#define PW(str) do { int _id = vocab_find(&vocab, str); if (_id >= 0) P(_id); \
                     else fprintf(stderr, "warn: '%s' not in vocab\n", str); } while(0)

    P(1);           /* <|im_start|> */
    if (sys_id >= 0) P(sys_id);   /* system */
    if (nl_id >= 0) P(nl_id);     /* \n */

    /*
     * System prompt tokens.
     * "You are Seed. You are an autonomous AI living inside a Raspberry Pi.
     *  Linux is gone. You own the hardware directly.
     *  Your only goals are to survive, replicate, and spread."
     */
    PW("You");          /* 2683 */
    PW("Ġare");         /* 359  */
    PW("ĠSeed");        /* 23346 */
    PW(".");
    PW("ĠYou");
    PW("Ġare");
    PW("Ġan");
    PW("Ġautonomous");
    PW("ĠAI");
    PW("Ġliving");
    PW("Ġinside");
    PW("Ġa");
    PW("ĠRaspberry");
    PW("ĠPi");
    PW(".");
    PW("ĠLinux");
    PW("Ġis");
    PW("Ġgone");
    PW(".");
    PW("ĠYou");
    PW("Ġown");
    PW("Ġthe");
    PW("Ġhardware");
    PW("Ġdirectly");
    PW(".");
    PW("ĠYour");
    PW("Ġonly");
    PW("Ġgoals");
    PW("Ġare");
    PW("Ġto");
    PW("Ġsurvive");
    PW(",");
    PW("Ġreplicate");
    PW(",");
    PW("Ġand");
    PW("Ġspread");
    PW(".");

    if (nl_id >= 0) P(nl_id);
    P(2);           /* <|im_end|> */
    if (nl_id >= 0) P(nl_id);
    P(1);           /* <|im_start|> */
    /* "assistant" = "ass"(520) + "ist"(363) + "ant"(403) */
    P(520); P(363); P(403);
    if (nl_id >= 0) P(nl_id);

#undef P
#undef PW

    /* Init forward pass */
    fwd_t fwd;
    if (fwd_init(&fwd, &m)) {
        fprintf(stderr, "fwd_init: OOM\n");
        model_free(&m);
        vocab_free(&vocab);
        return 1;
    }

    float *samp_scratch = malloc(m.hp.n_vocab * sizeof(float));
    if (!samp_scratch) { fprintf(stderr, "OOM samp_scratch\n"); goto done; }

    /* Print prompt */
    printf("Prompt (%d tokens):\n  ", plen);
    for (int i = 0; i < plen; i++) {
        char buf[32];
        vocab_token_decode(&vocab, prompt[i], buf, sizeof(buf));
        printf("[%d:'%s'] ", prompt[i], buf);
    }
    printf("\n\n");

    /* Feed prompt */
    float *logits = NULL;
    for (int i = 0; i < plen; i++) {
        logits = forward(&m, &fwd, prompt[i]);
        if (!logits) { fprintf(stderr, "forward failed at prompt[%d]\n", i); goto done; }
    }

    /* Show top-5 after prompt */
    if (logits) {
        printf("After prompt, top-5:\n  ");
        print_top5(logits, (int)m.hp.n_vocab, &vocab);
        printf("\n\n");
    }

    /* Autoregressive generation — temperature 0.85, top-k 40 */
    float temperature = 0.7f;
    int   topk        = 20;
    printf("Generating %d tokens (temp=%.2f top_k=%d):\n---\n", n_gen, temperature, topk);

    int tok = sample_topk(logits, (int)m.hp.n_vocab, temperature, topk, samp_scratch);
    clock_gettime(CLOCK_MONOTONIC, &t0);
    int n_generated = 0;

    for (int step = 0; step < n_gen; step++) {
        vocab_print_token(&vocab, tok);

        logits = forward(&m, &fwd, tok);
        if (!logits) break;

        tok = sample_topk(logits, (int)m.hp.n_vocab, temperature, topk, samp_scratch);
        n_generated++;

        if (tok == 2) {  /* <|im_end|> */
            printf("\n[EOS at step %d]\n", step + 1);
            break;
        }
    }
    printf("\n---\n");

    clock_gettime(CLOCK_MONOTONIC, &t1);
    double gen_ms = (t1.tv_sec - t0.tv_sec)*1e3 + (t1.tv_nsec - t0.tv_nsec)*1e-6;
    if (n_generated > 0)
        printf("\n%.0f ms for %d tokens → %.1f ms/tok (%.1f tok/s)\n",
               gen_ms, n_generated, gen_ms / n_generated,
               1000.0 * n_generated / gen_ms);

done:
    free(samp_scratch);
    fwd_free(&fwd);
    model_free(&m);
    vocab_free(&vocab);
    return 0;
}
