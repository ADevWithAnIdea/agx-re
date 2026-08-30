#!/usr/bin/env python3
"""EXP-0201 concurrency sampler -- RUNS ON THE NEO, alongside a gated run.

    python3 harness/gpuwatch.py raw/<run_id>/gpuwatch.jsonl <seconds>

FIELD-SWEEP-PROTOCOL section 7: "If you need a quiet window, ask for one and
**record concurrent GPU activity for the duration** so 'the machine was quiet' is
a measurement rather than a claim."

This experiment's confirmation runs (`falu3.op`, `falu3_ext.op`,
`copysign.operands`) carry a named quiet-machine debt: their prior verdicts were
degraded by concurrent load, and a contaminated 97 % agreement reads as a
refutation when it is only noise. So every gated run is sampled every 2 s and a
run is QUIET only if no sample saw a foreign GPU-runner process. Our own
`agxrun_persist` children are identified by PID subtree and excluded.

Recording, not enforcing: nothing here serializes anything. There is no lease.
"""
import json
import os
import subprocess
import sys
import time

PATTERNS = ("agxrun", "rendersweep", "gfrun", "shdump", "renderpersist",
            "agxrender", "MTLCompilerService")


def own_pids():
    """Our own process subtree, so our own runner is not counted as a stranger."""
    mine = {os.getpid(), os.getppid()}
    try:
        out = subprocess.check_output(["ps", "-Ao", "pid,ppid"], text=True,
                                      timeout=10)
    except Exception:                                           # noqa: BLE001
        return mine
    kids = {}
    for ln in out.splitlines()[1:]:
        p = ln.split()
        if len(p) == 2 and p[0].isdigit() and p[1].isdigit():
            kids.setdefault(int(p[1]), []).append(int(p[0]))
    stack = list(mine)
    while stack:
        p = stack.pop()
        for k in kids.get(p, []):
            if k not in mine:
                mine.add(k)
                stack.append(k)
    return mine


def sample():
    try:
        out = subprocess.check_output(["ps", "-Ao", "pid,ppid,%cpu,comm"],
                                      text=True, timeout=10)
    except Exception as e:                                      # noqa: BLE001
        return {"error": str(e)[:120]}
    mine = own_pids()
    rows = []
    for ln in out.splitlines()[1:]:
        p = ln.split(None, 3)
        if len(p) < 4 or not p[0].isdigit():
            continue
        pid, comm = int(p[0]), p[3].strip()
        if any(pat in comm for pat in PATTERNS):
            rows.append({"pid": pid, "cpu": p[2], "comm": comm[-60:],
                         "ours": pid in mine})
    return {"procs": rows,
            "n_foreign": sum(1 for r in rows if not r["ours"])}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    path, dur = sys.argv[1], float(sys.argv[2])
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    end = time.time() + dur
    n = 0
    with open(path, "a") as f:
        while time.time() < end:
            rec = sample()
            rec["ts"] = time.time()
            f.write(json.dumps(rec, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
            n += 1
            time.sleep(2.0)
    print("gpuwatch: %d samples -> %s" % (n, path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
