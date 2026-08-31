#!/usr/bin/env python3
"""EXP-0210 quiet-window sampler -- RUNS ON THE NEO, alongside a confirmation capture.

    python3 harness/quietsample.py --out <path.jsonl> --seconds <N> [--interval 2.0]
                                   [--label <tag>] [--exclude-pid P,...]

`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` Gate E requires a confirmation run that does NOT rely
on a busy machine.  `FIELD-SWEEP-PROTOCOL.md` section 7 requires that "the machine was quiet"
be a MEASUREMENT, not a claim.  This sampler makes it one, on four independent signals rather
than the one (process names) the fan-out used:

 1. `n_foreign_runner` -- DISPATCH-RUNNER processes not ours.  A dispatch runner is the class
    that contends for the GPU, faults, hangs, and manufactures `InnocentVictim` in a
    neighbour.  `n_compiler_svc` (the shader-compiler XPC service, which does not dispatch)
    and the legacy combined `n_foreign` are recorded separately so the numbers stay comparable
    with the fan-out's own busy measurements.   [AMENDMENT 01]
 2. `AGCInfo` from the IOKit registry: `fBusyCount`, `fSubmissionsSinceLastCheck` and
    `fLastSubmissionPID` -- a HARDWARE-SIDE statement about who is submitting, which does not
    depend on guessing process names.  A foreign submitter with an unfamiliar name is
    invisible to (1) and visible here.  NOTE `fLastSubmissionPID` is a LAST value: at the
    start of a capture it can still name our own immediately preceding capture's runner.
 3. `recoveryCount` -- the driver's cumulative device-reset counter.  A device reset is
    exactly the event that manufactures `InnocentVictim` and hang cascades in a neighbour's
    capture.  Its DELTA across a run is a direct victim/cascade detector, and it is the one
    measurement here that can falsify a "quiet" claim after the fact.
 4. `Renderer/Tiler Utilization %` and loadavg, for context.

Ownership [AMENDMENT 02]: one `ps` snapshot serves both the ownership walk and the row scan,
and a row is ours if it is in our ppid subtree OR shares our session id.  Two separate `ps`
calls race against our own short-lived `shdump` children; a session id survives reparenting
and zombie reaping.

Reading IOKit registry PROPERTIES is black-box data observation (CLAUDE.md, allowed technique
1).  No Apple binary is disassembled, decompiled, or introspected here; `ioreg` prints
driver-published property values, which are data and not code.

NOTE on "Device Utilization %": measured constant at 100 on this host with an idle GPU and no
submitters, so it is recorded but NOT used as a quiet criterion.  Renderer/Tiler read 0.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

RUNNER_PATTERNS = ("agxrun", "agxrun_persist", "agxrender", "renderpersist", "rendersweep",
                   "gfrun", "shdump", "persistrun", "agxtest")
COMPILER_PATTERNS = ("MTLCompilerService",)
PATTERNS = RUNNER_PATTERNS + COMPILER_PATTERNS

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


def snapshot():
    """AMENDMENT 02: ONE ps for both the ownership walk and the row scan."""
    try:
        out = subprocess.check_output(
            ["ps", "-Ao", "pid,ppid,pgid,sess,stat,%cpu,comm,args"],
            text=True, timeout=15)
    except Exception as e:                                          # noqa: BLE001
        return [], str(e)[:120]
    rows = []
    for ln in out.splitlines()[1:]:
        p = ln.split(None, 7)
        if len(p) < 8 or not p[0].isdigit():
            continue
        rows.append({"pid": int(p[0]),
                     "ppid": int(p[1]) if p[1].isdigit() else -1,
                     "pgid": p[2], "sess": p[3], "stat": p[4], "cpu": p[5],
                     "comm": p[6], "args": p[7]})
    return rows, None


def own_set(rows):
    """Ours = our ppid subtree UNION our session (AMENDMENT 02)."""
    me, parent = os.getpid(), os.getppid()
    by_pid = {r["pid"]: r for r in rows}
    kids = {}
    for r in rows:
        kids.setdefault(r["ppid"], []).append(r["pid"])
    mine = {me, parent}
    stack = [me, parent]
    while stack:
        p = stack.pop()
        for k in kids.get(p, []):
            if k not in mine:
                mine.add(k)
                stack.append(k)
    sess = {by_pid[p]["sess"] for p in (me, parent) if p in by_pid}
    sess.discard("")
    if sess:
        for r in rows:
            if r["sess"] in sess:
                mine.add(r["pid"])
    return mine


def all_pids():
    rows, _ = snapshot()
    return {r["pid"] for r in rows}


def gpu_stats():
    try:
        out = subprocess.check_output(IOREG, text=True, timeout=20,
                                      stderr=subprocess.DEVNULL)
    except Exception as e:                                          # noqa: BLE001
        return {"ioreg_error": str(e)[:120]}
    d = {}
    for k, pat in NUM.items():
        m = re.search(pat, out)
        d[k] = int(m.group(1)) if m else None
    return d


def proc_rows(exclude, baseline):
    rows, err = snapshot()
    if err:
        return [], {"ps_error": err}
    mine = own_set(rows)
    out = []
    for r in rows:
        blob = r["comm"] + " " + r["args"]
        if any(pat in blob for pat in PATTERNS):
            out.append({"pid": r["pid"], "cpu": r["cpu"], "cmd": r["args"][-110:],
                        "ours": r["pid"] in mine, "excluded": r["pid"] in exclude,
                        "kind": ("compiler"
                                 if any(q in blob for q in COMPILER_PATTERNS)
                                 else "runner"),
                        "stat": r["stat"], "exiting": r["comm"].startswith("("),
                        "sess": r["sess"], "ppid": r["ppid"],
                        "new_since_start": r["pid"] not in baseline})
    return out, {}


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
    baseline = all_pids()
    end = time.time() + a.seconds
    n = 0
    with open(a.out, "a") as f:
        while time.time() < end:
            rows, err = proc_rows(exclude, baseline)
            rec = {"ts": round(time.time(), 3), "label": a.label,
                   "loadavg": os.getloadavg(),
                   "procs": rows,
                   "n_foreign": sum(1 for r in rows
                                    if not r["ours"] and not r["excluded"]),
                   "n_foreign_runner": sum(1 for r in rows
                                           if r["kind"] == "runner"
                                           and not r["ours"] and not r["excluded"]),
                   "n_compiler_svc": sum(1 for r in rows if r["kind"] == "compiler"),
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
