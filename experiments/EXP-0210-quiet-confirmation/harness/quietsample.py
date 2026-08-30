#!/usr/bin/env python3
"""EXP-0210 quiet-window sampler -- RUNS ON THE NEO, alongside a confirmation capture.

    python3 harness/quietsample.py --out <path.jsonl> --seconds <N> [--interval 2.0]
                                   [--label <tag>] [--exclude-pid P,...]

`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` Gate E requires a confirmation run that does NOT
rely on a busy machine.  `FIELD-SWEEP-PROTOCOL.md` section 7 requires that "the machine was
quiet" be a MEASUREMENT, not a claim.  This sampler makes it one, on four independent
signals rather than the one (process names) the fan-out used:

 1. `n_foreign` -- processes whose comm/args match a GPU-runner pattern and are not in our
    own process subtree.  This reproduces the fan-out's own metric so the numbers are
    directly comparable with the busy measurements those experiments recorded.
 2. `AGCInfo` from the IOKit registry: `fBusyCount`, `fSubmissionsSinceLastCheck`, and
    `fLastSubmissionPID` -- a HARDWARE-SIDE statement about who is submitting, which does
    not depend on guessing process names.  A foreign submitter with an unfamiliar name is
    invisible to (1) and visible here.
 3. `recoveryCount` -- the driver's cumulative device-reset counter.  A device reset is
    exactly the event that manufactures `InnocentVictim` and hang cascades in a neighbour's
    capture.  Its DELTA across a run is a direct victim/cascade detector, and it is the one
    measurement in this file that can falsify a "quiet" claim after the fact.
 4. `Renderer/Tiler Utilization %` and loadavg, for context.

Reading IOKit registry PROPERTIES is black-box data observation (CLAUDE.md, allowed
technique 1).  No Apple binary is disassembled, decompiled, or introspected anywhere here;
`ioreg` prints driver-published property values, which are data and not code.

NOTE on "Device Utilization %": measured constant at 100 on this host with an idle GPU and
no submitters, so it is recorded but NOT used as a quiet criterion.  Renderer/Tiler read 0.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

# Union of the patterns the seven confirmed experiments used, plus this repo's runners.
PATTERNS = ("agxrun", "agxrun_persist", "agxrender", "renderpersist", "rendersweep",
            "gfrun", "shdump", "MTLCompilerService", "persistrun", "agxtest")

IOREG = ["ioreg", "-rc", "AGXAcceleratorG17P", "-d", "1", "-w", "0"]
NUM = {
    "device_util": r'"Device Utilization %"=(\d+)',
    "renderer_util": r'"Renderer Utilization %"=(\d+)',
    "tiler_util": r'"Tiler Utilization %"=(\d+)',
    "recovery_count": r'"recoveryCount"=(\d+)',
    "last_submission_pid": r'"fLastSubmissionPID"=(\d+)',
    "submissions_since_check": r'"fSubmissionsSinceLastCheck"=(\d+)',
    "busy_count": r'"fBusyCount"=(\d+)',
}


def own_pids():
    mine = {os.getpid(), os.getppid()}
    try:
        out = subprocess.check_output(["ps", "-Ao", "pid,ppid"], text=True, timeout=10)
    except Exception as e:                                          # noqa: BLE001
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


def gpu_stats():
    try:
        out = subprocess.check_output(IOREG, text=True, timeout=20, stderr=subprocess.DEVNULL)
    except Exception as e:                                          # noqa: BLE001
        return {"ioreg_error": str(e)[:120]}
    d = {}
    for k, pat in NUM.items():
        m = re.search(pat, out)
        d[k] = int(m.group(1)) if m else None
    return d


def proc_rows(exclude):
    try:
        out = subprocess.check_output(["ps", "-Ao", "pid,ppid,%cpu,comm,args"],
                                      text=True, timeout=15)
    except Exception as e:                                          # noqa: BLE001
        return [], {"ps_error": str(e)[:120]}
    mine = own_pids()
    rows = []
    for ln in out.splitlines()[1:]:
        p = ln.split(None, 4)
        if len(p) < 5 or not p[0].isdigit():
            continue
        pid = int(p[0])
        blob = p[3] + " " + p[4]
        if any(pat in blob for pat in PATTERNS):
            rows.append({"pid": pid, "cpu": p[2], "cmd": p[4][-110:],
                         "ours": pid in mine, "excluded": pid in exclude})
    return rows, {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, required=True)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--label", default="")
    ap.add_argument("--exclude-pid", default="")
    a = ap.parse_args()
    exclude = {int(x) for x in a.exclude_pid.split(",") if x.strip().isdigit()}
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    end = time.time() + a.seconds
    n = 0
    with open(a.out, "a") as f:
        while time.time() < end:
            rows, err = proc_rows(exclude)
            rec = {"ts": round(time.time(), 3), "label": a.label,
                   "loadavg": os.getloadavg(),
                   "procs": rows,
                   "n_foreign": sum(1 for r in rows
                                    if not r["ours"] and not r["excluded"]),
                   "gpu": gpu_stats()}
            rec.update(err)
            f.write(json.dumps(rec, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
            n += 1
            time.sleep(a.interval)
    sys.stderr.write("quietsample: %d samples -> %s\n" % (n, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
