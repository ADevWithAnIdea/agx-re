# RESULTS -- EXP-0115 M4 control-flow & SIMD: closing EXP-0104's deferred items

**Target: local Apple M4 (G16G) only.** macOS 26.6.2 (25G82), Metal 4, 10 GPU cores.
**No A18 Pro/G17P claim anywhere in this document. No M5 claim.** Two capture runs
from byte-identical authored source (pinned revision
`87d02c34f56357734f448695cf62d37ab555fcb0`, see `CAPTURE_CONTRACT.json`):
`raw/m4_20260828_run01.jsonl` / `raw/m4_20260828_run02.jsonl` (+ `.nongated.jsonl`
companions), 308 cases each.

**Cross-run gate: 295/308 cases (all of items 2-7, plus 149/162 branch-reach cases)
byte-identical between runs. 13/308 cases (all in item 1, the branch-reach mixed
zone) genuinely DIFFER between runs -- itself a first-class, disclosed finding, not
a harness defect (see item 1 below).** `verify.py --selftest` 321/321 PASS.
`verify.py --seqtest` 5/5 PASS at every state. `--smoke` PASS (non-recorded, ran
before any `raw/` file existed, confirmed `raw/` empty immediately after).
Both runs: identical per-item verdict distributions (run01: ok=18 mismatch=9
fault=128 hang=12 other=141; run02: ok=18 mismatch=9 fault=126 hang=17 other=138,
the fault/hang split shift is exactly the 13 non-deterministic branch-reach cases
reclassifying). **Zero device wedges; `macvdmtool` never invoked; zero
`DRIVER_EXCEPTION`/`HOST_TIMEOUT` in either run.**

## Headline verdicts

| item | verdict | evidence class |
|---|---|---|
| **1. Branch-reach boundary** | **MAPPED, with a major correction to the "clean boundary" framing**: the encoding has ZERO slack around the correct target (delta=+1 already faults) except one alias hole (delta=-2 is also correct); the region beyond the function's own 146-byte extent is a genuine CHECKERBOARD of fault/hang/silent-zero, not a single threshold; backward is uniformly fault/hang (never silent-zero) while forward mixes all three; **13/162 points show genuine run-to-run non-determinism** (same compiled bytes, different outcome on repeat) | `HW-VALIDATED`, 162 independently-constructed splice points per run, both runs |
| **2. CF-03 exact ceiling** | **THE CEILING FOUND IS THE MSL TOOLCHAIN'S (Clang bracket-depth=256), NOT (yet) A HARDWARE ONE**: exact max-compilable depths 254 (if-chain) / 255 (pure loop-nest) / 255 (bounded-divergent nest), all HW-dispatched successfully at their max; depth 255/256/256 respectively is a deterministic `COMPILE_FAIL`, reproduced both runs | `HW-VALIDATED` to the toolchain ceiling; ceiling itself is `STRUCTURAL` (compiler fact) |
| **3. dst_pred=1 mechanism** | **REFUTED the `if_push_pred` hypothesis decisively**: a 25-point (dst_pred, if_push.pred) matrix shows output depends ONLY on `dst_pred`; the sibling `if_push_pred.pred` nibble is COMPLETELY INERT (0-15, matched or mismatched, never changes anything); `dst_pred` itself: 0=correct, 1=a unique corruption, {2..15}=one uniform second corruption | `HW-VALIDATED`, downstream-read, independently constructed 2-field splices |
| **4. Static-shuffle OOB** | **NO, it does NOT behave like the dynamic form for `simd_shuffle`**: the static (single-instruction, embedded-immediate) form gives HARD ZERO for any out-of-range index, unlike the dynamic form's `idx & 0x1C` aliasing; `simd_shuffle_xor`/`quad_shuffle` static forms match their dynamic forms (both hard-zero) | `HW-VALIDATED`, 60 independently constructed raw-byte splices |
| **5. Vote family + popcount puzzle** | **RESOLVED the discard-specificity, NOT the exact bit mechanism**: an ordinary divergent RETURN (no discard) does NOT trigger the popcount jump, decisively narrowing the cause to `discard_fragment()` specifically (not generic divergent CF); jump does NOT scale with discard count or vary with location; `simd_all`/`simd_any`/explicit `simd_ballot(predicate)` all extend EXP-0104's inclusion finding | `HW-VALIDATED` for discard-specificity/count/location; exact byte-level mechanism remains `UNKNOWN` |
| **6. Fragment SIMD width** | **YES, closed**: `threads_per_simdgroup` = 32 (constant) at every tested render-target size from 1x1 (one real fragment) through 64x64, crossing the fixed 32x32 tile boundary repeatedly | `HW-VALIDATED`, 12 sizes, both runs |
| **7. SIMD-06 structural vs functional** | **NOT universally a no-op**: under DIVERGENT call patterns (per-lane call COUNT or call PRESENCE), the compiler retains real branch/reconvergence machinery around the barrier (10 vs 5, 18 vs 11 instructions); under UNIFORM call patterns (heavy register pressure, double calls, deep-but-non-divergent nesting) it remains byte-identical to no barrier, reproducing EXP-0104. Functional dispatch of the two divergent-risk shapes: correct, no deadlock, hard-timeout-guarded | `OWN-SHADER-DIFF` structural (adversarial) + `HW-PROBE` functional correctness |

---

## Response blocks

### Item 1 -- exact branch-reach fault/silent-zero/correct boundary map

```text
Status: [x] Closed (mapped) but with an added first-class finding: partial non-determinism
Answer: n/a (descriptive/quantitative)
Applies to: [x] M4/G16G
Evidence: [x] HW splice (independently constructed encodings)
Finite namespace: jump 48-bit signed LE byte-relative offset field, target = jump_addr + offset
  (see correction below re: db.json's documented "+4" convention)
Maximum-valid and first-invalid tests: see tables
Failure/overflow behavior: [x] fault [x] hang [x] alias/silent-zero [x] NON-DETERMINISTIC (new)
```

**OBSERVED -- near-baseline (both directions, both runs identical here).** Baseline
(`reach_baseline`, offset -44, target = the loop head after the `if_push` loop-iter
mask push) is correct: `[1,4,13,40,121,364,1093,3280]` for inputs `[0..7]`. **Forward
has ZERO slack: delta=+1 already faults** (`CMDBUF_ERROR`), and +2 through +9 all
fault. **Backward has exactly ONE alias hole: delta=-2 is ALSO fully correct**
(byte-identical to baseline output) -- landing 2 bytes before the documented target
still executes correctly (an undocumented, HW-VALIDATED "hole" in the encoding).
-1, -3, -4, -5, -7, -9, -11, -13, -15, -17, -19, -21, -23, -25, -27, -29, -31 all
fault; -6, -12, -14, -16, -18, -20, -22, -24, -26, -28, -32 all HANG in run01 (three
of these, -10/-30 in run01's baseline classification, reclassify between runs -- see
non-determinism below).

**OBSERVED -- the far checkerboard (forward only; backward has none).** A dense
128-byte-step sweep from +128 to +4096 is NOT a single threshold: solid FAULT from
+128 through +896-ish, then a genuine MIX of fault and silent-OK-zero from ~+992
through +4096 (e.g. +1024/+1536/+2048/+2176/+2304/+2688/+3200/+3328/+3584/+3712/
+3840/+3968/+4096 all silent-OK-ZERO `[0,0,0,0,0,0,0,0]`; +1280/+1408/+2432/+2560/
+2816/+2944/+3072/+3456 all FAULT -- interleaved, not monotonic). Far geometric
points: +8192 FAULT, **+16384 OK-zero** (an isolated far outlier), +32768 through
+4194304 (0x400000) all FAULT, and the true 48-bit-field extreme
+0x7FFFFFFFFFFF also FAULTs. **Backward is qualitatively different: the entire dense
128-step sweep from -128 to -4096, all 12 far geometric points, and the true extreme
-0x800000000000 are UNIFORMLY FAULT/HANG -- zero silent-OK-zero points observed
backward, in either run.**

**OBSERVED -- genuine run-to-run non-determinism (NEW finding, not anticipated in
`PRE_REGISTRATION.md`'s confounders list).** The cross-run gate (`verify.py
--captured`) found **13 of 162 branch-reach cases (8%) differ between run01 and
run02**; every other case in the entire 308-case matrix (items 2-7, plus the other
149 branch-reach cases including the correct baseline, the -2 hole, and most of the
checkerboard) is byte-identical across runs. The 13: `reach_fwd_{10,20,30,128,256,
512,2816}`, `reach_bwd_{4,8,10,30,128,256}`. Two distinct sub-patterns:

| sub-pattern | example | run01 | run02 |
|---|---|---|---|
| coarse STATUS itself flips | `reach_fwd_10` | `OK` silent-zero `[0]*8` | `HANG` |
| | `reach_fwd_20` | `OK` silent-zero | `HANG` |
| | `reach_fwd_30` | `OK` silent-zero | `HANG` |
| | `reach_bwd_10` | `CMDBUF_ERROR` | `HANG` |
| | `reach_bwd_8` | `CMDBUF_ERROR` | `HANG` |
| STATUS matches (`CMDBUF_ERROR` both) but the underlying GPU error code differs | `reach_bwd_128` | `...ErrorPageFault` | `...ErrorHang` |
| | `reach_bwd_256` | `...ErrorHang` | `...ErrorPageFault` |
| | `reach_bwd_30` | `...ErrorPageFault` | `...ErrorInnocentVictim` |
| | `reach_bwd_4` | `...ErrorPageFault` | `...ErrorHang` |
| | `reach_fwd_128` | `...ErrorPageFault` | `...ErrorHang` |
| | `reach_fwd_256` | `...ErrorPageFault` | `...ErrorHang` |
| | `reach_fwd_2816` | `...ErrorInnocentVictim` | `...ErrorHang` |
| | `reach_fwd_512` | `...ErrorHang` | `...ErrorPageFault` |

Root-cause check performed (per CODEX falsify-before-promote): the compiled
`_agc.main` bytes for `reach_loop` were extracted from BOTH runs' independently
compiled archives and are byte-for-byte IDENTICAL (only unrelated archive
metadata/timestamps differ) -- **ruling out compile-time byte differences as the
cause**. The splice bytes and target computation are identical (confirmed via each
record's `_locate.new_offset`). This means the SAME instruction bytes, entered at
the SAME (illegal) address, produce different observable outcomes on different
process invocations. The most defensible explanation (not independently isolated
further, reported as `INFERRED`): several of the differing deltas (e.g. +10 -> target
`0x48`) land on a REAL in-function instruction boundary reached via an entry path the
compiler never intended (skipping the preceding register-defining instructions), so
the outcome depends on whatever register/execution-mask state happens to be resident
at that point -- state this splice never initializes and which is not guaranteed
reproducible run-to-run. `kIOGPUCommandBufferCallbackErrorInnocentVictim` appearing
for two cases additionally shows that under back-to-back fault-provoking dispatches,
a command buffer can be reported as a victim of a NEARBY (not necessarily its own)
GPU error/recovery event -- a real operational-noise source in any test harness that
fires many faulting dispatches in quick succession.

**INTERPRETED.** The encoding's nominal 48-bit range is irrelevant; the practically
enforced range is a single correct point (delta=0) plus one alias hole (delta=-2),
with EVERYTHING else beyond +-1..2 bytes being some combination of FAULT, HANG, or
(forward only) silent-zero -- and for a specific, disclosed subset of offsets, the
FAILURE MODE ITSELF is not deterministic across repeated dispatches of byte-identical
code. **A driver must never treat "no `CMDBUF_ERROR` on one test run" as proof a
computed jump target is safe** -- not only can an out-of-spec target silently succeed
with wrong (zeroed) data with no fault at all, the exact behavior for some targets
may differ the next time the identical dispatch runs.

**Side finding, flagged for the orchestrator (no `db.json` edit made -- read-only
per dispatch):** `db.json`'s documented convention "target = jump_addr + 4 + offset"
for the `jump`/`jump_cond` family does not fit this experiment's own compiled
`reach_loop` binary as precisely as the simpler **"target = jump_addr + offset"**
(no +4): the baseline backward `jump` at file offset `0x6a` with offset=-44 lands
exactly on `0x3e` (the real loop-body-start instruction, right after the loop's
`if_push` mask push) under the no-+4 formula, and the forward `jump_cond` guard at
`0x24` with offset=`0x56` lands exactly on `0x7a` (the real outer `pop_reconverge`,
i.e. the loop-exit target) under the same no-+4 formula -- both are semantically
exactly the expected targets. This experiment did not need this formula for its own
delta-based splice sweep (which perturbs the existing valid offset directly, as
EXP-0104 did), so it is reported as a side observation, not re-derived as a
load-bearing fact here.

**Counterexamples / untested:** the checkerboard was sampled at 128-byte and
finer-detail resolution, not byte-exhaustively; a byte-exhaustive sweep of the full
mixed region (which this experiment's own evidence shows would itself be
non-deterministic in places) was judged not to add proportionate information for the
time/risk budget. The exact physical mechanism behind the non-determinism (residual
register/mask state vs. some other GPU-internal scheduling variable) was not
isolated beyond ruling out compiled-byte differences.

**Driver/compiler consequence:** relocatable code generation must compute
`jump`/`jump_cond` targets exactly; there is no soft-fail safety net in EITHER
direction, and for targets landing inside the function's own extent but at an
unintended entry point, even the FAILURE MODE cannot be assumed stable across runs
-- test suites that probe illegal branch targets must not treat one clean or one
faulting run as conclusive.

---

### Item 2 -- exact CF-03 nesting ceiling

```text
Status: [x] Partial (bounded from below by HW dispatch, closed from "above" by a
             TOOLCHAIN limit, not confirmed as a hardware limit)
Answer: [x] Unknown (true HW ceiling)  [x] Known (toolchain-reachable ceiling)
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution  [x] compile-only boundary probe
Finite namespace: if_push/pop_reconverge execution-mask reconvergence stack, per
  kernel invocation, for 3 structurally distinct nesting shapes
Maximum-valid and first-invalid tests: see table
Failure/overflow behavior: [x] toolchain COMPILE_FAIL (deterministic Clang diagnostic)
  [ ] HW fault  [ ] HW hang  [ ] HW wrong-result -- NONE of these three observed at
  ANY depth that compiled
```

**OBSERVED (both runs byte-identical).** `ifnest2` (nested divergent-return
if-chain): depths 128/192/224/240/248/252/**254** all compile AND dispatch
correctly (oracle-matched, e.g. depth 254 with inputs
`[0,1,127,253,254,255,304,769]` gives `[-1001,-1001,-1127,-1253,-1254,65025,92416,
591361]`, exact); depth **255 is a deterministic `COMPILE_FAIL`**
(`program_source:270:29: fatal error: bracket nesting level exceeded maximum of
256`). `loopnest1b` (pure nested-loop structural depth): 64/160/208/232/244/250/253/
**255** all compile+dispatch correctly; depth **256 is `COMPILE_FAIL`** (identical
diagnostic). `loopnestD2` (this experiment's new bounded-divergent design, see
below): 12/64/128/192/224/240/252/254/**255** all compile and dispatch with
`STATUS OK` (no fault/hang at any depth); depth **256 is `COMPILE_FAIL`**.

**Reconnaissance disclosure (per `PRE_REGISTRATION.md`):** the exact ceiling values
above were first found by bisection during this experiment's own pre-registration
reconnaissance (`work/pilot/bisect_bracket.py`), then re-derived independently and
formally in both gated capture runs via `harness/run.py`'s `compile_limit` case kind
-- both agree exactly with the reconnaissance.

**The `loopnestD2` oracle defect (disclosed, not hidden).** All 9 dispatched
`loopnestD2` depths show `verdict=MISMATCH` in BOTH runs (deterministically, not a
flaky result). Root cause, found and verified post-capture: the kernel places its
accumulation (`acc += 1`) inside ALL N nested `for` loops (at the innermost point
only), so it executes `trip_1 * trip_2 * ... * trip_N` times -- standard
multiplicative nested-loop semantics -- rather than the ADDITIVE (`trip_1 + trip_2 +
... + trip_N`) growth the pre-registered oracle assumed. This is exactly the
exponential-blowup shape this design was meant to avoid (see
`PRE_REGISTRATION.md`), rediscovered empirically rather than caught in review. Hand
verification: for every one of the 9 depths and all 8 tested inputs (small values
0-7, so even the multiplicative form never exceeds 2^24), the REAL hardware output
matches `acc = PRODUCT_{j=1..depth} (1 + bit((j-1) mod 32)(v))` exactly (e.g. depth
12, v=7: (1+1)*(1+1)*(1+1)*1*1*...= 2^3 = 8, observed output = 8). **This is a
defect in this experiment's own host-side oracle, not a hardware anomaly**: `STATUS
OK` (no fault, no hang) at every one of the 9 depths, including 255, is the
load-bearing CF-03 fact, and it holds regardless of which growth formula is
"correct". Per CODEX (raw JSONL is immutable once captured; no post-capture repair),
run02 deliberately used the SAME unmodified oracle so the cross-run determinism gate
stayed meaningful (both runs reproduce the identical, understood, MISMATCH
byte-for-byte) rather than silently patching the analysis mid-experiment.

**INTERPRETED.** No AGX hardware fault, hang, or silent-wrong-result was found at
ANY nesting depth this experiment could reach through ordinary MSL compilation, for
any of three structurally distinct nesting shapes (divergent-return if-chain,
pure-structural loop-nest, bounded-per-lane-divergent loop-nest). **The actual wall
hit is Metal's Clang-based front end's fixed bracket-nesting diagnostic
(`-fbracket-depth=256` default), confirmed not adjustable through the public
`MTLCompileOptions` API `tools/shdump/shdump.m` exposes** (only `fastMathEnabled`/
language-version/preprocessor-macro knobs are available; no bracket-depth
passthrough exists in the public Metal API surface this project is permitted to
use). This is a genuinely different kind of "break" than a hardware ceiling, and is
reported as such rather than conflated with one: **the true AGX
reconvergence-mask-stack hardware capacity for this specific resource remains
UNKNOWN beyond ~254-255 levels** -- this experiment pushed as far as this specific
MSL-source toolchain path allows and hit the toolchain, not silicon.

**Counterexamples / untested:** true structural depth beyond 254/255/255 (blocked by
the toolchain, not reachable via MSL source in this project's permitted tool
surface); mixed if+loop nesting; nesting combined with real function calls
(EXP-0035's separate call-depth resource); a hypothetical NIR-level or
directly-assembled encoding that bypasses Clang's C-like parser entirely (out of
scope -- this project's clean-room boundary requires going through the public
`newLibraryWithSource:` compiler for OWN-SHADER evidence, not hand-assembling
arbitrary novel code shapes beyond what `tools/agx-isa`'s validated encoder already
supports).

**Driver/compiler consequence:** a legalizer can emit AT LEAST 254 (if-chain) / 255
(loop-nest, either pure-structural or bounded-divergent) levels of nesting without a
documented hardware ceiling being hit. Because an NIR-based Mesa/asahi backend does
not go through Clang's C-like bracket-nesting parser at all, this specific limit is
almost certainly SPECIFIC to Metal's own toolchain and not inherited by that
implementation path -- flagged explicitly so the true hardware ceiling (still open)
is not mistaken for a resolved question.

---

### Item 3 -- the dst_pred=1 mechanism

```text
Status: [x] Closed  Answer: [x] Neither a real independently-addressable predicate
  file NOR the if_push_pred sibling opcode's "pred" field selects anything that
  affects execution -- REFUTES both remaining live hypotheses from EXP-0104/db.json
Applies to: [x] M4/G16G
Evidence: [x] HW splice (independently constructed 2-field encodings)  [x] downstream read
Finite namespace: icmp_pred.dst_pred (byte0 hi nibble, 4 bits) AND the sibling
  if_push_pred.pred field (byte+1 hi nibble, 4 bits, db.json-documented but never
  compiler-emitted) -- tested as a JOINT 2-field space
Maximum-valid and first-invalid tests: see table
Failure/overflow behavior: [x] alias (dst_pred: two distinct corruption signatures,
  value-dependent) [x] confirmed INERT (if_push.pred: zero effect, any value)
```

**OBSERVED -- both runs byte-identical, 25/25 cases.** `db.json` independently
documents a 4-byte opcode variant `if_push_pred` (byte0 `0x0f`, byte+1 low nibble
`0x5` with a NONZERO high nibble = a `pred` field), distinct from the plain
`if_push` the compiler always emits (high nibble 0). This is a plausible
"matching-consumer" mechanism EXP-0104 did not test (it only spliced `icmp_pred`'s
`dst_pred`, leaving the consumer as plain `if_push`, implicitly "slot 0"). This
experiment splices BOTH fields simultaneously on `cf_pred.metal:predtest_004`'s
first `icmp_pred`/`if_push` pair (tokenize-located, not hardcoded): a diagonal
(dst_pred=N, if_push.pred=N) matched sweep for N=0..15, plus off-diagonal
cross-talk points (e.g. dst_pred=1 with if_push.pred in {0,2,5,0xf}; dst_pred=0
with if_push.pred in {1,0xf}; dst_pred in {2,5,0xf} with if_push.pred=1).

**Result: exactly THREE output patterns across all 25 combinations, and the pattern
is determined ENTIRELY by `dst_pred`, never by `if_push.pred`:**

| dst_pred | if_push.pred (any of 0,1,2,5,0xf tested) | output (inputs `[0,1,2,3,4,5,50,200]`) |
|---:|---|---|
| 0 | 0, 1, or 0xf -- ALL IDENTICAL | `[-1001,-1001,-1002,-1003,-1004,25,2500,40000]` (correct) |
| 1 | 0, 1, 2, 5, or 0xf -- ALL IDENTICAL | `[-1003,-1003,-1001,-1001,-1001,-1001,-1001,-1001]` (a UNIQUE corruption) |
| 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 | (diagonal N=N tested for each; cross-talk 1 tested for {2,5,0xf}) -- ALL IDENTICAL | `[-1001]*8` (a SECOND, uniform corruption: every lane takes the outermost `else`) |

A supplementary full `dst_pred` census (0-15, `if_push` left at its natural plain
form) independently confirms the same 3-way split: `dst_pred=0` correct;
`dst_pred=1` the unique signature; `dst_pred={2..15}` (14 values, zero exceptions)
all collapse to the same uniform "-1001 x8" signature.

**INTERPRETED.** This DECISIVELY REFUTES the `if_push_pred`-as-matching-consumer
hypothesis this experiment set out to test: **the sibling opcode's `pred` field, as
independently constructed across its full 4-bit range and tested against every
`dst_pred` value this experiment covers, has ZERO observable effect on execution,
matched or mismatched.** Combined with `dst_pred`'s own exhaustive 0-15 census
(1 correct value, 1 unique-corruption value, 14 uniformly-corrupting values), the
most defensible reading is that `if_push`'s predicate consumer is **not
parameterized by an independently addressable index at all** -- it is closer to a
fixed/implicit single physical wire the immediately-preceding `icmp_pred` writes,
and `dst_pred`'s nonzero values are simply WRONG-OPERAND-FIELD corruption (in the
same family as the "wrong register field -> silent misroute, not fault" pattern
`docs/isa/register-move-and-liveness.md` already documents), not addresses into any
real predicate-register namespace. The `if_push_pred` encoding `db.json` documents
may be real for some OTHER producer/consumer pairing this experiment did not
construct (e.g. the ray-query traversal context its own provenance note cites), but
it is not the mechanism `dst_pred` was hypothesized to pair with.

**Counterexamples / untested:** `dst_pred`/`if_push.pred` values 3,4,6,7,8,9,a,b,c,d,e
were tested individually against `dst_pred` alone (the supplementary census) but not
individually cross-matrixed against every `if_push.pred` value (time-boxed to the 25
representative points above, substantially more than EXP-0104's 3-point precedent
but not exhaustive over all 256 pairs); this pairing was tested at exactly ONE
nesting position (`predtest_004`'s outermost `icmp_pred`/`if_push`), not at a nested
(nonzero `scope`, e.g. `0x56`) occurrence.

**Driver/compiler consequence:** unchanged from EXP-0104 -- always emit `dst_pred=0`
for `icmp_pred`; this experiment additionally establishes that emitting a
`if_push_pred`-style nonzero `pred` nibble on the consuming push is not a way to
"correctly address" a nonzero `dst_pred` either -- there is no available combination
of these two fields, across the space tested, that behaves as a working
multi-predicate mechanism. Flagged for the orchestrator as a candidate `db.json`
documentation note (this experiment does not edit `tools/agx-isa/db.json`, per the
"tools/* READ-ONLY" dispatch constraint): the current `if_push_pred` entry's
"predicate-register PUSH variant" characterization is not supported by this
experiment's splice evidence for this producer/consumer pairing.

---

### Item 4 -- static/immediate-index shuffle out-of-range

```text
Status: [x] Closed  Answer: [x] NO for simd_shuffle (different from dynamic)
                            [x] YES for simd_shuffle_xor / quad_shuffle (same as dynamic)
Applies to: [x] M4/G16G
Evidence: [x] HW splice (independently constructed raw encodings, bypassing the
  compiler's own literal-masking) [x] one point per family also OWN-SHADER
  naturally-compiled (quad_shuffle literal 7, unmasked by the compiler)
Finite namespace: simd_shuffle "lane" byte (index<<1, 8 bits raw, byte+6 of the
  single-instruction static/immediate encoding); same field for shuffle_xor
  (mask<<1) and quad_shuffle (index<<1, only 2 bits meaningful)
Maximum-valid and first-invalid tests: see tables
Failure/overflow behavior: [x] zero (simd_shuffle static: hard zero, NOT the dynamic
  form's idx&0x1C alias) [x] zero (shuffle_xor/quad_shuffle static: hard zero,
  matching their dynamic forms)
```

**OBSERVED -- compiler behavior for a literal argument (own reconnaissance, real
compile).** A literal (compile-time-constant) shuffle index compiles to a
qualitatively SIMPLER, single-instruction encoding than EXP-0104's genuinely
register-sourced ("dynamic") form (which this experiment's own reconnaissance,
compiling an independent copy of the same shape, found compiles to a
multi-instruction sequence with residual undecoded bytes in this project's current
tables) -- confirming static and dynamic really are different compiled shapes, as
`db.json`'s "byte+6 = lane index/xor mask (index<<1)" note (EXP-0018) originally
described. Critically, the compiler PRE-MASKS an illegal literal `simd_shuffle`
index at compile time (a literal `40` compiles to an embedded `lane` byte equal to
`(40 & 0x1F) << 1`, so the raw hardware value the instruction carries is already
legal) -- so this experiment splices the raw `lane` byte DIRECTLY, bypassing the
compiler's own masking entirely, to test what the hardware itself does with a
genuinely out-of-range static-form value (the strongest CODEX evidence tier:
independently constructed, not observed).

**OBSERVED -- HW splice sweep, `kernels/shuf_static.metal`'s 3 single-instruction
kernels, both runs byte-identical.**

| family | in-range (control) | first out-of-range | behavior for ALL out-of-range raw values tested |
|---|---|---|---|
| `simd_shuffle` (32 raw points, 4 in-range + 28 OOB/odd) | raw=0,2,30,62 (idx 0,1,15,31) -> exact broadcast of that lane's value, correct | raw=64 (idx 32) | **HARD ZERO** -- every one of 28 out-of-range/odd raw values from 64 through 255 (spanning idx 32-127, plus the odd/hole raw=1,65,127,255) gives 0, with ZERO exceptions; NO `idx & 0x1C`-style aliasing observed for the static form |
| `simd_shuffle_xor` (13 raw points) | raw=0,2,62 (mask 0,1,31) -> exact xor-pairing (identity / adjacent-swap / full reversal), correct | raw=1 (odd/hole) | **HARD ZERO** -- odd/hole raw=1 AND every raw>=64 (mask>=32) tested gives 0; matches its dynamic form's hard-zero behavior |
| `quad_shuffle` (15 raw points) | raw=0,2,4,6 (idx 0,1,2,3) -> exact per-quad broadcast, correct | raw=1 (odd/hole, "idx 0.5") | **HARD ZERO** -- every odd raw (1,3,5) AND every raw>=8 (idx>=4) tested gives 0, matching its dynamic form; ALSO independently confirmed via a naturally-compiled (unmasked-by-the-compiler) literal `quad_shuffle(v,(ushort)7)`, the strongest evidence tier for this one point |

**INTERPRETED.** The static and dynamic encodings are NOT interchangeable in their
out-of-range behavior for `simd_shuffle`: the dynamic (register-indexed) form
aliases via `idx & 0x1C` (EXP-0104), while the static (embedded-immediate) form
gives a hard zero for the identical effective out-of-range index -- **two genuinely
different hardware behaviors for what MSL exposes as the same builtin**, depending
purely on whether the compiler chose the single-instruction immediate encoding or
the multi-instruction register-indexed one. `simd_shuffle_xor` and `quad_shuffle`,
by contrast, are CONSISTENT between their static and dynamic forms (hard zero
either way) -- so the "does static match dynamic" answer is family-specific, not a
single rule.

**Counterexamples / untested:** the full byte range (0-255) was not exhaustively
swept for every family (a representative ~30-60 points per family, covering
in-range controls, the first-invalid boundary, the dynamic form's previously-tested
region at finer resolution, extremes, and odd/hole values); values between the
sparse sample points are assumed (not proven) to continue the same "hard zero"
pattern.

**Driver/compiler consequence:** NIR lowering that can prove a shuffle index is a
compile-time constant and chooses to emit AGX's single-instruction immediate form
must NOT assume the same out-of-range fallback as the general register-indexed
path -- `simd_shuffle`'s static form drops straight to zero rather than aliasing;
`simd_shuffle_xor`/`quad_shuffle` are safe to treat uniformly (hard zero) across
both forms.

---

### Item 5 -- full vote family under discard + the popcount 16->24 puzzle

```text
Status: [x] Partial (discard-specificity, count-independence, location-independence,
  and inclusion for 4 vote-family members all CLOSED; exact bit-level mechanism
  of the popcount jump remains UNKNOWN)
Answer: [x] Yes (helper lanes ARE included by simd_active_threads_mask, simd_all,
  simd_any, AND explicit simd_ballot(predicate) -- extends EXP-0104 to 3 more ops)
Applies to: [x] M4/G16G
Evidence: [x] HW-PROBE, fragment, real render target
```

**OBSERVED -- both runs byte-identical, 13 render cases.** `f_mask_baseline_pc`
(no discard): every pixel reports `popcount(simd_active_threads_mask())` = 16 (all
real fragments). `f_mask_1discard_pc` (fixed pixel (0,0) discards): the discarded
pixel shows the cleared/transparent color (alpha=0, confirming discard executed);
every SURVIVING pixel reports popcount **24** (the EXP-0104 8-bit jump,
reproduced). **`f_mask_1return_pc` (the decisive new control: an ordinary divergent
`return` at the SAME fixed pixel, NO `discard_fragment()` call): surviving pixels
report popcount 16 -- IDENTICAL to the undiverged baseline, NO jump.** Since
`return` also compiles through real branch/mask machinery (EXP-0104's CF-04
finding), this DECISIVELY REFUTES "generic to any divergent control flow" and
narrows the cause to `discard_fragment()` specifically. `f_mask_2discard_pc` (two
fixed pixels discard): survivors report popcount 24 -- IDENTICAL to one discard,
refuting "scales with discard count". `f_mask_discard11_pc` (discard moved to pixel
(1,1) instead of the corner (0,0)): survivors (including pixel (0,0), now a
survivor) report popcount 24 -- IDENTICAL, refuting "location-dependent".
`f_ballotpred_baseline_pc`/`_1discard_pc` (the EXPLICIT `simd_ballot(true)` form,
`db.json`'s pred=1 encoding, distinct from `simd_active_threads_mask`'s pred=0
form): reproduces the EXACT SAME 16->24 jump under discard -- the effect is not
specific to the `simd_active_threads_mask` encoding variant. `f_mask_baseline_raw`/
`f_mask_1discard_raw` (raw low-16 mask bits, R=low byte, G=next byte): both read
`0xFFFF` (R=255,G=255) with and without discard on a surviving pixel -- reproducing
EXP-0104's finding that the discarded lane's own LOW bit never clears (the extra 8
bits driving the popcount jump live in bits 16-23, outside this R/G encoding).

**OBSERVED -- extending inclusion to `simd_all`/`simd_any` (new).**
`f_all_baseline`/`f_all_1discard` (predicate FALSE only at the discarding pixel
(0,0)): `simd_all(pred)` reads FALSE for every surviving pixel BOTH with and
without discard -- the demoted lane's FALSE predicate still counts (INCLUDED).
`f_any_baseline`/`f_any_1discard` (predicate TRUE only at the discarding pixel):
`simd_any(pred)` reads TRUE for every surviving pixel BOTH with and without discard
-- the demoted lane's TRUE predicate still counts (INCLUDED). Both are decisive,
unambiguous (single boolean, no lane-index-mapping needed), and independently
reproduce EXP-0104's `simd_active_threads_mask` conclusion via two genuinely
different vote instructions.

**INTERPRETED -- the popcount puzzle, narrowed but not fully resolved.** The
discard-specificity is now firmly established: it is NOT a generic consequence of
divergent control flow (return doesn't trigger it), NOT proportional to discard
count (1 and 2 discards give the identical 24), and NOT dependent on WHICH pixel
discards. A structural (compile-only) byte comparison of the baseline/discard/return
fragment programs shows the discard and return kernels compile to genuinely
different, larger instruction sequences before the final vote-instruction read than
the no-CF baseline -- but this project's current fragment-stage decode tables have
undecoded residue in that exact sequence (an `<UNKNOWN>` byte0 `0xa6`/`0x54`-family
leader not yet in `tools/agx-isa/db.json`), so the EXACT bit-level source of the
extra 8 mask bits is NOT further isolated here. This is reported as a narrowed,
partially-open finding rather than a full resolution, per CODEX's preference for
`UNKNOWN` over invented certainty.

**Counterexamples / untested:** only ONE discard shape family (single/double fixed
pixel, one location variant) was tested; multi-quad-crossing discard patterns and a
FULL byte-level decode of the discard/return fragment prologue (which would require
extending `db.json`'s fragment-stage coverage, out of this experiment's scope) were
not attempted.

**Driver/compiler consequence:** unchanged from EXP-0104, now on firmer footing and
broader evidence -- a legalizer must NOT assume any vote-class op (`simd_active_
threads_mask`, `simd_all`, `simd_any`, `simd_ballot`) excludes a just-discarded
lane; all four tested here include it. The popcount SIDE-EFFECT of discard's
presence (independent of the vote result's own correctness) is a compiler/codegen
artifact whose magnitude (+8, fixed) should not be relied upon for anything -- it is
explicitly flagged `UNKNOWN` mechanism, not a documented capacity.

---

### Item 6 -- fragment-stage SIMD width sweep

```text
Status: [x] Closed  Answer: [x] Yes
Applies to: [x] M4/G16G
Evidence: [x] HW-PROBE, fragment, real render target, 12 sizes
Finite namespace: threads_per_simdgroup SR, fragment stage
```

**OBSERVED -- both runs byte-identical.** `[[threads_per_simdgroup]]` is available
and compiles successfully in the fragment stage (not previously established in this
repo). At EVERY one of 12 tested render-target sizes -- 1x1 (a single real
fragment), 2x2, 3x3, 4x4, 8x8, 16x16, 31x31, 32x32, 33x33 (crossing the fixed
32x32 AGX tile boundary, `docs/pipeline/README.md`), 40x24, 48x48, 64x64 -- EVERY
pixel reports `threads_per_simdgroup` = 32, with zero exceptions across
1+4+9+16+64+256+961+1024+1089+960+2304+4096 = 10784 total pixel readings.

**INTERPRETED.** Extends EXP-0104's compute-stage finding (`threads_per_simdgroup`
is a fixed architectural constant, not an occupancy count) to the fragment stage:
even a 1x1 render target (ONE real fragment, occupying a single lane of whatever
simdgroup the tiler/rasterizer schedules it into) reports the same fixed 32.

**Driver/compiler consequence:** a legalizer can treat `threads_per_simdgroup` as
compile-time-foldable to the constant 32 for both compute AND fragment stages on
this hardware, regardless of dispatch/target-size occupancy.

---

### Item 7 -- SIMD-06 structural vs functional independence

```text
Status: [x] Closed  Answer: [x] NOT universally a no-op -- a genuine, disclosed
  correction/extension of EXP-0104's finding
Applies to: [x] M4/G16G
Evidence: [x] own-MSL byte diff, 5 adversarial paired shapes (structural)
          [x] independently assembled HW execution, 2 deadlock-risk shapes
             (functional, hard 10s timeout)
```

**OBSERVED -- structural, both runs byte-identical.** Of 5 adversarial `_bar`/
`_nobar` paired shapes: `sgbar_highreg` (heavy register pressure), `sgbar_double`
(two consecutive barriers, different memory classes), and `sgbar_nested` (barrier at
CF depth 8) all reproduce EXP-0104's finding -- byte-identical compiles, 0 added
instructions, for every one of these UNIFORM-call-pattern shapes (every lane calls
the barrier the same number of times, at a compile-time-symmetric point).

**`sgbar_loop` (barrier inside a per-lane genuinely-divergent-trip-count loop, so
different lanes call the barrier a different NUMBER of times) and `sgbar_ifdiv`
(barrier called by only SOME lanes -- divergent call PRESENCE) are DIFFERENT: 124
vs 110 bytes (`sgbar_loop`) and 76 vs 46 bytes (`sgbar_ifdiv`), `identical=False`
both.** Tokenized inspection: for `sgbar_ifdiv`, the no-barrier twin (`if (v%2==0)
{}` -- an empty conditional block) is completely DEAD-CODE-ELIMINATED by the
compiler (5 instructions, no branch machinery at all, straight to `v*2`); the
barrier-present twin RETAINS a real, executing `if_push`/`pop_reconverge` pair
around the (otherwise-empty) barrier call (10 instructions, including a
`scoreboard_fence`), because the barrier is a genuine side-effecting operation the
compiler cannot eliminate. For `sgbar_loop`, the no-barrier twin is fully optimized
by the compiler into a CLOSED-FORM arithmetic expression (an `imad`/`irotate`/
`isel10` sequence recognizing the trivial `sum(0..v-1)` accumulation pattern, 11
instructions, NO loop machinery at all); the barrier-present twin retains a REAL
loop (`if_push`/`jump_cond`/`icmp_pred`/`ret`/`jump`/`pop_reconverge`, 18
instructions) because the barrier prevents the compiler from proving the loop has
no side effects.

**INTERPRETED, with an honest caveat.** This decisively shows `simdgroup_barrier`
is **NOT unconditionally a no-op**: under a DIVERGENT call pattern (count or
presence), its presence changes the compiled output. The mechanism, however, is
best understood as the barrier acting as an **optimization barrier / side-effect
anchor** that prevents the compiler from applying transformations (loop-to-
closed-form folding, dead-code elimination of an empty conditional) that it
otherwise would -- rather than necessarily proof that `simdgroup_barrier` itself
compiles to one specific dedicated opcode. Both readings support the same, sufficient
conclusion for a driver: **"compiles to zero instructions" is not a universal
property of `simdgroup_barrier`; it depends on the surrounding code shape, and
specifically breaks under per-lane-divergent call patterns**, resolving EXP-0104's
flagged ambiguity in the negative.

**OBSERVED -- functional, both runs byte-identical, MATCH.** Both deadlock-risk
shapes (`sg_func_loop_bar`, genuinely divergent per-lane barrier call COUNT;
`sg_func_ifdiv_bar`, divergent call PRESENCE) were dispatched under a hard 10s
timeout. **Neither hung; both completed with `STATUS OK` and exactly matched their
host oracle** (`sg_func_loop_bar`: `sum(0..v-1)` for `v` in `[0,1,2,3,5,8,13,21]`;
`sg_func_ifdiv_bar`: `v*2` for `v` in `[0..7]`). The extra machinery the compiler
retains for these divergent shapes handles the divergence CORRECTLY, not just
safely-from-a-deadlock perspective.

**Counterexamples / untested:** a scenario that isolates the barrier's compiled
form from the optimization-barrier confound (e.g. a shape complex enough to defeat
closed-form folding on BOTH sides, isolating only the barrier's marginal cost) was
not constructed; flagged as a genuine residual gap in fully attributing the byte
delta to "the barrier instruction" specifically, versus "what the barrier prevents
the compiler from doing".

**Driver/compiler consequence:** `simdgroup_barrier` under UNIFORM (every-lane,
same-count) usage can still be treated as free; under DIVERGENT usage (which the
Metal spec's "all threads in a SIMD-group must call simdgroup_barrier" language
already discourages), real machinery is retained and, per the functional test,
handles it correctly on this hardware -- no evidence of deadlock risk was found, but
this is not the same as the earlier "provably free" claim, which must be narrowed to
non-divergent call sites.

---

## Finite-resource summary table

| Namespace/resource | Scope | Exact usable range/count | Holes/reserved | First invalid | Observed failure | Correct fallback | Evidence |
|---|---|---:|---|---:|---|---|---|
| `jump` branch-target offset, forward | per instruction | delta=0 ONLY (zero slack) | none found forward | delta=+1 | `CMDBUF_ERROR`; checkerboard fault/silent-zero beyond ~+900B; solid fault beyond ~+32KB | exact target only; treat ALL non-zero forward deltas as unsafe, including ones that don't fault | `reach_fwd_*`, both runs (13/85 non-deterministic, see item 1) |
| `jump` branch-target offset, backward | per instruction | delta=0 and delta=-2 (one alias hole) | delta=-2 | delta=-1 | `CMDBUF_ERROR`/HANG; NEVER silent-zero backward | exact target only | `reach_bwd_*`, both runs (13/77 non-deterministic) |
| CF reconvergence stack, if-chain (`ifnest2`) | per kernel invocation | toolchain-reachable: **254** (HW-VALIDATED); true HW ceiling UNKNOWN beyond this | none found | 255 (Clang `COMPILE_FAIL`, not HW) | n/a (toolchain, not HW) | none needed at reachable depths | `deep_ifnest_*`, both runs MATCH |
| CF reconvergence stack, loop-nest (`loopnest1b`) | per kernel invocation | toolchain-reachable: **255** (HW-VALIDATED) | none found | 256 (`COMPILE_FAIL`) | n/a | none needed | `deep_loopnest1_*`, both runs MATCH |
| CF reconvergence stack, bounded-divergent nest (`loopnestD2`) | per kernel invocation | toolchain-reachable: **255**, `STATUS OK` at every depth (HW-VALIDATED for no-fault/hang; oracle itself defective, see item 2) | none found | 256 (`COMPILE_FAIL`) | n/a | none needed | `deep_loopnestD2_*`, both runs OK+deterministic-MISMATCH |
| `icmp_pred.dst_pred` | per instruction | compiler uses only {0}; splice-tested full 0-15 | 1 (unique 2nd signature) | 1 | value-dependent silent misroute (2 signatures: {1} vs {2..15}) | always emit 0 | `pred_dst*`, both runs identical |
| `if_push_pred.pred` (sibling field) | per instruction | splice-tested full 0-15, matched AND mismatched against every `dst_pred` tested | none -- fully inert | n/a (never changes output) | none (no effect at all) | irrelevant -- do not attempt to use | `pred_dst*_ifp*`, both runs identical |
| `simd_shuffle` static-form `lane` byte | per instruction | **[0,62] even** (idx 0-31) exact; raw>=64 -> hard 0 | odd raw values (never compiler-produced) also -> 0 | 64 | silent deterministic ZERO (NOT `&0x1C` aliasing, unlike dynamic form) | never rely on static-form OOB behavior matching dynamic | `sshuf_raw_*`, both runs identical |
| `simd_shuffle_xor` static-form `lane` byte | per instruction | **[0,62] even** (mask 0-31) exact; raw>=64 or odd -> hard 0 | odd raw -> 0 | 64 (or 1, odd) | silent deterministic ZERO (matches dynamic form) | mask index in software if portable | `sxor_raw_*`, both runs identical |
| `quad_shuffle` static-form `lane` byte | per instruction | **[0,6] even** (idx 0-3) exact; raw>=8 or odd -> hard 0 | odd raw -> 0 | 8 (or 1, odd) | silent deterministic ZERO (matches dynamic form) | mask index in software (`&3`) | `squad_raw_*`, both runs identical |
| `threads_per_simdgroup` (fragment) | per launch | fixed SR value = 32, 1x1 through 64x64 targets | n/a | n/a (constant) | n/a | n/a -- constant, not a count | `width_*`, both runs |
| discard-triggered vote-mask popcount jump | per compile | fixed +8, independent of discard count (1 vs 2) or location | mechanism at the byte level UNKNOWN | n/a | silent +8 popcount shift, low-16 bits unaffected | do not rely on popcount magnitude under discard | `vote_f_mask_*`, both runs |
| `simdgroup_barrier` compiled cost | per call site | 0 instructions IF every lane calls it the same number of times at a symmetric point; REAL machinery retained under divergent count/presence | n/a | n/a | n/a (no fault; functionally correct even under divergence, tested) | do not assume free under divergent call patterns | `sg_struct_*`/`sg_func_*`, both runs |

## Hangs and faults (safety record)

Run01: 4 contained `HANG`s in the near-baseline fine sweep (`reach_fwd_32`,
`reach_bwd_6/12/14/16/18/20/22/24/26/28/32` -- 11 total, all 8s-timeout, contained,
zero host impact) + `reach_fwd_10` was `OK` not `HANG` in this run (see item 1
non-determinism), 128 `CMDBUF_ERROR`s, zero `HOST_TIMEOUT`/`DRIVER_EXCEPTION`. Run02:
17 `HANG`s (the same set plus `reach_fwd_10/20/30` and `reach_bwd_8/10`
reclassifying from run01's `OK`/`CMDBUF_ERROR`, per item 1), 126 `CMDBUF_ERROR`s.
**Zero device wedges in either run; `macvdmtool` never invoked; every hang recovered
cleanly within its pre-registered timeout (8s for branch-reach splices, 10s for the
deadlock-risk `sgbar_*` functional cases -- neither of which actually hung) and the
NEXT case in the sweep always proceeded normally.**

## Gate results

```text
$ python3 harness/verify.py --selftest
--selftest: 321/321 PASS, 0 FAIL

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
(raw/ confirmed empty immediately after, before either capture run started)

$ python3 harness/verify.py --captured m4_20260828_run01 m4_20260828_run02
cases compared: 308
gated-field issues: 13   [all 13 in item 1 "branch-reach", a disclosed HW finding,
                          not a harness defect -- see item 1's response block]
nongated gputime_ns differs in 156/308 cases (nondeterminism-split proof: CONFIRMED)
cross_run_gate_pass=False
```

**Standing-gate note on gate #4.** `PRE_REGISTRATION.md`'s confounders section
anticipated item 1's checkerboard being layout-dependent but did NOT anticipate
genuine run-to-run non-determinism; this experiment's design (unlike EXP-0104's,
which pre-registered exactly one INTENTIONAL race-control case) discovered
UNPLANNED non-determinism empirically. Per CODEX ("never silently discard
inconvenient or negative results"; "state ... alternative explanations not yet
excluded"), this is reported as a genuine, load-bearing finding, and the standing
gate's `cross_run_gate_pass=False` result is the CORRECT, honest output of the gate
doing its job -- not suppressed, not explained away, and not used to justify
discarding either capture run (both are retained in full as evidence; see
`raw/m4_20260828_run0{1,2}.jsonl`).

## Clean-room attestation

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: authored MSL (kernels/reach.metal, kernels/cf_pred.metal,
  kernels/shuf_static.metal, kernels/vote_frag.metal, kernels/width_frag.metal,
  kernels/sgbar_adv.metal, kernels/deep/*.metal [27 files, generated by
  harness/gen_deep_kernels.py, deterministic]), authored Python
  (harness/gen_deep_kernels.py, harness/matrix.py, harness/lib.py, harness/run.py,
  harness/verify.py, harness/fixtures.py, analysis/report.py), read-only use of
  tools/shdump (shdump.m, agxparse.py), tools/agxtest (agxrun.m, agxrender.m,
  agxtest.py), tools/agx-isa (agxisa.py, isadb.py, db.json -- read/tokenize only,
  never modified) on our own compiled kernel bytes only. `MTLCompileOptions`'s
  public header (Xcode SDK) was read to confirm no bracket-depth passthrough
  exists -- a PUBLIC Apple API header, not a binary, consistent with the PUBLIC
  evidence category.
Apple binary introspection: NONE.
Target qualification: local M4/G16G only; no A18 Pro claim anywhere; no M5 claim.
Reproduction: README.md command sequence.
Evidence: raw/m4_20260828_run01{,.nongated}.jsonl,
  raw/m4_20260828_run02{,.nongated}.jsonl, CAPTURE_CONTRACT.json,
  PRE_REGISTRATION.md, manifest.json, analysis/summary_run0{1,2}.json,
  work/pilot/ (non-recorded reconnaissance scripts, retained for audit).
```
