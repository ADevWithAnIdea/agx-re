#!/usr/bin/env python3
"""EXP-0212 -- validation.json side of the queued-defect application.

Does exactly three things, and NOTHING else:

  1. Adds a row for each field that apply_db_edits.py CREATED, at label `untested`
     with the evidence pointer and a note that states, with exact numerators and
     denominators, what the committed evidence shows and what label it may support.
     EXP-0212 does not set labels; `untested` is the placeholder that asserts
     nothing, and validate_labels.py requires a note whenever `untested` carries
     evidence -- which is precisely the right forcing function here.

  2. Adds a DEF-0166-2 notice to every row whose db.json span MOVED under this
     application. Those rows' `label`, `start` and `width` are left EXACTLY as
     they were: `start`/`width` record the bits that were actually MEASURED, and
     silently re-pointing them at the new span is the mis-attachment DEF-0166-2
     exists to prevent. Each notice states the old span, the new span, and whether
     the experiment's committed raw covers the new span.

  3. Recomputes the `coverage` block and refreshes `db_sha256`, using
     work/merge_verdicts.py's own recompute_coverage so the two cannot drift.

  python3 analysis/apply_validation_notes.py [--dry-run]

CLEAN ROOM: reads only this repository's own committed artifacts.
"""
import hashlib, importlib.util, json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
VAL = os.path.join(ROOT, "tools", "agx-isa", "validation.json")
DB = os.path.join(ROOT, "tools", "agx-isa", "db.json")
TAG = "[EXP-0212, 2026-08-30]"


def _mv():
    spec = importlib.util.spec_from_file_location(
        "mv", os.path.join(ROOT, "work", "merge_verdicts.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["mv"] = m
    spec.loader.exec_module(m)
    return m


DEFER = ("LABEL DEFERRED: EXP-0212 applies descriptor corrections and does not set labels. "
         "`untested` is a placeholder that asserts nothing; the evidence below may support "
         "a stronger label and that ruling is the orchestrator's. ")

# ---------------------------------------------------------------------------
# 1. rows for fields CREATED by apply_db_edits.py
# ---------------------------------------------------------------------------
NEW_ROWS = {
    ("half_alu_fma12", "lensel"): dict(
        evidence=["EXP-0180", "EXP-0183", "EXP-0203"], target="G17P",
        range="bits 32..33 (byte+4 & 3); the 12-byte form is reachable only at value 3, "
              "measured over 4,096 LEN cases with zero ambiguous cells",
        note=DEFER + "Split out of `half_alu_fma12.ext` (old span 32..95). This bit pair was "
             "already measured and documented inside `ext`'s note as the LENGTH SELECTOR; "
             "EXP-0212 only gave it a field of its own. No new observation."),
    ("half_alu_fma12", "mods"): dict(
        evidence=["EXP-0203", "EXP-0180"], target="G17P",
        range="bits 34..39 (byte+4 bits 2..7), dense 0..255 over the whole byte on 3 arms x 2 "
              "runs; hardware identity preserved on 128/256 (the other 128 change the length "
              "selector), full-vector oracle match 4..8 of 256 per arm",
        note=DEFER + "Split out of `half_alu_fma12.ext` (old span 32..95). MEASURED: byte+4 "
             "0x03/0x07/0x0b/0x0f -> |a|*b + c and 0x13/0x17/0x1b/0x1f -> |a|*b - c, so bit 4 "
             "of byte+4 (instruction bit 36) negates the third operand; bit 7 (instruction bit "
             "39) additionally releases (zeroes) the byte+5 source lane; the 0x20..0x3f family "
             "is coherent but unmodelled; bit 2 of byte+4 (instruction bit 34) showed no effect "
             "on any of the three arms. PARTIAL by its own experiment's wording -- a liveness + "
             "partial-semantic map, not a complete modifier decode -- so a promotion above "
             "`isolated-byte-diff` would over-claim."),
    ("half_alu_fma12", "srcC"): dict(
        evidence=["EXP-0203"], target="G17P",
        range="bits 40..47 (byte+5), dense 0..255 on 3 arms x 2 gated runs = 1536 cases; "
              "256/256 hardware identity preserved AND 256/256 full-vector host-oracle match on "
              "EVERY arm; 29 distinct payloads; bit-7 don't-care 128/128",
        note=DEFER + "Split out of `half_alu_fma12.ext` (old span 32..95). This is the "
             "strongest single measurement in EXP-0203: the third fp16 source, half-register "
             "descriptor h = (reg<<1)|is_high with bit 7 a don't-care, predicted by an "
             "independent host oracle over the FULL post-state vector at every one of 256 "
             "values on all three arms. The evidence on its face meets the `hardware-run` bar "
             "(semantic checks against an independent predictor over the stated range); "
             "EXP-0212 does not make that call."),
    ("simd_reduce", "op_hi"): dict(
        evidence=["EXP-0205"], target="G17P",
        range="bits 11..15, exercised as the high 5 bits of a dense 0..255 byte+1 sweep on 4 "
              "reduce carriers x 2 gated runs; the observation repeats with period 8 across all "
              "256 values",
        note=DEFER + "Split out of `simd_reduce.op` (old span 8..15). INERT-WITHIN-FIELD on all "
             "four reduce carriers -- the period-8 repeat IS this field being ignored, "
             "established by a per-bit differential (observed vector at v vs at v XOR (1<<b)) "
             "in both runs, not by absence of movement. Per "
             "RE_EXPERIMENT_PROCESS_CORRECTIONS section 7 the bounded wording is `inert in this "
             "exact tested envelope (four simd/quad reduce carriers, opcls 1, dtype in "
             "{3,7,9,18}); global role unknown`. It is NOT reserved and NOT a don't-care."),
    ("irotate", "rot_dst"): dict(
        evidence=["EXP-0202"], target="G17P",
        range="bits 24..31 (byte+3), dense 0..255 on 2 carriers x 2 gated runs in opposite case "
              "order; reproduces at {0,1}; faults contiguously at 192..255",
        note=DEFER + "Split out of `irotate.operands` (old span 24..63). The DESTINATION, with "
             "the same meaning EXP-0139 established for the identical blob in `iunary` "
             "(DEF-0139-1). 0 cross-run disagreements of 3212. Gate A: the whole arm set is "
             "ledger-verified 20324/20324 with zero requested/actual mismatches."),
    ("irotate", "op_enable"): dict(
        evidence=["EXP-0202"], target="G17P",
        range="bits 32..39 (byte+4), dense 0..255 on 2 carriers x 2 gated runs; 128 of 256 "
              "values reproduce",
        note=DEFER + "Split out of `irotate.operands` (old span 24..63). An OP-ENABLE GATE, "
             "same meaning as the identical blob in `iunary` (DEF-0139-1)."),
    ("irotate", "rot_src"): dict(
        evidence=["EXP-0202"], target="G17P",
        range="bits 40..47 (byte+5), dense 0..255 on 2 carriers x 2 gated runs; reproduces at "
              "0..3",
        note=DEFER + "Split out of `irotate.operands` (old span 24..63). The SOURCE, same "
             "meaning as the identical blob in `iunary` (DEF-0139-1)."),
    ("irotate", "amt_tail"): dict(
        evidence=["EXP-0202"], target="G17P",
        range="bits 56..63 (byte+7), dense 0..255 on 2 carriers x 2 gated runs; reproduces at "
              "the 8 even values 0..14",
        note=DEFER + "Split out of `irotate.operands` (old span 24..63). The tail byte. Named "
             "`amt_tail` rather than `tail` because this descriptor already has a `tail` field "
             "at bits 64..95."),
    ("pop_reconverge", "reserved_hi"): dict(
        evidence=["EXP-0206"], target="G17P",
        range="bits 40..47 (byte+5), exercised at 9 distinct high-byte values "
              "{0,1,2,4,8,16,32,64,128} within a 52-value sampled sweep of the old 16-bit field, "
              "on the cf_ifnl carrier, confirmed on a quiet-machine pair (run05 <-> run07, 52 of "
              "52 agreement)",
        note=DEFER + "Split out of `pop_reconverge.reserved` (old span 32..47). INERT over the "
             "9 high-byte values tested, in the same sweep where the LOW byte is load-bearing -- "
             "a clean separation with no exceptions in the sampled set. NOT a dense 0..255 "
             "sweep: EXP-0206's own next-experiment list asks for exactly that. Bounded "
             "wording: `inert over 9 sampled values on the cf_ifnl carrier; global role "
             "unknown`."),
    ("frag_depth_store", "b1_lo"): dict(
        evidence=["EXP-0199"], target="G17P",
        range="bit 8 (byte+1 bit 0), exercised as part of a dense 0..255 byte+1 sweep on 2 "
              "carriers x 2 captures; the whole byte's accepted set is exactly (v & 0x06) == "
              "0x04, 64 of 256",
        note=DEFER + "FIELD CREATED with the match correction: byte+1 was declared a full-byte "
             "match 0x14 and only bits 1-2 are required, so this bit is free. CANONICAL EMIT "
             "VALUE 0. It is given a field rather than left bare so the relaxed match does not "
             "leave bits with neither a match nor a field."),
    ("frag_depth_store", "b1_hi"): dict(
        evidence=["EXP-0199"], target="G17P",
        range="bits 11..15 (byte+1 bits 3..7), exercised as part of a dense 0..255 byte+1 sweep "
              "on 2 carriers x 2 captures; the whole byte's accepted set is exactly "
              "(v & 0x06) == 0x04, 64 of 256",
        note=DEFER + "FIELD CREATED with the match correction. CANONICAL EMIT VALUE 2 "
             "(0x14 >> 3)."),
    ("frag_depth_store", "b2"): dict(
        evidence=["EXP-0199"], target="G17P",
        range="bits 16..23 (byte+2), dense 0..255 on 2 carriers x 2 captures = 512 dispatched, "
              "512 ok -- every value accepted",
        note=DEFER + "FIELD CREATED with the match correction: byte+2 was declared a full-byte "
             "match 0x54 and the HARDWARE DOES NOT ENFORCE IT AT ALL. The arm's detection power "
             "is proven on the same instruction by b5 (128 of 256 values zero the depth "
             "attachment while leaving colour unchanged), b3, b4 and byte+1. CANONICAL EMIT "
             "VALUE 0x54. Bounded wording: `inert over 0..255 in the c_depth and c_depth2 "
             "fragment carriers with a depth attachment; global role unknown` -- NOT `unused`."),
    ("half_pack", "dst"): dict(
        evidence=["EXP-0203"], target="G17P",
        range="bits 4..7 (byte0 high nibble). Two destination nibbles run end-to-end: the "
              "compiler's own 1 and, on arms HP_C/HP_D, nibble 7 (`78 0d 18 11`), where the host "
              "oracle matches 256/256. 2 of 16 nibbles exercised.",
        note=DEFER + "ADDED by EXP-0212 together with the byte0 match relaxation (8 pinned bits "
             "-> 4). Before that edit every db-expressible `half_pack` wrote r1, and the "
             "instruction had to be built byte by byte to express any other destination -- the "
             "same defect class as DEF-0180-1 one family over. COVERAGE BOUND, stated because "
             "no tool can read it out of `range`: only 2 of the 16 encodable nibbles have been "
             "dispatched, so this is a generated-point for two destinations, not a mapped "
             "4-bit register field. That bound, not the label, is what an emitter needs."),
}

# ---------------------------------------------------------------------------
# 2. DEF-0166-2 notices for rows whose db.json span MOVED
# ---------------------------------------------------------------------------
MOVED = {
    ("half_alu_fma12", "ext"): dict(
        old="start 32, width 64", new="start 48, width 48",
        rederivation="NOT NEEDED FOR THE LABEL. The row reads `untested`, which is equally "
                     "correct for the residue that remains (bytes +6..+11 are still "
                     "unmodelled), and the committed raw DOES cover the new span densely: "
                     "EXP-0203 analysis/ext_bytes.json sweeps byte+6..byte+11 at 256 values "
                     "each on 3 arms x 2 runs. What moved out from under this name -- the "
                     "length selector, the modifier bits and srcC -- now has its own rows."),
    ("simd_reduce", "op"): dict(
        old="start 8, width 8", new="start 8, width 3",
        rederivation="SUPPORTED BY COMMITTED RAW, ruling needed. EXP-0205 dispatched all 256 "
                     "values of byte+1 on 4 carriers in 2 gated runs (8312 recorded cases, 256 "
                     "distinct values), so every one of the 8 values of the new 3-bit field was "
                     "exercised 32 times over, and the semantic check that earned this label -- "
                     "four values, four DISTINCT predicted 32-lane vectors, four matches, zero "
                     "mismatches on sr_sum -- lies entirely inside the new span. The label is "
                     "therefore not weakened by the move; `start`/`width` are left at the "
                     "measured 8/8 rather than silently re-pointed, because updating them is a "
                     "verdict decision. SEMANTIC BOUND that survives either way: the "
                     "{0,1,2,3} -> {ior,isum,smax,umax} map holds only at opcls=1 with dtype=3."),
    ("irotate", "operands"): dict(
        old="start 24, width 40", new="start 48, width 8",
        rederivation="SUPPORTED BY COMMITTED RAW, ruling needed -- and the raw supports a "
                     "STRONGER label than this row carries. This row's `isolated-byte-diff` was "
                     "assigned because only ONE of the old field's five bytes was mapped; that "
                     "byte is byte+6, which is exactly the new span. EXP-0202's dense arm "
                     "`ROT/rot_alu#0/operands_b6` dispatched 256 values, and byte+6 = 4*(32-K) "
                     "was matched against an EXACT host-computed 32-word rotate vector at all 33 "
                     "modelled values on four carriers in two runs (264 exact vector matches, 0 "
                     "misses), plus an independent recovery of a single rotate-left amount at "
                     "those same 33 values (32 distinct amounts, no formula disagreements). "
                     "EXP-0202's own RESULTS says `byte+6 bits[6:2] alone meets the "
                     "hardware-run bar`. THE NAME IS NOW A MISNOMER (it should be `amount`); "
                     "renaming it is left to the orchestrator because a rename moves this "
                     "label onto a new NAME as well as new BITS."),
    ("pop_reconverge", "reserved"): dict(
        old="start 32, width 16", new="start 32, width 8",
        rederivation="NOT NEEDED FOR THE LABEL, and a future promotion needs NEW RAW. The row "
                     "reads `untested`, which stays correct. The committed raw is a SAMPLED "
                     "52-value sweep of the old 16-bit field covering only 33 of 256 distinct "
                     "LOW bytes (re-derived from EXP-0206's sweep.jsonl by EXP-0212), so it does "
                     "NOT densely cover the new 8-bit span -- which is exactly EXP-0206's own "
                     "next-experiment recommendation 2. The `low byte must be zero` model is "
                     "POST-HOC: no pre-registered model survived."),
    ("sfu_marker", "b0_hi"): dict(
        old="start 3, width 5", new="start 5, width 3",
        rederivation="SUPPORTED BY COMMITTED RAW, ruling needed. EXP-0199 swept byte0 densely "
                     "0..255 at each site (5943 recorded cases), so the 8 values of the new "
                     "3-bit span are exhaustively covered and all 8 are accepted -- that "
                     "measurement is what DEFINED the new span. NOTE FOR THE AUDIT: this row "
                     "carries NO `start`/`width`, so work/merge_verdicts.py's DEF-0166-2 guard "
                     "would NOT have caught this move. A verdict that omits the bits it "
                     "measured is invisible to that guard; the guard is only as good as the "
                     "verdicts' own honesty. Recorded here because no tool could."),
}


def main():
    dry = "--dry-run" in sys.argv
    mv = _mv()
    val = json.load(open(VAL))
    db = json.load(open(DB))
    dbf = {i["mnemonic"]: [f["name"] for f in i.get("fields", [])] for i in db["instructions"]}
    dbspan = {(i["mnemonic"], f["name"]): (f["start"], f["width"])
              for i in db["instructions"] for f in i.get("fields", [])}

    added = noted = 0
    for (m, f), spec in sorted(NEW_ROWS.items()):
        assert f in dbf[m], "%s.%s is not in db.json -- run apply_db_edits.py first" % (m, f)
        assert f not in val["instructions"][m], "%s.%s already has a row" % (m, f)
        s, w = dbspan[(m, f)]
        val["instructions"][m][f] = {
            "label": "untested",
            "range": spec["range"],
            "target": spec["target"],
            "evidence": spec["evidence"],
            "note": "%s ROW CREATED WITH THE FIELD. %s" % (TAG, spec["note"]),
            "start": s, "width": w,
        }
        added += 1

    for (m, f), spec in sorted(MOVED.items()):
        row = val["instructions"][m][f]
        now = dbspan[(m, f)]
        txt = ("%s DEF-0166-2 NOTICE -- THE DESCRIPTOR MOVED UNDER THIS ROW. db.json changed "
               "this field from (%s) to (%s) on 2026-08-30. This row's `label` was measured "
               "against the OLD span, and its `start`/`width` (%s) still record the bits that "
               "were actually measured -- they are deliberately NOT re-pointed at the new span, "
               "because a name-keyed re-point is exactly the silent mis-attachment DEF-0166-2 "
               "exists to prevent. RE-DERIVATION STATUS: %s"
               % (TAG, spec["old"], spec["new"],
                  "start %s, width %s" % (row.get("start"), row.get("width"))
                  if row.get("start") is not None else "not recorded",
                  spec["rederivation"]))
        row["note"] = ((row.get("note", "") + " ") if row.get("note") else "") + txt
        noted += 1
        print("  moved %-22s db now (%s,%s); row keeps (%s,%s)"
              % ("%s.%s" % (m, f), now[0], now[1], row.get("start"), row.get("width")))

    cov = mv.recompute_coverage(val, dbf)
    val["db_sha256"] = hashlib.sha256(open(DB, "rb").read()).hexdigest()
    print("\nadded %d rows, annotated %d moved rows" % (added, noted))
    print("emittable: %d  (%s)" % (cov["emittable_instructions"],
                                   ", ".join(cov["emittable_mnemonics"])))
    if dry:
        print("--dry-run: validation.json NOT written")
        return 0
    json.dump(val, open(VAL, "w"), indent=1)
    print("wrote", VAL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
