"""Detection engine: long-form text -> THE DETECT LAW v7 verdict, streamed and cost-aware.

Text is split into 200-token windows (the length the law was calibrated on). Model A
(Llama-3.2-1B) scores every window the law reads; model B (Llama-3.2-1B-Instruct) runs only
while the law asks for it (law_step returns 3). Reading stops as soon as the law stops.
The decision itself is the compiled int32 law (liblaw_v7), called through ctypes.

Two modes, chosen per check:
  careful   (default) B = Llama-3.2-1B-Instruct in 4-bit, the model the law's contrast term was calibrated on.
            Fewer human texts flagged (RAID book summaries 2.5%, reviews 1.0%).
  official  B = Llama-3.2-1B-Instruct in full precision, the configuration scored on the official RAID test set
            (80.08% at 5% FPR without attacks). More human texts flagged (book summaries 8.0%, reviews 3.0%).
Backends: MLX on Apple Silicon, PyTorch everywhere else (NVIDIA GPU if present, otherwise CPU); the 4-bit
weights are unpacked exactly for PyTorch. Pick one with DETECT_LAW_BACKEND=mlx|torch.
"""
import ctypes, os, platform, re, sys, threading, time
import numpy as np
from .textnorm import normalize
from ._build import library_path

LAW_VERSION = "v7"
A_REPO = "unsloth/Llama-3.2-1B"
MODES = {"careful": "mlx-community/Llama-3.2-1B-Instruct-4bit", "official": "unsloth/Llama-3.2-1B-Instruct"}
DEFAULT_MODE = "careful"
WINDOW, LN2, INT32_MIN = 200, float(np.log(2.0)), -2**31
RANGES = [(-(1 << 21), 0), (-(1 << 21), 0), (0, 1 << 22), (-(1 << 21), 1 << 21), (-(1 << 21), 0), (0, 1 << 24)]
VERDICT = {1: "ai", 0: "no_evidence", 2: "undecided"}
MEANING = {
    "ai": "Statistical evidence of AI generation. Some human texts get this verdict too (about 1-2% in tests, more in "
          "some genres), so it is evidence, not proof: route to human review, never to automatic penalties.",
    "no_evidence": "Both signals ruled out an AI-sized effect for the generators this filter covers. "
                   "Not proof of human authorship: frontier models (e.g. Claude) and paraphrased text can evade it.",
    "undecided": "Not enough evidence either way, usually because the text is short. No conclusion should be drawn.",
}


class LawState(ctypes.Structure):
    _fields_ = [("w", ctypes.c_int32 * 16)]


_lib = ctypes.CDLL(library_path())
_lib.law_init.argtypes = [ctypes.POINTER(LawState)]; _lib.law_init.restype = None
_lib.law_step.argtypes = [ctypes.POINTER(LawState)] + [ctypes.c_int32] * 6; _lib.law_step.restype = ctypes.c_int32
_lib.law_final.argtypes = [ctypes.POINTER(LawState)]; _lib.law_final.restype = ctypes.c_int32


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
    return np.clip(np.rint(np.asarray(a, np.float32) * np.float32(65536.0)), lo, hi).astype(np.int32)


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
        self._b(self.mode)
        self.models = {"A": a_repo, "modes": self.repos, "default_mode": self.mode, "backend": self.be.name, "device": self.be.device}

    def _b(self, mode):
        if mode not in self.B:                             # the other mode's model loads on first use
            self.B[mode] = self.be.load_b(self.repos[mode])
        return self.B[mode]

    def detect(self, text, strip_references=True, prose_only=True, mode=None):
        mode = mode or self.mode
        if mode not in MODES:
            raise ValueError(f"mode must be one of {sorted(MODES)}")
        t0 = time.time()
        text = normalize(text)                             # undo zero-width / homoglyph / whitespace tricks
        body = prose(text, strip_references) if prose_only else ""
        if not body:                                       # nothing survived the prose filter: use the raw text
            body = re.sub(r"\s+", " ", text).strip()
        ids = self.tok.encode(body, add_special_tokens=False)
        wins = [ids[i:i + WINDOW] for i in range(0, len(ids), WINDOW)]
        if len(wins) > 1 and len(wins[-1]) < 100:          # merge a short tail, as calibrated
            tail = wins.pop()
            wins[-1] = wins[-1] + tail
        st = LawState(); _lib.law_init(ctypes.byref(st))
        want_b, act, read, b_tok = True, None, 0, 0
        sA = sV = sC = sVC = 0.0
        with self.lock:
            B = self._b(mode)
            for w in wins:
                ctx, (L, E, V) = self.be.a(w)
                b = self.be.b(w, ctx, B) if want_b else None
                qa = [_q(a, lo, hi) for a, (lo, hi) in zip((L, E, V), RANGES[:3])]
                qb = [_q(x, lo, hi) for x, (lo, hi) in zip(b, RANGES[3:])] if b is not None else None
                for i in range(len(w)):
                    use_b = want_b and qb is not None
                    d, k, vc = (int(qb[0][i]), int(qb[1][i]), int(qb[2][i])) if use_b else (INT32_MIN,) * 3
                    r = _lib.law_step(ctypes.byref(st), int(qa[0][i]), int(qa[1][i]), int(qa[2][i]), d, k, vc)
                    read += 1; sA += float(L[i] - E[i]); sV += float(V[i])
                    if use_b:
                        b_tok += 1; sC += float(b[0][i] - b[1][i] - 90 / 2048 * b[2][i]); sVC += float(b[2][i])
                    if r in (0, 1):
                        act = r; break
                    want_b = (r == 3)
                if act is not None:
                    break
        if act is None:
            act = _lib.law_final(ctypes.byref(st))
        v = VERDICT[act]
        return {
            "verdict": v, "meaning": MEANING[v], "mode": mode, "law": LAW_VERSION,
            "tokens_in_text": len(ids), "tokens_read": read, "decided_early": read < len(ids),
            "model_b_tokens": b_tok,
            "evidence": {
                "surprise_bits_per_token": round(sA / max(read, 1), 4),
                "surprise_z": round(sA / np.sqrt(sV), 3) if sV > 0 else None,
                "contrast_bits_per_token": round(sC / max(b_tok, 1), 4) if b_tok else None,
                "contrast_z": round(sC / np.sqrt(sVC), 3) if sVC > 0 else None,
                "note": "Positive surprise = cheaper than the reference model expects (AI-like); positive contrast = "
                        "chosen the way a chat-tuned model chooses. Human text averages about 0 on both.",
            },
            "latency_ms": round((time.time() - t0) * 1000),
        }
