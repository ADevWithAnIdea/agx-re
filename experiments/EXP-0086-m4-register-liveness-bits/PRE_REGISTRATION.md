# PRE_REGISTRATION — EXP-0086 M4 register-liveness/"cache" bit falsification

Filed BEFORE any splice/GPU capture (host-side pilot compiles used to LOCATE
the candidate bits and freeze the anchors below are OWN-SHADER compiles only,
no splicing, no hypothesis-confirming mutation — this is the standard
"characterize the compiler's own output" step that precedes every splice
experiment in this repo, e.g. EXP-0036/EXP-0038/RT-1a).

## 0. Why this experiment exists

`docs/isa/README.md:770` claims: *"`0x54<->0x56` cache bit = byte+2 bit 1
(instr bit 17) = a source cache / last-use hint (NOT an op change)"*. Its
**only** supporting evidence is `experiments/RT-1a-FIX/RESULTS.md` line 81:
splicing byte+2 `0x18<->0x38` on a compact float accumulate "leaves the
reduction result unchanged" — i.e. that test spliced an instruction and
re-read **that same instruction's own result**. It never checked whether a
**later, separate instruction's read of the same register** is affected.
That test is structurally incapable of detecting a liveness/last-use bit,
whose failure mode by definition is a *later* read observing a stale or
discarded value. An external compiler engineer building a NIR->Apple9 backend
from our docs independently reports that Apple9 **does** have a register
lifetime mechanism (a bit marking a use as the last use of a value, plus
operand-provenance information) and that getting it wrong causes generated
code to intermittently return stale values or not execute at all. Our
documentation currently asserts the opposite ("NOT an op change" / implicitly,
"safe to ignore"). This experiment treats the existing claim as **UNPROVEN**
and attempts to falsify it with hardware evidence a later read can actually
observe.

## 1. Candidate bits under test (located by pilot OWN-SHADER compiles)

Pilot compiles (this exact toolchain; see §5) of minimal MSL that loads a
value `v` and reads it in two separate later ALU instructions located the
following, all HW-decoded with `tools/agx-isa` (no Apple binary touched):

- **CAND_A** (primary): the **top bit of the 7-bit register-select field**
  that identifies `v`'s source register in the float-ALU 2-source family
  (`falu2i` 6B / `falu2` 6B / `falu_srcmod12b` 12B — all three share a 7-bit
  register field per `tools/agx-isa/db.json`, `srcA_reg`/`srcB_reg`, whose low
  6 bits are the register number). Empirically, across 7 independent kernel
  compiles (adjacent / near / far4 / far16 / pressure / if_boundary /
  loop_boundary), **the FIRST scheduled read of `v` after its producer (or
  after a control-flow reconverge) always has this bit SET (field value
  `|0x40`), and an immediately-following second read of the SAME physical
  register always has it CLEAR** — confirmed to track temporal read order,
  not the specific immediate operand value, by an A/B swap of the two
  constants added to `v` (`k12_faluacc2`/near/adjacent immediate-swap pilot:
  the SET/CLEAR pattern followed which read came first in the *scheduled*
  instruction stream, not which literal constant was used). This is the
  generalized analog of the `0x54<->0x56` / `0x18<->0x38` bit named in the
  claim under test: same conceptual role (a source-operand
  cache/freshness flag), different absolute bit position per instruction
  family (confirmed: instruction bit 17 in `falu2i`/`falu2` is part of the
  **opcode** `opsel` field there — flipping it changes fadd/fmul/fma — so the
  claim's literal bit-17 framing cannot be the SAME physical bit universally;
  CAND_A is bit 31 in `falu2i`'s field layout, bit 15 in `falu2`'s).
  Splice: `new_field = natural_field ^ 0x40` (register number in the low 6
  bits is preserved bit-for-bit; this is a pure register-select-field
  bit-flip, not a register-number change).
- **CAND_B** (secondary, `adjacent` kernel only): bit 0 of the `opflags`
  field on the same two instructions, which also tracked first-vs-second use
  in every pilot compile (co-varies with CAND_A in all observed compiles; we
  do not yet know if it is a redundant encoding of the same hardware bit or
  an independent one — splicing it in isolation is exactly how we find out).
- We could **not** reproduce the literal `falu_acc` compact 4-byte form (the
  RT-1a-FIX evidence instruction) in a "shared source read twice" scenario
  after three honest attempts (with and without `--no-fast-math`, straight
  reduction-chain phrasing matching RT-1a's `a2+...+a7`): the compiler always
  chose the 6-byte `falu2`/`falu2i` sibling forms instead. This is recorded
  as a **scope limitation**: we test the same-family, same-conceptual-role
  bit the compiler actually emits for this scenario, not byte-for-byte the
  `falu_acc` descriptor. See RESULTS.md for the exact wording proposed for
  `docs/isa/README.md:770` given this substitution.

## 2. Falsifiable hypotheses

- **H1 (the existing "inert" claim, restated precisely):** CAND_A (and
  CAND_B) carry no functional register-value semantics; splicing either bit,
  in any polarity, on either instruction, under any distance/pressure/
  control-flow condition below, **never** changes the value a later
  instruction reads from the shared register, and never faults/hangs.
- **H2 (the liveness/cache hypothesis, the engineer's claim):** CAND_A
  encodes a genuine last-use/source-cache marker. Specifically we predict an
  **asymmetric** failure mode (falsifiable, not just "something breaks"):
  - Forcing a read's bit to **CLEAR when it is NOT the immediately-following
    read of that register in the natural schedule** (i.e. claiming "reuse a
    cached/forwarded copy" when none is actually pending) is the
    corruption-risk direction. Predicted observable failure: the later read's
    output value differs from the independent host oracle (`casematrix.EXPECTED`),
    or the dispatch faults/hangs.
  - Forcing a read's bit to **SET when CLEAR was natural** (needlessly
    re-fetching/treating a value as fresh) is predicted to be harmless
    (correct value, possibly with a cost the black-box test cannot observe).
  - Flipping **only the producer-side occurrence** vs **only the
    consumer-side occurrence** vs **both together** (the `flip_c1`/`flip_c2`/
    `flip_both` cases) tests whether the two sides must agree.

**What CONFIRMS the existing "inert" doc claim:** every CAND_A/CAND_B case
across all 7 distance/pressure/control-flow kernels, both runs, all 3 repeats,
returns `MATCH_EXPECTED` (no fault, no value change) — i.e. H1 survives an
adversarial test that H2 predicts should break it.

**What FALSIFIES it:** any CAND_A/CAND_B case reproducibly (see determinism
criterion, §4) returns `MISMATCH_EXPECTED` or a fault/hang where the unspliced
baseline for that kernel returns `MATCH_EXPECTED`. A single non-reproducible
(intermittent) deviation is recorded as `PARTIAL`/`REFINED` evidence, not a
full falsification — see §4.

## 3. Independent / controlled variables

- **Independent:** (a) which candidate bit (CAND_A / CAND_B); (b) which site
  is spliced (c1 = the earlier read / c2 = the later read / both); (c) the
  distance and structure between the two reads (7 kernels: `adjacent`
  (0 intervening real instrs), `near` (1), `far4` (2, non-adjacent
  scheduling), `far16` (~25), `pressure` (~40 live values, ~travel distance
  372 bytes / dozens of instructions, deliberately enough concurrently-live
  register-consuming values to stress allocation — see §6 for how this was
  established), `if_boundary` (reads straddle a real runtime-conditional
  `if_push`/`pop_reconverge`), `loop_boundary` (reads straddle a real
  runtime-bounded `for` loop's push/pop_reconverge, trip count from a memory
  value, not compile-time known).
- **Controlled:** identical splice mechanism (`tools/agx-isa` decode/assemble
  round-trip, same-length splice only — the field width never changes, only
  its value); identical toolchain/target (M4/G16G, this host); identical
  `--no-fast-math` compile flag; identical grid=1/tg=1 single-thread
  dispatch; fixed, distinct, non-degenerate float32 input values per kernel
  (`casematrix.INPUTS`) so a corrupted read cannot coincidentally equal the
  correct value.
- **Paired controls:**
  - `inert_control_c1`: flips bit 0 of the presumed-inert `ctrl`/`ctrl_lo`
    tail field on c1 (a field with no assigned semantic in `db.json`,
    observed constant/zero across every pilot compile). A null result here is
    the baseline for "splicing something and observing nothing" — it must be
    null for the CAND_A/CAND_B results to be interpretable as a genuine
    negative rather than "our splice mechanism doesn't work."
  - `positive_control_c2`: redirects c2's low-6-bit register-select field to
    a **different, wrong** register (register number XOR pattern, NOT the
    liveness bit). This is predicted to **always** produce a detectable
    deviation from the expected value on the `c2_out_idx` output — it proves
    the harness (compile -> splice -> run -> readback -> compare-to-oracle)
    is actually capable of detecting a corrupted read under each kernel's
    exact register-pressure/distance/control-flow condition. Without this,
    a null CAND_A/CAND_B result would be uninterpretable ("maybe nothing can
    be detected here at all").

## 4. Determinism / intermittency protocol

Every one of the 45 case templates (9 CAND_A + 6 CONTROL per kernel x 7
kernels, minus the two non-`adjacent` kernels not carrying CAND_B, plus 9
CAND_B cases on `adjacent` only = **45 templates**) is executed **3 times**
(`REPEAT_N = 3` in `casematrix.py`), each repeat its own fresh process
(fresh `agxtest.py` invocation, fresh Metal library load, fresh command
buffer) — 135 cases per run. A case is called **deterministic** if all 3
repeats within a run return the identical `verdict`. Both runs
(`m4-20260828-run01`, `m4-20260828-run02`) execute the **full identical
135-case matrix** a second time end to end (270 device invocations total),
and `verify.py`'s cross-run gate requires the GATED result file
(`04_results.jsonl`, which excludes all timing) to be byte-identical between
the two runs — so any run-to-run non-reproducibility is itself a capture-time
FAIL, not silently absorbed. A case is honestly reported as **intermittent**
only if repeats *within* a run disagree; a case that is internally consistent
within each run but whose *aggregate* verdict differs from another case's is
not "intermittent," it is a different case.

## 5. Environment (frozen)

- Git revision: `ab874936fb258e1849b56edb5b8aa0ba98c34853` (working tree
  dirty at time of filing — pre-existing unrelated untracked files from other
  in-flight experiments per `git status`; none touched by this experiment).
- Host: this machine (Apple M4, G16G, 10 GPU cores) — the sole test target
  per `CLAUDE.md`/`CODEX.md`; A18 Pro is hands-off, no claim here is promoted
  to G17P without a recorded validation or `INFERRED` label.
- macOS: 26.6.2 (build 25G82). `xcrun --version` and `sw_vers` are captured
  verbatim into `00_inputs.json` for both runs.
- Python: 3.14.6 (host analysis/harness scripts only; no Metal shader
  toolchain dependency — compilation is `newLibraryWithSource:` at runtime
  via `tools/shdump/shdump.m`, no `metal` CLI).
- Toolchain for the splice/assemble step: `tools/agx-isa/isadb.py`
  (unmodified, read-only) — `decode_one`/`assemble` round-trip asserted on
  every anchor at case-generation time (`casematrix._decode`).

## 6. How we established the test COULD detect a liveness violation

Per the task's explicit expectation-setting: a null CAND_A/CAND_B result is
only meaningful if the harness demonstrably CAN observe a corrupted read
under each condition. Two independent proofs are built into the frozen
matrix, not asserted after the fact:

1. **`positive_control_c2`** (§3) deliberately corrupts the register-select
   field (not the liveness bit) on the exact same instruction, at the exact
   same offset, under the exact same distance/pressure/control-flow
   condition as the CAND_A test for that kernel. If this control does NOT
   show a value deviation for a given kernel, that kernel's CAND_A/CAND_B
   null results are UNINTERPRETABLE for that kernel and RESULTS.md must say
   so explicitly rather than count them as confirming H1.
2. **Register pressure was verified structurally, not assumed:** the
   `pressure` kernel's compiled form (verified in `baseline.py`'s clean
   `isadb.disassemble()` tokenization, frozen in `casematrix.ANCHORS`)
   contains ~40 concurrently-referenced float temporaries and a genuine
   `falu_acc` binary-reduction tree between c1 and c2 (dozens of
   instructions, 372 bytes of intervening code) — i.e. real, HW-confirmed
   register-file traffic between the two reads of `v`, not merely a large
   instruction count of unrelated no-ops. The `if_boundary`/`loop_boundary`
   kernels were confirmed (again via clean tokenization) to place c1 and c2
   on opposite sides of a real `if_push`/`jump_cond`/`pop_reconverge`
   sequence with a **runtime-only** branch condition/trip count (read from a
   memory buffer, not a compile-time constant), so the compiler cannot have
   statically resolved away the control flow.

## 7. Frozen case matrix

135 cases per run, generated deterministically by
`casematrix.full_case_list()` (`REPEAT_N=3` x 45 templates). The 45 templates:

| kernel | CAND_A cases | CONTROL cases | CAND_B cases | BASELINE |
|---|---|---|---|---|
| adjacent | flip_c1, flip_c2, flip_both | inert_control_c1, positive_control_c2 | flip_c1, flip_c2, flip_both | baseline |
| near | flip_c1, flip_c2, flip_both | inert_control_c1, positive_control_c2 | — | baseline |
| far4 | flip_c1, flip_c2, flip_both | inert_control_c1, positive_control_c2 | — | baseline |
| far16 | flip_c1, flip_c2, flip_both | inert_control_c1, positive_control_c2 | — | baseline |
| pressure | flip_c1, flip_c2, flip_both | inert_control_c1, positive_control_c2 | — | baseline |
| if_boundary | flip_c1, flip_c2, flip_both | inert_control_c1, positive_control_c2 | — | baseline |
| loop_boundary | flip_c1, flip_c2, flip_both | inert_control_c1, positive_control_c2 | — | baseline |

Per-case **expected observation under H1** and **refuter (= what H2
predicts)**:

- `baseline`: expected `MATCH_EXPECTED` under both H1 and H2 (sanity floor;
  a baseline mismatch invalidates that kernel's whole case group and is
  reported, not hidden).
- `candA_flip_c1` / `candB_flip_c1`: H1 expects `MATCH_EXPECTED` (bit is
  decorative). H2's refuter: if the natural c1 bit was SET ("fresh", true for
  every kernel here) and we flip it to CLEAR ("claims a nonexistent cached
  predecessor"), H2 predicts this is a plausible corruption trigger for c1's
  OWN computation (self-consistent readback), independent of c2 — recorded,
  but the decisive test is c2.
- `candA_flip_c2` / `candB_flip_c2`: **the decisive case.** H1 expects
  `MATCH_EXPECTED`. H2's refuter: forcing c2's bit from its natural value to
  the opposite is, for every kernel here except `loop_boundary`, a CLEAR
  (natural) -> SET (forced) flip — i.e. forcing "treat as fresh" where the
  compiler chose "reuse." Also test the reverse direction explicitly via
  `loop_boundary` and `if_boundary`, whose natural c2 value is already SET
  post-boundary (see §1) — for those two kernels this case tests forcing
  SET -> CLEAR *across* the branch/loop boundary, the specific adversarial
  direction predicted by H2 to be most dangerous (claiming a cached
  predecessor that cannot exist because a branch/loop intervened).
- `candA_flip_both` / `candB_flip_both`: agreement test (task item 5). H1
  expects `MATCH_EXPECTED`. H2's refuter: if the mechanism requires
  producer/consumer AGREEMENT, swapping both should behave like "both
  fresh"/"both cached" rather than restoring correctness by symmetry;
  if the mechanism is per-instruction-independent, this case's outcome
  should just be the union of the two single-flip outcomes.
- `inert_control_c1`: expected `MATCH_EXPECTED` under H1 AND H2 (this field
  is not claimed to be the liveness bit by either hypothesis). A mismatch
  here is a THIRD hypothesis (some other, currently undocumented, field is
  live) and is reported as such, not folded into the CAND_A verdict.
- `positive_control_c2`: expected `MISMATCH_EXPECTED` under BOTH hypotheses
  (detection-capability proof, §3/§6). A `MATCH_EXPECTED` here means the
  detection method itself failed for that kernel and every other case in
  that kernel's group must be treated as `UNKNOWN`, not `PASS`, regardless
  of its own verdict.

## 8. Raw-tree schema (frozen; `run.py`/`verify.py` are the executable copy)

`raw/<run-id>/{00_inputs.json,01_cases.json,02_build.json,03_dispatch.json,
04_results.jsonl,04_results_raw.jsonl,05_run_manifest.json}`.
`04_results.jsonl` is the GATED, cross-run byte-compared record (schema:
`run.CASE_KEYS`) and contains **no** timing/duration/pid/address field —
`out_values`/`expected_values`/`verdict`/`mismatch_indices` only, computed
against the fixed independent oracle `casematrix.EXPECTED`, not against a
run-to-run "whatever the GPU said." `04_results_raw.jsonl` is the append-only,
**non**-gated per-repeat record (schema: `run.CASE_RAW_KEYS`) carrying
`duration_ms`/`stdout`/`stderr`/`exit`/`timed_out`/`exception` — never
byte-compared across runs. `verify.py --selftest` proves this distinction
with a synthetic tree whose two runs differ ONLY in raw timing and must
still PASS the cross-run gate (case `cross_run_timing_only_differs_still_passes`).
`verify.py --seqtest` separately proves the contracted gate ORDER
(PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT) is walkable end to end and that
each gate is runnable/satisfiable exactly where the capture sequence invokes
it. Both `--selftest` and `--seqtest` are required (and re-run) immediately
before every capture, in every tree state, per `run.py`.

## 9. Timeouts

`env_command`=10s, `host_build`=60s, `baseline`(host compile+tokenize,
7 kernels)=180s, `case_process`=60s (per `agxtest.py` invocation; compile
<=120s and dispatch <=300s ceilings from the dispatch brief are both well
inside this per-case wall-clock budget for these small single-thread
kernels), `smoke_process`=60s.

## 10. Known confounders

- Compiler scheduling is **not** source order (established in pilot: e.g.
  `if_boundary`'s syntactically-first `x1 = v+10.0f` is scheduled by the
  compiler AFTER the `if`/`pop_reconverge`, not before it) — every anchor
  below is a FROZEN byte offset from the actual compiled output, verified
  fresh by `baseline.py` before every capture, not an assumption from source
  order.
- The minifloat immediate encoding for `10.0f`/`20.0f`/`100.0f` could in
  principle be inexact; not a concern here since these are small exact
  integers and RT-1a-FIX Item 3 already HW-validated the immediate decode
  path for small integer constants — the independent oracle in
  `casematrix.EXPECTED` uses ordinary float32 arithmetic, matching what the
  compiled immediate values decode to.
- A splice that faults the whole command buffer (`CMDBUF_ERROR`/`HANG`)
  produces NO output at all for that case — `run.py` records this as
  `verdict=FAULT`, distinct from `MISMATCH_EXPECTED` (wrong value) and from
  `MATCH_EXPECTED`; both are treated as evidence, per CODEX, and are not
  silently dropped.
- `falu_srcmod12b` (the `loop_boundary` c1 instruction) is a 12-byte extended
  form with an undecoded 48-bit `ext_srcmod` tail; we only ever touch its
  named `srcA_reg`/`ctrl` fields via `isadb.assemble`, never the raw tail, so
  no unintended byte outside the intended field ever changes (asserted by
  `casematrix._splice_field`'s byte-diff against the field's declared width).

## 11. Frozen anchors (verbatim, cross-checked live by `baseline.py` every run)

See `casematrix.py::ANCHORS` for the full machine-readable table. Summary
(offset is the byte offset into `_agc.main`; `v_low6` is the register number
common to both c1 and c2's register-select field):

| kernel | c1 offset/mnemonic | c2 offset/mnemonic | v_low6 | c2_out_idx |
|---|---|---|---|---|
| adjacent | 0x12 falu2i | 0x18 falu2i | 1 | 1 |
| near | 0x2a falu2i | 0x40 falu2i | 1 | 1 |
| far4 | 0x72 falu2i | 0x84 falu2i | 1 | 1 |
| far16 | 0x192 falu2i | 0x22c falu2i | 2 | 1 |
| pressure | 0x41e falu2i | 0x592 falu2i | 2 | 1 |
| if_boundary | 0x54 falu2 | 0x66 falu2i | 0 | 0 |
| loop_boundary | 0x94 falu_srcmod12b | 0xb2 falu2i | 1 | 0 |

Note `c2_out_idx` is 0 (not 1) for `if_boundary`/`loop_boundary`: the
compiler rescheduled the syntactically-first variable (`x1`) to be the
instruction sharing `v`'s register with the in-scope/pre-boundary read; see
§10.

## 12. Clean-room provenance (this filing)

```text
Clean-room provenance: OWN-SHADER
Inputs inspected: our own kernels/*.metal, compiled via tools/shdump
  (newLibraryWithSource:), decoded with tools/agx-isa (read-only). No Apple
  binary, archive, BO, or command-stream inspection.
Apple binary introspection: NONE
Reproduction: python3 -B baseline.py --bin-dir <bindir> --out <report.json>
  (host-only, no GPU); python3 -B casematrix.py (case matrix summary)
Evidence: casematrix.py::ANCHORS (frozen anchors), this file (hypotheses)
```
