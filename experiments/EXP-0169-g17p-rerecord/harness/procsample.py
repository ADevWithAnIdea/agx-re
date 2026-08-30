#!/usr/bin/env python3
"""EXP-0169 quiet-window measurement.

  python3 harness/procsample.py --run <run_id> [--period 5] [--max-minutes 90]

FIELD-SWEEP-PROTOCOL section 7: "If you need a quiet window, ask for one and
RECORD CONCURRENT GPU ACTIVITY FOR THE DURATION (sample the process table into
raw/) so 'the machine was quiet' is a measurement rather than a claim."

Samples the process table every `--period` seconds into
raw/<run_id>/03_procsample.jsonl, one JSON object per sample, flushed
immediately. Records every process whose command line looks like another
agent's GPU work, plus the total count, so a contaminated stretch of a gated run
can be located afterwards by timestamp against sweep.jsonl's own `t`.

Read-only over the process table. Writes nothing but its own log.
"""
from __future__ import print_function

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent

# Other agents' GPU work on this host looks like one of these.
GPUISH = re.compile(r"agxrun|agxrender|gfrun|renderpersist|texpersist|"
                    r"MTLCompilerService|shdump|metal|EXP-0\d\d\d", re.I)
MINE = re.compile(r"EXP-0169")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--period", type=float, default=5.0)
    ap.add_argument("--max-minutes", type=float, default=90.0)
    a = ap.parse_args()
    dst = EXP / "raw" / a.run / "03_procsample.jsonl"
    dst.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + a.max_minutes * 60.0
    f = open(str(dst), "a", buffering=1)
    n = 0
    while time.time() < deadline:
        try:
            out = subprocess.check_output(["ps", "-Ao", "pid,pcpu,comm,args"],
                                          stderr=subprocess.DEVNULL).decode(
                                              errors="replace")
            lines = out.splitlines()[1:]
        except Exception as e:
            lines = []
        gpu, mine = [], 0
        for ln in lines:
            if not GPUISH.search(ln):
                continue
            if MINE.search(ln):
                mine += 1
                continue
            parts = ln.split(None, 3)
            gpu.append({"pid": parts[0] if parts else "?",
                        "pcpu": parts[1] if len(parts) > 1 else "?",
                        "cmd": (parts[3] if len(parts) > 3 else ln)[:160]})
        rec = {"t": round(time.time(), 3),
               "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "n_procs": len(lines), "n_mine": mine,
               "n_foreign_gpu": len(gpu), "foreign_gpu": gpu[:20],
               "quiet": len(gpu) == 0}
        f.write(json.dumps(rec, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
        n += 1
        time.sleep(a.period)
    f.close()
    print("procsample: %d samples -> %s" % (n, dst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
