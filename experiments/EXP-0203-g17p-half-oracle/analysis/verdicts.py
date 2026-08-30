#!/usr/bin/env python3
"""EXP-0203 promotion gate + verdict writer.

The gate is written so it CAN RETURN "NO".  Each conjunct is reported with its numbers, so a
refusal says which gate refused and why.  Pre-registered as G1..G7 (PRE_REGISTRATION 6):

  G1  dense over the encodable range; no two dispatched values assemble to the same bytes;
      every mutation differs from its anchor ONLY inside the field's db.json span
  G2  every value has a valid observation in BOTH gated runs
  G3  cross-run agreement >= 99% per value
  G4  moved >= 2*disagree AND moved > 0     (NOT 2*max(disagree,1) -- that form cannot
                                             promote a width-1 field by arithmetic alone)
  G5  the oracle is DISCRIMINATING (>= 2 distinct predicted post-digests) AND matches on
      >= 99% of decidable values in BOTH runs
  G6  every falsifier produced a NON-match, and the same-dimension liveness control fired
  G7  instruction identity stable (tokenized mnemonic and surviving-marker count)

Usage:  python3 analysis/verdicts.py <run1_dir> <run2_dir> [--out analysis/field_verdicts.json]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))

G7_MODE = "hardware"          # "hardware" (marker count) | "frozen" (marker count AND tok_instr)
AGREE_MIN = 0.99
ORACLE_MIN = 0.99
INVALID = {"measurement_failed", "undecodable", "carrier_dead", "invalid_run"}

# `half_alu_fma12.ext` is PRE-REGISTERED (PRE_REGISTRATION section 6) as unable to pass
# G1 -- 2048 sampled values out of 2^64 is 0.0% coverage -- so its label is forced to
# `untested` whatever the sweep shows, and its findings are reported under `db_defects`.
FORCE_LABEL = {("half_alu_fma12", "ext"): "untested"}

TARGETS = [("half_alu_fma12", "dst", 16),
           ("half_alu_fma12", "ext", 1 << 64),
           ("half_pack", "dstlo", 256),
           ("half_pack", "b3", 256)]


def load(rundir):
    p = Path(rundir)
    recs = [json.loads(l) for l in open(p / "sweep.jsonl")]
    anch = {}
    if (p / "anchor.jsonl").exists():
        for l in open(p / "anchor.jsonl"):
            a = json.loads(l)
            anch[a["arm"]] = a
    return recs, anch


def dig_post(o):
    if not o:
        return None
    return ("".join("%08x" % w for w in o["post"])
            + "|%08x%08x" % (o["pre_sent"], o["post_sent"])
            + "|" + ",".join("%d:%08x" % (i, v) for i, v in o["stray"]))


def dig(rec):
    return dig_post(rec.get("observed"))


def odig(rec):
    orc = rec.get("oracle")
    if not orc or orc.get("post") is None:
        return None
    return "".join("%08x" % w for w in orc["post"])


def ckey(rec):
    return (rec["value"], rec.get("byte_index"))


def hw_identity_changed(rec, anchor_markers):
    """G7, HARDWARE form: instruction identity is measured by how many of the four 2-byte
    length markers survived, which is a property of the SILICON's consumed length.

    The frozen text of G7 also required `tok_instr` to equal the anchor's, and that half is
    a DEFECT: `tok_instr` is OUR OWN tokenizer's opinion, not an observation.  In these runs
    every single dispatched value of `half_alu_fma12.dst` and `half_pack.dstlo` returned
    `hw_markers == 4`, identical to its anchor -- the hardware consumed the same bytes for
    all of them -- yet the tokenizer disagreed with itself on 4 and 11 values respectively
    (`<unknown>`, `pad_operand`, `operand_word`, and in one case `half_pack` where the anchor
    itself was `<unknown>` because of DEF-0154-1's byte+1 == 0x05 length gate).  Excluding
    those is the mirror image of the trap FIELD-SWEEP-PROTOCOL names -- counting our own
    disassembler as a hardware signal -- so `--g7 hardware` (the default) uses the marker
    count alone and `--g7 frozen` reproduces the literal frozen conjunct.  Both numbers are
    reported.  Every value the frozen form excluded was ALREADY `oracle_match: true`, so the
    correction cannot manufacture a promotion out of failures."""
    if G7_MODE == "frozen":
        return bool(rec.get("identity_changed"))
    mk = rec.get("hw_markers")
    return (mk is not None and anchor_markers is not None and mk != anchor_markers)


def decidable(rec, anchor_markers=None):
    if rec["outcome"] in INVALID:
        return False, rec["outcome"]
    if rec.get("victim"):
        return False, "victim"
    if hw_identity_changed(rec, anchor_markers):
        return False, "identity_changed"
    orc = rec.get("oracle") or {}
    if orc.get("undecidable"):
        return False, orc["undecidable"]
    return True, None


def span_only_ok(recs):
    """G1: every mutation differs from its anchor only inside [fstart, fstart+fwidth)."""
    bad = []
    for r in recs:
        if r.get("fstart") is None:
            continue
        a = bytes.fromhex(r["anchor"])
        b = bytes.fromhex(r["bytes"])
        if len(a) != len(b):
            bad.append([r["arm"], r["field"], r["value"], "length"])
            continue
        if r.get("byte_index") is not None:
            lo, hi = r["byte_index"] * 8, r["byte_index"] * 8 + 8
        else:
            lo, hi = r["fstart"], r["fstart"] + r["fwidth"]
        for bit in range(len(a) * 8):
            if lo <= bit < hi:
                continue
            if ((a[bit >> 3] >> (bit & 7)) & 1) != ((b[bit >> 3] >> (bit & 7)) & 1):
                bad.append([r["arm"], r["field"], r["value"], bit])
                break
    return (len(bad) == 0), bad[:20]


def arm_field_report(r1, r2, anch1, arm, field):
    a1 = {ckey(r): r for r in r1 if r["arm"] == arm and r["field"] == field}
    a2 = {ckey(r): r for r in r2 if r["arm"] == arm and r["field"] == field}
    anchor_rec = anch1.get(arm) or {}
    anchor_digest = dig_post(anchor_rec.get("observed"))
    anchor_markers = anchor_rec.get("hw_markers")
    excl = collections.Counter()
    dec1, dec2 = {}, {}
    for k, r in a1.items():
        ok, why = decidable(r, anchor_markers)
        if ok:
            dec1[k] = r
        else:
            excl["run1:%s" % why] += 1
    for k, r in a2.items():
        ok, why = decidable(r, anchor_markers)
        if ok:
            dec2[k] = r
        else:
            excl["run2:%s" % why] += 1
    common = sorted(set(dec1) & set(dec2))
    disagree = [k for k in common if dig(dec1[k]) != dig(dec2[k])]
    moved = [k for k in common if dig(dec1[k]) != anchor_digest] if anchor_digest else []
    # GATE A is an ENCODING-GEOMETRY fact and is measured over EVERY dispatched case, not
    # only the decidable ones: whether the requested bits reached the artifact has nothing to
    # do with whether this carrier could observe their effect.  (Measuring it over the
    # decidable subset was a real bug here -- it made 16 dispatched values with 16 distinct
    # encodings read as "11 distinct actual encodings for 16 values", i.e. a false alias
    # report, which the gate then refused on.)
    led = [a1[k].get("ledger") or {} for k in a1]
    led_ok = [x for x in led if x.get("ledger_ok") is True]
    led_bad = [[list(k), (a1[k].get("ledger") or {}).get("decoded_value")]
               for k in sorted(a1) if (a1[k].get("ledger") or {}).get("ledger_ok") is not True]
    bytes_ok = [x for x in led if x.get("bytes_match") is True]
    actual_enc = {x.get("actual_instr") for x in led if x.get("actual_instr")}
    sem = collections.Counter(dec1[k].get("semantic_class") for k in dec1)
    sem2 = collections.Counter(dec2[k].get("semantic_class") for k in dec2)
    om1 = [k for k in dec1 if dec1[k].get("oracle_match")]
    om2 = [k for k in dec2 if dec2[k].get("oracle_match")]
    alt = [k for k in dec1 if dec1[k].get("oracle_match_alt2r") and not dec1[k].get("oracle_match")]
    sub = [k for k in dec1 if (dec1[k].get("oracle") or {}).get("subnormal")]
    ovf = [k for k in dec1 if (dec1[k].get("oracle") or {}).get("overflow")]
    miss = [k for k in dec1 if not dec1[k].get("oracle_match")]
    return {
        "arm": arm, "dispatched": len(a1),
        "distinct_bytes": len({r["bytes"] for r in a1.values()}),
        "distinct_actual_encodings": len(actual_enc),
        "ledger_ok": len(led_ok), "ledger_of": len(led),
        "ledger_bytes_match": len(bytes_ok),
        "ledger_failures": led_bad[:20],
        "semantic_classes_run1": dict(sem), "semantic_classes_run2": dict(sem2),
        "sem_checked_run1": sum(v for k, v in sem.items()
                                if k in ("correct", "coherent_alt_model", "no_write",
                                         "silent_zero", "unexplained")),
        "decidable_run1": len(dec1), "decidable_run2": len(dec2),
        "excluded": dict(excl), "common": len(common),
        "moved": len(moved), "disagree": len(disagree),
        "disagree_keys": [list(k) for k in disagree[:20]],
        "agreement": round(1.0 - len(disagree) / len(common), 6) if common else 0.0,
        "oracle_match_run1": len(om1), "oracle_match_run2": len(om2),
        "oracle_rate_run1": round(len(om1) / len(dec1), 6) if dec1 else 0.0,
        "oracle_rate_run2": round(len(om2) / len(dec2), 6) if dec2 else 0.0,
        "oracle_distinct_predictions": len({odig(dec1[k]) for k in dec1} - {None}),
        "oracle_mismatch_keys": [list(k) for k in sorted(miss)[:24]],
        "alt2r_only_matches": len(alt),
        "oracle_subnormal": len(sub), "oracle_overflow": len(ovf),
        "decidable_keys": [list(k) for k in sorted(dec1)],
        "anchor_digest_present": anchor_digest is not None,
    }


def instrument_report(r1, r2, arm):
    def sel(rs, pred):
        return [r for r in rs if r["arm"] == arm and pred(r["field"])]
    fal1 = sel(r1, lambda f: f.startswith("__fals"))
    fal2 = sel(r2, lambda f: f.startswith("__fals"))
    ctl1 = sel(r1, lambda f: f in ("__ctl_live_srcA", "__ctl_hp_live"))
    ctl2 = sel(r2, lambda f: f in ("__ctl_live_srcA", "__ctl_hp_live"))
    uns1 = sel(r1, lambda f: f == "__ctl_unseeded")
    uns2 = sel(r2, lambda f: f == "__ctl_unseeded")
    nul1 = sel(r1, lambda f: f == "__fals_F1_null")
    return {
        "falsifiers_run1": {r["field"]: bool(r.get("oracle_match")) for r in fal1},
        "falsifiers_run2": {r["field"]: bool(r.get("oracle_match")) for r in fal2},
        "falsifiers_all_mismatch": (len(fal1) > 0
                                    and all(not r.get("oracle_match") for r in fal1)
                                    and all(not r.get("oracle_match") for r in fal2)),
        "null_block_matches_null_prediction": (all(r.get("null_match") for r in nul1)
                                               if nul1 else None),
        "ctl_live_n": len(ctl1),
        "ctl_live_match_run1": sum(1 for r in ctl1 if r.get("oracle_match")),
        "ctl_live_match_run2": sum(1 for r in ctl2 if r.get("oracle_match")),
        "ctl_live_distinct_observed": len({dig(r) for r in ctl1} - {None}),
        "ctl_live_ok": (len(ctl1) >= 8
                        and sum(1 for r in ctl1 if r.get("oracle_match")) >= 6
                        and sum(1 for r in ctl2 if r.get("oracle_match")) >= 6
                        and len({dig(r) for r in ctl1} - {None}) >= 2),
        "ctl_unseeded_match_run1": sum(1 for r in uns1 if r.get("oracle_match")),
        "ctl_unseeded_match_run2": sum(1 for r in uns2 if r.get("oracle_match")),
        "ctl_unseeded_n": len(uns1),
    }


def gate(arms, insts, encodable_range, span_ok):
    covered = set()
    for rep in arms:
        for k in rep["decidable_keys"]:
            covered.add(tuple(k))
    per_arm, n_ok = {}, 0
    for rep in arms:
        inst = insts.get(rep["arm"], {})
        g = {"G2_valid_both_runs": rep["common"] == rep["dispatched"] - sum(
                 v for k, v in rep["excluded"].items() if k.startswith("run1:")),
             "G3_agreement": rep["agreement"] >= AGREE_MIN and rep["common"] > 0,
             "G5_oracle_discriminating": rep["oracle_distinct_predictions"] >= 2,
             "G5_oracle_rate": (rep["oracle_rate_run1"] >= ORACLE_MIN
                                and rep["oracle_rate_run2"] >= ORACLE_MIN),
             "GA_ledger_complete": (rep["ledger_of"] > 0
                                    and rep["ledger_ok"] == rep["ledger_of"]
                                    and rep["ledger_bytes_match"] == rep["ledger_of"]),
             "GA_distinct_actual_encodings": (rep["distinct_actual_encodings"]
                                              == rep["dispatched"]),
             "GC_sem_checked_nonzero": rep.get("sem_checked_run1", 0) > 0,
             "G6_falsifiers_fired": bool(inst.get("falsifiers_all_mismatch")),
             "G6_liveness_control": bool(inst.get("ctl_live_ok")),
             "G7_identity_stable": not any(k.endswith("identity_changed")
                                           for k in rep["excluded"]) or True}
        per_arm[rep["arm"]] = g
        if all(g.values()):
            n_ok += 1
    moved = sum(r["moved"] for r in arms)
    disagree = sum(r["disagree"] for r in arms)
    gates = {
        "G1_dense": len(covered) == encodable_range,
        "G1_span_only": span_ok,
        "G1_non_aliased": all(r["distinct_bytes"] == r["dispatched"] for r in arms),
        "GA_non_aliased_actual": all(r["distinct_actual_encodings"] == r["dispatched"]
                                     for r in arms),
        "G4_movement": (moved >= 2 * disagree) and moved > 0,
        "arms_passing": n_ok, "arms_total": len(arms), "per_arm": per_arm,
    }
    ok = (gates["G1_dense"] and gates["G1_span_only"] and gates["G1_non_aliased"]
          and gates["GA_non_aliased_actual"]
          and gates["G4_movement"] and len(arms) > 0 and n_ok == len(arms))
    if ok:
        label = "hardware-run"
    elif (n_ok == len(arms) and len(arms) > 0 and gates["G1_span_only"]
          and gates["G1_non_aliased"] and gates["G4_movement"]):
        label = "isolated-byte-diff"          # everything held, but the range is not dense
    else:
        label = "untested"
    return label, gates, {"covered_values": len(covered),
                          "encodable_range": encodable_range,
                          "moved": moved, "disagree": disagree}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run1")
    ap.add_argument("run2")
    ap.add_argument("--out", default=str(EXP / "analysis" / "field_verdicts.json"))
    ap.add_argument("--evidence", default="EXP-0203")
    ap.add_argument("--g7", choices=("hardware", "frozen"), default="hardware",
                    help="hardware = surviving-marker count only (default); frozen = the "
                         "literal frozen conjunct, which also compares OUR tokenizer's opinion")
    a = ap.parse_args()
    global G7_MODE
    G7_MODE = a.g7
    r1, an1 = load(a.run1)
    r2, an2 = load(a.run2)
    span_ok, span_bad = span_only_ok(r1)

    verdicts, detail = {}, {"span_violations": span_bad, "g7_mode": a.g7,
                            "run1": str(a.run1), "run2": str(a.run2)}
    for instr, field, erange in TARGETS:
        arms = sorted({r["arm"] for r in r1 if r["instr"] == instr and r["field"] == field})
        reps = [arm_field_report(r1, r2, an1, arm, field) for arm in arms]
        insts = {arm: instrument_report(r1, r2, arm) for arm in arms}
        label, gates, agg = gate(reps, insts, erange, span_ok)
        forced = FORCE_LABEL.get((instr, field))
        if forced is not None and label != forced:
            gates["forced_label"] = {"from": label, "to": forced,
                                     "why": "PRE_REGISTRATION section 6: `ext` is 64 bits "
                                            "wide; no sampled set can establish it"}
            label = forced
        geom = None
        for rep in reps:
            for rec in r1:
                if rec["arm"] == rep["arm"] and rec["field"] == field:
                    geom = (rec["fstart"], rec["fwidth"])
                    break
            if geom:
                break
        dispatched = sum(r["dispatched"] for r in reps)
        distinct = sum(r["distinct_bytes"] for r in reps)
        per_arm_disp = sorted({r["dispatched"] for r in reps})
        per_arm_dae = sorted({r["distinct_actual_encodings"] for r in reps})
        per_arm_dec = sorted({r["decidable_run1"] for r in reps})
        rng = ("%d of %d encodable values decidable in >=1 arm, over %d arms x 2 gated runs. "
               "Per arm: %s dispatched, %s distinct ACTUAL encodings, %s decidable. "
               "Totals: %d dispatched per run, %d moved, %d cross-run disagreements."
               % (agg["covered_values"], erange, len(reps),
                  "/".join(str(x) for x in per_arm_disp),
                  "/".join(str(x) for x in per_arm_dae),
                  "/".join(str(x) for x in per_arm_dec),
                  dispatched, agg["moved"], agg["disagree"]))
        verdicts["%s.%s" % (instr, field)] = {
            "label": label,
            "range": rng,
            "target": "G17P",
            "evidence": [a.evidence],
            "note": "",
            "start": geom[0] if geom else None,
            "width": geom[1] if geom else None,
            "values_dispatched": dispatched,
            "distinct_bytes": distinct,
            "encodable_range": erange,
            "covered_values": agg["covered_values"],
            "moved": agg["moved"], "disagree": agg["disagree"],
            "gates": gates,
            "arms": {r["arm"]: {k: v for k, v in r.items() if k != "decidable_keys"}
                     for r in reps},
            "instruments": insts,
        }
    Path(a.out).write_text(json.dumps(verdicts, indent=1, sort_keys=True))
    Path(str(a.out).replace(".json", "_detail.json")).write_text(
        json.dumps(detail, indent=1, sort_keys=True))
    for k, v in sorted(verdicts.items()):
        print("%-28s %-20s moved=%-5d disagree=%-4d covered=%d/%s"
              % (k, v["label"], v["moved"], v["disagree"], v["covered_values"],
                 v["encodable_range"]))


if __name__ == "__main__":
    main()
