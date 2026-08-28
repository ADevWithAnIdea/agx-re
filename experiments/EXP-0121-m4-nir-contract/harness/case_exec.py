#!/usr/bin/env python3
"""EXP-0121 per-case executor. ONE case, ONE fresh subprocess invocation of the
appropriate READ-ONLY tool (tools/agxtest/agxtest.py for compute/concurrency,
harness/fsrun for render), decoded and compared against this case's own
host-computed oracle (harness/oracle.py). Prints ONE JSON record to stdout:
{"record": {...GATED...}, "detail": {...NON-GATED, e.g. concurrency raw counts...},
 "timing": {...}}.

Usage: case_exec.py --case-index N --run-dir DIR --bin-dir DIR --repo DIR --work-dir DIR
                     --case-timeout SEC
"""
import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import casematrix as CM  # noqa: E402
import oracle as O  # noqa: E402

OUT_RE = re.compile(r"^OUT (\d+) ([0-9a-fA-F]+)$", re.M)
PIXEL_RE = re.compile(r"^PIXEL(\d) (\d+) (\d+) bgra=([0-9a-f]{8}) rgba_unorm=([-\d.,]+)$", re.M)
BUFFER_RE = re.compile(r"^BUFFER (\d+) hex=([0-9a-fA-F]+)$", re.M)
STATUS_RE = re.compile(r"^STATUS (\S+)$", re.M)
MAIN_ORIG_RE = re.compile(r"^MAIN_ORIG ([0-9a-fA-F]+)$", re.M)
PIPELINE_SOURCE_RE = re.compile(r"^PIPELINE_SOURCE (\S+)$", re.M)


def sha256_hex(b):
    return hashlib.sha256(b).hexdigest()


def decode_words(hexstr, kind):
    raw = bytes.fromhex(hexstr)
    out = []
    for i in range(0, len(raw) - 3, 4):
        word = raw[i:i + 4]
        if kind == "f32":
            out.append(struct.unpack('<f', word)[0])
        elif kind == "i32":
            out.append(struct.unpack('<i', word)[0])
        elif kind == "u32":
            out.append(struct.unpack('<I', word)[0])
        elif kind == "bits":
            out.append(struct.unpack('<I', word)[0])
    return out


def run_compute(c, args):
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
    if not c.get("fastmath", False):
        argv.append("--no-fast-math")
    for idx, raw in c["buffers"].items():
        p = work / f"in_{idx}.bin"
        p.write_bytes(raw)
        argv += ["--buf", f"{idx}=@{p}"]
    for idx, nel in c["out"].items():
        argv += ["--out", f"{idx}={nel}"]
    if c.get("dump_main"):
        argv.append("--dump-main")

    started = time.time()
    timed_out = False
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=args.case_timeout + 15)
        stdout, stderr, exitc = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        stdout, stderr, exitc, timed_out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), \
            (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or ""), None, True
    duration_ms = int((time.time() - started) * 1000)

    status_m = STATUS_RE.search(stdout)
    status = "TIMEOUT" if timed_out else (status_m.group(1) if status_m else "NO_STATUS")
    out_idx = list(c["out"].keys())[0]
    m = OUT_RE.search(stdout)
    observed = decode_words(m.group(2), c["out_type"]) if (m and status == "OK") else None
    main_m = MAIN_ORIG_RE.search(stdout)
    main_hex = main_m.group(1) if main_m else None

    record = {
        "id": c["id"], "item": c["item"], "kind": c["kind"], "kernel": c["kernel"],
        "function": c["function"], "n": c.get("n"), "status": status,
        "main_len": (len(main_hex) // 2) if main_hex else None,
        "main_sha256": sha256_hex(bytes.fromhex(main_hex)) if main_hex else None,
        "observed_sha256": sha256_hex(json.dumps(observed, sort_keys=True).encode()) if observed is not None else None,
    }
    detail = {"id": c["id"], "observed": observed, "main_hex": main_hex, "argv": argv}
    timing = {"id": c["id"], "duration_ms": duration_ms, "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-2000:]}
    return record, detail, timing


def run_render(c, args):
    work = Path(args.work_dir) / c["id"]
    work.mkdir(parents=True, exist_ok=True)
    repo = Path(args.repo)
    kernel_path = EXP / "kernels" / c["kernel"]
    shdump = Path(args.bin_dir) / "shdump"
    fsrun = Path(args.bin_dir) / "fsrun"
    archive = work / "r.bin"
    argv0 = [str(shdump), "-o", str(archive), "--render", "--vertex", c["vertex"],
             "--fragment", c["fragment"], "--no-fast-math", str(kernel_path)]
    r0 = subprocess.run(argv0, capture_output=True, text=True, timeout=args.case_timeout)
    started = time.time()
    rt_count = c.get("rt_count", 1)
    argv = [str(fsrun), "--source", str(kernel_path),
            "--vertex", c["vertex"], "--fragment", c["fragment"],
            "--width", str(c["width"]), "--height", str(c["height"]), "--no-fast-math"]
    # shdump's --render mode only configures colorAttachments[0] (single-RT archive, see
    # tools/shdump/shdump.m); a multi-RT pipeline descriptor cannot be instantiated FROM that
    # archive (FailOnBinaryArchiveMiss -- confirmed PIPELINE_MISS in this experiment's own
    # pilot testing, recorded in PROGRESS.md). For rt_count==1 we still exercise the archived
    # (PIPELINE_SOURCE=archive) path exactly as tools/agxtest documents; for rt_count>1 we let
    # fsrun compile the pipeline directly from source (PIPELINE_SOURCE=compiled) -- functional
    # correctness only, no archive-splice provenance claim for those cases (recorded in the
    # case record's `pipeline_source` field, not silently assumed).
    if rt_count == 1:
        argv = [str(fsrun), "--archive", str(archive)] + argv[1:]
    if "rt_count" in c:
        argv += ["--rt-count", str(c["rt_count"])]
    # a scratch device buffer for kernels that write into device uint* buf(0); use --buf
    # (fill-style; fsrun ECHOES THESE BACK as `BUFFER idx hex=...` after the draw) rather than
    # --buf-u32 (bound but never read back by fsrun -- confirmed in this experiment's pilot).
    buf_bytes = c["width"] * c["height"] * 4 * 4  # up to 4 words/pixel, generous
    argv += ["--buf", f"0={buf_bytes},00"]
    argv += ["--buf-u32", f"1={c['width']},{c['height']}"]
    timed_out = False
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=args.case_timeout)
        stdout, stderr = r.stdout, r.stderr
    except subprocess.TimeoutExpired as e:
        stdout, stderr, timed_out = "", "", True
    duration_ms = int((time.time() - started) * 1000)
    status_m = STATUS_RE.search(stdout)
    status = "TIMEOUT" if timed_out else (status_m.group(1) if status_m else "NO_STATUS")
    pixels = [{"rt": mm.group(1), "x": mm.group(2), "y": mm.group(3), "bgra": mm.group(4)}
              for mm in PIXEL_RE.finditer(stdout)]
    buffers = {mm.group(1): mm.group(2) for mm in BUFFER_RE.finditer(stdout)}
    ps_m = PIPELINE_SOURCE_RE.search(stdout)
    pipeline_source = ps_m.group(1) if ps_m else None

    # structural: extract fragment-stage hex from the (unspliced) archive.
    agxparse_argv = [sys.executable, "-B", str(repo / "tools" / "shdump" / "agxparse.py"),
                      str(archive), "--stage", "fragment", "--extract-hex"]
    rp = subprocess.run(agxparse_argv, capture_output=True, text=True, timeout=30)
    frag_hex = rp.stdout.strip() if rp.returncode == 0 else None

    record = {
        "id": c["id"], "item": c["item"], "kind": c["kind"], "kernel": c["kernel"],
        "fragment": c["fragment"], "status": status, "pipeline_source": pipeline_source,
        "pixels_sha256": sha256_hex(json.dumps(pixels, sort_keys=True).encode()),
        "buffers_sha256": sha256_hex(json.dumps(buffers, sort_keys=True).encode()),
        "frag_len": (len(frag_hex) // 2) if frag_hex else None,
        "frag_sha256": sha256_hex(bytes.fromhex(frag_hex)) if frag_hex else None,
    }
    detail = {"id": c["id"], "pixels": pixels, "buffers": buffers, "frag_hex": frag_hex, "argv0": argv0, "argv": argv}
    timing = {"id": c["id"], "duration_ms": duration_ms, "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-2000:]}
    return record, detail, timing


def run_concurrency(c, args):
    work = Path(args.work_dir) / c["id"]
    work.mkdir(parents=True, exist_ok=True)
    repo = Path(args.repo)
    kernel_path = EXP / "kernels" / c["kernel"]
    pairs = c["pairs"]
    boxes = bytes(24 * pairs)  # 6 u32 words per mailbox, zero-initialized
    iters = struct.pack('<I', c["iterations"])
    spin = struct.pack('<I', c["spin_bound"])
    threadgroups = pairs * 2
    tg_size = 4
    grid = threadgroups * tg_size

    argv = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
            "--source", str(kernel_path), "--function", c["function"],
            "--grid", str(grid), "--tg", str(tg_size), "--int",
            "--shdump", str(Path(args.bin_dir) / "shdump"),
            "--agxrun", str(Path(args.bin_dir) / "agxrun"),
            "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
            "--workdir", str(work), "--run-timeout", str(args.case_timeout),
            "--no-fast-math"]
    for idx, raw in [(0, boxes), (2, iters), (3, spin)]:
        p = work / f"in_{idx}.bin"
        p.write_bytes(raw)
        argv += ["--buf", f"{idx}=@{p}"]
    argv += ["--buf", "1=0,0,0,0", "--out", "1=4"]

    started = time.time()
    timed_out = False
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=args.case_timeout + 15)
        stdout, stderr = r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        stdout, stderr, timed_out = "", "", True
    duration_ms = int((time.time() - started) * 1000)

    status_m = STATUS_RE.search(stdout)
    status = "TIMEOUT" if timed_out else (status_m.group(1) if status_m else "NO_STATUS")
    m = OUT_RE.search(stdout)
    verdict = "harness_error"
    mismatch = prod_to = cons_to = completed = None
    if m and status == "OK":
        vals = decode_words(m.group(2), "i32")
        mismatch, prod_to, cons_to, completed = vals
        expected_completed = pairs * c["iterations"]
        verdict = O.concurrency_verdict(mismatch, prod_to, cons_to, completed, expected_completed)

    record = {
        "id": c["id"], "item": c["item"], "kind": c["kind"], "function": c["function"],
        "pairs": pairs, "fenced": c["fenced"], "repeat": c["repeat"], "status": status,
        "verdict": verdict,
    }
    detail = {"id": c["id"], "mismatch": mismatch, "producer_timeouts": prod_to,
              "consumer_timeouts": cons_to, "completed": completed,
              "expected_completed": pairs * c["iterations"], "argv": argv}
    timing = {"id": c["id"], "duration_ms": duration_ms, "stdout_tail": stdout[-2000:], "stderr_tail": stderr[-1000:]}
    return record, detail, timing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-index", type=int, required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--case-timeout", type=float, default=40.0)
    a = ap.parse_args()

    cases = CM.build_cases()
    c = cases[a.case_index]
    if c["kind"] in ("compute",):
        record, detail, timing = run_compute(c, a)
    elif c["kind"] == "render":
        record, detail, timing = run_render(c, a)
    elif c["kind"] == "concurrency":
        record, detail, timing = run_concurrency(c, a)
    else:
        raise RuntimeError(f"unknown kind {c['kind']}")
    print(json.dumps({"record": record, "detail": detail, "timing": timing}))


if __name__ == "__main__":
    main()
