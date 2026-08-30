#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 -- the four "WITHHELD ... Case C" / EXP-0191-detection-gate clauses
appended to notes in the NOT-CHECKED set.

  n3_sample_read.tail      "Case C: fewer than two distinct VALID payloads (V=1)
                            but 1522 LEGAL values"          -> EXP-0192
  ray_move_copy6.optype    "Case C: 1 distinct VALID payload(s) across 191 LEGAL
                            values", "moved_total equals the hard-class cell
                            count EXACTLY"                   -> EXP-0193
  vtx_coord_xform.operand  "Case C: 1 distinct VALID payload(s) across 817 LEGAL
                            values"                          -> EXP-0193
  pop_reconverge.scope     "512 valid observations per arm, ONE distinct payload,
                            and no control of any kind at arm level", "passes only
                            at the looser CARRIER join", "(8 arms with no
                            observation ...)"                -> EXP-0191

Checked against those experiments' own committed structured outputs (not their
prose), so a number the note invented rather than carried is caught.

Read-only.  Writes analysis/check_withheld.json.
"""
import collections, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")


def j(p):
    return json.load(open(os.path.join(EXPS, p)))


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    r0192 = j("EXP-0192-fault-as-movement/analysis/reclassify.json")
    r0193 = j("EXP-0193-stable-live-sweep/analysis/reclassify.json")
    g0191 = j("EXP-0191-detection-gate/analysis/gate_results.json")
    out = {}

    def note(k):
        m, f = k.split(".", 1)
        return val["instructions"][m][f].get("note") or ""

    RXC = re.compile(r"(?:V=1\) but (\d+) LEGAL values|1 distinct VALID payload\(s\) "
                     r"across (\d+) LEGAL values)")
    for k, src, name in (("n3_sample_read.tail", r0192, "EXP-0192"),
                         ("ray_move_copy6.optype", r0193, "EXP-0193"),
                         ("vtx_coord_xform.operand", r0193, "EXP-0193")):
        n = note(k)
        mo = RXC.search(n)
        claimed = int(mo.group(1) or mo.group(2)) if mo else None
        e = src.get(k, {})
        claims = [{"claim": "case_C_legal_values", "source": name,
                   "claimed": claimed, "raw": e.get("L_legal_values_max"),
                   "ok": claimed == e.get("L_legal_values_max")},
                  {"claim": "case_C_V_equals_1", "source": name,
                   "claimed": 1, "raw": e.get("V_valid_payloads_max"),
                   "ok": e.get("V_valid_payloads_max") == 1},
                  {"claim": "case_letter", "claimed": "C", "raw": e.get("case"),
                   "ok": e.get("case") == "C"}]
        if "moved_total` equals the hard-class cell count EXACTLY" in n:
            claims.append({"claim": "hard_class_cell_count_present",
                           "raw": e.get("n_fault_cells"),
                           "ok": bool(e.get("n_fault_cells"))})
        out[k] = {"note": n, "claims": claims,
                  "verdict": "SUPPORTED" if all(c["ok"] for c in claims) else "CONTRADICTED"}

    # pop_reconverge.scope
    n = note("pop_reconverge.scope")
    arm = g0191["fields"]["pop_reconverge.scope"]["arms"][0]
    st, ca = arm["strict"], arm["carrier"]
    d1 = g0191["_meta"]["discrimination"]["D1_no_observation_arms_must_fail"]["n"]
    claims = [
        {"claim": "512 valid observations per arm",
         "claimed": 512, "raw": st["records_valid"], "ok": st["records_valid"].get("SIBLING") == 512},
        {"claim": "ONE distinct payload",
         "claimed": 1, "raw": st["n_distinct_payloads"],
         "ok": set(st["n_distinct_payloads"].values()) == {1}},
        {"claim": "no control of any kind at arm level",
         "raw": {"control_records_relied_on": st["control_records_relied_on"],
                 "pass_falsifier": st["pass_falsifier"],
                 "pass_live_control": st["pass_live_control"],
                 "pass_sibling_field": st["pass_sibling_field"]},
         "ok": (not st["control_records_relied_on"] and not st["pass_falsifier"]
                and not st["pass_live_control"] and not st["pass_sibling_field"])},
        {"claim": "passes only at the looser CARRIER join",
         "raw": {"strict_pass": st["pass"], "carrier_pass": ca["pass"]},
         "ok": (st["pass"] is False and ca["pass"] is True)},
        {"claim": "8 arms with no observation",
         "claimed": 8, "raw": d1, "ok": d1 == 8}]
    out["pop_reconverge.scope"] = {
        "note": n, "claims": claims,
        "verdict": "SUPPORTED" if all(c["ok"] for c in claims) else "CONTRADICTED"}

    json.dump(out, open(os.path.join(HERE, "check_withheld.json"), "w"), indent=1, sort_keys=True)
    c = collections.Counter(v["verdict"] for v in out.values())
    print("withheld-clause family:", len(out), dict(c))
    for k, v in sorted(out.items()):
        print("  %-28s %s" % (k, v["verdict"]))
        for cl in v["claims"]:
            if not cl["ok"]:
                print("       FAILS", json.dumps(cl)[:300])


if __name__ == "__main__":
    main()
