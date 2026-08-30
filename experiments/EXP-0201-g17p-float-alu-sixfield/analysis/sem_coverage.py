#!/usr/bin/env python3
"""EXP-0201 SEMANTIC COVERAGE -- exactly which values the independent predictor
committed to, and where the hardware confirmed or refuted it.

    python3 analysis/sem_coverage.py raw/<runA> raw/<runB>   -> analysis/sem_coverage.json

`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` section 2: `hardware-run` requires semantic
checks against an independent predictor OVER THE STATED RANGE, and `sem_checked == 0`
can never produce it. A label is therefore only as wide as the value set where the
predictor was actually confirmed -- so this script computes that set rather than
letting a per-arm aggregate stand in for it.

Three kinds of per-value prediction are scored separately, because they are
different claims:

  vector    the model named an 8-lane host-computed result for this value
            (`oracle.vals`), and the read-back either matched it or did not;
  fault     the model predicted the value produces no result (`predicted_fn ==
            "FAULT"`), scored against the OUTCOME, not against a vector;
  equiv     the model predicted `f(v) == f(v ^ mask)` for an operand descriptor
            whose top/size bits it claims are inert. This one is checked over the
            FULL range and is the only predictor `copysign.operands` has there.

A value counts as confirmed only if BOTH runs of the pair agree.
"""
import collections, glob, json, os, sys

HARD = {"fault", "hang", "undecodable", "measurement_failure", "invalid_run",
        "nondeterministic"}
EQUIV_MASK = {"copysign.operands": 0x81, "fspecial_est.srcA": 0x80}
TARGETS = [("falu3", "op"), ("falu3_ext", "op"), ("fspecial_est", "srcA"),
           ("falu3_srcmod12", "opsel"), ("falu3_srcmod12", "ctrl"),
           ("copysign", "operands")]


def sig(d):
    o = d.get("observed") or {}
    if d.get("outcome") in HARD:
        return "hard:" + str(d.get("outcome"))
    return json.dumps({k: o.get(k) for k in
                       ("status", "vals_u32", "aux_u32", "sent_u32", "tail_u32",
                        "unwritten", "sentinel_ok", "tail_ok")}, sort_keys=True)


def load(d):
    out = []
    for f in sorted(glob.glob(os.path.join(d, "sweep.jsonl"))):
        for ln in open(f, errors="replace"):
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def main():
    dirs = sys.argv[1:]
    if len(dirs) < 2:
        print(__doc__); return 2
    exp = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    A, B = load(dirs[0]), load(dirs[1])
    res = {}
    for mnem, field in TARGETS:
        key = "%s.%s" % (mnem, field)
        arms = sorted({d["arm"] for d in A
                       if d.get("instr") == mnem and d.get("field") == field})
        per_arm = {}
        for arm in arms:
            a = {d["value"]: d for d in A if d.get("arm") == arm and d.get("field") == field}
            b = {d["value"]: d for d in B if d.get("arm") == arm and d.get("field") == field}
            common = sorted(set(a) & set(b))
            vec_pred, vec_ok, vec_bad = [], [], []
            flt_pred, flt_ok = [], []
            for v in common:
                oa, ob = a[v].get("oracle") or {}, b[v].get("oracle") or {}
                if oa.get("vals") is not None:
                    vec_pred.append(v)
                    if a[v].get("match") and b[v].get("match"):
                        vec_ok.append(v)
                    else:
                        vec_bad.append(v)
                if oa.get("predicted_fn") == "FAULT" and ob.get("predicted_fn") == "FAULT":
                    flt_pred.append(v)
                    if a[v].get("outcome") in ("fault", "hang") and \
                       b[v].get("outcome") in ("fault", "hang"):
                        flt_ok.append(v)
            eq = None
            m = EQUIV_MASK.get(key)
            if m:
                pairs = [(v, v ^ m) for v in common if v < (v ^ m) and (v ^ m) in a]
                bad = [p for p in pairs
                       if sig(a[p[0]]) != sig(a[p[1]]) or sig(b[p[0]]) != sig(b[p[1]])]
                eq = {"mask": m, "pairs": len(pairs), "violations": len(bad),
                      "violating_pairs": [list(x) for x in bad[:16]]}
            per_arm[arm] = {
                "values_common": len(common),
                "vector_predicted": len(vec_pred), "vector_confirmed": len(vec_ok),
                "vector_refuted": len(vec_bad),
                "vector_confirmed_values": vec_ok,
                "vector_refuted_values": vec_bad[:64],
                "fault_predicted": len(flt_pred), "fault_confirmed": len(flt_ok),
                "inert_bit_equivalence": eq,
                "outcomes": dict(collections.Counter(
                    a[v].get("outcome") for v in common)),
            }
        best = max(per_arm, key=lambda k: (per_arm[k]["vector_confirmed"]
                                           + per_arm[k]["fault_confirmed"]))
        res[key] = {"arms": per_arm, "best_arm": best,
                    "sem_confirmed_total": (per_arm[best]["vector_confirmed"]
                                            + per_arm[best]["fault_confirmed"])}
    json.dump(res, open(os.path.join(exp, "analysis", "sem_coverage.json"), "w"),
              indent=1)
    for k, v in res.items():
        e = v["arms"][v["best_arm"]]
        eq = e["inert_bit_equivalence"]
        print("%-24s best=%-34s vec %d/%d conf, %d refuted | fault %d/%d | equiv %s"
              % (k, v["best_arm"], e["vector_confirmed"], e["vector_predicted"],
                 e["vector_refuted"], e["fault_confirmed"], e["fault_predicted"],
                 ("%d pairs, %d violations" % (eq["pairs"], eq["violations"])) if eq else "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
