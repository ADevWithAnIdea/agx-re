#!/usr/bin/env python3
# EXP-M4-11 item 5: SR table (reproduces RT-7 §5). get_sr @0x00, byte1 = SR selector (file off 0x01).
# Splice byte1 to each SR code; the output becomes that SR's value across a grid=128/tg=64 launch.
import subprocess, os
ROOT = "/Users/user/cleanroom_gpu"; AGXTEST = os.path.join(ROOT, "tools/agxtest/agxtest.py")
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kernels/sr.metal")
GRID, TG = 128, 64

def run(code):
    cmd = ["python3", AGXTEST, "--source", SRC, "--function", "k", "--grid", str(GRID), "--tg", str(TG),
           "--int", "--out", "0=%d" % GRID, "--splice", "_agc.main@0x01=%02x" % code, "--run-timeout", "25"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    st = res = None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS"): st = line.split()[1]
        if line.startswith("RESULT"): res = [int(x) for x in line.split()[2:]]
    return st, res

def summarize(res):
    if not res: return "None"
    first16 = res[:16]
    return "first16=%s uniq=%s max=%d" % (first16, sorted(set(res))[:6], max(res))

SRS = [(0xa0, "thread_position_in_grid.x -> 0..127"),
       (0xa4, "thread_position_in_threadgroup -> 0..63"),
       (0xa7, "thread_index_in_threadgroup -> 0..63"),
       (0x98, "threads_per_threadgroup -> 64"),
       (0x9c, "threadgroup_position_in_grid -> 0/1"),
       (0x82, "simd_lane_id -> 0..31"),
       (0x85, "simd_group_id -> 0/1"),
       (0xa8, "threadgroups_per_grid code (RT-7 nuance: bare read = threads_per_tg=64)")]
for code, desc in SRS:
    st, res = run(code)
    print("byte1=0x%02x  %-55s STATUS=%-4s %s" % (code, desc, st, summarize(res)))
