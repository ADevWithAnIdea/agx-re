#!/usr/bin/env python3
"""Throwaway exploratory driver (NOT the frozen run.py) to find the offset ladder's safe
range before committing to the frozen case matrix. Scratch only; not part of the raw/
evidence tree."""
import json, subprocess, sys, time

HERE = "/Users/user/asahi_re/public/agx-re/experiments/EXP-0122-m4-sparse-vm-conventions"
PROBE = HERE + "/work/probe"
KP = HERE + "/kernels/guard_access.metal"

offsets = [64, 4096, 16384, 65536, 1 << 20, 1 << 24, 1 << 28, 1 << 32, 1 << 36, 1 << 40, 1 << 44, 1 << 48]

for off in offsets:
    params = json.dumps({
        "name": "ladder_%d" % off, "base_len": 64, "mode": "shared",
        "off_dec": str(off), "compile_watchdog_ms": 15000, "dispatch_watchdog_ms": 6000,
        "kernel_path": KP,
    })
    t0 = time.time()
    try:
        r = subprocess.run([PROBE, "guard_read", params], capture_output=True, text=True, timeout=20)
        dt = time.time() - t0
        if r.returncode != 0:
            print("off=2^%.1f (%d) exit=%d dt=%.2fs stderr=%r" % (off.bit_length()-1, off, r.returncode, dt, r.stderr[:300]))
            continue
        rec = json.loads(r.stdout.strip().splitlines()[-1])
        g = rec["gated"]
        print("off=2^%d (%d) dt=%.2fs status=%s cb=%s obs=%s g1=%s g2=%s main_unchanged=%s" % (
            off.bit_length()-1, off, dt, g.get("status"), g.get("cb_status"), g.get("obs_hex"),
            g.get("g1_ok"), g.get("g2_ok"), g.get("main_unchanged")))
    except subprocess.TimeoutExpired:
        dt = time.time() - t0
        print("off=2^%d (%d) dt=%.2fs TIMEOUT (outer 20s) -- STOPPING ladder" % (off.bit_length()-1, off, dt))
        sys.exit(1)
