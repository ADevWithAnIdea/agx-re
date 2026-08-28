#!/usr/bin/env python3
"""EXP-0092 manifest generator. Hashes every artifact in the experiment tree
except manifest.json itself. States: PRE_GPU (authored tree only) and CAPTURED
(raw/ present). --write regenerates, --check fails closed on any drift."""
import argparse, hashlib, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent

KERNELS = ("srprobe", "dstprobe", "vdraw_probe", "numwg_probe")
# QUARANTINE_FILES: the retained, untouched, non-evidence partial capture from the
# first (buggy) m4-20260828-run01 attempt -- see QUARANTINE-run01-attempt1.md.
# Present in EVERY state (PRE_GPU and CAPTURED alike); frozen, never edited.
QUARANTINE_FILES = ("QUARANTINE-run01-attempt1.md",) + tuple(
    f"quarantine-m4-20260828-run01/{f}" for f in
    ("00_inputs.json", "01_cases.json", "02_build.json", "04_results.jsonl",
     "04_results_raw.jsonl", "STOP.json"))
PRE_GPU_FILES = ("CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
                 "RESULTS.md", "PROGRESS.md") + tuple(f"kernels/{k}.metal" for k in KERNELS) + (
                 "harness/build.sh", "harness/agxvdraw.m", "harness/agxcdispatch.m",
                 "baseline.py", "casematrix.py", "run.py",
                 "analysis.py", "make_manifest.py", "verify.py") + QUARANTINE_FILES


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def expected(capture):
    if capture:
        rels = [p.relative_to(HERE) for p in HERE.rglob("*")
                if p.is_file() and not p.is_symlink() and p.name != "manifest.json"]
        paths = sorted(str(r) for r in rels if r.parts[0] not in ("work", "selftest"))
    else:
        paths = list(PRE_GPU_FILES)
    return {"schema": 1, "state": "CAPTURED" if capture else "PRE_GPU",
            "artifacts": [{"path": p, "bytes": (HERE / p).stat().st_size,
                           "sha256": sha(HERE / p)} for p in paths]}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args()
    capture = (HERE / "raw").exists()
    exp = expected(capture)
    if a.write:
        HERE.joinpath("manifest.json").write_text(
            json.dumps(exp, indent=2, sort_keys=True) + "\n")
        print("WROTE manifest.json (%s, %d artifacts)" % (exp["state"], len(exp["artifacts"])))
        return 0
    cur = json.loads((HERE / "manifest.json").read_text())
    if cur != exp:
        sys.stderr.write("manifest STALE: regenerate with --write\n")
        return 1
    print("manifest OK (%s, %d artifacts)" % (exp["state"], len(exp["artifacts"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
