#!/usr/bin/env python3
"""EXP-0126 per-case executor. Invokes tools/agxtest/agxtest.py as a fresh
subprocess (splice-and-run on real M4 hardware), decodes the output buffer,
compares against the case's own recorded oracle. One case per process
invocation (run.py launches one subprocess per case; never re-run in place).

Buffer construction: KERNEL_IO[kernel] gives per-kernel STATIC defaults
(out_buf/out_words, plus an optional default in_buf/in_pack/in_vals and a
static extra_bufs dict, e.g. carrier_dag's unused-but-bound imem buffer).
A case's own "extra_bufs" dict OVERLAYS those defaults key-by-key (a case
that needs a non-default buffer(1) content, or a kernel with NO static
default at all such as carrier_cf, supplies it there). Pack types:
"f32"/"i32"/"u32" (struct-packed floats/ints) or "raw" (bytes passed
through verbatim, already the right length).

Architecture adapted from EXP-0119/case_exec.py (same one-fresh-process-
per-case, splice-via-agxtest.py design); extended for: MODE B splicing into
a real compiled kernel at a NON-zero, symbol-relative offset (H3_MODEB),
variable --grid/--tg (H3), and multiple typed input buffers beyond the
single in_buf/mem convention (H1_CF/H1_LOAD/H3_MODEA).
"""
import argparse, json, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import casematrix as CM  # noqa: E402

KERNEL_FILE = {"carrier": "carrier.metal", "carrier_dag": "carrier_dag.metal",
               "carrier_cf": "carrier_cf.metal", "iunary_popcount": "iunary_popcount.metal"}
KERNEL_FUNC = {"carrier": "k", "carrier_dag": "k", "carrier_cf": "k", "iunary_popcount": "k_popcount"}
PACK_FMT = {"f32": "<f", "u32": "<I", "i32": "<i"}


def pack_buf(pack, vals):
    if pack == "raw":
        return bytes(vals)
    fmt = PACK_FMT[pack]
    return b"".join(struct.pack(fmt, v) for v in vals)


def build_bufs(c, work):
    """Return a list of (idx, path) for every input buffer this case needs,
    per KERNEL_IO defaults overlaid with the case's own extra_bufs."""
    io = CM.KERNEL_IO[c["kernel"]]
    bufs = {}
    static_extra = io.get("extra_bufs") or {}
    for idx, (pack, vals) in static_extra.items():
        bufs[idx] = (pack, vals)
    if io.get("in_pack") is not None:
        bufs[io["in_buf"]] = (io["in_pack"], io["in_vals"])
    for idx, (pack, vals) in (c.get("extra_bufs") or {}).items():
        bufs[idx] = (pack, vals)
    paths = []
    for idx, (pack, vals) in bufs.items():
        p = work / ("buf_%d.bin" % idx)
        p.write_bytes(pack_buf(pack, vals))
        paths.append((idx, p))
    return paths


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
    n_words = io["out_words"]
    repo = Path(args.repo)
    argv = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
            "--source", str(EXP / "kernels" / KERNEL_FILE[kernel]), "--function", KERNEL_FUNC[kernel],
            "--grid", str(c["grid"]), "--tg", str(c["tg"]), "--no-fast-math",
            "--shdump", str(Path(args.bin_dir) / "shdump"),
            "--agxrun", str(Path(args.bin_dir) / "agxrun"),
            "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
            "--workdir", str(work), "--run-timeout", "45",
            "--out", "%d=%d" % (io["out_buf"], n_words)]
    for idx, path in build_bufs(c, work):
        argv += ["--buf", "%d=@%s" % (idx, path)]
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
        "grid": c["grid"], "tg": c["tg"],
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
