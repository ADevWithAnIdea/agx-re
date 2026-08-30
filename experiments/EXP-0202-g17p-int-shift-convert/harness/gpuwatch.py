#!/usr/bin/env python3
"""EXP-0202 quiet-window measurement.

Samples the target's process table every N seconds for the duration of a gated
run and appends one JSON object per sample to `raw/<run_id>/gpuwatch.jsonl`.

FIELD-SWEEP-PROTOCOL section 7 (amended 2026-08-30) requires that if you ask for
a quiet window you must RECORD CONCURRENT GPU ACTIVITY FOR THE DURATION, so that
"the machine was quiet" is a measurement rather than a claim. EXP-0158 ran its
confirmation against 8-12 sibling experiments and got 102 of 174 cases giving
MIXED outcomes across five runs of byte-identical programs; it could not prove
what it had been running against, and its cross-run gate was left failing.

Runs ON the target, alongside run.py.

  python3 harness/gpuwatch.py --run <run_id> [--interval 2.0]
"""
from __future__ import print_function
import argparse, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent

# Anything that could be issuing GPU work. Our own processes are recorded too --
# the point is a complete picture, not a flattering one.
PATTERNS = ("agxrun", "gfrun", "shdump", "MTLCompilerService", "python3",
            "WindowServer", "Metal", "GPUToolsService", "renderpersist")


def sample():
    try:
        out = subprocess.check_output(
            ["ps", "-Ao", "pid,ppid,pcpu,etime,comm"],
            stderr=subprocess.DEVNULL, timeout=10).decode(errors="replace")
    except Exception as e:
        return {"error": str(e)[:200]}
    rows = []
    for ln in out.splitlines()[1:]:
        p = ln.split(None, 4)
        if len(p) < 5:
            continue
        comm = p[4]
        if any(k.lower() in comm.lower() for k in PATTERNS):
            rows.append({"pid": p[0], "ppid": p[1], "cpu": p[2],
                         "etime": p[3], "comm": comm[-80:]})
    return {"n": len(rows), "procs": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--max-s", type=float, default=7200.0)
    a = ap.parse_args()
    d = EXP / "raw" / a.run
    d.mkdir(parents=True, exist_ok=True)
    f = open(str(d / "gpuwatch.jsonl"), "a", buffering=1)
    t0 = time.time()
    print("gpuwatch -> %s (interval %.1fs)" % (d / "gpuwatch.jsonl", a.interval))
    try:
        while time.time() - t0 < a.max_s:
            rec = {"t": round(time.time(), 3),
                   "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            rec.update(sample())
            f.write(json.dumps(rec, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
            time.sleep(a.interval)
    except KeyboardInterrupt:
        pass
    finally:
        f.close()


if __name__ == "__main__":
    main()
