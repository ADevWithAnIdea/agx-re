#!/usr/bin/env python3
"""renderarms.py -- EXP-0168 RENDER-arm specification: what is swept, on what,
with what liveness ladder, with what falsifier, and against what oracle.

An ARM is one (carrier, stage, mnemonic, occurrence).  Arms are DISCOVERED by
census rather than hand-listed, because this experiment cannot compile MSL
without the device and therefore cannot know in advance how many occurrences of
each instruction the compiler emits.  What is frozen before the run is:

  * the SELECTION RULE (this file),
  * the census output it selected from  (work/render_census_<id>.json),
  * the FROZEN ARM TABLE derived from it (work/render_frozen_arms.json,
    sha256-pinned in the run's 00_inputs.json),

and `renderrun.py` refuses at run time any arm whose located bytes differ from
the frozen census -- EXP-0163's frozen-occurrence integrity check, which caught
three arms being resolved to the wrong offset before a single value was swept.

THE STANDARD THIS FILE ENCODES
------------------------------
1. A field withheld as "inert" almost always means the carrier could not express
   what the field controls.  EXP-0163 is the canonical proof: `iter_at.loc` read
   inert on every EXP-0155 arm and moves 128/256 at rasterSampleCount 4, because
   at one sample the centroid, the sample point and the pixel centre are the
   same point.
2. TWO CARRIERS IDENTICAL IN THE DIMENSION THE FIELD CONTROLS ARE ONE CARRIER.
   Every carrier carries a `carrier_dim` string naming that dimension, and a
   verdict counts DISTINCT carrier_dim values, never arms and never occurrences.
   `frag_color_pack.dst`'s withheld evidence ("2 carriers") is two occurrences of
   one instruction in one program; `vtx_out_pos`'s is one single-varying program.
3. DETECTION POWER IS PROVEN BEFORE ANY CONCLUSION.  Every arm runs a liveness
   ladder first: >= 8 values of a KNOWN-LIVE control, requiring >= 2 distinct
   observed surface hashes among cases that were BOTH status-OK and valid.  A
   faulted control does not count as a live control -- that was EXP-0163's own
   sec.7 defect (`same_obs` requires both statuses OK, so a faulted control
   scored as live), and it is fixed here at the point of measurement rather than
   in post-processing.  An arm that cannot show its ladder is DISCARDED and its
   inertness is not evidence.
4. LADDER CONTROLS ARE VALUE FIELDS WHEREVER ONE EXISTS.  EXP-0163 produced 88
   device resets in 50 s, ~1.7/second, and every one came from splicing the
   bitwise complement of an opcode or register-number byte (`iter_at.grp/.dst`,
   `vary_store.b5_tag/.hint1`, `simd_shuffle.dst`, `frag_color_store.src`).  A
   device reset kills every other agent's command buffers, so the ladders here
   are chosen from fields whose documented role is a VALUE, and the one arm with
   no such option (`vtx_out_pos`, whose only two fields are the two under test)
   uses a PROGRAM ladder plus a zero-hazard DATA ladder, with the same-
   instruction ladder run last under a hard budget.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.  Every citation below is to our own committed
experiments.  No Apple binary is disassembled.
"""

# ---------------------------------------------------------------------------
# The four fields.  `byte_index` is recorded per case so attribution never
# depends on a db.json label string, which EXP-0144 showed can move out from
# under committed raw when a later experiment edits the descriptor.
# ---------------------------------------------------------------------------
TARGETS = {
    "vtx_out_pos": {
        "stage": "vertex", "family": "vtx",
        "fields": {
            "dst":  {"byte_index": 0, "fstart": 4, "fwidth": 4},
            "slot": {"byte_index": 7, "fstart": 56, "fwidth": 8},
        },
        "withheld_as": "INERT-SINGLE (EXP-0164)",
        "prior": "EXP-0147 (M4): dst 16 values, slot 256 values, ONE carrier, "
                 "0 of 272 moved. The carrier had a SINGLE user varying, and "
                 "EXP-0147's own RESULTS.md sec.6 names 'vtx_out_pos.slot in a "
                 "multi-varying carrier' as the open follow-up.",
        "controls": "the number and identity of varying/output slots (`slot`) "
                    "and which register feeds the output (`dst`)",
        "recovers_instruction": True,   # these are the ONLY withheld fields on it
    },
    "pixel_order": {
        "stage": "fragment", "family": "rog",
        "fields": {
            "kind": {"byte_index": 1, "fstart": 8, "fwidth": 8},
        },
        "withheld_as": "UNVERIFIABLE / no-field-records (EXP-0164)",
        "prior": "EXP-0162 (G17P) HW-VALIDATED the acquire/release pair with a "
                 "quantitative detection-power proof, but recorded its per-value "
                 "sweep under `instr=acquire|release, field=byte1`, so no record "
                 "under raw/ is attributable to `pixel_order.kind`. This is an "
                 "AUDITABILITY gap, not a refutation.",
        "controls": "acquire/wait versus release/signal -- which half of an "
                    "ordering bracket the instruction is",
        "recovers_instruction": False,
    },
    "frag_color_pack": {
        "stage": "fragment", "family": "fcp",
        "fields": {
            "dst": {"byte_index": 3, "fstart": 24, "fwidth": 8},
        },
        "withheld_as": "UNSTABLE (EXP-0164)",
        "prior": "EXP-0155 (G17P): 208 values, '2 carriers', 32 moved, failed "
                 "cross-run agreement. The two 'carriers' fcp@pack0 / fcp@pack1 "
                 "are TWO OCCURRENCES OF THE SAME INSTRUCTION IN ONE PROGRAM -- "
                 "one attachment format (BGRA8Unorm, color_format 80), one "
                 "render target, samples=1. That is ONE carrier.",
        "controls": "which GPR feeds the tilebuffer store",
        "recovers_instruction": False,
    },
}

# ---------------------------------------------------------------------------
# PRE-REGISTERED PREDICTIVE ORACLE for pixel_order.kind.
#
# Derived OFFLINE, before this experiment ran anything, from EXP-0162's
# append-only raw (raw/g17p_20260829_run04__rog/sweep.jsonl, 2048 sweep cases,
# `done` record: hangs 0, elapsed 11.4 s).  Its byte+1 sweep IS this field:
# `pixel_order.kind` is bits[8:16], i.e. byte+1.  The partition below reproduces
# all 256 recorded outcomes on BOTH members exactly -- verified by exhaustive
# comparison, not by inspection.
#
#     bit1 set                       -> ordering LOST (7 of the 8 updates)
#     bit1 clear and bit2 set:
#         acquire member ALSO needs bit4 set   -> ok        (32 / 256)
#         release member needs only bit2       -> ok        (64 / 256)
#     otherwise                                -> wrong_value
#     bits 0, 3, 5, 6, 7 are DON'T-CARE (and bit4 too, on the release member)
#
# This turns the pixel_order arm from an inert "differs from baseline" oracle
# into a genuine cross-experiment prediction: r_rog8 replicates EXP-0162's exact
# carrier parameters, so a disagreement is a real result either way.  r_rogx and
# r_rog2 then ask whether the SAME rule holds when ordering failure looks
# different, which is the actual open question.
# ---------------------------------------------------------------------------


def pixel_order_predict(member, value):
    """member: 'acquire' | 'release' (from the ORIGINAL byte+1 bit4)."""
    if value & 0x02:
        return "lost_7_of_8"
    if member == "acquire":
        return "ok" if (value & 0x10) and (value & 0x04) else "wrong_value"
    return "ok" if (value & 0x04) else "wrong_value"


PIXEL_ORDER_MODEL_NOTE = (
    "pre-registered from EXP-0162 raw/g17p_20260829_run04__rog/sweep.jsonl; "
    "reproduces all 256 recorded outcomes on both members; "
    "live bits 1,2,4; don't-care bits 0,3,5,6,7")


def pixel_order_member(orig_kind):
    return "acquire" if (orig_kind & 0x10) else "release"


# ---------------------------------------------------------------------------
# LIVENESS LADDERS
#
# Each entry:
#   id        stable identifier, recorded per case
#   mnemonic  which instruction the control byte lives in.  None == no splice
#             at all (the DATA ladder: re-run the byte-identical unmutated
#             program with different uniform data).
#   field     the db.json field name to set, or None for the data ladder
#   values    >= 8 values
#   hazard    low | high  -- 'high' ladders run LAST and under a hard budget
#   cite      why this control is KNOWN-LIVE, with the experiment that showed it
#   expect    what the ladder should show if the observation path is live
# ---------------------------------------------------------------------------
LADDERS = {
    "vtx": [
        dict(id="L_data", mnemonic=None, field=None,
             values=[0], hazard="none",
             cite="zero-splice control: the same program bytes with a different "
                  "uniform buffer (@buf0). Proves the whole observation path "
                  "vertex -> varying -> fragment -> pixel and vertex -> "
                  "device out-buf is live and readable, with no splice hazard "
                  "at all.",
             expect="every surface hash changes; the new values match the "
                    "host-computed alt oracle exactly"),
        dict(id="L_vary_hint6", mnemonic="vary_store", field="hint6",
             values=[0x00, 0x01, 0x02, 0x03, 0x10, 0x11, 0x12, 0x13],
             hazard="low",
             cite="EXP-0163 sec.4 (G17P, HW-VALIDATED): vary_store.hint6 bit4 "
                  "alone, 2 classes x 128 values, on 7 arms across 5 carriers -- "
                  "bit4 SET zeroes ALL FOUR fragment output channels. hint6 is a "
                  "VALUE field: EXP-0163's fault table attributes its 88 device "
                  "resets to b5_tag (18) and hint1 (8) on this instruction, and "
                  "NONE to hint6.",
             expect="the four values with bit4 clear reproduce the baseline; the "
                    "four with bit4 set zero the fragment output -> >= 2 hashes"),
        dict(id="L_self_b1", mnemonic="vtx_out_pos", field=None, raw_byte=1,
             values=[0, 1, 2, 3, 4, 5, 6, 7], hazard="high",
             cite="SAME-INSTRUCTION ladder of last resort. vtx_out_pos declares "
                  "only two fields and BOTH are under test, so there is no "
                  "value-field control on this instruction; byte+1 is a match "
                  "constant (0x00) and mutating it may desync the decode. Run "
                  "LAST, budget 2 hangs, then stopped and recorded.",
             expect="unknown by construction -- this ladder is reported, and an "
                    "inert verdict does not depend on it"),
    ],
    "rog": [
        dict(id="L_data", mnemonic=None, field=None, values=[0], hazard="none",
             cite="zero-splice control: same bytes, different `src` uniform "
                  "(@buf0). The ordered accumulator's value is a closed-form "
                  "function of src, so the alt oracle is an exact prediction.",
             expect="texel and pixel both move to the alt oracle exactly"),
        dict(id="L_po_flags", mnemonic="pixel_order", field="flags",
             values=[0, 1, 2, 3, 4, 5, 6, 7], hazard="low",
             cite="EXP-0162 (G17P, HW-VALIDATED) proved detection power on this "
                  "exact carrier QUANTITATIVELY: corrupting byte+4 loses exactly "
                  "7 of 8 raster-order updates (texel 8*src -> 1*src, pixel "
                  "clear+36*src -> clear+8*src). EXP-0147 measured the full "
                  "accepted set: acquire correct iff bit0=0 and (v & 0x0e) != 0; "
                  "release correct iff (v & 0x0f) >= 2. byte+4 is a VALUE field "
                  "(db.json's `flags`), not an opcode or a register number.",
             expect="0x00/0x01 break ordering, 0x02/0x04/0x06 hold it -> >= 2 "
                    "hashes; and the acquire/release asymmetry at 0x01 vs 0x03 "
                    "re-measures EXP-0147's M4 rule on G17P"),
        dict(id="L_po_scope", mnemonic="pixel_order", field="scope",
             values=[0x50, 0xd0, 0x51, 0xd1, 0x58, 0xd8, 0x70, 0xf0],
             hazard="low",
             cite="EXP-0147: acquire correct iff bit4=1 and bit6 XOR bit7=1 "
                  "(64/256); release correct iff bit4=1 and bit7=1. All eight "
                  "values above keep byte+3 bits 4 and 6 set, which EXP-0162's "
                  "corrected match REQUIRES, so every one still decodes as "
                  "pixel_order and none is an opcode splice.",
             expect=">= 2 hashes from the bit7 partition"),
    ],
    "fcp": [
        dict(id="L_data", mnemonic=None, field=None, values=[0], hazard="none",
             cite="zero-splice control (@buf0). UNAVAILABLE on r_fcp1 / r_fcp1s, "
                  "whose colour values are literals in the MSL -- that is "
                  "recorded as `skipped`, never silently omitted.",
             expect="every colour channel moves to the alt oracle exactly"),
        dict(id="L_fcp_mode", mnemonic="frag_color_pack", field="mode",
             values=[0, 1, 2, 3, 4, 5, 6, 7], hazard="low",
             cite="EXP-0155 (G17P): frag_color_pack.mode is correct iff "
                  "mod 4 in {2,3}. So 0,1,4,5 break and 2,3,6,7 hold -- a "
                  "documented 50% break rate on a VALUE field, which makes it "
                  "the most reliable non-hazardous control on this instruction.",
             expect="4 values reproduce the baseline, 4 do not -> >= 2 hashes"),
        dict(id="L_fcp_val", mnemonic="frag_color_pack", field="val",
             values=[0x00, 0x20, 0x40, 0x60, 0x80, 0xa0, 0xc0, 0xe0],
             hazard="low",
             cite="HW-VALIDATED (EXP-0008/0029, A18): splicing byte+6 0x80 -> "
                  "0x40 moved the read-back green from 0.502 to 0.251, i.e. "
                  "byte+6 IS the colour component value. EXP-0155 used ('val', "
                  "0x80) as this instruction's liveness control. Live only where "
                  "the pack's source is an immediate, so it is expected to pass "
                  "on r_fcp1/r_fcp1s and may legitimately fail on the "
                  "register-source carriers -- which is why it is not the only "
                  "ladder here.",
             expect=">= 2 hashes on immediate-source carriers"),
        dict(id="L_fcp_mask", mnemonic="frag_color_pack", field="src_present_mask",
             values=[0x00, 0x10, 0x20, 0x40, 0x50, 0x80, 0x90, 0xd0],
             hazard="low",
             cite="HW-VALIDATED (EXP-M4-14, A18): byte+7 is a per-component "
                  "source-present bitmask -- 0x10 = component 0 only, 0x40 = "
                  "component 1 only, 0xd0/0x50 = both (register / immediate "
                  "source baseline). 0xff is EXCLUDED here: it is a documented "
                  "ILLEGAL encoding that hard-faults the GPU, and it is used "
                  "below as a FALSIFIER instead, once per carrier.",
             expect="the gating values drop channels -> >= 2 hashes"),
    ],
}

# ---------------------------------------------------------------------------
# FALSIFIERS -- cases pre-registered to FAIL.  If everything passes, the sweep
# proves nothing about our ability to detect a difference.
#
#   predict: the outcome string the analysis must observe.  Not "differs" --
#            a named, host-computed prediction wherever prior work supports one.
# ---------------------------------------------------------------------------
FALSIFIERS = {
    "vtx": [
        dict(id="F_data_alt", mnemonic=None, field=None, value=None,
             predict="alt_oracle_exact",
             note="@buf0 = the alt uniform. Pre-registered to NOT reproduce the "
                  "baseline, and to match the host-computed alt oracle exactly "
                  "on every surface including the vertex-stage device buffer."),
        dict(id="F_hint6_kill", mnemonic="vary_store", field="hint6", value=0x10,
             predict="all_fragment_channels_zero",
             note="EXP-0163 sec.4, HW-VALIDATED on G17P over 7 arms / 5 "
                  "carriers: vary_store.hint6 bit4 set makes all four fragment "
                  "output channels read back 0.0. Pre-registered to FAIL the "
                  "baseline comparison with that exact signature. If it instead "
                  "reproduces the baseline, this carrier's fragment observation "
                  "path is not live and every inert result on it is void."),
    ],
    "rog": [
        dict(id="F_data_alt", mnemonic=None, field=None, value=None,
             predict="alt_oracle_exact",
             note="@buf0 = ROG_SRC_ALT. Texel and pixel are closed-form in src."),
        dict(id="F_flags_01", mnemonic="pixel_order", field="flags", value=0x01,
             predict="lost_7_of_8",
             note="EXP-0162's quantitative detection-power proof, re-run as a "
                  "falsifier: byte+4 -> 0x01 must lose exactly 7 of the 8 "
                  "raster-order updates (texel R+1*src, pixel C+8*(R+src)). Not "
                  "'differs' -- a named number. If ordering does NOT break here, "
                  "this carrier cannot see an ordering failure and its "
                  "pixel_order results are void."),
    ],
    "fcp": [
        dict(id="F_data_alt", mnemonic=None, field=None, value=None,
             predict="alt_oracle_exact",
             note="@buf0 = the alt colour set, whose 8-bit codes are disjoint "
                  "from the baseline's by construction."),
        dict(id="F_mode_00", mnemonic="frag_color_pack", field="mode", value=0x00,
             predict="not_ok",
             note="EXP-0155: mode is correct iff mod 4 in {2,3}, so 0x00 must "
                  "NOT reproduce the baseline."),
        dict(id="F_mask_ff", mnemonic="frag_color_pack", field="src_present_mask",
             value=0xFF, predict="contained_fault", hazard="fault",
             note="EXP-M4-14, HW-VALIDATED on A18: byte+7 == 0xff is an ILLEGAL "
                  "encoding that produces a CONTAINED command-buffer fault (the "
                  "device survived). Pre-registered to FAULT, once per carrier. "
                  "It proves the harness can still see a fault, and it is a "
                  "cross-target check of an A18 result on G17P. A contained "
                  "CMDBUF_ERROR is NOT a device reset and costs no sibling "
                  "agent's work -- but if it hangs instead, it counts against "
                  "the arm's hang budget like any other hang."),
    ],
}

# ---------------------------------------------------------------------------
# BYTE-MATE CONTROLS
#
# Rule: vary ONLY the field's own bits, and where a field is sub-byte, ALSO
# sweep the complementary bits of the same byte with the field held at its
# anchor value.  If the complement moves the same observable, attribution is
# ambiguous and the analysis must say so.
# ---------------------------------------------------------------------------
BYTE_MATES = {
    ("vtx_out_pos", "dst"): dict(
        raw_byte=0, mate_mask=0x0F, values=list(range(16)), hazard="high",
        note="`dst` is byte0 bits[4:8]; its byte-mate is byte0's LOW nibble, "
             "which db.json pins to 0xb as part of the instruction match. So "
             "this control is a DECODE-BOUNDARY probe, not an ordinary "
             "byte-mate: 15 of its 16 values make the bytes decode as something "
             "other than vtx_out_pos, and movement there is EXPECTED. It does "
             "NOT create attribution ambiguity for `dst`, because no value of "
             "`dst` changes the mnemonic (the match constrains only bits[0:4]) "
             "-- the control's purpose is to show the byte is reached at all. "
             "Highest-hazard item in this plan: hard budget of 2 hangs, then "
             "stopped and recorded PARTIAL."),
    ("vtx_out_pos", "slot"): None,        # whole byte
    ("pixel_order", "kind"): None,        # whole byte
    ("frag_color_pack", "dst"): None,     # whole byte
}

BYTE_MATE_NA_NOTE = ("field is the whole of its byte, so there are no "
                     "complementary bits to hold or sweep; the byte-mate "
                     "control is not applicable and is recorded as such")

# ---------------------------------------------------------------------------
# Budgets.  A device reset kills every other agent's in-flight command buffers,
# so these are hard stops, not warnings.
# ---------------------------------------------------------------------------
MAX_HANGS_PER_FIELD = 2         # then STOP that (arm, field), record PARTIAL
MAX_HANGS_PER_ARM = 6           # then STOP that arm, record PARTIAL
MAX_HANGS_TOTAL = 24            # then STOP the run, record PARTIAL
HANG_SLEEP_S = (2.0, 4.0, 8.0)  # after the 1st, 2nd, 3rd+ confirmed hang
CONFIRM_N = 3                   # majority-of-3 before any fault/hang verdict
MAX_INVALID_RETRIES = 4         # poison / sentinel / victim -> re-run
REQ_TIMEOUT = 15.0
BASELINE_EVERY = 250
BASELINE_RETRIES = 4

# The verdict bar (mirrors EXP-0163, which is what the orchestrator merges).
INERT_MIN_DISTINCT_CARRIER_DIMS = 3
LADDER_MIN_DISTINCT_HASHES = 2


def arm_id(mnemonic, carrier, stage, occ):
    return "%s@%s/%s#%d" % (mnemonic, carrier, stage, occ)


def coverage_for(width):
    """FIELD-SWEEP-PROTOCOL sec.3: w <= 8 -> sweep ALL 2^w values, densely."""
    if width <= 8:
        return list(range(1 << width))
    vals = {0, 1, 2, (1 << width) - 2, (1 << width) - 1}
    vals |= {1 << i for i in range(width)}
    vals |= {(1 << i) - 1 for i in range(1, width)}
    vals |= {(k * 0x9E3779B1) & ((1 << width) - 1) for k in range(3, 60, 2)}
    return sorted(vals)


def selftest():
    bad = []
    # The pre-registered pixel_order partition must have the recorded sizes.
    for member, sizes in (("acquire", {"ok": 32, "lost_7_of_8": 128, "wrong_value": 96}),
                          ("release", {"ok": 64, "lost_7_of_8": 128, "wrong_value": 64})):
        got = {}
        for v in range(256):
            k = pixel_order_predict(member, v)
            got[k] = got.get(k, 0) + 1
        if got != sizes:
            bad.append("pixel_order %s partition: got %r want %r" % (member, got, sizes))
    if len(coverage_for(4)) != 16 or len(coverage_for(8)) != 256:
        bad.append("coverage_for: dense sweep is not dense")
    for fam, lst in LADDERS.items():
        for L in lst:
            if L["mnemonic"] is not None and len(L["values"]) < 8:
                bad.append("ladder %s/%s has fewer than 8 values" % (fam, L["id"]))
    for fam in ("vtx", "rog", "fcp"):
        if fam not in LADDERS or fam not in FALSIFIERS:
            bad.append("family %s missing ladder or falsifier" % fam)
    # 0xff must appear ONLY as a falsifier, never inside a ladder
    for L in LADDERS["fcp"]:
        if L["field"] == "src_present_mask" and 0xFF in L["values"]:
            bad.append("0xff (documented ILLEGAL) is inside a ladder")
    return bad


if __name__ == "__main__":
    f = selftest()
    print("renderarms selftest: %s" % ("PASS" if not f else "FAIL\n  " + "\n  ".join(f)))
    if f:
        raise SystemExit(1)
