#!/usr/bin/env python3
"""EXP-0166 stage 3 — write the three deliverables plus the disposition map and H3 evidence.

  python3 analysis/emit_deliverables.py

Writes, in this directory only:
  field_verdicts.json        merge-ready survivors, flat <mnemonic>.<field>
  withheld.json              every rejected key with reason and numbers
  proposed_db_defects.json   descriptor defects with evidence (§4 of the dispatch)
  exp0146_disposition.json   all 94 original EXP-0146 verdict keys -> disposition
  h3_srcB_ext.json           the H3 / F3 test on iadd2.srcB_ext
"""
import collections
import json
import os

import adjudicate as A
import verdicts as V

HERE = A.HERE

# A6/A7 downgrade rules -------------------------------------------------------
WIDE_CAP = {"irotate.operands", "irotate.tail", "n2_op8.body", "n2_op10.immword"}   # A6
REG_TYPED_CAP = set()      # A7, filled from db.json below


def hexset(vals, limit=24):
    if len(vals) > limit:
        return "{%s, ...(%d total)}" % (", ".join(hex(v) for v in vals[:limit]), len(vals))
    return "{%s}" % ", ".join(hex(v) for v in vals)


def h3_test():
    """H3 / F3: are iadd2.srcB_ext's 'forbidden' bits 2..6 a source-register selector?"""
    runs = {r: A.load_jsonl(os.path.join(A.SRC, "raw", r, "sweep.jsonl")) for r in A.GATED_RUNS}
    idx = {}
    for r, recs in runs.items():
        for rec in recs:
            v = rec.get("value")
            if rec.get("instr") == "iadd2" and rec.get("field") == "srcB_ext" \
               and not isinstance(v, (list, dict)):
                idx[(r, v)] = rec
    groups = collections.defaultdict(set)
    agreeing = 0
    for v in range(128):
        r1 = idx.get((A.GATED_RUNS[0], v))
        r3 = idx.get((A.GATED_RUNS[1], v))
        if not (r1 and r3):
            continue
        o1, o3 = A.observable(r1), A.observable(r3)
        if o1 != o3:
            continue
        agreeing += 1
        groups[v >> 2].add(o3)
    single = {k: list(s)[0] for k, s in groups.items() if len(s) == 1}
    obs_by_group = {str(k): {"outcome": o[0], "words": list(o[1])} for k, o in sorted(single.items())}
    distinct = len({(o[0], o[1]) for o in single.values()})
    return {
        "hypothesis": "H3 — iadd2.srcB_ext bits 2..6 are the srcA REGISTER selector (reg<<2), "
                      "not a modifier constraint (v & 0x7C) == 0x00",
        "method": "Group the 128 cross-run-agreeing srcB_ext values by v>>2 and ask whether each "
                  "group of 4 (the two free low bits) collapses to ONE observable. If bits 2..6 "
                  "select a register, every group must be internally identical.",
        "target": "M4/G16G (EXP-0146 raw run01+run03)",
        "values_cross_run_agreeing": agreeing,
        "groups_of_four": len(groups),
        "groups_with_a_single_observable": len(single),
        "distinct_observables_across_groups": distinct,
        "result": "CONFIRMED — 32/32 groups collapse to exactly one observable, so the low two bits "
                  "of srcB_ext are don't-care and bits 2..6 are the discriminator, exactly the "
                  "reg<<2 packing EXP-0154 proved independently on G17P (DEF-0154-4). Only 6 "
                  "distinct observables appear across the 32 indices and groups 6..31 are all "
                  "identical, so the carrier only distinguishes the handful of registers it "
                  "actually loaded — the packing is established, the per-register map is NOT.",
        "falsifier_F3": "did NOT fire (F3 would have required the excluded values to be "
                        "inexplicable as a different source-register selection)",
        "consequence": "EXP-0146's published rule `(v & 0x7C) == 0x00` is a carrier artefact "
                       "meaning 'srcA must be r0'. Shipped as a modifier constraint it would tell "
                       "an emitter that bits 2..6 must be zero, when those bits are how a register "
                       "is chosen. The row is VETOED from merge (G3).",
        "observables_by_group": obs_by_group,
    }


def main():
    merged, withheld, arms, decomposed, comp, dbf, dbi, val, flaked = V.main()

    # A7: which db.json fields are typed `reg`
    for m, inst in dbi.items():
        for f in inst.get("fields", []):
            if f.get("type") == "reg":
                REG_TYPED_CAP.add("%s.%s" % (m, f["name"]))

    st = arms
    dec = decomposed

    def best_of(key):
        return merged[key]["_stats"]["chosen"]

    # ------------------------------------------------------------------ rows
    NOTES = {
        "iadd2.opc_tail": (
            "64-bit form only, carrier `k_u64sub` (`1f 01 56 00 02 08 00 50 17 05`). Dense 0..255, "
            "both gated runs agreeing on every value. Accept-set is exactly the 64 values with "
            "(v & 0x11) == 0x11; the other 192 give 16 silent zeros and 176 wrong values. This is "
            "a SECOND carrier for a field EXP-0139 established on the 32-bit form, and the "
            "accept-set is carrier-scoped: do not read it as a global rule."),
        "iadd2.opc_tail2": (
            "64-bit form only, carrier `k_u64sub`. Dense 0..255, both gated runs agreeing on every "
            "value. Accept-set is exactly the 64 values with (v & 0x05) == 0x05; the other 192 all "
            "return a wrong value (no silent zeros). Second carrier for EXP-0139's 32-bit result; "
            "the accept-set is carrier-scoped."),
        "ilogic.lut_a_z": (
            "Recovered by decomposing EXP-0146's dense byte+4 sweep (A5): the 8 sub-values of bits "
            "37-39 with every other bit of byte+4 at its compiled value. Only 0 reproduces; all 7 "
            "non-zero values break the carrier. This is the sweep `validation.json` says is "
            "needed ('lut_a_z is untouched ... needs a sweep over the full byte+4 domain') — "
            "EXP-0154's G17P arm only reached lut_a 0..15 = bits 32-35. NOTE: 'must be clear' and "
            "'selects something this carrier cannot observe' are not distinguished; the emitter "
            "guidance is the same either way — emit 0. SISTER FIELD STILL OPEN: `lut_a_free` is "
            "dense-INERT 8/8 here but on ONE carrier, so it stays withheld and `ilogic` remains "
            "not-yet-emittable on that one field."),
        "iadd2.addsub": (
            "byte0 bit 7, the ADD/SUBTRACT selector, in the 64-bit carrier `k_u64sub` "
            "(`1f 01 56 00 02 08 00 50 17 05`). Both values of a 1-bit field executed: 0 reproduces "
            "the compiled 64-bit SUBTRACT, 1 produces (a + b) mod 2^64 EXACTLY on all 8 frozen "
            "rows including full 64-bit wrap and lo->hi carry, matched against a host-computed "
            "oracle. This is the encoding behind EXP-0146's headline (a native single-instruction "
            "64-bit integer ADD the Apple compiler never emits). REVALIDATED ON G17P by EXP-0153 "
            "(12 rows x 5 repetitions x 2 gated runs) — cited, not merged; this row is the M4 half. "
            "The field currently reads `untested` because EXP-0164's audit bucketed it INERT-SINGLE "
            "with `max_values_dispatched: 5`; a 1-bit field has only 2 values and both moved."),
        "iadd2.srcB_imm": (
            "64-bit form, carrier `k_u64sub`. Dense 0..255, both gated runs agreeing on every "
            "value. Accept-set {0x08,0x09,0x0a,0x0b} = (v & 0xFC) == 0x08 — the low two bits are "
            "free; 4 values silently zero and 248 return a wrong value. Consistent with EXP-0139's "
            "32-bit-form model of a 9-bit immediate stored (K<<1) at b5 + b6bit0. "
            "⚠ Carrier-scoped: this carrier's srcB is a REGISTER, so the accept-set is 'the "
            "descriptor bits that keep this operand', not the immediate's legal range."),
        "iadd2.srcB_reg_hi": (
            "64-bit form, carrier `k_u64sub`. Dense 0..127 (7-bit field), both gated runs agreeing "
            "on every value. Exactly the 64 EVEN values reproduce and the 64 odd ones return a "
            "wrong value — i.e. only bit 0 of the field is live and it must be clear; bits 1..6 "
            "are HW-tested free across all 64 combinations. Reproduces EXP-0139's 32-bit-form "
            "finding on a second, structurally different carrier."),
        "ilogic.lut_a_sel": (
            "A5-decomposed from EXP-0146's dense byte+4 sweep: the 4 sub-values of bits 32-33 with "
            "every other bit of byte+4 at its compiled value. All 4 executed; only 0 reproduces "
            "the carrier's AND, and the other 3 select DIFFERENT boolean functions (that is the "
            "field's job — see EXP-0146's 16-function LUT table). Currently `untested` because "
            "EXP-0154's G17P sweep was orphaned by the concurrent lut_a split and then withdrawn. "
            "⚠ OPERAND-LABEL TRAP (EXP-0154 DEF-0154-5): the published LUT table's `a`/`b` are "
            "SWAPPED relative to db.json's `srcA`/`srcB`; that affects which function a selector "
            "value names, not this field's liveness."),
        "irotate.operands": (
            "⚠ MARGINAL COVERAGE ONLY. 40-bit raw field swept BYTE-WISE — each of bytes +3..+7 over "
            "all 256 values with the other four at their compiled value (1280 of 2^40 combinations). "
            "No joint value, and neither `max` nor `max-1` of the 40-bit field was ever encoded, so "
            "FIELD-SWEEP-PROTOCOL §3.3's coverage bar for w>8 is NOT met — hence "
            "`isolated-byte-diff`, not `hardware-run` (A6). Per-byte accept-sets (M4): "
            "+3 {0x00,0x01}; +4 (v&0x02)==0x02; +5 (v&0xfc)==0x00; +6 {0x6c,0x6e}; "
            "+7 (v&0xf1)==0x00. The ROTATE AMOUNT is NOT independently emittable from this carrier "
            "(+6 admits only two values). ⚠ SAFETY: EXP-0154 reports byte+7 = 231/232 GENUINELY "
            "HANGS the GPU on G17P (kIOGPUCommandBufferCallbackErrorHang, contained, majority-of-3). "
            "EXP-0154 left byte+7 `untested` on G17P; this M4 row is the only evidence there is."),
        "irotate.tail": (
            "⚠ MARGINAL COVERAGE ONLY. 32-bit raw field swept BYTE-WISE — bytes +8..+11, each over "
            "all 256 values with the others at their compiled value (1024 of 2^32 combinations); "
            "neither `max` nor `max-1` was encoded, so §3.3's w>8 bar is not met (A6). Per-byte "
            "accept-sets (M4): +8 (v&0xb7)==0xb0; +9 (v&0x12)==0x10; +10 (v&0xfd)==0x09; "
            "+11 (v&0x01)==0x00. EXP-0154 left +8 and +10 `untested` on G17P; this M4 row is the "
            "only evidence for them."),
        "n2_op10.dst": (
            "Dense 0..15. Only 0x3 — the carrier's own compiled value — reproduces; the other 15 "
            "give 14 wrong values and 1 silent zero, both gated runs agreeing on every value. "
            "CAPPED at isolated-byte-diff by A7: `dst` is typed `reg`, and a singleton accept-set "
            "establishes 'every other value breaks this carrier', NOT 'value N selects register N'. "
            "A register-granularity carrier (16-register dump) is required before an emitter may "
            "choose a destination through this field. `n2_op10` has 230 live occurrences on G17P "
            "(EXP-0157 census), so a G17P re-sweep is strictly better than this row."),
        "n2_op8.opsel": (
            "Dense 0..255, 254 comparable (2 innocent-victim), one value (0x87) disagreed across "
            "the gated runs. Accept-set is the singleton {0x49}: 91 silent zeros, 152 wrong values, "
            "10 faults. ⚠ TARGET NOTE: `n2_op8` has NO CARRIER ON G17P — EXP-0157 found zero "
            "occurrences across 59 own-MSL programs in two provocation rounds, including 20 "
            "SFU-family programs. This M4/G16G row is the only hardware evidence for the field and "
            "G17P can neither confirm nor refute it. Clean-room rule 5 respected: only the "
            "accept/reject envelope is recorded, never the SFU range-reduction recipe."),
        "sfu_marker.b1_hi": (
            "NEW FIELD. EXP-0165 relaxed `sfu_marker`'s match on 2026-08-30 (triage C7b) from two "
            "whole pinned bytes to [0,3,6]+[8,2,2] and split out `b0_hi` (bits 3-7) and `b1_hi` "
            "(bits 10-15); neither has a validation.json entry, which `validate_labels.py` "
            "hard-fails on. This row fills `b1_hi` from evidence that already existed. "
            "A5-decomposed from EXP-0146's dense byte+1 probe: the 64 encodings whose byte+1 low "
            "two bits hold the match value, i.e. every value of the new 6-bit field. Accept-set is "
            "the 32 values with bit 2 of the field (= byte+1 bit 4) CLEAR — exactly EXP-0146's "
            "published byte rule (v & 0x13) == 0x02, restated in the new field's coordinates. "
            "CORROBORATION (not merged, different target): EXP-0157 measured the identical byte "
            "rule on G17P in THREE independent carriers (sfusin/sfucos/sfumix). Its sibling "
            "`b0_hi` is NOT offered — that arm has 19 cross-run fault/silent-zero flips and misses "
            "the 99% bar."),
        "n2_op8.srcA_desc": (
            "Dense 0..255, one value (0x00) disagreed across the gated runs. Accept-set is the "
            "singleton {0xc2}: 224 silent zeros and 31 wrong values. ⚠ Same target note as "
            "`n2_op8.opsel`: no carrier exists on G17P. ⚠ A7-adjacent caution: this is a source "
            "DESCRIPTOR with a singleton accept-set, so it is typed `raw` and escapes A7's literal "
            "scope, but the same limitation applies — 'only 0xc2 works here' is not a source-operand "
            "map. Clean-room rule 5 respected."),
    }

    out = {}
    for key in sorted(merged):
        b = best_of(key)
        label = merged[key]["label"]
        # A6: wide composite. A7: reg-typed field whose accept-set is a singleton.
        if key in WIDE_CAP or (key in REG_TYPED_CAP and b.get("I") == 1):
            label = "isolated-byte-diff"
        w = b["width"]
        if b["source"] == "A1-composite":
            rng = ("BYTE-WISE MARGINAL ONLY: %d constituent bytes x 0..255 dense each "
                   "(%d encodings); the %d-bit field was NEVER swept jointly and its max/max-1 "
                   "were never encoded" % (len(b["per_byte"]), 256 * len(b["per_byte"]), w))
        else:
            rng = ("0..%d dense (%d of %d encodings actually spliced), %d/%d values comparable "
                   "across both gated runs; %d moved the observable, %d reproduced it, %d "
                   "disagreed" % ((1 << w) - 1, b["distinct_encodings"], 1 << w,
                                  b["N"], b["N"] + b["victim_skipped"], b["M"], b["I"], b["D"]))
            if b["I"] and b["I"] <= 24:
                rng += "; accept-set " + hexset(b["inert_values"])
        if b["source"] == "A5-decomposed":
            rng = "A5-DECOMPOSED from EXP-0146 arm(s) %s. " % ",".join(b["decomposed_from"]) + rng
        out[key] = {
            "label": label,
            "range": rng,
            "target": A.TARGET,
            "evidence": A.EVIDENCE,
            "semantics": None,
            "note": NOTES[key],
            "carrier": b["carrier"],
            "counts": {k: b[k] for k in ("N", "D", "M", "I", "agreement",
                                         "distinct_encodings", "victim_skipped")
                       if b.get(k) is not None},
            "supersedes_label": merged[key]["_stats"]["current_label"],
        }
        if b["source"] == "A1-composite":
            out[key]["counts"] = {"per_byte": b["per_byte"]}

    json.dump(out, open(os.path.join(HERE, "field_verdicts.json"), "w"), indent=1, sort_keys=True)
    print("wrote field_verdicts.json — %d merge-ready rows" % len(out))

    # ------------------------------------------------------------------ withheld
    wh = {}
    for k, e in withheld.items():
        b = e["chosen"]
        wh[k] = {
            "reason": e["reason"],
            "current_label": e["current_label"],
            "current_target": e["current_target"],
            "current_evidence": e["current_evidence"],
            "carriers_disagree": e["carriers_disagree"],
            "arms": [{kk: r.get(kk) for kk in
                      ("source", "arm", "carrier", "verdict", "N", "D", "M", "I", "agreement",
                       "distinct_encodings", "dense", "width", "verdict_literal_prereg",
                       "decomposed_from", "per_byte")} for r in e["all_arms"]],
        }
    json.dump(wh, open(os.path.join(HERE, "withheld.json"), "w"), indent=1, sort_keys=True)
    print("wrote withheld.json — %d rejected keys" % len(wh))

    # ------------------------------------------------------------------ H3
    h3 = h3_test()
    json.dump(h3, open(os.path.join(HERE, "h3_srcB_ext.json"), "w"), indent=1, sort_keys=True)
    print("wrote h3_srcB_ext.json — %s" % h3["result"].split(" — ")[0])

    # ------------------------------------------------------------------ db defects
    # D1: fields whose bits a nonzero `match` bit also SETS -> unfillable through isadb.assemble()
    overlaps = []
    for m, inst in sorted(dbi.items()):
        mm = 0
        for s, w, v in inst.get("match", []):
            if v:
                mm |= (v & ((1 << w) - 1)) << s
        for f in inst.get("fields", []):
            fmask = ((1 << f["width"]) - 1) << f["start"]
            ov = mm & fmask
            if ov:
                lost = bin(ov).count("1")
                overlaps.append({"mnemonic": m, "field": f["name"], "start": f["start"],
                                 "width": f["width"], "forced_mask": hex(ov >> f["start"]),
                                 "bits_unfillable": lost,
                                 "reachable_values": (1 << f["width"]) >> lost,
                                 "total_values": 1 << f["width"]})

    demonstrated = []
    for k, s in sorted(st.items()):
        if not s["dense"] and not s["field"].startswith("byte+") and s["match_overlap_mask"]:
            demonstrated.append({"arm": k, "distinct_encodings": s["distinct_encodings"],
                                 "values_dispatched": s["values_dispatched"],
                                 "match_overlap_mask": s["match_overlap_mask"]})

    defects = [
        {
            "id": "DEF-0166-1",
            "title": "53 db.json fields have bits that a nonzero `match` constant also sets — "
                     "unfillable through the DB's own assembler",
            "severity": "emitter-breaking + it silently under-covers sweeps",
            "db_says": "`match` lists constant bits, `fields` lists fillable bits; the two are "
                       "treated as disjoint by every consumer.",
            "hardware_says": "not a hardware claim — this is an internal inconsistency in the "
                             "descriptor, established from the recorded bytes of EXP-0146's own "
                             "sweeps.",
            "mechanism": "tools/agx-isa/isadb.py `assemble()` ORs the match constant, then ORs the "
                         "field values: `v |= value << start` for match, then `v |= val << start` "
                         "for each field. An OR can never CLEAR a bit, so wherever a field overlaps "
                         "a match bit that is SET, that bit is stuck at 1 for every value an "
                         "emitter (or a sweep) supplies.",
            "how_established": "Static scan of the pinned db.json (all 53 cases listed below), plus "
                               "three DEMONSTRATED instances recovered from EXP-0146's raw `bytes`: "
                               "an arm that dispatched 256 values produced far fewer distinct "
                               "encodings.",
            "demonstrated_in_exp0146_raw": demonstrated,
            "worked_example": {
                "arm": "shift_amt_move.kind", "db_match": "[16,4,12] pins byte+2's low nibble to 0xC",
                "db_field": "kind = (start 16, width 8) — the WHOLE of byte+2",
                "observed_bytes": {"v=0": "0b010c05", "v=1": "0b010d05", "v=2": "0b010e05",
                                   "v=3": "0b010f05", "v=4": "0b010c05 (same as v=0)"},
                "consequence": "64 of 256 values reachable; EXP-0146's verdict file claims "
                               "'256 values tested (full 8-bit dense)'."},
            "affects_committed_claims": [
                "EXP-0146 `irotate.b1`: 128 of 256 encodings reachable, claimed dense.",
                "EXP-0146 `irotate.b2`: 32 of 256 encodings reachable, claimed dense.",
                "EXP-0146 `shift_amt_move.kind`: 64 of 256 encodings reachable, claimed dense.",
                "NOT EXP-0154 for `irotate.b1`: its raw shows 256 distinct byte-strings, so its "
                "harness wrote bytes directly rather than through assemble(). Any experiment that "
                "used isadb.assemble() to build sweep cases should be re-checked the same way — "
                "count distinct `bytes` values, do not trust the dispatched-value count."],
            "all_overlaps": overlaps,
            "proposed_fix": "For each row: either narrow the field to the bits the match does not "
                            "pin, or drop the redundant match entry. Both are DECODE changes and "
                            "need the corpus A/B. Independently, `assemble()` should raise when a "
                            "supplied field value's bits are already pinned by `match`, so this "
                            "class of under-coverage becomes an error rather than a silent no-op.",
            "evidence": ["experiments/EXP-0146-m4-emit-int-misc/raw/run01/sweep.jsonl",
                         "experiments/EXP-0146-m4-emit-int-misc/raw/run03/sweep.jsonl",
                         "tools/agx-isa/isadb.py::assemble",
                         "experiments/EXP-0166-exp0146-recovery/analysis/derived_stats.json"],
            "target": "not target-specific (descriptor/tooling)",
        },
        {
            "id": "DEF-0166-2",
            "title": "iadd2.srcB_ext: EXP-0146's M4 raw independently reproduces DEF-0154-4 — "
                     "the 'forbidden' bits are the srcA register selector",
            "severity": "emitter-breaking (already recorded from G17P; this is the M4 half)",
            "db_says": "srcB_ext is typed `mod` (start 49, width 7).",
            "hardware_says": "bits 2..6 select the srcA register in the reg<<2 packing; the low two "
                             "bits are don't-care. 32/32 groups of four consecutive values collapse "
                             "to exactly ONE cross-run-agreeing observable.",
            "how_established": h3["method"],
            "resolves": "H3/F3 of this experiment. It also shows the refutation was already latent "
                        "in EXP-0146's own capture a day before EXP-0154 ran on G17P — the M4 data "
                        "never supported the modifier reading.",
            "target": "M4/G16G (reproduces EXP-0154's G17P result)",
            "evidence": ["experiments/EXP-0166-exp0146-recovery/analysis/h3_srcB_ext.json"],
        },
        {
            "id": "DEF-0166-3",
            "title": "mov_zext16: EXP-0146's own M4 data shows its zext16 carrier is DEAD for this "
                     "instruction — independent corroboration of DEF-0161-2",
            "severity": "corroboration of an existing emitter-breaking defect",
            "db_says": "(post-repair) src_reg = byte0's high nibble; src_flag = byte+1, inert.",
            "hardware_says": "In EXP-0146's `zext16` carrier on M4, decomposing its own sweeps (A5) "
                             "gives: byte0 high nibble (the repaired `src_reg`, 16/16 sub-values) "
                             "INERT; byte+1 (129 of 256 encodings reached) INERT; byte+3 bits 3-7 "
                             "(the repaired `extend`, 32/32) INERT. Only byte+2 (`subform`) moves "
                             "(154 of 256). So the narrow itself is unobservable in that carrier "
                             "while a wrong sub-form can still corrupt it.",
            "how_established": "A5 decomposition of EXP-0146 raw run01+run03; no new device run.",
            "resolves": "EXP-0161 diagnosed EXP-0146's inertness as a carrier artefact from G17P "
                        "(its byte0:=0x00 falsifier scores `ok` there). This confirms the same "
                        "thing ON M4, from EXP-0146's own bytes: the register nibble is inert too, "
                        "which a live carrier could not produce.",
            "consequence": "No mov_zext16 row from EXP-0146 should merge, in either the old or the "
                           "repaired field model. EXP-0165 owns the descriptor.",
            "target": "M4/G16G",
            "evidence": ["experiments/EXP-0166-exp0146-recovery/analysis/decomposed_fields.json"],
        },
        {
            "id": "DEF-0166-4",
            "title": "n2_op10.immword and n2_op8.body each span bytes with different roles — one "
                     "raw field modelling several",
            "severity": "mis-modelled field boundary (FIELD-SWEEP-PROTOCOL §6)",
            "db_says": "n2_op10.immword = a single 48-bit `imm`; n2_op8.body = a single 40-bit `raw`.",
            "hardware_says": "Per-byte, on M4: n2_op10 byte+5 moves the observable for 242 of 256 "
                             "values while byte+9 moves it for ZERO of 256 (219 reproduce, 37 "
                             "unstable) — a dead byte inside a field typed `imm`. n2_op8 byte+3/+5/"
                             "+6/+7 are stable-live while byte+4 is unstable (12 cross-run "
                             "disagreements).",
            "how_established": "byte-wise sweeps in EXP-0146 run01+run03, re-adjudicated here.",
            "consequence": "Both composites are WITHHELD by this experiment (A1). A descriptor "
                           "split would let the live bytes reach emitter grade without dragging a "
                           "dead byte with them.",
            "clean_room_note": "Only per-byte accept/reject envelopes are recorded. The SFU "
                               "range-reduction / marshalling coefficient SEQUENCE is deliberately "
                               "NOT reconstructed (CLAUDE.md forbidden-technique 5).",
            "target": "M4/G16G",
            "evidence": ["experiments/EXP-0166-exp0146-recovery/analysis/derived_stats.json"],
        },
        {
            "id": "DEF-0166-5",
            "title": "ilogic.outmod: M4 and G17P disagree on whether the field is live",
            "severity": "target divergence — not yet resolved",
            "db_says": "outmod (byte+7) bit7 = an output/store flag.",
            "hardware_says": "M4 (EXP-0146, carrier k_logic_and, dense 0..255, both gated runs "
                             "agreeing on every value): 128 values move the observable — every "
                             "value with bit 7 CLEAR silently zeroes — and 128 reproduce. "
                             "G17P (EXP-0154, carrier SYNTH+LIFTED:k_and@ilogic[32:42], 253 "
                             "sampled): 'inert across the whole encodable range', 253/253 ok.",
            "likeliest_explanation": "carrier, not silicon: EXP-0154 judges by a 16-register dump, "
                                     "where a store-enable bit is invisible; EXP-0146's carrier "
                                     "stores the result, so the same bit gates the observable. "
                                     "NOT ESTABLISHED — it is a hypothesis, and the two records "
                                     "contradict each other as written.",
            "consequence": "The EXP-0146 row is WITHHELD under G3 rather than merged. Whichever way "
                           "it resolves, one of the two committed records needs correcting, and an "
                           "emitter reading EXP-0154's 'inert' would drop the store.",
            "recommended_test": "Re-run the G17P ilogic arm with a STORE-consumed observable (not a "
                                "register dump) and sweep byte+7 densely. One arm settles it.",
            "target": "M4/G16G vs G17P",
            "evidence": ["experiments/EXP-0146-m4-emit-int-misc/analysis/field_verdicts.json",
                         "experiments/EXP-0154-g17p-emit-alu/analysis/field_verdicts.json",
                         "experiments/EXP-0166-exp0146-recovery/analysis/derived_stats.json"],
        },
        {
            "id": "DEF-0166-6",
            "title": "sfu_marker.b0_hi is now hardware-run in validation.json, but its M4 half is "
                     "UNSTABLE — the G17P half is what carries it",
            "severity": "evidence-strength caution on an already-merged row",
            "status": "The structural blocker is GONE: EXP-0165 landed the C7b relaxation while "
                      "this experiment was running, so `sfu_marker`'s match is now [0,3,6]+[8,2,2] "
                      "and it has two real fields, `b0_hi` (3,5) and `b1_hi` (10,6). Both were "
                      "merged as hardware-run / G16G+G17P citing EXP-0146 + EXP-0157 + EXP-0165, "
                      "and `sfu_marker` is now counted emittable. That vindicates the recovery "
                      "direction — this defect entry is the caveat, not an objection.",
            "the_caution": "Re-adjudicated under this experiment's thresholds, EXP-0146's two M4 "
                           "arms are NOT equally strong. byte+1 -> `b1_hi`: N=64 decomposed "
                           "sub-values, D=0, accept-set exactly the 32 values with the field's "
                           "bit 2 clear = the published (v & 0x13) == 0x02 rule — clean, "
                           "stable-live. byte+0 -> `b0_hi`: N=32, D=3 (agreement 0.906), and the "
                           "underlying byte probe has 19 cross-run disagreements, every one a "
                           "fault <-> silent-zero flip. Under FIELD-SWEEP-PROTOCOL §7 those are "
                           "contamination-shaped ('contamination can destroy an observation but "
                           "never fabricate a coherent one'), but they are still 19 unresolved "
                           "flips and the arm does not clear the 99% bar ON M4.",
            "consequence": "`b0_hi`'s hardware-run label should rest on EXP-0157's three G17P "
                           "carriers, which reproduced the rule exactly; the M4 citation is "
                           "corroboration, not an independent confirmation of comparable strength. "
                           "This experiment offers NO sfu_marker row (both are G2-redundant "
                           "against the already-merged, cross-target versions).",
            "target": "M4/G16G (this caution) vs G16G+G17P (the merged row)",
            "evidence": ["experiments/EXP-0166-exp0146-recovery/analysis/derived_stats.json",
                         "experiments/EXP-0166-exp0146-recovery/analysis/decomposed_fields.json"],
        },
    ]
    json.dump({"defects": defects}, open(os.path.join(HERE, "proposed_db_defects.json"), "w"),
              indent=1, sort_keys=False)
    print("wrote proposed_db_defects.json — %d defects" % len(defects))

    # ------------------------------------------------------------------ disposition of all 94
    orig = json.load(open(os.path.join(A.SRC, "analysis", "field_verdicts.json")))
    disp = {}
    for k in sorted(orig):
        if k == "db_defects":
            continue
        head, carrier = k.split("@", 1)
        mnem, fld = head.split(".", 1)
        armkey = "%s.%s@%s" % (mnem, fld, carrier)
        s = st.get(armkey)
        compkey = "%s.%s" % (mnem, fld)
        if fld.startswith("byte+"):
            # a raw byte probe: it may still be a constituent of a composite db.json field
            owner = None
            for (cm, cf), byts in A.COMPOSITES.items():
                if cm == mnem and int(fld.split("+")[1]) in byts:
                    owner = "%s.%s" % (cm, cf)
            d = {"class": "not-a-db.json-field (raw byte probe)",
                 "disposition": "ineligible for validation.json as its own row (G1); "
                                + ("aggregated into the composite field %s (A1) -> %s"
                                   % (owner, ("MERGED" if owner in out else
                                              "withheld" if owner in wh else "no verdict"))
                                   if owner else
                                   "reported in proposed_db_defects.json / RESULTS.md")}
            if owner:
                d["composite_owner"] = owner
        elif compkey in out or compkey in wh:
            # a composite db.json field name (operands/tail/body/immword)
            d = ({"class": "SURVIVED", "merged_as": compkey, "label": out[compkey]["label"]}
                 if compkey in out else
                 {"class": "withheld", "key": compkey, "reason": wh[compkey]["reason"]})
            d["via"] = "A1 byte-wise composite aggregation"
        else:
            dbname = s["db_field_at_swept_bits"] if s else None
            if dbname is None:
                subs = sorted(k for k in dec
                              if dec[k]["instr"] == mnem and dec[k]["carrier"] == carrier
                              and dec[k]["bits"][0] >= (s["changed_bit_span"][0] if s else 0)
                              and dec[k]["bits"][0] + dec[k]["bits"][1] - 1
                              <= (s["changed_bit_span"][1] if s else 0))
                d = {"class": "db.json DRIFT — the bits EXP-0146 swept under this name are no "
                              "longer a single field of that mnemonic",
                     "disposition": "A5 decomposition applied; see decomposed_fields.json",
                     "decomposed_into": [{"key": k, "verdict": dec[k]["verdict"],
                                          "merged": ("%s.%s" % (dec[k]["instr"], dec[k]["field"]))
                                          in out} for k in subs]}
            else:
                tgt = "%s.%s" % (mnem, dbname)
                if tgt in out:
                    d = {"class": "SURVIVED", "merged_as": tgt, "label": out[tgt]["label"]}
                elif tgt in wh:
                    d = {"class": "withheld", "key": tgt, "reason": wh[tgt]["reason"]}
                else:
                    d = {"class": "no verdict", "key": tgt}
                if dbname != fld:
                    d["renamed"] = "EXP-0146 called these bits `%s`; db.json now calls them `%s`" \
                                   % (fld, dbname)
        if s:
            d["counts"] = {"N": s["N_A3"], "D": s["D_A3"], "M": s["M_A3"], "I": s["I_A3"],
                           "agreement": s["agreement_A3"], "verdict": s["verdict_A3"],
                           "distinct_encodings": s["distinct_encodings"], "dense": s["dense"]}
        disp[k] = d
    json.dump(disp, open(os.path.join(HERE, "exp0146_disposition.json"), "w"),
              indent=1, sort_keys=True)
    survived = sum(1 for v in disp.values() if v.get("class") == "SURVIVED")
    print("wrote exp0146_disposition.json — %d original keys, %d map to a surviving row"
          % (len(disp), survived))

    # ------------------------------------------------------------------ summary
    print()
    print("SUMMARY")
    print("  original EXP-0146 verdict keys           : %d" % len(disp))
    print("  ... naming a raw byte probe (not a field): %d"
          % sum(1 for v in disp.values() if v["class"].startswith("not-a-db")))
    print("  ... mapping to a surviving merged row    : %d" % survived)
    print("  merge-ready rows written                 : %d" % len(out))
    for k, v in sorted(out.items()):
        print("      %-22s %-20s (was %s)" % (k, v["label"], v["supersedes_label"]))
    print("  flaked arm-baselines found (A3)          : %d" % len(flaked))
    return out, wh, disp


if __name__ == "__main__":
    main()
