#!/usr/bin/env python3
"""EXP-0167 concurrent-GPU-activity sampler, VERSION 2 — ancestry-resolving.

WHY A SECOND VERSION.  `gpuwatch.py` (v1) reported 4 samples with
`n_foreign == 1` during the `iso01` capture, naming `(agxrun)` and `(shdump)`
with `etime 00:00`.  Root cause, verified on the target: **macOS `ps`
truncates the `comm` column to 16 characters** (a Python process reports
`comm = "/Applications/Xc"`), and a process whose `argv` is momentarily
unreadable — the fork/exec transition, or a zombie — is rendered by `ps` as
`(agxrun)` in BOTH `comm` and `args`.  v1 matched `comm` against the harness
regex (which `(agxrun)` satisfies) and then looked for the `EXP-0167` marker in
`args` (which `(agxrun)` does not contain), so it filed its OWN child, caught
mid-`exec`, as foreign.  The same truncation is why v1's `n_mine` was always 0.

v2 fixes the classification without changing the question:

  * match on the FULL `args` first, `comm` only as a fallback;
  * resolve every candidate by **process ancestry**: walk the ppid chain and
    classify the process as `mine` if any ancestor is this experiment's own
    process tree (a pid passed in `--my-root-pids`, or any process whose args
    contain the marker).  A child caught mid-`exec` is resolved by its parent,
    which is exactly the information v1 threw away;
  * record `argv_unreadable` explicitly, so a process `ps` could not describe
    is never silently counted as either mine or foreign.

v1 is left RUNNING AND UNMODIFIED for the whole experiment so the two records
cover the same window and can be compared.  Its output file is append-only
evidence and is not edited.  Nothing here touches the GPU or any Apple binary:
it reads `/bin/ps` and `sysctl`, i.e. our own machine's process list.

Usage: gpuwatch2.py --out FILE --marker EXP-0167 [--interval 2.0]
                    [--phase NAME] [--my-root-pids 123,456]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HARNESS_RE = re.compile(
    r"agxrun|agxrun_persist|shdump|agxtest|agxparse|persistrun|MTLReplayer", re.I)
MTL_RE = re.compile(r"MTLCompilerService", re.I)
EXPPATH_RE = re.compile(r"EXP-\d{4}")
UNREADABLE_RE = re.compile(r"^\(.*\)$")


def ps_table():
    try:
        p = subprocess.run(["/bin/ps", "-Ao", "pid=,ppid=,%cpu=,etime=,user=,comm=,args="],
                           capture_output=True, text=True, timeout=15)
        return p.stdout.splitlines(), (None if p.returncode == 0 else "ps exit %d" % p.returncode)
    except (OSError, subprocess.TimeoutExpired) as e:
        return [], type(e).__name__


def sample(marker, my_roots):
    lines, ps_error = ps_table()
    procs = {}
    for ln in lines:
        f = ln.split(None, 6)
        if len(f) < 7:
            continue
        pid, ppid, cpu, etime, user, comm, args = f
        try:
            procs[int(pid)] = {"pid": int(pid), "ppid": int(ppid), "cpu": float(cpu),
                               "etime": etime, "user": user, "comm": comm, "args": args}
        except ValueError:
            continue

    # every pid whose OWN args name the marker is a root of our tree
    roots = set(my_roots)
    for pid, r in procs.items():
        if marker in r["args"]:
            roots.add(pid)

    def is_mine(pid, depth=0):
        """True if pid or any ancestor is in `roots`.  Depth-capped so a pid
        cycle or a re-used pid cannot loop."""
        seen = set()
        while pid and pid not in seen and depth < 24:
            if pid in roots:
                return True
            seen.add(pid)
            r = procs.get(pid)
            if not r:
                return False
            pid = r["ppid"]
            depth += 1
        return False

    mine, foreign, mtl, unreadable = [], [], [], []
    for pid, r in procs.items():
        hay = r["args"] if not UNREADABLE_RE.match(r["args"].strip()) else r["comm"]
        is_harness = bool(HARNESS_RE.search(hay) or HARNESS_RE.search(r["comm"]))
        is_mtl = bool(MTL_RE.search(hay) or MTL_RE.search(r["comm"]))
        is_exp = bool(EXPPATH_RE.search(r["args"]))
        if not (is_harness or is_mtl or is_exp):
            continue
        rec = dict(r)
        rec["args"] = r["args"][:240]
        rec["argv_unreadable"] = bool(UNREADABLE_RE.match(r["args"].strip()))
        if is_mtl:
            mtl.append(rec)
            continue
        if is_mine(pid):
            rec["why_mine"] = "marker in own args" if marker in r["args"] else "ancestry"
            mine.append(rec)
        elif rec["argv_unreadable"]:
            # argv not readable AND no resolvable ancestry: report it in its own
            # bucket rather than asserting it is somebody else's.
            unreadable.append(rec)
        else:
            foreign.append(rec)

    try:
        la = subprocess.run(["/usr/sbin/sysctl", "-n", "vm.loadavg"],
                            capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        la = None

    return {"t": time.time(),
            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ps_error": ps_error, "n_procs_scanned": len(procs),
            "n_mine": len(mine), "n_foreign": len(foreign),
            "n_unresolved_unreadable": len(unreadable),
            "n_mtlcompiler": len(mtl),
            "mtlcompiler_busy": [m for m in mtl if m["cpu"] >= 5.0],
            "mine": mine, "foreign": foreign, "unresolved_unreadable": unreadable,
            "loadavg": la}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--marker", default="EXP-0167")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--phase", default="")
    ap.add_argument("--my-root-pids", default="")
    ap.add_argument("--max-seconds", type=float, default=4.0 * 3600)
    a = ap.parse_args()
    roots = set(int(x) for x in a.my_root_pids.split(",") if x.strip())
    roots.add(os.getpid())
    t0 = time.time()
    with open(a.out, "a") as f:
        f.write(json.dumps({"event": "watch_start", "version": 2, "phase": a.phase,
                            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "interval": a.interval, "marker": a.marker,
                            "my_root_pids": sorted(roots), "pid": os.getpid()},
                           sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
        while time.time() - t0 < a.max_seconds:
            s = sample(a.marker, roots)
            s["phase"] = a.phase
            f.write(json.dumps(s, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
            time.sleep(a.interval)
        f.write(json.dumps({"event": "watch_end", "version": 2, "phase": a.phase,
                            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                           sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


if __name__ == "__main__":
    sys.exit(main())
