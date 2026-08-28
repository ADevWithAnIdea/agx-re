#!/usr/bin/env python3
"""EXP-0096 deterministic analysis: decode both capture runs, compare them
byte-exactly, and classify every case against its frozen family. No clock, no
randomness, no network: identical inputs produce byte-identical output.

Only 04_results.jsonl / 06_budget_results.jsonl (the semantic payloads) are
read; the two *_timing.jsonl files are never opened here (see PRE_REGISTRATION.md
timing-isolation section).
"""
import argparse, hashlib, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import casematrix as CM   # noqa: E402
import baseline as BL     # noqa: E402

RUNS = ("m4-20260828-run01", "m4-20260828-run02")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_run(rid):
    d = HERE / "raw" / rid
    lines = [json.loads(l) for l in (d / "04_results.jsonl").read_text().splitlines()]
    blines = [json.loads(l) for l in (d / "06_budget_results.jsonl").read_text().splitlines()]
    disp = json.loads((d / "03_dispatch.json").read_text())
    return {"rid": rid, "lines": lines, "blines": blines, "dispatch": disp,
            "results_sha256": sha(d / "04_results.jsonl"),
            "budget_results_sha256": sha(d / "06_budget_results.jsonl")}


def classify_splice(line, cs):
    row = {"name": cs["name"], "item": cs["item"], "kernel": cs["kernel"],
           "status": line["status"], "fields": cs["fields"],
           "fault": line["status"] in ("CMDBUF_ERROR", "HANG"),
           "timed_out": line["timed_out"]}
    dec = line["decoded"]
    if cs["kernel"] == "tga":
        row["matches_baseline"] = dec.get("matches_baseline") if dec else None
        row["matches_known_ip2_corruption"] = dec.get("matches_known_ip2_corruption") if dec else None
        row["num_diff_from_baseline"] = dec.get("num_diff_from_baseline") if dec else None
        row["first_diff_index"] = dec.get("first_diff_index") if dec else None
        row["observed_sha256"] = dec.get("observed_sha256") if dec else None
        row["decodable"] = bool(dec and dec.get("decodable"))
    elif cs["kernel"] == "tg_ld":
        row["byte_offset"] = dec["byte_offset"] if dec else None
        row["word"] = dec["word"] if dec else None
        row["undecodable"] = (dec is None and line["status"] == "OK")
        pred = cs["pred"].get("H-ELEM+H-U")
        row["matches_pred"] = (row["byte_offset"] == pred) if (dec and pred is not None) else None
    else:  # tg_st
        row["store_byte_offset"] = dec["byte_offset"] if dec else None
        row["store_words_changed"] = len(dec["words_changed"]) if dec else None
        pred = cs["pred"].get("H-ELEM+H-U")
        row["matches_pred"] = (row["store_byte_offset"] == pred) if (dec and pred is not None) else None
    return row


def tga_retention_pairs(rows_by_name):
    """Test the retention-flag-vs-index-bit discrimination for the
    TGA-DSTREG byte0-hi sweep (see casematrix.py's caution and
    work/COMPILER-EXPLAINER-INTERACTION-20260828.md / apple9_isa_explainer.md).
    For each (lo, lo|8) pair: identical output -> bit3 INERT for this
    observable; one baseline-like + one a coherent-but-different pattern ->
    INDEX-like; one baseline-like + one matching neither named hypothesis ->
    UNCLASSIFIED (recorded, not forced into a bucket)."""
    out = []
    for lo, hi in CM.tga_dstreg_bit3_pairs():
        rlo = rows_by_name.get("tga_dstreg_%x" % lo)
        rhi = rows_by_name.get("tga_dstreg_%x" % hi)
        if rlo is None or rhi is None:
            out.append({"lo": lo, "hi": hi, "verdict": "MISSING"})
            continue
        same = rlo.get("observed_sha256") == rhi.get("observed_sha256")
        verdict = ("IDENTICAL_bit3_inert" if same else
                  "DIFFERENT_see_matches_baseline_and_ip2_fields")
        out.append({"lo": lo, "hi": hi, "verdict": verdict,
                    "lo_matches_baseline": rlo.get("matches_baseline"),
                    "hi_matches_baseline": rhi.get("matches_baseline"),
                    "lo_matches_ip2": rlo.get("matches_known_ip2_corruption"),
                    "hi_matches_ip2": rhi.get("matches_known_ip2_corruption")})
    return out


def tgls_ld03_digest(rows):
    dense = [r for r in rows if r["item"] == "TGLS-LD-03" and r["name"].startswith("ld_range_f")]
    over = [r for r in rows if r["item"] == "TGLS-LD-03" and r["name"].startswith("ld_over_f")]
    field_to_word = {}
    anomalies = []
    for r in dense:
        f = r["fields"].get("idx_off", 0)
        field_to_word[f] = r["word"]
        if r["word"] != f or r["status"] != "OK":
            anomalies.append({"f": f, "status": r["status"], "word": r["word"],
                              "byte_offset": r["byte_offset"], "fault": r["fault"]})
    first_bad = next((f for f in sorted(field_to_word) if field_to_word[f] != f), None)
    over_rows = []
    first_invalid_over = None
    for r in over:
        f = r["fields"].get("idx_off", 0)
        ok = (r["word"] == f and r["status"] == "OK")
        over_rows.append({"f": f, "status": r["status"], "word": r["word"], "matches_f": ok})
        if not ok and first_invalid_over is None:
            first_invalid_over = f
    return {"dense_range": [0, 2047], "dense_cases": len(dense),
            "field_to_word": field_to_word, "first_bad_within_dense": first_bad,
            "anomalies": anomalies, "over_ceiling_cases": len(over),
            "over_rows_sample": over_rows[:20], "first_invalid_over_ceiling": first_invalid_over}


def tgls_ld01_digest(rows):
    elemsize_rows = [r for r in rows if r["item"] == "TGLS-LD-01"]
    by_code = {}
    for r in elemsize_rows:
        code = r["fields"].get("elem_size")
        by_code[code] = {"status": r["status"], "word": r["word"],
                         "byte_offset": r["byte_offset"], "fault": r["fault"],
                         "undecodable": r.get("undecodable")}
    working_codes = sorted(c for c, v in by_code.items()
                           if v["status"] == "OK" and v["word"] is not None)
    return {"baseline_code": 0x08, "cases": len(elemsize_rows), "by_code": by_code,
            "working_codes": working_codes}


def budget_digest(brows):
    static_rows = [r for r in brows if r["item"] == "BUDGET-STATIC-CAP"]
    dyn_rows = [r for r in brows if r["item"] == "BUDGET-DYNAMIC-CAP"]
    comb_rows = [r for r in brows if r["item"] == "BUDGET-COMBINED"]

    def first_pipeline_fail(rows):
        fails = sorted((r["static_bytes"] for r in rows if r["pipeline_status"] == "FAIL"))
        return fails[0] if fails else None

    def last_pipeline_ok(rows, below):
        oks = sorted((r["static_bytes"] for r in rows
                     if r["pipeline_status"] == "OK" and r["static_bytes"] < below))
        return oks[-1] if oks else None

    static_first_fail = first_pipeline_fail(static_rows)
    static_last_ok = (last_pipeline_ok(static_rows, static_first_fail)
                      if static_first_fail else None)

    def first_corrupt(rows, total_key):
        bad = sorted(((r[total_key[0]] + r[total_key[1]], r["bad_byte_count"])
                      for r in rows if r.get("bad_byte_count") not in (None, 0)))
        return bad[0][0] if bad else None

    def last_clean(rows, total_key, below):
        clean = sorted((r[total_key[0]] + r[total_key[1]] for r in rows
                        if r.get("bad_byte_count") == 0
                        and (r[total_key[0]] + r[total_key[1]]) < below))
        return clean[-1] if clean else None

    dyn_first_bad = first_corrupt(dyn_rows, ("static_bytes", "dynamic_bytes"))
    dyn_last_clean = last_clean(dyn_rows, ("static_bytes", "dynamic_bytes"), dyn_first_bad) \
        if dyn_first_bad else None
    comb_first_bad = first_corrupt(comb_rows, ("static_bytes", "dynamic_bytes"))
    comb_last_clean = last_clean(comb_rows, ("static_bytes", "dynamic_bytes"), comb_first_bad) \
        if comb_first_bad else None

    # PSO_STATIC_TGMEM rounding granularity (queried-property view)
    pso_rounding = sorted(set((r["static_bytes"], r["pso_static_tgmem"])
                              for r in static_rows if r["pipeline_status"] == "OK"))

    return {
        "static_cases": len(static_rows), "dynamic_cases": len(dyn_rows),
        "combined_cases": len(comb_rows),
        "static_last_pipeline_ok_bytes": static_last_ok,
        "static_first_pipeline_fail_bytes": static_first_fail,
        "dynamic_last_clean_total_bytes": dyn_last_clean,
        "dynamic_first_corrupt_total_bytes": dyn_first_bad,
        "combined_last_clean_total_bytes": comb_last_clean,
        "combined_first_corrupt_total_bytes": comb_first_bad,
        "pso_static_tgmem_rounding_sample": pso_rounding[:40],
        "unexpected_pipeline_status": [
            {"name": r["name"], "static_bytes": r["static_bytes"], "dynamic_bytes": r["dynamic_bytes"],
             "expect_pipeline_ok": None, "pipeline_status": r["pipeline_status"]}
            for r in brows if r["pipeline_status"] not in ("OK", "FAIL")],
        "any_dispatch_fault": [
            {"name": r["name"], "status": r["status"], "dispatch_status": r["dispatch_status"]}
            for r in brows if r["status"] not in ("OK", "PIPELINE_FAIL", "COMPILE_FAIL")],
    }


def hand_check(rows_by_name, budget_by_name):
    out = []
    for name, kind, val in CM.hand_validation():
        if kind in ("baseline_array", "known_ip2_corruption"):
            row = rows_by_name.get(name)
            match = (row is not None and (row.get("matches_baseline") if kind == "baseline_array"
                     else row.get("matches_known_ip2_corruption")))
            out.append({"name": name, "kind": kind, "match": bool(match)})
        elif kind == "word":
            row = rows_by_name.get(name)
            elem = val - 0x3CA50000   # the pattern-tag word value decodes to this element index
            match = (row is not None and row.get("word") == elem)
            out.append({"name": name, "kind": kind, "expected_word": elem,
                        "observed_word": (row.get("word") if row else None), "match": bool(match)})
        elif kind == "byte_offset":
            row = rows_by_name.get(name)
            match = (row is not None and row.get("store_byte_offset") == val)
            out.append({"name": name, "kind": kind, "expected": val,
                        "observed": (row.get("store_byte_offset") if row else None),
                        "match": bool(match)})
    return out


def analyze(run_a, run_b):
    a, b = load_run(run_a), load_run(run_b)
    issues = []
    if a["results_sha256"] != b["results_sha256"]:
        issues.append("splice runs are not byte-identical")
    if a["budget_results_sha256"] != b["budget_results_sha256"]:
        issues.append("budget runs are not byte-identical")
    if a["dispatch"]["splice_status_counts"] != b["dispatch"]["splice_status_counts"]:
        issues.append("splice status counts differ across runs")
    if a["dispatch"]["budget_status_counts"] != b["dispatch"]["budget_status_counts"]:
        issues.append("budget status counts differ across runs")

    rows = [classify_splice(line, cs) for line, cs in zip(a["lines"], CM.CASES)]
    rows_by_name = {r["name"]: r for r in rows}
    brows = a["blines"]
    budget_by_name = {r["name"]: r for r in brows}

    by_item = {}
    for row in rows:
        by_item.setdefault(row["item"], []).append(row)

    faults = [{"name": r["name"], "item": r["item"], "status": r["status"],
               "timed_out": r["timed_out"]} for r in rows if r["fault"] or r["timed_out"]]

    tga_pairs = tga_retention_pairs(rows_by_name)
    tga_lendisc = [{"name": r["name"], "status": r["status"],
                    "matches_baseline": r.get("matches_baseline")}
                   for r in by_item.get("TGA-LENDISC", [])]
    tga_reserved = [{"name": r["name"], "status": r["status"],
                     "matches_baseline": r.get("matches_baseline")}
                    for r in by_item.get("TGA-RESERVED", [])]
    tga_srcsel_nonbaseline = [{"name": r["name"], "matches_baseline": r.get("matches_baseline"),
                               "matches_ip2": r.get("matches_known_ip2_corruption"),
                               "status": r["status"]}
                              for r in by_item.get("TGA-SRCSEL", [])
                              if not r.get("matches_baseline")]

    out = {
        "schema": 1, "experiment": "EXP-0096-m4-threadgroup-addressing",
        "runs": [run_a, run_b],
        "results_sha256": {run_a: a["results_sha256"], run_b: b["results_sha256"]},
        "budget_results_sha256": {run_a: a["budget_results_sha256"],
                                  run_b: b["budget_results_sha256"]},
        "repeat_exact": a["results_sha256"] == b["results_sha256"],
        "budget_repeat_exact": a["budget_results_sha256"] == b["budget_results_sha256"],
        "status_counts": a["dispatch"]["splice_status_counts"],
        "budget_status_counts": a["dispatch"]["budget_status_counts"],
        "total_splice_cases": len(rows), "total_budget_cases": len(brows),
        "faults": faults,
        "hand_validation": hand_check(rows_by_name, budget_by_name),
        "tga_dstreg_retention_vs_index_pairs": tga_pairs,
        "tga_srcsel_nonbaseline_count": len(tga_srcsel_nonbaseline),
        "tga_srcsel_nonbaseline_sample": tga_srcsel_nonbaseline[:40],
        "tga_lendisc_rows": tga_lendisc,
        "tga_reserved_rows": tga_reserved,
        "tgls_ld03_digest": tgls_ld03_digest(rows),
        "tgls_ld01_digest": tgls_ld01_digest(rows),
        "tgls_ld_idxreg_rows": [{"name": r["name"], "status": r["status"], "word": r["word"],
                                 "byte_offset": r["byte_offset"]}
                                for r in by_item.get("TGLS-LD-IDXREG", [])],
        "tgls_ld_wrap_rows": [{"name": r["name"], "status": r["status"], "word": r["word"]}
                              for r in by_item.get("TGLS-LD-05", [])],
        "tgls_st03_rows": [{"name": r["name"], "status": r["status"],
                            "store_byte_offset": r["store_byte_offset"],
                            "matches_pred": r["matches_pred"]}
                           for r in by_item.get("TGLS-ST-03", [])],
        "tgls_st01_rows": [{"name": r["name"], "status": r["status"],
                            "store_byte_offset": r["store_byte_offset"]}
                           for r in by_item.get("TGLS-ST-01", [])],
        "budget_digest": budget_digest(brows),
        "issues": issues,
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", default=RUNS[0])
    ap.add_argument("--run-b", default=RUNS[1])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    out = analyze(a.run_a, a.run_b)
    txt = json.dumps(out, indent=2, sort_keys=True) + "\n"
    if a.write:
        (HERE / "analysis.json").write_text(txt)
        print("WROTE analysis.json (%d bytes)" % len(txt))
    else:
        sys.stdout.write(txt)
    bad_hand = [h for h in out["hand_validation"] if not h["match"]]
    if bad_hand or out["issues"]:
        print("ANALYSIS GATE: FAIL (%d hand divergences, %d issues)"
              % (len(bad_hand), len(out["issues"])))
        return 1
    print("ANALYSIS GATE: PASS (hand set reproduced; runs byte-identical)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
