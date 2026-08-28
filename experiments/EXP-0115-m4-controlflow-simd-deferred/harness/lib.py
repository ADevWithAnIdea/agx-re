#!/usr/bin/env python3
"""lib.py -- EXP-0115 shared execution helpers.

Adapted from EXP-0104's harness/lib.py (own-authored, reused pattern). Wraps
the read-only tools (this experiment's own work/bin/{shdump,agxrun,agxrender,
agxparse.py} builds of the read-only tools/shdump + tools/agxtest sources, and
tools/agx-isa/agxisa.py) so every case in matrix.py runs as its OWN subprocess
with a hard timeout. No Apple binary is inspected anywhere in this file; every
byte compiled/spliced/run is the compiled form of our own MSL in
../kernels/*.metal or ../kernels/deep/*.metal.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(EXP_ROOT))
WORK = os.path.join(EXP_ROOT, "work")
BIN = os.path.join(WORK, "bin")
KERNELS = os.path.join(EXP_ROOT, "kernels")
AGXTEST_PY = os.path.join(REPO_ROOT, "tools", "agxtest", "agxtest.py")
AGXISA_PY = os.path.join(REPO_ROOT, "tools", "agx-isa", "agxisa.py")

SHDUMP = os.path.join(BIN, "shdump")
AGXRUN = os.path.join(BIN, "agxrun")
AGXRENDER = os.path.join(BIN, "agxrender")
AGXPARSE = os.path.join(BIN, "agxparse.py")


def sh(cmd, timeout):
    """Run CMD (list) with a hard wall-clock timeout. Returns (rc, stdout, stderr, timed_out)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr, False
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, (bytes, bytearray)) else (e.stdout or "")
        err = e.stderr.decode() if isinstance(e.stderr, (bytes, bytearray)) else (e.stderr or "")
        return -1, out, err, True


def parse_agxtest_stdout(stdout):
    """Parse agxtest.py's line-oriented stdout into a dict."""
    d = {"status": "UNKNOWN", "results": {}, "splices": [], "gputime_ns": None,
         "main_len": None}
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            d["status"] = line.split(None, 1)[1].strip()
        elif line.startswith("GPUTIME_NS "):
            d["gputime_ns"] = int(line.split(None, 1)[1])
        elif line.startswith("MAIN_LEN "):
            d["main_len"] = int(line.split(None, 1)[1])
        elif line.startswith("RESULT "):
            parts = line.split()
            idx = int(parts[1])
            vals = [int(v) for v in parts[2:]]
            d["results"][idx] = vals
        elif line.startswith("SPLICE "):
            d["splices"].append(line[len("SPLICE "):])
        elif line.startswith("ERROR "):
            d.setdefault("error", line[len("ERROR "):])
    return d


def run_compute(source, function, grid, tg, bufs, outs, splices=None,
                 timeout=20.0, run_timeout=15.0, workdir=None):
    """bufs: {idx: [ints]}; outs: {idx: nelems}. Returns parsed dict + raw stdout/stderr."""
    workdir = workdir or WORK
    cmd = [sys.executable, AGXTEST_PY, "--source", source, "--function", function,
           "--grid", str(grid), "--tg", str(tg), "--int",
           "--shdump", SHDUMP, "--agxrun", AGXRUN, "--agxparse", AGXPARSE,
           "--workdir", workdir, "--run-timeout", str(run_timeout), "--dump-main"]
    for idx, vals in (bufs or {}).items():
        cmd += ["--buf", f"{idx}=" + ",".join(str(v) for v in vals)]
    for idx, n in (outs or {}).items():
        cmd += ["--out", f"{idx}={n}"]
    for sp in (splices or []):
        cmd += ["--splice", sp]
    rc, out, err, timed_out = sh(cmd, timeout)
    parsed = parse_agxtest_stdout(out)
    parsed["rc"] = rc
    parsed["timed_out"] = timed_out
    parsed["stderr_tail"] = err[-800:] if err else ""
    if parsed["status"] == "UNKNOWN" and timed_out:
        parsed["status"] = "HANG"
    return parsed


def compile_and_extract(source, function, render=False, vertex=None, fragment=None,
                         timeout=90.0, workdir=None, tag=None, stage=None):
    """Compile via shdump; return (archive_path, main_hex, rc, log, timed_out) for
    _agc.main (compute), or with stage='vertex'/'fragment' for a render archive."""
    workdir = workdir or WORK
    tag = tag or function or f"{vertex}_{fragment}"
    arch = os.path.join(workdir, f"loc_{tag}.bin")
    if render:
        cmd = [SHDUMP, "-o", arch, "--render", "--vertex", vertex, "--fragment", fragment, source]
    else:
        cmd = [SHDUMP, "-o", arch, "-f", function, source]
    rc, out, err, timed_out = sh(cmd, timeout)
    if rc != 0 or timed_out:
        return arch, None, rc, out + err, timed_out
    extract_cmd = [sys.executable, AGXPARSE, arch, "--extract-hex"]
    if stage:
        extract_cmd += ["--stage", stage]
    rc2, hexout, err2, t2 = sh(extract_cmd, timeout)
    return arch, hexout.strip(), rc2, out + err + hexout + err2, (timed_out or t2)


def tokenize(hexstr, timeout=15.0):
    rc, out, err, timed_out = sh([sys.executable, AGXISA_PY, "tokenize", hexstr], timeout)
    return rc, out, err, timed_out


def run_render(source, vertex, fragment, width, height, timeout=25.0,
               run_timeout=20.0, workdir=None, tag=None):
    workdir = workdir or WORK
    tag = tag or fragment
    arch = os.path.join(workdir, f"r_{tag}.bin")
    rc, out, err, timed_out = sh([SHDUMP, "-o", arch, "--render", "--vertex", vertex,
                                   "--fragment", fragment, source], timeout)
    d = {"compile_rc": rc, "compile_out": out + err, "compile_timed_out": timed_out}
    if rc != 0 or timed_out:
        d["status"] = "COMPILE_FAIL"
        return d
    cmd = [AGXRENDER, "--archive", arch, "--source", source, "--vertex", vertex,
           "--fragment", fragment, "--width", str(width), "--height", str(height)]
    rc2, out2, err2, timed_out2 = sh(cmd, run_timeout)
    d["rc"] = rc2
    d["timed_out"] = timed_out2
    d["stderr_tail"] = err2[-800:] if err2 else ""
    status = "UNKNOWN"
    pixels = {}
    gputime = None
    for line in out2.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1].strip()
        elif line.startswith("GPUTIME_NS "):
            gputime = int(line.split(None, 1)[1])
        elif line.startswith("PIXEL "):
            parts = line.split()
            x, y = int(parts[1]), int(parts[2])
            bgra = parts[3].split("=")[1]
            b = int(bgra[0:2], 16); g = int(bgra[2:4], 16)
            r = int(bgra[4:6], 16); a = int(bgra[6:8], 16)
            pixels[f"{x},{y}"] = {"r": r, "g": g, "b": b, "a": a}
    d["status"] = status if not timed_out2 else "HANG"
    d["gputime_ns"] = gputime
    d["pixels"] = pixels
    return d


def compile_only(source, function, timeout=90.0, workdir=None, tag=None):
    """Attempt to compile SOURCE/FUNCTION only (no dispatch). Returns dict with
    status in {"OK","COMPILE_FAIL","COMPILE_TIMEOUT"} and a truncated log tail
    (deterministic given fixed toolchain+source -- used for the CF-03 exact
    nesting-ceiling boundary, where a Clang front-end diagnostic IS the
    expected/desired result, not an error to hide)."""
    workdir = workdir or WORK
    tag = tag or function
    arch = os.path.join(workdir, f"cchk_{tag}.bin")
    rc, out, err, timed_out = sh([SHDUMP, "-o", arch, "-f", function, source], timeout)
    log = (out + err)
    if timed_out:
        return {"status": "COMPILE_TIMEOUT", "log_tail": log[-600:]}
    if rc != 0:
        return {"status": "COMPILE_FAIL", "log_tail": log[-600:]}
    return {"status": "OK", "log_tail": log[-200:]}


class RecordWriter:
    """Append-only JSONL writer: open, write, flush, close on EVERY record so a
    kill costs at most the in-flight record (never buffers in memory)."""
    def __init__(self, path):
        self.path = path

    def append(self, obj):
        with open(self.path, "a") as f:
            f.write(json.dumps(obj, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
