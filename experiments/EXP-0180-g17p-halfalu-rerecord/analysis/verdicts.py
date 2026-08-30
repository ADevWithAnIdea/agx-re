#!/usr/bin/env python3
"""EXP-0180 raw -> analysis/field_verdicts.json (flat, FIELD-SWEEP-PROTOCOL section 5)
and analysis/reproduction.json.

The gates are the ones frozen in PRE_REGISTRATION.md section 7 and CAPTURE_CONTRACT.json.
Nothing is decided here that was not decided before the run:

  gate_stable         >= 99.0% per-value cross-run agreement on the observation digest
  gate_live           moved >= 2x disagreements, and moved > 0
  gate_ladder         the (arm,carrier)'s ladder passed AND all its falsifiers fired.
                      A failing instrument supports NEITHER live NOR inert.
  gate_identity       a value counts as movement only if its `tok_instr` AND its
                      HARDWARE-MEASURED length equal the anchor's. Values that fail are
                      recorded, reported, and EXCLUDED from `encodable_range`, which is
                      restated as the MEASURED range. (EXP-0169 section 16b generalised.)
  gate_expressiveness an INERT reading maps to `hardware-run` ONLY for a field whose
                      controlled dimension is YES in EXPRESSIVE below. rsv6/b7_lo/b7_mid
                      have no nameable dimension and no carrier difference, so inertness
                      there is NOT promotable whatever the statistics say (EXP-0179's
                      ret.scoreboard declination, made a standing rule).

Outcomes that are NOT observations -- `measurement_failed`, `invalid_run`, `carrier_dead`
-- never count as movement, never count as inertness, and are excluded from
`values_dispatched` so they cannot inflate coverage either.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
MIN_AGREE_PCT = 99.0
MOVED_OVER_DISAGREE = 2.0
NON_OBSERVATIONS = ("measurement_failed", "invalid_run", "carrier_dead")

# FROZEN (PRE_REGISTRATION.md 11b). "YES" = the carriers/arms differ in the dimension the
# field controls, so an INERT reading is meaningful. "NO" = they do not, so an inert reading
# is not promotable and the row is reported as NOT ANSWERABLE by this experiment.
EXPRESSIVE = {
    "half_alu_ext8.dst": "YES", "half_alu_ext8.srcA": "YES", "half_alu_ext8.b5": "YES",
    "half_alu_ext8.srcB_desc": "YES", "half_alu_ext8.opsel": "YES",
    "half_alu_ext8.opflags": "PARTIAL", "half_alu_ext8.saturate": "YES",
    "half_alu_ext8.op_valid_marker": "YES",
    "half_alu_ext8.rsv6": "NO", "half_alu_ext8.b7_lo": "NO", "half_alu_ext8.b7_mid": "NO",
    "half_alu_fma12.dst": "YES", "half_alu_fma12.srcA": "YES",
    "half_alu_fma12.opsel": "YES", "half_alu_fma12.opflags": "PARTIAL",
    "half_alu_fma12.ext": "NOT-A-FIELD",
}


def load(run):
    recs = []
    for ln in open(str(EXP / "raw" / run / "sweep.jsonl")):
        ln = ln.strip()
        if ln:
            recs.append(json.loads(ln))
    return recs


def digest(o):
    if o is None:
        return None
    return ("".join("%08x" % v for v in o["post"])
            + "|%08x%08x" % (o["pre_sent"], o["post_sent"])
            + "|" + ",".join("%d:%08x" % (i, v) for i, v in o["stray"]))


def len_map(recs):
    """The HARDWARE length rule, measured by the LEN arm: 4 surviving markers -> 6 bytes,
    3 -> 8, 2 -> 10, 1 -> 12, 0 -> 14. Keyed by (byte+2, byte+4)."""
    m, zero = {}, None
    for r in recs:
        if r["arm"] != "LEN":
            continue
        if r["field"] == "__falsifier_F4_zero_point":
            zero = r.get("hw_markers")
            continue
        if r.get("hw_markers") is None or r["outcome"] in NON_OBSERVATIONS:
            continue
        b = bytes.fromhex(r["bytes"])
        m[(b[2], b[4])] = 6 + 2 * (4 - r["hw_markers"])
    return m, zero


def hw_len(lm, blk, fallback):
    return lm.get((blk[2], blk[4]), fallback)


def main(runA, runB):
    A, B = load(runA), load(runB)
    lmA, zeroA = len_map(A)
    lmB, zeroB = len_map(B)
    lm = lmA if lmA else lmB

    anchors = {}
    for run, recs in ((runA, A), (runB, B)):
        for ln in open(str(EXP / "raw" / run / "anchor.jsonl")):
            a = json.loads(ln)
            anchors[(run, a["arm"], a["carrier"])] = a

    def index(run, recs):
        d = defaultdict(dict)
        for r in recs:
            if r.get("foreign") or r["field"].startswith("__"):
                continue
            key = (r["instr"], r["field"], r["arm"], r["carrier"])
            d[key][(r.get("byte_index"), r["value"])] = r
        return d

    IA, IB = index(runA, A), index(runB, B)

    # Two ladder steps are DIAGNOSTIC, not detection-power steps, and both were declared so
    # in harness/casematrix.py BEFORE the run (that file is hashed in CAPTURE_CONTRACT.json):
    #   __ladder_L_srcB_desc_samelen -- "isolates the operand half of an overloaded byte";
    #       its non-movement is the finding that byte+4 is a PURE LENGTH SELECTOR.
    #   __ladder_L_ext_b9 -- "If it does not move, that is evidence FOR the over-consumption,
    #       not against detection power."
    # They are reported, and they are excluded from gate_ladder.
    DIAGNOSTIC = ("__ladder_L_srcB_desc_samelen", "__ladder_L_ext_b9")

    def instrument(run, recs, arm, carrier):
        sel = [r for r in recs if r["arm"] == arm and r["carrier"] == carrier
               and (r["field"].startswith("__ladder_") or r["field"].startswith("__falsifier_"))]
        det = {r["field"]: {"outcome": r["outcome"], "match": r["match"],
                            "diagnostic": r["field"] in DIAGNOSTIC,
                            "pass": (r["match"] is False and
                                     r["outcome"] not in NON_OBSERVATIONS)}
               for r in sel}
        core = [v for k, v in det.items() if k not in DIAGNOSTIC]
        return det, (bool(core) and all(v["pass"] for v in core))

    out, repro = {}, {}
    keys = sorted(set(IA) | set(IB))
    per_field = defaultdict(list)
    for (instr, field, arm, carrier) in keys:
        a, b = IA.get((instr, field, arm, carrier), {}), IB.get((instr, field, arm, carrier), {})
        common = sorted(set(a) & set(b))
        anchor_blk = bytes.fromhex(next(iter(a.values()))["anchor"]) if a else None
        anchor_tok = None
        akey = (runA, arm, carrier)
        if akey in anchors:
            anchor_tok = anchors[akey].get("tok_instr")
        alen = hw_len(lm, anchor_blk, None) if anchor_blk else None

        # Is this arm's byte+2 actually covered by the measured LEN map? If not, its
        # identity exclusions come only from OUR TOKENIZER failing to length the block,
        # which is a weaker (and smaller) exclusion than the hardware-measured one. Both
        # are reported; the hardware-covered arms are the defensible number.
        lenmap_covered = anchor_blk is not None and any(k[0] == anchor_blk[2] for k in lm)
        agree = moved = disagree = identity_excluded = 0
        excluded_vals, seen_bytes, dispatched = [], set(), 0
        for k in common:
            ra, rb = a[k], b[k]
            if ra["outcome"] in NON_OBSERVATIONS or rb["outcome"] in NON_OBSERVATIONS:
                continue
            blk = bytes.fromhex(ra["bytes"])
            same_id = (ra.get("tok_instr") == rb.get("tok_instr")
                       and (alen is None or hw_len(lm, blk, alen) == alen)
                       and (anchor_tok is None or ra.get("tok_instr") == anchor_tok))
            dispatched += 1
            seen_bytes.add(ra["bytes"])
            if digest(ra["observed"]) == digest(rb["observed"]):
                agree += 1
            else:
                disagree += 1
            if not same_id:
                identity_excluded += 1
                excluded_vals.append(k[1])
                continue
            if ra["match"] is False and rb["match"] is False:
                moved += 1
        pct = (100.0 * agree / dispatched) if dispatched else 0.0
        det, lad_pass = instrument(runA, A, arm, carrier)
        detB, lad_passB = instrument(runB, B, arm, carrier)
        per_field["%s.%s" % (instr, field)].append({
            "arm": arm, "carrier": carrier, "values_dispatched": dispatched,
            "distinct_bytes": len(seen_bytes), "agree": agree, "agree_pct": round(pct, 3),
            "disagreements": disagree, "moved": moved,
            "identity_excluded": identity_excluded, "identity_excluded_values": excluded_vals[:64],
            "ladder": det, "ladder_pass": bool(lad_pass and lad_passB),
            "anchor_hw_len": alen, "lenmap_covered": lenmap_covered,
            "measured_range_this_arm": dispatched - identity_excluded,
            "gate_stable": pct >= MIN_AGREE_PCT,
            "gate_live": moved > 0 and moved >= MOVED_OVER_DISAGREE * max(disagree, 1) / 1.0
            if disagree else moved > 0,
        })

    db = json.loads((EXP / "work" / "frozen" / "db.json").read_text())
    INS = {i["mnemonic"]: i for i in db["instructions"]}
    for key, arms in sorted(per_field.items()):
        mn, fn = key.split(".", 1)
        f = next(x for x in INS[mn]["fields"] if x["name"] == fn)
        enc = 1 << f["width"]
        good = [x for x in arms if x["ladder_pass"]]
        live = [x for x in good if x["gate_stable"] and x["gate_live"]]
        inert = [x for x in good if x["gate_stable"] and x["moved"] == 0]
        measured = max((x["values_dispatched"] - x["identity_excluded"]) for x in arms) if arms else 0
        cov_arms = [x for x in arms if x.get("lenmap_covered")]
        measured_lm = (max(x["measured_range_this_arm"] for x in cov_arms) if cov_arms else None)
        cov = 100.0 * measured / enc if enc else 0.0
        expr = EXPRESSIVE.get(key, "NO")

        if not good:
            vclass, label = "NO-DETECTION-POWER", "untested"
        elif expr == "NOT-A-FIELD":
            vclass, label = "NOT-A-FIELD", "untested"
        elif live:
            full = cov >= 99.999 and len(live) >= 2
            vclass = "LIVE-FULL" if full else "LIVE-PARTIAL"
            label = "hardware-run" if full else "isolated-byte-diff"
        elif inert and len(inert) >= 2:
            if expr == "YES":
                vclass, label = "INERT-MULTI", "hardware-run"
            else:
                vclass, label = "INERT-NOT-EXPRESSIBLE", "corpus-correlation"
        elif inert:
            vclass, label = "INERT-SINGLE", "untested"
        elif any(not x["gate_stable"] for x in good):
            vclass, label = "UNSTABLE", "untested"
        else:
            vclass, label = "NO-DETECTION-POWER", "untested"

        out[key] = {
            "label": label, "verdict_class": vclass, "target": "G17P",
            "evidence": ["EXP-0180"], "arms": arms,
            "start": f["start"], "width": f["width"], "encodable_range": enc,
            "values_dispatched": max((x["values_dispatched"] for x in arms), default=0),
            "distinct_bytes": max((x["distinct_bytes"] for x in arms), default=0),
            "measured_encodable_range": measured,
            "measured_encodable_range_lenmap": measured_lm,
            "coverage_pct": round(cov, 3),
            "coverage_pct_lenmap": (round(100.0 * measured_lm / enc, 3)
                                    if measured_lm is not None and enc else None),
            "thin": measured < 8, "under_covered": any(
                x["distinct_bytes"] < x["values_dispatched"] for x in arms),
            "n_carriers": len({x["carrier"] for x in good}),
            "expressiveness": expr,
            "range": "%d of %d encodable values after gate_identity (%0.1f%%), %d distinct "
                     "encodings, %d ladder-passing carriers"
                     % (measured, enc, cov, max((x["distinct_bytes"] for x in arms), default=0),
                        len({x["carrier"] for x in good})),
        }

    (EXP / "analysis" / "field_verdicts.json").write_text(
        json.dumps(out, indent=1, sort_keys=True))
    print(json.dumps({"rows": len(out),
                      "by_class": {k: sum(1 for v in out.values() if v["verdict_class"] == k)
                                   for k in {v["verdict_class"] for v in out.values()}},
                      "len_map_entries": len(lm), "len_zero_point": (zeroA, zeroB)},
                     indent=1, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
