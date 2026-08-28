#!/usr/bin/env python3
"""EXP-0147 analysis: two gated runs -> analysis/field_verdicts.json.

Applies the labelling rule frozen in PRE_REGISTRATION.md section 8. Nothing here
touches the GPU; it is a pure function of the two raw sweep files.

  python3 analysis/verdicts.py --run01 m4_20260828_run01 --run02 m4_20260828_run02
"""
import argparse, collections, json, os, sys

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(EXP, "harness"))
import sweepplan as SP  # noqa: E402

# Per-field human-readable models. Every rule here was re-derived from the raw
# records as an exact SET IDENTITY (analysis/summarize.py + the assertions in
# RESULTS.md section 2), never by eyeballing a range.
NOTES = {
 "matrix_mac.dst_desc":
   "Correct A*B+C iff bit6==1 and bit7==0 (0x40-0x7f, 64/64). Bits 0-5 don't-care. "
   "0x00-0x3f and 0x80-0xbf give a SILENT ZERO; 0xc0-0xff give a wrong value. "
   "Verified as an exact set identity over all 256 values in both runs.",
 "matrix_mac.b11hi":
   "Documented A*B+C iff (b11hi & 3)==0 (32/128); bits 2-6 don't-care. The two low bits "
   "are ACCUMULATOR SIGN controls resolved per tile row: bit0 -> rows 0-3 use -C; bit1 -> "
   "all 8 rows use -C; both -> rows 0-3 +C, rows 4-7 -C. So the matrix unit performs "
   "A*B-C (multiply-subtract) and a half-tile variant, which simdgroup_multiply_accumulate "
   "never emits.",
 "tile_read.b2": "Fully splice-inert: all 256 values give the byte-exact correct pixel in both runs.",
 "tile_read.b4": "Fully splice-inert: all 256 values correct in both runs.",
 "tile_read.b6":
   "bit0 is a READ-ENABLE: all 128 odd values correct, all 128 even values give a SILENT "
   "ZERO (pixel collapses to the no-read oracle). Bits 1-7 don't-care. Identical rule on "
   "tile_read_mrt.b6.",
 "tile_read.rt_index":
   "With one attachment bound, correct only at 0x00,0x01,0x80,0x81 (baseline 0x00): bit0 "
   "and bit7 don't-care. Every other index SILENTLY RETURNS ZERO rather than faulting.",
 "tile_read.dst":
   "Correct only at 0x00,0x01,0xc0,0xc1 (baseline 0x00); 0x02-0x07 wrong; the bulk silently "
   "zero; 0xf6-0xff fault or collateral. Not a plain 8-bit GPR index. Intra-run replicates "
   "100% stable; 8 of 256 cross-run misses are boundary cases that came back invalid_run "
   "under concurrent GPU load, hence isolated-byte-diff rather than hardware-run.",
 "tile_read.b7":
   "Correct only at 0xae,0xaf,0xee,0xef (baseline 0xae). 85 of 256 values are "
   "NONDETERMINISTIC across replicates and across runs - recorded `unstable`, not promoted; "
   "they most likely expose stale register or tile state.",
 "tile_read.tail":
   "Swept per constituent byte (4x256) plus structured whole-field values. Bytes 1 and 3 are "
   "almost entirely SILENT ZERO off their baseline; byte 0 is nondeterminism-heavy (95 "
   "unstable). Promoted only at the reproducing points.",
 "tile_read_mrt.dst":
   "Same shape as tile_read.dst shifted by this carrier's baseline: correct only at "
   "0x08,0x09,0xc8,0xc9. Intra-run stable 256/256; 10 cross-run misses are load-related "
   "invalid_run.",
 "tile_read_mrt.b4": "Fully splice-inert: all 256 values correct in both runs.",
 "tile_read_mrt.b6": "bit0 read-enable, identical to tile_read.b6 (odd correct / even silent zero).",
 "tile_read_mrt.rt_index":
   "Correct only at 0x08,0x09,0x88,0x89 (baseline 0x08); bit0 and bit7 don't-care. Other "
   "indices silently return zero on attachment 1.",
 "tile_read_mrt.fmt":
   "Correct only at 0x2e,0x2f,0x6e,0x6f,0xae,0xaf,0xee,0xef (baseline 0x2e): bits 0, 6 and 7 "
   "are don't-care and bits 1-5 are the format selector. 104 values give a silent zero.",
 "tile_read_mrt.tail":
   "Per-byte dense plus structured whole-field. Byte 1 and byte 2 almost entirely silent "
   "zero off baseline; 30 unstable cases not promoted.",
 "vtx_out_pos.dst":
   "FULLY INERT over all 16 values in both runs. The arm's litmus-power probe does move the "
   "pixel, so this is measured inertness, not a blind spot. SCOPE LIMIT: the carrier has a "
   "single output slot.",
 "vtx_out_pos.slot":
   "FULLY INERT over all 256 values in both runs. SCOPE LIMIT: this carrier writes ONE "
   "varying slot, so this cannot distinguish 'don't-care' from 'only one legal slot exists' "
   "in a multi-varying program. A multi-varying carrier is the named follow-up.",
 "vtx_coord_xform.mode":
   "Correct exactly when (mode & 0xf3) in {0x22,0xe2} (8/256, baseline 0x22). 240 of 256 "
   "values SUPPRESS THE DRAW ENTIRELY (no_draw, confirmed twice with a healthy device in "
   "between); 8 give a wrong pixel.",
 "vtx_coord_xform.sel":
   "91 of 256 correct, 143 no_draw, 19 genuine 'Caused GPU Hang Error' faults, 1 wrong "
   "value. Intra-run 255/256 stable.",
 "vtx_coord_xform.operand":
   "40-bit field swept per byte (5x256) plus structured whole-field values. Bytes 0 and 4 "
   "are FULLY INERT (256/256 each); byte 3 is fault-prone (17 faults); bytes 1-2 mix correct "
   "with no_draw. Intra-run 1339/1339 stable.",
 "pixel_order.scope":
   "ACQUIRE member: correct iff bit4==1 AND (bit6 XOR bit7)==1 (64/256, baseline 0x50). "
   "RELEASE member: correct iff bit4==1 AND bit7==1 (64/256, baseline 0xd0). Low nibble "
   "don't-care in both. This settles db.json's open note 'scope {0x50,0xd0}, bit7 differs' "
   "with the full accepted set.",
 "pixel_order.flags":
   "ACQUIRE: correct iff bit0==0 AND (v & 0x0e)!=0 (112/256). RELEASE: correct iff "
   "(v & 0x0f)>=2 (224/256). byte+4 is therefore a REAL field with a large legal set, NOT "
   "the constant 0x06 that db.json's match clause pins it to - see db_defects.",
 "pixel_order.b5": "Fully splice-inert: all 256 values correct on BOTH the acquire and the release member.",
 "n3_sample_read.b1": "Fully splice-inert: all 256 values correct in both runs.",
 "n3_sample_read.b3": "Fully splice-inert: all 256 values correct in both runs.",
 "n3_sample_read.tail":
   "48-bit field swept per byte (6x256) plus structured whole-field values. Bytes 1-5 are "
   "FULLY INERT (256/256 each); only byte 0 matters, where 53 values fault with 'Caused GPU "
   "Hang Error'. Intra-run 1603/1603 stable; 12 cross-run misses are load-related.",
}

# The six fence fields: swept in full, but NOT promoted. `untested` with evidence
# means "an experiment swept this and could not establish a model", which the
# validator requires to be spelled out.
FENCE_NOTE = (
 "SWEPT IN FULL BUT UNEXPLAINED - deliberately left `untested` rather than called inert. "
 "What was tried: {what}. What was seen: {seen}. Why it is not promoted: the arm's "
 "litmus-power probe (neutering the NEIGHBOURING threadgroup_barrier) does break the "
 "program, so the carrier is not powerless - but that demonstrates GENERAL detection "
 "sensitivity, not ORDERING-SPECIFIC sensitivity, and the pre-registered sensitivity "
 "control (corrupt the fence's own byte0) PASSED when it was registered to fail. Per "
 "PRE_REGISTRATION.md section 8 and the EXP-0141 lesson (its first tile litmus could not "
 "detect a spliced-out barrier and would have 'proven' a fence inert it had no power to "
 "observe), no field of this arm may be promoted. A successor needs an ordering-specific "
 "litmus that counts stale lanes."
)
FENCE_DETAIL = {
 "scoreboard_fence.kind":  ("all 256 values of byte+1 spliced into `07 42 02 00` in a device-atomic carrier",
                            "all 256 leave the read-back bit-exact; so does corrupting byte0, the opcode itself"),
 "scoreboard_fence.scope": ("all 128 values of the 7-bit byte+2 field", "all 128 leave the read-back bit-exact"),
 "scoreboard_fence.mask":  ("all 256 values of byte+3", "all 256 leave the read-back bit-exact"),
 "compute_fence_scoped.kind":  ("all 256 values of byte+1 spliced into `87 00 80 04` in a threadgroup "
                                "store -> barrier -> +137 far-neighbour-load carrier (every lane reads a "
                                "slot written by a different simdgroup)",
                                "all 256 leave the read-back bit-exact"),
 "compute_fence_scoped.scope": ("all 256 values of byte+2", "all 256 leave the read-back bit-exact"),
 "compute_fence_scoped.mask":  ("all 256 values of byte+3",
                                "246 leave the read-back bit-exact but 10 values REPRODUCIBLY BREAK it "
                                "(0x00,0x08,0x0c,0x10,0x18,0x80,0x88,0x8c,0x90,0x98) - a genuine live "
                                "signal, and the single highest-value follow-up from this experiment"),
}

# The concrete, reviewable demonstration that the measurement can SEE the thing
# each field is being tested for -- the EXP-0141 requirement, stated in numbers.
DETECTION = {
 "matrix_mac":
   "Litmus power: forcing op-enable byte+10 0x24 -> 0x00 drops the multiply and the "
   "read-back becomes C passthrough - the matrix unit's contribution provably vanishes "
   "from the observable, in both runs.",
 "tile_read":
   "Litmus power, ORDERING/CONTRIBUTION-SPECIFIC and byte-exact in both runs: forcing "
   "byte+7 -> 0x00 makes the tilebuffer read return zero and the pixel collapses from "
   "[1.5,-1,1,4.5] (= dst*2+src) to [1,-2,3,0.5] (= src alone) on 4/4 pixels, 4/4 "
   "components. The measurement therefore demonstrably detects a dead tilebuffer read.",
 "tile_read_mrt":
   "Litmus power, byte-exact in both runs: forcing byte+7 -> 0x00 collapses attachment 1 "
   "to -src (its tile read returning zero) while attachment 0 stays correct.",
 "vtx_out_pos":
   "Litmus power: corrupting the op-select match constant suppresses the draw, and the "
   "spatial-liveness control shows all 4 pixels of the 2x2 target differ, i.e. the vertex "
   "stage's output demonstrably reaches every observed pixel.",
 "vtx_coord_xform":
   "Litmus power: corrupting the op-select match constant moves the pixel; the vertex-uniform "
   "liveness control moves it too, so the vertex stage output provably reaches the pixel.",
 "pixel_order":
   "ORDERING-SPECIFIC litmus power, reproduced byte-identically in BOTH runs: with the "
   "acquire member's byte+4 corrupted, the read-back texel falls from 8*src to 1*src - "
   "7 of the 8 serialised read-modify-writes are LOST - and the accumulated pixel falls "
   "from clear+36*src to clear+8*src. This is the direct analogue of EXP-0141's 224/256 "
   "stale lanes: the litmus is demonstrably able to count lost updates, so an 'inert' "
   "verdict here is a measurement, not a blind spot.",
 "pixel_order_rel":
   "Adversarial second method on the RELEASE member. Note the asymmetry: the SAME byte+4 "
   "corruption that loses 7 of 8 updates on the acquire member loses NONE on the release "
   "member (texel stays 8*src in both runs). Its sensitivity control therefore did NOT fail "
   "as pre-registered, so this arm does not itself promote anything; the acquire arm does.",
 "n3_sample_read":
   "Litmus power: corrupting the op-select match constant moves the pixel; the spatial "
   "control shows all 4 pixels differ, so the sample-rate interpolation path is observed.",
 "scoreboard_fence":
   "INSUFFICIENT. Neutering the neighbouring threadgroup_barrier breaks the program "
   "outright (read-back stays at the host poison), which proves GENERAL sensitivity but NOT "
   "ordering-specific sensitivity: it cannot show the litmus counting stale lanes. Combined "
   "with the sensitivity control PASSING when registered to fail, no field of this arm is "
   "promoted - exactly the EXP-0141 trap this check exists to avoid.",
 "compute_fence_scoped":
   "INSUFFICIENT, same reasoning as scoreboard_fence, despite the far-neighbour (+137, "
   "prime > the 32-lane simdgroup width) hazard being designed so every lane reads a slot "
   "written by a different simdgroup. The 10 reproducible breaking values of `mask` show "
   "the field IS live, but without an ordering-specific litmus the model is not established.",
}

# One-line measured meaning per field, the `semantics` key of
# FIELD-SWEEP-PROTOCOL section 5, so the orchestrator's merge is mechanical.
SEMANTICS = {
 "matrix_mac.dst_desc": "destination descriptor: bit6 must be 1 and bit7 must be 0; bits 0-5 don't-care",
 "matrix_mac.b11hi": "bits 0-1 = accumulator SIGN per tile half (bit0 -> rows 0-3 use -C, bit1 -> all rows use -C); bits 2-6 don't-care; a*b+c requires (v&3)==0",
 "tile_read.b2": "splice-inert over all 256 values in this carrier",
 "tile_read.b4": "splice-inert over all 256 values in this carrier",
 "tile_read.b6": "bit0 = tilebuffer-read enable (even -> silent zero); bits 1-7 don't-care",
 "tile_read.rt_index": "render-target selector; bit0 and bit7 don't-care; any unbound index reads as a SILENT ZERO",
 "tile_read.dst": "destination register selector; only 0x00,0x01,0xc0,0xc1 correct in this carrier - not a plain 8-bit GPR index",
 "tile_read.b7": "correct only at 0xae,0xaf,0xee,0xef; 85 of 256 values are nondeterministic",
 "tile_read.tail": "bytes 1 and 3 gate the read (silent zero off baseline); byte 0 nondeterminism-heavy; byte 2 mostly tolerant",
 "tile_read_mrt.dst": "destination register selector; correct only at 0x08,0x09,0xc8,0xc9",
 "tile_read_mrt.b4": "splice-inert over all 256 values in this carrier",
 "tile_read_mrt.b6": "bit0 = tilebuffer-read enable, identical to tile_read.b6",
 "tile_read_mrt.rt_index": "render-target/imageblock-slice selector; correct only at 0x08,0x09,0x88,0x89; others silent zero",
 "tile_read_mrt.fmt": "slot format: bits 1-5 are the selector; bits 0, 6, 7 don't-care",
 "tile_read_mrt.tail": "bytes 1-2 gate the read (silent zero off baseline); 30 unstable values",
 "vtx_out_pos.dst": "splice-inert over all 16 values in this single-output-slot carrier",
 "vtx_out_pos.slot": "splice-inert over all 256 values in this SINGLE-varying carrier; untested for multi-varying programs",
 "vtx_coord_xform.mode": "correct iff (mode & 0xf3) in {0x22,0xe2}; 240 of 256 values suppress the draw entirely",
 "vtx_coord_xform.sel": "operand selector: 91 of 256 correct, 143 suppress the draw, 19 fault",
 "vtx_coord_xform.operand": "40-bit operand: bytes 0 and 4 splice-inert; byte 3 fault-prone; bytes 1-2 gate the draw",
 "pixel_order.scope": "memory scope: acquire needs bit4==1 and bit6 XOR bit7==1; release needs bit4==1 and bit7==1; low nibble don't-care",
 "pixel_order.flags": "a REAL field, not the constant 0x06: acquire accepts bit0==0 and (v&0x0e)!=0 (112/256), release accepts (v&0x0f)>=2 (224/256)",
 "pixel_order.b5": "splice-inert over all 256 values on both the acquire and release member",
 "n3_sample_read.b1": "splice-inert over all 256 values in this carrier",
 "n3_sample_read.b3": "splice-inert over all 256 values in this carrier",
 "n3_sample_read.tail": "48-bit tail: bytes 1-5 splice-inert; only byte 0 matters (53 faulting values)",
 "scoreboard_fence.kind": "NOT ESTABLISHED - all 256 values inert in a device-atomic carrier that lacks ordering-specific litmus power",
 "scoreboard_fence.scope": "NOT ESTABLISHED - all 128 values inert in this carrier",
 "scoreboard_fence.mask": "NOT ESTABLISHED - all 256 values inert in this carrier",
 "compute_fence_scoped.kind": "NOT ESTABLISHED - all 256 values inert in a threadgroup far-neighbour carrier",
 "compute_fence_scoped.scope": "NOT ESTABLISHED - all 256 values inert in this carrier",
 "compute_fence_scoped.mask": "LIVE BUT NOT MODELLED - 10 of 256 values reproducibly break the threadgroup result (0x00,0x08,0x0c,0x10,0x18,0x80,0x88,0x8c,0x90,0x98)",
}

CONTROLS = ("_baseline", "_liveness_src_alt", "_liveness_dst_alt", "_liveness_vp_alt",
            "_liveness_spatial", "_litmus_power", "_identity_splice", "_sensitivity")


def load(run_id):
    p = os.path.join(EXP, "raw", run_id, "sweep.jsonl")
    return [json.loads(l) for l in open(p)]


def rngstr(vals):
    """Compact contiguous-range description of an integer value set."""
    iv = sorted(v for v in vals if isinstance(v, int))
    if not iv: return ""
    out, s, p = [], iv[0], iv[0]
    for x in iv[1:]:
        if x == p + 1: p = x; continue
        out.append((s, p)); s = p = x
    out.append((s, p))
    return ",".join(f"0x{a:02x}" if a == b else f"0x{a:02x}-0x{b:02x}" for a, b in out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run01", required=True)
    ap.add_argument("--run02", required=True)
    ap.add_argument("--out", default=os.path.join(EXP, "analysis", "field_verdicts.json"))
    a = ap.parse_args()
    r1, r2 = load(a.run01), load(a.run02)

    def index(recs):
        ctrl, sweep, meta = {}, {}, {}
        for r in recs:
            if r.get("kind") == "arm_meta": meta[r["arm"]] = r
            if "field" not in r: continue
            k = (r["carrier"], r["field"])
            if r["field"] in CONTROLS: ctrl[k] = r
            elif r["field"] == "_baseline_recheck": ctrl.setdefault(k, []).append(r) \
                if isinstance(ctrl.get(k), list) else ctrl.setdefault(k, [r])
            else: sweep[(r["carrier"], r["field"], str(r["value"]))] = r
        return ctrl, sweep, meta

    c1, s1, m1 = index(r1)
    c2, s2, m2 = index(r2)

    # ---- cross-run agreement ------------------------------------------------
    common = set(s1) & set(s2)
    agree = sum(1 for k in common if s1[k]["outcome"] == s2[k]["outcome"])
    xrun = {"cases_in_both_runs": len(common), "same_outcome": agree,
            "agreement_pct": round(100.0 * agree / max(1, len(common)), 3),
            "only_in_run01": len(set(s1) - set(s2)),
            "only_in_run02": len(set(s2) - set(s1))}

    verdicts = {}
    # Corrected models found by the sweeps. NOT applied to db.json -- the
    # orchestrator owns that file (FIELD-SWEEP-PROTOCOL section 6).
    defects = {
        "pixel_order.flags": {
            "severity": "descriptor is self-contradictory AND over-constrains the hardware",
            "db_says": "field `flags` at bits[32:40] (byte+4), while match constant "
                       "[32,8,6] pins those SAME bits to 0x06",
            "measured": "with the acquire member spliced, the program stays byte-exactly "
                        "correct (texel = 8*src, pixel = clear + 36*src) for 112 of the 256 "
                        "values of byte+4, and for 224 of 256 on the release member. byte+4 "
                        "is therefore a REAL field with a large legal set, not a constant.",
            "consequence": "as modelled, every legal encoding with byte+4 != 0x06 fails to "
                           "match `pixel_order` at all, so it is neither decodable nor "
                           "emittable; and `flags` can never be given a value by an emitter.",
            "suggested": "drop the [32,8,6] match constant, keep `flags` as a field, and "
                         "record the measured legal sets (see fields.pixel_order.flags)."},
        "scoreboard_fence.kind": {
            "severity": "enum incomplete",
            "db_says": "kind in {0x00, 0x02, 0x22, 0xc0, 0xc2}",
            "measured": "our own MSL (kernels/pipe_compute.metal :: k_atomic, a device "
                        "atomic RMW plus a device+texture fence) compiles to `07 42 02 00`, "
                        "i.e. kind = 0x42, which the enum does not list.",
            "suggested": "add 0x42; its role is not established here."},
        "matrix_mac.dst_desc": {
            "severity": "typed `raw`, but the hardware rule is simple and now known",
            "measured": "correct result iff bit6 == 1 and bit7 == 0 (0x40..0x7f, 64/64 "
                        "values); bits 0-5 are don't-care. 0x00-0x3f and 0x80-0xbf give a "
                        "SILENT ZERO, 0xc0-0xff give a wrong value.",
            "suggested": "split into a 2-bit control (bits 6-7) plus 6 don't-care bits."},
        "matrix_mac.b11hi": {
            "severity": "typed `raw`, but two of its bits are semantic",
            "measured": "correct a*b+c iff bits 0 and 1 of the field (byte+11 bits 1 and 2) "
                        "are both 0 -- 32/128 values, exactly those with (v & 3) == 0. "
                        "Either bit alone inverts the sign of the C addend (a*b-c); both set "
                        "cancel back to a*b+c. Bits 2-6 are don't-care.",
            "suggested": "split into two accumulator-sign bits plus 5 don't-care bits."},
        "tile_read.b6 / tile_read_mrt.b6": {
            "severity": "typed `raw` with no semantics; bit0 is an enable",
            "measured": "all 128 ODD values give the correct read; all 128 EVEN values give "
                        "a SILENT ZERO (the pixel collapses to the no-read oracle). Bits 1-7 "
                        "are don't-care. Identical on both instructions.",
            "suggested": "model byte+6 bit0 as a read-enable."},
    }
    for arm in SP.ARMS:
        an, instr = arm["arm"], arm["instr"]
        # ---- per-arm control gate (PRE_REGISTRATION section 8) --------------
        def ctrl_ok(name, want_match, runs=(c1, c2)):
            got = []
            for c in runs:
                r = c.get((an, name))
                if r is None: return None
                got.append(bool(r["match"]) == want_match)
            return all(got)

        gate = {
            "baseline_ok": ctrl_ok("_baseline", True),
            "identity_splice_ok": ctrl_ok("_identity_splice", True),
            "sensitivity_failed_as_preregistered": ctrl_ok("_sensitivity", False),
            "litmus_power": ctrl_ok("_litmus_power", True),
        }
        for lv in ("_liveness_src_alt", "_liveness_dst_alt", "_liveness_vp_alt", "_liveness_spatial"):
            if (an, lv) in c1: gate[lv.lstrip("_")] = ctrl_ok(lv, True)
        # Concrete detection strength of the litmus-power probe, so a reviewer can
        # judge it the way EXP-0141's "224/256 stale lanes" can be judged, rather
        # than trusting a boolean.
        lp = {}
        for tag, c, rr in (("run01", c1, r1), ("run02", c2, r2)):
            rec = c.get((an, "_litmus_power"))
            base = c.get((an, "_baseline"))
            if rec:
                lp[tag] = {"probe": (arm.get("power_probe") or {}).get("why", "")[:200],
                           "outcome_with_probe": rec["outcome"],
                           "detected_a_difference": bool(rec["match"]),
                           "observed_with_probe": rec.get("observed"),
                           "observed_baseline": base.get("observed") if base else None}
        # The litmus-power probe sometimes FAULTS rather than degrading, which
        # proves the byte matters but not that the measurement can see the
        # specific failure mode. The sensitivity control (also pre-registered to
        # fail) often carries the sharper evidence, so record it next to the
        # probe and let the reviewer judge, as with EXP-0141's 224/256 stale lanes.
        for tag, c in (("run01", c1), ("run02", c2)):
            rec, base = c.get((an, "_sensitivity")), c.get((an, "_baseline"))
            if rec and tag in lp:
                lp[tag]["sensitivity_control"] = {
                    "outcome": rec["outcome"],
                    "failed_as_preregistered": not bool(rec["match"]),
                    "observed": rec.get("observed"),
                    "observed_baseline": base.get("observed") if base else None,
                    "why": (arm.get("sensitivity") or {}).get("why", "")[:200]}
        rechecks = [r for r in r1 + r2 if r.get("carrier") == an and r.get("field") == "_baseline_recheck"]
        gate["baseline_rechecks"] = len(rechecks)
        gate["baseline_rechecks_all_ok"] = all(r["match"] for r in rechecks) if rechecks else None
        promotable = bool(gate["baseline_ok"] and gate["identity_splice_ok"]
                          and gate["sensitivity_failed_as_preregistered"] and gate["litmus_power"])

        for f in arm["fields"]:
            fn = f["name"]
            cases1 = {k[2]: v for k, v in s1.items() if k[0] == an and k[1] == fn}
            cases2 = {k[2]: v for k, v in s2.items() if k[0] == an and k[1] == fn}
            both = set(cases1) & set(cases2)
            stable = [k for k in both if cases1[k]["outcome"] == cases2[k]["outcome"]]
            intra = [k for k in both if cases1[k].get("stable") is not False
                     and cases2[k].get("stable") is not False]
            oc = collections.Counter(cases1[k]["outcome"] for k in both)
            expected = (f["nbytes"] * 256 + len(SP.wide_values(f["width"]))) if f.get("nbytes") \
                       else (1 << f["width"])
            complete = len(both) >= expected

            # value partition, for byte-wide fields only (multi-byte fields are
            # reported per constituent byte in `note`)
            part = {}
            if not f.get("nbytes"):
                for k in both:
                    part.setdefault(cases1[k]["outcome"], []).append(int(k))

            # PRE_REGISTRATION section 8 clause (4) is an INTRA-run condition
            # ("every non-ok case reproduced across its 3 replicates"). We apply
            # it, and additionally require CROSS-run agreement before saying
            # `hardware-run` -- strictly tighter than the frozen rule, never
            # looser, so it cannot over-promote. Both readings are reported.
            intra_clean = (len(intra) == len(both))
            cross_clean = (len(stable) == len(both))
            if promotable and complete and intra_clean and cross_clean:
                label = "hardware-run"
            elif promotable and complete and intra_clean:
                label = "isolated-byte-diff"
            elif promotable and complete:
                label = "isolated-byte-diff"
            else:
                label = "untested"
            label_frozen = ("hardware-run" if (promotable and complete and intra_clean)
                            else ("isolated-byte-diff" if (promotable and complete) else "untested"))

            v = {
                "label": label,
                "range": (f"full {f['width']}-bit range, dense ({expected} cases) x2 runs"
                          if complete else f"PARTIAL: {len(both)}/{expected} cases"),
                "target": "M4",
                "evidence": ["EXP-0147"],
                "outcomes": dict(oc),
                "label_under_frozen_rule_literal": label_frozen,
                "cross_run_reproduced": f"{len(stable)}/{len(both)}",
                "intra_run_replicates_stable": f"{len(intra)}/{len(both)}",
                "carrier": an,
                "instruction_liveness_proven": promotable,
                "control_gate": gate,
                "semantics": SEMANTICS.get(f"{instr}.{fn}", ""),
                "litmus_power": lp,
                "detection_proof": DETECTION.get(instr if instr != "pixel_order" else an, ""),
                "note": (NOTES.get(f"{instr}.{fn}")
                         or (FENCE_NOTE.format(what=FENCE_DETAIL[f"{instr}.{fn}"][0],
                                               seen=FENCE_DETAIL[f"{instr}.{fn}"][1])
                             if f"{instr}.{fn}" in FENCE_DETAIL else "")),
            }
            if label == "untested" and not v["note"].strip():
                v["note"] = ("Swept on hardware but no model established; see `outcomes` "
                             "and `control_gate`.")
            if part:
                v["value_partition"] = {k: rngstr(vv) for k, vv in sorted(part.items())}
            key = f"{instr}.{fn}"
            if key in verdicts:
                # The pixel_order acquire and release members are two arms over
                # the SAME db field. The acquire arm is the primary record; the
                # release arm is the pre-registered adversarial second method.
                verdicts[key]["adversarial_second_method"] = {
                    "carrier": an, "outcomes": dict(oc),
                    "value_partition": {k: rngstr(vv) for k, vv in sorted(part.items())} if part else None,
                    "control_gate": gate,
                    "label_under_frozen_rule_literal": label_frozen,
                "cross_run_reproduced": f"{len(stable)}/{len(both)}",
                }
            else:
                verdicts[key] = v

    verdicts["mesh_out_src.sel"] = {
        "label": "untested",
        "range": "none - not attempted",
        "target": "M4",
        "evidence": [],
        "note": "NOT ATTEMPTED, and pre-registered as such (PRE_REGISTRATION.md section 1). "
                "mesh_out_src lives in a MESH-stage program, which needs an object/mesh "
                "render pipeline that neither tools/shdump nor this experiment's harness "
                "builds. `evidence` is deliberately empty: this is a genuinely unexamined "
                "field, not a swept-but-unexplained one. Building a mesh-pipeline harness "
                "is the named follow-up.",
        "carrier": None,
        "instruction_liveness_proven": False,
        "semantics": "NOT ESTABLISHED - mesh-stage field, no mesh-pipeline harness exists here",
    }

    out = {
        "_spec": "docs/evidence-classification.md section 2 labels; "
                 "promotion rule frozen in PRE_REGISTRATION.md section 8",
        "_runs": {"run01": a.run01, "run02": a.run02},
        "_cross_run": xrun,
        "_outcome_vocabulary": {
            "ok": "matched the host oracle",
            "silent_zero": "matched the zero-oracle: the instruction contributed 0",
            "wrong_value": "ran, produced neither the oracle nor the zero-oracle",
            "no_draw": "runner returned OK but the integrity sentinel proves nothing was "
                       "drawn; confirmed twice with a healthy device in between",
            "no_dispatch": "same, compute stage",
            "fault": "OS reported 'Caused GPU Hang Error' for THIS submission after retries",
            "invalid_run": "collateral damage from another process's GPU errors "
                           "('Discarded (victim...)' / 'Ignored (for causing prior...)'); "
                           "NOT evidence about the encoding",
            "unstable": "the 3 intra-run replicates disagreed",
            "hang": "watchdog expired",
        },
        "fields": verdicts,
        "db_defects": defects,
    }
    with open(a.out, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True); f.write("\n")
    print(json.dumps({"cross_run": xrun,
                      "labels": dict(collections.Counter(v["label"] for v in verdicts.values()))},
                     indent=2))


if __name__ == "__main__":
    main()
