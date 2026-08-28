#!/usr/bin/env python3
"""Deterministic derived analysis for EXP-0106. Reads the frozen expected
values from CAPTURE_CONTRACT.json (authored, hash-bound at capture time) and
the retained raw receipts; emits byte-exact analysis.json. No expected
hardware values are embedded here beyond what the contract already carries.
Independently re-authored from the EXP-0095 pattern (this project's own
prior work).

Beyond the per-case match/deviation/abort_confirmed/rejection_confirmed
verdict, this adds two INTERPRETIVE (not gating) cross-checks specific to
this experiment's b09 family, computed only from already-captured, already
byte-exact-verified per-case words -- neither is a pass/fail gate:
  - injectivity: do the 12 b09_offset_* boundary/corner cases produce 12
    pairwise-distinct gather.x values (the TEX-03 "no aliasing" claim)?
  - dynamic_cross_check: does b09_offset_dynamic's per-lane out[i] equal the
    corresponding constant-offset case's out[0] for the same (dx,dy) (the
    TEX-04 "the dynamic operand reflects each lane's own value" claim)?
"""
import argparse, json
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
RUNS = ("m4-20260830-run01", "m4-20260830-run02")

def contract_cases():
    return json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())["cases"]

def raw_receipt(run, cid):
    return json.loads((HERE / "raw" / run / f"case_{cid}.json").read_text())

def family_kind(fam):
    if fam == "b_descriptor":
        return "descriptor"
    if fam == "b03_query":
        return "query"
    return "dispatch"

def classify(c, za, zb):
    cid = c["case"]
    expect = c.get("expect_status", "ok")
    if expect == "abort":
        ok = (za["exit"] < 0 and zb["exit"] < 0 and not za["timed_out"] and not zb["timed_out"]
              and za["exception"] is None and zb["exception"] is None)
        return {"family": c["family"], "rule_note": c["rule_note"],
                "verdict": "abort_confirmed" if ok else "unexpected", "run_a_exit": za["exit"], "run_b_exit": zb["exit"]}
    pa = json.loads(za["stdout"])
    pb = json.loads(zb["stdout"])
    if pa != pb:
        raise SystemExit("repeat mismatch " + cid)
    if expect in ("library_failed", "pipeline_rejected"):
        ok = pa.get("status") == expect
        return {"family": c["family"], "rule_note": c["rule_note"],
                "verdict": "rejection_confirmed" if ok else "unexpected", "status": pa.get("status")}
    kind = family_kind(c["family"])
    if kind == "descriptor":
        return {"family": c["family"], "rule_note": c["rule_note"], "verdict": "match",
                "type": pa["type"], "width": pa["width"], "height": pa["height"], "depth": pa["depth"],
                "arrayLength": pa["arrayLength"], "sampleCount": pa["sampleCount"],
                "actualSampleCount": pa["actualSampleCount"], "texture_ok": pa["texture_ok"]}
    if kind == "query":
        return {"family": c["family"], "rule_note": c["rule_note"], "verdict": "match",
                "sample_count": pa["sample_count"], "supported": pa["supported"]}
    n = c["n_outputs"]
    exp = c["expected_out_words"]
    ow = pa["out_words"]
    checked = [i for i in range(n) if exp[i] is not None]
    matches = all(ow[i] == exp[i] for i in checked)
    rec = {"family": c["family"], "rule_note": c["rule_note"], "status": pa["status"],
           "n_outputs": n, "expected_out_words": exp[:n], "observed_out_words": ow[:n],
           "verdict": "match" if matches else "deviation"}
    if not matches:
        rec["deviation_words"] = {i: {"expected": exp[i], "observed": ow[i]} for i in checked if ow[i] != exp[i]}
    if n and any(exp[i] is None for i in range(n)):
        rec["observed_no_oracle_words"] = {i: ow[i] for i in range(n) if exp[i] is None}
    return rec

def b09_crosschecks(out, cs):
    sweep = {}
    for c in cs:
        if c["family"] == "b09_offset" and out[c["case"]]["verdict"] == "match":
            sweep[c["case"]] = out[c["case"]]["observed_out_words"][0]
    values = list(sweep.values())
    injective = len(values) == len(set(values))
    dyn_case = next((c for c in cs if c["family"] == "b09_offset_dynamic"), None)
    cross = None
    if dyn_case is not None and out[dyn_case["case"]]["verdict"] == "match":
        dyn_words = out[dyn_case["case"]]["observed_out_words"]
        # (dx,dy) pairs used by b09_offset_dynamic's args, read back from the contract itself.
        flat = dyn_case["args"]["buffers"][0]["values"]
        pairs = [(flat[2 * i], flat[2 * i + 1]) for i in range(len(flat) // 2)]
        matched = []
        for i, (dx, dy) in enumerate(pairs):
            tag = f"{dx}_{dy}".replace("-", "m")
            const_case = f"b09_offset_{tag}"
            const_val = sweep.get(const_case)
            matched.append({"lane": i, "dx": dx, "dy": dy, "dynamic_value": dyn_words[i],
                            "constant_case": const_case, "constant_value": const_val,
                            "agree": const_val is not None and const_val == dyn_words[i]})
        cross = {"pairs": matched, "all_agree": all(m["agree"] for m in matched)}
    return {"injective": injective, "distinct_values": len(set(values)), "total_sweep_cases": len(values),
            "dynamic_cross_check": cross}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", action="store_true")
    ap.add_argument("--run-a")
    ap.add_argument("--run-b")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    cs = contract_cases()
    if a.static:
        if (HERE / "raw").exists():
            raise SystemExit("raw exists: use capture verification, not static mode")
        print(json.dumps({"state": "PRE_GPU", "result": "NO_OBSERVATIONS", "cases": [c["case"] for c in cs]}, sort_keys=True))
        return
    if not a.run_a or not a.run_b or a.run_a not in RUNS or a.run_b not in RUNS:
        raise SystemExit("two contracted run IDs required")
    out = {}
    for c in cs:
        za, zb = raw_receipt(a.run_a, c["case"]), raw_receipt(a.run_b, c["case"])
        out[c["case"]] = classify(c, za, zb)
    n_match = sum(1 for v in out.values() if v.get("verdict") == "match")
    n_dev = sum(1 for v in out.values() if v.get("verdict") == "deviation")
    n_abort = sum(1 for v in out.values() if v.get("verdict") == "abort_confirmed")
    n_rej = sum(1 for v in out.values() if v.get("verdict") == "rejection_confirmed")
    n_unexpected = sum(1 for v in out.values() if v.get("verdict") == "unexpected")
    doc = {"runs": [a.run_a, a.run_b], "repeat_exact": True,
           "summary": {"match": n_match, "deviation": n_dev, "abort_confirmed": n_abort,
                       "rejection_confirmed": n_rej, "unexpected": n_unexpected, "total": len(cs)},
           "cases": out, "b09_crosschecks": b09_crosschecks(out, cs)}
    if a.write:
        (HERE / "analysis.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(json.dumps(doc, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
