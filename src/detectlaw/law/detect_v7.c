/* ===========================================================================
   THE DETECT LAW v7 -- streaming, two signals, early stop + end-of-text test.
   int32 only.  Built from the round-6 test findings (see README):
     - short texts collapsed under anytime-only boundaries  -> add an END TEST
     - model B was gated on surprise, so contrast was never   -> B runs from the
       checked on domain-shifted text                            first token
     - "no evidence" ruled out only surprise-sized effects    -> needs BOTH arms
     - a short text that simply ended was called "no evidence" -> 2 (undecided)

   API.  Call law_step once per token.  Run model B (supply D, K, VC) from the
   first token until law_step returns 2; pass INT32_MIN for D, K, VC when B is not
   run.  Call law_final ONLY at the true end of the text (its end test assumes the
   text length was not chosen by looking at the evidence).
     law_step : 1 AI, stop | 0 no evidence of AI, stop | 2 continue, A only
                | 3 continue, run B for the next token
     law_final: 1 AI | 0 no evidence (both arms ruled out an AI-sized effect)
                | 2 undecided (too short, or ambiguous)

   INPUT per token (Q16.16): L = log2 pA(x), E = sum pA log2 pA, V = sum pA (log2 pA - E)^2,
   D = log2 pB(x) - L, K = sum pA (log2 pB - log2 pA), VC = sum pA (log2 pB - log2 pA - K)^2.
   Ranges: L,E,K in [-2^21,0]; D in [-2^21,2^21]; V in [0,2^22]; VC in [0,2^24]; T <= 2^20.

   ---------------------------------------------------------------------------
   THE MATHS
   Per token, with c_A = 3/2048 and c_C = 90/2048 (human biases, measured):
     surprise  a = min(L - E - c_A*V, 8 bits)      f = max(a, -8 bits)
     contrast  c = min(D - K - c_C*VC, 6 bits)     g = max(c, -6 bits)
   Under the null (human text) each a has mean <= 0 and variance <= rho_A*V with
   rho_A = 1.06; each c has mean <= 0 and variance <= rho_C*VC, rho_C = 1.28.

   EARLY STOP (anytime valid).  Increments are bounded above by M (8 or 6 bits),
   so by Bennett  E exp(lam*x) <= exp(lam^2 * phi(lam*M) * v / 2),
   phi(u) = 2(e^u - 1 - u)/u^2.  exp(lam*S - lam^2*phi*rho*W/2) is then a
   supermartingale and Ville's inequality gives, for every length at once,
       P( S >= log(1/alpha)/lam + (lam/2)*phi*rho*W  ever ) <= alpha.
   Three lines per arm (tuned to cross at 100/400/1600 tokens for surprise and
   80/320/1280 for contrast), each at alpha = 0.2%/3: 0.2% per arm, 0.4% total.

   END TEST (fixed length).  At the true end of the text, for every arm that ran
   through all of it:  z = S / sqrt(rho*W) > tau,  tau = 2.747781 (0.3% per arm,
   0.6% total).  Union bound: early 0.4% + end 0.6% = 1.0% of human texts flagged.

   FUTILITY ("no evidence").  Target AI effect, from the measured AI shifts:
   surprise 0.40 bits/token, contrast 0.35 bits/token, modelled as a mean of
   kappa*rho*V per token (the temperature-tilt shape), kappa_A = 0.03281,
   kappa_C = 0.09429.  Sequentially, by Ville under the alternative (Bennett on
   the lower clip), an arm is ruled out when F < kappa(1 - phi/2)*rho*W - log(40)/kappa
   (2.5% error per arm).  At the end, an arm still running is ruled out when
   F <= kappa*rho*W - 1.96*sqrt(rho*W) (2.5%).  "No evidence" needs BOTH arms
   ruled out.

   INTEGER FORM.  Sums are exact (quotient + remainder carries, as in the proven
   rounds): S, F, N, G in 2^-5 bit; W, C (= sum V, sum VC) in 2^-2 bit^2.
   Lines: S >= Q + (P*W) >> 15 (surprise) or >> 14 (contrast); P, Q rounded UP
   and W read as the CEILING (conservative); futility lines rounded DOWN with W
   as the floor (conservative).  End tests compare X^2 >= k*W after scaling both
   by a common power of 4 so every product fits int32 (ge_z).
   =========================================================================== */
#include <stdint.h>

#define CLIPA 524288                 /* 8 bits in 2^-16 bit */
#define CLIPC 393216                 /* 6 bits in 2^-16 bit */
static const int32_t PA[3] = { 17434, 8165, 3944 };   /* 2^-15 per (2^-2 bit^2) -> 2^-5 bit */
static const int32_t QA[3] = {  2448, 4585, 8858 };   /* 2^-5 bit */
static const int32_t PC[3] = { 22721, 10340, 4913 };  /* 2^-14 scale */
static const int32_t QC[3] = {  1287, 2343, 4452 };
#define PFA 4132                     /* surprise futility slope, 2^-15 scale */
#define QFA 3598                     /* surprise futility intercept, 2^-5 bit */
#define PFC 12361                    /* contrast futility slope, 2^-15 scale */
#define QFC 1252
#define PKA 9118                     /* kappa_A*rho_A*W, 2^-15 scale (rounded down) */
#define PKC 31638
#define KENDA 2049                   /* ceil(256*rho_A*tau^2) */
#define KENDC 2475                   /* ceil(256*rho_C*tau^2) */
#define KFUTA 1043                   /* ceil(256*rho_A*1.96^2) */
#define KFUTC 1259

/* state: w0 t | w1 S w2 Sr | w3 F w4 Fr | w5 W w6 Wr | w7 centring carry A
          w8 N w9 Nr | w10 G w11 Gr | w12 C w13 Cr | w14 centring carry C
          w15 flags: bit0 surprise ruled out, bit1 contrast ruled out,
                     bit2 contrast not run (B declined), bits3-4 latched act+1 */
typedef struct { int32_t w[16]; } law_state;

static inline int32_t cap_hi(int32_t x, int32_t m) { return x < m ? x : m; }      /* min(x, m)  */
static inline int32_t cap_lo(int32_t x, int32_t m) { return x > -m ? x : -m; }    /* max(x, -m) */
static inline void acc11(int32_t *q, int32_t *r, int32_t x) { int32_t s = x + *r; *q += s >> 11; *r = s & 2047; }
static inline void acc14(int32_t *q, int32_t *r, int32_t x) { int32_t s = x + *r; *q += s >> 14; *r = s & 16383; }
/* P*W >> s for s in {14,15}, W >= 0; every caller keeps P*(W>>16) << (16-s) below 2^31 */
static inline int32_t mulsh(int32_t P, int32_t W, int s) { return ((P * (W >> 16)) << (16 - s)) + ((P * (W & 65535)) >> s); }
/* 1 iff X > 0 and X*X >= k*W; k < 4096, 0 <= W <= 2^30+1.  Scale W down by 4
   (ceiling, conservative) and X by 2 (floor, conservative) until W < 2^18, so
   k*W < 2^30 and the boundary sqrt(k*W) < 2^15. */
static int32_t ge_z(int32_t X, int32_t W, int32_t k)
{   if (X <= 0) return 0;
    while (W >= (1 << 18)) { W = (W + 3) >> 2; X >>= 1; }
    if (X >= 32768) return 1;
    return X * X >= k * W; }

void law_init(law_state *s) { int i; for (i = 0; i < 16; i++) s->w[i] = 0; }

int32_t law_step(law_state *s, int32_t L, int32_t E, int32_t V, int32_t D, int32_t K, int32_t VC)
{   int32_t *w = s->w, fl = w[15], t, j, ai = 0, okA, okC, actC, WA, WC;
    if ((fl >> 3) & 3) return ((fl >> 3) & 3) - 1;             /* a stop stands */
    {   int32_t cn = 3 * V + w[7];                              /* <= 12584959 */
        int32_t g = (L - E) - (cn >> 11);                       /* 2^-16 bit, -2103296..2097152 */
        int32_t a = cap_hi(g, CLIPA);                          /* <= 8 bits */
        w[7] = cn & 2047;
        acc11(&w[1], &w[2], a);                                 /* S: 2^-5 bit, >= -1.08e9, <= 2.7e8 */
        acc11(&w[3], &w[4], cap_lo(a, CLIPA));                 /* F: |F| <= 2.7e8 */
        acc14(&w[5], &w[6], V); }                               /* W: 2^-2 bit^2, <= 2^28 */
    actC = !(fl & 6);
    if (actC) {
        if (D == INT32_MIN || K == INT32_MIN || VC == INT32_MIN) { fl |= 4; actC = 0; }
        else {
            int32_t dn = 90 * VC + w[14];                       /* <= 1509951487 */
            int32_t h = (D - K) - (dn >> 11);                   /* -2834432..4194304 */
            int32_t c = cap_hi(h, CLIPC);                      /* <= 6 bits */
            w[14] = dn & 2047;
            acc11(&w[8], &w[9], c);                             /* N: >= -1.46e9, <= 2.0e8 */
            acc11(&w[10], &w[11], cap_lo(c, CLIPC));           /* G: |G| <= 2.0e8 */
            acc14(&w[12], &w[13], VC); } }                      /* C: 2^-2 bit^2, <= 2^30 */
    t = ++w[0];
    okA = (t >= 16) & (w[5] >= 64);                             /* sum V  >= 16 bits^2, exact floor */
    okC = (t >= 16) & (w[12] >= 128);                           /* sum VC >= 32 bits^2, exact floor */
    WA = w[5] + (w[6] > 0);  WC = w[12] + (w[13] > 0);          /* ceilings, conservative */
    if (okA && !(fl & 1)) for (j = 0; j < 3; j++) ai |= w[1] >= QA[j] + mulsh(PA[j], WA, 15);
    if (okC && actC)      for (j = 0; j < 3; j++) ai |= w[8] >= QC[j] + mulsh(PC[j], WC, 14);
    if (ai) { w[15] = fl | (2 << 3); return 1; }
    if (okA && !(fl & 1) && w[3] < mulsh(PFA, w[5], 15) - QFA) fl |= 1;
    if (okC && actC && w[10] < mulsh(PFC, w[12], 15) - QFC) { fl |= 2; actC = 0; }
    if ((fl & 3) == 3) { w[15] = fl | (1 << 3); return 0; }
    w[15] = fl;
    return actC ? 3 : 2; }

int32_t law_final(const law_state *s)
{   const int32_t *w = s->w; int32_t fl = w[15], t = w[0], okA, okC, aliveA, aliveC, WA, WC, noA, noC;
    if ((fl >> 3) & 3) return ((fl >> 3) & 3) - 1;
    okA = (t >= 16) & (w[5] >= 64);  okC = (t >= 16) & (w[12] >= 128);
    aliveA = !(fl & 1);  aliveC = !(fl & 6);                    /* ran through the whole text */
    WA = w[5] + (w[6] > 0);  WC = w[12] + (w[13] > 0);
    if ((okA && aliveA && ge_z(w[1], WA, KENDA)) || (okC && aliveC && ge_z(w[8], WC, KENDC))) return 1;
    noA = (fl & 1) || (okA && ge_z(mulsh(PKA, w[5], 15) - w[3], WA, KFUTA));
    noC = (fl & 2) || (okC && !(fl & 4) && ge_z(mulsh(PKC, w[12], 15) - w[10], WC, KFUTC));
    return (noA && noC) ? 0 : 2; }
