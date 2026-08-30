#!/usr/bin/env python3
"""make_verdicts.py -- EXP-0199: build analysis/field_verdicts.json.

Every NUMBER comes from analysis/gate_report.json (derived from the two gated
confirmation captures); the prose axes are the experiment's stated conclusions.
Nothing here re-reads the GPU.

    python3 analysis/gates.py && python3 analysis/make_verdicts.py
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
G = json.load(open(os.path.join(HERE, "gate_report.json")))["groups"]
GA = json.load(open(os.path.join(HERE, "gate_report.json")))["gate_A"]
A = {json.loads(l)["case"]: json.loads(l)
     for l in open(os.path.join(EXP, "raw", "g17p_conf01", "sweep.jsonl"))}
B = {json.loads(l)["case"]: json.loads(l)
     for l in open(os.path.join(EXP, "raw", "g17p_conf04", "sweep.jsonl"))}


def g(k):
    return G.get(k, {})


def counts(k):
    v = g(k)
    if not v:
        return {}
    o = v["outcomes"]
    return {"encodable": 256, "dispatched": v["dispatched"],
            "distinct_requested": v["distinct_requested"],
            "distinct_actual_encodings": v["distinct_actual"],
            "legal_ok": v["n_ok"],
            "silent_or_altered": v["moved"] - v["n_fault"] - v.get("n_hang", 0),
            "faults": v["n_fault"], "hangs": v.get("n_hang", 0),
            "measurement_failed": v["measurement_failed"],
            "untested": 256 - v["dispatched"],
            "cross_run_agreement": v["agreement"],
            "accepted_rule": v["accepted_rule"]}


def boundary_row(pat):
    out = []
    for Bd in (38, 52, 62, 74, 84, 94, 104):
        c = pat % Bd
        out.append(A[c]["outcome"] if A[c]["outcome"] == B[c]["outcome"]
                   else "%s/%s" % (A[c]["outcome"], B[c]["outcome"]))
    return out


TGT = "G17P-direct"
REP = ("INCOMPLETE -- Gate E not met. Two gated captures WERE taken in shuffled "
       "(g17p_conf01) and reversed (g17p_conf04) order with identical actual-byte "
       "ledgers, 0 hangs, 0 measurement failures and 0 invalid ledgers, and four "
       "retained discovery captures agree with them; but RE_EXPERIMENT_PROCESS_"
       "CORRECTIONS Gate E requires a QUIET machine, and this experiment MEASURED "
       "the machine and found it was never quiet (median 9, peak 17 concurrent "
       "foreign GPU processes). Raw cross-run outcome agreement 6475/6511 = 0.9945; "
       "adjudicated 6501/6511 = 0.99846 after classifying a fault-against-a-clean-"
       "observation as a measurement failure (EXP-0160 / EXP-0201 filter). Both "
       "captures ran 19:29-19:42 UTC, entirely BEFORE EXP-0204's declared 20:00-20:25 "
       "UTC hang window, so none of the 36 disagreements can be attributed to it. "
       "Everything below is therefore AUDITABLE and awaiting a serialized quiet "
       "confirmation run, not independently-confirmed.")

V = {
    "_meta": {
        "experiment": "EXP-0199",
        "target": "A18 Pro / G17P (T8140, AGXAcceleratorG17P, 5 cores, macOS 26.6)",
        "process": "RE_EXPERIMENT_PROCESS_CORRECTIONS.md gates A-E; AMENDMENT-01",
        "gate_A_ledger": {"checks": GA["ledger_checks"],
                          "failures": GA["ledger_failures"],
                          "pass": GA["pass_"],
                          "how": ("the runners print ACTUAL <off> <hex> from the "
                                  "spliced file RE-READ FROM DISK; the driver decodes "
                                  "the swept byte out of those bytes independently and "
                                  "asserts it equals the requested value. A round trip "
                                  "was NOT used and is not this gate.")},
        "axes": ["encoding_geometry", "liveness", "semantics", "compiler_recipe",
                 "target", "reproducibility"],
        "gate_E": {"met": False,
                   "why": "no quiet machine was obtainable; concurrency was MEASURED, "
                          "median 9 and peak 17 foreign GPU processes",
                   "captures": ["g17p_conf01 (shuffled)", "g17p_conf04 (reversed)"],
                   "utc_window": "19:29-19:42, entirely before EXP-0204's declared "
                                 "20:00-20:25 UTC hang window",
                   "raw_cross_run_agreement": "6475/6511 = 0.99447",
                   "adjudicated_cross_run_agreement": "6501/6511 = 0.99846",
                   "disagreements": {"total": 36,
                                     "fault_or_hang_on_exactly_one_side": 26,
                                     "carrying_InnocentVictim": 11,
                                     "soft_remaining": 10,
                                     "of_which_are_the_baseline_records_themselves": 3},
                   "status": "held for a serialized quiet confirmation run"},
        "note": ("No percentage is reported without its numerator and denominator. "
                 "Negative findings are worded 'inert in <exact tested envelope>; "
                 "global role unknown' and never 'unused'/'reserved'/'don't-care'.")
    }
}

# ---------------------------------------------------------- frag_depth_store --
V["frag_depth_store._instruction"] = {
    "label": "isolated-byte-diff",
    "previous_label": "corpus-correlation",
    "range": ("b3/b4/b5/byte+1/byte+2 dense 0..255 on carrier c_depth (1280 cases) and "
              "b3/b5/byte+1/byte+2 dense 0..255 on the adversarial carrier c_depth2 "
              "(1024 cases), each in two gated captures"),
    "target": TGT,
    "evidence": ["EXP-0199"],
    "axes": {
        "encoding_geometry": "geometry-mapped",
        "liveness": "live",
        "semantics": "bounded-map (which attachment it writes, and that its byte+5 "
                     "bit 1 selects between the shader depth value and 0.0); the "
                     "operand map of b3/b4 is unknown",
        "compiler_recipe": "not-generated",
        "target_axis": TGT,
        "reproducibility": REP
    },
    "counts": {"b3@c_depth": counts("frag_depth_store.b3@None/c_depth"),
               "b4@c_depth": counts("frag_depth_store.b4@None/c_depth"),
               "b5@c_depth": counts("frag_depth_store.b5@None/c_depth"),
               "byte1@c_depth": counts("frag_depth_store.byte1@None/c_depth"),
               "byte2@c_depth": counts("frag_depth_store.byte2@None/c_depth"),
               "b3@c_depth2": counts("frag_depth_store.b3@None/c_depth2"),
               "b5@c_depth2": counts("frag_depth_store.b5@None/c_depth2"),
               "byte1@c_depth2": counts("frag_depth_store.byte1@None/c_depth2"),
               "byte2@c_depth2": counts("frag_depth_store.byte2@None/c_depth2")},
    "semantic_model_selection": {
        "M_A1_writes_shader_depth_to_the_depth_attachment": "SELECTED",
        "M_A2_fixed_function_position_z": "REFUTED (baseline depth equals the "
            "shader's interpolated depth output, not position.z = 0.0, on both "
            "carriers; and with the instruction replaced the depth attachment keeps "
            "the CLEAR value 1.0, not 0.0)",
        "M_A3_general_selectable_tile_store": "REFUTED (0 of 2304 dispatched "
            "mutations of this instruction's own bytes moved the COLOUR surface "
            "while leaving DEPTH unchanged, in either capture)",
        "M_A4_carrier_artefact": "REFUTED (reproduced on c_depth2, whose depth is a "
            "DECREASING function of a DIFFERENT varying and whose colour carries a "
            "THIRD varying: same host oracle held exactly, same accepted sets, same "
            "128/128 split on b5)"
    },
    "note": ("THE FIRST DIRECT OBSERVATION OF THIS INSTRUCTION'S EFFECT. db.json says "
             "of itself 'Not individually splice-validated (agxrender has no depth "
             "attachment to read back)' and EXP-0181 records that the earlier sweeps "
             "were scored against a COLOUR probe. Here the Depth32Float attachment is "
             "read back per pixel. Unmutated, DEPTH equals the host-computed "
             "interpolated shader depth EXACTLY at three probe pixels with three "
             "DISTINCT values, on both carriers (c_depth: 0.395833/0.270833/0.520833 "
             "== (PIX0.r-0.5)*4 ; c_depth2: 0.6125/0.6875/0.5375 == 0.9-(PIX0.g-0.125)). "
             "Clearing byte+5 bit 1 makes the depth attachment receive 0.0 at every "
             "covered pixel while the colour value at every covered pixel is unchanged "
             "-- 128 of 256 b5 values, identically on both carriers and in both "
             "captures. Accepted sets are exact: b3 (v & 0xfc) == 0x00 (4 of 256), "
             "b4 (v & 0x1f) == 0x00 (8 of 256), b5 (v & 0x02) == 0x02 (128 of 256), "
             "byte+1 (v & 0x06) == 0x04 (64 of 256).")
}
V["frag_depth_store.byte2"] = {
    "label": "hardware-run",
    "range": "0..255 dense, both carriers, two gated captures",
    "target": TGT,
    "evidence": ["EXP-0199"],
    "axes": {"encoding_geometry": "geometry-mapped", "liveness": "accepted-inert",
             "semantics": "unknown", "compiler_recipe": "not-generated",
             "target_axis": TGT, "reproducibility": REP},
    "counts": counts("frag_depth_store.byte2@None/c_depth"),
    "note": ("DB DEFECT CANDIDATE. db.json declares byte+2 == 0x54 as a MATCH field "
             "(match [16,8,84]). On hardware all 256 values of byte+2 leave both the "
             "colour and the depth surface byte-identical to the baseline, on BOTH "
             "carriers and in BOTH captures (512 dispatched, 512 ok). So this byte is "
             "not enforced at this position: inert over 0..255 in the c_depth and "
             "c_depth2 fragment carriers with a depth attachment; global role unknown. "
             "The instruction's detection power is proven on the same arm by b5, b3, "
             "b4 and byte+1, which do move the observable.")
}
V["frag_depth_store.byte1"] = {
    "label": "hardware-run",
    "range": "0..255 dense, both carriers, two gated captures",
    "target": TGT, "evidence": ["EXP-0199"],
    "axes": {"encoding_geometry": "geometry-mapped", "liveness": "live",
             "semantics": "bounded-map (only bits 1-2 are required)",
             "compiler_recipe": "not-generated", "target_axis": TGT,
             "reproducibility": REP},
    "counts": counts("frag_depth_store.byte1@None/c_depth"),
    "note": ("DB DEFECT CANDIDATE. db.json declares byte+1 == 0x14 as a full-byte "
             "MATCH (match [8,8,20]). The hardware accepts exactly 64 of 256 values, "
             "and the accepted set is EXACTLY (v & 0x06) == 0x04 -- six of the eight "
             "bits are free. The other 192 values discard the tile.")
}

# ------------------------------------------------------------------ vary_slot --
V["vary_slot._instruction"] = {
    "label": "corpus-correlation",
    "previous_label": "corpus-correlation",
    "range": "sel/slot/byte0/byte+2 dense 0..255 on c_vary4, two gated captures",
    "target": TGT, "evidence": ["EXP-0199"],
    "axes": {"encoding_geometry": "geometry-mapped", "liveness": "live",
             "semantics": "unknown -- db.json's stated semantics is REFUTED and no "
                          "replacement model is established",
             "compiler_recipe": "not-generated", "target_axis": TGT,
             "reproducibility": REP},
    "counts": {"slot": counts("vary_slot.slot@None/c_vary4"),
               "sel": counts("vary_slot.sel@None/c_vary4"),
               "byte0": counts("vary_slot.byte0@None/c_vary4"),
               "byte2": counts("vary_slot.byte2@None/c_vary4")},
    "semantic_model_selection": {
        "M_B1_slot_selects_the_varying_slot_(db.json)": "REFUTED",
        "M_B2_bit2_is_an_enable": "SELECTED (255 of 256 values match its per-case "
            "prediction exactly: ok iff (v & 0x04) == 0, draw_gone iff set; 1 "
            "cross-run disagreement)",
        "M_B3_fully_inert": "REFUTED",
        "M_PC_positive_control_out_slot_equals_index_shifted_5": "HELD -- 26 of 32 "
            "cases matched the host-computed prediction exactly and 32 of 32 agreed "
            "across the two captures; the 6 non-matching cases are all moves to a "
            "HIGHER slot, where two stores then target one slot and the model did not "
            "specify which writer wins. All 6 DOWNWARD relocations were predicted and "
            "observed exactly (channel and value)."
    },
    "note": ("db.json: 'byte+3 = the varying slot (monotone, tracks the store slot)'. "
             "REFUTED on hardware, on a carrier proven able to show slot selection. "
             "Across 256 values x 2 captures, `slot` produced ZERO relocations, while "
             "the positive control on the SAME observable produced six exact, "
             "host-predicted relocations by changing vary_store.out_slot on a "
             "DIFFERENT instruction. This independently reproduces EXP-0172's "
             "DEF-0172-3 ('only bit 2') on a new carrier with four separately "
             "identifiable varyings, and adds the discriminating negative: not merely "
             "'bits 5-6 did nothing' but 'no value of the whole byte ever selects a "
             "different varying'. An implementer must treat vary_store.out_slot as the "
             "slot lever.")
}
V["vary_slot.byte0"] = {
    "label": "hardware-run", "range": "0..255 dense, two gated captures",
    "target": TGT, "evidence": ["EXP-0199"],
    "axes": {"encoding_geometry": "geometry-mapped", "liveness": "live",
             "semantics": "unknown", "compiler_recipe": "not-generated",
             "target_axis": TGT, "reproducibility": REP},
    "counts": counts("vary_slot.byte0@None/c_vary4"),
    "note": ("DB DEFECT CANDIDATE. db.json declares byte0 == 0x00 as a full-byte MATCH "
             "(match [0,8,0]). On hardware 60 of 256 byte0 values leave the observable "
             "unchanged -- the contiguous range 0x00..0x3b -- and the other 196 move "
             "it. byte0 is therefore NOT a fixed match byte here; it carries live bits. "
             "This is consistent with the same carrier's vertex shader containing four "
             "instructions of the shape `dX 0Y 40 ZZ` (offsets 70/80/90/100) that share "
             "vary_slot's byte+2 == 0x40 but whose byte0 is NOT 0x00 and which the "
             "current length rule cannot tokenize (LEN_UNKNOWN).")
}
V["vary_slot.byte2"] = {
    "label": "hardware-run", "range": "0..255 dense, two gated captures",
    "target": TGT, "evidence": ["EXP-0199"],
    "axes": {"encoding_geometry": "geometry-mapped", "liveness": "live",
             "semantics": "bounded-map (bits 1..6 required, bits 0 and 7 free)",
             "compiler_recipe": "not-generated", "target_axis": TGT,
             "reproducibility": REP},
    "counts": counts("vary_slot.byte2@None/c_vary4"),
    "note": ("db.json declares byte+2 == 0x40 as a full-byte MATCH. The hardware "
             "accepts exactly 4 of 256 values and the accepted set is EXACTLY "
             "(v & 0x7e) == 0x40, i.e. bit 0 and bit 7 are free.")
}
V["vary_slot.sel"] = {
    "label": "hardware-run", "range": "0..255 dense, two gated captures",
    "target": TGT, "evidence": ["EXP-0199"],
    "axes": {"encoding_geometry": "geometry-mapped", "liveness": "live",
             "semantics": "unknown", "compiler_recipe": "not-generated",
             "target_axis": TGT, "reproducibility": REP},
    "counts": counts("vary_slot.sel@None/c_vary4"),
    "note": ("db.json: 'byte+1 (sel) in {0x04,0x0a,0x0c} = the output-class form'. In "
             "this carrier (where the compiler emitted 0x0c) the accepted set is "
             "EXACTLY (v & 0x0f) == 0x0c -- 16 of 256, high nibble free, and 0x04 and "
             "0x0a are NOT accepted. 240 values move the observable.")
}

# --------------------------------------------------------------- sfu_marker ---
V["sfu_marker._instruction"] = {
    "label": "isolated-byte-diff",
    "previous_label": "tokenization-only",
    "range": ("2-byte INSERTION at 7 instruction boundaries the compiler did not "
              "choose, in a straight-line compute carrier containing no 0x06 leader "
              "of its own; plus byte0 and byte+1 dense 0..255 at two of those "
              "boundaries; two gated captures"),
    "target": TGT, "evidence": ["EXP-0199", "EXP-0146", "EXP-0157"],
    "axes": {
        "encoding_geometry": "geometry-mapped (length 2 CONFIRMED by insertion)",
        "liveness": "accepted-inert in an integer-only compute carrier; LIVE in the "
                    "SFU carriers of EXP-0146/EXP-0157",
        "semantics": "bounded-map for FRAMING only (the hardware consumes exactly two "
                     "bytes); the micro-operation remains unknown",
        "compiler_recipe": "generated-point (bytes we chose, at an offset the compiler "
                           "did not choose, in a program that then executed correctly)",
        "target_axis": TGT, "reproducibility": REP},
    "counts": {"insert_0602_ok_at_boundaries": boundary_row("C_sfu0602@%d"),
               "control_0000_at_same_boundaries": boundary_row("C_ctl_pad0000@%d"),
               "control_ffff_at_same_boundaries": boundary_row("C_ctl_ffff@%d"),
               "control_delete2_at_same_boundaries": boundary_row("C_del2@%d"),
               "byte0@74": counts("sfu_marker.match_byte0@74/k_line3"),
               "byte0@94": counts("sfu_marker.match_byte0@94/k_line3"),
               "byte1@74": counts("sfu_marker.match_byte1@74/k_line3"),
               "byte1@94": counts("sfu_marker.match_byte1@94/k_line3")},
    "semantic_model_selection": {
        "M_len2": "SELECTED (ok at 7 of 7 boundaries in both captures)",
        "M_len4": "REFUTED", "M_notinstr": "REFUTED",
        "detection_power": "the three controls at the SAME boundaries are ok at 0 of 7"
    },
    "note": ("INDEPENDENT EMISSION DEMONSTRATED. Inserting the two bytes 06 02 at an "
             "instruction boundary the compiler did not choose leaves the carrier's "
             "full 32-lane output EXACTLY equal to the host oracle, the independent "
             "pre-sentinel intact and the two never-written poison regions intact, at "
             "all seven tested boundaries, in both captures. At the same seven "
             "boundaries `00 00`, `ff ff` and a 2-byte DELETION are correct at none. "
             "That difference is the length proof: if the hardware consumed any number "
             "of bytes other than two, the following instruction would lose its "
             "leader, exactly as it does for the controls.\n"
             "MATCH-BIT CORRECTION: db.json declares (byte0 & 0x07) == 6 (32 values). "
             "Of those 32, exactly 8 are accepted, and they are exactly "
             "(byte0 & 0x1f) == 0x06 -- bits 5,6,7 free, bits 3,4 must be 0. byte0 = "
             "0x0e also satisfies the declared match but is `stop` and halts the "
             "program (poison in the output, sentinel present). 36 byte0 values total "
             "are accepted at each site; the other 28 have (byte0 & 0x07) == 4, the "
             "get_sr/mov_imm low-3-bits-100 family, which is a DIFFERENT descriptor "
             "and is not evidence about sfu_marker.\n"
             "byte+1 is UNCONSTRAINED FOR FRAMING: 256 of 256 accepted at boundary 94 "
             "and 255 of 256 at boundary 74 (the single exception is a lone fault "
             "against a clean observation on a measured-busy machine). This does not "
             "contradict EXP-0146/0157, which measured byte+1 in a REPLACEMENT context "
             "inside an SFU carrier where a wrong value produced a wrong sin result: "
             "that is a SEMANTIC constraint on the SFU control word, not a framing "
             "constraint. Both hold.")
}

# ----------------------------------------------------- frame_marker_compact ---
V["frame_marker_compact._instruction"] = {
    "label": "tokenization-only",
    "previous_label": "tokenization-only",
    "range": ("2-byte and 4-byte INSERTION at 7 boundaries; b1 dense 0..255 (minus the "
              "two EXP-0172 hang hazards) in both the 2-byte and the 4-byte form; "
              "byte+2 and byte+3 dense 0..255 in the 4-byte form; two gated captures"),
    "target": TGT, "evidence": ["EXP-0199"],
    "axes": {
        "encoding_geometry": "geometry-mapped -- and the DECLARED LENGTH IS REFUTED",
        "liveness": "live", "semantics": "unknown (the marker's role is not "
                                         "established; only its framing is)",
        "compiler_recipe": "generated-point for the FOUR-byte form only",
        "target_axis": TGT, "reproducibility": REP},
    "counts": {"insert2_60_01_at_boundaries": boundary_row("D_fmc2@%d"),
               "insert4_60_01_00_00_at_boundaries": boundary_row("D_fmc4@%d"),
               "control_insert4_00000000_at_boundaries": boundary_row("D_ctl_4pad@%d"),
               "b1_in_2byte@74": counts("frame_marker_compact.b1_in_2byte@74/k_line3"),
               "b1_in_4byte@74": counts("frame_marker_compact.b1_in_4byte@74/k_line3"),
               "b1_in_4byte@94": counts("frame_marker_compact.b1_in_4byte@94/k_line3"),
               "byte2_in_4byte@74":
                   counts("frame_marker_compact.byte2_in_4byte@74/k_line3"),
               "byte3_in_4byte@74":
                   counts("frame_marker_compact.byte3_in_4byte@74/k_line3"),
               "match_byte0@74": counts("frame_marker_compact.match_byte0@74/k_line3")},
    "semantic_model_selection": {
        "M_len2 (db.json: 2 bytes when byte+2 != 0)": "REFUTED -- 0 of 7 boundaries, "
            "and 0 of 254 b1 values, ever leave the program correct",
        "M_len4": "SELECTED -- ok at 7 of 7 boundaries, and 253 of 254 / 254 of 254 "
            "b1 values at the two swept sites",
        "M_notinstr": "REFUTED",
        "detection_power": "the 4-byte all-zero control `00 00 00 00` at the same "
            "seven boundaries is correct at only 2 of 7, so a 4-byte insertion is not "
            "automatically benign"
    },
    "note": ("THE DESCRIPTOR'S LENGTH IS REFUTED ON HARDWARE, in the tested envelope. "
             "db.json models a 2-byte `frame_marker_compact` (byte0 0x60, byte+2 != "
             "0x00) distinct from the 4-byte `spill_frame_marker`, and isadb.py's "
             "length rule picks between them on byte+2 -- a byte that lies OUTSIDE the "
             "claimed 2-byte instruction. Inserting `60 XX` as TWO bytes at an "
             "instruction boundary breaks the program at every one of seven "
             "boundaries and for all 254 tested XX; inserting `60 XX 00 00` as FOUR "
             "bytes leaves it exactly correct at all seven boundaries and for all 254 "
             "tested XX. In this envelope the hardware consumes FOUR bytes at a 0x60 "
             "leader regardless of byte+1 and regardless of byte+2. This supports "
             "EXP-0148's listing of frame_marker_compact as an UNRESOLVED "
             "CONTINUATION-WORD CANDIDATE: the 2-byte reading is most simply explained "
             "as a 4-byte instruction whose byte+2 and byte+3 were being read as the "
             "next instruction.\n"
             "In the 4-byte form byte+3 is inert over its full range (256 of 256 ok) "
             "and byte+2 is constrained to exactly 40 of 256 values "
             "{h0,h1,h2,h3,h7 for even h}. byte0 is NOT the declared full-byte match "
             "0x60: 12 of a 16-value control set are accepted, including 0x20, 0x30, "
             "0x40, 0x50, 0x70, 0xa0, 0xc0 and 0xe0.\n"
             "SCOPE: this is measured by INSERTION into two straight-line compute "
             "carriers at seven boundaries. The corpus occurrences of `60 00 "
             "<nonzero>` are in threadgroup-atomic and divergent-control-flow "
             "contexts that were NOT re-tested here; the 2-byte reading is refuted in "
             "the tested envelope, not proven impossible everywhere.")
}

# ------------------------------------------------------------------- n2_op6 ---
V["n2_op6._instruction"] = {
    "label": "corpus-correlation",
    "previous_label": "corpus-correlation",
    "range": "byte0 / opsel / imm_sel dense 0..255 at c_depth fragment offset 48, "
             "two gated captures",
    "target": TGT, "evidence": ["EXP-0199", "EXP-0157"],
    "axes": {"encoding_geometry": "geometry-mapped", "liveness": "live",
             "semantics": "unknown -- DECLARED UNKNOWN IN ADVANCE; sem_checked == 0",
             "compiler_recipe": "not-generated", "target_axis": TGT,
             "reproducibility": REP},
    "counts": {"byte0": counts("n2_op6.byte0@48/c_depth"),
               "opsel": counts("n2_op6.opsel@48/c_depth"),
               "imm_sel": counts("n2_op6.imm_sel@48/c_depth")},
    "note": ("NOT PROMOTED, and the reason is stated rather than assumed. Amendment 01 "
             "declared this arm semantics-unknown BEFORE the run, because db.json's "
             "own text calls the descriptor 'a genuine catch-all bucket' whose "
             "'per-sub-op value maps are mixed'. A bucket has no single operation to "
             "predict, so no independent predictor could be written and sem_checked is "
             "0 -- which per RE_EXPERIMENT_PROCESS_CORRECTIONS 2 can never yield "
             "hardware-run or semantically-mapped.\n"
             "What the arm DID establish, on a fourth carrier and on G17P: all three "
             "swept bytes are LIVE. byte0 has an exact accepted set (v & 0xcb) == 0x02 "
             "(8 of 256) with 16 faults and 64 tile discards; opsel accepts exactly "
             "(v & 0x1e) == 0x00 (16 of 256); imm_sel accepts exactly (v & 0x0f) == "
             "0x04 (16 of 256). Replacing the whole instruction with a 6-byte barrier "
             "discards the tile, so it is load-bearing. Every non-accepted value moved "
             "the COLOUR surface only, never the depth surface.")
}

json.dump(V, open(os.path.join(HERE, "field_verdicts.json"), "w"), indent=1)
print("wrote analysis/field_verdicts.json  (%d entries)" % (len(V) - 1))
for k in V:
    if k != "_meta":
        print("  %-38s %s" % (k, V[k].get("label")))
