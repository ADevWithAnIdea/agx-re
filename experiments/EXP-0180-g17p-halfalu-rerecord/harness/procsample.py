#!/usr/bin/env python3
"""EXP-0180 concurrent-GPU-activity sampler.

FIELD-SWEEP-PROTOCOL section 7: if a run claims a quiet machine, that claim must be a
MEASUREMENT. Samples the process table every 5 s for the run's duration into
raw/<run>/03_procsample.jsonl, flushed per sample.
"""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
MARK = ("agxrun_persist", "agxrender", "gfrun", "rendersweep", "MTLCompilerService",
        "shdump", "metal", "clang")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--max-seconds", type=float, default=3600.0)
    a = ap.parse_args()
    out = EXP / "raw" / a.run
    out.mkdir(parents=True, exist_ok=True)
    f = open(str(out / "03_procsample.jsonl"), "a", buffering=1)
    t0 = time.time()
    me = os.getpid()
    while time.time() - t0 < a.max_seconds:
        try:
            ps = subprocess.run(["ps", "-axo", "pid=,ppid=,pcpu=,comm="],
                                stdout=subprocess.PIPE, timeout=20).stdout.decode()
        except Exception as e:                                    # noqa: BLE001
            ps = "PSERROR %s" % e
        hits = []
        for ln in ps.splitlines():
            p = ln.split(None, 3)
            if len(p) < 4:
                continue
            if any(m.lower() in p[3].lower() for m in MARK) and int(p[0]) != me:
                hits.append({"pid": int(p[0]), "cpu": float(p[2]), "comm": p[3].strip()})
        f.write(json.dumps({"t": round(time.time(), 3), "n": len(hits),
                            "quiet": len(hits) == 0, "procs": hits[:32]},
                           sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
