#!/usr/bin/env python3
"""EXP-0167 concurrent-GPU-activity sampler.  Runs ON THE TARGET, alongside the
capture, and touches no GPU itself.

WHY THIS EXISTS.  EXP-0158's dominant limitation is that it could not say what
else was running on the device while it captured: its RESULTS.md can only
report "8-12 sibling GPU experiments" from the orchestrator's knowledge, not
from a measurement.  This experiment's entire claim is that the SAME programs
behave differently on a QUIET machine, so "quiet" has to be evidence in `raw/`,
not an assertion in prose.

`~/agxre/gpulease.sh` cannot supply that evidence: as of 2026-08-30 it is a
neutralised pass-through shim (`shift 2; [ "$1" = "--" ] && shift; exec "$@"`)
that takes no lock at all.  EXP-0158's own run03/run04 went through that same
shim, so those runs were not locked either.  Isolation here is established by
hand coordination (the orchestrator quiesced the other device agents) and
VERIFIED by this sampler.

WHAT IT SAMPLES, every --interval seconds:

  * every process whose comm/args match `agxrun|agxrun_persist|shdump|agxtest|
    agxparse|persistrun|MTLCompilerService|MTLReplayer`, plus any `python`
    process whose args mention an `EXP-NNNN` path;
  * each is classified `mine` (args contain this experiment's marker) or
    FOREIGN (anything else) -- a foreign ACTIVE harness process is the thing
    that would invalidate the run;
  * `MTLCompilerService` is counted separately and is NOT treated as
    contention: idle XPC instances are normal on this host and are present
    even on a fully quiet machine.  Only its %cpu is recorded so a reader can
    see whether one was actually working.
  * system load average, for a coarse independent cross-check.

One JSON object per sample, appended + fsync'd, so a kill costs at most one
sample.  Never edited afterwards; this file is append-only raw evidence.

Usage: gpuwatch.py --out FILE --marker EXP-0167 [--interval 2.0] [--phase NAME]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HARNESS_RE = re.compile(
    r"agxrun|agxrun_persist|shdump|agxtest|agxparse|persistrun|MTLReplayer",
    re.I)
MTL_RE = re.compile(r"MTLCompilerService", re.I)
EXPPATH_RE = re.compile(r"EXP-\d{4}")
PY_RE = re.compile(r"\bpython[\d.]*\b", re.I)


def sample(marker):
    """One snapshot of the process table.  `ps` only -- no GPU, no Apple binary
    introspection: this reads the kernel's own process list, which is data
    about OUR machine's state, not about Apple's code."""
    try:
        p = subprocess.run(["/bin/ps", "-Ao", "pid=,ppid=,%cpu=,etime=,user=,comm=,args="],
                           capture_output=True, text=True, timeout=15)
        lines = p.stdout.splitlines()
        ps_error = None if p.returncode == 0 else "ps exit %d" % p.returncode
    except (OSError, subprocess.TimeoutExpired) as e:
        lines, ps_error = [], type(e).__name__

    mine, foreign, mtl = [], [], []
    for ln in lines:
        f = ln.split(None, 6)
        if len(f) < 7:
            continue
        pid, ppid, cpu, etime, user, comm, args = f
        is_harness = bool(HARNESS_RE.search(comm) or HARNESS_RE.search(args))
        is_mtl = bool(MTL_RE.search(comm) or MTL_RE.search(args))
        is_exp_py = bool(PY_RE.search(comm) and EXPPATH_RE.search(args))
        if not (is_harness or is_mtl or is_exp_py):
            continue
        rec = {"pid": int(pid), "ppid": int(ppid), "cpu": float(cpu),
               "etime": etime, "user": user, "comm": comm, "args": args[:240]}
        if is_mtl:
            mtl.append(rec)
        elif marker in args:
            mine.append(rec)
        else:
            foreign.append(rec)

    try:
        la = subprocess.run(["/usr/sbin/sysctl", "-n", "vm.loadavg"],
                            capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        la = None

    return {"t": time.time(),
            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ps_error": ps_error,
            "n_mine": len(mine), "n_foreign": len(foreign),
            "n_mtlcompiler": len(mtl),
            "mtlcompiler_busy": [m for m in mtl if m["cpu"] >= 5.0],
            "foreign": foreign,
            "mine_pids": [m["pid"] for m in mine],
            "loadavg": la}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--marker", default="EXP-0167")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--phase", default="")
    ap.add_argument("--max-seconds", type=float, default=4.0 * 3600)
    a = ap.parse_args()
    t0 = time.time()
    with open(a.out, "a") as f:
        f.write(json.dumps({"event": "watch_start", "phase": a.phase,
                            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "interval": a.interval, "marker": a.marker,
                            "pid": os.getpid()}, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
        while time.time() - t0 < a.max_seconds:
            s = sample(a.marker)
            s["phase"] = a.phase
            f.write(json.dumps(s, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
            time.sleep(a.interval)
        f.write(json.dumps({"event": "watch_end", "phase": a.phase,
                            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                           sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


if __name__ == "__main__":
    sys.exit(main())
