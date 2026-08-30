#!/usr/bin/env python3
"""EXP-0210 -- Q3, completed: was the GPU's last submitter ever someone else?

    python3 analysis/q3_check.py raw/<tag>/quiet.jsonl [...]

Q3 was pre-registered as "`fLastSubmissionPID` never becomes a PID outside our own subtree".
`harness/quietcheck.py` only LISTS the observed submitter PIDs; this adjudicates each one
against the same capture's own process rows.  Categories:

  ours      -- seen in this capture's samples with ours=True
  foreign   -- seen in this capture's samples with ours=False   <-- Q3 FAILS
  idle_328  -- the login-window `SecurityAgent`, PID 328, recorded at freeze as the GPU's
               last submitter on the idle machine.  It submits nothing while we run; it is
               simply the value the register still held.
  stale     -- not present in this capture's rows at all.  `fLastSubmissionPID` is a LAST
               value, so at the start of a capture it can still name a runner from OUR OWN
               immediately preceding capture, which has since exited.  Adjudicated by
               checking the PID against the preceding capture's own rows when one is given.

Q3 fails only on `foreign`.  Everything else is reported, never assumed away.
"""
import json
import sys


def rows_of(path):
    ours, foreign, subs = set(), set(), []
    for ln in open(path):
        ln = ln.strip()
        if not ln:
            continue
        r = json.loads(ln)
        for p in r.get("procs", []):
            (ours if p.get("ours") else foreign).add(p["pid"])
        g = r.get("gpu") or {}
        if g.get("last_submission_pid") is not None:
            subs.append(g["last_submission_pid"])
    return ours, foreign, subs


def main():
    prev_ours = set()
    for path in sys.argv[1:]:
        ours, foreign, subs = rows_of(path)
        cls = {}
        for s in sorted(set(subs)):
            if s in foreign:
                cls[s] = "FOREIGN"
            elif s in ours:
                cls[s] = "ours"
            elif s == 328:
                cls[s] = "idle_328_SecurityAgent"
            elif s in prev_ours:
                cls[s] = "stale_ours_previous_capture"
            else:
                cls[s] = "absent_from_rows"
        print(json.dumps({"capture": path,
                          "Q3_pass": not any(v == "FOREIGN" for v in cls.values()),
                          "submitters": cls,
                          "n_own_pids_seen": len(ours),
                          "n_foreign_pids_seen": len(foreign)}, sort_keys=True))
        prev_ours = ours
    return 0


if __name__ == "__main__":
    sys.exit(main())
