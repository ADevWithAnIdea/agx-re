#!/usr/bin/env python3
"""Deterministic derived analysis for EXP-0079.

Reads the frozen expected matrix from CAPTURE_CONTRACT.json (authored,
hash-bound at capture time) and the retained raw receipts. Emits byte-exact
analysis.json. No expected hardware values are embedded in this script; every
expectation comes from the pre-registered contract. Deviations between the
preregistered expectations and the observations are recorded verbatim as
results; they never fail this script. Several cases are pre-registered
HYPOTHESES-TO-FALSIFY (rule "c"): a "deviation" verdict on one of those is not
a defect, it is the falsification result the case exists to produce.
"""
import argparse, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
RUNS = ("m4-20260828-run01", "m4-20260828-run02")

def contract_cases():
    return json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())["cases"]

def payload(run, cid):
    z = json.loads((HERE / "raw" / run / f"case_{cid}.json").read_text())
    if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
        raise SystemExit("non-success case receipt " + cid + " in " + run)
    p = json.loads(z["stdout"])
    if p.get("case") != cid:
        raise SystemExit("payload identity " + cid)
    return p

def classify(p, c):
    obs_words = ["%08x" % w for w in p["read_words_le"]]
    rec = {"format": c["format"], "status": p["status"],
           "inputs": c["inputs"], "rule": c["rule"], "rule_note": c["rule_note"],
           "expected_texel_hex": c["expected_texel_hex"],
           "expected_read_words_le": c["expected_read_words_le"],
           "observed_texel_hex": p["physical_texel_hex"], "observed_read_words_le": obs_words,
           "backing_hex": p["backing_hex"], "result_hex": p["result_hex"]}
    if p["status"] != "ok":
        stage = {"store_pipeline_rejected": "store_pipeline", "read_pipeline_rejected": "read_pipeline",
                 "texture_rejected": "texture", "command_buffer_error": "command_buffer"}.get(p["status"], p["status"])
        rec["verdict"] = "api_rejected"
        rec["rejection_stage"] = stage
        rec["rejection_error"] = next((p[k] for k in ("store_pipeline_error", "read_pipeline_error",
                                                      "texture_error", "command_buffer_error") if p[k]), "")
        return rec
    texel_ok = p["physical_texel_hex"] == c["expected_texel_hex"]
    words_ok = obs_words == c["expected_read_words_le"]
    rec["verdict"] = "match" if (texel_ok and words_ok) else "deviation"
    if not texel_ok:
        rec["texel_deviation"] = {"expected": c["expected_texel_hex"], "observed": p["physical_texel_hex"]}
    if not words_ok:
        rec["words_deviation"] = {"expected": c["expected_read_words_le"], "observed": obs_words}
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
        print(json.dumps({"state": "PRE_GPU", "result": "NO_OBSERVATIONS",
                          "cases": [c["case"] for c in cs]}, sort_keys=True))
        return
    if not a.run_a or not a.run_b or a.run_a not in RUNS or a.run_b not in RUNS:
        raise SystemExit("two contracted run IDs required")
    out = {}
    for c in cs:
        pa, pb = payload(a.run_a, c["case"]), payload(a.run_b, c["case"])
        if pa != pb:
            raise SystemExit("repeat mismatch " + c["case"])
        out[c["case"]] = classify(pa, c)
    doc = {"runs": [a.run_a, a.run_b], "repeat_exact": True, "cases": out}
    if a.write:
        (HERE / "analysis.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(json.dumps(doc, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
