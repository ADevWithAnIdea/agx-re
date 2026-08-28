#!/usr/bin/env python3
"""EXP-0113 per-case executor. Invokes tools/agxtest/agxtest.py as a fresh
subprocess (splice-and-run on real M4 hardware), parses OUT hex, decodes
each oracle word EITHER as a raw little-endian uint32 OR as an IEEE-754
float32 (per that word's own oracle["kind"]) -- never both, never
reinterpreted implicitly -- and compares to the case's own recorded
oracle. One case per process invocation (run.py launches one subprocess
per case; never re-run in place). Dispatch (--grid/--tg) and buffer
bindings are READ FROM THE CASE / its `carrier` field, not hardcoded --
this experiment splices over FIVE different carriers (kernels/carrier.metal,
loadfwd_carrier.metal, carrier_buf{1,2,3}.metal).

Usage: case_exec.py --case-index N --run-dir DIR --bin-dir DIR --repo DIR
Prints one JSON object to stdout (the complete case record).
"""
import argparse, json, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import casematrix as CM  # noqa: E402

LOADFWD_A_CSV = ",".join(str(v) for v in (1234, 5678, 9, 10))
ZEROS4_CSV = "0,0,0,0"

# per-carrier run spec: buffer bindings (idx -> csv), which buffer index
# holds the output, how many output words to request, and whether the
# INPUT buffers need --int packing (irrelevant to output decode, which is
# always driven by each oracle word's own "kind").
CARRIER_SPECS = {
    "carrier.metal": {"buf": {1: ZEROS4_CSV}, "out_idx": 0, "out_words": 8, "int": False},
    "loadfwd_carrier.metal": {"buf": {0: LOADFWD_A_CSV, 1: ZEROS4_CSV}, "out_idx": 2, "out_words": 8, "int": True},
    "carrier_buf1.metal": {"buf": {}, "out_idx": 0, "out_words": 4, "int": False},
    "carrier_buf2.metal": {"buf": {1: ZEROS4_CSV}, "out_idx": 0, "out_words": 4, "int": False},
    "carrier_buf3.metal": {"buf": {1: ZEROS4_CSV, 2: ZEROS4_CSV}, "out_idx": 0, "out_words": 4, "int": False},
}


def decode_case(c, out_hex):
    raw = bytes.fromhex(out_hex)
    n_words = len(raw) // 4
    observed = {}
    ok = True
    for k, expected in c["oracle"].items():
        idx = int(k)
        if idx >= n_words:
            observed[k] = None
            ok = False
            continue
        word = raw[idx * 4:idx * 4 + 4]
        kind = expected["kind"]
        if kind == "u32":
            got = struct.unpack("<I", word)[0]
        elif kind == "f32":
            got = struct.unpack("<f", word)[0]
        else:
            raise ValueError("unknown oracle kind %r" % (kind,))
        observed[k] = got
        ok = ok and (got == expected["value"])
    return observed, ok


def run_one(c, args):
    work = Path(args.run_dir) / "work" / ("case_%03d" % c["i"])
    work.mkdir(parents=True, exist_ok=True)
    repo = Path(args.repo)
    dispatch = c["dispatch"]
    spec = CARRIER_SPECS[c["carrier"]]
    argv = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
            "--source", str(EXP / "kernels" / c["carrier"]), "--function", "k",
            "--grid", str(dispatch["grid"]), "--tg", str(dispatch["tg"]), "--no-fast-math",
            "--shdump", str(Path(args.bin_dir) / "shdump"),
            "--agxrun", str(Path(args.bin_dir) / "agxrun"),
            "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
            "--workdir", str(work), "--run-timeout", "30"]
    if spec["int"]:
        argv.append("--int")
    for idx, csv in spec["buf"].items():
        argv += ["--buf", "%d=%s" % (idx, csv)]
    argv += ["--out", "%d=%d" % (spec["out_idx"], spec["out_words"])]
    argv += ["--splice", "_agc.main@0=%s" % c["hex"]]
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
    out_prefix = "OUT %d " % spec["out_idx"]
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1].strip()
        elif line.startswith(out_prefix):
            out_hex = line[len(out_prefix):].strip()
        elif line.startswith("PIPELINE_SOURCE"):
            pipeline_source = line.split(None, 1)[1].strip()
    observed, ok = ({}, False)
    if status == "OK" and out_hex:
        observed, ok = decode_case(c, out_hex)
    record = {
        "i": c["i"], "name": c["name"], "group": c["group"], "carrier": c["carrier"],
        "oracle": c["oracle"], "expect_match": c["expect_match"], "notes": c["notes"],
        "dispatch": dispatch,
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
