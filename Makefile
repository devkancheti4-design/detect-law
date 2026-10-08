CC ?= cc
VERSION := 0.3.0
LAW = src/detectlaw/law/api_v81.c src/detectlaw/law/detect_v81.c
EXT := $(if $(filter Darwin,$(shell uname)),dylib,so)

.PHONY: all test test-v7 clean dist

all: src/detectlaw/law/liblaw_v81_m0.$(EXT) src/detectlaw/law/liblaw_v81_m1.$(EXT)

src/detectlaw/law/liblaw_v81_m%.$(EXT): $(LAW)
	$(CC) -O2 -Wall -Wextra -Werror -std=c99 -DV81_MODE=$* -shared -fPIC -o $@ src/detectlaw/law/api_v81.c

# both modes: -Werror, then extreme and random streams under UBSan + ASan
test:
	for m in 0 1; do \
	  $(CC) -O2 -Wall -Wextra -Werror -std=c99 -DV81_MODE=$$m -o tests/smoke_v81 tests/smoke_v81.c && ./tests/smoke_v81 || exit 1; \
	  $(CC) -O1 -g -std=c99 -DV81_MODE=$$m -fsanitize=undefined,address -fno-sanitize-recover=all -o tests/smoke_v81_san tests/smoke_v81.c && ./tests/smoke_v81_san || exit 1; \
	done
	rm -rf tests/smoke_v81 tests/smoke_v81_san tests/smoke_v81_san.dSYM

# the v7 proof harness, kept with the archived v7 law
test-v7:
	$(CC) -O2 -Wall -Wextra -Werror -o archive/v7/eval_v7 archive/v7/eval_v7.c -lm
	./archive/v7/eval_v7 check

dist: clean
	cd .. && tar --exclude='*.dylib' --exclude='*.so' --exclude='__pycache__' --exclude='.venv' --exclude='*.egg-info' -czf detect-law-$(VERSION).tar.gz detect-law

clean:
	rm -rf src/detectlaw/law/liblaw_v* tests/smoke_v81 tests/smoke_v81_san* archive/v7/eval_v7 build *.egg-info src/*.egg-info
