"""Detection engine: long-form text -> THE DETECT LAW v8.1 verdict, streamed and cost-aware.

Text is split into 200-token windows (the length the law was calibrated on), each scored from a fresh BOS.
Per token, model A (Llama-3.2-1B) gives surprisal, entropy and variance; model B (Llama-3.2-1B-Instruct) gives
the contrast against A; and the window itself gives the repetition signal (was this token already used here, and
how much probability did A put on already-used tokens). The decision is the compiled int32 law (law/detect_v81.c,
the exact file used for the official RAID run), called through ctypes. Reading stops as soon as the law stops.

Two modes, chosen per check (each has its own measured constants, compiled into its own library):
  careful   (default) B = Llama-3.2-1B-Instruct in 4-bit.
  official  B = Llama-3.2-1B-Instruct in full precision, the configuration submitted to the official RAID test.
On 3,200 held-out human RAID texts both modes flagged 0.22% as AI (poetry 1.25%, other genres 0-0.25%).
Backends: MLX on Apple Silicon, PyTorch everywhere else (NVIDIA GPU if present, otherwise CPU); the 4-bit
weights are unpacked exactly for PyTorch. Pick one with DETECT_LAW_BACKEND=mlx|torch.
"""
import ctypes, os, platform, re, sys, threading, time
import numpy as np
from .textnorm import normalize
from ._build import library_path

LAW_VERSION = "v8.1"
A_REPO = "unsloth/Llama-3.2-1B"
MODES = {"careful": "mlx-community/Llama-3.2-1B-Instruct-4bit", "official": "unsloth/Llama-3.2-1B-Instruct"}
DEFAULT_MODE = "careful"
WINDOW, LN2, INT32_MIN = 200, float(np.log(2.0)), -2**31
RANGES = [(-(1 << 21), 0), (-(1 << 21), 0), (0, 1 << 22), (-(1 << 21), 1 << 21), (-(1 << 21), 0), (0, 1 << 24)]
VERDICT = {1: "ai", 0: "no_evidence", 2: "undecided"}
MEANING = {
    "ai": "Statistical evidence of AI generation. A few human texts get this verdict too (0.22% of human RAID texts "
          "in tests, 1.25% of poems), so it is evidence, not proof: route to human review, never to automatic penalties.",
    "no_evidence": "Every signal ruled out an AI-sized effect for the generators this filter covers. "
                   "Not proof of human authorship: frontier models (e.g. Claude) and paraphrased text can evade it.",
    "undecided": "No significant evidence of AI was found, but an AI-sized effect could not be ruled out either. "
                 "Most human texts end here (98% in tests), and so do some AI texts, especially short or paraphrased "
                 "ones. Draw no conclusion.",
}
ARMS = ("surprise", "contrast", "repetition")


class LawState(ctypes.Structure):
    _fields_ = [("w", ctypes.c_int32 * 24)]


_P32 = ctypes.POINTER(ctypes.c_int32)
_LIBS = {}


def _law(mode):
    """The compiled law for one mode (its own measured constants)."""
    if mode not in _LIBS:
        lib = ctypes.CDLL(library_path(mode))
        lib.api_init.argtypes = [ctypes.POINTER(LawState)]; lib.api_init.restype = None
        lib.api_block.argtypes = [ctypes.POINTER(LawState)] + [_P32] * 8 + [ctypes.c_int32]
        lib.api_block.restype = ctypes.c_int32
        for fn in ("api_final", "api_score", "api_tokens"):
            getattr(lib, fn).argtypes = [ctypes.POINTER(LawState)]; getattr(lib, fn).restype = ctypes.c_int32
        lib.api_z.argtypes = [ctypes.POINTER(LawState), _P32]; lib.api_z.restype = None
        _LIBS[mode] = lib
    return _LIBS[mode]


def prose(text, strip_references=True):
    """Keep running prose: drop headings, table cells, equation lead-ins and the reference list."""
    out = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw.replace("•", " ")).strip()
        if not line:
            continue
        if strip_references and re.match(r"^(REFERENCES|References|Bibliography|BIBLIOGRAPHY)\b", line):
            break
        w = line.split()
        if line.endswith(":") or re.search(r"(expressed|represented|calculated|given|defined) as$|is$", line):
            continue
        if (len(w) <= 8 and not line.endswith(".")) or line.lower().startswith(("where ", "keywords")) or len(w) < 6:
            continue
        out.append(line)
    return " ".join(out)


def _q(a, lo, hi):
    """Fixed point 2^-16, exactly as the law's calibration and the official run quantised (float64 rounding)."""
    return np.ascontiguousarray(np.clip(np.rint(np.asarray(a, np.float64) * 65536.0), lo, hi), dtype=np.int32)


def _repeats(ids):
    """R[i] = 1 if token i already appeared earlier in the window; the mask marks, for each position, which
    distinct tokens have already appeared (so Q = A's probability mass on already-used tokens)."""
    first, R = {}, np.zeros(len(ids), np.int32)
    for i, t in enumerate(ids):
        if t in first:
            R[i] = 1
        else:
            first[t] = i
    U = sorted(first)
    mask = np.zeros((len(ids), len(U)), np.float32)
    for j, t in enumerate(U):
        mask[first[t] + 1:, j] = 1.0
    return R, U, mask


def _local(repo):
    """Local folder of a Hugging Face model: the cached copy if present (no network), otherwise download once."""
    from huggingface_hub import snapshot_download
    try:
        return snapshot_download(repo, local_files_only=True)
    except Exception:
        print(f"detect-law: downloading {repo} (one time)...", file=sys.stderr, flush=True)
        return snapshot_download(repo, allow_patterns=["*.json", "*.safetensors", "*.model", "*.txt", "*.tiktoken"])


def _dequant_mlx4(src):
    """Unpack an MLX 4-bit checkpoint into a plain fp16 Hugging Face checkpoint (exact: weight = scale * code + bias)."""
    import json
    from safetensors.numpy import load_file, save_file
    out = os.path.join(os.path.expanduser("~/.cache/detect-law"), os.path.basename(os.path.dirname(os.path.dirname(src))) + "-fp16")
    if os.path.exists(os.path.join(out, "model.safetensors")):
        return out
    cfg = json.load(open(os.path.join(src, "config.json")))
    q = cfg.pop("quantization", None) or {}; cfg.pop("quantization_config", None)
    bits, group = q.get("bits", 4), q.get("group_size", 64)
    W = {}
    for f in sorted(x for x in os.listdir(src) if x.endswith(".safetensors")):
        W.update(load_file(os.path.join(src, f)))
    per = 32 // bits
    res = {}
    for k, v in W.items():
        if k.endswith((".scales", ".biases")):
            continue
        base = k[:-len(".weight")] if k.endswith(".weight") else None
        if base and f"{base}.scales" in W:
            codes = ((v[..., None] >> (np.arange(per, dtype=np.uint32) * bits)) & ((1 << bits) - 1)).reshape(v.shape[0], -1).astype(np.float32)
            sc = np.repeat(W[f"{base}.scales"].astype(np.float32), group, axis=1)
            bi = np.repeat(W[f"{base}.biases"].astype(np.float32), group, axis=1)
            res[k] = (sc * codes + bi).astype(np.float16)
        else:
            res[k] = v.astype(np.float16)
    os.makedirs(out, exist_ok=True)
    cfg["torch_dtype"] = "float16"; cfg.setdefault("architectures", ["LlamaForCausalLM"]); cfg.setdefault("model_type", "llama")
    json.dump(cfg, open(os.path.join(out, "config.json"), "w"), indent=2)
    save_file(res, os.path.join(out, "model.safetensors"), metadata={"format": "pt"})
    return out


def pick_backend():
    want = os.environ.get("DETECT_LAW_BACKEND", "auto").lower()
    if want in ("mlx", "torch"):
        return want
    if sys.platform == "darwin" and platform.machine() == "arm64":
        try:
            import mlx.core, mlx_lm  # noqa: F401
            return "mlx"
        except ImportError:
            pass
    return "torch"


class _MLX:
    name = "mlx"

    def __init__(self, a_repo):
        from mlx_lm import load
        import mlx.core as mx
        self.mx, self._load = mx, load
        self.A, self.tok = load(_local(a_repo))
        self.device = "apple-gpu"

    def load_b(self, repo):
        return self._load(_local(repo))[0]

    def a(self, ids):
        mx = self.mx
        x = mx.array([[self.tok.bos_token_id] + ids]); t = mx.array(ids)[:, None]
        la = self.A(x)[0, :-1].astype(mx.float32)
        lpa = (la - mx.logsumexp(la, axis=-1, keepdims=True)) / LN2
        pa = mx.exp(lpa * LN2)
        L = mx.take_along_axis(lpa, t, axis=-1)[:, 0]; E = mx.sum(pa * lpa, -1); V = mx.sum(pa * (lpa - E[:, None]) ** 2, -1)
        mx.eval(L, E, V)
        return (lpa, pa), [np.array(L), np.array(E), np.array(V)]

    def b(self, ids, ctx, B):
        mx = self.mx
        lpa, pa = ctx
        x = mx.array([[self.tok.bos_token_id] + ids]); t = mx.array(ids)[:, None]
        lb = B(x)[0, :-1].astype(mx.float32)
        dl = (lb - mx.logsumexp(lb, axis=-1, keepdims=True)) / LN2 - lpa
        D = mx.take_along_axis(dl, t, axis=-1)[:, 0]; K = mx.sum(pa * dl, -1); VC = mx.sum(pa * (dl - K[:, None]) ** 2, -1)
        mx.eval(D, K, VC)
        return [np.array(D), np.array(K), np.array(VC)]

    def q(self, ctx, U, mask):
        mx = self.mx
        Q = mx.sum(mx.take(ctx[1], mx.array(U), axis=1) * mx.array(mask), -1)
        mx.eval(Q)
        return np.array(Q)


class _Torch:
    name = "torch"

    def __init__(self, a_repo):
        import torch
        from transformers import AutoTokenizer
        self.torch = torch
        self.device = os.environ.get("DETECT_LAW_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
        if self.device.startswith("cuda"):
            self.dt = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        else:
            self.dt = torch.float32
        path = _local(a_repo)
        self.tok = AutoTokenizer.from_pretrained(path)
        self.A = self._from(path)

    def _from(self, path):
        from transformers import AutoModelForCausalLM
        try:
            m = AutoModelForCausalLM.from_pretrained(path, dtype=self.dt)
        except TypeError:                                  # older transformers
            m = AutoModelForCausalLM.from_pretrained(path, torch_dtype=self.dt)
        return m.to(self.device).eval()

    def load_b(self, repo):
        import json
        path = _local(repo)
        if "quantization" in json.load(open(os.path.join(path, "config.json"))):
            path = _dequant_mlx4(path)                     # same 4-bit weights the Mac runs, unpacked exactly
        return self._from(path)

    def _logp2(self, model, ids):
        torch = self.torch
        x = torch.tensor([[self.tok.bos_token_id] + ids], device=self.device)
        with torch.inference_mode():
            return torch.log_softmax(model(input_ids=x).logits[0, :-1].float(), -1) / LN2

    def a(self, ids):
        torch = self.torch
        lpa = self._logp2(self.A, ids)
        pa = torch.exp(lpa * LN2)
        t = torch.tensor(ids, device=self.device)[:, None]
        L = lpa.gather(-1, t)[:, 0]; E = (pa * lpa).sum(-1); V = (pa * (lpa - E[:, None]) ** 2).sum(-1)
        return (lpa, pa), [x.cpu().numpy() for x in (L, E, V)]

    def b(self, ids, ctx, B):
        torch = self.torch
        lpa, pa = ctx
        dl = self._logp2(B, ids) - lpa
        t = torch.tensor(ids, device=self.device)[:, None]
        D = dl.gather(-1, t)[:, 0]; K = (pa * dl).sum(-1); VC = (pa * (dl - K[:, None]) ** 2).sum(-1)
        return [x.cpu().numpy() for x in (D, K, VC)]

    def q(self, ctx, U, mask):
        torch = self.torch
        pa = ctx[1]
        return (pa[:, torch.tensor(U, device=self.device)] * torch.tensor(mask, device=self.device)).sum(-1).cpu().numpy()


class Engine:
    def __init__(self, mode=None, a_repo=A_REPO, backend=None, b_repo=None):
        self.mode = mode or os.environ.get("DETECT_LAW_MODE", DEFAULT_MODE)
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {sorted(MODES)}")
        self.repos = dict(MODES)
        if b_repo:                                         # custom B for experiments
            self.repos[self.mode] = b_repo
        self.be = (_MLX if (backend or pick_backend()) == "mlx" else _Torch)(a_repo)
        self.tok = self.be.tok
        self.B = {}
        self.lock = threading.Lock()                       # one forward pass at a time
        self._b(self.mode); _law(self.mode)
        self.models = {"A": a_repo, "modes": self.repos, "default_mode": self.mode, "backend": self.be.name, "device": self.be.device}

    def _b(self, mode):
        if mode not in self.B:                             # the other mode's model loads on first use
            self.B[mode] = self.be.load_b(self.repos[mode])
        return self.B[mode]

    def detect(self, text, strip_references=True, prose_only=True, mode=None, max_tokens=None):
        mode = mode or self.mode
        if mode not in MODES:
            raise ValueError(f"mode must be one of {sorted(MODES)}")
        t0 = time.time()
        text = normalize(text)                             # undo zero-width / homoglyph / whitespace tricks
        body = prose(text, strip_references) if prose_only else ""
        if not body:                                       # raw text, paragraph breaks kept, as calibrated
            body = text
        ids = self.tok.encode(body, add_special_tokens=False)
        if max_tokens:                                     # the official RAID run read the first 1,024 tokens
            ids = ids[:max_tokens]
        wins = [ids[i:i + WINDOW] for i in range(0, len(ids), WINDOW)]
        if len(wins) > 1 and len(wins[-1]) < 100:          # merge a short tail, as calibrated
            tail = wins.pop()
            wins[-1] = wins[-1] + tail
        lib, st = _law(mode), LawState()
        lib.api_init(ctypes.byref(st))
        act = None
        with self.lock:
            B = self._b(mode)
            for w in wins:
                ctx, (L, E, V) = self.be.a(w)
                D, K, VC = self.be.b(w, ctx, B)
                R, U, mask = _repeats(w)
                Q = self.be.q(ctx, U, mask)
                cols = [_q(x, lo, hi) for x, (lo, hi) in zip((L, E, V, D, K, VC), RANGES)]
                cols += [np.ascontiguousarray(R, dtype=np.int32),
                         np.ascontiguousarray(np.clip(np.rint(np.asarray(Q, np.float64) * 65536.0), 0, 65536), dtype=np.int32)]
                r = lib.api_block(ctypes.byref(st), *[c.ctypes.data_as(_P32) for c in cols], len(w))
                if r in (0, 1):
                    act = r
                    break
        if act is None:
            act = lib.api_final(ctypes.byref(st))
        read = lib.api_tokens(ctypes.byref(st))
        zs = (ctypes.c_int32 * 3)(); lib.api_z(ctypes.byref(st), zs)
        z = {a: (None if v == INT32_MIN else round(v / 16, 2)) for a, v in zip(ARMS, zs)}
        score = lib.api_score(ctypes.byref(st))
        v = VERDICT[act]
        return {
            "verdict": v, "meaning": MEANING[v], "mode": mode, "law": LAW_VERSION,
            "tokens_in_text": len(ids), "tokens_read": read, "decided_early": read < len(ids),
            "score": round(float(np.sqrt(score / 256.0)), 4),
            "evidence": {
                "surprise_z": z["surprise"], "contrast_z": z["contrast"], "repetition_z": z["repetition"],
                "law_score": score,
                "note": "Each z compares the text with human writing (about 0 for human text; positive = AI-like). "
                        "Surprise: wording more predictable than the reference model expects. Contrast: words chosen "
                        "the way a chat-tuned model chooses them. Repetition: fewer repeated words than the reference "
                        "model predicts (typical of AI sampling with a repetition penalty). score = sqrt(law_score/256), "
                        "the number submitted to RAID; None = not enough text for that signal yet.",
            },
            "latency_ms": round((time.time() - t0) * 1000),
        }
