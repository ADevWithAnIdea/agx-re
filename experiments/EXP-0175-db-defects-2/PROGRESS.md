# EXP-0175 — PROGRESS (append-only)

## 2026-08-30 — freeze
Pre-registration written. Baseline gate measured against the live tree:

    corpus     clean = 833/1080, strict leftover = 388604, tokens = 25419
    roundtrip  OK=302 FAIL=0 crash=0 ALL PASS
    db.json    sha256 322847609de79055b651b79fbd630948bb97120bcefd037a3c7ae5a301ba64a5
               172 instructions, 1062 fields
    validation 541 hardware-run + 86 isolated-byte-diff = 627 emitter-grade / 1062
    overlap    59 fields overlap own match; 25 zero-free-bit; 16 of those emitter-grade

No db.json edits yet.

## 2026-08-30 — re-derivations complete (all five), before any live edit

| defect | re-derived verdict | key numbers |
|---|---|---|
| DEF-0171-1 ilogic byte0 = (dst<<4)\|0x0b | **CONFIRMED** | 15/16 destinations land in r(v>>4), both runs, 0 misses; r15 unobservable by construction |
| DEF-0171-2 no length rule for byte0 0x31 | **CONFIRMED, scope corrected** | all 3 G17P bfloat anchors raise `unknown instruction length`; the blocker is isadb.py's length rule, NOT the descriptors — bf_add/mul/fma_dst already claim the bytes with 12 match bits |
| DEF-0171-3 ibfe.sign_ext is not the sign control | **CONFIRMED** | 0/2 sub-values move on 3 carriers x 2 anchors x 2 runs while byte+6 moves 254/256 |
| DEF-0171-4 outmod bit7 is a source-read control | **CONFIRMED** | nand writes 0xFFFFFFFF x128, others 0x00000000 x128, poison_out==0, sentinels intact, both runs |
| DEF-0171-5 fspecial_est.subop 0x0f | **CONFIRMED** | anchor `0983250f00c2`; match leaves 2 free bits -> legal set {9,b,d,f}; enum had 3 of 4 |

**New finding (not in EXP-0171): byte0 BIT 3 is a don't-care on the ilogic datapath.**
Low nibble 0x3 reproduces the dst<<4 behaviour for 15 of 16 destinations, and
`0x23 03 1f 01 ...` gives a byte-identical 16-register state to the `0x2b` anchor.
NOT folded into the match (low-nibble-3 is a populated, separately HW-validated group).

Candidate gates, all measured before landing:

    baseline    clean=833/1080 leftover=388604 tokens=25419 roundtrip ALL PASS
    cand_def1   clean=833/1080 leftover=388604 tokens=25419 roundtrip ALL PASS
                firing delta: b_alu10_lof 182->175, ilogic 16->23 (7 moved, conserved)
    cand_all    identical to cand_def1 (fold changes no byte)
    cand_merge  identical; b_alu10_lof 182->0, b_alu10_loe 52->0, ilogic 16->250 (conserved)

No db.json edits yet.

## 2026-08-30 — Task 1 + Task 2 LANDED in tools/agx-isa/db.json

db.json sha256 322847609de79055... -> e172359749fe45fc7afba327a659b69ca2c22661000a0ecd450af94292918cc4
172 instructions (UNCHANGED), 1062 -> 1038 fields (+1 ilogic.dst, -25 folded).

Applied: DEF-0171-1 (match + dst field), DEF-0171-3, DEF-0171-4, DEF-0171-5,
DEF-0171-2 (the db.json half only), and the 25-field fold.
NOT applied: the full ilogic/b_alu10_* merge (H2) -- measured, reported, left to
the orchestrator; the isadb.py length rule for byte0 0x31 (another file's owner).

Live-tree gates AFTER landing:
    corpus     clean=833/1080 leftover=388604 tokens=25419   (IDENTICAL to baseline)
    firing     b_alu10_lof 182->175, ilogic 16->23; 7 instructions, population conserved
    roundtrip  302 OK / 0 FAIL / ALL PASS  (after a 2-line fixture patch, see below)
    emit_worklist.py, match_overlap_report.py  both run; overlap 59->34, zero-free 25->0
    validate_labels.py  EXIT 1 -- 32 FAILs, ALL mechanical and expected:
        25 orphaned rows + 1 missing (ilogic.dst) + 6 coverage counts.
        analysis/orphaned_validation_rows.json has the complete list.

**Two collateral edits outside db.json, both forced and both minimal:**
1. `tools/agx-isa/roundtrip_test.py` -- the SYNTH fixture list hard-coded five
   folded field names (`rt_intersect.subop`, `rt_transform_test.{marker,subop,
   cmpmode}`, `ray_move.form`) and omitted `ilogic.dst`. Without the patch the
   suite CRASHED (KeyError from assemble) and 2 ilogic cases FAILed. Fixture keys
   only; every assembled byte string is unchanged. Pre-image kept at
   work/roundtrip_test.py.before.
2. `experiments/EXP-0175-db-defects-2/analysis/ab_gate.py` -- the version
   inherited from EXP-0165 runs roundtrip_test.py IN-PROCESS via runpy, so
   `import isadb` resolves once and every tree after the first silently
   re-measures the FIRST tree's database. It reported ALLPASS=True for a
   candidate that actually crashed. Now run in a subprocess.

## 2026-08-30 — DEF-0174-1 folded in (coordinator's mid-task dispatch, highest priority)

Re-derived FIRST, from EXP-0174's own raw, by fitting BOTH competing models against a
host-computed oracle rather than checking the reported one:

    arm B/srcmap, dense byte+1 0..255, 2 register plans x 2 gated runs
      aliasing v vs v+128 identical            128/128  (all four plan x run cells)
      db.json model  S = byte+1 & 0x7f            3/32
      EXP-0174 model S = bits 1..7, hs = bit 0   32/32
      bit0 = 1 predicted as a HIGH-half read     16/16
    VERDICT: CONFIRMED

The 16-bit granularity fell out of my own oracle: the naive whole-32-bit reading scores
15/16, and the single failure is source r9 = 0x40200000, the only seeded register with a
non-zero high half. One decisive case, and it is the discriminating one.

APPLIED to the live db.json:
  n3_mov        srcA_reg 7 -> 8 bits at byte+1 ((S<<1)|half); srcA_uni DELETED
  frame_marker  same, explicitly labelled STRUCTURAL/INFERRED -- EXP-0174 did NOT sweep it
  mov_zext16    NO field change. Its byte+1 is a DIFFERENT field, HW-tested INERT over 256
                values in two register forms (EXP-0161/0165). The dispatch's "likely fixes
                three descriptors" is two of three, and the third would have been a new
                defect. Relationship note added instead.
  n3_mov        DEF-0174-2 (byte+2 = op selector, byte+3 bit0 = destination half) and the
                emitter-ready encoding, incl. "a 32-bit copy is TWO instructions"
  reg_move_c0   DEF-0174-4: "NO VALIDATED GPR-TO-GPR MOVE EXISTS" marked SUPERSEDED
                (CODEX 8: earlier record preserved and labelled, not deleted)
  pad_operand   DEF-0174-3 recorded as an observation; classification UNCHANGED (its
                "NOT A STANDALONE HARDWARE OPCODE" phrase is checked by validate_labels
                check 9 against emitter_role: data-word -- check 9 still passes)

Gate: corpus 833/1080, 388604 leftover, 25419 tokens -- UNCHANGED, zero firing delta.
roundtrip ALL PASS 302/0. validate_labels 34 FAILs (27 orphans + 1 missing + 6 counts).

MERGE BLOCKER CLEARED: n3_mov.srcA_reg is now (start 8, width 8), matching EXP-0174's
verdict row. analysis/orphaned_validation_rows.json gained a `respanned_rows` block.

## 2026-08-30 — WRITING FINISHED
db.json final sha a77f8cfa163fcf720c0c1093e4ddc5815ceb43c218bb64a87c86d3dcf975dc22
172 instructions, 1036 fields. No further writes from this experiment.
