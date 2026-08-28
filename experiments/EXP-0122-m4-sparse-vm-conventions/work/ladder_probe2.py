#!/usr/bin/env python3
"""Throwaway exploratory driver #2 (NOT frozen run.py). Bisects the apparent
wraparound near 2^44 and probes the 16384-neighbourhood anomaly found by
ladder_probe.py. Scratch only."""
import json, subprocess, sys, time

HERE = "/Users/user/asahi_re/public/agx-re/experiments/EXP-0122-m4-sparse-vm-conventions"
PROBE = HERE + "/work/probe"
KP = HERE + "/kernels/guard_access.metal"


def run(name, off):
    params = json.dumps({
        "name": name, "base_len": 64, "mode": "shared",
        "off_dec": str(off), "compile_watchdog_ms": 15000, "dispatch_watchdog_ms": 6000,
        "kernel_path": KP,
    })
    t0 = time.time()
    try:
        r = subprocess.run([PROBE, "guard_read", params], capture_output=True, text=True, timeout=20)
        dt = time.time() - t0
        if r.returncode != 0:
            print("%-28s off=%-20d exit=%d dt=%.2fs stderr=%r" % (name, off, r.returncode, dt, r.stderr[:200]))
            return
        rec = json.loads(r.stdout.strip().splitlines()[-1])
        g = rec["gated"]
        print("%-28s off=0x%-16x dt=%.2fs cb=%s obs=%s g1=%s g2=%s mainU=%s" % (
            name, off, dt, g.get("cb_status"), g.get("obs_hex"), g.get("g1_ok"), g.get("g2_ok"),
            g.get("main_unchanged")))
    except subprocess.TimeoutExpired:
        dt = time.time() - t0
        print("%-28s off=%-20d dt=%.2fs TIMEOUT" % (name, off, dt))
        sys.exit(1)


print("--- bisect wraparound between 2^40 (zero) and 2^44 (self-alias-looking) ---")
for shift in (41, 42, 43):
    run("bisect_2^%d" % shift, 1 << shift)

print("--- masking hypothesis: does (2^44 + K) read like offset K? ---")
run("ctrl_off32", 32)
run("2^44_plus_32", (1 << 44) + 32)
run("2^44_plus_0", (1 << 44) + 0)
run("2^44_minus_32(wrap)", (1 << 44) - 32)  # should be like a large offset if masking is exact power-of-two
run("2^45_plus_32", (1 << 45) + 32)
run("3x2^44_plus_32", 3 * (1 << 44) + 32)
run("2^44_minus_1", (1 << 44) - 1)

print("--- 16384-neighbourhood anomaly ---")
for off in (16384 - 256, 16384 - 4, 16384, 16384 + 4, 16384 + 256, 16384 + 4096,
            2 * 16384, 3 * 16384, 4 * 16384, 65536 - 16384):
    run("nb_%d" % off, off)
