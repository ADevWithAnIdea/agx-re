#!/usr/bin/env python3
"""EXP-0077 deterministic analysis: decode both capture runs, compare them
byte-exactly, classify every case against the frozen hypotheses, and write
analysis.json. No clock, no randomness, no network: identical inputs produce
byte-identical output.

Verdict method (per item):
  MEM-01  which elem_size codes scale the GPR index by which byte stride
          (observed byte offset vs idx * scale table), load and store;
  MEM-02  element-units vs byte-units for idx_off (H-ELEM vs H-BYTE agreement
          counts over the discriminating cases);
  MEM-03  signedness + exact usable range + holes + first-invalid + failure
          mode from the dense 0..2047 sweep at idx=1024 (in-bounds under both
          signedness hypotheses), the idx=64 negative-side probes, the byte+11
          tail-inertness probes and any fault/timeout/undecodable case;
  MEM-04  the element-code space beyond 4 (ceiling, odd codes, high bits) and
          whether any non-power-of-two stride is reachable;
  MEM-05  wrap agreement for the (index + offset) * scale cases that land at
          byte 0 only under exact mod-2^32 arithmetic, plus the failure modes
          of the far-OOB controls.
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
    disp = json.loads((d / "03_dispatch.json").read_text())
    return {"rid": rid, "lines": lines, "dispatch": disp,
            "results_sha256": sha(d / "04_results.jsonl")}


def classify(line, cs):
    """One row of observed evidence for a case."""
    row = {"name": cs["name"], "item": cs["item"], "kernel": cs["kernel"],
           "status": line["status"],
           "idx0": cs["idx"][0] & 0xFFFFFFFF,
           "fields": cs["fields"],
           "out0": line["out0_hex"],
           "byte_offset": None, "word": None, "residue": None,
           "store_byte_offset": None,
           "undecodable": False, "fault": line["status"] in ("CMDBUF_ERROR", "HANG"),
           "timed_out": line["timed_out"]}
    dec = line["decoded"]
    if cs["kernel"] == "ld":
        if dec is None:
            row["undecodable"] = line["status"] == "OK"
            row["raw_value"] = line["out0_hex"]
        else:
            row["byte_offset"], row["word"], row["residue"] = (
                dec["byte_offset"], dec["word"], dec["residue"])
    else:
        if dec is not None:
            row["store_byte_offset"] = dec["byte_offset"]
            row["store_bytes_changed"] = len(dec["nonzero_bytes"])
            row["store_words_changed"] = dec["words_changed"]
    # hypothesis agreement on the frozen predictions
    agrees = {}
    obs = row["byte_offset"] if cs["kernel"] == "ld" else row["store_byte_offset"]
    for hyp, pred in cs["pred"].items():
        if isinstance(pred, int) and 0 <= pred <= (CM.A_WORDS - 1) * 4:
            agrees[hyp] = (obs == pred)
        elif pred == "oob":
            agrees[hyp] = (obs is None)
        else:
            agrees[hyp] = None          # exploration case, no frozen number
    row["agrees"] = agrees
    return row


def hand_check(rows_by_name):
    """Cross-check the frozen hand-computed values (independent of the encoder
    used for predictions): name -> expected 32-bit observation."""
    out = []
    for name, expected in CM.hand_validation():
        row = rows_by_name.get(name)
        if row is None:
            out.append({"name": name, "expected": "0x%08X" % expected, "observed": None,
                        "match": False, "note": "case missing"})
            continue
        obs = int.from_bytes(bytes.fromhex(row["out0"][:8]), "little") if row["out0"] else None
        out.append({"name": name, "expected": "0x%08X" % expected,
                    "observed": ("0x%08X" % obs) if obs is not None else None,
                    "match": obs == expected,
                    "note": "" if obs == expected else "HAND-SET DIVERGENCE"})
    return out


def analyze(run_a, run_b):
    a, b = load_run(run_a), load_run(run_b)
    issues = []
    if a["results_sha256"] != b["results_sha256"]:
        issues.append("runs are not byte-identical")
    if a["dispatch"]["status_counts"] != b["dispatch"]["status_counts"]:
        issues.append("status counts differ across runs")

    rows = [classify(line, cs) for line, cs in zip(a["lines"], CM.CASES)]
    by_item = {}
    for row in rows:
        by_item.setdefault(row["item"], []).append(row)

    # --- hypothesis scoreboards over the discriminating families -------------
    def score(names):
        agree = {}
        for nm in names:
            row = next(r for r in rows if r["name"] == nm)
            for hyp, ok in row["agrees"].items():
                if ok is None:
                    continue
                t, f = agree.get(hyp, (0, 0))
                agree[hyp] = (t + (1 if ok else 0), f + (0 if ok else 1))
        return {k: list(v) for k, v in sorted(agree.items())}

    mem02_names = [c["name"] for c in CM.CASES if c["item"] == "MEM-02"]
    mem05_names = [c["name"] for c in CM.CASES if c["item"] == "MEM-05"]
    mem01_names = [c["name"] for c in CM.CASES if c["item"] == "MEM-01"]

    # --- MEM-03 dense sweep digest -------------------------------------------
    dense = [r for r in by_item.get("MEM-03", []) if r["name"].startswith("ld_range_f")]
    dense_map = {}          # field value -> observed element (word)
    dense_anomalies = []
    for row in dense:
        f = row["fields"].get("idx_off", 0)
        elem = row["word"] if row["residue"] == 0 else None
        dense_map[f] = elem
        exp_u, exp_s = 1024 + f, 1024 + CM.sext11(f)
        if elem is None or (elem != exp_u and elem != exp_s) or row["status"] != "OK":
            dense_anomalies.append({"f": f, "row": {k: row[k] for k in
                                                    ("status", "out0", "byte_offset",
                                                     "word", "residue", "fault")}})
    # decide signedness from the dense sweep: which model explains every case
    fit_u = sum(1 for f, e in dense_map.items() if e == 1024 + f)
    fit_s = sum(1 for f, e in dense_map.items() if e == 1024 + CM.sext11(f))
    # first-invalid under each model (first field value the model misses)
    first_bad_u = next((f for f in sorted(dense_map) if dense_map[f] != 1024 + f), None)
    first_bad_s = next((f for f in sorted(dense_map)
                        if dense_map[f] != 1024 + CM.sext11(f)), None)

    neg = [r for r in by_item.get("MEM-03", []) if r["name"].startswith("ld_neg_")]
    tail = [r for r in by_item.get("MEM-03", []) if r["name"].startswith("ld_tail")]
    st_range = [r for r in by_item.get("MEM-03", []) if r["kernel"] == "st"]

    elemcode = [r for r in by_item.get("MEM-04", []) if r["name"].startswith("ld_elemcode")]
    wrap = by_item.get("MEM-05", [])
    idxreg = by_item.get("VAL-IDXREG", [])
    extra = by_item.get("VAL-EXTRA", [])
    ctrl = by_item.get("CTRL", [])

    faults = [{"name": r["name"], "item": r["item"], "status": r["status"],
               "timed_out": r["timed_out"]}
              for r in rows if r["fault"] or r["timed_out"]]
    undecodable = [r["name"] for r in rows if r["undecodable"] and not r["fault"]]

    out = {
        "schema": 1,
        "experiment": "EXP-0077-m4-mem-offset-semantics",
        "runs": [run_a, run_b],
        "results_sha256": {run_a: a["results_sha256"], run_b: b["results_sha256"]},
        "repeat_exact": a["results_sha256"] == b["results_sha256"],
        "status_counts": a["dispatch"]["status_counts"],
        "total_cases": len(rows),
        "faults": faults,
        "undecodable_ok_status": undecodable,
        "hand_validation": hand_check({r["name"]: r for r in rows}),
        "hypothesis_scores": {
            "MEM-01_scale": score(mem01_names),
            "MEM-02_element_vs_byte_units": score(mem02_names),
            "MEM-05_wrap32": score(mem05_names),
        },
        "mem03_dense": {
            "field_range": [0, 2047],
            "idx0": 1024,
            "cases": len(dense),
            "element_observed_for_every_field_value": dense_map,
            "fit_unsigned": fit_u,
            "fit_signed": fit_s,
            "first_field_value_missed_by_unsigned_model": first_bad_u,
            "first_field_value_missed_by_signed_model": first_bad_s,
            "anomalies": dense_anomalies,
        },
        "mem03_negative_side": [{k: r[k] for k in ("name", "status", "out0",
                                                  "byte_offset", "word", "residue",
                                                  "agrees", "fault")}
                                for r in neg],
        "mem03_tail_probes": [{k: r[k] for k in ("name", "status", "byte_offset", "word",
                                                 "agrees")} for r in tail],
        "mem03_store_boundary": [{k: r[k] for k in ("name", "status", "store_byte_offset",
                                                   "agrees")} for r in st_range],
        "mem04_elemcode_probes": [{k: r[k] for k in ("name", "status", "byte_offset",
                                                     "word", "residue", "out0",
                                                     "fault")} for r in elemcode],
        "mem05_rows": [{k: r[k] for k in ("name", "status", "byte_offset", "word",
                                          "residue", "agrees", "fault", "timed_out")}
                       for r in wrap],
        "val_idxreg_rows": [{k: r[k] for k in ("name", "status", "out0", "byte_offset",
                                               "word", "residue", "fault")} for r in idxreg],
        "val_extra_rows": [{k: r[k] for k in ("name", "status", "out0", "byte_offset",
                                              "word", "agrees")} for r in extra],
        "ctrl_rows": [{k: r[k] for k in ("name", "status", "out0", "byte_offset",
                                         "word", "agrees")} for r in ctrl],
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
