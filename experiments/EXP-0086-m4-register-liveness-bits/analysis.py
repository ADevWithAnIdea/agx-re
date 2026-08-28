#!/usr/bin/env python3
"""EXP-0086 analysis: cross-run comparison + per-case verdict summary +
determinism (intermittency) assessment across the REPEAT_N in-run repeats.
Deterministic (no clock calls); reads only committed raw/ JSONL.
"""
import argparse, json, sys
from pathlib import Path
from collections import defaultdict

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import casematrix as CM  # noqa: E402


def load(run_id):
    p = HERE / "raw" / run_id / "04_results.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()]


def anchor_meta():
    meta = {}
    for kernel in CM.KERNELS:
        anc = CM.ANCHORS[kernel]
        meta[kernel] = {"c2_out_idx": anc["c2_out_idx"], "v_low6": anc["v_low6"]}
    return meta


def summarize(run_id):
    lines = load(run_id)
    by_case = defaultdict(list)
    for ln in lines:
        key = (ln["kernel"], ln["case_name"])
        by_case[key].append(ln)
    meta = anchor_meta()
    rows = []
    for (kernel, case_name), reps in sorted(by_case.items()):
        reps_sorted = sorted(reps, key=lambda x: x["rep"])
        verdicts = [r["verdict"] for r in reps_sorted]
        statuses = [r["status"] for r in reps_sorted]
        target_idx = meta[kernel]["c2_out_idx"]
        target_hit = [target_idx in (r["mismatch_indices"] or []) for r in reps_sorted]
        other_hit = [bool(set(r["mismatch_indices"] or []) - {target_idx}) for r in reps_sorted]
        deterministic = len(set(verdicts)) == 1
        item = reps_sorted[0]["item"]
        rows.append({
            "kernel": kernel, "case_name": case_name, "item": item,
            "n_reps": len(reps_sorted), "verdicts": verdicts, "statuses": statuses,
            "deterministic": deterministic,
            "target_out_idx": target_idx,
            "target_mismatch_any": any(target_hit),
            "target_mismatch_all": all(target_hit) if verdicts else False,
            "other_index_mismatch_any": any(other_hit),
            "out_values_rep0": reps_sorted[0]["out_values"],
            "expected_values": reps_sorted[0]["expected_values"],
        })
    return rows


def cross_run_check(run_a, run_b):
    a = load(run_a)
    b = load(run_b)
    ta = {(l["kernel"], l["case_name"], l["rep"]): l for l in a}
    tb = {(l["kernel"], l["case_name"], l["rep"]): l for l in b}
    same_keys = set(ta) == set(tb)
    diffs = []
    if same_keys:
        for k in ta:
            la, lb = dict(ta[k]), dict(tb[k])
            if la != lb:
                diffs.append({"key": list(k), "run_a": la, "run_b": lb})
    return {"same_keys": same_keys, "n_diffs": len(diffs), "diffs": diffs[:20]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", default="m4-20260828-run01")
    ap.add_argument("--run-b", default="m4-20260828-run02")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    rows_a = summarize(a.run_a)
    rows_b = summarize(a.run_b)
    cross = cross_run_check(a.run_a, a.run_b)

    corrupting = [r for r in rows_a if r["item"] in ("CAND_A", "CAND_B")
                  and r["target_mismatch_any"]]
    intermittent = [r for r in rows_a if not r["deterministic"]]
    control_flagged = [r for r in rows_a if r["item"] == "CONTROL"
                       and r["case_name"].startswith("inert_control")
                       and r["target_mismatch_any"]]
    positive_control_ok = [r for r in rows_a if r["case_name"] == "positive_control_c2"
                           and r["target_mismatch_any"]]
    positive_control_all = [r for r in rows_a if r["case_name"] == "positive_control_c2"]

    report = {
        "schema": 1,
        "run_a": a.run_a, "run_b": a.run_b,
        "cross_run": cross,
        "n_case_groups": len(rows_a),
        "rows_run_a": rows_a,
        "corrupting_cases": [{"kernel": r["kernel"], "case_name": r["case_name"],
                              "verdicts": r["verdicts"]} for r in corrupting],
        "intermittent_cases": [{"kernel": r["kernel"], "case_name": r["case_name"],
                                "verdicts": r["verdicts"]} for r in intermittent],
        "inert_control_flagged": [{"kernel": r["kernel"], "case_name": r["case_name"]}
                                  for r in control_flagged],
        "positive_control_detected_n": len(positive_control_ok),
        "positive_control_total_n": len(positive_control_all),
    }
    out_path = HERE / "analysis.json"
    if a.write:
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print("WROTE analysis.json")
    print(json.dumps({
        "cross_run_same_keys": cross["same_keys"], "cross_run_n_diffs": cross["n_diffs"],
        "n_corrupting_cases": len(corrupting), "n_intermittent_cases": len(intermittent),
        "n_inert_control_flagged": len(control_flagged),
        "positive_control": "%d/%d" % (len(positive_control_ok), len(positive_control_all)),
    }, indent=2))
    if a.write and (not cross["same_keys"] or cross["n_diffs"] > 0):
        print("ANALYSIS GATE: FAIL (cross-run mismatch -- see analysis.json)")
        sys.exit(1)


if __name__ == "__main__":
    main()
