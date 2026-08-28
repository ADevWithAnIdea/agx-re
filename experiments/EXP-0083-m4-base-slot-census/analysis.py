#!/usr/bin/env python3
"""EXP-0083 deterministic analysis: classify the captured base-slot census
observations against the pre-registered hypotheses (MEM-15/MEM-16/MEM-17).

All expectations are computed from the frozen constants imported from run.py
(single source of truth): the fill rule P(k,w) = 0xC0DE0000|(k<<8)|w, the
idxbuf exception (word 0 = probe element index 5), the 31-buffer direct
binding population, and the frozen matrix of 351 cases.

Pre-registered hypotheses under test:
  H1 (MEM-15, capacity kernel): a kernel that reads a distinguishable value
      through every one of the 31 MSL buffer indices at once returns every
      value correctly (all witness words match the fill model).
  H2 (MEM-16 layout): in the 31-binding census, slot k for k = 1..30 holds
      exactly buffer k's base (probe returns P(k,5)); slot 0 does NOT hold
      buffer 0 (pre-freeze feasibility: it returned P(5,0), a word-0 value
      under a word-5 probe -- characterized here, not assumed).
  H3 (MEM-17 load): every slot outside the populated set reads 0x00000000
      with no fault and no buffer change; boundary values 128..255 behave
      identically to value-128 (feasibility: 128 aliased slot 0).
  H4 (MEM-17 store): a store through an unpopulated slot is discarded (no
      bound buffer changes, no fault); a store through a populated slot
      writes that slot's buffer at the probe element.
  H5 (MEM-17 atomic): an exchange through an unpopulated selector returns
      0x00000000 and its write is discarded, no fault; through a populated
      selector it exchanges that buffer's word.
  H6 (census4 control): with only 4 buffers bound, slots 1..3 hold the same
      buffers as in the 31-binding census and slots outside the populated
      set read 0 (per-slot content independent of binding count).
Refuters are per-case; every divergent case is recorded verbatim.

Cross-run discipline (frozen before capture): every case must have identical
status in both runs; probe_word must be identical for every case whose value
is pattern-decodable or exactly zero in either run (the deterministic
classes); only non-decodable non-zero values may legitimately differ (they
are reported as the observed nondeterminism answer, not gate-required).
"""
import argparse, json
from pathlib import Path

import run as R

HERE = Path(__file__).resolve().parent


def load_run(rid):
    lines = (HERE / "raw" / rid / "04_results.jsonl").read_text().splitlines()
    if len(lines) != R.TOTAL:
        raise SystemExit("run %s: expected %d case lines, got %d" % (rid, R.TOTAL, len(lines)))
    out = []
    for i, ln in enumerate(lines):
        q = json.loads(ln)
        c = R.CASES[i]
        if set(q) != R.CASE_KEYS or q["i"] != c["i"] or q["name"] != c["name"] \
                or q["kernel"] != c["kernel"] or q["op"] != c["op"] or q["slot"] != c["slot"]:
            raise SystemExit("run %s: case line %d does not echo the frozen matrix" % (rid, i))
        if q["status"] not in R.STATUS_VALUES:
            raise SystemExit("run %s: case %s has status %r" % (rid, c["name"], q["status"]))
        out.append(q)
    return out


def classify(q):
    """One per-case classification record (verbatim observation + decode)."""
    c = R.CASES[q["i"]]
    rec = {"name": q["name"], "kernel": q["kernel"], "op": q["op"], "slot": q["slot"],
           "cls": c["cls"], "spliced": c["spliced"], "status": q["status"]}
    if q["status"] != "ok":
        rec["cb_status"] = q["cb_status"]
        rec["err"] = (q["err"] or "")[:160]
        rec["result"] = "fault_or_no_record"
        return rec
    word = R.probe_word_value(q["probe_word"]) if q["probe_word"] else None
    rec["probe_word"] = q["probe_word"]
    rec["decoded"] = R.decode_pattern(word) if word is not None else None
    rec["witness_ok"] = q["witness_ok"]
    rec["changed"] = q["changed"]
    if word == 0:
        rec["result"] = "zero"
    elif rec["decoded"] is not None:
        k, w = rec["decoded"]
        rec["result"] = "buffer_k%d_word_w%d" % (k, w)
        rec["holds_buffer"] = k
        rec["word_index"] = w
    else:
        rec["result"] = "nonzero_other"
    return rec


def slot_map(qs, cls):
    rows = {}
    for q in qs:
        c = R.CASES[q["i"]]
        if c["cls"] == cls:
            rows[c["slot"]] = classify(q)
    return rows


def boundary_table(rows, boundaries=(7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 255)):
    return {str(b): rows.get(b, {}).get("result", "not_tested") for b in boundaries}


def alias_report(rows):
    """slots that hold a buffer, buffers held by >1 slot, holes in the hold set."""
    holds = {s: r["holds_buffer"] for s, r in rows.items() if r.get("holds_buffer") is not None}
    by_buf = {}
    for s, b in holds.items():
        by_buf.setdefault(b, []).append(s)
    return {
        "slots_holding_buffers": {str(s): b for s, b in sorted(holds.items())},
        "buffers_held_by_multiple_slots": {str(b): s for b, s in by_buf.items() if len(s) > 1},
        "word_index_anomalies": {str(s): r["word_index"]
                                 for s, r in rows.items()
                                 if r.get("holds_buffer") is not None
                                 and r.get("word_index") != R.GEOMETRY["probe_element_index"]},
        "first_slot_not_holding_a_distinct_buffer":
            next((s for s in sorted(rows)
                  if rows[s].get("holds_buffer") is None), None),
    }


def cross_run(a, b):
    """Frozen cross-run gate (R.cross_run_problems, single authority) +
    observed determinism report."""
    gate_problems = R.cross_run_problems(a, b)
    differing = []
    for i in range(R.TOTAL):
        qa, qb = a[i], b[i]
        if qa["status"] == qb["status"] and qa["probe_word"] != qb["probe_word"]:
            differing.append({"case": qa["name"], "a": qa["probe_word"], "b": qb["probe_word"],
                              "class_a": R.probe_word_class(qa["probe_word"]),
                              "class_b": R.probe_word_class(qb["probe_word"])})
    return differing, gate_problems


def hypotheses(c31, c4, cap, st, at):
    """H1..H6 verdicts with per-case refuters (verbatim)."""
    out = {}
    capq = cap[0] if cap else None
    out["H1_MEM15_capacity_all_reads_correct"] = {
        "hypothesis": "every one of the 31 buffers is read correctly at once",
        "verdict": (capq is not None and capq["status"] == "ok"
                    and capq.get("witness_ok") is True
                    and capq.get("decoded") == (1, R.GEOMETRY["probe_element_index"])),
        "observed": {"status": capq and capq["status"], "witness_ok": capq and capq.get("witness_ok"),
                     "probe": capq and capq.get("decoded")},
        "refuters": [capq["name"]] if capq and (capq["status"] != "ok"
                                                or capq.get("witness_ok") is not True) else []}
    ref = [r for s, r in sorted(c31.items())
           if not (r["status"] == "ok" and r.get("holds_buffer") == s
                   and r.get("word_index") == R.GEOMETRY["probe_element_index"]
                   and r.get("witness_ok") is True)]
    out["H2_MEM16_slots_1_to_30_hold_own_buffer"] = {
        "hypothesis": "census31 slot k returns P(k,5) for k=1..30; slot 0 does not hold buffer 0",
        "verdict": (not [r for s, r in sorted(c31.items()) if 1 <= s <= 30
                         and not (r.get("holds_buffer") == s
                                  and r.get("word_index") == R.GEOMETRY["probe_element_index"])])
        and c31.get(0, {}).get("holds_buffer") != 0,
        "slot0_observed": c31.get(0, {}),
        "refuters": [r["name"] for r in ref if 1 <= r["slot"] <= 30]}
    ref3 = [r for s, r in sorted(c31.items())
            if s not in range(0, 31) and r["status"] != "ok"]
    out["H3_MEM17_unpopulated_load_zero_no_fault"] = {
        "hypothesis": "slots outside 0..30 read 0x00000000, no fault, no buffer change; "
                      "128..255 mirror their value-128 behavior",
        "verdict": (not [r for s, r in sorted(c31.items()) if s > 30
                         and not (r["status"] == "ok" and r["result"] == "zero"
                                  and r["changed"] == [])])
        and all(c31.get(s, {}).get("result") == c31.get(s - 128, {}).get("result")
                for s in range(128, 256) if s in c31),
        "refuters": [r["name"] for r in ref3 if r["status"] != "ok"
                     or r["result"] != "zero" or r["changed"]]}
    out["H4_MEM17_store_discarded_unpopulated"] = {
        "hypothesis": "store via unpopulated slot discarded; via populated slot writes that buffer",
        "verdict": all(r["status"] == "ok" for r in st
                       if r["slot"] > 30) and all(
                           r["changed"] == [] for r in st if r["slot"] > 30 and r["status"] == "ok"),
        "observed": [{"slot": r["slot"], "status": r["status"], "changed": r.get("changed"),
                      "err": r.get("err")} for r in st]}
    out["H5_MEM17_atomic_discarded_unpopulated"] = {
        "hypothesis": "exchange via unpopulated selector returns 0 and writes nothing; "
                      "via populated selector exchanges that buffer",
        "observed": [{"slot": r["slot"], "status": r["status"], "probe": r.get("decoded"),
                      "probe_word": r.get("probe_word"), "changed": r.get("changed"),
                      "err": r.get("err")} for r in at]}
    ref6 = [r for s, r in sorted(c4.items())
            if not (r["status"] == "ok" and (r["result"] == "zero" or r.get("holds_buffer") == s))]
    out["H6_census4_binding_count_independence"] = {
        "hypothesis": "with 4 bindings, slots 1..3 hold the same buffers as census31; "
                      "other tested slots read zero",
        "verdict": not ref6,
        "comparison": {str(s): {"c4": c4.get(s, {}).get("result"),
                                "c31": c31.get(s, {}).get("result")} for s in sorted(c4)},
        "refuters": [r["name"] for r in ref6]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", required=True)
    ap.add_argument("--run-b", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    qs_a, qs_b = load_run(a.run_a), load_run(a.run_b)
    differing, gate_problems = cross_run(qs_a, qs_b)
    if gate_problems:
        (HERE / "analysis_gate_failure.json").write_text(json.dumps(gate_problems, indent=2))
        raise SystemExit("cross-run gate FAILED: %d problems (see analysis_gate_failure.json)"
                         % len(gate_problems))
    # classifications from run A (gate proved run B equivalent in the frozen classes)
    c31 = slot_map(qs_a, "census31")
    c4 = slot_map(qs_a, "census4")
    cap = [classify(q) for q in qs_a if R.CASES[q["i"]]["cls"] == "capacity"]
    st = [classify(q) for q in qs_a if R.CASES[q["i"]]["cls"] == "store"]
    at = [classify(q) for q in qs_a if R.CASES[q["i"]]["cls"] in ("atomic_sel", "atomic_b4")]
    status_counts = {rid: {s: sum(1 for q in qs if q["status"] == s) for s in R.STATUS_VALUES}
                     for rid, qs in ((a.run_a, qs_a), (a.run_b, qs_b))}
    populated = sorted(s for s, r in c31.items() if r.get("holds_buffer") is not None)
    report = {
        "schema": 1, "runs": [a.run_a, a.run_b],
        "status_counts": status_counts,
        "census31": {"slot_map": {str(s): c31[s] for s in sorted(c31)},
                     "boundaries": boundary_table(c31),
                     "alias_report": alias_report(c31),
                     "populated_slots": populated,
                     "n_populated": len(populated)},
        "census4": {"slot_map": {str(s): c4[s] for s in sorted(c4)},
                    "boundaries": boundary_table(c4),
                    "alias_report": alias_report(c4)},
        "capacity": cap,
        "mem15": {"direct_binding_api_max": 31,
                  "capacity_kernel_all_correct": bool(cap and cap[0]["status"] == "ok"
                                                      and cap[0].get("witness_ok") is True),
                  "census31_slots_holding_distinct_buffers": len(populated),
                  "first_slot_not_holding_a_distinct_buffer":
                      alias_report(c31)["first_slot_not_holding_a_distinct_buffer"]},
        "mem16": {"alias_report_31": alias_report(c31),
                  "alias_report_4": alias_report(c4),
                  "boundaries_31": boundary_table(c31),
                  "boundaries_4": boundary_table(c4),
                  "word_index_anomalies_31": alias_report(c31)["word_index_anomalies"]},
        "mem17": {"load": {"zero_slots": sorted(s for s, r in c31.items() if r["result"] == "zero"),
                           "nonzero_other_slots": {str(s): r.get("probe_word") for s, r in c31.items()
                                                   if r["result"] == "nonzero_other"},
                           "fault_slots": {str(s): r["status"] for s, r in c31.items()
                                           if r["result"] == "fault_or_no_record"},
                           "changed_buffers": {str(s): r["changed"] for s, r in c31.items() if r["changed"]}},
                  "store": [{"slot": r["slot"], "status": r["status"],
                             "changed": r.get("changed"), "err": r.get("err")} for r in st],
                  "atomic": [{"slot": r["slot"], "cls": r["cls"], "status": r["status"],
                              "probe": r.get("decoded"), "probe_word": r.get("probe_word"),
                              "changed": r.get("changed"), "err": r.get("err")} for r in at]},
        "repeat": {"probe_word_differences": differing,
                   "gate": "statuses identical everywhere; probe_word identical in the "
                           "deterministic classes (pattern-decodable or zero)"},
        "hypotheses": hypotheses(c31, c4, cap, st, at),
    }
    txt = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if a.write:
        (HERE / "analysis.json").write_text(txt)
        print("WROTE analysis.json (%d bytes); cross-run gate PASS" % len(txt))
    else:
        print(txt)


if __name__ == "__main__":
    main()
