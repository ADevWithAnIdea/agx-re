#!/usr/bin/env python3
"""EXP-0089 manifest generator. Hashes every artifact in the experiment tree
except manifest.json itself. States: PRE_GPU (authored tree only) and CAPTURED
(raw/ present). --write regenerates, --check fails closed on any drift."""
import argparse, hashlib, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent

KERNELS = ("adjacent", "near", "far4", "far16", "pressure", "if_boundary", "loop_boundary",
          "lit17_unpack", "lit17_cvt", "discrim3")
PRE_GPU_FILES = ("CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
                 "RESULTS.md", "PROGRESS.md") + tuple(f"kernels/{k}.metal" for k in KERNELS) + (
                 "harness/build.sh", "baseline.py", "casematrix.py", "run.py",
                 "analysis.py", "make_manifest.py", "verify.py")


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
