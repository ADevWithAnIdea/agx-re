#!/usr/bin/env python3
"""EXP-0102 per-case executor. ONE case, ONE fresh subprocess invocation of
tools/agxtest/agxtest.py (compile-our-MSL -> dispatch on real M4 -> readback),
decoded and compared against the case's own host-computed oracle(s)
(analysis/oracle.py, never GPU output). Prints ONE JSON record to stdout.

Large exhaustive-lane outputs (65536 elements) are NOT inlined into the
returned record in full -- a sha256 + summary + bounded mismatch list goes
into the record (kept in the byte-compared 01_results.jsonl), and the full
per-lane array is written to a sibling raw/<run>/full/<case_id>.json file
(still append-only text/JSON evidence, just not part of the tight ledger).

Usage: case_exec.py --case-index N --run-dir DIR --bin-dir DIR --repo DIR --full-dir DIR
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "analysis"))
import casematrix as CM  # noqa: E402

MISMATCH_CAP = 20

# Bytes each output KIND uses per logical element; agxtest.py/agxrun's own
# --out unit is "4-byte words" regardless of the element's true width, so
# the harness must scale NELEMENTS accordingly (a bug this file used to
# have -- see PROGRESS.md pilot-phase note).
WORDS_PER_ELEM = {"u32": 1, "i32": 1, "f32": 1, "half2_bits": 1, "short2": 1,
                  "f32x2": 2, "f32x4": 4, "u64": 2}


def sha256_of(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def _norm(v):
    """tuple -> list so a decoded (list-of-lists) observed value compares
    equal to an oracle value built as a plain tuple."""
    return list(v) if isinstance(v, (tuple, list)) else v


def _eq(a, b):
    """Elementwise equality that treats NaN==NaN as a match (both sides are
    IEEE754 'is this bit pattern a NaN', not a numeric comparison) since a
    literal Python `nan != nan` would otherwise always fail a case whose
    HW-correct, oracle-correct answer is exactly 'both sides are NaN'."""
    a, b = _norm(a), _norm(b)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_eq(x, y) for x, y in zip(a, b))
    try:
        if a != a and b != b:  # both NaN
            return True
    except TypeError:
        pass
    return a == b


def compare(observed, oracle_models):
    """observed: list (possibly of tuples/lists). oracle_models: {name: list}.
    Returns per-model {match_count, total, mismatches[:MISMATCH_CAP]}."""
    out = {}
    n = len(observed)
    for name, exp in oracle_models.items():
        if exp is None or len(exp) != n:
            out[name] = {"error": f"oracle/observed length mismatch or missing "
                                   f"(oracle={None if exp is None else len(exp)}, observed={n})"}
            continue
        mism = []
        match_count = 0
        for i in range(n):
            if _eq(observed[i], exp[i]):
                match_count += 1
            elif len(mism) < MISMATCH_CAP:
                mism.append({"i": i, "observed": observed[i], "expected": exp[i]})
        out[name] = {"match_count": match_count, "total": n,
                     "all_match": match_count == n, "mismatches_sample": mism}
    return out


def run_one(c, args):
    # Scratch build/dispatch directory (compiled Metal binary archives,
    # buffer .bin files) lives OUTSIDE raw/ -- raw/ is text/JSON-only
    # evidence per SUBAGENT_BRIEF.md ("never binary archives, .metallib, or
    # Apple blobs" under raw/). args.work_dir is a sibling scratch tree.
    work = Path(args.work_dir) / c["id"]
    work.mkdir(parents=True, exist_ok=True)
    repo = Path(args.repo)
    kernel_path = EXP / "kernels" / c["kernel"]
    argv = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
            "--source", str(kernel_path), "--function", c["function"],
            "--grid", str(c["grid"]), "--tg", str(c["tg"]),
            "--shdump", str(Path(args.bin_dir) / "shdump"),
            "--agxrun", str(Path(args.bin_dir) / "agxrun"),
            "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
            "--workdir", str(work), "--run-timeout", str(args.case_timeout)]
    if c.get("no_fast_math", True):
        argv.append("--no-fast-math")
    for idx, raw in c["buffers"].items():
        p = work / f"in_{idx}.bin"
        p.write_bytes(raw)
        argv += ["--buf", f"{idx}=@{p}"]
    wpe = WORDS_PER_ELEM[c["out_kind"]]
    for idx, nel in c["out"].items():
        argv += ["--out", f"{idx}={nel * wpe}"]
    if c.get("structural"):
        argv.append("--dump-main")

    started = time.time()
    timed_out, exc = False, None
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=args.case_timeout + 15)
        stdout, stderr, exitc = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        timed_out, exc = True, "TimeoutExpired"
        stdout, stderr, exitc = (e.stdout or ""), (e.stderr or ""), None
    dur_ms = int((time.time() - started) * 1000)

    status, pipeline_source, main_len = "NO_STATUS", None, None
    main_orig_hex = None
    outs_hex = {}
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1].strip()
        elif line.startswith("PIPELINE_SOURCE"):
            pipeline_source = line.split(None, 1)[1].strip()
        elif line.startswith("MAIN_LEN "):
            main_len = int(line.split(None, 1)[1].strip())
        elif line.startswith("MAIN_ORIG "):
            main_orig_hex = line.split(None, 1)[1].strip()
        elif line.startswith("OUT "):
            _, idx, hexbytes = line.split(None, 2)
            outs_hex[int(idx)] = hexbytes.strip()

    decoder = CM.DECODERS[c["out_kind"]]
    decoded = {}
    compared = {}
    for idx in c["out"]:
        hx = outs_hex.get(idx)
        if hx is None:
            decoded[str(idx)] = None
            continue
        raw = bytes.fromhex(hx)
        vals = decoder(raw)
        vals = [list(v) if isinstance(v, tuple) else v for v in vals]
        decoded[str(idx)] = vals

    main_out_idx = max(c["out"].keys())
    observed_main = decoded.get(str(main_out_idx))
    full_dir = Path(args.full_dir)
    full_dir.mkdir(parents=True, exist_ok=True)
    full_ref = None
    inline_observed = observed_main
    observed_sha256 = None
    if status == "OK" and observed_main is not None:
        observed_sha256 = sha256_of(observed_main)
        if len(observed_main) > 200:
            full_path = full_dir / f"{c['id']}.json"
            full_path.write_text(json.dumps({"case_id": c["id"], "observed": observed_main},
                                             sort_keys=True))
            full_ref = str(full_path)
            inline_observed = None
            compared = compare(observed_main, c["oracle"])
            # keep only summaries (no per-model full mismatch dumps beyond cap,
            # already enforced by compare()); good as-is
        else:
            compared = compare(observed_main, c["oracle"])

    record = {
        "i": c["_i"], "id": c["id"], "items": c["items"], "kernel": c["kernel"],
        "function": c["function"], "grid": c["grid"], "notes": c["notes"],
        "status": status, "pipeline_source": pipeline_source,
        "main_len": main_len, "main_hash_sha256": (hashlib.sha256(bytes.fromhex(main_orig_hex)).hexdigest()
                                                     if main_orig_hex else None),
        "main_hex": main_orig_hex if c.get("structural") and (main_len or 0) <= 64 else
                    (f"see full_dir/{c['id']}.main.hex" if main_orig_hex else None),
        "timed_out": timed_out, "exception": exc, "exit": exitc,
        "observed_sha256": observed_sha256,
        "observed_inline": inline_observed,
        "observed_full_ref": full_ref,
        "compared": compared,
    }
    if main_orig_hex and (main_len or 0) > 64:
        (full_dir / f"{c['id']}.main.hex").write_text(main_orig_hex)
    return record, dur_ms, argv, stdout, stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-index", type=int, required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--full-dir", required=True)
    ap.add_argument("--work-dir", required=True,
                     help="scratch build/dispatch dir OUTSIDE raw/ (binary archives, buffer files)")
    ap.add_argument("--case-timeout", type=float, default=40.0)
    a = ap.parse_args()
    cs = CM.build_cases()
    for i, c in enumerate(cs):
        c["_i"] = i
    c = cs[a.case_index]
    record, dur_ms, argv, stdout, stderr = run_one(c, a)
    record["duration_ms"] = dur_ms
    timing = {"i": c["_i"], "id": c["id"], "duration_ms": dur_ms, "argv": argv,
              "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-4000:]}
    print(json.dumps({"record": record, "timing": timing}, sort_keys=True))


if __name__ == "__main__":
    main()
