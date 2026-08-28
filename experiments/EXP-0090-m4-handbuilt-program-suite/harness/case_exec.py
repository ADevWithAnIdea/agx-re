#!/usr/bin/env python3
"""EXP-0090 per-case executor. Builds input buffers for one case (from
casematrix.py), invokes tools/agxtest/agxtest.py as a fresh subprocess
(splice-and-run on real M4 hardware), parses the raw OUT hex, decodes the
program-specific oracle fields, and compares. Single case per process
invocation (the caller -- run.py -- launches one subprocess per case).

Usage: case_exec.py --case-index N --run-dir DIR --bin-dir DIR --repo DIR
Prints one JSON object to stdout (the complete case record).
"""
import argparse, json, os, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(EXP.parents[1] / "tools" / "agx-isa"))
import casematrix as CM   # noqa: E402
import isa_helpers as H   # noqa: E402

CARRIER_METAL = {"p1": "carrier_p1.metal", "p2": "carrier_p2.metal", "p3": "carrier_p3.metal"}
OUT_WORDS = {"p1": 8, "p2": 64, "p3": 1}


def build_inputs(c, work):
    prog = c["params"]
    kind = c["program"]
    files = {}
    if kind == "p1":
        files[1] = work / "fin.bin"
        files[1].write_bytes(b"\x00" * 16)   # unused (P1 seeds via immediates, not device_load)
        files[2] = work / "iA.bin"
        files[2].write_bytes(struct.pack("<i", prog["ia0"]) + b"\x00" * 12)
    elif kind == "p2":
        files[1] = work / "mem.bin"
        files[1].write_bytes(b"".join(struct.pack("<f", v) for v in CM.MEM_WORDS))
    elif kind == "p3":
        files[1] = work / "a.bin"
        files[1].write_bytes(struct.pack("<f", prog["a_val"]))
        files[2] = work / "n.bin"
        files[2].write_bytes(struct.pack("<i", prog["n_val"]))
    return files


def decode_case(c, out_hex):
    raw = bytes.fromhex(out_hex)
    words_f = [struct.unpack("<f", raw[i:i + 4])[0] for i in range(0, len(raw) - 3, 4)]
    words_u = [struct.unpack("<I", raw[i:i + 4])[0] for i in range(0, len(raw) - 3, 4)]
    kind = c["program"]
    observed = {}
    ok = True
    if kind == "p1":
        observed["out0"] = words_f[0] if len(words_f) > 0 else None
        observed["out1_int_bits"] = words_u[4] if len(words_u) > 4 else None
        ok = (observed["out0"] == c["oracle"]["out0"] and
              observed["out1_int_bits"] == c["oracle"]["out1_int_bits"])
    elif kind == "p2":
        bo_m = c["oracle"]["store_byte_off_main"]
        wm = bo_m // 4
        observed["store_val_main_bits"] = words_u[wm] if wm < len(words_u) else None
        ok = observed["store_val_main_bits"] == c["oracle"]["store_val_main_bits"]
    elif kind == "p3":
        observed["out0"] = words_f[0] if len(words_f) > 0 else None
        ok = observed["out0"] == c["oracle"]["out0"]
    return observed, ok


def run_one(c, args):
    work = Path(args.run_dir) / "work" / ("case_%03d" % c["i"])
    work.mkdir(parents=True, exist_ok=True)
    files = build_inputs(c, work)
    repo = Path(args.repo)
    argv = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
            "--source", str(EXP / "kernels" / CARRIER_METAL[c["program"]]), "--function", "k",
            "--grid", "1", "--tg", "1", "--no-fast-math",
            "--shdump", str(Path(args.bin_dir) / "shdump"),
            "--agxrun", str(Path(args.bin_dir) / "agxrun"),
            "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
            "--workdir", str(work), "--run-timeout", "30"]
    for idx, path in files.items():
        argv += ["--buf", "%d=@%s" % (idx, path)]
    argv += ["--out", "0=%d" % OUT_WORDS[c["program"]]]
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
        "i": c["i"], "name": c["name"], "item": c["item"], "program": c["program"],
        "params": c["params"], "oracle": c["oracle"], "argv": argv,
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
