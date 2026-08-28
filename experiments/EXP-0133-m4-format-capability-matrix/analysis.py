#!/usr/bin/env python3
"""Derives analysis.json from raw/<run01>/raw/<run02>: the per-format capability
matrix, conversion-case verdicts, layout results, sparse results, and a
run01-vs-run02 byte-exact repeat check (excluding started_utc, the only
nondeterministic field any record carries)."""
import argparse, importlib.util, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
RUNS = ("m4-20260828-run07", "m4-20260828-run08")

def load_runner():
    spec = importlib.util.spec_from_file_location("exp0133_runner", HERE / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def load_case(rid, cid):
    return json.loads((HERE / "raw" / rid / "cases" / (cid + ".json")).read_text())

def status_of(z):
    if z["exit"] == 0 and not z["timed_out"] and z["exception"] is None:
        try:
            p = json.loads(z["stdout"])
        except ValueError:
            return "unparseable_stdout", None
        return "ok", p
    return "process_%s" % (("timeout" if z["timed_out"] else (z["exception"] or ("exit_%s" % z["exit"]))),), None

def axis_status(payload_or_none, kind_status):
    if kind_status != "ok":
        return kind_status
    axes = payload_or_none.get("axes", {})
    only = next(iter(axes.values()), {})
    return only.get("status", "missing")

def build():
    mod = load_runner()
    contract = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    cases = mod.build_cases(contract)

    matrix = {}  # format name -> axis -> status string
    for f in contract["formats"]:
        matrix[f["name"]] = {"id": f["id"], "kind": f["kind"], "family": f["family"], "axes": {}}
    for c in cases:
        if c["kind"] != "capability":
            continue
        z = load_case(RUNS[0], c["id"])
        kstatus, payload = status_of(z)
        name = [c["argv_tail"][i + 1] for i, x in enumerate(c["argv_tail"]) if x == "--name"][0]
        axis = c["argv_tail"][-1]
        matrix[name]["axes"][axis] = axis_status(payload, kstatus)
        matrix[name]["axes_expect_may_abort"] = matrix[name].get("axes_expect_may_abort", {})
        matrix[name]["axes_expect_may_abort"][axis] = c["expect_may_abort"]

    conversion = {}
    for c in cases:
        if c["kind"] != "conversion":
            continue
        z = load_case(RUNS[0], c["id"])
        kstatus, payload = status_of(z)
        conversion[c["id"]] = {"harness_status": kstatus, "payload": payload}

    layout = {}
    for c in cases:
        if c["kind"] not in ("layout", "layout_below_min"):
            continue
        z = load_case(RUNS[0], c["id"])
        kstatus, payload = status_of(z)
        layout[c["id"]] = {"harness_status": kstatus, "payload": payload}

    sparse = {}
    for c in cases:
        if c["kind"] != "sparse":
            continue
        z = load_case(RUNS[0], c["id"])
        kstatus, payload = status_of(z)
        sparse[c["id"]] = {"harness_status": kstatus, "payload": payload}

    # repeat check across runs (excludes started_utc; everything else compared byte-exact)
    mismatches = []
    for c in cases:
        z0 = load_case(RUNS[0], c["id"])
        z1 = load_case(RUNS[1], c["id"])
        for k in ("argv", "cwd", "timeout_seconds", "timed_out", "exit", "stdout", "stderr", "exception"):
            if z0[k] != z1[k]:
                mismatches.append({"case": c["id"], "field": k})
    repeat_exact = len(mismatches) == 0

    # crash / negative-result census
    census = {"total_cases": len(cases), "ok": 0, "expected_abort_and_aborted": 0,
              "expected_abort_but_ok": 0, "unexpected_nonzero": 0}
    for c in cases:
        z = load_case(RUNS[0], c["id"])
        ok = z["exit"] == 0 and not z["timed_out"] and z["exception"] is None
        if ok:
            census["ok"] += 1
            if c["expect_may_abort"]:
                census["expected_abort_but_ok"] += 1
        else:
            if c["expect_may_abort"]:
                census["expected_abort_and_aborted"] += 1
            else:
                census["unexpected_nonzero"] += 1

    return {"schema": 1, "runs": list(RUNS), "repeat_exact": repeat_exact,
            "mismatch_count": len(mismatches), "mismatches_sample": mismatches[:20],
            "case_census": census, "capability_matrix": matrix,
            "conversion": conversion, "layout": layout, "sparse": sparse}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    out = build()
    if a.write:
        (HERE / "analysis.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
        print("wrote analysis.json: repeat_exact=%s mismatches=%d census=%s" %
              (out["repeat_exact"], out["mismatch_count"], out["case_census"]))
    else:
        print(json.dumps(out, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
