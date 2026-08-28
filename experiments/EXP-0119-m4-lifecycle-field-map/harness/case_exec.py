#!/usr/bin/env python3
"""EXP-0119 per-case executor. Invokes tools/agxtest/agxtest.py as a fresh
subprocess (splice-and-run on real M4 hardware), decodes the output buffer,
compares against the case's own recorded oracle. One case per process
invocation (run.py launches one subprocess per case; never re-run in place).

MODE A cases (kernel="carrier"): one splice at offset 0 replacing the whole
`_agc.main` region with a hand-assembled program (isa_helpers.build_program).
MODE B cases (kernel="lit17_unpack"/"lit17_cvt"): zero or more field-level
splices into specific offsets of a real compiled kernel (may be an empty
list for the baseline/no-splice case).

Oracle values of `None` mean EXPLORATORY -- no prediction is asserted for
that word index; `match` is computed only over the non-None oracle keys, and
is trivially True if every key is None (an exploratory-only case is never
scored as an unexpected mismatch; its raw observed values are the point).

Usage: case_exec.py --case-index N --run-dir DIR --bin-dir DIR --repo DIR
Prints one JSON object to stdout (the complete case record).
"""
import argparse, json, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import casematrix as CM  # noqa: E402

KERNEL_FILE = {"carrier": "carrier.metal", "lit17_unpack": "lit17_unpack.metal", "lit17_cvt": "lit17_cvt.metal"}
PACK_FMT = {"f32": "<f", "u32": "<I", "i32": "<i"}


def build_in_file(work, kernel):
    io = CM.KERNEL_IO[kernel]
    fmt = PACK_FMT[io["in_pack"]]
    p = work / "in.bin"
    p.write_bytes(b"".join(struct.pack(fmt, v) for v in io["in_vals"]))
    return p


def decode_case(c, out_hex, n_words):
    raw = bytes.fromhex(out_hex)
    words_f = [struct.unpack("<f", raw[i:i + 4])[0] for i in range(0, min(len(raw), n_words * 4) - 3, 4)]
    words_u = [struct.unpack("<I", raw[i:i + 4])[0] for i in range(0, min(len(raw), n_words * 4) - 3, 4)]
    observed = {}
    ok = True
    for k, expected in c["oracle"].items():
        idx = int(k)
        got = words_f[idx] if idx < len(words_f) else None
        observed[k] = {"f32": got, "u32": (words_u[idx] if idx < len(words_u) else None)}
        if expected is not None:
            ok = ok and (got == expected)
    return observed, ok


def run_one(c, args):
    work = Path(args.run_dir) / "work" / ("case_%03d" % c["i"])
    work.mkdir(parents=True, exist_ok=True)
    kernel = c["kernel"]
    io = CM.KERNEL_IO[kernel]
    in_path = build_in_file(work, kernel)
    n_words = io["out_words"]
    repo = Path(args.repo)
    argv = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
            "--source", str(EXP / "kernels" / KERNEL_FILE[kernel]), "--function", "k",
            "--grid", "1", "--tg", "1", "--no-fast-math",
            "--shdump", str(Path(args.bin_dir) / "shdump"),
            "--agxrun", str(Path(args.bin_dir) / "agxrun"),
            "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
            "--workdir", str(work), "--run-timeout", "45",
            "--buf", "%d=@%s" % (io["in_buf"], in_path),
            "--out", "%d=%d" % (io["out_buf"], n_words)]
    for off, hexbytes in c["splices"]:
        argv += ["--splice", "_agc.main@0x%x=%s" % (off, hexbytes)]
    started = time.time()
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
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
        elif line.startswith("OUT %d " % io["out_buf"]):
            out_hex = line[len("OUT %d " % io["out_buf"]):].strip()
        elif line.startswith("PIPELINE_SOURCE"):
            pipeline_source = line.split(None, 1)[1].strip()
    observed, ok = ({}, False)
    if status == "OK" and out_hex:
        observed, ok = decode_case(c, out_hex, n_words)
    record = {
        "i": c["i"], "name": c["name"], "group": c["group"], "kernel": kernel,
        "splices": ["0x%x=%s" % (off, h) for off, h in c["splices"]],
        "oracle": c["oracle"], "notes": c["notes"],
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
