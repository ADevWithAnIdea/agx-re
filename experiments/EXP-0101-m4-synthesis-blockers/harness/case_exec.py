#!/usr/bin/env python3
"""EXP-0101 per-case executor. Builds the mem input buffer, invokes
tools/agxtest/agxtest.py as a fresh subprocess (splice-and-run on real M4
hardware), parses OUT hex, decodes the case's own oracle word(s), compares.
One case per process invocation (run.py launches one subprocess per case;
never re-run in place). Verbatim architecture from
EXP-0099-m4-lifetime-field-model/harness/case_exec.py.

Usage: case_exec.py --case-index N --run-dir DIR --bin-dir DIR --repo DIR
Prints one JSON object to stdout (the complete case record).
"""
import argparse, json, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import casematrix as CM  # noqa: E402

CARRIER_METAL = "carrier.metal"
OUT_WORDS = CM.OUT_WORDS


def build_mem_file(work):
    p = work / "mem.bin"
    p.write_bytes(b"".join(struct.pack("<f", v) for v in CM.MEM_WORDS))
    return p


def decode_case(c, out_hex):
    """Oracle comparison is always an exact float `==` (the ISA is
    deterministic; EXP-0090/EXP-0099's own standing convention). This is
    exact even for the denormal bit-pattern oracles this experiment's H2
    cases use (e.g. 0x00000100): struct.unpack('<f', ...) round-trips a
    denormal's exact bit pattern to an exact Python float, and IEEE-754
    `==` on two such non-NaN floats is bit-exact -- no separate
    integer/bits comparison path is needed."""
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
    mem_path = build_mem_file(work)
    repo = Path(args.repo)
    argv = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
            "--source", str(EXP / "kernels" / CARRIER_METAL), "--function", "k",
            "--grid", "1", "--tg", "1", "--no-fast-math",
            "--shdump", str(Path(args.bin_dir) / "shdump"),
            "--agxrun", str(Path(args.bin_dir) / "agxrun"),
            "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
            "--workdir", str(work), "--run-timeout", "30",
            "--buf", "1=@%s" % mem_path,
            "--out", "0=%d" % OUT_WORDS,
            "--splice", "_agc.main@0=%s" % c["hex"]]
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
        "i": c["i"], "name": c["name"], "group": c["group"],
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
