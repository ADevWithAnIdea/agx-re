#!/usr/bin/env python3
"""EXP-0203 concurrent-GPU-activity sampler.

FIELD-SWEEP-PROTOCOL section 7: sweeps run unlocked, but "the machine was quiet" must be a
MEASUREMENT and not a claim.  This samples the process table into
`raw/<run>/03_procsample.jsonl` for the duration of a run, so a contamination question can be
answered from the committed raw afterwards instead of argued about.

Usage:  python3 harness/procsample.py --run <run_id> [--seconds 900]
"""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
KEYS = ("agxrun", "shdump", "python3", "MTLCompiler", "WindowServer", "run.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--seconds", type=float, default=900.0)
    ap.add_argument("--interval", type=float, default=5.0)
    a = ap.parse_args()
    out = EXP / "raw" / a.run / "03_procsample.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    end = time.time() + a.seconds
    with open(str(out), "a", buffering=1) as f:
        while time.time() < end:
            try:
                ps = subprocess.run(["ps", "-Ao", "pid,pcpu,comm,args"],
                                    stdout=subprocess.PIPE, timeout=20).stdout.decode()
            except Exception as e:                             # noqa: BLE001
                ps = "ERROR %s" % e
            rows = [l.strip()[:160] for l in ps.splitlines()
                    if any(k in l for k in KEYS)]
            la = os.getloadavg()
            f.write(json.dumps({"t": round(time.time(), 2), "loadavg": la,
                                "n": len(rows), "rows": rows[:40]}) + "\n")
            f.flush()
            time.sleep(a.interval)


if __name__ == "__main__":
    main()
