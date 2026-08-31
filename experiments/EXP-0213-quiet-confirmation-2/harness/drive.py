#!/usr/bin/env python3
"""EXP-0213 -- sequential capture driver.  Runs on the repo host.

    python3 harness/drive.py <plan.json>

Each plan entry is one capture: it calls harness/capture.sh (which wraps the SOURCE
experiment's own unedited run.py in a measured quiet window on the neo) and then
harness/pull_run.sh (which pulls exactly ONE new run directory back into that source
experiment's own raw/ tree and refuses to touch an existing directory).

Progress is appended to PROGRESS.md after EVERY capture, and the per-capture result is
appended to work/drive_log.jsonl as it completes -- never buffered to be written at the end
(SUBAGENT_BRIEF: assume the host dies mid-run).
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sh(cmd, timeout):
    t0 = time.time()
    p = subprocess.run(["bash", "-c", cmd], cwd=HERE, text=True,
                       capture_output=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr, round(time.time() - t0, 1)


def progress(line):
    with open(os.path.join(HERE, "PROGRESS.md"), "a") as f:
        f.write("- %s  %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), line))
        f.flush()
        os.fsync(f.fileno())


def main():
    plan = json.load(open(sys.argv[1]))
    logp = os.path.join(HERE, "work", "drive_log.jsonl")
    os.makedirs(os.path.dirname(logp), exist_ok=True)
    done = set()
    if os.path.exists(logp):
        for ln in open(logp):
            try:
                done.add(json.loads(ln)["tag"])
            except Exception:                                        # noqa: BLE001
                pass
    for e in plan["captures"]:
        tag = e["tag"]
        if tag in done:
            print("SKIP (already in drive_log): %s" % tag)
            continue
        # AMENDMENT-01: a capture whose wall-clock cap is load-bearing goes through
        # capture_cap.sh, whose cap kills the whole capture instead of orphaning its child.
        script = "capture_cap.sh" if e.get("capped") else "capture.sh"
        cmd = ("sh harness/%s %s %d %d %s %s"
               % (script, tag, e["sample_s"], e["alarm_s"], e["remote_exp"],
                  json.dumps(e["cmd"])))
        rc, out, err, dt = sh(cmd, timeout=e["alarm_s"] + 600)
        qc = None
        qpath = os.path.join(HERE, "raw", tag, "quietcheck.json")
        if os.path.exists(qpath):
            try:
                qc = json.load(open(qpath))
            except Exception:                                        # noqa: BLE001
                qc = None
        drc = None
        capped = None
        for ln in out.splitlines():
            if ln.startswith("__DRIVE_RC="):
                drc = int(ln.split("=", 1)[1])
            if ln.startswith("__DRIVE_CAPPED="):
                capped = int(ln.split("=", 1)[1])
        prc = None
        if e.get("run_id"):
            prc, pout, perr, pdt = sh(
                "sh harness/pull_run.sh %s %s %s"
                % (e["remote_exp"].split("/")[-1], e["run_id"], e["local_exp"]),
                timeout=900)
        rec = {"tag": tag, "run_id": e.get("run_id"), "capture_rc": rc,
               "drive_rc": drc, "cap_hit": capped, "pull_rc": prc, "elapsed_s": dt,
               "quiet": (qc or {}).get("QUIET"),
               "max_foreign_runner_live": (qc or {}).get("max_foreign_runner_live"),
               "recovery_pre": (qc or {}).get("recovery_pre"),
               "recovery_post": (qc or {}).get("recovery_post"),
               "recovery_delta": (qc or {}).get("recovery_delta"),
               "stdout_tail": out[-1400:], "stderr_tail": err[-600:]}
        with open(logp, "a") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        progress("%s rc=%s drive_rc=%s pull_rc=%s quiet=%s dt=%ss recovery %s->%s"
                 % (tag, rc, drc, prc, (qc or {}).get("QUIET"), dt,
                    (qc or {}).get("recovery_pre"), (qc or {}).get("recovery_post")))
        print("[%s] rc=%s drive_rc=%s pull_rc=%s quiet=%s dt=%ss rec %s->%s"
              % (tag, rc, drc, prc, (qc or {}).get("QUIET"), dt,
                 (qc or {}).get("recovery_pre"), (qc or {}).get("recovery_post")))
        sys.stdout.flush()
        if drc is None and rc != 0:
            print("!! capture produced no __DRIVE_RC -- possible SSH/device failure; STOPPING")
            progress("STOP: %s produced no __DRIVE_RC" % tag)
            return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
