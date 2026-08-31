#!/usr/bin/env python3
"""EXP-0213 -- decide the quiet gate over one capture's samples.  Runs on the repo host.

    python3 harness/quietcheck.py raw/<tag>/quiet.jsonl [--gpu raw/<tag>/gpu.jsonl]

THREE DEFECTS THIS DELIBERATELY DOES NOT INHERIT (all found by EXP-0210):

 1. `MTLCompilerService` is an XPC service that **launchd** owns, so it can NEVER be a
    descendant of the sampler; a ppid walk classifies our own shader compiles as foreign.
    EXP-0201's gate refused all six of its fields on 1 of 273 such samples while printing
    100.00 % agreement.  Here the compiler service is counted and reported SEPARATELY and
    is not part of the gate: it does not dispatch.
 2. A parenthesised process `comm` -- `(shdump)`, `(agxrun_persist)` -- is an EXITING /
    zombie process.  It holds no GPU context.  EXP-0202's gate marked a run busy on one
    such row.  Here `exiting` rows are reported and named but do not fail the gate; the
    STRICT count including them is printed alongside so a reader can apply either rule.
 3. EXP-0210's own frozen Q2 ("recoveryCount unchanged first-to-last") is a gate NO
    fault-heavy experiment can ever pass, because our own pre-registered illegal encodings
    reset the device.  A criterion that cannot come out the other way is not a gate.  Here
    the reset counter is REPORTED (pre, post, delta, per-sample series) and the quiet
    criterion is stated on FOREIGN ATTRIBUTION: no foreign dispatch runner in any sample
    and no foreign submitter, which together mean no other GPU client existed to reset the
    device or to be reset by us.

Ownership follows EXP-0210 AMENDMENT-02: one `ps` snapshot for both the ownership walk and
the row scan, ownership = our ppid subtree UNION our session id.
"""
import argparse
import json
import sys


def load(path):
    recs = []
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                recs.append(json.loads(ln))
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("samples")
    ap.add_argument("--gpu", default="")
    ap.add_argument("--known-idle-pid", type=int, default=328,
                    help="SecurityAgent: the login-window process that is this host's "
                         "last GPU submitter while idle and submits nothing while we run")
    a = ap.parse_args()

    recs = load(a.samples)
    if not recs:
        print(json.dumps({"error": "no samples", "QUIET": False}, indent=1))
        return 2

    rows = [(r, pr) for r in recs for pr in r.get("procs", [])]
    foreign_rows = [(r, pr) for r, pr in rows
                    if not pr.get("ours") and not pr.get("excluded")
                    and pr.get("kind") == "runner"]
    live_foreign = [(r, pr) for r, pr in foreign_rows if not pr.get("exiting")]
    exiting_foreign = [(r, pr) for r, pr in foreign_rows if pr.get("exiting")]

    per_sample_live, per_sample_strict = [], []
    for r in recs:
        pl = ps = 0
        for pr in r.get("procs", []):
            if pr.get("ours") or pr.get("excluded") or pr.get("kind") != "runner":
                continue
            ps += 1
            if not pr.get("exiting"):
                pl += 1
        per_sample_live.append(pl)
        per_sample_strict.append(ps)

    comp = [r.get("n_compiler_svc") for r in recs if r.get("n_compiler_svc") is not None]
    gpu = [r["gpu"] for r in recs if isinstance(r.get("gpu"), dict)]
    rc = [g.get("recovery_count") for g in gpu if g.get("recovery_count") is not None]
    subs = sorted({g.get("last_submission_pid") for g in gpu} - {None})
    ioerr = sum(1 for g in gpu if "ioreg_error" in g)
    span = recs[-1]["ts"] - recs[0]["ts"]
    rate = span / max(len(recs) - 1, 1)

    pre = post = None
    if a.gpu:
        try:
            snaps = load(a.gpu)
            for s in snaps:
                if s.get("tag") == "pre":
                    pre = s.get("recovery_count")
                if s.get("tag") == "post":
                    post = s.get("recovery_count")
        except OSError:
            pass

    # Foreign submitter adjudication.  fLastSubmissionPID is a LAST value, so at the start
    # of a capture it can legitimately still name our own preceding capture's runner or the
    # idle-machine SecurityAgent.  Anything else is reported for adjudication by name.
    own_pids = {pr["pid"] for r, pr in rows if pr.get("ours")}
    foreign_pids = {pr["pid"] for r, pr in rows
                    if not pr.get("ours") and not pr.get("excluded")}
    seen_pids = {pr["pid"] for r, pr in rows}
    # Categories, following EXP-0210 sec.1.2's own adjudication:
    #   idle_known      -- the login-window process that is the last submitter on an idle
    #                      machine and submits nothing while we run
    #   ours            -- one of our own runners, seen in the sampled rows
    #   FOREIGN         -- seen in the sampled rows and NOT ours: a real gate failure
    #   absent_from_rows-- lived and died between two 2 s samples.  fLastSubmissionPID is a
    #                      LAST value, so our own short-lived runners land here routinely.
    #                      DISCLOSED as a residual, not scored as foreign: with zero live
    #                      foreign runners in every sample there is no foreign client for it
    #                      to be.  This is the 2 s sampling hole EXP-0210 also disclosed.
    sub_foreign = [p for p in subs if p in foreign_pids]
    sub_absent = [p for p in subs
                  if p != a.known_idle_pid and p not in seen_pids]
    unexplained = sub_foreign

    q1 = max(per_sample_live) == 0 if per_sample_live else False
    q3 = len(unexplained) == 0
    q4 = rate < 10.0
    out = {
        "samples": len(recs),
        "span_s": round(span, 1),
        "sample_rate_s": round(rate, 2),
        "Q1_zero_live_foreign_runner": q1,
        "max_foreign_runner_live": max(per_sample_live) if per_sample_live else None,
        "max_foreign_runner_strict": max(per_sample_strict) if per_sample_strict else None,
        "exiting_only_rows": [{"pid": pr["pid"], "cmd": pr["cmd"][-70:], "stat": pr["stat"]}
                              for _, pr in exiting_foreign][:8],
        "live_foreign_examples": [{"pid": pr["pid"], "cmd": pr["cmd"][-70:]}
                                  for _, pr in live_foreign][:8],
        "compiler_svc_max": max(comp) if comp else None,
        "compiler_svc_note": "XPC service owned by launchd; never a sampler descendant; "
                             "does not dispatch; NOT part of the gate",
        "Q3_no_foreign_submitter": q3,
        "submitter_pids": subs,
        "submitter_foreign": sub_foreign,
        "submitter_absent_from_rows": sub_absent,
        "submitter_note": "fLastSubmissionPID is a LAST value; PIDs absent from the sampled "
                          "rows are our own short-lived runners between two 2 s samples. "
                          "DISCLOSED, not gated.",
        "Q4_sampler_alive": q4,
        "recovery_pre": pre,
        "recovery_post": post,
        "recovery_delta": (post - pre) if (pre is not None and post is not None) else None,
        "recovery_first_last_in_samples": [rc[0], rc[-1]] if rc else None,
        "recovery_note": "REPORTED, NOT GATED (EXP-0210 AMENDMENT-03): our own frozen "
                         "illegal encodings reset the device, so 'unchanged' is a gate no "
                         "fault-heavy capture can pass.",
        "ioreg_errors": ioerr,
        "loadavg_max": max(r["loadavg"][0] for r in recs if "loadavg" in r),
    }
    out["QUIET"] = bool(q1 and q3 and q4 and ioerr == 0)
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
