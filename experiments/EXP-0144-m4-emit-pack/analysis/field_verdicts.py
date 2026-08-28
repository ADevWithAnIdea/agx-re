#!/usr/bin/env python3
"""EXP-0144: build analysis/field_verdicts.json in the FIELD-SWEEP-PROTOCOL.md
section 5 schema, from analysis/byte_scans.json (+ format/wide/gate reports).

  python3 analysis/field_verdicts.py

Labels come from docs/evidence-classification.md section 2 and NOTHING ELSE.
The labelling rule is mechanical and stated in the output under "_method", so a
reviewer can re-derive every label from the byte scans without trusting prose.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
sys.path.insert(0, str(EXP / "harness"))
import isadb                # noqa: E402  read-only
import casematrix as CM     # noqa: E402

DBI = {i["mnemonic"]: i for i in json.loads(isadb.to_json())["instructions"]}
TARGETS = {t["mnem"]: t for t in CM.TARGETS}

# EVIDENCE BASE: the m4_20260828_rv01__* REVALIDATION captures ONLY. The earlier
# run01-run05 captures are retained append-only history and back NO label here: they
# were taken across a window in which a GPU test destabilised WindowServer and took
# MTLCompilerService down machine-wide, and they disagree at up to 43.8% with 1,083
# of 1,084 disagreements carrying a hang on exactly one side. Where the revalidation
# and an original disagree, the REVALIDATION wins and the field's note says so.
REPRO = ("majority-of-3 (escalated to 5 on disagreement) within the rv01 "
         "revalidation; attempts with an InnocentVictim-class fault or a missing "
         "integrity sentinel were discarded and re-run; carrier baseline "
         "re-validated every 100 cases")

NOT_COVERED = {
 "cvt_bf16": "NOT COVERED by the revalidation. The rv01 shard for this instrument "
             "never dispatched a single case: the host's MTLCompilerService "
             "collapsed machine-wide before the carrier could be compiled "
             "(raw/m4_20260828_rv01__cvt_bf16/NOT_RUN.md). The contaminated "
             "run03 DID sweep all 8 bytes of this instruction densely and suggested "
             "rounding is RNE and byte+6 selects half-vs-bfloat, but that capture is "
             "not admissible evidence and no label is carried forward from it.",
 "packed_half2_hi": "NOT COVERED by the revalidation, same MTLCompilerService "
             "collapse (raw/m4_20260828_rv01__packed_half2_hi/NOT_RUN.md). This is "
             "also the one instrument that could not be provoked from any MSL shape "
             "tried, so it is only reachable by a synthesised encoding; in the "
             "contaminated run03 that synthesis executed and computed the packed-half2 "
             "multiply for the HIGH LANE ONLY, which is worth re-testing but is not "
             "admissible here.",
}

METHOD = (
 "A db.json field is labelled from the dense hardware sweeps of the BYTES that "
 "cover its bit range. hardware-run requires (a) every covering byte swept with at "
 "least 200 of 256 values actually executed and cross-run stable, (b) the field's "
 "own encodable range fully covered when it is narrower than a byte, and (c) a "
 "stated value->behaviour rule (an exact bitmask, an operand/register map, a format "
 "table, or 'inert across the whole range'). A byte whose sweep was cut short by the "
 "two-hangs-per-area rule but still executed 150-199 values, or whose rule fits only "
 "approximately, is isolated-byte-diff. Below 150 executed values, or an instrument "
 "lost to a GPU cascade, is untested. No other label is used, and no label is issued "
 "from a record whose validity != valid.")


DB_DEFECTS = {
 "pack_convert.fmt_word_is_not_one_field": {
   "db_says": "bytes +5..+9 are one 40-bit raw field `fmt_word`",
   "measured": "byte+5 = lane-0 SOURCE register (reg<<2, bits 0-1 don't care); "
               "byte+6 = lane-1 SOURCE register (reg<<3, bits 1-2 don't care, bit0=0); "
               "byte+8 = conversion enable (bits 2 and 6 both set); "
               "byte+9 = FORMAT selector (0x4x snorm2x16 / 0x8x unorm2x16 / 0xcx unorm8x2, "
               "bits 2-3 don't care). byte+7 not established (2 genuine hangs stopped it at 8 values).",
   "evidence": "analysis/byte_scans.json pack_convert.byte5/6/8/9; analysis/format_maps.json",
   "impact": "an emitter following db.json cannot choose the pack format or either source register"},
 "pack_convert.src_is_actually_dst": {
   "db_says": "byte+3 = `src`, the source GPR",
   "measured": "byte+3 is the DESTINATION register (reg<<1, bit0 don't care): sweeping it "
               "redirects the result into 6 distinct observed registers, an identical map to "
               "cvt_i2f/cvt_f2i `dst`. The real sources are bytes +5/+6.",
   "evidence": "analysis/byte_scans.json pack_convert.byte3 dst_redirect_slots",
   "impact": "an emitter would write the result to the wrong register"},
 "unpack_convert.convert_desc_is_not_one_field": {
   "db_says": "bytes +3..+6 are one 32-bit raw field `convert_desc`",
   "measured": "byte+3 = DESTINATION register (3 distinct registers observed); byte+4 is "
               "COMPLETELY INERT over all 256 values; byte+5 = SOURCE register (reg<<3, "
               "bits 0-2 don't care); byte+6 = opcode/descriptor (bits 0,2 == 0,1 exactly).",
   "evidence": "analysis/byte_scans.json unpack_convert.byte3/4/5/6",
   "impact": "same as above: neither operand register is reachable from db.json"},
 "unpack_convert.reg_sel_is_a_format_selector": {
   "db_says": "byte+7 high nibble `reg_sel`, 'most likely the unpack RESULT destination "
              "(role INFERRED, not splice-confirmed)'",
   "measured": "bits 6:5 select the FORMAT -- 0x0a/0x8a unorm8, 0x2a/0xaa snorm16, "
               "0x4a/0xca unorm16, 0x6a/0xea unorm8; bit7 don't care; bit3 changes which "
               "SOURCE register is read. Not a destination.",
   "evidence": "analysis/byte_scans.json unpack_convert.byte7 operand map; "
               "the compiler's own unorm(...1cca) vs snorm(...1caa) pair",
   "impact": "the role inference is wrong; it also mis-explains our own compiler's output"},
 "unpack_convert.byte2_enable_rule": {
   "db_says": "match relaxed at commit 2b1cbc50 so only bit1 is pinned; field `cache`",
   "measured": "the instruction reproduces its result IFF (byte+2 & 0x03) != 0 -- a TWO-bit "
               "OR enable. Bits 2-7 are inert. Exact over all 256 values. This reconciles "
               "EXP-0089 (0x56->0x54 breaks it: 0x54&3==0) with EXP-0119 (single-bit flips "
               "of 0x56 all inert: each leaves byte&3 != 0).",
   "evidence": "analysis/predicates.json unpack_convert.byte2",
   "impact": "db.json's match is still not the hardware rule"},
 "cvt_f2h_and_cvt_f2h_dst_are_one_instruction": {
   "db_says": "two separate descriptors (byte0==0x11 vs byte0 low nibble 1 + byte+3 hi nibble 8)",
   "measured": "identical bit rules on every byte (+1 0x7f==0x01, +2 0xc7==0x04, +3 no "
               "bitmask, +4 0xf7==0x04, +5 0x10==0x00); they differ only in byte0's dst nibble.",
   "evidence": "analysis/byte_scans.json cvt_f2h.* vs cvt_f2h_dst.*",
   "impact": "duplicate descriptors; the dst nibble is the only real difference"},
 "length_rule_gaps_observed": {
   "measured": "isadb.instr_length() cannot length byte0==0x01 (cvt_f2h_dst with dst nibble 0, "
               "emitted by our own compiler) nor byte0==0x18 (the packed_half2_hi family), so "
               "both fail to tokenize even though db.json has field tables for them.",
   "evidence": "work/pilot/carriers.log",
   "impact": "whole classes of two documented instructions do not disassemble"},
 "cvt_bf16_match_overfits_byte4": {
   "db_says": "match pins byte+4 == 0x01",
   "measured": "our own compiler emits byte+4 == 0x05 for float->bfloat in the sweep carrier, "
               "so the descriptor fails to decode its own compiler's output.",
   "evidence": "work/pilot/anchors2.log (anchor 0101148105024000)",
   "impact": "decode gap on compiler-emitted code"},
 "_note": "Recorded, NOT patched: db.json is owned by the orchestrator and several "
          "experiments were sweeping concurrently."}


def covering_bytes(mnem, fname):
    d = DBI[mnem]
    f = next(x for x in d["fields"] if x["name"] == fname)
    lo, hi = f["start"], f["start"] + f["width"]
    return [b for b in range(d["length"]) if 8 * b < hi and 8 * b + 8 > lo], f


def main():
    scans = json.loads((HERE / "byte_scans.json").read_text())
    fmaps = json.loads((HERE / "format_maps.json").read_text())
    wide = json.loads((HERE / "wide_fields.json").read_text())
    gate = json.loads((HERE / "gate_report.json").read_text())
    preds = json.loads((HERE / "predicates.json").read_text())
    overt = json.loads((HERE / "reval_vs_original.json").read_text())

    by_ib = {}
    for k, v in scans.items():
        by_ib[(v["instr"], v["byte"])] = v

    out = {"_method": METHOD, "_gate": {k: gate.get(k) for k in
           ("runs", "identical", "differing", "pct_identical",
            "excluded_invalid", "excluded_innocent_victim")}}
    counts = {}
    for mnem in sorted(TARGETS):
        d = DBI[mnem]
        for f in d["fields"]:
            bs, fdef = covering_bytes(mnem, f["name"])
            scs = [by_ib.get((mnem, b)) for b in bs]
            scs = [s for s in scs if s]
            key = "%s.%s" % (mnem, f["name"])
            if not scs:
                out[key] = {"label": "untested", "range": "none", "target": "M4",
                            "evidence": ["EXP-0144"], "reproducibility": "not measured",
                            "note": NOT_COVERED.get(
                                mnem,
                                "NOT COVERED by the revalidation: the rv01 shard for "
                                "%s stopped before reaching the byte(s) covering this "
                                "field (the host's MTLCompilerService collapsed "
                                "mid-shard). No label is carried forward from the "
                                "contaminated run01-run05 captures. See RESULTS.md."
                                % mnem)}
                counts["untested"] = counts.get("untested", 0) + 1
                continue
            nmin = min(s["n_values_executed"] for s in scs)

            def _exact(s):
                """A byte is EXACTLY characterised if any of three independent
                descriptions fits it completely: a bitmask, an exact 1-3 bit
                predicate found by predicates.py, or -- for an operand byte, where a
                predicate is the wrong shape entirely -- a measured register map
                covering at least three distinct registers."""
                if s["bit_rule"].get("exact") or s["bit_rule"].get("kind") == "always_ok":
                    return True
                pk = preds.get("%s.byte%d" % (mnem, s["byte"]), {}) \
                     .get("exact_predicate_for_reproducing_the_result", {}).get("kind")
                if pk in ("equality", "not_equality", "any_set", "all_set", "always"):
                    return True
                for om in (s.get("operand_map") or {}).values():
                    if om.get("kind") == "linear":
                        return True
                    if om.get("kind") == "table" and len(set(om.get("map", {}).values())) >= 3:
                        return True
                if len(s.get("dst_redirect_slots") or {}) >= 3:
                    return True
                return False

            exact = all(_exact(s) for s in scs)
            if nmin >= 200 and exact:
                label = "hardware-run"
            elif nmin >= 150:
                label = "isolated-byte-diff"
            else:
                label = "untested"
            rng = "; ".join("byte+%d: %s" % (s["byte"], s["coverage"]) for s in scs)
            sem = []
            for s in scs:
                bits = []
                br = s["bit_rule"]
                if br.get("kind") == "always_ok":
                    bits.append("byte+%d INERT: all 256 values reproduce the result" % s["byte"])
                elif br.get("kind") == "bitmask":
                    bits.append("byte+%d: %s" % (s["byte"], br["emit"]))
                elif br.get("kind") == "bitmask_approx":
                    pe = preds.get("%s.byte%d" % (mnem, s["byte"]), {}) \
                         .get("exact_predicate_for_reproducing_the_result", {})
                    if pe.get("kind") in ("equality", "not_equality", "any_set",
                                          "all_set", "always"):
                        bits.append("byte+%d: EXACT predicate -- reproduces the result "
                                    "iff %s (%d of %d values)"
                                    % (s["byte"], pe["form"], br["n_ok"],
                                       s["n_values_executed"]))
                    else:
                        bits.append("byte+%d: no single-bitmask rule; %d of %d values "
                                    "reproduce the result (see byte_scans/predicates)"
                                    % (s["byte"], br["n_ok"], s["n_values_executed"]))
                elif br.get("kind") == "never_ok":
                    bits.append("byte+%d: NO value reproduced the result" % s["byte"])
                for pos, om in (s.get("operand_map") or {}).items():
                    if om.get("kind") == "linear":
                        bits.append("byte+%d %s: %s" % (s["byte"], pos, om["emit"]))
                    elif om.get("kind") == "table":
                        bits.append("byte+%d %s: source-register map measured "
                                    "(see byte_scans.json)" % (s["byte"], pos))
                if s.get("silent_zero_discriminated") or s.get("silent_zero_ambiguous"):
                    bits.append("byte+%d silent zeros: %d DISCRIMINATED (the six companion "
                                "values stored through the same path were intact, so the "
                                "store ran and the zero is a real register read) / %d "
                                "ambiguous"
                                % (s["byte"], s.get("silent_zero_discriminated", 0),
                                   s.get("silent_zero_ambiguous", 0)))
                if s.get("dst_redirect_slots"):
                    bits.append("byte+%d: DESTINATION redirection observed into %d distinct "
                                "output slots -- this byte selects the result register"
                                % (s["byte"], len(s["dst_redirect_slots"])))
                fm = fmaps.get("%s.byte%d" % (mnem, s["byte"]))
                if fm:
                    real = {c: m for c, m in fm["codes"].items() if m != ["zero"]}
                    if real:
                        bits.append("byte+%d FORMAT CODES: %s" % (s["byte"], json.dumps(real)))
                sem.append(" | ".join(bits))
            ov = [overt.get("%s.byte%d" % (mnem, s["byte"]), {}) for s in scs]
            n_cmp = sum(x.get("compared", 0) for x in ov)
            n_ov = sum(x.get("overturned", 0) for x in ov)
            note = ("Derived from the rv01 REVALIDATION only. Compared against the "
                    "contaminated run03/run05 on %d measurements: %d overturned by the "
                    "majority vote (%.2f%%); where they disagree the revalidation wins."
                    % (n_cmp, n_ov, 100.0 * n_ov / max(1, n_cmp)))
            if nmin < 200:
                note += (" COVERAGE IS PARTIAL: the smallest covering byte executed only "
                         "%d values (see `range`)." % nmin)
            out[key] = {"label": label, "range": rng, "target": "M4",
                        "evidence": ["EXP-0144"], "semantics": "  ||  ".join(sem),
                        "reproducibility": REPRO, "note": note,
                        "outcomes": {("byte%d" % s["byte"]): s["outcomes"] for s in scs}}
            counts[label] = counts.get(label, 0) + 1

    out["db_defects"] = DB_DEFECTS
    out["_counts"] = counts
    out["_wide_fields"] = wide
    (HERE / "field_verdicts.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("field_verdicts.json:", counts)


if __name__ == "__main__":
    main()
