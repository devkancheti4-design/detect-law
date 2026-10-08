/* detect-law's interface to THE DETECT LAW v8.1 (detect_v81.c, byte-identical to the file used for the official
   RAID run). Nothing here changes a decision: api_block only loops law_step over one window, and api_z only reports
   each arm's signed z for the explanation shown to the user.
   Built once per mode:  cc -O2 -std=c99 -DV81_MODE=0|1 -shared -fPIC -o liblaw_v81_m<mode>.so api_v81.c          */
#include "detect_v81.c"

void    api_init(law_state *s)         { law_init(s); }
int32_t api_final(const law_state *s)  { return law_final(s); }
int32_t api_score(const law_state *s)  { return law_score(s); }
int32_t api_tokens(const law_state *s) { return s->w[0]; }

/* feed one window; returns 0 or 1 if the law latches a stop inside it, else 2 */
int32_t api_block(law_state *s, const int32_t *L, const int32_t *E, const int32_t *V, const int32_t *D,
                  const int32_t *K, const int32_t *VC, const int32_t *R, const int32_t *Q, int32_t n)
{
    int32_t i, r;
    for (i = 0; i < n; i++) {
        r = law_step(s, L[i], E[i], V[i], D[i], K[i], VC[i], R[i], Q[i]);
        if (r == 0 || r == 1) return r;
    }
    return 2;
}

/* signed z of one arm in 1/16 units (the same z law_score squares), or INT32_MIN below the arm's floor */
static int32_t zsigned(int32_t Sp, int32_t W, int32_t th, int32_t tau16, int32_t floor_)
{
    int64_t z;
    if (W < floor_) return INT32_MIN;
    z = ((int64_t)tau16 * Sp) / (th > 0 ? th : 1);
    return (int32_t)(z > 512 ? 512 : (z < -512 ? -512 : z));
}

void api_z(const law_state *s, int32_t *out)   /* out[0] surprise, out[1] contrast, out[2] repetition */
{
    const int32_t *w = s->w;
    out[0] = zsigned(CENT(w[1], w[3],  A), w[3],  THR(w[3],  A), A_TAU16, A_FLOOR);
    out[1] = zsigned(CENT(w[5], w[7],  C), w[7],  THR(w[7],  C), C_TAU16, C_FLOOR);
    out[2] = zsigned(CENT(w[9], w[11], R), w[11], THR(w[11], R), R_TAU16, R_FLOOR);
}
