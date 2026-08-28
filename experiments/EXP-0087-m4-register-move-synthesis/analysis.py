#!/usr/bin/env python3
"""EXP-0087 post-capture analysis (deterministic; no clock, no device).

Reads the two closed raw runs, confirms they are byte-identical (verify.py
already gates this structurally; this script re-derives the same fact from
first principles for the report), and classifies every case against its
FROZEN pred{} from casematrix.py into one of:

  WORKS         the expected output slot took exactly the predicted value,
                and no other slot changed.
  NOOP_ZERO     the expected output slot changed to exactly 0.0 (a silent
                zero read), and no other slot changed.
  NOOP_UNCHANGED the whole 16-float output is byte-identical to the
                (in[K]==out[K]) baseline: the splice had no visible effect
                at all.
  CORRUPT       some slot OTHER than the one predicted also changed
                (cross-talk to an unrelated store).
  FAULT         STATUS was not OK (CMDBUF_ERROR / HANG / other).
  EXPLORE       the case's frozen prediction was "explore" or "unchanged";
                the observation is recorded but not scored pass/fail.
  MISMATCH      status OK, but the expected slot did not take the predicted
                value and none of the above categories apply (a genuine
                refutation of that case's frozen prediction).

Also folds in the compiler-emitted-move CENSUS captured in
raw/<run>/06_baseline.json (kernels/census.metal), unmodified.

CLI: python3 analysis.py --run-a RUN01 --run-b RUN02 --write
"""
import argparse, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import casematrix as CM   # noqa: E402


def load_run(rid):
    d = HERE / "raw" / rid
    results = [json.loads(l) for l in (d / "04_results.jsonl").read_text().splitlines()]
    baseline = json.loads((d / "06_baseline.json").read_text())
    return results, baseline


def classify(cs, line):
    """Score one case's observation against its FROZEN pred{} from
    casematrix.py. See module docstring for the verdict vocabulary."""
    if line["status"] != "OK":
        return "FAULT", {}
    diff = {int(k): v for k, v in (line["diff_from_baseline"] or {}).items()}
    pred = cs["pred"]
    if not isinstance(pred, dict) or not pred:
        return "EXPLORE", diff
    if any(v in ("explore", "unchanged") for v in pred.values()):
        return "EXPLORE", diff
    expected = {int(k[3:]): v for k, v in pred.items()
               if k.startswith("out") and k[3:].isdigit()}
    if not expected:
        return "EXPLORE", diff
    if not diff:
        return "NOOP_UNCHANGED", diff
    other = {k: v for k, v in diff.items() if k not in expected}
    matches = all(k in diff and abs(diff[k] - v) < 1e-6 for k, v in expected.items())
    if other:
        return "CORRUPT", diff
    if matches:
        return "WORKS", diff
    if all(diff.get(k) == 0.0 for k in expected):
        return "NOOP_ZERO", diff
    return "MISMATCH", diff


def build_report(run_a, run_b):
    res_a, base_a = load_run(run_a)
    res_b, base_b = load_run(run_b)
    identical = (json.dumps(res_a, sort_keys=True) == json.dumps(res_b, sort_keys=True))
    rows = []
    tally = {}
    for cs, line in zip(CM.CASES, res_a):
        assert cs["name"] == line["name"]
        verdict, diff = classify(cs, line)
        tally[verdict] = tally.get(verdict, 0) + 1
        rows.append({"name": cs["name"], "item": cs["item"], "probe": cs["probe"],
                     "dst": cs["dst"], "src": cs["src"], "byte2": "0x%02x" % cs["byte2"],
                     "op_desc": "0x%02x" % cs["op_desc"], "assembled_as": cs["assembled_as"],
                     "note": cs["note"], "pred": cs["pred"], "status": line["status"],
                     "diff_from_baseline": diff, "verdict": verdict})
    census = {fn: {"clean_tokenize": v["clean_tokenize"],
                   "n_instructions": len(v["instructions"]),
                   "reg_move_instances": [
                       {"offset": ins["offset"], "mnemonic": ins["mnemonic"],
                        "hex": ins["hex"], "fields": ins["fields"]}
                       for ins in v["instructions"]
                       if ins["mnemonic"] in ("uniform_mov", "reg_move_c0", "reg_move_c1",
                                              "reg_move_c9", "reg_move_cb", "reg_move_c2var")],
                   "leftover_hex": v["leftover_hex"]}
              for fn, v in base_a["census"].items()}
    census_cross_run_identical = (json.dumps(base_a["census"], sort_keys=True)
                                  == json.dumps(base_b["census"], sort_keys=True))
    return {"schema": 1, "run_a": run_a, "run_b": run_b,
            "results_byte_identical_across_runs": identical,
            "census_byte_identical_across_runs": census_cross_run_identical,
            "verdict_tally": dict(sorted(tally.items())), "cases": rows, "census": census}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", required=True)
    ap.add_argument("--run-b", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    report = build_report(a.run_a, a.run_b)
    txt = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if a.write:
        (HERE / "analysis.json").write_text(txt)
        print("WROTE analysis.json (%d cases, tally=%s)"
              % (len(report["cases"]), report["verdict_tally"]))
    else:
        sys.stdout.write(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
