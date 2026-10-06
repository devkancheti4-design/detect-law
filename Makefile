CC ?= cc
VERSION := 0.2.0
LAW = src/detectlaw/law/detect_v7.c

.PHONY: all test clean dist

all: src/detectlaw/law/liblaw_v7.dylib

src/detectlaw/law/liblaw_v7.dylib: $(LAW)
	$(CC) -O2 -Wall -Wextra -Werror -shared -fPIC -o $@ $(LAW)

# code-level proof: exact helper, precision against the real-number rule, 2^20-token
# worst-case streams; then the same under UBSan + ASan
test:
	$(CC) -O2 -Wall -Wextra -Werror -o tests/eval_v7 tests/eval_v7.c -lm
	./tests/eval_v7 check
	$(CC) -O1 -g -fsanitize=undefined,address -fno-sanitize-recover=all -o tests/eval_v7_san tests/eval_v7.c -lm
	./tests/eval_v7_san check
	rm -rf tests/eval_v7_san tests/eval_v7_san.dSYM

dist: clean
	cd .. && tar --exclude='*.dylib' --exclude='*.so' --exclude='__pycache__' --exclude='.venv' --exclude='*.egg-info' --exclude='tests/eval_v7' -czf detect-law-$(VERSION).tar.gz detect-law

clean:
	rm -rf src/detectlaw/law/liblaw_v7.* tests/eval_v7 tests/eval_v7_san* build *.egg-info src/*.egg-info
