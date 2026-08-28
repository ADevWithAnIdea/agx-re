#!/usr/bin/env python3
import subprocess, json, time

PROBE = "/Users/user/asahi_re/public/agx-re/experiments/EXP-0122-m4-sparse-vm-conventions/work/probe"
KP = "/Users/user/asahi_re/public/agx-re/experiments/EXP-0122-m4-sparse-vm-conventions/kernels/sparse_access.metal"

params = json.dumps({
    "width": 128, "height": 128, "tile_w": 64, "tile_h": 64, "page": "16",
    "mapped_tiles": [[0, 0]],
    "write_coord": [10, 10],
    "pattern_rgba": [0.25, 0.5, 0.75, 1.0],
    "read_coords": [[10, 10], [70, 10], [10, 70], [100, 100]],
    "compile_watchdog_ms": 15000, "dispatch_watchdog_ms": 8000,
    "kernel_path": KP,
})
t0 = time.time()
r = subprocess.run([PROBE, "sparse_partial_map", params], capture_output=True, text=True, timeout=25)
print("exit", r.returncode, "dt", time.time() - t0)
if r.returncode != 0:
    print("STDERR", r.stderr[-3000:])
else:
    rec = json.loads(r.stdout.strip())
    print(json.dumps(rec, indent=2))
