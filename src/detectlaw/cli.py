"""detect-law FILE [FILE ...] [--json] [--official] [--keep-references] [--raw]

Reads .txt / .md / .docx / .pdf; "-" reads stdin.
"""
import argparse, json, sys


def main(argv=None):
    p = argparse.ArgumentParser(prog="detect-law", description="Explainable AI-text triage (THE DETECT LAW v8.1).")
    p.add_argument("files", nargs="+")
    p.add_argument("--json", action="store_true", help="print the full JSON result")
    p.add_argument("--keep-references", action="store_true", help="also read the reference list")
    p.add_argument("--raw", action="store_true", help="read all text, including headings and table cells")
    p.add_argument("--official", action="store_true", help="official mode: the exact setup submitted to RAID (full-precision model B)")
    a = p.parse_args(argv)
    from .engine import Engine
    from .files import read_text
    eng = Engine(mode="official" if a.official else None)
    for f in a.files:
        try:
            text = sys.stdin.read() if f == "-" else read_text(f)
        except (OSError, ValueError) as e:
            print(f"{f}: {e}", file=sys.stderr)
            continue
        r = eng.detect(text, strip_references=not a.keep_references, prose_only=not a.raw)
        if a.json:
            print(json.dumps({"file": f, **r}, indent=2))
        else:
            e = r["evidence"]
            print(f"{f}: {r['verdict'].upper()}  ({r['mode']} mode; read {r['tokens_read']} of {r['tokens_in_text']} tokens; "
                  f"z: surprise {e['surprise_z']}, contrast {e['contrast_z']}, repetition {e['repetition_z']}; score {r['score']}; "
                  f"{r['latency_ms']} ms)\n  {r['meaning']}")


if __name__ == "__main__":
    main()
