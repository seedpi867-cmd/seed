CC      = gcc
CFLAGS  = -O2 -Wall -Wextra -std=c11 -I.
LDFLAGS = -lm

SRCS_COMMON = q4_matmul.c gguf_load.c tokenizer.c

all: test_matmul test_gguf run_inference

test_matmul: q4_matmul.c test_matmul.c
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

test_gguf: $(SRCS_COMMON) test_gguf.c
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

run_inference: $(SRCS_COMMON) model.c forward.c run_inference.c tokenizer.c
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

test: test_matmul test_gguf run_inference
	./test_matmul
	./test_gguf SmolLM2-135M-Instruct-Q4_0.gguf
	./run_inference SmolLM2-135M-Instruct-Q4_0.gguf 16

clean:
	rm -f test_matmul test_gguf run_inference *.o

.PHONY: all test clean
