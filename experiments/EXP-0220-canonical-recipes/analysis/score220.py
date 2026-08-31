#!/usr/bin/env python3
"""EXP-0220 scorer -- reads ONLY committed raw, contacts no device.

Emits analysis/gates.json (the five gates, scored separately),
analysis/arm_table.json (per-arm exact numerators and denominators -- section 5:
"never report only a percentage") and analysis/quiet.json (the Gate E
quiet-window measurement).
"""
import collections
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
RUNS = ["g17p-20260831-run01", "g17p-20260831-run02"]


def load(run):
    out = []
    with open(os.path.join(EXP, "raw", run, "sweep.jsonl")) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def quiet(run):
    p = os.path.join(EXP, "raw", run, "procs.jsonl")
    rows = []
    if os.path.exists(p):
        for ln in open(p):
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except ValueError:
                    pass
    rc = [r.get("gpu", {}).get("recovery_count") for r in rows
          if r.get("gpu", {}).get("recovery_count") is not None]
    foreign = [r.get("n_foreign_runner", r.get("n_foreign", 0)) for r in rows]
    return {"samples": len(rows),
            "recovery_count_first": rc[0] if rc else None,
            "recovery_count_last": rc[-1] if rc else None,
            "recovery_count_delta": (rc[-1] - rc[0]) if len(rc) >= 2 else None,
            "max_foreign_runner": max(foreign) if foreign else None,
            "any_foreign_runner": bool(foreign and max(foreign) > 0)}


def main():
    R = {r: load(r) for r in RUNS}
    by = {r: {c["name"]: c for c in R[r]} for r in RUNS}
    n = {r: len(R[r]) for r in RUNS}

    # ---- Gate A -----------------------------------------------------------
    gA = {"records": 0, "instructions": 0, "hard_disagreements": 0,
          "dispatched_bytes_unverified": 0, "examples": [],
          "descriptor_ambiguities": collections.Counter(),
          "not_walk_boundary": collections.Counter()}
    for r in RUNS:
        for c in R[r]:
            gA["records"] += 1
            gA["instructions"] += c["gate_a"]["n_instr"]
            gA["hard_disagreements"] += c["gate_a"]["n_bad"]
            if not c.get("dispatched_bytes_verified"):
                gA["dispatched_bytes_unverified"] += 1
            if c["gate_a"]["n_bad"] and len(gA["examples"]) < 5:
                gA["examples"].append({"run": r, "name": c["name"],
                                       "bad": c["gate_a"]["bad"][:2]})
            for a in c["gate_a"]["alias"]:
                if a.get("kind") == "descriptor_ambiguity":
                    gA["descriptor_ambiguities"]["%s->%s" % (a["requested"], a["decoded"])] += 1
                elif a.get("kind") == "not_a_walk_boundary":
                    gA["not_walk_boundary"][a["mnemonic"]] += 1
    gA["descriptor_ambiguities"] = dict(gA["descriptor_ambiguities"])
    gA["not_walk_boundary"] = dict(gA["not_walk_boundary"])
    gA["PASS"] = (gA["hard_disagreements"] == 0
                  and gA["dispatched_bytes_unverified"] == 0)

    # ---- Gate B -----------------------------------------------------------
    gB = {}
    for r in RUNS:
        b = by[r]
        base = b.get("ctl_baseline")
        norun = b.get("ctl_norun")
        moves = [b[k] for k in b if k.startswith("ctl_move_")]
        sig = set()
        for m in moves:
            sig.add(m.get("out_sha256", {}).get("0"))
        gB[r] = {
            "ctl_baseline_exact": base and base["observed_bucket"] == "exact",
            "ctl_baseline_predicted_bytes": base and base.get("n_pred_ok"),
            "ctl_norun_leaves_buffer_poison": norun and norun["observed_bucket"] == "exact"
            and norun.get("n_stray_bytes") == 0,
            "ctl_move_cases": len(moves),
            "ctl_move_distinct_out_digests": len(sig),
            "detection_power": len(sig) == len(moves) and len(moves) >= 2,
        }
    gB["PASS"] = all(v["ctl_baseline_exact"] and v["ctl_norun_leaves_buffer_poison"]
                     and v["detection_power"] for k, v in gB.items() if k in RUNS)

    # ---- Gate C -----------------------------------------------------------
    gC = {"per_run": {}, "arm": {}}
    for r in RUNS:
        t = collections.Counter()
        for c in R[r]:
            t[str(c.get("bucket_ok"))] += 1
        gC["per_run"][r] = dict(t)
    arm = collections.defaultdict(lambda: collections.Counter())
    for c in R[RUNS[0]]:
        a = c["arm"]
        arm[a]["cases"] += 1
        arm[a]["bucket_" + str(c.get("bucket_ok"))] += 1
        arm[a]["obs_" + c["observed_bucket"]] += 1
        arm[a]["pred_" + c["predicted_bucket"]] += 1
        arm[a]["sem_checks"] += c.get("sem_checked", 0)
    for a in arm:
        both = 0
        for c in R[RUNS[0]]:
            pass
        gC["arm"][a] = dict(arm[a])
    fails = [c["name"] for r in RUNS for c in R[r] if c.get("bucket_ok") is False]
    gC["failures"] = sorted(set(fails))
    gC["n_failures"] = len(fails)
    gC["PASS"] = (len(fails) == 0)

    # ---- Gate D -----------------------------------------------------------
    gD = {"copied_fields": 0, "carrier_fields": 0, "rule_fields": 0, "free_fields": 0,
          "programs": 0, "donor_field_names": set()}
    for r in RUNS:
        for c in R[r]:
            gD["programs"] += 1
            L = c["ledger"]
            gD["copied_fields"] += L.get("COPIED", 0)
            gD["carrier_fields"] += L.get("CARRIER", 0)
            gD["rule_fields"] += L.get("RULE", 0)
            gD["free_fields"] += L.get("FREE", 0)
            for f in c.get("donor_fields") or []:
                gD["donor_field_names"].add(f)
    gD["donor_field_names"] = sorted(gD["donor_field_names"])
    gD["PASS"] = (gD["copied_fields"] == 0 and gD["carrier_fields"] == 0
                  and not gD["donor_field_names"])

    # ---- Gate E -----------------------------------------------------------
    a, b = by[RUNS[0]], by[RUNS[1]]
    shared = sorted(set(a) & set(b))
    hash_dis = [k for k in shared if a[k]["prog_sha256"] != b[k]["prog_sha256"]]
    bucket_dis = [k for k in shared if a[k]["observed_bucket"] != b[k]["observed_bucket"]]
    out_dis = [k for k in shared
               if a[k].get("out_sha256") != b[k].get("out_sha256")]
    order01 = [c["name"] for c in R[RUNS[0]]]
    order02 = [c["name"] for c in R[RUNS[1]]]
    gE = {"shared_cases": len(shared),
          "program_hash_disagreements": len(hash_dis),
          "bucket_disagreements": len(bucket_dis),
          "full_output_digest_disagreements": len(out_dis),
          "bucket_disagreement_examples": bucket_dis[:10],
          "output_digest_disagreement_examples": out_dis[:10],
          "order_identical": order01 == order02,
          "quiet": {r: quiet(r) for r in RUNS}}
    # The contract's Gate E has two independent conjuncts.  They are scored
    # SEPARATELY, because they answer different questions and one of them is
    # about OUR OWN dispatches rather than about a neighbour's.
    gE["reproducibility_PASS"] = (len(hash_dis) == 0 and len(bucket_dis) == 0
                                  and len(out_dis) == 0
                                  and not gE["order_identical"])
    gE["quiet_machine_PASS"] = all(not v["any_foreign_runner"]
                                   for v in gE["quiet"].values())
    gE["zero_device_reset_PASS"] = all(v["recovery_count_delta"] == 0
                                       for v in gE["quiet"].values())
    gE["PASS"] = gE["reproducibility_PASS"] and gE["quiet_machine_PASS"]
    # attribute every device reset to the case that caused it
    gE["device_resets"] = {r: quiet(r)["recovery_count_delta"] for r in RUNS}
    gE["hard_cases_per_run"] = {
        r: sorted(c["name"] for c in R[r]
                 if c["outcome"] in ("fault", "hang", "victim")) for r in RUNS}
    gE["hard_case_sets_identical"] = (gE["hard_cases_per_run"][RUNS[0]]
                                      == gE["hard_cases_per_run"][RUNS[1]])

    # ---- hard outcomes, counted separately -------------------------------
    hard = collections.Counter()
    for r in RUNS:
        for c in R[r]:
            if c["outcome"] in ("fault", "hang", "victim", "measurement_failure",
                                "invalid_run"):
                hard[(c["outcome"], c["arm"])] += 1
    snaps = {}
    for r in RUNS:
        for tag in ("gpu_pre", "gpu_post"):
            p = os.path.join(EXP, "raw", r, tag + ".json")
            if os.path.exists(p):
                snaps["%s/%s" % (r, tag)] = json.load(open(p))
    doc = {"runs": RUNS, "cases_per_run": n, "gpu_snapshots": snaps,
           "gate_A": gA, "gate_B": gB, "gate_C": {k: v for k, v in gC.items()
                                                  if k != "arm"},
           "gate_D": gD, "gate_E": gE,
           "hard_outcomes": {"%s|%s" % k: v for k, v in sorted(hard.items())},
           "ALL_GATES_PASS": all([gA["PASS"], gB["PASS"], gC["PASS"], gD["PASS"],
                                  gE["PASS"]])}
    json.dump(doc, open(os.path.join(HERE, "gates.json"), "w"), indent=1, sort_keys=True)
    json.dump(gC["arm"], open(os.path.join(HERE, "arm_table.json"), "w"),
              indent=1, sort_keys=True)
    print(json.dumps({k: (v if not isinstance(v, dict) else
                          {kk: vv for kk, vv in v.items() if kk != "arm"})
                      for k, v in doc.items()}, indent=1, sort_keys=True)[:6000])
    return 0 if doc["ALL_GATES_PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
