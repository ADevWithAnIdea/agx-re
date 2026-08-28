#!/usr/bin/env python3
"""Throwaway exploratory driver #3 (NOT frozen run.py). Pins the exact wrap modulus
found by ladder_probe2.py (candidate 2^43) precisely at its edge. Scratch only."""
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
    r = subprocess.run([PROBE, "guard_read", params], capture_output=True, text=True, timeout=20)
    dt = time.time() - t0
    if r.returncode != 0:
        print("%-24s off=%-20d exit=%d dt=%.2fs stderr=%r" % (name, off, r.returncode, dt, r.stderr[:200]))
        return
    rec = json.loads(r.stdout.strip().splitlines()[-1])
    g = rec["gated"]
    print("%-24s off=0x%-16x dt=%.2fs cb=%s obs=%s" % (name, off, dt, g.get("cb_status"), g.get("obs_hex")))


M43 = 1 << 43
run("2^43_minus_4096", M43 - 4096)   # still below boundary: expect far/zero
run("2^43_minus_4", M43 - 4)         # just below boundary: expect far/zero
run("2^43_exact", M43)               # boundary: expect wrap to base+0 => a5c0dbf6
run("2^43_plus_4", M43 + 4)          # just above: expect wrap to base+4 => main[4..7]
run("2^43_plus_60", M43 + 60)        # wrap to base+60 (last in-bounds word for 64B buf)
run("2^43_plus_64", M43 + 64)        # wrap to base+64 => first fully-OOB word => expect 0
run("3x2^42", 3 * (1 << 42))         # = 1.5 * 2^43, below modulus if M=2^43 range check
run("2^43_x5_plus_4", 5 * M43 + 4)   # 5*2^43 mod 2^43 = 0 => wrap to base+4
