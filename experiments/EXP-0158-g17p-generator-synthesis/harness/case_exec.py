#!/usr/bin/env python3
"""EXP-0112 per-case executor. Builds the required input buffer(s) for the
case's carrier, invokes tools/agxtest/agxtest.py as a fresh subprocess
(splice-and-run on real M4 hardware), parses OUT hex, decodes the case's
own oracle word(s), compares. One case per process invocation (run.py
launches one subprocess per case; never re-run in place). Architecture
verbatim-adapted from EXP-0101/EXP-0090's own harness/case_exec.py (same
gate machinery; this experiment's cases are whole GENERATED programs
across two different carriers instead of single hand-built splices).

Usage: case_exec.py --case-index N --run-dir DIR --bin-dir DIR --repo DIR
Prints one JSON object to stdout (the complete case record).
"""
import argparse, json, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import casematrix as CM  # noqa: E402
import generator as G    # noqa: E402

CARRIER_DAG = "carrier_dag.metal"
CARRIER_CF = "carrier_cf.metal"


def build_dag_buffers(work):
    mem_path = work / "mem.bin"
    mem_path.write_bytes(b"".join(struct.pack("<f", v) for v in G.MEM_WORDS))
    imem_path = work / "imem.bin"
    imem_path.write_bytes(b"".join(struct.pack("<i", v) for v in G.IMEM_WORDS))
    return mem_path, imem_path


def decode_case(c, out_hex):
    """Exact float `==` oracle comparison (the ISA is deterministic; every
    prior experiment's standing convention) -- exact even for bit-pattern
    oracles (IADD_ANCHOR) since struct.unpack round-trips a bit pattern to
    an exact Python float and IEEE-754 `==` on two non-NaN floats is
    bit-exact. (generator.py/families.py both deliberately keep every
    oracle value finite and non-NaN-shaped -- see their own docstrings.)"""
    raw = bytes.fromhex(out_hex)
    words_f = [struct.unpack("<f", raw[i:i + 4])[0] for i in range(0, len(raw) - 3, 4)]
    observed = {}
    ok = True
    for k, expected in c["oracle"].items():
        idx = int(k)
        got = words_f[idx] if idx < len(words_f) else None
        observed[k] = got
        ok = ok and (got == expected)
    return observed, ok


def run_one(c, args):
    work = Path(args.run_dir) / "work" / ("case_%03d" % c["i"])
    work.mkdir(parents=True, exist_ok=True)
    repo = Path(args.repo)
    out_words = max(int(k) for k in c["oracle"]) + 1

    if c["carrier"] == "dag":
        mem_path, imem_path = build_dag_buffers(work)
        argv = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
                "--source", str(EXP / "kernels" / CARRIER_DAG), "--function", "k",
                "--grid", "1", "--tg", "1", "--no-fast-math",
                "--shdump", str(Path(args.bin_dir) / "shdump"),
                "--agxrun", str(Path(args.bin_dir) / "agxrun"),
                "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
                "--workdir", str(work), "--run-timeout", "30",
                "--buf", "1=@%s" % mem_path,
                "--buf", "2=@%s" % imem_path,
                "--out", "0=%d" % out_words,
                "--splice", "_agc.main@0=%s" % c["hex"]]
    elif c["carrier"] == "cf":
        a_path = work / "a.bin"
        a_path.write_bytes(struct.pack("<f", c["cf_a"]))
        n_path = work / "n.bin"
        n_path.write_bytes(struct.pack("<i", c["cf_n"]))
        argv = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
                "--source", str(EXP / "kernels" / CARRIER_CF), "--function", "k",
                "--grid", "1", "--tg", "1", "--no-fast-math",
                "--shdump", str(Path(args.bin_dir) / "shdump"),
                "--agxrun", str(Path(args.bin_dir) / "agxrun"),
                "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
                "--workdir", str(work), "--run-timeout", "30",
                "--buf", "1=@%s" % a_path,
                "--buf", "2=@%s" % n_path,
                "--out", "0=%d" % out_words,
                "--splice", "_agc.main@0=%s" % c["hex"]]
    else:
        raise ValueError("unknown carrier %r" % c["carrier"])

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
        "oracle": c["oracle"], "expect_match": c["expect_match"], "notes": c["notes"],
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
