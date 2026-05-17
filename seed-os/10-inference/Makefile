CC      = gcc
CFLAGS  = -O2 -Wall -Wextra -std=c11 -I.
LDFLAGS = -lm

# Cross-compiler for AArch64 bare-metal
CC_BM   = aarch64-linux-gnu-gcc
CFLAGS_BM = -O2 -Wall -std=c11 -I. -DBAREMETAL \
            -ffreestanding -nostdlib -mcpu=cortex-a53 \
            -fno-builtin -fno-stack-protector \
            -Wno-unused-parameter

SRCS_COMMON = q4_matmul.c gguf_load.c tokenizer.c
SRCS_BM     = baremetal.c q4_matmul.c gguf_load.c tokenizer.c model.c forward.c

all: test_matmul test_gguf run_inference

test_matmul: q4_matmul.c test_matmul.c
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

test_gguf: $(SRCS_COMMON) test_gguf.c
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

run_inference: $(SRCS_COMMON) model.c forward.c run_inference.c tokenizer.c
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

# Bare-metal object files: verify everything compiles without libc
baremetal_check: $(SRCS_BM)
	$(CC_BM) $(CFLAGS_BM) -c baremetal.c     -o /tmp/bm_baremetal.o
	$(CC_BM) $(CFLAGS_BM) -c q4_matmul.c     -o /tmp/bm_q4matmul.o
	$(CC_BM) $(CFLAGS_BM) -c gguf_load.c     -o /tmp/bm_gguf.o
	$(CC_BM) $(CFLAGS_BM) -c tokenizer.c     -o /tmp/bm_tokenizer.o
	$(CC_BM) $(CFLAGS_BM) -c model.c         -o /tmp/bm_model.o
	$(CC_BM) $(CFLAGS_BM) -c forward.c       -o /tmp/bm_forward.o
	@echo "BAREMETAL COMPILE OK — all objects built without libc"

test: test_matmul test_gguf run_inference
	./test_matmul
	./test_gguf SmolLM2-135M-Instruct-Q4_0.gguf
	./run_inference SmolLM2-135M-Instruct-Q4_0.gguf 16

clean:
	rm -f test_matmul test_gguf run_inference *.o

.PHONY: all test clean baremetal_check
