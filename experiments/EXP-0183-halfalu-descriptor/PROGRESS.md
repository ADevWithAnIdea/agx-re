# EXP-0183 — PROGRESS (append-only; timestamps are local)

## 2026-08-30 — M0: orientation + baseline frozen
- Read CLAUDE.md, CODEX.md, experiments/SUBAGENT_BRIEF.md, FIELD-SWEEP-PROTOCOL.md §3.
- Read EXP-0180 RESULTS.md + analysis/db_defects.json; EXP-0181 analysis/orphaned_validation_rows.json.
- **PURE ANALYSIS. No device, no SSH, no GPU.** Every observation below is re-read from
  committed `raw/` trees; no new hardware run.
- File ownership honoured: I edit `tools/agx-isa/db.json` ONLY. `tools/agx-isa/isadb.py`
  belongs to EXP-0182 and is untouched (it is currently dirty in the working tree — that is
  EXP-0182 mid-flight).
- git HEAD at start: `20613a44194dc48fa95cb0563b88efabf757d09c`; `tools/agx-isa/isadb.py`
  DIRTY (EXP-0182).
- sha256 at start: db.json `1ada4e7b…be04`, isadb.py `500db91a…aa9f`,
  validation.json `230623ac…3eac`.
- **Baseline gate measured, and the dispatch's numbers are STALE by one uncommitted tree:**
  - `work/base_head` (git HEAD isadb.py): **833/1080 clean, 388,604 leftover, 25,419 tokens**
    — exactly the dispatch's figures. Confirms the provenance of the quoted baseline.
  - `work/base_live` (live working tree, = HEAD + EXP-0182's uncommitted isadb.py):
    **840/1080 clean, 387,496 leftover, 25,587 tokens.**
  - Both ALL PASS, 302 `[OK]`, 0 FAIL, 0 crash.
  - **I gate against `base_live`**, the tree my edit actually lands on; `base_head` is
    recorded so the dispatch's number is reconciled rather than contradicted.

## 2026-08-30 — M1: pre-registration frozen, re-derivation COMPLETE
- `PRE_REGISTRATION.md` written and frozen before any `db.json` edit.
- `analysis/rederive.py` → `analysis/defects_rederived.json`. Headline results, all recomputed
  from committed raw with EXP-0180's analysis scripts NOT imported:
  - **H1 (DEF-0180-1) CONFIRMED.** DSTNIB: 15 of 16 destinations confirmed (`n=0..14`),
    `n=15` **unobservable** (`R_IDX`, the store index the harness re-seeds before every
    store). C_LO also masks `n=13` (second consumer) and `n=14` (`R_ZERO`/pad register).
    **Zero refutations.** 16/16 values identical across both runs on both carriers.
    Control: r15 is never non-zero in 16,335 observed cases; r14 is non-zero **exactly once
    in 11,115 C_HI cases — the DSTNIB `n=14` case itself.**
  - **H1b2 — the strongest single check, and it lands on the SIX-BYTE `half_alu`:**
    the seed program's fourteen 6-byte half-adds are `[j<<4][h_B][opsel4][h_A][0x00][0xC0]`
    and nothing but byte0 names register `j`. Per-case identity
    `pre[j].lo == fp16(h[1] + h[2j+1])` for j=0..13: **228,690 checks per run, 0 mismatches,
    in both runs.** Same data refutes `half_alu.srcB` at byte+4 as an operand: byte+4 = 0x00
    = r0's LOW half, which is **non-zero in all 32,670 observed pre-vectors** and does not
    enter the sum.
  - **H1c CONFIRMED and extended:** `r[byte0>>4].lo = fp16(h[byte+1] * h[byte+3] + h[byte+5])`
    on both carriers in both runs, with the anchor's own triple recovered by brute force over
    all 32 half-registers. **byte+5 is the fma addend** — db calls it `b5`, a "mod".
  - **H2 (DEF-0180-2) CONFIRMED exactly:** 32 of 32 cells, **0 ambiguous, 0 cross-run
    disagreements**; my table is byte-identical to EXP-0180's. db.json's stated rule is wrong
    in **25 of 32** cells.

## 2026-08-30 — M2: coordinator course-correction absorbed
- **Length rule NOT applied as code.** EXP-0182's measurement (verbatim = −17 clean files,
  +3,220 leftover) stands; `db.json`'s `byte0_table` is documentation only and now records the
  measured table, the bound, AND the nine agreeing cells the tokenizer implements. Corpus
  effect: zero.
- **`fma12.opsel` fold measured and REFUSED**: 841 → 835 clean, +748 leftover, firings 7 → 0.
  Candidate kept as `work/cand_final_plus_fold`; the decision is the db owner's.
- **`cvt_bf16` [32,8,1] → [32,1,1] re-derived and landed.** EXP-0162's dense byte+4 sweep:
  52 accepted values, ALL with bit 0 set, and **0x01 itself is `wrong_value`** — the descriptor
  pinned a value the hardware rejects. Corpus effect zero; anchor test FAIL → PASS.
- `anchor_decode_test.py` run before (249/255, cvt_bf16 MUST-PASS FAIL) and after
  (250/255, ALL PASS, 5 fixed, 0 regressed).

## 2026-08-30 — M3: db.json LANDED and STABLE
- `tools/agx-isa/db.json` sha256 `2412eac1cad4449eb385702062abd03e5c926d04f7d384e6bf3684c9c4c7c6c4`.
- Gate: **841/1080 clean (+1), 387,214 leftover (−282), 25,634 tokens (+47)**, roundtrip
  ALL PASS 302/0/0, anchor decode ALL PASS. No regression on any axis.
- `analysis/validation_updates.json` written; `analysis/simulate_merge.py` proves applying it
  yields a `validation.json` that passes `validate_labels.py` with ZERO FAILs and ZERO WARNs,
  at **53 emittable / 636 emitter-grade rows**.
- `tools/agx-isa/match_overlap.json` was regenerated and then **restored to HEAD** — I do not
  own it. The regenerated copy is `analysis/match_overlap_regenerated.json`; one command fixes
  the live one.
- README.md, RESULTS.md, manifest.json, raw/README.md written. **No git commit.**
