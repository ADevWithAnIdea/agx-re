#!/usr/bin/env python3
"""EXP-0092 analysis: reads raw/<run>/04_results.jsonl for both closed runs,
cross-checks byte-identity (defense in depth; verify.py --captured is
authoritative), and classifies every srsweep SR-selector result into one of:
  KNOWN_MATCH          -- matches the independently pre-registered pattern for
                           a characterized SR (casematrix.KNOWN_SR).
  ALIASES_KNOWN_SR      -- an UNCHARACTERIZED sr_sel produced the exact pattern
                           of a DIFFERENT known SR (candidate alias/mirror).
  ALL_ZERO               -- constant zero raw value at every thread (i.e. every
                           observed out[] element equals the +1000 offset).
  CONSTANT_NONZERO       -- a single nonzero constant across all 64 threads.
  STRUCTURED_UNCLASSIFIED-- varies across threads but matches no known pattern.
  FAULT                  -- STATUS != OK (dispatch itself failed).
This file performs NO GPU operation; it is pure post-processing of already
closed raw/ evidence.
"""
import argparse, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import casematrix as CM  # noqa: E402
import run as R           # noqa: E402


def load_run(rid):
    lines = (HERE / "raw" / rid / "04_results.jsonl").read_text().splitlines()
    return [json.loads(l) for l in lines]


def classify_srsweep(sr, observed, status):
    if status != "OK":
        return "FAULT"
    if observed is None:
        return "FAULT"
    offset = CM.SRSWEEP_OFFSET
    raw = [v - offset for v in observed]
    if sr in CM.KNOWN_SR and raw == CM.KNOWN_SR[sr]:
        return "KNOWN_MATCH"
    for other_sr, pat in CM.KNOWN_SR.items():
        if other_sr != sr and raw == pat:
            return "ALIASES_KNOWN_SR:0x%02x" % other_sr
    if all(v == raw[0] for v in raw):
        return "ALL_ZERO" if raw[0] == 0 else "CONSTANT_NONZERO:%d" % raw[0]
    return "STRUCTURED_UNCLASSIFIED"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "analysis.json"))
    a = ap.parse_args()

    runs = {}
    for rid in R.RUNS:
        p = HERE / "raw" / rid
        if not p.exists():
            raise SystemExit("raw/%s missing -- run both captures before analysis" % rid)
        runs[rid] = load_run(rid)

    r1, r2 = runs[R.RUNS[0]], runs[R.RUNS[1]]
    cross_run_identical = (json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True))

    # Use run01 as the analysis source (byte-identical to run02 per the gate).
    by_backend = {"srsweep": [], "dstsweep": [], "drawparam": [], "numworkgroups": []}
    for line in r1:
        by_backend[line["backend"]].append(line)

    # --- srsweep classification -------------------------------------------
    sr_classes = {}
    class_counts = {}
    for line in by_backend["srsweep"]:
        sr = line["params"]["sr_sel"]
        cls = classify_srsweep(sr, line["observed"], line["status"])
        sr_classes["0x%02x" % sr] = cls
        base_cls = cls.split(":")[0]
        class_counts[base_cls] = class_counts.get(base_cls, 0) + 1
    first_invalid_sr = None
    for line in sorted(by_backend["srsweep"], key=lambda l: l["params"]["sr_sel"]):
        if line["status"] != "OK":
            first_invalid_sr = line["params"]["sr_sel"]
            break
    known_matches = sorted(int(k, 16) for k, v in sr_classes.items() if v == "KNOWN_MATCH")
    alias_hits = {k: v for k, v in sr_classes.items() if v.startswith("ALIASES_KNOWN_SR")}
    all_zero = sorted(int(k, 16) for k, v in sr_classes.items() if v == "ALL_ZERO")
    constant_nonzero = {k: v for k, v in sr_classes.items() if v.startswith("CONSTANT_NONZERO")}
    structured_unclassified = sorted(int(k, 16) for k, v in sr_classes.items()
                                     if v == "STRUCTURED_UNCLASSIFIED")
    faulted = sorted(int(k, 16) for k, v in sr_classes.items() if v == "FAULT")

    # --- dstsweep --------------------------------------------------------
    dst_results = []
    for line in sorted(by_backend["dstsweep"], key=lambda l: l["params"]["reg"]):
        dst_results.append({"reg": line["params"]["reg"], "status": line["status"],
                            "verdict": line["verdict"]})
    first_invalid_reg = next((d["reg"] for d in dst_results if d["verdict"] != "MATCH_EXPECTED"),
                             None)

    # --- drawparam ---------------------------------------------------------
    drawparam_results = [{"case": l["case_name"], "status": l["status"], "verdict": l["verdict"]}
                         for l in by_backend["drawparam"]]

    # --- numworkgroups -------------------------------------------------------
    numwg_results = [{"case": l["case_name"], "status": l["status"], "verdict": l["verdict"],
                      "observed": l["observed"], "expected": l["expected"]}
                     for l in by_backend["numworkgroups"]]

    out = {
        "schema": 1, "cross_run_byte_identical": cross_run_identical,
        "srsweep": {
            "total": len(by_backend["srsweep"]),
            "first_invalid_sr_by_status": first_invalid_sr,
            "class_counts": class_counts,
            "known_match_count": len(known_matches),
            "known_match_sr": ["0x%02x" % s for s in known_matches],
            "alias_hits": alias_hits,
            "all_zero_sr": ["0x%02x" % s for s in all_zero],
            "constant_nonzero_sr": constant_nonzero,
            "structured_unclassified_sr": ["0x%02x" % s for s in structured_unclassified],
            "faulted_sr": ["0x%02x" % s for s in faulted],
            "per_sr_classification": sr_classes,
        },
        "dstsweep": {
            "total": len(dst_results), "first_invalid_reg": first_invalid_reg,
            "per_reg": dst_results,
        },
        "drawparam": {"total": len(drawparam_results), "results": drawparam_results,
                     "all_match": all(r["verdict"] == "MATCH_EXPECTED" for r in drawparam_results)},
        "numworkgroups": {"total": len(numwg_results), "results": numwg_results},
    }
    Path(a.out).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print("wrote %s (cross_run_byte_identical=%s)" % (a.out, cross_run_identical))


if __name__ == "__main__":
    main()
