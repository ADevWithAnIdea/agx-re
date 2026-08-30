#!/usr/bin/env python3
"""EXP-0174 analysis: cross-run gate, derived maps, and field verdicts.

  python3 analysis/analyze.py --runs g17p_20260830_run01,g17p_20260830_run02

Writes:
  analysis/field_verdicts.json   flat "<mnemonic>.<field>" per FIELD-SWEEP-PROTOCOL section 5
  analysis/maps.json             the derived dst / source / subform / companion maps
  analysis/gate.json             the cross-run gate arithmetic, per field
  analysis/grid_census.json      the 256x256 byte+2 x byte+3 census

Every number printed here is recomputed from the committed raw. Nothing is
carried over from PROGRESS.md or from the pre-freeze calibration -- `raw/prefreeze/**`
is not read by this script at all.
"""
from __future__ import print_function

import argparse
import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
SEED = {0: 10, 1: 21, 2: 34, 3: 47, 4: 58, 5: 65, 6: 71, 7: 83, 8: 94,
        9: 0x40200000, 10: 113, 11: 119, 12: 125, 13: 127, 14: 3, 15: 121}
BYVAL = {v: k for k, v in SEED.items()}


def load(run):
    return [json.loads(l) for l in
            open(EXP / "raw" / run / "sweep.jsonl")]


def key(r):
    return (r["arm"], r["plan"], r["bytes"])


def dumphash(r):
    o = r.get("observed") or {}
    g = o.get("regs")
    return None if g is None else "".join("%08x" % v for v in g)


# ---------------------------------------------------------------------------
def cross_run(a, b):
    """Per-field cross-run agreement, movement and disagreement, counting ONLY
    cases whose validity is 'valid' in BOTH runs."""
    A = {key(r): r for r in a}
    B = {key(r): r for r in b}
    per = collections.defaultdict(lambda: {
        "shared": 0, "agree": 0, "moved": 0, "disagree_examples": [],
        "values": set(), "bytes": set(), "outcomes": collections.Counter(),
        "carriers": set(), "start": None, "width": None, "encodable_range": None,
        "undecidable": 0, "faults": 0, "skipped": 0})
    for k, ra in A.items():
        rb = B.get(k)
        if rb is None:
            continue
        f = ra["field"]
        p = per[f]
        p["start"], p["width"] = ra["start"], ra["width"]
        p["encodable_range"] = ra["encodable_range"]
        p["values"].add(ra["value"])
        p["bytes"].add(ra["bytes"])
        p["carriers"].add(ra["carrier"])
        if ra.get("skipped") or rb.get("skipped"):
            p["skipped"] += 1
            continue
        if ra["validity"] != "valid" or rb["validity"] != "valid":
            continue
        p["shared"] += 1
        p["outcomes"][ra["outcome"]] += 1
        if ra["outcome"] == "fault":
            p["faults"] += 1
        if ra["undecidable"]:
            p["undecidable"] += 1
        # Agreement compares the (status, OS fault class, dump hash) TRIPLE, not
        # the dump alone. A case that faults reproducibly has no dump in either
        # run, and scoring that as a DISAGREEMENT would be wrong: the two runs
        # made the same observation. It would also be the only kind of case my
        # gate could never pass, which is a defect in the metric rather than a
        # property of the hardware. `27 0a 01 00` (byte0 low nibble 7) is
        # exactly such a case -- a reproducible fault in both runs and both
        # plans -- and it was scoring the X/* falsifier row at 96.875%.
        ha = (ra.get("os_class"), ra["outcome"] == "fault", dumphash(ra))
        hb = (rb.get("os_class"), rb["outcome"] == "fault", dumphash(rb))
        if ha == hb:
            p["agree"] += 1
        elif len(p["disagree_examples"]) < 8:
            p["disagree_examples"].append({"bytes": ra["bytes"],
                                           "run_a": list(ha), "run_b": list(hb)})
        if ra["moved"]:
            p["moved"] += 1
    return per


def maps(rows):
    """The derived operand maps, recomputed from raw."""
    out = {}
    # dst map
    dm = {}
    for r in rows:
        if r["arm"] != "A/dstmap":
            continue
        g = (r["observed"] or {}).get("regs")
        dm.setdefault(str(r["value"]), {})[r["plan"]] = {
            "outcome": r["outcome"], "undecidable": r["undecidable"],
            "written": (None if g is None else g[r["value"]]),
            "moved_slots": r["moved_slots"]}
    out["dst_map"] = dm
    # source map: byte+1 -> what landed in r2
    sm = {}
    for r in rows:
        if r["arm"] != "B/srcmap":
            continue
        g = (r["observed"] or {}).get("regs")
        v = None if g is None else g[2]
        sm.setdefault(str(r["value"]), {})[r["plan"]] = {
            "r2": v, "r2_hex": (None if v is None else "0x%08x" % v),
            "matches_seed_of": BYVAL.get(v), "outcome": r["outcome"],
            "model_predicted": r["oracle"][2] if r["oracle"] else None,
            "match": r["match"]}
    out["src_map"] = sm
    # subform op map (dst = r9, wide) at b3 = 0 and 1
    fm = {}
    for r in rows:
        if r["arm"] != "D/subform":
            continue
        g = (r["observed"] or {}).get("regs")
        fm.setdefault("b3=%02x" % r["b3"], {}).setdefault(str(r["value"]), {})[r["plan"]] = {
            "r9": (None if g is None else "0x%08x" % g[9]),
            "r5": (None if g is None else g[5]),
            "moved_slots": r["moved_slots"], "match": r["match"]}
    out["subform_map"] = fm
    cm = {}
    for r in rows:
        if r["arm"] != "E/companion":
            continue
        g = (r["observed"] or {}).get("regs")
        cm.setdefault("b2=%02x" % r["b2"], {}).setdefault(str(r["value"]), {})[r["plan"]] = {
            "r9": (None if g is None else "0x%08x" % g[9]),
            "moved_slots": r["moved_slots"], "match": r["match"]}
    out["companion_map"] = cm
    return out


def gen_summary(rows, arm):
    tot = ok = und = bad = 0
    fails = []
    for r in rows:
        if r["arm"] != arm:
            continue
        tot += 1
        if r["undecidable"]:
            und += 1
        elif r["outcome"] == "ok" and r["match"]:
            ok += 1
        else:
            bad += 1
            if len(fails) < 25:
                fails.append({"bytes": r["bytes"], "plan": r["plan"],
                              "note": r["note"], "outcome": r["outcome"],
                              "observed": (r["observed"] or {}).get("regs"),
                              "oracle": r["oracle"]})
    return {"total": tot, "ok": ok, "undecidable": und, "failed": bad,
            "failures": fails}


def falsifiers(rows, move_pred):
    """A falsifier FIRES when the observation differs from THE MOVE IT IS MEANT
    TO RULE OUT, which is what PRE_REGISTRATION.md section 6 actually claims
    ("only nibble 3 may produce the predicted move").

    This is deliberately NOT "the observation equals no-change". Byte0's other
    low nibbles are other instruction groups and several of them do their own
    work; that is not a failure of the n3 model, and scoring it as one would be
    a falsifier that cannot be satisfied. `matched_no_change` is reported
    alongside so both readings are visible in the committed analysis."""
    out = {}
    for r in rows:
        if not r["falsifier"] and r["arm"] != "X/selfmove":
            continue
        a = out.setdefault(r["arm"], {
            "n": 0, "fired": 0, "not_fired": [], "undecidable": 0,
            "matched_no_change": 0,
            "definition": "fired == the observed dump differs from the "
                          "n3 MOVE prediction for the same (dst, src)"})
        a["n"] += 1
        if r["undecidable"]:
            a["undecidable"] += 1
            continue
        if r["match"]:
            a["matched_no_change"] += 1
        mp = move_pred.get((r["plan"], r["dst"], r["b1"]))
        obs = (r["observed"] or {}).get("regs")
        if mp is None or obs is None:
            a["fired"] += 1
            continue
        if obs != mp:
            a["fired"] += 1
        elif len(a["not_fired"]) < 12:
            a["not_fired"].append({"bytes": r["bytes"], "plan": r["plan"],
                                   "outcome": r["outcome"], "note": r["note"],
                                   "observed": obs})
    return out


def move_predictions(rows):
    """(plan, dst, b1) -> the dump the n3 MOVE would produce, harvested from
    the arms where the model DID apply and matched. Purely a lookup built from
    this run's own raw."""
    out = {}
    for r in rows:
        if r["arm"] in ("A/dstmap", "B/srcmap", "G/genhalf") and \
                r["predicts"] == "move" and r["b2"] == 0x01 and r["b3"] == 0x00 \
                and r["oracle"]:
            out[(r["plan"], r["dst"], r["b1"])] = r["oracle"]
    return out


def grid_census(run):
    p = EXP / "raw" / run / "grid.jsonl"
    if not p.exists():
        return None
    meta = json.loads((EXP / "raw" / run / "04_grid_meta.json").read_text())
    ref = meta["ref_dump"]
    dst = meta["dst"]
    src_b1 = meta["src_b1"]
    S = (src_b1 >> 1) % 64
    hs = src_b1 & 1
    v = (ref[S] >> (16 * hs)) & 0xFFFF          # the 16-bit source value, 65
    d0 = ref[dst]
    MOVE_LO = (d0 & 0xFFFF0000) | v
    MOVE_HI = (d0 & 0x0000FFFF) | (v << 16)
    NARROW = d0 & 0xFFFF
    kinds = collections.Counter()
    by_kind = collections.defaultdict(list)
    writes = collections.Counter()
    movers_lo, movers_hi = set(), set()
    n = bad = 0
    for l in open(p):
        rec = json.loads(l)
        n += 1
        if rec["y"] != "valid" or rec["s"] != "OK":
            bad += 1
            continue
        b2, b3 = rec["v"]
        delta = {s2: v2 for s2, v2 in (rec["d"] or [])}
        got = delta.get(dst, d0)
        released = (S in delta and delta[S] == 0 and S != dst)
        if got == d0:
            k = "no_write"
        elif got == MOVE_LO:
            k = "move_lo"
            movers_lo.add(b2)
        elif got == MOVE_HI:
            k = "move_hi"
            movers_hi.add(b2)
        elif got == NARROW:
            k = "narrow_in_place"
        elif got == 0:
            k = "zero"
        else:
            k = "other"
        if k != "no_write":
            writes[b2] += 1
        kinds[(k, released)] += 1
        if len(by_kind[k]) < 40:
            by_kind[k].append({"b2": b2, "b3": b3, "dst_val": "0x%08x" % got,
                               "released_src": released})
    def mask_of(bs):
        if not bs:
            return None
        ones = 0xFF
        zeros = 0xFF
        for b in bs:
            ones &= b
            zeros &= (~b) & 0xFF
        return {"bits_always_1": ones, "bits_always_0": zeros,
                "n": len(bs), "values": sorted(bs)}
    return {"run": run, "plan": meta["plan"]["name"], "n": n, "invalid": bad,
            "dst": dst, "src_b1": src_b1, "src_reg": S, "src_half": hs,
            "src_value": v,
            "outcome_kinds": {("%s|released=%s" % k): c
                              for k, c in sorted(kinds.items())},
            "examples": {k: vv for k, vv in by_kind.items()},
            "b2_that_move_lo": mask_of(movers_lo),
            "b2_that_move_hi": mask_of(movers_hi),
            "n_b2_that_write_dst": len(writes),
            "move_mask_check": {
                "hypothesis": "(b2 & 0x03) == 1 and (b2 & 0xE0) == 0",
                "predicted": sorted(b for b in range(256)
                                    if (b & 3) == 1 and (b & 0xE0) == 0),
                "observed_move_lo": sorted(movers_lo),
                "observed_move_hi": sorted(movers_hi)}}


def grid_agreement(r1, r2):
    def load_g(run):
        out = {}
        for l in open(EXP / "raw" / run / "grid.jsonl"):
            d = json.loads(l)
            out[tuple(d["v"])] = json.dumps(d["d"], sort_keys=True)
        return out
    A, B = load_g(r1), load_g(r2)
    shared = set(A) & set(B)
    agree = sum(1 for k in shared if A[k] == B[k])
    dis = [k for k in shared if A[k] != B[k]][:12]
    return {"runs": [r1, r2], "shared": len(shared), "agree": agree,
            "agreement_pct": round(100.0 * agree / max(1, len(shared)), 4),
            "disagree_examples": [list(k) for k in dis]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    args = ap.parse_args()
    r1, r2 = [x.strip() for x in args.runs.split(",")]
    a, b = load(r1), load(r2)
    per = cross_run(a, b)

    gate = {}
    for f, p in sorted(per.items()):
        agree_pct = 100.0 * p["agree"] / max(1, p["shared"])
        dis = p["shared"] - p["agree"]
        gate[f] = {
            "values_dispatched": len(p["values"]),
            "distinct_bytes": len(p["bytes"]),
            "encodable_range": p["encodable_range"],
            "start": p["start"], "width": p["width"],
            "shared_valid_cases": p["shared"],
            "cross_run_agreement_pct": round(agree_pct, 4),
            "moved": p["moved"], "disagreements": dis,
            "movement_over_disagreement": (float("inf") if dis == 0 and p["moved"]
                                           else (p["moved"] / dis if dis else 0.0)),
            "carriers": sorted(p["carriers"]),
            "n_carriers": len(p["carriers"]),
            "outcomes": dict(p["outcomes"]),
            "undecidable": p["undecidable"], "faults": p["faults"],
            "skipped_never_dispatched": p["skipped"],
            "disagree_examples": p["disagree_examples"],
            "gate_agreement_pass": agree_pct >= 99.0,
            "gate_movement_pass": (dis == 0 and p["moved"] > 0) or
                                  (dis > 0 and p["moved"] >= 2 * dis),
        }
    (EXP / "analysis" / "gate.json").write_text(json.dumps(gate, indent=1, sort_keys=True))

    m = maps(a)
    mp_a, mp_b = move_predictions(a), move_predictions(b)
    m["falsifiers_run01"] = falsifiers(a, mp_a)
    m["falsifiers_run02"] = falsifiers(b, mp_b)
    m["gen32_run01"] = gen_summary(a, "F/gen32")
    m["gen32_run02"] = gen_summary(b, "F/gen32")
    m["genhalf_run01"] = gen_summary(a, "G/genhalf")
    m["genhalf_run02"] = gen_summary(b, "G/genhalf")
    m["alternate_control"] = {}
    for run, rows in ((r1, a), (r2, b)):
        alt = collections.defaultdict(set)
        for r in rows:
            if r["arm"] == "X/alternate":
                g = (r["observed"] or {}).get("regs")
                alt[(r["plan"], r["value"])].add(None if g is None else g[2])
        m["alternate_control"][run] = {
            "%s/%s" % k: sorted(v) for k, v in sorted(alt.items())}
    (EXP / "analysis" / "maps.json").write_text(json.dumps(m, indent=1, sort_keys=True))

    census = {"per_run": [], "cross_run_same_plan": None,
              "cross_run_cross_plan": None}
    for run in (r1, r2, "g17p_20260830_run03"):
        c = grid_census(run)
        if c:
            census["per_run"].append(c)
    try:
        census["cross_run_same_plan"] = grid_agreement(r1, "g17p_20260830_run03")
    except Exception as e:
        census["cross_run_same_plan"] = {"error": str(e)}
    try:
        census["cross_run_cross_plan"] = grid_agreement(r1, r2)
    except Exception as e:
        census["cross_run_cross_plan"] = {"error": str(e)}
    (EXP / "analysis" / "grid_census.json").write_text(json.dumps(census, indent=1, sort_keys=True))

    print("=== GATE ===")
    for f in sorted(gate):
        g = gate[f]
        print("%-28s vals=%-4d bytes=%-4d agree=%7.3f%% moved=%-5d dis=%-3d "
              "carriers=%d  %s %s" % (
                  f, g["values_dispatched"], g["distinct_bytes"],
                  g["cross_run_agreement_pct"], g["moved"], g["disagreements"],
                  g["n_carriers"],
                  "AGREE-OK" if g["gate_agreement_pass"] else "AGREE-FAIL",
                  "MOVE-OK" if g["gate_movement_pass"] else "MOVE-FAIL"))
    print()
    print("=== GENERATION ===")
    for k in ("gen32_run01", "gen32_run02", "genhalf_run01", "genhalf_run02"):
        s = m[k]
        print("  %-16s total=%-5d ok=%-5d undecidable=%-4d FAILED=%d"
              % (k, s["total"], s["ok"], s["undecidable"], s["failed"]))
    print()
    print("=== FALSIFIERS (run01) ===")
    for k, v in sorted(m["falsifiers_run01"].items()):
        print("  %-14s n=%-4d fired=%-4d undecidable=%-3d not_fired=%d"
              % (k, v["n"], v["fired"], v["undecidable"], len(v["not_fired"])))
    print()
    print("=== STALE-PIPELINE CONTROL ===")
    print(" ", json.dumps(m["alternate_control"]))
    print()
    print("=== GRID ===")
    for c in census["per_run"]:
        print("  %s plan=%s n=%d invalid=%d  b2 writing dst: %d"
              % (c["run"], c["plan"], c["n"], c["invalid"], c["n_b2_that_write_dst"]))
        print("     kinds:", json.dumps(c["outcome_kinds"]))
        print("     b2 that MOVE_LO:", json.dumps(c["b2_that_move_lo"]))
        print("     b2 that MOVE_HI:", json.dumps(c["b2_that_move_hi"]))
    print("  same-plan  cross-run:", json.dumps(census["cross_run_same_plan"])[:220])
    print("  cross-plan cross-run:", json.dumps(census["cross_run_cross_plan"])[:220])


if __name__ == "__main__":
    main()
