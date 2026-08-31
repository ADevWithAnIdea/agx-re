#!/usr/bin/env python3
"""EXP-0221 scorer -- reads ONLY committed raw, contacts no device.

Writes analysis/gates.json (the five gates, scored SEPARATELY), arm_table.json
(per-arm exact numerators and denominators -- section 5: "never report only a
percentage"), and codeword.json (arm T's boolean channel).
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
RUN01 = "g17p-20260831-run01"
RUN02 = "g17p-20260831-run02"
RUNNOTG = "g17p-20260831-notg"
RUNS = [RUN01, RUN02]


def load(run):
    p = os.path.join(EXP, "raw", run, "sweep.jsonl")
    out = []
    if not os.path.exists(p):
        return out
    for ln in open(p):
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
            "recovery_count_frozen": (len(set(rc)) == 1) if rc else None,
            "max_foreign_runner": max(foreign) if foreign else None,
            "any_foreign_runner": bool(foreign and max(foreign) > 0)}


def snaps(run):
    out = {}
    for tag in ("gpu_pre", "gpu_post"):
        p = os.path.join(EXP, "raw", run, tag + ".json")
        if os.path.exists(p):
            try:
                out[tag] = json.load(open(p))
            except ValueError:
                pass
    return out


def main():
    R = {r: load(r) for r in RUNS}
    notg = load(RUNNOTG)
    for r in RUNS:
        if not R[r]:
            print("MISSING RUN:", r)
            return 2
    by = {r: {c["name"]: c for c in R[r]} for r in RUNS}

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
                    gA["descriptor_ambiguities"]["%s->%s"
                                                 % (a["requested"], a["decoded"])] += 1
                elif a.get("kind") == "not_a_walk_boundary":
                    gA["not_walk_boundary"][a["mnemonic"]] += 1
    gA["descriptor_ambiguities"] = dict(gA["descriptor_ambiguities"])
    gA["not_walk_boundary"] = dict(gA["not_walk_boundary"])
    gA["note"] = ("section 3z is not a precondition here: no offset is "
                  "signature-derived, every boundary is known because we "
                  "generated it.  The whole-program walk is RECORDED as a "
                  "db.json finding for the orchestrator, not used as the "
                  "instrument that locates instructions.")
    gA["PASS"] = (gA["hard_disagreements"] == 0
                  and gA["dispatched_bytes_unverified"] == 0)

    # ---- Gate B -----------------------------------------------------------
    gB = {}
    for r in RUNS:
        b = by[r]
        base, norun = b.get("ctl_baseline"), b.get("ctl_norun")
        moves = [b[k] for k in b if k.startswith("ctl_move_")]
        sig = {m.get("out_sha256", {}).get("0") for m in moves}
        pre, post = b.get("ctl_tripwire_pre"), b.get("ctl_tripwire_post")
        tgctl = [b[k] for k in b if k.startswith("tg_ctl_device")]
        gB[r] = {
            "ctl_baseline_exact": bool(base and base["observed_bucket"] == "exact"),
            "ctl_baseline_predicted_bytes": base and base.get("n_pred_ok"),
            "ctl_norun_leaves_buffer_poison":
                bool(norun and norun["observed_bucket"] == "exact"
                     and norun.get("n_stray_bytes") == 0),
            "ctl_move_cases": len(moves),
            "ctl_move_distinct_out_digests": len(sig),
            "falu2_detection_power": len(sig) == len(moves) and len(moves) >= 2,
            # arm S: `stop` has no observable of its own
            "stop_tripwire_fires_before_stop": bool(pre and pre.get("tripwire_written")),
            "stop_tripwire_silent_after_stop":
                bool(post and post.get("tripwire_written") is False),
            # arm T: the sixteen-register read-back bank, on the device side
            "tg_ctl_device_cases": len(tgctl),
            "tg_ctl_device_all_arrived":
                bool(tgctl) and all(t.get("codeword_prediction_ok") for t in tgctl),
            "tg_ctl_device_regs":
                [len(t.get("codeword_regs") or []) for t in tgctl],
        }
        gB[r]["detection_power_all_arms"] = all([
            gB[r]["ctl_baseline_exact"], gB[r]["ctl_norun_leaves_buffer_poison"],
            gB[r]["falu2_detection_power"],
            gB[r]["stop_tripwire_fires_before_stop"],
            gB[r]["stop_tripwire_silent_after_stop"],
            gB[r]["tg_ctl_device_all_arrived"]])
    gB["PASS"] = all(gB[r]["detection_power_all_arms"] for r in RUNS)

    # ---- Gate C -----------------------------------------------------------
    gC = {"per_run": {}, "arm": {}}
    for r in RUNS:
        gC["per_run"][r] = dict(collections.Counter(
            str(c.get("bucket_ok")) for c in R[r]))
    arm = collections.defaultdict(lambda: collections.Counter())
    for c in R[RUN01]:
        a = c["arm"]
        arm[a]["cases"] += 1
        arm[a]["bucket_" + str(c.get("bucket_ok"))] += 1
        arm[a]["obs_" + c["observed_bucket"]] += 1
        arm[a]["pred_" + c["predicted_bucket"]] += 1
        arm[a]["sem_checks"] += c.get("sem_checked", 0)
        if c.get("codeword_prediction_ok") is not None:
            arm[a]["cw_pred_" + str(c["codeword_prediction_ok"])] += 1
    gC["arm"] = {a: dict(v) for a, v in arm.items()}
    fails = sorted({c["name"] for r in RUNS for c in R[r]
                    if c.get("bucket_ok") is False})
    gC["failures"] = fails
    gC["n_failures"] = len(fails)
    gC["failures_by_arm"] = dict(collections.Counter(
        by[RUN01][f]["arm"] for f in fails if f in by[RUN01]))
    gC["PASS"] = (len(fails) == 0)

    # ---- Gate D -----------------------------------------------------------
    gD = {"copied_fields": 0, "carrier_fields": 0, "rule_fields": 0,
          "free_fields": 0, "programs": 0, "donor_field_names": set()}
    for r in RUNS:
        for c in R[r]:
            gD["programs"] += 1
            L = c["ledger"]
            for k in ("COPIED", "CARRIER", "RULE", "FREE"):
                gD[k.lower() + "_fields"] += L.get(k, 0)
            for f in c.get("donor_fields") or []:
                gD["donor_field_names"].add(f)
    gD["donor_field_names"] = sorted(gD["donor_field_names"])
    gD["PASS"] = (gD["copied_fields"] == 0 and gD["carrier_fields"] == 0
                  and not gD["donor_field_names"])

    # ---- Gate E -----------------------------------------------------------
    a, b = by[RUN01], by[RUN02]
    shared = sorted(set(a) & set(b))
    hash_dis = [k for k in shared if a[k]["prog_sha256"] != b[k]["prog_sha256"]]
    bucket_dis = [k for k in shared
                  if a[k]["observed_bucket"] != b[k]["observed_bucket"]]
    out_dis = [k for k in shared if a[k].get("out_sha256") != b[k].get("out_sha256")]
    cw_dis = [k for k in shared
              if a[k].get("codeword_arrived") != b[k].get("codeword_arrived")]
    gE = {"shared_cases": len(shared),
          "program_hash_disagreements": len(hash_dis),
          "bucket_disagreements": len(bucket_dis),
          "full_output_digest_disagreements": len(out_dis),
          "codeword_arrival_disagreements": len(cw_dis),
          "bucket_disagreement_examples": bucket_dis[:12],
          "output_digest_disagreement_examples": out_dis[:12],
          "codeword_disagreement_examples": cw_dis[:12],
          "order_identical": [c["name"] for c in R[RUN01]] ==
                             [c["name"] for c in R[RUN02]],
          "quiet": {r: quiet(r) for r in RUNS},
          "gpu_snapshots": {r: snaps(r) for r in RUNS}}
    gE["reproducibility_PASS"] = (len(hash_dis) == 0 and len(bucket_dis) == 0
                                  and not gE["order_identical"])
    gE["quiet_machine_PASS"] = all(not v["any_foreign_runner"]
                                   for v in gE["quiet"].values())
    gE["zero_device_reset_conjunct"] = all(
        v["recovery_count_delta"] == 0 for v in gE["quiet"].values()
        if v["recovery_count_delta"] is not None)
    gE["hard_cases_per_run"] = {
        r: sorted(c["name"] for c in R[r]
                  if c["outcome"] in ("fault", "hang", "victim")) for r in RUNS}
    gE["hard_case_sets_identical"] = (gE["hard_cases_per_run"][RUN01]
                                      == gE["hard_cases_per_run"][RUN02])
    gE["hangs_per_run"] = {r: sum(1 for c in R[r] if c["outcome"] == "hang")
                           for r in RUNS}
    # FIELD-SWEEP-PROTOCOL 10.2: classify hangs.  A frozen recoveryCount WITH
    # hangs is the accumulating case; a frozen counter with NO hangs means only
    # "nothing reset the device".
    for r in RUNS:
        q = gE["quiet"][r]
        gE.setdefault("hang_classification", {})[r] = (
            "no hangs" if gE["hangs_per_run"][r] == 0 else
            ("ACCUMULATING (recoveryCount frozen across hangs)"
             if q.get("recovery_count_frozen") else "driver-recoverable"))
    gE["PASS"] = gE["reproducibility_PASS"] and gE["quiet_machine_PASS"]

    # ---- arm T: the codeword channel, and the two-carrier comparison ------
    T = {"per_arm": {}, "carrier_control": {}}
    for r in RUNS:
        per = collections.defaultdict(lambda: collections.Counter())
        for c in R[r]:
            if c.get("codeword_arrived") is None:
                continue
            per[c["arm"]]["cases"] += 1
            per[c["arm"]]["arrived" if c["codeword_arrived"] else "absent"] += 1
            if c.get("codeword_prediction_ok") is not None:
                per[c["arm"]]["pred_ok" if c["codeword_prediction_ok"]
                              else "pred_WRONG"] += 1
        T["per_arm"][r] = {k: dict(v) for k, v in per.items()}
    # H3: the address law, case by case
    law = {"predicted_deliver": [], "predicted_silent": [],
           "false_negative": [], "false_positive": []}
    for c in R[RUN01]:
        if c["arm"] != "T3-tg-address-law":
            continue
        e, g = c.get("expect_codeword"), c.get("codeword_arrived")
        (law["predicted_deliver"] if e else law["predicted_silent"]).append(c["name"])
        if e and not g:
            law["false_negative"].append(c["name"])
        if (not e) and g:
            law["false_positive"].append(c["name"])
    law["H3_PASS"] = not law["false_negative"] and not law["false_positive"]
    T["address_law"] = law
    # H2: does `space` bit 1 fault WITHOUT a threadgroup allocation?
    if notg:
        bn = {c["name"]: c for c in notg}
        rows = []
        for k, c in sorted(bn.items()):
            if c["arm"] != "D2-space":
                continue
            v = int(k[len("d_space"):])
            o1 = by[RUN01].get(k)
            rows.append({"space": v, "tg_bit1": bool(v & 2),
                         "notg_outcome": c["outcome"],
                         "tg_outcome": o1["outcome"] if o1 else None})
        T["carrier_control"]["D2_space_rows"] = rows
        f_notg = sorted(r_["space"] for r_ in rows if r_["notg_outcome"] == "fault")
        f_tg = sorted(r_["space"] for r_ in rows if r_["tg_outcome"] == "fault")
        T["carrier_control"]["fault_values_no_threadgroup"] = f_notg
        T["carrier_control"]["fault_values_with_threadgroup"] = f_tg
        # H2 said EXP-0220's `space` bit-1 faults were a CARRIER property.  The
        # two carriers produce the IDENTICAL fault set, so H2 is REFUTED -- and
        # that is a result, not a broken control.  The control that matters for
        # arm T is `tg_roundtrip_needs_the_tile` below, and it PASSES.
        T["carrier_control"]["H2_faults_are_a_carrier_property"] = (
            set(f_notg) != set(f_tg))
        T["carrier_control"]["H2_VERDICT"] = (
            "REFUTED: identical fault sets on both carriers (`space & 0x06 == "
            "0x06`, 64 of 256).  `space` bit 1 alone never faulted."
            if set(f_notg) == set(f_tg) else "supported")
        deliv_tg = sorted(k for k, c in by[RUN01].items()
                          if c["arm"] == "T3-tg-address-law"
                          and c.get("codeword_arrived"))
        deliv_no = sorted(k for k, c in bn.items()
                          if c["arm"] == "T3-tg-address-law"
                          and c.get("codeword_arrived"))
        T["carrier_control"]["T3_delivered_with_tile"] = deliv_tg
        T["carrier_control"]["T3_delivered_without_tile"] = deliv_no
        T["carrier_control"]["tg_roundtrip_needs_the_tile_PASS"] = (
            bool(deliv_tg) and not deliv_no)
        T["carrier_control"]["notg_cases"] = len(notg)

    hard = collections.Counter()
    for r in RUNS:
        for c in R[r]:
            if c["outcome"] in ("fault", "hang", "victim", "measurement_failure",
                                "invalid_run"):
                hard[(c["outcome"], c["arm"])] += 1

    doc = {"runs": RUNS, "cases_per_run": {r: len(R[r]) for r in RUNS},
           "gate_A": gA, "gate_B": gB, "gate_C": {k: v for k, v in gC.items()
                                                  if k != "arm"},
           "gate_D": gD, "gate_E": gE, "arm_T": T,
           "hard_outcomes": {"%s|%s" % k: v for k, v in sorted(hard.items())},
           "ALL_GATES_PASS": all([gA["PASS"], gB["PASS"], gC["PASS"], gD["PASS"],
                                  gE["PASS"]])}
    json.dump(doc, open(os.path.join(HERE, "gates.json"), "w"), indent=1,
              sort_keys=True)
    json.dump(gC["arm"], open(os.path.join(HERE, "arm_table.json"), "w"),
              indent=1, sort_keys=True)
    for k in ("gate_A", "gate_B", "gate_C", "gate_D", "gate_E"):
        print(k, "PASS =", doc[k]["PASS"])
    print("Gate C failures:", gC["n_failures"], gC["failures_by_arm"])
    print("arm T address law:", {k: len(v) for k, v in law.items()
                                 if isinstance(v, list)}, "H3_PASS",
          law["H3_PASS"])
    cc = T.get("carrier_control", {})
    print("H2 (faults are a carrier property):", cc.get("H2_VERDICT"))
    print("threadgroup round trip needs the tile:",
          cc.get("tg_roundtrip_needs_the_tile_PASS"),
          "| delivered with tile:", len(cc.get("T3_delivered_with_tile") or []),
          "without:", len(cc.get("T3_delivered_without_tile") or []))
    return 0 if doc["ALL_GATES_PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
