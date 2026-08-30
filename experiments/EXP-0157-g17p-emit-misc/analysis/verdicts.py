#!/usr/bin/env python3
"""EXP-0157 verdict builder.

Reads the gated captures, adjudicates them against each other, and writes
`analysis/field_verdicts.json` in the FIELD-SWEEP-PROTOCOL section 5 schema.

Rules applied here, all pre-registered:

  * a field is scored ONLY at an anchor whose `_ANCHOR_VERDICT` is `live`;
  * a case counts ONLY if both gated runs report the same outcome;
  * `fault`/`hang` in one run and something else in the other is a DISAGREEMENT
    and is excluded (and counted), never averaged;
  * every label comes from `docs/evidence-classification.md` section 2 and
    nothing else; `target` is always `G17P`.

A field reaches `hardware-run` only if its full pre-registered value set was
executed at a LIVE anchor with agreement across both runs. Anything less is
reported at the weaker label it actually earned -- `untested` when the anchor
was inert, because an inert anchor proves nothing about the field.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))

OUTCOME_OK = "ok"

# ---------------------------------------------------------------------------
# db.json corrections established by THIS experiment, on hardware.
# `db.json` is NOT edited here (FIELD-SWEEP-PROTOCOL section 6); the
# orchestrator owns it.
# ---------------------------------------------------------------------------
DB_DEFECTS = {
  "op04_len8.length": {
    "claim": "db.json declares a FIXED length of 8 for every byte0 low-nibble-4 residue.",
    "measured": "Refuted on hardware. A register-witness probe (harness/run_lm.py, "
                "both positive controls passing) measures the CONSUMED length "
                "directly. All six `op04_len8` byte patterns taken from our own "
                "G17P compiles consume TWELVE bytes, not eight.",
    "rule": "For a `04` leader the consumed length is a joint function of byte+1 "
            "bit 7 and byte+2 (and, in the bit7-clear family, byte+3 bit 7). With "
            "byte+2 = 0x00 and byte+3 = 0x00: byte+1 bit7 SET -> 4, CLEAR -> 8. "
            "With the candidates' own tails: byte+1 bit7 SET -> 8, CLEAR -> 12 "
            "(128/128 split, reproduced on three independent candidates). Full "
            "measured map: analysis/length_rule.json and analysis/length_map_q.json.",
    "target": "G17P", "evidence": ["EXP-0157"],
    "note": "This resolves the item EXP-0148 left OPEN, by a different method: "
            "EXP-0148 scored six STATIC length rules on corpus tokenization, and "
            "round-trip is blind to over-consumption by construction. This asks "
            "the silicon. It does NOT re-run EXP-0148's six rules."
  },
  "mesh_out_src.length": {
    "claim": "db.json declares `04 XX` to be a 2-byte MESH-stage compact source op.",
    "measured": "CONFIRMED for byte+1 bit7 CLEAR and REFUTED for bit7 SET, in a "
                "COMPUTE program. Splicing `04 XX` ahead of four 2-byte marker "
                "instructions: all 128 values with bit7 clear consume exactly 2 "
                "bytes (every marker runs); all 128 with bit7 set consume 4 (the "
                "first marker is swallowed). No value changed the stored result, "
                "so `sel` has no observable effect in a compute program.",
    "target": "G17P", "evidence": ["EXP-0157"],
    "note": "`mesh_out_src`'s match is byte0 == 0x04 with no constraint on byte+1, "
            "so as written it also matches the 4-byte form. It collides with "
            "`op04_len8`, whose match is only the byte0 low nibble."
  },
  "sfu_marker.fields": {
    "claim": "db.json: 'byte-INVARIANT 2-byte token (06 02) ... fixed control token "
             "with no operand bits'. It therefore has ZERO fields.",
    "measured": "Refuted on G17P, reproducing EXP-0146's M4 result EXACTLY and in "
                "THREE independent carriers (fast::sin, fast::cos, sin+cos+tan): "
                "byte+0 accepts only (v & 0xf7) == 0x06 (2 of 256) and byte+1 only "
                "(v & 0x13) == 0x02 (32 of 256). Both bytes are load-bearing.",
    "target": "G17P", "evidence": ["EXP-0157", "EXP-0146"],
    "note": "A descriptor with zero fields cannot be counted against emittability "
            "and cannot be emitted with any variation; it needs two 8-bit fields."
  },
  "rtq_pred.reachability": {
    "claim": "db.json models `06 c2 00 00` as a ray-query traversal predicate word.",
    "measured": "Not refuted, but NOT REACHABLE from either own-MSL ray-query "
                "carrier we can build. Erasing all four bytes at 8 of 8 resolved "
                "anchors (triangle geometry) and 10 of 10 (bounding-box geometry) "
                "leaves the traversal oracle exactly correct; erasing 256 "
                "CONTIGUOUS bytes at three of those offsets also leaves it correct, "
                "while the same 4-byte erase over a live `sr_read_wide` anchor "
                "breaks it immediately.",
    "target": "G17P", "evidence": ["EXP-0157"],
    "note": "Those regions are UNREACHED, not inert. Nothing about the descriptor "
            "may be concluded from this experiment."
  },
  "rtq_dualsrc.reachability": {
    "claim": "db.json models `17 02 00 ..` as a 12-byte intersection_query dual-source op.",
    "measured": "Same as rtq_pred: inert at 11 of 11 anchors under triangle geometry "
                "and 12 of 12 under bounding-box geometry, and a 256-byte erase at "
                "three of those offsets leaves the oracle correct. UNREACHED.",
    "target": "G17P", "evidence": ["EXP-0157"]
  },
  "n2_op8.no_carrier_on_G17P": {
    "claim": "db.json: the transcendental SFU range-reduction select; EXP-0146 found "
             "it in `fast::sin` on M4/G16G.",
    "measured": "NOT EMITTED by any of 17 own-MSL provocations on G17P across two "
                "independent rounds (fast/precise sin, cos, tan, sinpi/cospi/tanpi, "
                "exp/log/pow, atan2/asin/acos, sinh/cosh/tanh, rsqrt/sqrt/divide, "
                "modf/fract/fmod, half transcendentals, large-argument forms, with "
                "and without fast-math). Also absent from every ray-query carrier.",
    "target": "G17P", "evidence": ["EXP-0157"],
    "note": "A statement about what G17P's compiler emits, not about the silicon. "
            "The M4 evidence stands on its own target. All 4 fields stay `untested` "
            "on G17P for want of a carrier."
  },
  "coord_madf.no_carrier_on_G17P": {
    "claim": "db.json: byte0-LEADER 0x2e coordinate FMA, gated on byte+2 == 0x23 "
             "(EXP-0037, cube/array coordinate generation).",
    "measured": "NOT EMITTED by any of 9 own-MSL texture provocations on G17P "
                "(cube, cube-array, 3D, 2D-array, sample_compare, gather, explicit "
                "level, gradientcube, read_write 3D), with and without fast-math.",
    "target": "G17P", "evidence": ["EXP-0157"],
    "note": "All 5 fields stay `untested` on G17P for want of a carrier."
  },
}


# ---------------------------------------------------------------------------
# Fields this experiment DECLINES to promote even though the mechanical rule
# would allow it. Each carries the reason; none is a bookkeeping convenience.
# ---------------------------------------------------------------------------
DECLINED = {
  ("scoreboard_fence", "kind"): "fence",
  ("scoreboard_fence", "scope"): "fence",
  ("scoreboard_fence", "mask"): "fence",
  ("compute_fence_scoped", "kind"): "fence",
  ("compute_fence_scoped", "scope"): "fence",
  ("compute_fence_scoped", "mask"): "fence",
  ("op04_len8", "dst"): "length",
  ("op04_len8", "mode"): "length",
  ("op04_len8", "body"): "length",
}
DECLINE_REASON = {
  "fence": ("DECLINED. The u64eq carrier DOES detect this fence's removal -- replacing its "
            "four bytes with a hardware-verified inert filler (two mov_imm(r13,0), whose "
            "inertness arm L's CTRL_INERT established on this target) breaks the oracle, "
            "which is more than EXP-0141 or EXP-0147 could show. But detecting REMOVAL is "
            "not detecting ORDERING: nothing here shows two different fence values "
            "producing two different, host-predictable orderings, so an accepted value may "
            "preserve the required ordering or may merely be indistinguishable here. Per the "
            "dispatch, promotion needs ordering-specific litmus power. Left `untested`."),
  "length": ("DECLINED. This experiment REFUTED the descriptor's length on hardware: the six "
             "real `op04_len8` patterns from our own G17P compiles consume TWELVE bytes, not "
             "the eight db.json declares (harness/run_lm.py, both controls passing). Every "
             "field offset in the descriptor is therefore measured against a model that is "
             "wrong, and the sweep's near-total inertness is explained by splicing only 8 of "
             "the instruction's 12 bytes. No field of a descriptor whose LENGTH is refuted "
             "may be promoted. Left `untested`; the corrected length model is in db_defects."),
}


def load(path):
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def load_many(paths):
    out = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for q in sorted(p.rglob("sweep.jsonl")):
                out += load(q)
        else:
            out += load(p)
    return out


def key(r):
    return (r.get("arm"), r.get("carrier"), r.get("instr"), r.get("anchor_idx"),
            r.get("field"), r.get("value"))


def bit_rule(ok_vals, all_vals):
    """Exact (mask, value) such that ok <=> (v & mask) == value, or None."""
    ok = set(ok_vals)
    other = set(all_vals) - ok
    if not ok or not other:
        return None
    mask = 0xFF
    if max(all_vals) > 0xFF:
        mask = (1 << max(1, max(all_vals).bit_length())) - 1
    first = next(iter(ok))
    m = mask
    for v in ok:
        m &= ~(v ^ first) & mask
    val = first & m
    if all((v & m) == val for v in ok) and all((v & m) != val for v in other):
        return m, val
    return None


def summarize_field(recs):
    out = collections.Counter(r["outcome"] for r in recs)
    vals = [r["value"] for r in recs]
    okv = [r["value"] for r in recs if r["outcome"] == OUTCOME_OK]
    return out, vals, okv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", help="sweep.jsonl paths or run dirs")
    ap.add_argument("--out", default=str(HERE / "field_verdicts.json"))
    ap.add_argument("--report", default=str(HERE / "gate_report.json"))
    a = ap.parse_args()

    runs = [load_many([p]) for p in a.runs]
    print("runs: %s" % [len(r) for r in runs])

    # ---- anchor liveness (a live verdict in ANY run makes the anchor live) --
    live = set()
    scanned = set()
    for rs in runs:
        for r in rs:
            if r.get("field") == "_ANCHOR_VERDICT":
                k = (r["arm"], r["carrier"], r["instr"], r["anchor_idx"])
                scanned.add(k)
                if r["outcome"] == "live":
                    live.add(k)

    # ---- gate ---------------------------------------------------------------
    # GATE SHAPE. runs[0] is the first capture. The remaining runs are the
    # SECOND capture, and they are complementary rather than replicated: run02
    # was stopped as a partial and run03 covers exactly the carriers run02 never
    # reached, so the second capture is their UNION, not their intersection.
    # Intersecting all three would silently discard every case the (much
    # smaller) later run had not yet reached -- which is how a 6-descriptor
    # result briefly read as 3. A case is gated when it appears in runs[0] AND
    # in at least one later run; the two are compared pairwise.
    maps = [{key(r): r for r in rs
             if not str(r.get("field", "")).startswith("_")} for rs in runs]
    if len(maps) == 1:
        common = set(maps[0])
        agree = {k: maps[0][k] for k in common}
        disagree = {}
    else:
        second = {}
        for m in maps[1:]:
            for k, r in m.items():
                second.setdefault(k, r)
        common = set(maps[0]) & set(second)
        agree, disagree = {}, {}
        for k in common:
            if maps[0][k]["outcome"] == second[k]["outcome"]:
                agree[k] = maps[0][k]
            else:
                disagree[k] = sorted({maps[0][k]["outcome"], second[k]["outcome"]})

    gate = {"runs": a.runs, "records_per_run": [len(r) for r in runs],
            "common_cases": len(common), "agreeing": len(agree),
            "disagreeing": len(disagree),
            "anchors_scanned": len(scanned), "anchors_live": len(live),
            "disagreement_examples": [
                {"key": list(k), "outcomes": v}
                for k, v in list(disagree.items())[:40]]}

    # ---- per-field verdicts -------------------------------------------------
    byfield = collections.defaultdict(list)
    for k, r in agree.items():
        byfield[(r["arm"], r["carrier"], r["instr"], r["anchor_idx"],
                 r["field"])].append(r)

    verdicts = {}
    for (arm, carrier, instr, aidx, field), recs in sorted(byfield.items()):
        anchor_live = (arm, carrier, instr, aidx) in live
        counts, vals, okv = summarize_field(recs)
        rule = bit_rule(okv, vals)
        name = "%s.%s@%s" % (instr, field, carrier)
        width_full = len(set(vals))
        label = "hardware-run" if anchor_live else "untested"
        note = ""
        dec = DECLINED.get((instr, field.split(".")[0]))
        if dec:
            label = "untested"
            note = DECLINE_REASON[dec]
        elif not anchor_live:
            note = ("anchor at offset %s failed BOTH liveness controls, so this "
                    "sweep proves nothing about the field; recorded, not promoted"
                    % recs[0].get("anchor"))
        if len(counts) == 1 and OUTCOME_OK in counts and anchor_live:
            note = ("HW-TESTED INERT in this carrier: every value reproduced the "
                    "carrier's oracle exactly. Inert here does NOT mean "
                    "don't-care in general.")
        entry = {
            "label": label,
            "range": "%d values executed (%s)" % (
                width_full,
                "full dense" if width_full in (2, 4, 8, 16, 32, 64, 128, 256)
                else "boundaries + samples"),
            "target": "G17P",
            "evidence": ["EXP-0157"],
            "carrier": carrier,
            "anchor": recs[0].get("anchor"),
            "anchor_after_gap": recs[0].get("after_gap"),
            "anchor_live": anchor_live,
            "outcomes": dict(counts),
            "ok_values": len(okv),
            "exact_rule": ("(value & 0x%02x) == 0x%02x" % rule) if rule else None,
            "note": note,
            "semantics": "",
        }
        if name in verdicts:
            verdicts[name + "#a%d" % aidx] = entry
        else:
            verdicts[name] = entry

    verdicts["db_defects"] = DB_DEFECTS
    Path(a.out).write_text(json.dumps(verdicts, indent=1, sort_keys=True) + "\n")
    Path(a.report).write_text(json.dumps(gate, indent=1, sort_keys=True) + "\n")
    print("fields: %d   live anchors: %d/%d   agree %d / disagree %d"
          % (len(verdicts), len(live), len(scanned), len(agree), len(disagree)))


if __name__ == "__main__":
    main()
