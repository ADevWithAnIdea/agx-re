# RESULTS — EXP-0104 M4 control-flow & SIMD/quad semantics

**Target: local Apple M4 (G16G) only.** macOS 26.6.2 (25G82), Metal 4, 10 GPU cores.
**No A18 Pro/G17P claim anywhere in this document.** Two capture runs from
byte-identical authored source (pinned revision `0f1af7fa1d3e21a9996c3b49d7d91f6377427225`,
see `CAPTURE_CONTRACT.json`): `raw/m4_20260827_run01.jsonl` /
`raw/m4_20260827_run02.jsonl` (+ `.nongated.jsonl` companions), 92 cases each.

**Cross-run gate: PASS, 0 gated-field issues** (`harness/verify.py --captured` — every
one of the 92 cases' STATUS/verdict/RESULT/splice-note fields is byte-identical
between the two runs; `gputime_ns` differs in 81/92 cases, confirming the
gated/nongated split is real, not vacuous). **Both runs: 71 OK/MATCH, 0 mismatch,
4 contained faults (`CMDBUF_ERROR`), 1 contained hang (recovered by an 8s timeout,
zero host impact), 16 structural/no-single-value-oracle cases (all `STATUS OK`).**
`verify.py --selftest` 103/103 PASS. `verify.py --seqtest` 5/5 PASS at every state
(`PRE_GPU` before either run, `RUN01_PRESENT`, `RUN02_PRESENT`). `--smoke` PASS
(non-recorded, ran before any `raw/` file existed). **Zero device wedges; `macvdmtool`
never invoked.**

## Headline verdicts

| item | verdict | evidence class |
|---|---|---|
| **CF-01** (arbitrary reducible if/else expressible) | **YES, with a sharp structural correction** — reducible if/else IS fully expressible by the decoded ops, but the compiler uses TWO qualitatively different lowerings (pure predication with zero branch ops, vs. real `icmp_pred`+`if_push`/`pop_reconverge`) depending on whether the region contains `return`/`break`/`continue`, not depending on nesting shape | `HW-PROBE`/`OWN-SHADER`, 8 shape kernels, 0 tokenizer leftover, all HW-run and oracle-matched |
| **CF-02** (nested loops with break+continue, no hidden helper) | **YES** — `break` and `continue` compose correctly in one data-dependent loop, no undecoded residue | `HW-PROBE`, oracle-matched |
| **CF-03** (max safe reconvergence nesting depth) | **NO FAILURE OBSERVED up to the tested maximum** — nested if/return to depth 128, and pure nested-loop structural depth to 64, both 100% correct; report as "≥128" / "≥64", NOT as a discovered ceiling | `HW-PROBE`, 21 depth points, all MATCH |
| **CF-04** (divergent return vs ordinary branch, distinct lowering) | **YES, decisively** — a `return` forces real mask push/pop machinery (13 instructions incl. `icmp_pred`/`if_push`/`pop_reconverge`); the semantically-equivalent branch WITHOUT `return` collapses to pure predication (8 instructions, ZERO mask ops); neither uses the `0x8f` subroutine-call marker | `OWN-SHADER-DIFF` (compile-only structural, clean tokenization both sides) + `HW-PROBE` correctness |
| **CF-05** (independently addressable predicate file) | **NO** — the `icmp_pred` `dst_pred` nibble is real and load-bearing (HW-splice-proven) but the compiler NEVER emits a nonzero value (0/18+ compiled instances across depth 1–16 and an if-in-else shape), and splicing it nonzero does not "address a different slot" cleanly — it silently corrupts the branch outcome (two distinct corruption signatures observed, value-dependent) | `HW-VALIDATED` (splice + downstream-read, not just the spliced instruction's own result) |
| **CF-06** (predicate allocation/lifetime known enough for an allocator) | **YES, but the answer is "there is no allocation to do"** — always emit `dst_pred=0`; the real nesting/lifetime resource is the `if_push`/`pop_reconverge` mask stack tested under CF-03, not a predicate register file | same evidence as CF-05 + CF-03 |
| **branch reach** (not numbered; part of CF-01/02 core questions) | Encoding is a 48-bit signed field, but the PRACTICAL valid range is far narrower than the encoding and highly non-contiguous: a ±8-byte perturbation from a valid target already faults or hangs; a +4096B perturbation landing past the code extent runs to completion with `STATUS OK` but SILENTLY ZEROED output (no fault) | `HW-VALIDATED` splice, 6 boundary points + baseline |
| **SIMD-01** (width always 32) | **YES, and stronger than expected** — `threads_per_simdgroup` reports the fixed constant 32 even for a PARTIAL (16-real-thread) final simdgroup at tg=48; it is an architectural constant, not an occupancy count. Fragment-stage width sweep is explicitly **DEFERRED** (see Deferred section) | `HW-PROBE`, compute only |
| **SIMD-02** (ballot exactly 32 bits, one stable bit-to-lane map) | **YES** — 3 genuinely divergent predicates (derived from `thread_position_in_grid`), every lane reads back the identical 32-bit mask, bit `i` = predicate(lane `i`) exactly | `HW-PROBE`, 3/3 MATCH |
| **SIMD-03** (shuffle/broadcast/rotate/fill out-of-range definition) | **Defined, deterministic, NOT a simple wraparound, and NOT uniform across the shuffle family** — `simd_shuffle(v,idx)` dynamic form: idx≥32 behaves as `idx & 0x1C` (only bits 2–4 selected; bits 0–1 and ≥5 dropped), fitting all 12 tested out-of-range points with zero exceptions; `simd_shuffle_xor`/`quad_shuffle` dynamic forms: out-of-range mask/idx instead returns a hard ZERO on every lane (a different failure mode) | `HW-PROBE`/`OWN-SHADER`, 28 swept points, fully reproduced across both runs |
| **SIMD-04** (scans/reductions correct under partial/divergent activity) | **YES** — exclusive/inclusive prefix-sum and reduction restricted to the active (even-lane) subset match a closed-form active-lane-order oracle exactly; masked-off lanes contribute nothing | `HW-PROBE`, MATCH |
| **SIMD-05** (quad numbering + horizontal/vertical/diagonal mapping) | **YES, fully resolved** — xor-mask 1 = horizontal (x^1,y), 2 = vertical (x,y^1), 3 = diagonal (x^1,y^1); within-quad linear order is row-major (0=top-left,1=top-right,2=bottom-left,3=bottom-right); `quad_shuffle_up/down`'s "fill" clamps at the quad's own lane-0/lane-3 boundary, all confirmed on real 4×4 render-target geometry | `HW-PROBE`, 6 fragment kernels, full 16-pixel tables |
| **SIMD-06** (barrier compiles to no instruction, lockstep) | **YES, unconditionally, for every memory-class variant tested** — `simdgroup_barrier(mem_none)`, `(mem_threadgroup)`, and `(mem_device)` all compile BYTE-IDENTICAL (46/46 bytes) to no barrier at all — stronger than `threadgroup_barrier`, which EXP-0093 showed DOES add a real instruction even for `mem_none` | `OWN-SHADER-DIFF` structural (0 GPU risk) + functional correctness (see caveat in item text) |
| **SIMD-07** (helper lanes included/excluded correctly) | **PARTIAL, with a genuinely surprising refutation** — `simd_active_threads_mask()` does NOT exclude a just-discarded neighbor: the low-16 raw mask bits are byte-identical (`0xFFFF`) with and without the discard. Combined with EXP-0091 (data ops include the demoted lane), the full picture is: **helper lanes are included by BOTH data-movement AND vote-class ops tested here** — narrower hypothesis (that vote ops exclude helpers) is REFUTED, not confirmed | `HW-PROBE`, 4 fragment kernels incl. a raw-bitmask diagnostic |

---

## Response blocks

Template per `APPLE9_RE_IMPLEMENTATION_GAPS.md`'s "Required response format". `Evidence:` boxes checked reflect what was actually done in THIS experiment.

### CF-01 — Can arbitrary reducible NIR `if`/`else` control flow be expressed using the decoded predicate and reconvergence operations?

```text
Status: [x] Closed (for the tested shape corpus)  [ ] Open  [ ] Partial  [ ] N/A
Answer: [x] Yes  [ ] No  [ ] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both
Evidence: [x] independently assembled HW execution (own-MSL, HW dispatch)  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [x] encode/decode round trip (clean tokenize)
          [x] own-MSL byte diff only                 [ ] corpus inference only
```
**OBSERVED.** 8 authored shapes — diamond join (`cf_shape_diamond`), 5-way
if-elseif chain (`cf_shape_elseif`), if-nested-in-else (`cf_shape_if_in_else`),
21-point nested-if/return depth sweep (`cf_ifnest_*`, depths 1–128), and the
`predalias`/`plain_join` two-nested-loop shape — all tokenize with the DB's
existing decode set at **0 leftover bytes** (verified via `tools/agx-isa/agxisa.py
tokenize`, read-only) and all HW-run outputs exactly match a Python host oracle,
92/92 relevant cases, both runs byte-identical.

**INTERPRETED — the sharp finding.** The decoded op set expresses reducible
if/else via **two structurally different lowerings selected by the presence of
`return`/`break`/`continue`, not by nesting depth or shape**:
- **Pure predication (no branch at all):** `plain_join` (ordinary if/else, no
  return) tokenizes to **8 instructions, zero `icmp_pred`/`if_push`/
  `pop_reconverge`** — a compare-select (`isel8`) only.
- **Real branch/mask-stack machinery:** `ret_early` (semantically similar
  values, but has a `return`) tokenizes to **13 instructions including
  `icmp_pred`+`if_push`+`pop_reconverge`**.
An INITIAL `predalias` kernel (two nested if/else regions, each containing a
data-dependent loop, but **no return/break/continue anywhere**) was designed
specifically to force two simultaneously-live predicates for the CF-05 splice
test, and instead tokenized to **ZERO `icmp_pred` instances** — fully
predicated even with inner loops. This is recorded as a genuine negative
result (see PROGRESS.md), not discarded: it is itself evidence for the
CF-01/CF-04 boundary rule above, and it is why the CF-05 splice target was
moved to `ifnest_004` instead.

**Counterexamples / untested cases:** shapes with >2 independently-live
predicates simultaneously overlapping (not return-gated) were not
constructed; a corpus-scale (hundreds of shapes) census was not run (see
`EXP-M4-13-full-corpus` for the broader compile-only census this experiment
does not repeat).

**Driver/compiler consequence:** a legalizer targeting this ISA should
recognize the "does this region need to skip to the epilogue" property (not
mere presence of divergent control) as the trigger for emitting real
`icmp_pred`/`if_push`/`pop_reconverge`; ordinary value-computing divergence
can and apparently SHOULD be lowered to predication instead, matching what
Metal's own compiler does.

---

### CF-02 — Can arbitrary nested NIR loops with `break` and `continue` be expressed without an undocumented compiler-generated helper sequence?

```text
Status: [x] Closed  Answer: [x] Yes
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution  [x] encode/decode round trip
```
**OBSERVED.** `shape_break_continue` — one data-dependent loop containing both
a `continue` (at `k==3`) and a `break` (at `k==7`) — tokenizes cleanly and its
HW output matches an exact Python re-implementation of the same control flow
(`bc_a=[0,1,2,5,8,10,3,7]`), both runs byte-identical.

**Counterexamples / untested:** multi-level nested loops each independently
using break/continue were not combined in one kernel (nesting depth itself is
covered separately under CF-03's `loopnest1`/`loopnestD` families, which do
not additionally exercise break/continue at every level).

**Driver/compiler consequence:** no dedicated "loop-exit helper" instruction
was found or needed; `break`/`continue` compose via the same `jump_cond`/
mask-pop machinery documented in EXP-0010/RT-1b.

---

### CF-03 — Is the maximum safe hardware reconvergence nesting depth known?

```text
Status: [x] Partial (bounded from below, not from above)  Answer: [x] Unknown (exact ceiling)
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution
Finite namespace: execution-mask/reconvergence stack, per-kernel-invocation scope
Maximum-valid and first-invalid tests: see table below
Failure/overflow behavior: NONE OBSERVED in tested range
```
**OBSERVED — full sweep (all 21 depth points, both runs, 0 mismatches):**

| family | tested depths | result |
|---|---|---|
| `ifnest_*` (nested divergent-`return` if-chain, real `icmp_pred`/`if_push`/`pop_reconverge` per level, per-lane genuinely divergent exit depth from a data value) | 1,2,4,8,16,32,64,96,**128** | **ALL MATCH**, both runs |
| `loopnest1_*` (pure nested-loop structural depth, trip count pinned to 1 so total work stays O(1) regardless of depth — isolates STRUCTURAL nesting from total iteration count) | 1,2,4,8,16,32,**64** | **ALL MATCH**, both runs |
| `loopnestD_*` (nested loops, genuinely per-lane-divergent trip count `(gid%3)+1` ∈ {1,2,3} at EVERY level simultaneously) | 1,2,4,8,**12** | **ALL MATCH**, both runs |

**INTERPRETED.** No hardware or compiler-imposed nesting-depth ceiling was
found within the tested range. This is reported as **"no failure observed up
to depth 128 (if-chain) / 64 (pure loop-nest structural depth) / 12
(genuinely divergent nested-loop depth)"** — NOT as "the maximum safe depth is
128/64/12". The compiler itself imposed no rejection at any tested depth
(all compiled successfully, including a 128-level-deep single kernel). This
partially but not fully closes CF-03: the finite-resource mandate's exact
ceiling is still open; a driver can safely assume depths in this tested range
work, and should treat depths beyond ~128 (if) / ~64 (loop) as **UNKNOWN, not
assumed-safe**, pending a further push (this experiment's time/risk budget
did not extend the sweep past these points; going further risks longer
per-case compile/dispatch times without new information about the exact
transition point).

**Counterexamples / untested:** true structural depth beyond 128 (ifnest) /
64 (loopnest1); mixed if+loop nesting (this experiment tested each family in
isolation); nesting combined with function calls (EXP-0035's separate,
already-bounded call-depth resource).

**Driver/compiler consequence:** a legalizer can emit at least 128 levels of
divergent-return if-nesting or 64 levels of loop-nesting without a documented
hardware ceiling being hit; if a future need arises for deeper nesting, this
experiment does not establish where it would break.

---

### CF-04 — Does divergent return require a distinct lowering from an ordinary branch to a shared epilogue?

```text
Status: [x] Closed  Answer: [x] Yes
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution  [x] own-MSL byte diff (structural pair)
```
**OBSERVED.**
- `ret_early` (`if (v>16) { o[i]=777; return; } ... o[i]=acc;`) → 100-byte
  `_agc.main`, 13 instructions, clean tokenize, uses `icmp_pred`+`if_push`+
  `pop_reconverge`. HW-run: exact match against the oracle over
  `[0,5,10,16,17,20,30,100]`.
- `plain_join` (same semantic values, NO `return`) → 66-byte `_agc.main`, 8
  instructions, clean tokenize, uses ONLY a compare-select (`isel8`) — **zero**
  mask-push/pop instructions. Same oracle, exact match.
- Neither program's tokenized instruction stream contains the `0x8f`
  subroutine-CALL/RETURN opcode (verified by full disassembly, not a raw byte
  scan) — confirming EXP-0035's finding that `0x8f` is reserved for real
  function calls, not kernel-level early exit.
- `multi_return` — **three** early-return points at three different nesting
  depths (`v>90`→1 at depth 1, `v>75`→2 and the depth-2 fallthrough→3, `v>30`
  at depth 1 again→4, else→5), all HW-run and exactly matched against a 5-way
  host oracle over `[95,80,65,45,20,61,76,30]`, both runs.

**INTERPRETED.** Divergent `return` is lowered via the SAME execution-mask
push/pop machinery as any other divergent block, NOT via subroutine
CALL/RETURN — but it is NOT free: it costs real branch instructions that the
value-only equivalent does not need at all. Multiple return points at
different depths all converge correctly onto the single shared final store
(the "epilogue"), confirming a genuinely shared epilogue rather than
per-return-point specialized code.

**Driver/compiler consequence:** lower an SSA/NIR "divergent return" as an
execution-mask-narrowing `if_push` guarding the remainder of the shader
(exactly what Metal's compiler does), reconverging at the natural function
exit; do not model it as a call-frame return.

---

### CF-05 — Are Boolean predicates stored in an independently addressable predicate file rather than ordinary GPR values?

```text
Status: [x] Closed  Answer: [x] No
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution  [x] HW splice  [x] own-MSL byte diff
Finite namespace: icmp_pred dst_pred field, byte0 high nibble, 4 bits (0-15 structurally addressable)
Maximum-valid and first-invalid tests: compiler NEVER emits nonzero (0/18+ instances); splice value 1 is already load-bearing/corrupting
Failure/overflow behavior: [x] alias/wrap (value-dependent silent corruption)  [ ] reject  [ ] fault
```
**OBSERVED — compiler census (compile-only, `OWN-SHADER-DIFF`).** Tokenizing
`ifnest_004` (4 `icmp_pred` instances), `ifnest_016` (16 instances), and
`shape_if_in_else` (2 instances) — **every single occurrence has
`dst_pred=0`.** 18/18, zero exceptions, across nesting depths 1–16 and an
asymmetric if-in-else shape.

**OBSERVED — HW splice (`HW-VALIDATED`, downstream-read not self-read).**
`ifnest_004`'s FIRST `icmp_pred` (`_agc.main` offset `0x12`, natural byte0
`0x0a` i.e. `dst_pred=0`) spliced to `dst_pred∈{1,5,0xf}`, baseline oracle
`[-1001,-1001,-1002,-1003,-1004,25,2500,40000]` for inputs
`[0,1,2,3,4,5,50,200]`:

| spliced `dst_pred` | observed output | verdict |
|---|---|---|
| 0 (baseline) | `[-1001,-1001,-1002,-1003,-1004,25,2500,40000]` | correct |
| **5** | `[-1001]*8` | every lane silently takes the OUTERMOST else path, regardless of input |
| **0xf** | `[-1001]*8` | identical to `dst_pred=5` |
| **1** | `[-1003,-1003,-1001,-1001,-1001,-1001,-1001,-1001]` | a DIFFERENT, non-uniform corruption — NOT "all outer-else" |

Reproduced byte-identically across both capture runs (part of the 0-issue
cross-run gate).

**INTERPRETED.** The field is real and load-bearing (splicing it changes
downstream behavior, ruling out "purely cosmetic/inert nibble"), but the
evidence refutes model (A) from `PRE_REGISTRATION.md` (a genuine
independently-addressable predicate file a compiler could allocate into):
the compiler never uses any index but 0, and forcing a nonzero index does
**not** cleanly "read a different addressed predicate slot with correct
semantics" — it silently corrupts execution (two distinct signatures observed
for `dst_pred=1` vs. `{5,0xf}`, consistent with the general
"wrong-operand-field → silent zero/misroute, not a fault" pattern documented
in `docs/isa/register-move-and-liveness.md`). The most defensible reading:
**`if_push`'s predicate consumer is NOT parameterized by an independent
address at all** (or is parameterized in a way this experiment's single-value
splices do not cleanly characterize) — the nibble is closer to an opcode/mode
sub-field than a GPR-like index, even though it occupies the identical
bit-position convention as a real GPR-select nibble elsewhere in the ISA
(`0x?2` family, EXP-M4-01). This directly refutes the "independently
addressable predicate file" hypothesis in CF-05's question.

**Counterexamples / untested:** `dst_pred` values 2,3,4,6–0xe were not
individually spliced (time-boxed to 3 representative points: smallest nonzero,
a mid value, the maximum); the exact mechanism distinguishing `dst_pred=1`'s
corruption from `{5,0xf}`'s corruption is UNKNOWN and not further isolated.

**Driver/compiler consequence:** **always emit `dst_pred=0`** for `icmp_pred`,
exactly matching observed compiler behavior. Do not attempt to allocate
distinct predicate indices for concurrently-live conditions; there is no
evidence this is a supported operation, and initial evidence it is actively
unsafe.

---

### CF-06 — Are all predicate-file allocation and lifetime restrictions known well enough for a register allocator or late predicate allocator?

```text
Status: [x] Closed  Answer: [x] Yes (the answer is "there is nothing to allocate")
Applies to: [x] M4/G16G
Evidence: shared with CF-05 (HW splice) and CF-03 (128-level-deep census)
Lifetime, destruction, and reuse semantics: dst_pred is always slot 0, single-use,
  immediately consumed by the adjacent if_push; the real nesting/lifetime resource
  is the if_push/pop_reconverge mask STACK (LIFO by construction: push on if_push,
  pop on pop_reconverge, walked correctly to depth 128 in the CF-03 sweep).
```
**OBSERVED.** Combining CF-05's splice result (no real addressable predicate
file; always index 0) with CF-03's depth census (128 sequential/nested
`icmp_pred`→`if_push` pairs, ALL emitting `dst_pred=0`, and all executing
correctly): there is no predicate-allocator DECISION for a legalizer to make.
The actual finite, lifetime-managed resource that DOES need tracking is the
execution-mask **stack** implied by `if_push`/`pop_reconverge`'s `scope`/
`scope_kind` fields (per `EXP-M4-13`'s "ping-pongs 0x54/0x56 with nesting
parity" observation, not independently re-derived here) — which is exactly
what CF-03's depth sweep stress-tests, and which held correct to the tested
depths.

**Driver/compiler consequence:** a "late predicate allocator" pass is not
needed for this ISA as currently understood — a legalizer should emit
`icmp_pred` with `dst_pred=0` unconditionally and rely on the hardware's own
`if_push`/`pop_reconverge` LIFO discipline (already exercised correctly to
128 levels) for nesting, rather than building a software register-allocation
model for predicates.

---

### Branch reach and target encoding (CF-01/CF-02 core-questions addendum, not a separately numbered item)

```text
Status: [x] Partial  Answer: n/a (descriptive)
Applies to: [x] M4/G16G
Evidence: [x] HW splice
Finite namespace: jump/jump_cond 48-bit signed LE byte-relative offset field
  (byte+3..+8 of the 10-byte encoding); target = jump_addr + 4 + offset
Maximum-valid and first-invalid tests: see table
Failure/overflow behavior: [x] fault  [x] alias/wrap(zero-out silent)  [ ] reject
```
**OBSERVED.** `reach_loop`'s real backward-jump `jump` instruction (located by
tokenizing the compiled bytes, not a hardcoded offset), baseline offset
**-44** (target lands at the loop head, oracle `s=s*3+1` over `a=[0..7]` →
`[1,4,13,40,121,364,1093,3280]`, exact match). Six splice deltas applied to
that baseline offset:

| delta | resulting offset | status | output |
|---|---|---|---|
| +8B | -36 | `CMDBUF_ERROR` | (fault, no output) |
| -8B | -52 | **HANG** (contained, 8s timeout, recovered) | — |
| +4096B | +4052 | `STATUS OK` | **`[0,0,0,0,0,0,0,0]`** — silently WRONG, not a fault |
| -4096B | -4140 | `CMDBUF_ERROR` | (fault) |
| +0x400000B | +4194260 | `CMDBUF_ERROR` | (fault) |
| -0x400000B | -4194348 | `CMDBUF_ERROR` | (fault) |

**INTERPRETED.** The encoding's nominal 48-bit signed range is not the
practical constraint. Even an 8-byte deviation from a valid target already
either faults (landing mid-instruction, off any real decode boundary) or
hangs (in this direction, apparently redirecting into a self-sustaining
loop). The mid-range +4096B case is the most important negative-safety
finding: it did **not** fault — the GPU executed *something* to completion
and returned `STATUS OK` with silently ZEROED output, consistent with
jumping past the actual 146-byte `_agc.main` extent into unallocated/padding
memory that happens to decode as an immediately-terminating or degenerate
sequence, rather than triggering a detected fault. **A driver must never
treat "no CMDBUF_ERROR" as proof a jump target is correct** — silent
zero-output execution is a real, HW-observed outcome for an out-of-extent
target.

**Counterexamples / untested:** the exact byte where a forward offset
transitions from "faults" to "silently completes with zeroed output" was not
bisected (six chosen points, not an exhaustive sweep); this is recorded as an
explicit residual unknown, not generalized beyond the tested deltas.

**Driver/compiler consequence:** relocatable code generation must compute
`jump`/`jump_cond` targets exactly (real instruction-boundary-aligned,
within the actual allocated code extent) — there is no soft-fail safety net;
both silent data corruption and contained hangs are live possible outcomes
of a wrong target, not just a clean fault.

---

### SIMD-01 — Is the executable subgroup width always 32 for every supported Apple9 stage and launch shape?

```text
Status: [x] Partial (compute closed; fragment/vertex DEFERRED)
Answer: [x] Yes (compute, all tested shapes)  [ ] Unknown (fragment stage, not swept)
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution
Finite namespace: threads_per_simdgroup SR; per-simdgroup, always reports 32
```
**OBSERVED.** `width_report` at tg=64 (2 full groups): `threads_per_simdgroup`
= 32 for all 64 threads. At **tg=48, grid=96** (1 full 32-thread group + 1
**PARTIAL 16-thread** final group per threadgroup): `thread_index_in_simdgroup`
correctly resets to 0..15 for the partial group,
`simdgroup_index_in_threadgroup`=1 correctly, and **`threads_per_simdgroup`
still reports 32** for those 16 real threads — the SAME constant as the full
group, not 16.

**INTERPRETED.** `threads_per_simdgroup` is a fixed architectural constant
(32), not a live occupancy count — a genuinely new fact beyond EXP-0018's
full-multiple-of-32 launch shapes.

**Deferred:** a dedicated fragment/vertex-stage width sweep (multiple render
target sizes/tile-boundary shapes) was NOT run — this experiment's fragment
cases (SIMD-05/07) incidentally show `popcount(simd_active_threads_mask())`=16
for a full undiscarded 4×4 (16-pixel) target, loosely consistent with one
32-wide group holding all 16 real fragments, but that is not a controlled
width sweep and is not promoted as a SIMD-01 finding. **Follow-up needed:** a
fragment-stage `width_report`-equivalent across several target sizes.

---

### SIMD-02 — Are subgroup ballots exactly 32 bits with one stable bit-to-lane mapping?

```text
Status: [x] Closed  Answer: [x] Yes
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution
```
**OBSERVED.** Three predicates genuinely derived from `thread_position_in_grid`
(`i%3==0`, `i%7<2`, `5<=i<19`), grid=32/tg=32 (one simdgroup). For all three,
every one of the 32 lanes' readback of `(uint64_t)simd_ballot(pred)` (low 32
bits) is **identical across the group** and exactly equals the host-computed
`Σ pred(j)·2^j`. 3/3 MATCH, both runs.

**Driver/compiler consequence:** `simd_ballot`'s bit `i` = lane `i`'s
predicate, stable and group-visible, confirming the direct NIR
`ballot`→hardware mapping needs no lane-renumbering.

---

### SIMD-03 — Do subgroup shuffle, broadcast, rotate, and fill operations define out-of-range lanes in the way required by NIR?

```text
Status: [x] Closed for the DYNAMIC (runtime-indexed) form tested; static/immediate form not retested here
Answer: [x] Yes -- defined and deterministic, but NOT what a naive model predicts
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution
Finite namespace: simd_shuffle index [0,32) valid; simd_shuffle_xor mask [0,32) valid; quad_shuffle index [0,4) valid
Maximum-valid and first-invalid tests: see tables
Failure/overflow behavior: [x] alias/wrap (simd_shuffle: partial-bit-mask alias)  [x] zero/discard (simd_shuffle_xor / quad_shuffle: hard zero)  [ ] fault
```
**OBSERVED — `simd_shuffle(v, idx)`, `v[lane]=lane`, dynamic per-lane `ushort idx` from a buffer (not a compile-time constant, so the compiler cannot reject or fold it):**

| idx | in \[0,32)? | result (all lanes agree) | `idx & 0x1C` prediction |
|---:|---|---:|---:|
| 0,1,31 | yes | 0,1,31 (exact identity) | n/a (exact path) |
| 32 | no | 0 | 0 ✓ |
| 33 | no | 0 | 0 ✓ |
| 40 | no | 8 | 8 ✓ |
| 63 | no | 28 | 28 ✓ |
| 64 | no | 0 | 0 ✓ |
| 65 | no | 0 | 0 ✓ |
| 127 | no | 28 | 28 ✓ |
| 4095 | no | 28 | 28 ✓ |
| 65535 | no | 28 | 28 ✓ |
| per-lane `idx=lane+32` | no | `lane − (lane%4)` pattern exactly matching `(lane+32)&0x1C` | ✓ (all 32 lanes) |
| per-lane `idx=lane` (identity control) | yes | exact identity | n/a |

**Model: for idx≥32, the effective source lane = `idx & 0x1C`** (only bits 2–4
of the 16-bit index are used; bits 0–1 and every bit ≥5 are ignored) — fits
**all 14 out-of-range data points with zero exceptions**, both runs
byte-identical. This is NOT modulo-32 (which would predict 33→1, 63→31,
65→1, 127→31 — all wrong) and NOT clamping, pass-through, or fault.

**OBSERVED — `simd_shuffle_xor(v, mask)`, dynamic mask:** in-range (0,1,31)
gives the exact documented xor-pairing (`[1,0,3,2,...]` for mask=1, full
reversal for mask=31). **Out-of-range (32,33,63): every lane reads a hard
ZERO** — not `lane XOR (mask&0x1C)` (which would still vary per lane), a
qualitatively DIFFERENT failure mode from plain `simd_shuffle`.

**OBSERVED — `quad_shuffle(v, idx)`, dynamic idx:** in-range (0,1,2,3) gives
the exact per-quad value. **Out-of-range (4,5,8,255): hard ZERO on every
lane**, same signature as `simd_shuffle_xor`'s out-of-range behavior.

**INTERPRETED.** Three genuinely different, each internally-consistent,
deterministic (reproduced byte-for-byte across both runs) out-of-range
behaviors exist in the SAME instruction-family group (`db.json`'s
`simd_shuffle`/`0x47`/`0xc7` byte0 group covers both `simd_shuffle` and
`simd_shuffle_xor`; `quad_shuffle` shares the group at `mode=quad`) — the
specific sub-mode changes the failure signature. None of the three is a
GPU fault; all are safe (silent, deterministic) but WRONG results for
out-of-range input, and NIR/Vulkan lowering must not assume any one of
"wrap", "clamp", "pass-through-self", or "zero" applies uniformly across the
whole shuffle family.

**Counterexamples / untested:** the STATIC/immediate-operand shuffle form
(compile-time-constant lane argument, `EXP-0018`'s original evidence) was
NOT re-tested here — this experiment's finding is specific to the DYNAMIC
(runtime-register) form, which uses a different encoding path per
`tools/agx-isa/db.json`'s "dynamic shuffle" note; `simd_shuffle_up/down`'s
documented "fill" boundary behavior (EXP-0018) was not re-swept at
out-of-range magnitudes here (only the quad-scope up/down fill was tested,
under SIMD-05).

**Driver/compiler consequence:** NIR `nir_intrinsic_shuffle` lowering must
either (a) always clamp/mask the index in software before emitting the
hardware op (safe, portable), or (b) if relying on hardware behavior for a
known-in-range-by-construction case, never assume undefined-index safety —
`simd_shuffle_xor`/`quad_shuffle` zero out silently rather than returning any
plausible fallback value.

---

### SIMD-04 — Are inclusive/exclusive scans and reductions correct for partially active and divergent subgroups?

```text
Status: [x] Closed  Answer: [x] Yes
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution
```
**OBSERVED.** `scan_divergent`: odd lanes take an `else` arm (sentinel -1,
calling NO subgroup op at all); even lanes call
`simd_prefix_exclusive_sum(1)`, `simd_prefix_inclusive_sum(1)`, `simd_sum(1)`
under the `if`. All three outputs exactly match the closed-form
active-lane-order oracle (excl/incl = 0,1,2,...,15 at positions 0,2,...,30;
reduce = 16 at every active lane), both runs.

**Driver/compiler consequence:** scan/reduce intrinsics correctly restrict to
the active execution mask with no special legalization needed for the
"some lanes skip the call entirely" divergence shape.

---

### SIMD-05 — Are quad lane numbering and horizontal/vertical/diagonal neighbor mappings completely known?

```text
Status: [x] Closed  Answer: [x] Yes
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution (fragment, real render target)
```
**OBSERVED — compute linear half (`quad_xor_map`, grid=32/tg=32):** all 5
sub-cases (`xor1`,`xor2`,`xor3`,`up1`,`down1`) exactly match a host oracle
assuming 4-consecutive-lane quads with `up`/`down` "fill at boundary" —
confirms `thread_index_in_quadgroup = lane % 4` (EXP-0018) generalizes
correctly to the full permute set.

**OBSERVED — fragment geometric half (4×4 render target, pixel `code =
x·16+y`, `f_quad_selfcode` confirms exact round-trip through the 8-bit color
channel first):**

| mask/op | reported partner (own code → partner code, sampled) | geometric mapping |
|---|---|---|
| `quad_shuffle_xor(code,1)` | (0,0)→16=code(1,0); (1,0)→0=code(0,0) | **horizontal**: `(x^1, y)` |
| `quad_shuffle_xor(code,2)` | (0,0)→1=code(0,1); (0,1)→0=code(0,0) | **vertical**: `(x, y^1)` |
| `quad_shuffle_xor(code,3)` | (0,0)→17=code(1,1); (1,1)→0=code(0,0) | **diagonal**: `(x^1, y^1)` |
| `quad_shuffle_up(code,1)` | (0,0)→0 (own, "fill"); (1,0)→0=code(0,0); (0,1)→16=code(1,0); (1,1)→1=code(0,1) | within-quad linear order = **row-major**: lane0=(x0,y0) top-left, lane1=(x0+1,y0) top-right, lane2=(x0,y0+1) bottom-left, lane3=(x0+1,y0+1) bottom-right; `up` = value from (linear index−1), lane0 fills with its own value |
| `quad_shuffle_down(code,1)` | mirror of `up` (lane3 fills with own value) | consistent with the same row-major order |

All 16 pixels checked per kernel (not just the sample above), both runs
byte-identical. Quads tile the screen in fixed, non-overlapping 2×2 blocks
aligned to even (x,y) — confirmed by (2,0)/(3,0)/(2,1)/(3,1) forming their own
self-consistent quad, independent of quad (0,0)/(1,0)/(0,1)/(1,1).

**INTERPRETED.** Full 2-D geometric quad model, HW-validated:
**xor1=horizontal, xor2=vertical, xor3=diagonal; linear lane order within a
quad is row-major (top-left, top-right, bottom-left, bottom-right); `up`/
`down` fill at the quad's own lane-0/lane-3 boundary** (matching Metal's
documented "fill" semantics, now pinned to the exact geometric lane
assignment).

**Driver/compiler consequence:** a legalizer implementing `nir_intrinsic_
quad_swap_horizontal/vertical/diagonal` can map directly to
`quad_shuffle_xor` with mask 1/2/3 respectively, with the row-major lane
convention above.

---

### SIMD-06 — Does a SIMD-group barrier compile to no instruction because all 32 lanes execute in lockstep with the required memory visibility?

```text
Status: [x] Closed  Answer: [x] Yes
Applies to: [x] M4/G16G
Evidence: [x] own-MSL byte diff (structural, 0 GPU risk)  [x] independently assembled HW execution (correctness, see caveat)
```
**OBSERVED — structural (compile-only, `simd_sgbar_structural`):**
`sgbar_none` (no barrier call), `sgbar_memnone`, `sgbar_memtg`, `sgbar_memdev`
— **all four compile to the IDENTICAL 46-byte `_agc.main`**, byte-for-byte
(`identical_to_base=True` for all four against the no-barrier baseline).
`simdgroup_barrier` adds **zero instructions for every tested memory class**,
not just `mem_none` — a stronger result than `threadgroup_barrier`, which
EXP-0093 showed DOES emit a real `0x07`-family instruction even for
`mem_none` (because it must converge the whole threadgroup, which may span
multiple simdgroups).

**OBSERVED — functional (`sgbar_conv` vs `sgbar_conv_none`, grid=32/tg=32, one
simdgroup, per-lane variable-length data-dependent delay loop + cross-lane
DEVICE-memory read of another lane's slot):** **byte-identical, fully correct
output with and without the `simdgroup_barrier(mem_device)` call**
(`[1215,1177,...,37]`, exact match to the closed-form oracle, both variants,
both runs).

**INTERPRETED — the structural result is decisive; the functional result is
a consistent but WEAKER corroboration, not independent proof.** Because
`grid=tg=32` places every lane of this test in the SAME single simdgroup, the
kernel's own divergent-loop control flow ALREADY reconverges all lanes via
the ordinary `if_push`/`pop_reconverge` mechanism (CF-03-tested to depth 128)
before the cross-lane read — meaning this specific test design cannot, by
construction, distinguish "the barrier is truly unnecessary because lockstep
execution already provides it" from "this test never created a scenario
where a barrier could have mattered". The STRUCTURAL byte-identical evidence
is what actually establishes "compiles to no instruction"; the functional
run corroborates that removing it caused no observed harm, without
independently proving why.

**Counterexamples / untested:** a scenario that could distinguish these two
readings (e.g. one that does NOT rely on reconverged control flow to
guarantee same-instruction-pointer execution before the cross-lane read) was
not constructed — flagged as a genuine residual gap, not silently smoothed
over.

**Driver/compiler consequence:** `simdgroup_barrier` (any memory class) can
be treated as a pure compiler-visible synchronization POINT with zero
hardware cost when lowering NIR subgroup barriers restricted to a single
simdgroup — no fence instruction needs to be emitted, in contrast to a
threadgroup-scope barrier.

---

### SIMD-07 — Are helper lanes included or excluded correctly by every subgroup and quad operation exposed to fragment shaders?

```text
Status: [x] Partial (one vote-class op tested, one discard shape)
Answer: [x] Yes (helper lanes ARE included, refuting the "vote ops exclude them" hypothesis)
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution (fragment, real render target)
```
**OBSERVED.** 4×4 render target, one fixed pixel (0,0) discards
(`discard_fragment()`).
- `f_ballot_baseline` (no discard): every one of the 16 pixels reports
  `popcount(simd_active_threads_mask())` = **16** (all real fragments in one
  simdgroup); raw low-16 mask bits = **`0xFFFF`** (all 16 real lanes set).
- `f_ballot_onediscard`: the discarded pixel shows the render target's clear
  color (confirms the discard executed); every SURVIVING pixel's
  `popcount(simd_active_threads_mask())` = **24** (an 8-bit INCREASE from
  baseline — see caveat below); but the **raw low-16 mask bits are STILL
  `0xFFFF`**, byte-identical to the no-discard baseline. The demoted lane's
  own bit did **not** clear.

**INTERPRETED.** The low-16-bit raw evidence is unambiguous and directly
answers the pre-registered refuter: **`simd_active_threads_mask()` does NOT
exclude a just-demoted (discarded) neighbor** — it continues to report that
lane as part of the mask. This REFUTES the naive "vote ops correctly exclude
helper lanes" hypothesis and instead REINFORCES/extends EXP-0091's finding
(data-movement ops like `quad_shuffle_xor` also include the demoted lane) —
the combined picture from EXP-0091 + this experiment is that **both
data-movement and vote-class operations tested so far treat a demoted helper
lane as still "active"**, at least until the fragment program actually
terminates.

**Honest residual puzzle (NOT resolved, flagged rather than guessed):** the
POPCOUNT went from 16 to 24 (a jump of 8) despite the low-16 bits being
unchanged — meaning bits 16–23 of the 32-bit mask differ between the two
compiles. This is NOT explained by this experiment; candidate causes (a
scheduling/occupancy-padding artifact of the discard changing register
pressure or code shape, vs. a genuine second set of helper/shadow lanes) were
not distinguished. Recorded as `UNKNOWN`, not promoted to a claim.

**Counterexamples / untested:** only `simd_active_threads_mask()` was tested
as the vote-class representative; `simd_ballot`, `simd_all`, `simd_any` under
discard were not independently re-tested (though `simd_active_threads_mask`
is itself one of the family EXP-0018 documented alongside `simd_ballot`);
only ONE discard shape (single fixed pixel) was tested; multi-pixel discard
and quad-boundary-crossing discard patterns are untested.

**Driver/compiler consequence:** a legalizer must NOT assume
`simd_active_threads_mask`/`simd_ballot`-class ops give a "real fragments
only" count under discard — helper lanes remain counted, at least in the
low-order (real-fragment) bit range, consistent with SPIR-V "demote" (not
"terminate") semantics for the discard already established by EXP-0091.

---

## Finite-resource summary table

| Namespace/resource | Scope | Encoding | Exact usable range/count | Holes/reserved | First invalid value | Observed failure | Correct "need more" fallback | Evidence |
|---|---|---|---:|---|---:|---|---|---|
| CF exec-mask/reconvergence nesting depth (if-return chain) | per kernel invocation | `if_push`/`pop_reconverge` mask stack | **≥128** (no failure observed; not a discovered ceiling) | none found | not found (untested beyond 128) | n/a (none observed) | none needed at tested depths; deeper depths UNKNOWN | `cf_ifnest_*`, both runs MATCH |
| CF exec-mask/reconvergence nesting depth (pure loop-nest, O(1) work) | per kernel invocation | `if_push`/`pop_reconverge` mask stack via loop back-edge | **≥64** | none found | not found | n/a | none needed at tested depths | `cf_loopnest1_*`, both runs MATCH |
| `icmp_pred` `dst_pred` field | per instruction | byte0 high nibble, 4 bits | compiler uses only **{0}**; splice-tested {1,5,0xf} all UNSAFE | 1–0xf untested individually beyond {1,5,0xf} | **1** (already corrupts) | silent value-dependent misroute, no fault | always emit 0; do not allocate | `cf_predalias_splice_*`, both runs identical |
| `jump`/`jump_cond` branch-target offset | per instruction | 48-bit signed LE byte-relative, `target=addr+4+off` | practical range far narrower than 2^48; exact boundary not bisected | untested interior | **±8B off a valid target already unsafe** (fault or hang) | `CMDBUF_ERROR` / contained HANG / silent-zero `STATUS OK` (3 distinct modes) | exact target computation only; no soft-fail margin | `cf_reach_splice_*`, both runs identical |
| `threads_per_simdgroup` (compute) | per launch | fixed SR value | **32**, including a 16-real-thread PARTIAL final group | n/a | n/a (constant, not a count) | n/a | n/a — it is a constant, not capacity | `simd_width_partial48`, both runs |
| `simd_shuffle` dynamic lane index | per lane, per call | runtime `ushort` register | **[0,32)** exact; ≥32 aliases to `idx & 0x1C` | bits 0–1 and ≥5 of idx always dropped once idx≥32 | **32** | silent deterministic alias (not fault, not wrap-mod-32) | mask index in software before emit if portable behavior required | `simd_shuffle_idx_*` (14 points), both runs identical |
| `simd_shuffle_xor` dynamic mask | per lane, per call | runtime `ushort` register | **[0,32)** exact; ≥32 → hard 0 | n/a | **32** | silent deterministic ZERO (different signature from plain shuffle) | mask index in software | `simd_shufflexor_mask_*` (6 points), both runs identical |
| `quad_shuffle` dynamic index | per lane, per call | runtime `ushort` register | **[0,4)** exact; ≥4 → hard 0 | n/a | **4** | silent deterministic ZERO | mask index in software (`&3`) | `simd_quadshuffle_idx_*` (8 points), both runs identical |
| raster-order-group index (context, not retested — see EXP-0093) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | cited for contrast only, not this experiment's evidence |

## Deferred (explicitly, not silently dropped)

1. **SIMD-01 fragment/vertex-stage width sweep** — not run as a dedicated
   multi-size render-target sweep; only incidental evidence (popcount=16 for
   one 4×4 target) exists. Follow-up: a `width_report`-equivalent fragment
   kernel across several target sizes and tile-boundary-crossing shapes.
2. **CF-03 exact nesting ceiling** — bounded from below (≥128 if-chain, ≥64
   loop-nest), not located exactly. Follow-up: push the sweep further with a
   binary-search strategy, watching compile time and per-case timeout budget.
3. **CF-05 `dst_pred` mechanism for value 1 vs. {5,0xf}** — two distinct
   corruption signatures observed and reported, but the underlying mechanism
   for why `1` differs from `5`/`0xf` was not isolated. Follow-up: a full
   0x1–0xf sweep with per-value downstream-read verification.
4. **Branch-reach exact fault/silent-corruption boundary** — six points
   bracket the behavior qualitatively; the precise byte offset where forward
   jumps transition from `CMDBUF_ERROR` to silent-zero `STATUS OK` was not
   bisected.
5. **SIMD-03 static/immediate-operand shuffle out-of-range behavior** — this
   experiment tested only the DYNAMIC (runtime-register) index form; the
   compile-time-constant form (EXP-0018's original evidence) was not
   re-tested for out-of-range immediates (Metal's own compiler will generally
   reject an obviously-illegal compile-time constant before it reaches this
   question, which is part of why the dynamic form is the more relevant
   probe for driver-generated code that cannot always prove range statically).
6. **SIMD-07 full vote-family-under-discard + the popcount 16→24 puzzle** —
   only `simd_active_threads_mask()` under one discard shape was tested; the
   unexplained 8-bit increase in the upper mask bits is recorded as an open,
   unexplained observation, not resolved.
7. **SIMD-06's structural-vs-functional distinction** — flagged above; a test
   design that does not rely on the kernel's own CF-reconvergence to mask the
   difference was not constructed.

## Hangs and faults (safety record)

One contained **HANG** (`cf_reach_splice_small_bwd`, 8-second timeout, exact
per the pre-registered `run_timeout=8.0`), four contained `CMDBUF_ERROR`s
(the other branch-reach splices), zero of either in any other case out of 92.
**Zero device wedges, zero use of `macvdmtool`, zero manual intervention
required.** Both runs reproduced the exact same fault/hang set at the exact
same cases (part of the 0-issue cross-run gate).

## Gate results

```text
$ python3 harness/verify.py --selftest
--selftest: 103/103 PASS, 0 FAIL

$ python3 harness/verify.py --seqtest
current state: RUN02_PRESENT
  [PRE_GPU] selftest_runs_without_raw: PASS
  [PRE_GPU] captured_correctly_refuses_when_absent: PASS
  [RUN01_PRESENT] captured_refuses_with_one_run: PASS
  [RUN01_PRESENT] run01_gated_readable: PASS
  [RUN02_PRESENT] captured_runs_with_both_present: PASS
--seqtest: 5/5 PASS

$ python3 harness/verify.py --smoke
SMOKE (non-recorded, real GPU dispatch, written to work/ only): status=OK -> PASS

$ python3 harness/verify.py --captured m4_20260827_run01 m4_20260827_run02
cases compared: 92
gated-field issues: 0
nongated gputime_ns differs in 81/92 cases (nondeterminism-split proof: CONFIRMED)
cross_run_gate_pass=True
```

## Clean-room attestation

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: authored MSL (kernels/cf_nest.metal [generated by
  harness/gen_cf_kernels.py], kernels/cf_misc.metal, kernels/simd_misc.metal,
  kernels/frag_misc.metal), authored Python (harness/gen_cf_kernels.py,
  harness/matrix.py, harness/lib.py, harness/run.py, harness/verify.py,
  harness/fixtures.py, analysis/report.py), read-only use of tools/shdump
  (shdump.m, agxparse.py), tools/agxtest (agxrun.m, agxrender.m, agxtest.py),
  tools/agx-isa (agxisa.py, isadb.py, db.json) on our own compiled kernel
  bytes only.
Apple binary introspection: NONE.
Target qualification: local M4/G16G only; no A18 Pro claim anywhere.
Reproduction: README.md command sequence.
Evidence: raw/m4_20260827_run01{,.nongated}.jsonl,
  raw/m4_20260827_run02{,.nongated}.jsonl, CAPTURE_CONTRACT.json,
  PRE_REGISTRATION.md, manifest.json, analysis/summary.json.
```
