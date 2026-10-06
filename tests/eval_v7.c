/* Tests THE DETECT LAW v7 (detect_v7.c, #included verbatim).  The harness plays the
   caller: it supplies model-B inputs from the first token until law_step returns 2,
   stops at a terminal act, else calls law_final at the end of the text.
   Cost = 0.606 ms per token read + 0.556 ms per token with B (measured on this Mac).
     ./eval_v7 check                                code-level checks (run under UBSan too)
     ./eval_v7 null N T mu_a ra mu_c rc seed        synthetic null streams
     ./eval_v7 real N T seed a.bin [b.bin ...]      long streams of random 200-token windows
     ./eval_v7 each a.bin                           every text as its own stream
     ./eval_v7 doc  scan.bin W                      first W windows of a scan file as ONE stream
   BUILD  cc -O2 -Wall -Wextra -Werror -o eval_v7 eval_v7.c -lm                    */
#include "../src/detectlaw/law/detect_v7.c"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define MS_A 0.606
#define MS_B 0.556
#define RHOA 1.06
#define RHOC 1.28
typedef struct { int32_t T; int32_t *a[6]; } Txt;
typedef struct { int act, stop, btok; double ms; } Run;
typedef void (*Src)(void *, int32_t *, int32_t *, int32_t *, int32_t *, int32_t *, int32_t *);

static double ur(void) { return (rand() + 0.5) / ((double)RAND_MAX + 1); }
static double gauss(void) { return sqrt(-2 * log(ur())) * cos(6.283185307179586 * ur()); }
static int32_t cl(double x, int32_t lo, int32_t hi) { return x < lo ? lo : x > hi ? hi : (int32_t)lrint(x); }

/* ---------- the same rule in real numbers (the specification the integers must match) ---------- */
typedef struct { double S, F, W, N, G, C; int t, fl; } Sh;   /* fl: 1 A out, 2 C out, 4 C declined */
static void sh_add(Sh *h, int32_t L, int32_t E, int32_t V, int32_t D, int32_t K, int32_t VC, int withB)
{   double a = ((double)L - E - 3.0 * V / 2048) / 65536; if (a > 8) a = 8;
    h->S += a; h->F += a < -8 ? -8 : a; h->W += V / 65536.0;
    if (!(h->fl & 6)) { if (!withB) h->fl |= 4; else {
        double c = ((double)D - K - 90.0 * VC / 2048) / 65536; if (c > 6) c = 6;
        h->N += c; h->G += c < -6 ? -6 : c; h->C += VC / 65536.0; } }
    h->t++; }
/* margins in z units (positive = the condition holds); smallest |margin| over live decisions */
static int sh_step(Sh *h, double *minm)
{   int j, ai = 0, okA = h->t >= 16 && h->W >= 16, okC = h->t >= 16 && h->C >= 32, aC = !(h->fl & 6); double m;
    *minm = 1e9;
    if (okA && !(h->fl & 1)) for (j = 0; j < 3; j++) { m = (h->S - (QA[j] / 32.0 + PA[j] * h->W / 262144.0)) / sqrt(RHOA * h->W); ai |= m >= 0; if (fabs(m) < *minm) *minm = fabs(m); }
    if (okC && aC) for (j = 0; j < 3; j++) { m = (h->N - (QC[j] / 32.0 + PC[j] * h->C / 131072.0)) / sqrt(RHOC * h->C); ai |= m >= 0; if (fabs(m) < *minm) *minm = fabs(m); }
    if (ai) return 1;
    if (okA && !(h->fl & 1)) { m = (PFA * h->W / 262144.0 - QFA / 32.0 - h->F) / sqrt(RHOA * h->W); if (fabs(m) < *minm) *minm = fabs(m); if (m > 0) h->fl |= 1; }
    if (okC && aC) { m = (PFC * h->C / 262144.0 - QFC / 32.0 - h->G) / sqrt(RHOC * h->C); if (fabs(m) < *minm) *minm = fabs(m); if (m > 0) h->fl |= 2; }
    if ((h->fl & 3) == 3) return 0;
    return (h->fl & 6) ? 2 : 3; }
static int sh_final(Sh *h, double *minm)
{   int okA = h->t >= 16 && h->W >= 16, okC = h->t >= 16 && h->C >= 32, nA, nC; double m;
    *minm = 1e9;
    if (okA && !(h->fl & 1)) { m = (h->S - sqrt(KENDA * h->W / 256)) / sqrt(RHOA * h->W); *minm = fabs(m); if (m >= 0) return 1; }
    if (okC && !(h->fl & 6)) { m = (h->N - sqrt(KENDC * h->C / 256)) / sqrt(RHOC * h->C); if (fabs(m) < *minm) *minm = fabs(m); if (m >= 0) return 1; }
    nA = (h->fl & 1) != 0; nC = (h->fl & 2) != 0;
    if (!nA && okA) { m = (PKA * h->W / 262144.0 - h->F - sqrt(KFUTA * h->W / 256)) / sqrt(RHOA * h->W); if (fabs(m) < *minm) *minm = fabs(m); nA = m >= 0; }
    if (!nC && okC && !(h->fl & 4)) { m = (PKC * h->C / 262144.0 - h->G - sqrt(KFUTC * h->C / 256)) / sqrt(RHOC * h->C); if (fabs(m) < *minm) *minm = fabs(m); nC = m >= 0; }
    return (nA && nC) ? 0 : 2; }

static long long viol = 0, cmp = 0, disagree = 0;
static Run run(Src src, void *ctx, int T, int check, int declineB)
{   law_state s; Sh h; Run r = {2, T, 0, 0}; int i, wantB = 1, diverged = 0; double mm;
    memset(&h, 0, sizeof h); law_init(&s);
    for (i = 0; i < T; i++) {
        int32_t L, E, V, D, K, VC, x; int withB = wantB && !declineB;
        src(ctx, &L, &E, &V, &D, &K, &VC);
        if (!withB) D = K = VC = INT32_MIN;
        x = law_step(&s, L, E, V, D, K, VC);
        r.ms += MS_A + (withB ? MS_B : 0); r.btok += withB;
        if (check && !diverged) { int y; sh_add(&h, L, E, V, D, K, VC, withB); y = sh_step(&h, &mm); cmp++;
            if (y != x) { diverged = 1; disagree++; if (mm > 0.02) viol++; } }
        if (x == 0 || x == 1) { r.act = x; r.stop = i + 1; return r; }
        wantB = (x == 3); }
    r.act = law_final(&s);
    if (check && !diverged) { int y = sh_final(&h, &mm); cmp++; if (y != r.act) { disagree++; if (mm > 0.02) viol++; } }
    return r; }

/* ---------- sources ---------- */
typedef struct { double mua, ra, muc, rc; } Syn;
static void syn_src(void *c, int32_t *L, int32_t *E, int32_t *V, int32_t *D, int32_t *K, int32_t *VC)
{   Syn *p = c; double v = 0.2 + 22 * ur(), vc = 0.1 + 5.5 * ur(), e = -(2 + 8 * ur()), k = -(0.5 + 4 * ur());
    *E = cl(e * 65536, -(1 << 21), 0); *V = cl(v * 65536, 0, 1 << 22);
    *L = cl((e + 3.0 / 2048 * v + p->mua * v / 12.2 + sqrt(p->ra * v) * gauss()) * 65536, -(1 << 21), 0);
    *K = cl(k * 65536, -(1 << 21), 0); *VC = cl(vc * 65536, 0, 1 << 24);
    *D = cl((k + 90.0 / 2048 * vc + p->muc * vc / 3.71 + sqrt(p->rc * vc) * gauss()) * 65536, -(1 << 21), 1 << 21); }
typedef struct { Txt *t[8]; int n[8], nf, seq, k, pos; Txt *cur; } Real;
static void real_src(void *c, int32_t *L, int32_t *E, int32_t *V, int32_t *D, int32_t *K, int32_t *VC)
{   Real *p = c;
    if (!p->cur || p->pos >= p->cur->T) {
        if (p->seq) p->cur = &p->t[0][p->k++];
        else { int f = rand() % p->nf; p->cur = &p->t[f][rand() % p->n[f]]; }
        p->pos = 0; }
    *L = p->cur->a[0][p->pos]; *E = p->cur->a[1][p->pos]; *V = p->cur->a[2][p->pos];
    *D = p->cur->a[3][p->pos]; *K = p->cur->a[4][p->pos]; *VC = p->cur->a[5][p->pos]; p->pos++; }
static Txt *readbin(const char *path, int *n)
{   FILE *f = fopen(path, "rb"); Txt *x; int32_t k, j, nn;
    if (!f || fread(&nn, 4, 1, f) != 1) { fprintf(stderr, "cannot read %s\n", path); exit(1); }
    *n = nn; x = calloc(nn, sizeof *x);
    for (k = 0; k < nn; k++) { if (fread(&x[k].T, 4, 1, f) != 1) exit(1);
        for (j = 0; j < 6; j++) { x[k].a[j] = malloc(4 * x[k].T); if (fread(x[k].a[j], 4, x[k].T, f) != (size_t)x[k].T) exit(1); } }
    fclose(f); return x; }
static int cmpi(const void *a, const void *b) { return *(const int *)a - *(const int *)b; }
static void report(const char *label, Run *r, int N)
{   int i, c[3] = {0, 0, 0}, *st = malloc(N * sizeof *st); double ms = 0, b = 0, tk = 0;
    for (i = 0; i < N; i++) { c[r[i].act]++; ms += r[i].ms; b += r[i].btok; tk += r[i].stop; st[i] = r[i].stop; }
    qsort(st, N, sizeof *st, cmpi);
    printf("%s n=%d  AI %.2f%%  no-evidence %.2f%%  undecided %.2f%% | tokens read mean %.0f (median %d), with B %.0f | cost %.0f ms/text\n",
           label, N, 100.0 * c[1] / N, 100.0 * c[0] / N, 100.0 * c[2] / N, tk / N, st[N / 2], b / N, ms / N);
    free(st); }

static int check(void)
{   int bad = 0, k;
    puts("1. ge_z, with the four k the law uses, vs X > 0 && X*X >= k*W in int64");
    {   long long t; int b = 0, lib = 0; srand(1);
        for (t = 0; t < 3000000; t++) {
            static const int32_t KS[4] = {KENDA, KENDC, KFUTA, KFUTC};
            int32_t W = (int32_t)(((long long)rand() * 1024 + rand() % 1024) % ((1 << 30) + 2)), kk = KS[rand() % 4], X;
            double bnd = sqrt((double)kk * W); X = (int32_t)(bnd * (0.9 + 0.2 * ur())) + (rand() % 3) - 1;
            {   int got = ge_z(X, W, kk), want = X > 0 && (long long)X * X >= (long long)kk * W;
                if (got && !want) b++;                       /* never fires where the exact test does not */
                if (!got && want && X > bnd * 1.001 + 2) lib++; } }  /* misses only within its scaling error */
        printf("    fired where exact does not: %d   missed beyond 0.1%% + 2 units: %d   (of 3,000,000)\n", b, lib); bad += b + lib; }
    puts("2. PRECISION vs the same rule in real numbers (whole streams, step by step and final)");
    {   Syn p; srand(2); viol = cmp = disagree = 0;
        for (k = 0; k < 6000; k++) { p.mua = 1.2 * ur(); p.ra = 0.9 + 0.4 * ur(); p.muc = 0.8 * ur(); p.rc = 0.9 + 0.5 * ur();
                                     run(syn_src, &p, 16 + rand() % 4000, 1, (k % 7) == 0); }
        printf("    %lld comparisons, %lld disagreements, %lld of them with margin > 0.02 z (violations)\n", cmp, disagree, viol); bad += (int)viol; }
    puts("3. WORST-CASE STREAMS of 2^20 tokens at the corners of the input range (UBSan catches overflow)");
    {   static const int32_t le[2] = {-(1 << 21), 0}, dd[2] = {-(1 << 21), 1 << 21}, vv[2] = {0, 1 << 22}, vc[2] = {0, 1 << 24};
        int c, i; for (c = 0; c < 64; c++) { law_state s; law_init(&s);
            for (i = 0; i < (1 << 20); i++) { int x = law_step(&s, le[c & 1], le[(c >> 1) & 1], vv[(c >> 2) & 1], dd[(c >> 3) & 1], le[(c >> 4) & 1], vc[(c >> 5) & 1]);
                if (x < 0 || x > 3) bad++; s.w[15] &= 7; }        /* clear the latch to keep accumulating */
            { int y = law_final(&s); if (y < 0 || y > 2) bad++; } }
        puts("    64 corner streams of 1,048,576 tokens run (latch cleared each step)"); }
    printf("%s  %d failure%s\n", bad ? "NOT CLEAN" : "CLEAN", bad, bad == 1 ? "" : "s");
    return bad != 0; }

int main(int argc, char **argv)
{   if (argc < 2) { fprintf(stderr, "see header\n"); return 1; }
    if (!strcmp(argv[1], "check")) return check();
    if (!strcmp(argv[1], "null")) { int N = atoi(argv[2]), T = atoi(argv[3]), i; Syn p = {atof(argv[4]), atof(argv[5]), atof(argv[6]), atof(argv[7])};
        Run *r = malloc(N * sizeof *r); srand(atoi(argv[8])); for (i = 0; i < N; i++) r[i] = run(syn_src, &p, T, 0, 0); report("", r, N); return 0; }
    if (!strcmp(argv[1], "real")) { int N = atoi(argv[2]), T = atoi(argv[3]), i; Real p; Run *r = malloc(N * sizeof *r);
        memset(&p, 0, sizeof p); srand(atoi(argv[4]));
        for (p.nf = 0; 5 + p.nf < argc && p.nf < 8; p.nf++) p.t[p.nf] = readbin(argv[5 + p.nf], &p.n[p.nf]);
        for (i = 0; i < N; i++) { p.cur = 0; r[i] = run(real_src, &p, T, 0, 0); } report("", r, N); return 0; }
    if (!strcmp(argv[1], "each")) { int n, i; Txt *x = readbin(argv[2], &n); Real p; Run *r = malloc(n * sizeof *r);
        memset(&p, 0, sizeof p); p.nf = 1; p.seq = 1;
        for (i = 0; i < n; i++) { p.t[0] = &x[i]; p.k = 0; p.cur = 0; r[i] = run(real_src, &p, x[i].T, 0, 0); } report("", r, n); return 0; }
    if (!strcmp(argv[1], "doc")) { int n, W = atoi(argv[3]), T = 0, i; Txt *x = readbin(argv[2], &n); Real p; Run r;
        memset(&p, 0, sizeof p); p.nf = 1; p.seq = 1; p.t[0] = x; for (i = 0; i < W; i++) T += x[i].T;
        r = run(real_src, &p, T, 0, 0);
        printf("one stream, %d tokens: verdict %s at token %d | tokens with B %d | cost %.0f ms (every token through both models: %.0f ms)\n",
               T, r.act == 1 ? "AI" : r.act == 0 ? "NO EVIDENCE" : "UNDECIDED", r.stop, r.btok, r.ms, T * (MS_A + MS_B));
        return 0; }
    return 1; }
