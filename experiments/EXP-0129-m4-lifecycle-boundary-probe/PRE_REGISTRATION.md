# PRE_REGISTRATION -- EXP-0126 M4 register-lifecycle boundary probe

Pinned revision: `633cd06b0c9890bc641128ca7b49ff66eee41cb1` (dirty tree at
pre-registration time: other in-flight sibling experiment directories only,
none touching this experiment's own files -- SUBAGENT_BRIEF.md's own rule,
"a capture is valid if the authored blob hashes match; repo HEAD moving
because a sibling experiment landed is not contamination").
Target: **local Apple M4 / G16G only**. No A18 Pro access (hands-off, user
directive 2026-08-27). No M5 evidence used anywhere.

This experiment closes the three remaining unknowns in the register-
lifecycle arc (`docs/isa/register-move-and-liveness.md`,
EXP-0086/0089/0099/0113/0119): **H1** (do bits 15/31 stay HW-tested inert
under axes EXP-0119 did not reach), **H2** (is the literal-bit-17-position
mechanism one thing or several, via a genuinely discriminating test, not
more instances of the same test), **H3** (root-cause the EXP-0119-vs-
EXP-M4-14 ibitcount contradiction on M4 alone).

## 0. Pilot phase (informs this contract; not itself evidence)

Extensive host+hardware piloting (work/pilot_*, not committed as evidence,
per this project's standing convention -- EXP-0111/EXP-0119 piloted the
same way) shaped every case below and caught four real bugs before this
contract was frozen:

1. **Fragment-stage MODE-B splice target not observably live.** A first
   attempt at an H1 fragment-stage axis (kernels/fs_adjacent.metal,
   harness/fsrun.m) located a real compiler-emitted falu2 instruction whose
   srcA_reg field is genuinely top-bit-set (0x40, addressing r0/`v`) inside
   `_agc.main.constant_program` (NOT `_agc.main` -- fragment-stage code is
   split across two regions differently than compute). A positive control
   (changing the SAME field's low bits, expecting a different value) did
   NOT change the rendered pixel, in either of two independent
   constructions (a saturated-output pilot and a properly [1/64]-scaled
   one) -- meaning the located instruction is not demonstrably on the path
   to the observable output within this experiment's time budget.
   **Consequence: H1's fragment-stage axis is NOT REACHED** (disclosed, not
   faked) -- see RESULTS.md Limitations. `kernels/fs_adjacent.metal` and
   `harness/fsrun.m` (adapted from EXP-0111/EXP-0091's own fsrun.m, with a
   clean-room fix removing its `NSTemporaryDirectory()`/system-`/tmp` use)
   are retained for provenance/audit but exercised by NO case in the frozen
   matrix.
2. **CF-boundary transcription bug.** The first hand-transcription of
   EXP-0112/EXP-0090's own `build_cf_program` (into
   `isa_helpers.build_cf_topbit_program`) had one wrong opflags nibble
   (`1` instead of `2`) on the untouched sibling instruction. Caught by a
   byte-exact diff against EXP-0112's own `cf.py::build_cf_program` output
   BEFORE any hardware run (`srcA_reg_byte=0x41` must reproduce that
   function's bytes exactly, and now does).
3. **`falu2i` with a load-sourced operand requires `mods=0xC0`**
   (EXP-0101's own already-published finding). An early H1_LOAD pilot used
   the naive `mods=0` default and silently read zero for every case
   regardless of field value -- traced to this missing bit pair, not a
   bit-15/31 effect.
4. **`agxtest.py --splice SYM@OFF=HEX`'s `OFF` is relative to the symbol
   region**, not the archive's absolute file offset. An early H3_MODEB
   pilot used the absolute offset (computed via `agxparse.py --locate`) and
   spliced past the end of a 44-byte `_agc.main`, producing an all-zero
   readback at every grid size that briefly looked like (but was not) a
   genuine dispatch-shape effect.

## 1. H1 -- bits 15/31 (`falu2`-family `srcA_reg_top`/`srcB_reg_top`) in
new axes

**Established (do not redo):** HW-tested inert for addressing and
retention in `falu2`, `falu2i`, `falu2_ext` (both slots), `falu3_srcmod12`
(both slots), and under 15-deep register pressure (EXP-0099, EXP-0119).

**Hypothesis (H1-null, the standing account):** the field's top bit
remains inert for addressing (a value with the top bit set reads the SAME
register as the same value with it clear) and for retention (the SAME
instruction's own retention-control field -- `opflags` bit19/20, or the
skeleton's structurally-analogous position -- alone decides whether a
later reader is corrupted, regardless of the top bit) in every new axis
below. Role remains `UNKNOWN` if confirmed inert (a bounded reserved-space
statement, not a claim of having found the bit's true purpose).

**Falsifier:** ANY axis where flipping ONLY the top bit (low 6 bits held
fixed) changes the OWN result (addressing) or the LATER-READ result
(retention) from what the H1-null hypothesis predicts.

| group | axis | construction | own-result probe | later-read probe |
|---|---|---|---|---|
| H1_CF | real loop+if/else control-flow boundary | EXP-0112/EXP-0090's own byte-for-byte skeleton (`carrier_cf.metal`), varying ONLY the "arm_true" falu2i's `srcA_reg` (0x41 baseline vs 0x01 top-bit-cleared) | TRUE-arm parameters (a=90,n=10) select the field-varied instruction's own result into the store | FALSE-arm parameters (a=10,n=5) select the UNTOUCHED sibling's result -- a second, independent, later reader of the SAME register (r1/acc), executed immediately after the field-varied instruction, before isel10 overwrites r1 |
| H1_LOAD | operand provenance = `device_load` (EXP-0101 bridge formula: `extmode=2*target_register`, `dst_lo/dst_ext9=(1,1)`), not ALU-write | field ∈ {7, 71} (71=7+64, top bit set) on the falu2i reading the loaded register (`mods=0xC0` required) | word0 = falu2i's own result | word4 = a second, independent falu2i reading the same register again |
| H1_HALFWIDTH | destination/operand width = b16 (`srcA_size=0`) instead of the established b32 | field ∈ {3, 67} at b16 throughout | word0 | word4 (EXPLORATORY oracle -- see pilot note 5 below) |
| H1_PRESSURE | ~40 simultaneously-live registers (r16..r55, `device_load` into each), pushing the highest live index near EXP-0112's own 64-alias boundary (device_load consumer register aliases R mod 64 for R in [64,112]) | field ∈ {3, 67} on r3 (untouched by the pressure loads), standard H1 construction | word0 | word4 |
| (not reached) | fragment stage vs compute | -- | -- | -- disclosed, see pilot note 1 |
| (not reached) | uniform-register operand class | -- | -- | disclosed as EXP-0119 already did: no validated construction exists for this axis anywhere in the project |

5. **H1_HALFWIDTH pilot note (recorded before the gate, not chased
   further):** at b16, a seed-then-immediate-read-back diagnostic (no
   intervening instruction) correctly returns 30.0, but the SAME
   two-instruction H1 construction (seed, then a SECOND b16 instruction
   reading the seed back) reads 0.0 in ALL FOUR (field, retention-bit)
   combinations -- an anomaly independent of both variables under test.
   This group's oracle is therefore `None` (EXPLORATORY): the case record
   itself, and cross-case comparison (are all 4 combinations
   byte-identical to each other), answers the narrow H1 question; the
   anomaly is reported as OBSERVED/UNINTERPRETED, not silently folded into
   an "inert at b16" claim.

## 2. H2 -- is the literal-bit-17-position mechanism one thing or several?

**Established (do not redo):** EXP-0119 found THREE distinct own/later
signatures across four families at this literal position (or its
structurally analogous position): `unpack_convert`/`cvt_i2f` (bit-dependent,
corrupts own+later), `falu2`-family `opflags` (bit-dependent, corrupts
later only), `ibitcount`'s `cache` (bit-INDEPENDENT -- own always correct,
later ALWAYS corrupted regardless of the bit), `device_store`'s
`addr_mode` (fully inert).

**This experiment's discriminating question (per the dispatch, not
answered by "more instances"):** for `ibitcount` specifically -- is the
"unconditional" later-read corruption because this family has NO software
release control (a genuinely different, hardwired mechanism), or because
the real release-control bit for THIS family's encoding sits at a
DIFFERENT literal position than `cache`/bit17 (the same underlying
release-concept, relocated)?

**Falsifier for "hardwired, no control" (H2-null):** ANY bit, anywhere in
ibitcount's non-match-forced "mod"-typed fields (`op_enable` bits other
than the established compute-enable bit1; `srcdesc` bits other than the
established GPR-read-enable bit6; `tail`, fully uncharacterized), that
changes the later-read outcome from unconditional-corruption to
conditional-or-retained, WITHOUT also breaking the own-result (own-result
breaking too would indicate a degraded/non-GPR read, a confounded
"nothing to release" case, not a clean release-control bit).

| group | construction | falsifier check |
|---|---|---|
| H2_BYTESWEEP | XOR each individually-free bit of `op_enable`(7 bits)/`srcdesc`(7 bits)/`tail`(8 bits) against the anchor; own+later checked every time | 22 cases, exhaustive over every free bit in the three non-match-forced fields |
| H2_INTERACTION | with the release-control candidate found by H2_BYTESWEEP's own pilot (srcdesc bit4) held at its "retains" setting, sweep `cache`/bit17 itself | does `cache` regain a role once the real control bit is at its non-releasing setting, or stay independently inert? |
| H2_LATERWRITE | corrupt (cache irrelevant either way), then either go straight to the later reader or rewrite the register first | does a fresh, ordinary rewrite restore access (falu2's EXP-0119 H4.2 signature) for ibitcount's own corruption too? |
| H2_DISTANCE | 0/1/4 throwaway intervening instructions between the ibitcount producer and the later reader | does the corruption depend on distance (a pipeline-hazard account) or is it distance-invariant (matching falu2's own CandB finding, EXP-0089)? |

**Pilot finding (drives H2_INTERACTION's design, stated here before the
gate so the formal run is a confirmation, not a fishing expedition):**
`srcdesc` bit4 (anchor `0x5c` has bit4 SET; the anchor is EXP-M4-14's own
HW-VALIDATED value) flips the later-read outcome from corrupted (20.0) to
RETAINED (50.0) while leaving own-result CORRECT (popcount=6) either way --
a clean, non-confounded, bidirectional release-control signature,
DIFFERENT from bits 0/3 of `srcdesc` and bit2 of `tail`, which break
own-result too (a confounded "degraded GPR read" pattern, not a clean
release toggle). H2_INTERACTION's own falsifier: with srcdesc bit4 cleared,
does `cache` now matter?

## 3. H3 -- A18-vs-M4 ibitcount discrepancy

**Established (do not redo):** EXP-M4-14 (A18 Pro, real compiled
`k_popcount` kernel, device_load-sourced input, real 4-thread dispatch)
found `cache`=stale (bit17=0) breaks the stored popcount. EXP-0119
(M4, hand-built MODE A program, ALU-immediate-seeded register, grid=1
single lane) reproduced EXP-M4-14's OWN literal anchor bytes and found NO
effect. EXP-0119 disclosed, not resolved, the discrepancy and named the
confound it could not rule out: "a dispatch-shape (grid/thread-count/
real-vs-single-lane) confound... cannot be ruled out with the tooling
used here."

**Hypothesis space (the three candidates the dispatch named):**
(i) genuine G17P-vs-G16G microarchitectural difference; (ii) an error in
the A18 record; (iii) a context difference that makes both records
correct.

**This experiment's method:** vary dispatch shape (grid=1 vs grid=4) and
operand provenance (ALU-immediate-seeded vs device_load-sourced) ONE AXIS
AT A TIME, entirely on M4 (no A18 access needed or used), to determine
which axis (if either) reproduces the A18 "breaks" signature.

**Falsifier for "dispatch shape is the deciding axis":** if EXP-M4-14's
own literal anchor bytes, spliced into a fresh M4 compile of the SAME
own-MSL corpus file, give the SAME "no effect" result as EXP-0119 at
grid=1 vs a "breaks" result at grid=4 (holding operand provenance fixed --
`k_popcount` is always device_load-sourced), dispatch shape explains the
discrepancy.

**Falsifier for "operand provenance is the deciding axis":** if a MODE A
hand-built ibitcount reading a device_load-sourced register (not
ALU-seeded) shows the "breaks" signature AT GRID=1 (i.e. WITHOUT varying
dispatch shape at all, matching EXP-0119's own single-lane shape exactly),
while the SAME construction with an ALU-seeded register does not, operand
provenance explains the discrepancy independent of dispatch shape.

**Pilot finding (drives the verdict, stated here before the gate):** BOTH
falsifiers for "dispatch shape alone" were checked and REFUTED in the
relevant direction, while the operand-provenance falsifier was CONFIRMED:
EXP-M4-14's own literal bytes on `iunary_popcount.metal` break at BOTH
grid=1 AND grid=4 (dispatch shape does not gate the effect); a MODE A
hand-built program with a device_load-sourced register breaks AT GRID=1
(matching EXP-0119's own dispatch shape exactly), while the SAME
construction with an ALU-seeded register (EXP-0119's own construction,
independently re-run in this experiment's own tree) does NOT break, at
EITHER grid size. **Operand provenance, not dispatch shape, is the
deciding axis** -- see H3_MODEB/H3_MODEA below and RESULTS.md for the
full, gated confirmation.

| group | construction | axis varied | axis held fixed |
|---|---|---|---|
| H3_MODEB | EXP-M4-14's own literal anchor bytes, MODE B splice into a fresh M4 compile of `iunary_popcount.metal` (verbatim from EXP-M4-14's corpus) | dispatch shape (grid 1 vs 4) | operand provenance (always device_load, real per-thread `a[i]`) |
| H3_MODEA | MODE A hand-built ibitcount | operand provenance (ALU-seeded vs device_load-sourced) x dispatch shape (grid 1 vs 4, all lanes running the IDENTICAL tid-independent program) | -- (full 2x2 crossing both axes) |

## 4. Confounders / limitations disclosed up front

- H1_CF/H1_LOAD/H1_HALFWIDTH/H1_PRESSURE/H2_*/H3_MODEA's register-field
  addressing rests on formulas this project ALREADY independently
  HW-validated in prior experiments (EXP-0099, EXP-0101, EXP-M4-14) -- this
  experiment does not re-derive them, only re-confirms via
  `baseline.py`/pilot that they still tokenize/compile identically on this
  pinned revision.
- H3_MODEA's grid=4 cases have every lane write to the SAME fixed output
  word (no per-lane addressing constructed) -- a deliberate concurrent
  same-address race, safe here ONLY because every racing lane computes the
  IDENTICAL value (no per-lane divergent input in the hand-built
  instruction stream); this answers "does own-result depend on provenance
  x dispatch shape", not per-lane output separation (H3_MODEB covers real
  per-thread divergent addressing).
- No case in this matrix touches EXP-0089's known GPU-hang field (the
  12-byte extended-ctrl form inside a real loop) -- there is deliberately
  no designated hang-candidate case; every case's failure mode is bounded
  by the standing per-case (60s)/agxtest (45s) timeouts regardless.
- H1's fragment-stage and uniform-register-operand axes are NOT REACHED
  (see pilot note 1 and the H1 table) -- disclosed, not silently dropped.

## 5. Standing gates

`verify.py --selftest` (structural, no GPU); `--seqtest` over
PRE_GPU/RUN01_PRESENT/RUN02_PRESENT; a NON-RECORDED smoke case (index 0)
before `raw/` is created; `--between-runs` gated on authored-file hashes
ONLY, never live `git HEAD`; `--captured`, requiring `01_results.jsonl`
BYTE-IDENTICAL across both independent runs (gated keys only --
`duration_ms`/`argv`/`stdout`/`stderr` are non-gated, recorded in a
sibling `01_timing.jsonl`). Two runs: `m4-20260828-run01`,
`m4-20260828-run02`. Append+fflush+fsync per record. Never reuse a run id.
No post-capture repair.
