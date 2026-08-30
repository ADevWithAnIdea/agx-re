#!/usr/bin/env python3
"""EXP-0206 -- the per-arm and per-value tables that RESULTS.md quotes.

Everything here is recomputed from raw/<gated run>/sweep.jsonl. Nothing is read
back from a manifest, and the CALIBRATION captures (census, pilot, smoke, the
killed run01) are excluded by name -- pooling them is what makes wave_audit's
field-keyed V and cross-run agreement unusable for this experiment.
"""
import collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
GATED = ["g17p_20260830_run03", "g17p_20260830_run04",
         "g17p_20260830_run05", "g17p_20260830_run06",
         "g17p_20260830_run07"]
VALID = {"ok", "silent_zero", "wrong_value", "not_written"}


def load():
    out = []
    for r in GATED:
        f = os.path.join(EXP, "raw", r, "sweep.jsonl")
        if not os.path.exists(f):
            continue
        for ln in open(f):
            try:
                rec = json.loads(ln)
            except Exception:                                   # noqa: BLE001
                continue
            rec["_run"] = r[-6:]
            out.append(rec)
    return out


def main():
    rs = load()
    by = collections.defaultdict(list)
    for r in rs:
        if r.get("role") in ("target", "control", "control_termination"):
            by[(r.get("role"), r.get("arm"))].append(r)
    print("%-4s %-56s %-6s %5s %5s %5s %5s %5s %5s %5s %s"
          % ("role", "arm", "runs", "n", "L", "V", "ok", "coh", "dead", "rej", "payload split"))
    for (role, arm), a in sorted(by.items()):
        runs = sorted({r["_run"] for r in a})
        val = [r for r in a if r["outcome"] in VALID]
        pay = collections.Counter((r["outcome"], (r["observed"] or {}).get("vh"))
                                  for r in val)
        b = collections.Counter(r.get("sem_bucket") for r in a)
        print("%-4s %-56s %-6s %5d %5d %5d %5d %5d %5d %5d %s"
              % (role[:4], arm[:56], ",".join(x[-2:] for x in runs), len(a),
                 len({r["value"] for r in val}),
                 len({(r["observed"] or {}).get("vh") for r in val}),
                 b.get("correct", 0), b.get("coherent", 0), b.get("dead", 0),
                 b.get("reject", 0),
                 " ".join("%s:%d" % (k[0][:4], v) for k, v in pay.most_common())))
    print()
    print("ledger: %d/%d ok" % (sum(1 for r in rs if r.get("ledger_ok") is True),
                                sum(1 for r in rs if "ledger_ok" in r)))
    print("contaminated cases: %d of %d"
          % (sum(1 for r in rs if r.get("contaminated")),
             sum(1 for r in rs if r.get("role") == "target")))
    for r in GATED:
        f = os.path.join(EXP, "raw", r, "procs.jsonl")
        if os.path.exists(f):
            n = [json.loads(l).get("n_other_agents", 0) for l in open(f)]
            print("%s concurrency: %d samples, other GPU procs min=%d max=%d mean=%.1f"
                  % (r, len(n), min(n), max(n), sum(n) / max(len(n), 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
