/* Smoke test for THE DETECT LAW v8.1 (law/detect_v81.c via law/api_v81.c): streams of extreme and random inputs,
   including the quantisation bounds, run under -Werror and UBSan/ASan. Checks the verdict codes, that a stop
   latches, and that law_score stays within its documented bound (3 * 2^18).  make test                          */
#include <stdio.h>
#include <stdlib.h>
#include "../src/detectlaw/law/api_v81.c"

static uint32_t rng = 2463534242u;
static int32_t rnd(int32_t lo, int32_t hi) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return lo + (int32_t)(rng % (uint32_t)(hi - lo + 1)); }

int main(void)
{
    int stream, fails = 0;
    for (stream = 0; stream < 15; stream++) {
        law_state s; int32_t i, n = 1 << 18, act = 2, zs[3];
        api_init(&s);
        for (i = 0; i < n; i++) {
            int32_t L, E, V, D, K, VC, R, Q;
            switch (stream % 5) {
            case 0:  L = -(1 << 21); E = 0; V = 1 << 22; D = (1 << 21); K = -(1 << 21); VC = 1 << 24; R = 0; Q = 65536; break;   /* bounds, corner 1 */
            case 1:  L = 0; E = -(1 << 21); V = 0; D = -(1 << 21); K = 0; VC = 0; R = 1; Q = 0; break;                       /* bounds, corner 2 */
            case 2:  L = rnd(-(1 << 21), 0); E = rnd(-(1 << 21), 0); V = rnd(0, 1 << 22); D = rnd(-(1 << 21), 1 << 21);
                     K = rnd(-(1 << 21), 0); VC = rnd(0, 1 << 24); R = rnd(0, 1); Q = rnd(0, 65536); break;
            case 4:  L = -65536 - rnd(0, 20000); E = L - 131072; V = 262144; D = 65536; K = -rnd(0, 20000);              /* strong AI: */
                     VC = 131072; R = 0; Q = 19661 + rnd(0, 6000); break;                                        /* must stop early */
            default: L = rnd(-400000, 0); E = L + rnd(-60000, 60000); E = E > 0 ? 0 : E; V = rnd(0, 600000);
                     D = rnd(-40000, 40000); K = rnd(-40000, 0); VC = rnd(0, 200000); R = rnd(0, 1); Q = rnd(0, 30000);
                     if (rnd(0, 9) == 0) D = INT32_MIN; break;                                                       /* B missing */
            }
            act = law_step(&s, L, E, V, D, K, VC, R, Q);
            if (act != 0 && act != 1 && act != 2) { printf("stream %d: bad code %d\n", stream, act); fails++; break; }
            if (act != 2) {
                if (law_step(&s, 0, 0, 0, 0, 0, 0, 0, 0) != act) { printf("stream %d: stop did not latch\n", stream); fails++; }
                break;
            }
        }
        if (stream % 5 == 4 && (act != 1 || api_tokens(&s) >= n)) { printf("stream %d: strong AI did not stop early\n", stream); fails++; }
        if (act == 2) act = api_final(&s);
        api_z(&s, zs);
        if (api_score(&s) < 0 || api_score(&s) > 3 * (1 << 18)) { printf("stream %d: score out of range\n", stream); fails++; }
        printf("stream %2d: verdict %d after %7d tokens, score %6d, z/16 %5d %5d %5d\n", stream, act, api_tokens(&s), api_score(&s),
               zs[0] == INT32_MIN ? 0 : zs[0], zs[1] == INT32_MIN ? 0 : zs[1], zs[2] == INT32_MIN ? 0 : zs[2]);
    }
    printf(fails ? "FAILED\n" : "ok\n");
    return fails != 0;
}
