#!/usr/bin/env python3
"""verdicts.py -- EXP-0163: two gated runs -> analysis/field_verdicts.json.

    python3 analysis/verdicts.py --runs raw/g17p_.../sweep.jsonl [...]

Reduces the append-only sweep records to one verdict per target field, in the
three PRE-REGISTERED buckets (PRE_REGISTRATION sec.9):

  LIVE                -- some arm with strict detection power shows >=1 value
                         that moved the observation, in EVERY run, on the SAME
                         arm.
  INERT-ROBUST        -- inert over the full dense range on >=3 structurally
                         different carriers that EACH passed the strict
                         detection profile, in every run.
  STILL-UNDERPOWERED  -- anything else: too few arms with proven detection
                         power, an incomplete sweep, or cross-run disagreement.

The strict-detection-power gate is the whole point: an arm that cannot be shown
to move its own observation contributes NOTHING to an inert verdict.  Arms
without it are reported, with their sweeps, under `underpowered_arms`.

Output schema follows FIELD-SWEEP-PROTOCOL sec.5 (flat dict keyed
"<mnemonic>.<field>", each value carrying label / target / evidence / range /
note) with the EXP-0163 additions the dispatch asked for: the bucket, the arm
and carrier that carried the verdict, and per-run agreement.

CLEAN-ROOM: analysis of our own captured observations only.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
import carriers as CA      # noqa: E402
import arms as AR          # noqa: E402

MOVED = {"wrong_value", "silent_zero"}
# Outcomes that are NOT evidence about the field value itself.
NOT_FIELD_EVIDENCE = {"foreign", "unreproduced", "not_run"}


def load(path):
    """-> (run_name, per-arm detection summary, per (arm,field) case table).

    DETECTION POWER IS RECOMPUTED HERE FROM THE RAW RECORDS, not taken from the
    run manifest.  run.py's in-run `changed` predicate treats a FAULTED control
    as "moved" (its test is `not same_obs`, and same_obs requires both statuses
    OK).  A fault is an effect, but it is not a demonstration that the arm can
    OBSERVE a value difference, which is the thing an inert verdict depends on.
    So the gate used here is strictly:

        status == OK  AND  the observation changed  AND  the patched bytes
        still decode as the arm's own mnemonic

    and `detect_via_fault_only` records arms whose only moving control faulted.
    (This was found by comparing the pre-freeze smoke with run01: their single
    disagreement in 962 shared cases was `tex_write.amode = 0xab`, which the
    smoke scored `moved` purely because that command buffer returned
    kIOGPUCommandBufferCallbackErrorHang.)
    """
    run = os.path.basename(os.path.dirname(path))
    detect, cases = {}, collections.defaultdict(dict)
    base_final = {}
    strict = collections.defaultdict(list)
    faulty = collections.defaultdict(list)
    seen_arms = set()
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        arm, f = d["carrier"], d["field"]
        if f == "_detect_summary":
            detect[arm] = json.loads(d["note"])
            seen_arms.add(arm)
        elif f == "_detect":
            if d["outcome"] != "moved":
                continue
            fn = d["note"].split(":")[1].split("=")[0].strip()
            tag = f"{fn}={d['value']:#x}"
            same_mnem = d["note"].rstrip().endswith("redecodes_as=" + d["instr"])
            if d["observed"].get("status") == "OK" and same_mnem:
                strict[arm].append(tag)
            else:
                faulty[arm].append(tag + "/" + (d["observed"].get("os_class") or "decode"))
        elif f == "_baseline_final":
            base_final[arm] = bool(d["match"])
        elif not f.startswith("_"):
            cases[(arm, f)][d["value"]] = d["outcome"]
    for arm in seen_arms:
        detect.setdefault(arm, {})
        detect[arm]["detect_ok_strict"] = bool(strict.get(arm))
        detect[arm]["strict_live_controls"] = strict.get(arm, [])[:24]
        detect[arm]["fault_only_controls"] = faulty.get(arm, [])[:24]
    return run, detect, cases, base_final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("-o", default=os.path.join(HERE, "field_verdicts.json"))
    args = ap.parse_args()

    runs = [load(p) for p in args.runs]
    names = [r[0] for r in runs]
    armspec = {a["id"]: a for a in AR.ARMS}

    out = {}
    per_arm_report = {}
    for mnem, fields in sorted(CA.TARGETS.items()):
        for fname in fields:
            key = f"{mnem}.{fname}"
            arms = [a for a in AR.ARMS if a["mnemonic"] == mnem and fname in a["fields"]]
            rec = {"arms": {}, "runs": names}
            live_arms, inert_arms, weak_arms = [], [], []
            for a in arms:
                aid = a["id"]
                per_run = {}
                power = {}
                for (rn, detect, cases, bf) in runs:
                    tab = cases.get((aid, fname), {})
                    mv = sorted(v for v, o in tab.items() if o in MOVED)
                    bad = sorted(v for v, o in tab.items()
                                 if o in ("fault", "hang", "undecodable"))
                    skip = sorted(v for v, o in tab.items() if o in NOT_FIELD_EVIDENCE)
                    per_run[rn] = {"n": len(tab), "moved": len(mv),
                                   "moved_values": mv[:64], "n_faults": len(bad),
                                   "fault_values": bad[:32],
                                   "n_not_evidence": len(skip),
                                   "baseline_final_ok": bf.get(aid)}
                    power[rn] = bool(detect.get(aid, {}).get("detect_ok_strict"))
                rec["arms"][aid] = {
                    "carrier": a["carrier"], "stage": a["stage"], "occ": a["occ"],
                    "located_via": "tokenize" if a["tokenized"] else "scan-or-prefix",
                    "baseline_field_value": a["census_fields"].get(fname),
                    "detect_ok": power, "per_run": per_run,
                    "why_this_carrier": a["why"][:400],
                }
                all_power = all(power.values())
                moved_all = all(per_run[r]["moved"] > 0 for r in names)
                swept_all = all(per_run[r]["n"] > 0 for r in names)
                if not swept_all:
                    weak_arms.append(aid)
                elif not all_power:
                    weak_arms.append(aid)
                elif moved_all:
                    live_arms.append(aid)
                elif all(per_run[r]["moved"] == 0 for r in names):
                    inert_arms.append(aid)
                else:
                    weak_arms.append(aid)      # cross-run disagreement
            distinct_inert_carriers = sorted({armspec[a]["carrier"] for a in inert_arms})
            if live_arms:
                bucket = "LIVE"
            elif len(distinct_inert_carriers) >= 3:
                bucket = "INERT-ROBUST"
            else:
                bucket = "STILL-UNDERPOWERED"
            rec.update(bucket=bucket, live_arms=live_arms, inert_arms=inert_arms,
                       underpowered_arms=weak_arms,
                       inert_carriers=distinct_inert_carriers)
            out[key] = rec
    # Per-arm detection-power report, so a reviewer can audit the gate.
    for (rn, detect, cases, bf) in runs:
        for aid, s in detect.items():
            per_arm_report.setdefault(aid, {})[rn] = {
                "detect_ok_strict": s.get("detect_ok_strict"),
                "strict_live_controls": s.get("strict_live_controls", []),
                "fault_only_controls": s.get("fault_only_controls", []),
                "in_run_detect_ok": s.get("detect_ok"),
                "profile_steps": s.get("profile_steps"),
            }

    doc = {"experiment": "EXP-0163", "target": "G17P (Apple A18 Pro, applegpu_g17p)",
           "runs": names, "fields": out, "detection_power": per_arm_report}
    with open(args.o, "w") as f:
        json.dump(doc, f, indent=1, sort_keys=True)

    print(f"{'field':30s} {'bucket':20s} live_arms / inert_carriers")
    for k, v in sorted(out.items()):
        print("%-30s %-20s %s / %s" % (
            k, v["bucket"],
            ",".join(c.split("@")[1] for c in v["live_arms"][:4]) or "-",
            ",".join(v["inert_carriers"]) or "-"))
    print("\nwrote", args.o)


if __name__ == "__main__":
    main()
