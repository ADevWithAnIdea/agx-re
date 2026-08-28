#!/usr/bin/env python3
"""Exploratory (non-recorded) bisection of the reach_loop jump-offset boundary.
Finds approximate transition points to freeze into the formal matrix.
Not part of the gated capture -- pure reconnaissance, run once, results hand-
copied into harness/matrix.py's frozen delta list.
"""
import subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "reach.metal")
SHDUMP = os.path.join(HERE, "..", "bin", "shdump")
AGXRUN = os.path.join(HERE, "..", "bin", "agxrun")
AGXPARSE = os.path.join(HERE, "..", "bin", "agxparse.py")
AGXTEST = os.path.join(HERE, "..", "..", "..", "..", "tools", "agxtest", "agxtest.py")
WORKDIR = os.path.join(HERE, "run_bisect")
os.makedirs(WORKDIR, exist_ok=True)

BASE_OFFSET = -44
JUMP_FIELD_ABS = 0x6a + 3  # jump instr at 0x6a, offset field at byte+3

def classify(delta, timeout=8.0):
    new_off = BASE_OFFSET + delta
    new_bytes = (new_off & ((1 << 48) - 1)).to_bytes(6, "little")
    splice = f"_agc.main@{JUMP_FIELD_ABS:#x}={new_bytes.hex()}"
    cmd = [sys.executable, AGXTEST, "--source", SRC, "--function", "reach_loop",
           "--grid", "8", "--tg", "8", "--int", "--buf", "1=0,1,2,3,4,5,6,7", "--out", "0=8",
           "--shdump", SHDUMP, "--agxrun", AGXRUN, "--agxparse", AGXPARSE,
           "--workdir", WORKDIR, "--run-timeout", str(timeout), "--splice", splice]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except subprocess.TimeoutExpired:
        return "HOST_TIMEOUT", None
    status = "UNKNOWN"
    result = None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1].strip()
        if line.startswith("RESULT "):
            result = line
    return status, result

def bisect(lo, hi, lo_cls, hi_cls, tag):
    """lo/hi are deltas; lo_cls/hi_cls are their known classes (different).
    Returns (last_lo, lo_cls, first_hi, hi_cls) narrowed to adjacency (or close)."""
    print(f"--- bisecting [{tag}] between delta={lo}({lo_cls}) and delta={hi}({hi_cls}) ---")
    while hi - lo > 1:
        mid = (lo + hi) // 2
        cls, res = classify(mid)
        print(f"  delta={mid:>10d} -> {cls}  {res}")
        if cls == lo_cls:
            lo = mid
        else:
            hi = mid
            hi_cls = cls
    print(f"  => transition between delta={lo} ({lo_cls}) and delta={hi} ({hi_cls})")
    return lo, hi

if __name__ == "__main__":
    # Near-baseline classification for reference deltas already known from EXP-0104
    for d in (0, 8, -8, 4096, -4096):
        cls, res = classify(d)
        print(f"delta={d} -> {cls} {res}")
