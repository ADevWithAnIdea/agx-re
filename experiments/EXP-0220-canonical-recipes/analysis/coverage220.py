#!/usr/bin/env python3
"""EXP-0220 coverage report -- the OPERAND CLASSES a canonical recipe must cover.

Reads only committed raw.  Emits analysis/coverage.json and a printable table
with EXACT numerators and denominators per arm and per field
(RE_EXPERIMENT_PROCESS_CORRECTIONS section 5: "never report only a percentage").
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
RUNS = ["g17p-20260831-run01", "g17p-20260831-run02"]

# which arm exercises which instruction, for the per-instruction roll-up
ARM_INSTR = {
    "A1-operand-class": "falu2", "A2-dst": "falu2", "A3-srcA_reg": "falu2",
    "A4-srcB_reg": "falu2", "A5-opflags": "falu2", "A6-mod_hi": "falu2",
    "A7-ctrl": "falu2", "A8-operand-size": "falu2", "A9-reg_top": "falu2",
    "A10-inline-immediate": "falu2", "A11-opsel": "falu2",
    "A12-ieee-boundary": "falu2", "A13-operand-provenance": "falu2",
    "B1-st_format": "device_store", "B2-addr_mode-context": "device_store",
    "B3-extmode": "device_store", "B4-index_reg": "device_store",
    "B4H-index_reg-hazard": "device_store", "B5-idx_off": "device_store",
    "B6-base_slot": "device_store", "B7-space": "device_store",
    "B8-descriptor-tail": "device_store", "B9-index-lifetime": "device_store",
    "S0": "device_store", "CTL": "both",
}


def load(run):
    return [json.loads(l) for l in open(os.path.join(EXP, "raw", run, "sweep.jsonl"))
            if l.strip()]


def main():
    R = {r: load(r) for r in RUNS}
    base = R[RUNS[0]]

    # ---- per-arm table ----------------------------------------------------
    arms = collections.defaultdict(lambda: collections.Counter())
    for c in base:
        a = arms[c["arm"]]
        a["cases"] += 1
        a["pred_" + c["predicted_bucket"]] += 1
        a["obs_" + c["observed_bucket"]] += 1
        a["bucket_" + str(c.get("bucket_ok"))] += 1
        a["sem_checks"] += c.get("sem_checked", 0)
        a["distinct_programs"] = 0
    for a in arms:
        arms[a]["distinct_programs"] = len({c["prog_sha256"] for c in base
                                            if c["arm"] == a})

    # ---- per-field distinct ACTUAL encodings, from the byte ledger ---------
    # Gate A asks for "distinct actual encodings", not distinct requested values.
    fld = collections.defaultdict(lambda: {"requested": set(), "decoded": set(),
                                           "bytes": set(), "disagree": 0})
    for c in base:
        for u in c["under_test"]:
            m = u["mnemonic"]
            if m not in ("falu2", "device_store", "device_load", "mov_imm", "stop"):
                continue
            dec = u.get("decoded_actual") or {}
            for k, v in u["requested"].items():
                e = fld["%s.%s" % (m, k)]
                e["requested"].add(v)
                if k in dec:
                    e["decoded"].add(dec[k])
                    if dec[k] != v:
                        e["disagree"] += 1
                e["bytes"].add(u["bytes"])
    fields = {}
    for k, e in sorted(fld.items()):
        fields[k] = {"distinct_requested_values": len(e["requested"]),
                     "distinct_decoded_values": len(e["decoded"]),
                     "distinct_instruction_byte_strings": len(e["bytes"]),
                     "ledger_disagreements": e["disagree"],
                     "min_requested": min(e["requested"]) if e["requested"] else None,
                     "max_requested": max(e["requested"]) if e["requested"] else None}

    # ---- per-instruction roll-up -----------------------------------------
    roll = collections.defaultdict(lambda: collections.Counter())
    for c in base:
        ins = ARM_INSTR.get(c["arm"], "?")
        roll[ins]["cases"] += 1
        roll[ins]["bucket_" + str(c.get("bucket_ok"))] += 1
        roll[ins]["sem_checks"] += c.get("sem_checked", 0)

    doc = {"runs": RUNS,
           "arm_table": {k: dict(v) for k, v in sorted(arms.items())},
           "field_ledger": fields,
           "instruction_rollup": {k: dict(v) for k, v in sorted(roll.items())}}
    json.dump(doc, open(os.path.join(HERE, "coverage.json"), "w"),
              indent=1, sort_keys=True)

    print("%-26s %6s %6s %6s %6s %6s %9s" %
          ("arm", "cases", "gated", "pass", "fail", "meas", "semchecks"))
    for a, v in sorted(arms.items()):
        gated = v["cases"] - v.get("bucket_None", 0)
        print("%-26s %6d %6d %6d %6d %6d %9d" %
              (a, v["cases"], gated, v.get("bucket_True", 0),
               v.get("bucket_False", 0), v.get("bucket_None", 0), v["sem_checks"]))
    print()
    print("%-34s %8s %8s %8s %6s" % ("field", "req", "decoded", "bytes", "disag"))
    for k, v in sorted(fields.items()):
        print("%-34s %8d %8d %8d %6d" %
              (k, v["distinct_requested_values"], v["distinct_decoded_values"],
               v["distinct_instruction_byte_strings"], v["ledger_disagreements"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
