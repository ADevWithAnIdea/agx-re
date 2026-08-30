#!/usr/bin/env python3
"""gates.py -- EXP-0199 AMENDMENT-01 analysis.

Scores the two GATED CONFIRMATION captures (g17p_conf01 shuffled, g17p_conf04
reversed) against the five gates of RE_EXPERIMENT_PROCESS_CORRECTIONS and emits
the six independent axes required by its §2.

    python3 analysis/gates.py            # -> analysis/gate_report.json + stdout

The discovery captures (g17p_run01*, g17p_run02*, smoke01, prefreeze) are read
only to report what they contributed; no verdict rests on them alone.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# EXP-0210: this copy lives outside EXP-0199, so EXP is taken from the environment.
EXP = os.environ.get("EXP0210_EXPDIR",
                     os.path.abspath(os.path.join(HERE, "..", "..", "..",
                                     "EXP-0199-g17p-instruction-level")))
RAW = os.path.join(EXP, "raw")
import os as _os
# EXP-0210: VERBATIM COPY of EXP-0199/analysis/gates.py with ONE change -- the two run ids
# are taken from the environment so the same scoring can be pointed at the quiet pair.
# EXP-0199 itself is not modified. Default is EXP-0199's own committed pair.
CONF = _os.environ.get("EXP0210_CONF", "g17p_conf01,g17p_conf04").split(",")


def load(rid):
    p = os.path.join(RAW, rid, "sweep.jsonl")
    return {json.loads(l)["case"]: json.loads(l) for l in open(p)}


def obskey(r):
    """Cross-run identity of an observation."""
    o, ob = r["outcome"], r.get("observed", {})
    if o in ("fault", "hang"):
        return (o, r.get("errdom", ""))
    if "h" in ob:
        return (o, ob["h"])
    if "ph" in ob and "dh" in ob:
        return (o, ob["ph"], ob["dh"])
    if "ph" in ob:
        return (o, ob["ph"])
    return (o,)


def mask_rule(vals):
    """Tightest single (mask,value) rule admitting exactly `vals` over 0..255."""
    if not vals:
        return None
    vals = sorted(set(vals))
    ones, zeros = 0xFF, 0xFF
    for v in vals:
        ones &= v
        zeros &= (~v) & 0xFF
    mask = ones | zeros
    val = vals[0] & mask
    adm = [v for v in range(256) if (v & mask) == val]
    return dict(mask="0x%02x" % mask, value="0x%02x" % val,
                exact=(adm == vals), n_admitted=len(adm), n_observed=len(vals))


def main():
    A, B = load(CONF[0]), load(CONF[1])
    common = sorted(set(A) & set(B))

    rep = {"runs": CONF, "cases_conf01": len(A), "cases_conf04": len(B),
           "common": len(common), "gate_A": {}, "groups": {}, "arms": {}}

    # ---------------- GATE A : the actual-byte ledger ---------------------
    ledger_checked = ledger_failed = 0
    req_by_group = collections.defaultdict(set)
    act_by_group = collections.defaultdict(set)
    for c in common:
        for r in (A[c], B[c]):
            L = r.get("ledger") or {}
            if L.get("checked"):
                ledger_checked += 1
                if not L.get("ok"):
                    ledger_failed += 1
        r = A[c]
        if r.get("field") and r.get("req_bytes"):
            g = (r.get("instr"), r["field"], r.get("site"), r.get("carrier"))
            req_by_group[g].add(r["req_bytes"])
            act = r.get("actual", {}).get(str(r.get("anchor", "")), None)
            if act is None and r.get("actual"):
                # the anchor key is recorded in the case; fall back to the
                # window that starts with the requested bytes
                for k, v in r["actual"].items():
                    if v.startswith(r["req_bytes"]):
                        act = v
                        break
            if act:
                act_by_group[g].add(act[:len(r["req_bytes"])])
    rep["gate_A"] = dict(ledger_checks=ledger_checked,
                         ledger_failures=ledger_failed,
                         pass_=(ledger_failed == 0 and ledger_checked > 0))

    # ---------------- per-group tallies -----------------------------------
    groups = collections.defaultdict(list)
    for c in common:
        r = A[c]
        if r.get("field"):
            groups[(r.get("instr"), r["field"], r.get("site"),
                    r.get("carrier"))].append(c)

    for g, cases in sorted(groups.items(), key=str):
        n = agree = disagree = mf = 0
        outc = collections.Counter()
        ok_vals, fault_vals, hang_vals = [], [], []
        for c in cases:
            ra, rb = A[c], B[c]
            if "measurement_failed" in (ra["outcome"], rb["outcome"]) or \
               "invalid_ledger" in (ra["outcome"], rb["outcome"]):
                mf += 1
                continue
            n += 1
            outc[ra["outcome"]] += 1
            if obskey(ra) == obskey(rb):
                agree += 1
            else:
                disagree += 1
            v = ra.get("value")
            if ra["outcome"] == "ok" and isinstance(v, int):
                ok_vals.append(v)
            if ra["outcome"] == "fault":
                fault_vals.append(v)
            if ra["outcome"] == "hang":
                hang_vals.append(v)
        key = "%s.%s@%s/%s" % g
        moved = n - outc.get("ok", 0)
        rep["groups"][key] = dict(
            dispatched=n, measurement_failed=mf,
            distinct_requested=len(req_by_group.get(g, ())),
            distinct_actual=len(act_by_group.get(g, ())),
            agree=agree, disagree=disagree,
            agreement=round(agree / n, 5) if n else None,
            moved=moved, outcomes=dict(outc),
            n_ok=outc.get("ok", 0), n_fault=len(fault_vals), n_hang=len(hang_vals),
            accepted_rule=mask_rule(ok_vals) if ok_vals else None,
            gate_agreement=(n > 0 and agree / n >= 0.99),
            gate_movement=(moved >= 2.0 * disagree and moved > 0),
            gate_measfail=(mf <= 0.01 * max(len(cases), 1)))
    return A, B, common, rep


if __name__ == "__main__":
    A, B, common, rep = main()
    print("GATE A ledger: %d checks, %d failures -> %s" %
          (rep["gate_A"]["ledger_checks"], rep["gate_A"]["ledger_failures"],
           "PASS" if rep["gate_A"]["pass_"] else "FAIL"))
    print()
    for k, v in rep["groups"].items():
        print("%-44s disp=%-4d req=%-4d act=%-4d agree=%-7s moved=%-4d dis=%-3d mf=%-3d %s"
              % (k, v["dispatched"], v["distinct_requested"], v["distinct_actual"],
                 v["agreement"], v["moved"], v["disagree"], v["measurement_failed"],
                 json.dumps(v["outcomes"])))
        if v["accepted_rule"]:
            r = v["accepted_rule"]
            print("      ok-set: %d values -> (v & %s) == %s   exact=%s"
                  % (r["n_observed"], r["mask"], r["value"], r["exact"]))
    json.dump(rep, open(os.path.join(HERE, "gate_report.json"), "w"), indent=1)
    print("\nwrote analysis/gate_report.json")
