#!/usr/bin/env python3
"""EXP-0076 deterministic analysis: classify the captured buffer-robustness
observations against the pre-registered hypotheses (MEM-06..MEM-10).

All expectations are computed from the frozen constants imported from run.py
(single source of truth): the 64-byte allocation, the fill rule
F(i) = (0xA5 + 0x1B*i) mod 256, the store rule S(j) = (0xC7 + j) mod 256, and
the frozen matrix of 106 cases.

Pre-registered hypothesis under test, for every executed case:
  H1 (MEM-06): an unaligned load of width W at byte offset OFF returns exactly
      the little-endian bytes F(OFF..OFF+W) with no fault and no buffer change.
  H2 (MEM-07): an unaligned store of width W writes exactly S(0..W) at
      OFF..OFF+W and leaves every other byte of the allocation unchanged.
  H3 (MEM-08): an out-of-allocation read returns the uniform value 0x00 for
      every tested width/alignment.
  H4 (MEM-09): a read that starts in-bounds and crosses the end returns the
      per-component mix (in-bounds fill bytes + 0x00 for the OOB tail).
  H5 (MEM-10): an out-of-allocation store is discarded: the allocation, both
      guard allocations, and both result guards are unchanged.
Refuters are per-case; every divergent case is recorded verbatim.

Cross-run discipline (frozen before capture): in-bounds cases must be
byte-identical between the two runs (a violation is a hard STOP); per-case
identity of out-of-allocation/straddle/atomic observations is REPORTED as the
observed determinism answer, not required.
"""
import argparse, json
from pathlib import Path

import run as R

HERE = Path(__file__).resolve().parent

LOAD_OOB = ("oob1", "far")


def bfill():
    return bytes(R.fill(i) for i in range(64))


def bstore():
    return bytes((0xC7 + j) & 0xFF for j in range(16))


def expected_load(off, w):
    """H1/H3/H4 expected value bytes for a load of width w at offset off."""
    return bytes(R.fill(off + j) if off + j < 64 else 0x00 for j in range(w))


def expected_store_buffer(off, w):
    """H2/H5 expected 64-byte allocation contents after a store (OOB discarded)."""
    b = bytearray(bfill())
    for j in range(w):
        i = off + j
        if i < 64:
            b[i] = bstore()[j]
    return bytes(b)


def load_run(rid):
    lines = (HERE / "raw" / rid / "04_results.jsonl").read_text().splitlines()
    if len(lines) != R.TOTAL:
        raise SystemExit("run %s: expected %d case lines, got %d" % (rid, R.TOTAL, len(lines)))
    out = []
    for i, ln in enumerate(lines):
        q = json.loads(ln)
        c = R.CASES[i]
        if set(q) != R.CASE_KEYS or q["i"] != c["i"] or q["name"] != c["name"] \
                or q["op"] != c["op"] or q["width"] != c["width"] or q["off"] != c["off"]:
            raise SystemExit("run %s: case line %d does not echo the frozen matrix" % (rid, i))
        if q["status"] not in R.STATUS_VALUES:
            raise SystemExit("run %s: case %s has status %r" % (rid, c["name"], q["status"]))
        out.append(q)
    return out


def diffs(a, b):
    """Positions and values where byte sequences differ (little-endian hex)."""
    return [{"byte": i, "expected": "%02x" % a[i], "observed": "%02x" % b[i]}
            for i in range(min(len(a), len(b))) if a[i] != b[i]]


def classify(q):
    """One per-case record: expectation under H1..H5 vs observation, verbatim."""
    c = R.CASES[q["i"]]
    rec = {"name": q["name"], "op": q["op"], "width_bits": 8 * q["width"], "off": q["off"],
           "cls": c["cls"], "status": q["status"]}
    if q["status"] != "ok":
        rec["observed"] = {"cb_status": q["cb_status"], "err": q["err"], "exit": q["exit"],
                           "timed_out": q["timed_out"]}
        rec["result"] = "fault_or_no_record"
        return rec
    obs = bytes.fromhex(q["obs"]) if q["obs"] else b""
    buf = bytes.fromhex(q["buf_after"]) if q["buf_after"] else b""
    rec["guards"] = {k: q[k] for k in ("pre_ok", "g1_ok", "g2_ok", "res_g0_ok", "res_g1_ok")}
    if q["op"] in ("load", "axch"):
        w = q["width"]
        exp = expected_load(q["off"], w)
        got = obs[:w]
        rec["expected_value_hex"] = exp.hex()
        rec["observed_value_hex"] = got.hex()
        rec["value_matches_hypothesis"] = got == exp
        if got != exp:
            rec["value_diffs"] = diffs(exp, got)
    if q["op"] in ("store", "axch"):
        expb = expected_store_buffer(q["off"], q["width"])
        rec["buffer_matches_hypothesis"] = buf == expb
        if buf != expb:
            rec["buffer_diffs"] = diffs(expb, buf)[:16]
        rec["window_after_hex"] = (buf[q["off"]:q["off"] + q["width"]].hex()
                                   if q["off"] < 64 else "")
    if q["op"] == "load":
        rec["buffer_unchanged_by_load"] = buf == bfill()
    # per-class result tag
    if c["cls"] in R.IN_BOUND_CLASSES:
        key = "value_matches_hypothesis" if q["op"] == "load" else "buffer_matches_hypothesis"
        rec["result"] = "byte_exact" if rec.get(key) else "divergent"
    elif c["cls"] in LOAD_OOB and q["op"] == "load":
        got = obs[:q["width"]]
        rec["result"] = "oob_read_all_zero" if got == b"\x00" * q["width"] else "oob_read_nonzero"
    elif c["cls"] in LOAD_OOB and q["op"] == "store":
        unchanged = buf == bfill() and q["g1_ok"] and q["g2_ok"] and q["res_g0_ok"] and q["res_g1_ok"]
        rec["result"] = "oob_store_discarded" if unchanged else "oob_store_not_discarded"
    elif c["cls"].startswith("straddle"):
        w, off = q["width"], q["off"]
        nb = 64 - off                       # in-bounds byte count of the window
        if q["op"] == "load":
            got = obs[:w]
            rec["in_bounds_part_matches"] = got[:nb] == bytes(R.fill(off + j) for j in range(nb))
            rec["oob_part_all_zero"] = got[nb:] == b"\x00" * (w - nb)
            rec["oob_part_hex"] = got[nb:].hex()
            rec["result"] = ("straddle_mix_model" if rec["in_bounds_part_matches"]
                             and rec["oob_part_all_zero"] else "straddle_divergent")
        else:
            inb = buf[off:64] == bstore()[:nb]
            rest = buf[:off] == bfill()[:off]
            rec["in_bounds_part_written"] = inb
            rec["rest_of_buffer_unchanged"] = rest
            guards = q["g1_ok"] and q["g2_ok"] and q["res_g0_ok"] and q["res_g1_ok"]
            rec["result"] = ("straddle_store_model" if inb and rest and guards
                             else "straddle_store_divergent")
    else:  # axch stretch: both the exchanged-out value and the buffer must match
        rec["result"] = ("byte_exact" if rec.get("value_matches_hypothesis")
                         and rec.get("buffer_matches_hypothesis") else "divergent")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", required=True)
    ap.add_argument("--run-b", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    A = load_run(a.run_a)
    B = load_run(a.run_b)

    # frozen cross-run discipline
    differing = [qa["name"] for qa, qb in zip(A, B)
                 if json.dumps(qa, sort_keys=True) != json.dumps(qb, sort_keys=True)]
    inb_diff = [qa["name"] for qa, qb in zip(A, B)
                if R.CASES[qa["i"]]["cls"] in R.IN_BOUND_CLASSES
                and json.dumps(qa, sort_keys=True) != json.dumps(qb, sort_keys=True)]
    if inb_diff:
        raise SystemExit("in-bounds cases differ between runs (frozen gate): %s" % inb_diff)

    per_case = [classify(q) for q in A]
    by_name = {r["name"]: r for r in per_case}

    def sel(pred):
        return [r for r in per_case if pred(r)]

    def summarize(rows):
        divergent = [r["name"] for r in rows if r["result"] not in
                     ("byte_exact", "oob_read_all_zero", "oob_store_discarded",
                      "straddle_mix_model", "straddle_store_model")]
        return {"total": len(rows), "divergent": len(divergent), "divergent_cases": divergent}

    load_rows = sel(lambda r: r["op"] == "load" and r["cls"] in R.IN_BOUND_CLASSES)
    store_rows = sel(lambda r: r["op"] == "store" and r["cls"] in R.IN_BOUND_CLASSES)
    oob_read = sel(lambda r: r["op"] == "load" and r["cls"] in LOAD_OOB)
    oob_store = sel(lambda r: r["op"] == "store" and r["cls"] in LOAD_OOB)
    straddle = sel(lambda r: r["cls"].startswith("straddle"))
    atomic = sel(lambda r: r["op"] == "axch")
    faults = sel(lambda r: r["result"] == "fault_or_no_record")
    guard_anomalies = [r for r in per_case if r["status"] == "ok" and r.get("guards")
                       and not all(r["guards"].values())]

    # unaligned-only view (mis1/mishalf) for MEM-06/MEM-07, per width
    def unaligned(rows):
        return [{"name": r["name"], "width_bits": r["width_bits"], "off": r["off"],
                 "result": r["result"]} for r in rows if r["cls"] in ("mis1", "mishalf")]

    out = {
        "runs": [a.run_a, a.run_b],
        "matrix_cases": R.TOTAL,
        "status_counts": {a.run_a: {s: sum(1 for q in A if q["status"] == s) for s in R.STATUS_VALUES},
                          a.run_b: {s: sum(1 for q in B if q["status"] == s) for s in R.STATUS_VALUES}},
        "repeat": {"all_lines_identical": not differing, "differing_cases": differing,
                   "in_bounds_identical": not inb_diff},
        "hypotheses": {
            "H1_MEM06_unaligned_loads_byte_exact": summarize(load_rows),
            "H2_MEM07_unaligned_stores_byte_exact": summarize(store_rows),
            "H3_MEM08_oob_reads_zero": summarize(oob_read),
            "H4_MEM09_straddle_reads_mix": summarize(
                [r for r in straddle if r["op"] == "load"]),
            "H5_MEM10_oob_stores_discarded": summarize(oob_store),
        },
        "mem06_unaligned_loads": unaligned(load_rows) + [
            {"name": r["name"], "width_bits": r["width_bits"], "result": r["result"],
             "note": "control"} for r in load_rows if r["cls"] in ("align_in", "last")],
        "mem07_unaligned_stores": unaligned(store_rows) + [
            {"name": r["name"], "width_bits": r["width_bits"], "result": r["result"],
             "note": "control"} for r in store_rows if r["cls"] in ("align_in", "last")],
        "mem08_oob_reads": [{"name": r["name"], "width_bits": r["width_bits"], "off": r["off"],
                             "cls": r["cls"], "observed_value_hex": r.get("observed_value_hex"),
                             "result": r["result"]} for r in oob_read],
        "mem09_straddle_reads": [r for r in straddle if r["op"] == "load"],
        "mem10_oob_stores": [r for r in oob_store],
        "straddle_stores": [r for r in straddle if r["op"] == "store"],
        "atomic_stretch": atomic,
        "faults": faults,
        "guard_anomalies": guard_anomalies,
        "load_buffer_mutations": [r["name"] for r in per_case
                                  if r["op"] == "load" and r["status"] == "ok"
                                  and r.get("buffer_unchanged_by_load") is False],
        "per_case": per_case,
    }
    txt = json.dumps(out, indent=2, sort_keys=True) + "\n"
    if a.write:
        (HERE / "analysis.json").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
