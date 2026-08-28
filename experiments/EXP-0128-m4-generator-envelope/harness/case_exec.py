#!/usr/bin/env python3
"""EXP-0128 per-case executor. Builds the required input buffer(s) for the
case's carrier, invokes tools/agxtest/agxtest.py as a fresh subprocess
(splice-and-run on real M4 hardware), parses OUT hex, decodes the case's
own oracle word(s), compares. One case per process invocation (run.py
launches one subprocess per case; never re-run in place). Architecture
verbatim-adapted from EXP-0112/EXP-0101/EXP-0090's own harness/case_exec.py.

Usage: case_exec.py --case-index N --run-dir DIR --bin-dir DIR --repo DIR
Prints one JSON object to stdout (the complete case record).
"""
import argparse, json, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import casematrix as CM  # noqa: E402
import families as F     # noqa: E402

CARRIER_DAG = "carrier_dag.metal"


def decode_case(c, out_hex):
    """`c['mode']` selects int32 vs float32 word decoding for BOTH the
    observed bytes and the (already correctly-typed) oracle dict values.
    Exact `==` comparison throughout -- int32 is trivially exact; every
    float32 oracle in this experiment is produced via isa_helpers.f32 (an
    exact IEEE-754 round-trip), matching every prior experiment's standing
    convention (EXP-0112 decode_case's own docstring)."""
    raw = bytes.fromhex(out_hex)
    if c["mode"] == "int":
        words = [struct.unpack("<i", raw[i:i + 4])[0] for i in range(0, len(raw) - 3, 4)]
    else:
        words = [struct.unpack("<f", raw[i:i + 4])[0] for i in range(0, len(raw) - 3, 4)]
    observed = {}
    ok = True
    for k, expected in c["oracle"].items():
        idx = int(k)
        got = words[idx] if idx < len(words) else None
        observed[k] = got
        ok = ok and (got == expected)
    return observed, ok


def run_one(c, args):
    work = Path(args.run_dir) / "work" / ("case_%03d" % c["i"])
    work.mkdir(parents=True, exist_ok=True)
    repo = Path(args.repo)
    out_words = max(int(k) for k in c["oracle"]) + 1

    mem_path = work / "mem.bin"
    mem_path.write_bytes(b"".join(struct.pack("<f", v) for v in F.MEM_WORDS))
    imem_path = work / "imem.bin"
    imem_path.write_bytes(b"\x00" * 256)  # unused by every case; present only so agxtest's
                                            # --buf 2 matches carrier_dag.metal's 3-buffer signature

    argv = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
            "--source", str(EXP / "kernels" / CARRIER_DAG), "--function", "k",
            "--grid", "1", "--tg", "1", "--no-fast-math",
            "--shdump", str(Path(args.bin_dir) / "shdump"),
            "--agxrun", str(Path(args.bin_dir) / "agxrun"),
            "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
            "--workdir", str(work), "--run-timeout", "20",
            "--buf", "1=@%s" % mem_path,
            "--buf", "2=@%s" % imem_path,
            "--out", "0=%d" % out_words,
            "--splice", "_agc.main@0=%s" % c["hex"]]
    if c["mode"] == "int":
        argv.append("--int")

    started = time.time()
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=45)
        timed_out, exc = False, None
        stdout, stderr, exitc = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        timed_out, exc = True, "TimeoutExpired"
        stdout, stderr, exitc = (e.stdout or ""), (e.stderr or ""), None
    dur_ms = int((time.time() - started) * 1000)
    status, out_hex, pipeline_source = "NO_STATUS", None, None
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1].strip()
        elif line.startswith("OUT 0 "):
            out_hex = line[len("OUT 0 "):].strip()
        elif line.startswith("PIPELINE_SOURCE"):
            pipeline_source = line.split(None, 1)[1].strip()
    observed, ok = ({}, False)
    if status == "OK" and out_hex:
        observed, ok = decode_case(c, out_hex)
    record = {
        "i": c["i"], "name": c["name"], "group": c["group"], "carrier": c["carrier"],
        "mode": c["mode"], "oracle": c["oracle"], "expect_match": c["expect_match"], "notes": c["notes"],
        "argv": argv,
        "timed_out": timed_out, "exception": exc, "exit": exitc,
        "status": status, "pipeline_source": pipeline_source, "out_hex": out_hex,
        "observed": observed, "match": ok, "stdout": stdout, "stderr": stderr,
    }
    return record, dur_ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-index", type=int, required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--repo", required=True)
    a = ap.parse_args()
    cs = CM.build_cases()
    c = cs[a.case_index]
    record, dur_ms = run_one(c, a)
    record["duration_ms"] = dur_ms
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
