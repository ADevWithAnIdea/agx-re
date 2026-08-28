# PRE_REGISTRATION — EXP-0099 M4 lifetime-field model

**Pinned repository revision (per SUBAGENT_BRIEF.md — record and compare
against THIS value, never live `HEAD`):** `dc61f8c1f99fa72d5a2094fbbcc31269ba4ca89e`
(tree dirty with unrelated sibling-experiment untracked artifacts at pin
time — expected and explicitly not a contamination signal per SUBAGENT_BRIEF.md).

Target: **local Apple M4 / G16G only.** macOS 26.6.2 (build 25G82), Metal 4.
No A18 Pro (hands-off, standing directive). No M5 evidence used anywhere.

## 0. Origin and status of this document

This contract is written **after** an extensive, honestly-disclosed pilot
phase (see `PROGRESS.md`), not before any hardware contact — consistent with
every prior experiment in this family (EXP-0086/0089/0090 all had an
informal pilot before their frozen, gated capture). The pilot phase:

1. Decoded the external compiler engineer's own example bytes
   (`apple9_isa_explainer.md`) against our `tools/agx-isa/db.json` field
   layout (static, no GPU) — confirmed the background analysis
   (`work/COMPILER-EXPLAINER-INTERACTION-20260828.md`)'s byte-level reading
   of the compact float form, and additionally found that his 10-byte logic
   example's "retain source 0" encoding **does not decode under our current
   `db.json` at all** (`isadb.disassemble` reports `unknown instruction
   length`), while the "release both" encoding decodes as a structurally
   different, weakly-validated family (`b_alu10_loe`) than the family his
   text implies (`ilogic`, whose match condition requires the WHOLE of
   byte0 == 0x0B, not merely its low nibble) — see RESULTS.md for the full
   finding and its status as a separate, static, decoding-dispatch defect.
2. Built a working splice-and-execute harness against an original,
   higher-register-pressure carrier kernel; found it **silently failed
   every `device_load`-involving splice** (reads returned `0.0` regardless
   of the loaded value) while the SAME instructions worked correctly
   against `EXP-0090`'s own `carrier_p2.metal`. Root cause not fully
   isolated in the time available (see `PROGRESS.md` "INCIDENT" entry);
   the carrier was rewritten to closely match `carrier_p2.metal`'s
   register-pressure shape, which resolved it. This is disclosed, not
   hidden — it is a real, if narrow, negative result about kernel
   complexity and splice reliability that a future experiment should
   revisit.
3. While isolating that incident, independently discovered that
   `tools/agx-isa`'s own previously-`HW-VALIDATED`
   `device_store extmode = 2*data_reg` formula (EXP-0090 finding_5) and the
   `device_load -> device_store` "direct forward" `addr_mode=0x56` pattern
   (EXP-0090 finding_3) **both fail for every destination register tried
   except the exact one (`r5`) EXP-0090's own anchor happened to use** —
   and that `device_load`'s result **cannot be read by a subsequent
   `falu2`/`falu2i` instruction via ANY of the 8 candidate "route" values**,
   replicating (not merely repeating — an independently re-derived,
   register- and route-varied confirmation) EXP-0090's own P4/finding_2/
   finding_4 blocker. This is now the experiment's own formal H4 test
   (`ROUTE_LOAD`/`ROUTE_ALU`/`H4_BIT21` below), not treated as a plumbing
   bug requiring further fixing.
4. Designed and validated (informally, on real hardware) the final H1/H2
   test shape below, which does NOT depend on the load-to-ALU bridge at
   all — see H1/H2 falsifier design.

Because (3) is itself load-bearing evidence for H4, and repeating it under
the FORMAL two-run gate is exactly the kind of "adversarial /
second-method" validation CODEX step 8 asks for, this pre-registration
freezes the design the pilot converged on and proceeds directly to the two
contracted gated captures. No case's **hex bytes or oracle** were adjusted
after seeing a GPU result beyond the plumbing fixes described above
(carrier kernel shape, `device_load` `space` default, device_store word
addressing unit) — every hypothesis-bearing case's PREDICTION was written
down before that specific case was first executed, and matches what is
recorded in `casematrix.py` verbatim.

## 1. Hypotheses under test (H1–H6, per dispatch)

**H1 — FIELD SPLIT.** Is `falu2`'s `srcA_reg`/`srcB_reg` (db.json: 7-bit
fields, bits 9–15 / 25–31) a literal 7-bit register index (current
`db.json` model), or a 6-bit register index plus a retention flag in the
top bit (explainer's model)?

- **Falsifier design:** seed a KNOWN value `V_LOW` into register r3 via an
  independently HW-VALIDATED ALU-only path (`falu2i`, srcA=an unwritten
  register — proven to read exactly 0.0, EXP-0087 MOVE-04). Never write
  register r67 at all. Construct a `falu2` instruction whose `srcA_reg`
  FIELD VALUE is `67` (low 6 bits = 3, the SAME low register r3 lives in;
  bit for weight 64 = 1) and separately `3` (bit clear), with a
  don't-care/unwritten `srcB`, and read the result back.
  - **CONFIRMS current db.json model:** field value 67 reads **0.0**
    (register 67, genuinely unwritten).
  - **CONFIRMS explainer's model (or any 6-bit-address model):** field
    value 67 reads **`V_LOW`** (register 3's seeded value — bit 15 is not
    part of the address).
  - **Refuter:** if field value 67 reads neither 0.0 nor `V_LOW` (e.g. a
    third, unrelated value), NEITHER model is confirmed and the field's
    behavior is `UNKNOWN`.

**H2 — COMPLEMENTARY PAIR.** Is retention the correlated transition
`(bit15,bit19)=(1,0)` / release `(0,1)` (explainer's model — flipping ONE
half is inert, flipping the PAIR changes behavior), reconciling EXP-0086's
positive CAND_B (bit19 alone) with its null CAND_A (bit15 alone)? Same
question for `(bit31,bit20)` on `srcB`.

- **Falsifier design:** for BOTH `srcA` (field value ∈ {3, 67}, i.e. bit15
  ∈ {0,1}) and independently `opflags` bit19 ∈ {0,1} — all 4 combinations —
  add a SEPARATE, LATER instruction (`falu2i`, `srcA_reg=3` literal, a
  second immediate `K2=20.0`) that reads register 3 again, and record its
  result too (EXP-0086's own "adjacent" methodology, generalized to also
  cross the register-field top bit against the opflags bit).
  - **CONFIRMS complementary-pair model:** the later reader's result
    depends on the JOINT state of (bit15,bit19), not on bit19 alone — e.g.
    (1,0) and (0,0) give DIFFERENT later-read outcomes.
  - **REFUTES complementary-pair model (single-bit model, i.e. EXP-0086's
    original finding stands unmodified):** the later reader's result
    depends on bit19 ALONE, identically for both bit15 values.
  - Mirrored construction for `srcB`/`(bit31,bit20)`.

**H3 — REGISTERS 64–95.** If `srcA_reg` is only 6 bits in this family, how
are registers 64–95 addressed?

- **Design:** answered by REASONING from H1's own result, not a separate
  hardware group (see §5 below for why a dedicated `falu3`-based probe was
  judged out of this experiment's time budget). If H1 confirms the current
  db.json model, H3 is trivially answered (literal field values 64–95). If
  H1 confirms a 6-bit-only model, H3 is left **UNKNOWN/OPEN** and reported
  as such, not guessed.

**H4 — CONSUMER ROUTE / LOAD-TO-ALU BLOCKER.** Does explainer's claimed
"consumer route" field (`falu2`'s `mod_hi` bits 1–3 = instruction bits
45–47) determine whether a `device_load`-produced operand can be
consumed by `falu2`/`falu2i` (EXP-0090's blocker #1)?

- **Falsifier design:** `ROUTE_LOAD` (8 cases, route 0–7): `device_load` a
  known value `V_LOAD` into a register, then `falu2(srcA=that register,
  srcB=don't-care, mod_hi=route_mod_hi(route))`, store the result.
  `ROUTE_ALU` (8 cases, same route sweep): identical construction but
  `srcA` is ALU-computed (a `falu2i` result), a same-shader-family control.
  `H4_BIT21` (2 cases): route=6 (the ALU-working default) with opflags
  bit21 set, for both LOAD and ALU sourcing.
  - **CONFIRMS the route hypothesis:** at least one route value in
    `ROUTE_LOAD` reads `V_LOAD` correctly while others do not (isolating
    which).
  - **REFUTES the route hypothesis (for this specific field/family):** all
    8 `ROUTE_LOAD` cases mismatch (read something other than `V_LOAD`,
    predicted 0.0 from the pilot) while all 8 `ROUTE_ALU` controls match —
    proving the harness/route-field wiring is sound and the LOAD path
    specifically remains blocked regardless of route.
  - A companion case (`h4_store_bridge_regstore`, grouped with `H4_BIT21`)
    tests whether `device_load`'s result can even be independently
    STORE-verified (via the — now known narrow — `extmode=2*data_reg`
    formula) for a register beyond EXP-0090's own tested range, as a
    second, ALU-independent data point on the same underlying blocker.

**H5 — GPR-SOURCED MOVE.** With H1/H2/H4 answered, retry EXP-0090 P4's
failing case (`reg_move` reading a GPR written by `falu2i`) under
candidate fixes informed by the model.

- **Falsifier design:** `move_baseline_fail_replicate` (replicates
  EXP-0090's exact failing shape, predicted to mismatch), `move_bit21_set`
  (producer opflags bit21=1 — "destination publication" hypothesis),
  `move_padding` (4 padding instructions between producer and `reg_move` —
  timing hypothesis), `move_bit21_and_padding` (both combined), and
  `move_load_sourced` (same `reg_move`, but the source register is written
  by `device_load` instead of `falu2i` — directly closes EXP-0090's own
  named open question, "whether `reg_move` can read a GPR written by
  `device_load` ... remains UNKNOWN").
  - **CONFIRMS a fix:** that specific variant's result matches its oracle
    while `move_baseline_fail_replicate` does not.
  - **REFUTES all three candidate fixes:** all four (`bit21_set`,
    `padding`, `bit21_and_padding`, and the baseline replicate) mismatch
    identically.

**H6 — FAMILY GENERALITY (bit 17 in `unpack_convert`/`cvt_i2f`).**
Answered via STATIC db.json structural analysis, not a new hardware group
— see §5 for the explicit, time-boxed scoping decision and its reasoning
(both families' bit-17-bearing byte is structurally disjoint from any
register-descriptor byte, unlike `falu2`'s bit15/bit31, which rules out
"same field, repositioned" without requiring a new splice sweep to show a
negative).

## 2. Independent / controlled variables

- **Independent:** the specific bit/field values enumerated per hypothesis
  above (`srcA_reg`/`srcB_reg` field value, `opflags` bits 19/20/21, `mod_hi`
  route bits 45–47, `reg_move` producer opflags/padding, register source
  family — ALU vs `device_load`).
- **Controlled/held fixed within each comparison:** carrier kernel and its
  measured `_agc.main` length (170 bytes, `--no-fast-math`), buffer slot
  assignment (`SLOT_OUT=0`, `SLOT_MEM=1`), the seed value `V_LOW` (30.0,
  the fixed point of `isadb.imm_encode/imm_decode(42.5)`), the later
  reader's own immediate `K2` (20.0, also an exact fixed point), dispatch
  shape (`grid=1,tg=1`), `--no-fast-math`, per-case timeout (45s).

## 3. Expected observation and refuters — summary table

| group | independent var | if current db.json model | if explainer's model | refuter (neither) |
|---|---|---|---|---|
| SRCA_PAIR/SRCB_PAIR word0 | field value ∈{3,67} | 67→0.0 | 67→30.0 | any 3rd value |
| SRCA_PAIR/SRCB_PAIR word4 | bit19/20 ∈{0,1}, crossed with field top bit | later-read depends on bit19/20 ONLY | later-read depends on the (bit15,bit19)/(bit31,bit20) PAIR | later-read independent of BOTH (never corrupts) |
| ROUTE_LOAD | route 0–7 | (no claim) | exactly one route reads `V_LOAD` correctly | all 8 mismatch identically (blocker persists) |
| ROUTE_ALU | route 0–7 | (no claim) | route never matters for ALU-sourced (explainer's own claim) | any ROUTE_ALU case mismatches (route DOES matter, contradicting explainer) |
| GPR_MOVE_RETRY | fix variant | (no claim) | at least one candidate fix works | all four (incl. baseline) mismatch identically |

## 4. Known confounders

- **Kernel register pressure / carrier complexity** demonstrably affects
  splice reliability (pilot incident, §0.2) — mitigated by using a
  carrier structurally close to EXP-0090's own proven-working
  `carrier_p2.metal`, and by `baseline.py` re-deriving `CARRIER_LEN`/slot
  facts fresh (no hardcoded trust) immediately before capture.
- **`device_store`'s word-addressing unit** (`idx_off` unit = 16 bytes = 4
  words, EXP-0090's own HW-VALIDATED formula) is easy to mis-apply (the
  pilot phase did, once, and caught it via an all-zero second-word
  readback that made no sense against a working first word) — every case
  here uses `idx_off ∈ {0,1}` exclusively, decoded via a single documented
  formula (`word_index = idx_off*4`) in `casematrix.py`'s own docstring.
- **Minifloat immediate rounding** (`isadb.imm_encode`/`imm_decode`,
  EXP-0006): `V_LOW`/`K2`/`V_ALU` are all computed via `H.imm_value()` (a
  fixed point of that codec), never a raw literal, so the oracle can never
  disagree with what the assembler actually encodes.
- **Register-file leftover state / non-zero "unwritten" reads**: the pilot
  phase observed `reg_move`'s failure mode reads back a small, denormal,
  NON-zero bit pattern (`0x00000100`) rather than exactly 0.0 in every
  `GPR_MOVE_RETRY` variant tried — recorded and reported as an exact
  observation, not smoothed into "reads zero" by assumption.
- **Compiler-emitted vs hand-assembled bytes**: every instruction here is
  assembled via `tools/agx-isa`'s own `isadb.assemble()`, never copied from
  a captured template, and every case round-trips through
  `isadb.disassemble`+`assemble` before being accepted into the matrix
  (`isa_helpers.assert_round_trip`, called by `casematrix._case`).

## 5. Explicit scoping decisions (time-boxed, disclosed up front)

- **H3** is not given its own hardware group. The only currently-validated
  way to write a register ≥64 is `device_load` (9-bit extended dst,
  EXP-M4-13 R8), and this pilot phase independently confirmed (replicating
  EXP-0090) that `device_load`'s result cannot be reliably consumed by
  `falu2`/`falu2i` via ANY register or route. A separate high-register path
  via `falu3`'s plain 8-bit register fields is a plausible candidate but
  `db.json` flags that family's own field semantics (`op` enum values
  especially) as weakly-validated/structural-only ("op-select value
  meanings inferred") — characterizing it well enough to build a decisive,
  non-confounded H3 probe is judged to be its own multi-case undertaking,
  out of this experiment's time budget. H3 is reported `UNKNOWN/OPEN`.
- **H6** is answered via `db.json` structural analysis only (RESULTS.md):
  `unpack_convert`'s `cache` field and `cvt_i2f`'s `mode` field (both the
  byte containing literal bit 17) are structurally DISJOINT bytes from
  either family's own register-descriptor field(s) — unlike `falu2`, where
  bit15/31 sit INSIDE the register-descriptor byte. This is sufficient to
  answer "is it the same field repositioned" (no) without requiring a new
  hardware sweep; whether bit 17 has ITS OWN companion bit within its own
  byte remains open and is recommended as follow-up work, not asserted.
- **8-byte FMA / 10-byte logic tables** (explainer's two remaining tables):
  answered primarily via STATIC db.json decoding of his own example bytes
  (RESULTS.md), because (a) the 10-byte logic example does not decode
  under any of our modeled families as shown in §0.1 — a decisive negative
  in itself — and (b) no `db.json` family matches the literal "8-byte,
  same base-48-bit layout as falu2, 3rd source at bits 48–63" shape he
  describes (our own 8-byte `falu3` uses an entirely different, full-byte
  register-field layout; our 12-byte `falu3_srcmod12` matches the base
  layout but is 12, not 8, bytes) — reported as an open discrepancy, not
  papered over by guessing which of our families he means.

## 6. Environment / tool revisions

- macOS 26.6.2 (build 25G82), Apple M4 (G16G), Metal 4.
- `tools/agx-isa/isadb.py`, `tools/agxtest/agxtest.py`, `tools/shdump/*`:
  read-only, used exactly as documented in their own READMEs; not modified.
- Python 3.14 (`/opt/homebrew/opt/python@3.14/bin/python3.14`), invoked as
  `python3 -B` throughout (no `.pyc` cache writes into the tree).

## 7. Raw-record schema (frozen)

Gated (`01_results.jsonl`, byte-compared across runs): `i, name, group,
oracle, expect_match, notes, status, pipeline_source, out_hex, observed,
match`. Non-gated (`01_timing.jsonl`, NOT byte-compared):
`i, duration_ms, argv, stdout, stderr`. See `run.py`'s `SMOKE_KEYS` /
`GATED_KEYS`/`NONGATED_KEYS` for the single authoritative definition
imported by both the runner and `verify.py --selftest`.

## 8. Timeouts

Per-case hard timeout 45s (subprocess), `agxtest.py --run-timeout 30`
internal GPU timeout. Environment/build commands: 5–120s. Full run: no
overall wall-clock cap beyond the sum of 35 cases' individual timeouts
(~26 minutes worst case), consistent with EXP-0090's own precedent.
