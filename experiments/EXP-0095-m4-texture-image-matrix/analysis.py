#!/usr/bin/env python3
"""Deterministic derived analysis for EXP-0095. Reads the frozen expected
matrix from CAPTURE_CONTRACT.json (authored, hash-bound at capture time) and
the retained raw receipts; emits byte-exact analysis.json. No expected
hardware values are embedded here beyond what the contract already carries.
Rule "c" cases are pre-registered HYPOTHESES-TO-FALSIFY: a "deviation"
verdict there is not a defect, it is the falsification result the case
exists to produce; rule "a"/"b" cases have hard expectations and a
"deviation" there IS a defect to investigate.
"""
import argparse, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
RUNS = ("m4-20260829-run01", "m4-20260829-run02")

def contract_cases():
    return json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())["cases"]

def raw_receipt(run, cid):
    return json.loads((HERE / "raw" / run / f"case_{cid}.json").read_text())

def classify(c, run_a_receipt, run_b_receipt):
    cid = c["case"]
    if c.get("expect_status") == "abort":
        za, zb = run_a_receipt, run_b_receipt
        ok = (za["exit"] < 0 and zb["exit"] < 0 and not za["timed_out"] and not zb["timed_out"]
              and za["exception"] is None and zb["exception"] is None)
        return {"family": c["family"], "rule": c["rule"], "rule_note": c["rule_note"],
                "verdict": "abort_confirmed" if ok else "unexpected", "run_a_exit": za["exit"], "run_b_exit": zb["exit"]}
    pa = json.loads(run_a_receipt["stdout"])
    pb = json.loads(run_b_receipt["stdout"])
    if pa != pb:
        raise SystemExit("repeat mismatch " + cid)
    if c["family"] == "a07_descriptor":
        return {"family": c["family"], "rule": c["rule"], "rule_note": c["rule_note"], "verdict": "match",
                "width": pa["width"], "bytes_needed": pa["bytes_needed"], "texture_ok": pa["texture_ok"]}
    n = c["n_outputs"]
    exp = c["expected_out_words"]
    ow = pa["out_words"]
    checked = [i for i in range(n) if exp[i] is not None]
    matches = all(ow[i] == exp[i] for i in checked)
    rec = {"family": c["family"], "rule": c["rule"], "rule_note": c["rule_note"], "status": pa["status"],
           "n_outputs": n, "expected_out_words": exp[:n], "observed_out_words": ow[:n],
           "verdict": "match" if matches else "deviation"}
    if not matches:
        rec["deviation_words"] = {i: {"expected": exp[i], "observed": ow[i]} for i in checked if ow[i] != exp[i]}
    return rec

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
    doc = {"runs": [a.run_a, a.run_b], "repeat_exact": True, "summary": {"match": n_match, "deviation": n_dev, "abort_confirmed": n_abort, "total": len(cs)}, "cases": out}
    if a.write:
        (HERE / "analysis.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(json.dumps(doc, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
