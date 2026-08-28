# PRE_REGISTRATION — EXP-0091 M4 fragment sample/coverage/discard/demote/helper state machine

Filed BEFORE any capture run counts as evidence. Pilot work below (host-side OWN-SHADER
compiles with `tools/shdump`/`tools/agx-isa`, and exploratory GPU dispatches with this
experiment's own `harness/fsrun.m`) was used to LOCATE candidate encodings and to shake
bugs out of the harness/case-matrix, exactly the standard "characterize before freezing"
step this repo's prior splice experiments use (EXP-0086 §0, EXP-0087). Nothing below is a
hypothesis-confirming post-hoc rewrite: the case matrix in `run.py` (hashed in
`work/pre_reg_hashes.txt`) is committed unchanged for both capture runs.

**Dispatch:** Bundle A, closing addendum items GLFS-A01, GLFS-A02, GLFS-A03, GLFS-A05,
GLFS-A06, GLFS-A07 (`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md`) and primary-list item OPT-09
(`APPLE9_RE_IMPLEMENTATION_GAPS.md:501-505`).

**Orchestrator note applied (received mid-pilot):** the two-run cross-run gate compares
this experiment's own captured artifacts (`raw/*/*.gated.json`) against each other, and
compares this experiment's *authored blob hashes* against the values pinned in this file
at freeze time. It does **not** require the live repository HEAD to be unchanged between
run01 and run02 — sibling experiments land commits continuously and that is not
contamination. The git revision below is recorded for provenance only.

## 0. Exact addendum wording under test (quoted verbatim)

> **GLFS-A01 — Exact fragment sample-state operation and finite mask capacity**
> What Apple9 instruction or instruction sequence kills samples, submits surviving
> samples to depth and stencil testing, and makes the final set of samples eligible for
> tilebuffer output? Decode every opcode, operand, modifier, predicate, mask, and state
> field. In particular, determine whether the physical operation has independent
> `target` and `live` masks like the current Asahi model, or has different semantics
> that require another representation. [...] For 1x, 2x, and 4x pipelines, test every
> mask value, repeated and overlapping operations, an empty target, an empty live set,
> already-killed samples, and samples already submitted to depth/stencil. [...] Record
> the exact mask width, maximum hardware sample count, inactive high-bit behavior, first
> unsupported sample count, and behavior of every reserved encoding.

> **GLFS-A02 — Demote, discard, terminate, and helper-lane state transitions**
> What are the exact Apple9 state transitions produced by fragment discard, NIR
> demotion, and true invocation termination? Start with both a covered live invocation
> and an uncovered original helper. At distinguishable points in divergent control flow,
> apply every candidate discard/demote mechanism and then test whether the invocation
> continues to execute ALU, ordinary loads, texture operations with implicit LOD,
> derivatives needed by neighboring lanes, quad operations, and subgroup operations.
> Separately test whether it can subsequently produce any observable framebuffer,
> depth/stencil, sample-mask, query, buffer, image, or atomic side effect. [...]
> Determine whether demotion is per-invocation or per-sample, whether killing the last
> live sample automatically changes helper state, whether a later operation can make a
> demoted invocation or killed sample live again, and whether true termination requires
> a separate branch/halt operation. [...] This must close the broad `OPT-09` question
> with executable behavior, while retaining `discard`, `demote`, and `terminate` as
> separate terms unless the evidence proves them equivalent for all portable-NIR
> observations.

> **GLFS-A03 — Helper-status source and changes during an invocation**
> What does the inferred helper-status `get_sr 0x84` return in every fragment execution
> state, and is it the complete value required by NIR helper-invocation queries?
> Validate the selector and complete result encoding with raw execution rather than a
> compiler byte diff. Test original uncovered helpers, covered invocations, partially
> covered MSAA invocations, per-sample shading, API sample masks, alpha-to-coverage,
> failed early depth/stencil tests, explicit demotion, per-sample killing, and killing
> the final live sample. Read it repeatedly before and after each transition. [...]

> **GLFS-A05 — Early/late depth-stencil ordering and fragment side effects**
> What exact Apple9 events perform early and late depth/stencil tests and updates, and
> what ordering do they have relative to shader execution, demotion, sample-mask output,
> tilebuffer output, occlusion queries, buffer/image stores, and atomics? Test at
> minimum ordinary late testing, an explicit early-fragment-tests shader, fragment depth
> output, conservative-depth qualifiers, fragment stencil output if supported, discard
> before and after a candidate test operation, and a mixture of passing and failing
> samples in one fragment. Determine separately when comparisons occur, when
> depth/stencil values are updated, when an invocation or sample is prevented from
> executing, and which effects a later discard can and cannot undo. [...]

> **GLFS-A06 — Suppression of helper and demoted-lane side effects**
> Which Apple9 operations automatically suppress side effects from original helper
> lanes and demoted lanes, and which require explicit compiler predication or control
> flow? Test buffer stores, image stores, every supported atomic family, color output,
> dual-source output, depth output, stencil output, sample-mask output, occlusion-query
> contribution, and any observable tile-memory operation. Run each first from an
> original helper and then from a covered invocation demoted immediately before the
> operation. [...] For every instruction family, document whether suppression is
> inherent, controlled by an encoded predicate or execution-mask bit, or must be
> synthesized. [...] This item extends `FS-12`: suppression of color alone does not
> close it.

> **GLFS-A07 — Sample shading invocation and liveness model**
> How does Apple9 execute OpenGL per-sample shading, and how do invocation frequency,
> sample ID, coverage, helpers, demotion, and derivative quads interact? For every
> supported framebuffer sample count and representative `MinSampleShading` values from
> zero through one, count shader invocations and record the active sample ID and every
> coverage/helper value. [...] Determine whether Apple9 launches one invocation per
> sample, groups samples into invocations, or loops samples in software or a
> prolog/epilog [...]

> **OPT-09** — Does fragment discard on Apple9 have SPIR-V demote semantics, including
> continued helper-lane execution for derivatives and implicit-LOD texture operations?
> Compiler consequence: `Yes` permits `.discard_is_demote = true`; `No` requires
> separate discard and demote lowerings.

## 1. Pilot findings used to build the frozen hypotheses (no GPU evidentiary weight by
   themselves where marked pilot-only; promoted only via the frozen capture runs below)

### 1.1 GLFS-A01 localization (host-side OWN-SHADER compile, `tools/shdump` + our own
byte-offset scan + `tools/agx-isa` tokenizer — no GPU dispatch)

Differentially compiling `kernels/loc_*.metal` (baseline / divergent-branch-without-
discard / `discard_fragment()` / `[[sample_mask]]` write, constant and runtime-valued,
combined and separate) and byte-scanning the extracted fragment `_agc.main` for every
`byte0==0x57,byte2==0x54` and `byte0==0x07,byte1==0x02,byte2==0x54` occurrence shows:

- `loc_base` and `loc_if_nodiscard` (plain shader; divergent `if`/reconverge with NO
  discard and no mask write) tokenize CLEAN via `tools/agx-isa` (0 leftover) and contain
  **zero** occurrences of `0x57/../0x54`. A generic branch/reconverge is not sufficient
  to emit this op family.
- Every kernel that calls `discard_fragment()` and/or writes `[[sample_mask]]` (constant
  or runtime-valued) emits a 6-byte op `57 <B1> 54 <B3> <B4> <B5>` immediately followed
  by a 6-byte companion `07 02 54 01 <B4'> <B5'>` (byte3=`0x01`, distinct from the
  ordinary end-of-program epilog `07 02 54 0c 02 00` that still follows later,
  unconditionally, at the very end of every fragment main).
- `B1` takes exactly two observed values: `0x1c` for a fully compile-time-provable,
  unconditional, straight-line kill (`discard_fragment()` with no branch, and the
  byte-identical `[[sample_mask]]=0` case — these two source constructs compile to
  **byte-identical** fragment mains), and `0x14` for every branch-computed or
  runtime-buffer-sourced case (conditional discard, `[[sample_mask]]` fed a
  ternary/branch value, or a *constant but non-zero* `[[sample_mask]]` value — MSL does
  not const-fold the explicit stage-output the same way it does the discard builtin).
- The submission op itself never carries the mask value as a literal immediate: two
  constant-mask kernels differing only in mask value (`0xF` vs `0xA`) differ at exactly
  one byte, in an *earlier* ALU immediate-materializing instruction (`value = mask<<1`),
  not in the submission op. This is consistent with the submission op being
  register-sourced (it consumes a fixed operand slot; the value is always produced by
  an ordinary preceding ALU/load instruction).
- `db.json` (`tools/agx-isa`) currently mis-tokenizes this pattern as an 8-byte
  `vary_store` (a **vertex**-stage varying-output op, `0x57` family) applied to a
  **fragment** context, over-consuming 2 bytes and leaving the rest of the main as
  leftover — an opcode-byte collision between the vertex-output-store family and this
  fragment-mask-submission family, structurally identical to the `0x9f 11 54`
  compute-vs-fragment collision EXP-0029 already found and fixed for a different byte0
  group. This experiment does not edit `tools/agx-isa/db.json` (read-only per dispatch);
  it records the correction as a finding for the orchestrator.

**H1 (frozen):** the `57 <0x14|0x1c> 54 ...` + `07 02 54 01 ...` pair is present in the
compiled fragment main **if and only if** the source calls `discard_fragment()` or
writes `[[sample_mask]]`, regardless of divergent control flow that does neither.
**Falsifier:** any `loc_if_nodiscard`-class kernel (divergent branch, no discard, no
mask write) that emits this byte pattern, or any `loc_if_discard`/`loc_samplemask`-class
kernel that omits it.

### 1.2 GLFS-A01 splice validation (pilot GPU dispatch, `harness/fsrun.m`, archive +
`MTLPipelineOptionFailOnBinaryArchiveMiss`, `kernels/s_kill_probe.metal`)

Per the register-move/liveness methodological warning (`docs/isa/register-move-and-
liveness.md`, EXP-0086): every splice below is validated through **downstream,
independent, hardware-committed side channels** (resolved color, fixed-function
rasterized depth, hardware occlusion-query count) rather than by inspecting the spliced
instruction's own encoded bit pattern as "plausible." For this fixed-function
coverage-submission op there is no GPR the next ALU instruction reads (unlike EXP-0086's
register-liveness bit) — the only observable effect *is* the final tile/attachment
state, so color+depth+occlusion together are the correct "later read."

Located `s_kill_probe.bin` fragment main at absolute file offset 13744 (114 bytes);
candidate op at absolute offset 13798 (`57 14 54 00 00 01`); companion at absolute
offset 13804 (`07 02 54 01 00 00`). Baseline (mask=1 bit0 set → predicted survive;
mask=0 → predicted killed), both via plain compile and via the unspliced archive,
reproduce identically on all three channels (color, fixed-function depth, occlusion),
confirming the archive-forcing mechanism itself is not the confound.

**H2 (frozen):** byte+4 of the candidate op (`57 14 54 00 [B4] 01`) is (at least in
part) a source-register-select field. **Prediction:** `B4=0x00` (baseline, register the
compiler routed the real computed mask into) survives; some nonzero `B4` values redirect
the read to a different (apparently always-zero/uninitialized) register, killing a
should-survive fragment on all three channels simultaneously. **Falsifier:** any `B4`
value that changes only ONE of the three channels (would mean color-store suppression
and true sample kill are different, separately-controlled mechanisms — the addendum's
own explicitly flagged falsifier) or that faults/hangs.
Pilot sweep (single dispatch per value, mask=1 baseline): `B4∈{0x01,0x02,0x04,0x08,
0x10,0xFE,0xFF}` → killed on all 3 channels together; `B4∈{0x20,0x40,0x80}` → survives,
matching baseline on all 3 channels together; own byte+1 (`0x14→0x1c`), own byte+3
(`0x00→0x01`), companion byte+3/+4/+5 → null (no observable change) in this
configuration — recorded as genuine negative results, not re-tried speculatively.
Positive control (corrupting one byte of the unrelated `frag_color_pack` op) changes the
color channel, confirming the splice mechanism itself can produce an observable
difference (i.e. absence of change elsewhere is not a dead harness).

### 1.3 MSAA mask-width sweep (pilot GPU dispatch, plain compile, no splice)

`kernels/f_persample_mask_resolve.metal`: a per-sample-shaded (`[[sample_id]]`)
fragment writes `color=1` only for samples whose bit is set in a runtime `[[sample_
mask]]`-sourced value, and also writes that same value to `[[sample_mask]]`; after
ordinary MSAA box-filter resolve, `resolved.r ≈ popcount(mask & ((1<<N)-1))/N`. Per
EXP-M4-09 (`experiments/EXP-M4-09-cmdstream-coverage/cmd7-msaa-query-ts/RESULTS.md`),
`N∈{1,2,4}` is the complete Metal-legal M4 sample-count range (`supportsTextureSample
Count:8` is `NO`, both texture- and pipeline-creation reject 8x) — this experiment does
not re-attempt 8x.

**H3 (frozen):** at sample count N, the effective mask is exactly the low N bits of the
32-bit `[[sample_mask]]` value; bits at or above bit N are inert (no fault, no alias,
no corruption of the low bits). **Falsifier:** any high-bit pattern that changes the
resolved fraction implied by `popcount(low N bits)`, or a fault/hang at any tested mask
value (tested up to `0xFFFFFFFF` and `0x80000000`).

### 1.4 Demote-vs-terminate decisive design (GLFS-A02/OPT-09)

`kernels/d_demote_before.metal`: even-x lanes call `discard_fragment()` then, only in
that taken branch, add `(1000,1000)` to a local copy of `pos.xy` (screen-space
fragment coordinate, whose true per-pixel step is exactly 1.0 in x). `fwidth()` of that
value is computed AFTER the branch merge, by every lane; only surviving (odd-x) lanes'
color/buffer output reaches memory (per §1.5/§1.6 below), so the buffer record is read
from a lane that was never itself discarded.

**H4 (frozen, the OPT-09/GLFS-A02 headline test):** if Apple9 discard has SPIR-V demote
semantics (helper lane keeps executing straight-line code after the kill point), the
surviving neighbor's `fwidth()` reflects the discarded neighbor's post-discard mutation:
predicted exact value `abs((x_survivor) - (x_discarded + 1000)) = 999.0` for adjacent
quad lanes at fragcoord step 1. If discard is a true terminate (no further instructions
execute), the mutation never happens and `fwidth()` matches the no-discard control's
`1.0` exactly. **Falsifier:** any value other than these two exact predictions (e.g. a
stale/frozen or garbage/undefined third value) refutes both simple hypotheses and must
be reported as such. `kernels/d_demote_after.metal` (identical, but discard placed AFTER
the `fwidth()` read) is the statement-order control: it must read `1.0` regardless of
the demote/terminate answer, since no lane's mutation exists yet at read time.
`kernels/d_quad_shuffle.metal` independently cross-checks via `quad_shuffle_xor`
retrieving a post-discard-computed marker value directly from the discarded lane's own
register file (predicted exact value `px*1000+py+7777` evaluated at the discarded
lane's own `(px,py)`, if demote holds).

### 1.5 Suppression matrix design (GLFS-A06, cross-validating GLFS-A02/A03)

`kernels/g6_suppress.metal`: even-x lanes discard, then ALL lanes (including the
discarded ones) unconditionally execute, in program order after the branch merge: (1) a
per-lane-uniquely-indexed device buffer store into a pre-poisoned (`0xEE` fill) slot,
(2) a global atomic increment, (3) a color output write, (4) an explicit `[[depth(any)]]`
output write. **H5 (frozen):** for each of the four channels independently, the
discarded lanes' slot either stays poisoned/unincremented/unwritten (suppressed) or is
overwritten with the expected computed value (not suppressed); `g6_suppress_control.
metal` (identical, no discard) is the paired baseline proving the harness can detect an
unsuppressed write on every channel. No specific direction is pre-committed per channel
— this is the open question the addendum asks; all four are recorded as observed.

### 1.6 Depth-ordering design (GLFS-A05)

`analysis/gen_e_kernels.py` generates the `kernels/e_*.metal` family: a vertex shader
whose rasterized (fixed-function) depth is the **unclamped** affine function
`z=(ndcx+1)/2` of screen-space NDC x (clamping at the oversized "big triangle"'s
vertices was tried in pilot and found to distort the visible-region gradient by exactly
2x — documented as a fixed pilot bug, not promoted); at width W this produces a clean
left(z<0.5, pass under Less)/right(z≥0.5, fail) split against `clearDepth=0.5`. Each
variant records, per pixel, an unconditional atomic "the shader body ran" counter fired
as the very first shader statement (so it fires regardless of any later discard),
crossed with `{no attribute, [[early_fragment_tests]]} x {no discard, y<H/2 discard} x
{fixed-function depth, explicit [[depth(any)]] shader output}`.

**H6 (frozen):** ordinary (no attribute) and shader-depth-output testing are LATE — the
per-pixel "ran" counter fires for both the depth-pass and depth-fail region (the shader
always launches; the test is applied to the already-computed result).
`[[early_fragment_tests]]` is EARLY — the "ran" counter is zero for the depth-fail
region (the shader launch itself is skipped). **Falsifier:** any configuration where the
"ran" counter for the fail region is nonzero under `[[early_fragment_tests]]`, or zero
under ordinary/shader-depth-output testing. Occlusion-query count is read independently
in every configuration to test **which effects a later discard can and cannot undo**:
the open, not-pre-committed question is whether an early-tests pass that already
incremented the visibility counter can be retroactively cancelled by a later
`discard_fragment()` inside the (launched) shader.

### 1.7 Sample-shading invocation model (GLFS-A07)

`kernels/f_persample_count.metal` (`[[sample_id]]` declared) vs `f_perpixel_count.metal`
(not declared) each atomically increment a `(pixel,sample)`-indexed counter at N∈
{1,2,4}. **H7 (frozen):** per-sample shading launches exactly one invocation per
covered `(pixel,sample)` pair (each slot reaches exactly 1). The per-pixel case's
invocation-frequency behavior at N>1 is the **open** question this probe exists to
answer — no direction is pre-committed; MSL exposes no `MinSampleShading`-style
fractional-rate control at all (checked against the public Metal Shading Language
specification — a `PUBLIC`-sourced negative result, not a hardware test), so Metal's
only knob is the binary presence/absence of `[[sample_id]]`.
`kernels/f_persample_discard.metal` (odd `sample_id` invocations discard) cross-checks
per-sample kill granularity and per-invocation helper-status recorded before/after the
discard (GLFS-A03).

## 2. Independent / controlled variables

- **Independent:** which language construct (`discard_fragment()` / `[[sample_mask]]`
  write, constant vs. branch/buffer-sourced) — group `loc`; which byte is spliced and
  to what value — group `splice`; sample count N and mask bit pattern — group `msaa`;
  discard placement (before/after the derivative read; unconditional/per-lane/
  per-sample) and probe channel (fwidth, quad_shuffle, implicit-LOD sample, is_helper,
  buffer/atomic/color/depth) — groups `demote`/`suppress`; `[[early_fragment_tests]]`
  presence, discard presence, and depth-output mode — group `depth`; `[[sample_id]]`
  presence and sample count — group `sampleshading`.
- **Controlled:** M4/G16G, this host, macOS 26.6.2 (25G82), Metal 4, Apple clang
  21.0.0 (clang-2100.1.1.101); `MTLCompileOptions.fastMathEnabled=YES` (default) for
  every case (no case in this experiment varies fast-math); single-triangle,
  vertex_id-driven full-target coverage geometry (or the documented partial-coverage
  variant for the original-helper case) so pixel/quad topology is identical across
  paired cases; fresh `MTLDevice`/process per case (`fsrun` is one-shot).
- **Paired controls:** every `demote`/`suppress` kernel has a no-discard control
  (`d_control_nodiscard`, `g6_suppress_control`); every `depth` variant is one cell of a
  complete 2x2x2-ish factorial rather than an isolated case; `splice` has an unspliced-
  archive baseline plus a positive control (color-op corruption) proving the mechanism
  can detect change.

## 3. Frozen case matrix

The complete, frozen case matrix is `run.py`'s `build_cases()` (78 cases: 9 `loc`
compile-scans, 25 `splice` GPU dispatches, 22 `msaa` GPU dispatches, 7 `demote` GPU
dispatches, 6 `depth` GPU dispatches, 2 `suppress` GPU dispatches, 7 `sampleshading` GPU
dispatches). `python3 run.py --list` enumerates it; `work/pre_reg_hashes.txt` pins the
sha256 of every authored kernel/harness/analysis/runner file at freeze time. No case is
added, removed, or reparameterized between run01 and run02.

## 4. Raw record schema (frozen; see `schema.py`, the single shared key-set)

Every case produces exactly two sibling JSON files: `<case_id>.gated.json` (byte/value-
deterministic: case id, group, kind, exact params, status, structured result — pixels,
depth, occlusion, buffer hex, or the compile-scan payload) and `<case_id>.nongated.json`
(GPU timing, wall-clock, pid — never compared across runs). `run.py` asserts the key set
of every written record against `schema.GATED_KEYS`/`NONGATED_KEYS` before writing, so a
schema drift fails loudly instead of silently producing an incomparable record.

## 5. Environment (frozen)

```
git revision (agx-re, recorded for provenance, NOT a cross-run gate): 1e0c481a96eb595b5b1f41b19d07a911a43c75a2
host: Apple M4, 10 GPU cores, macOS 26.6.2 (25G82), Metal 4
compiler: Apple clang version 21.0.0 (clang-2100.1.1.101), arm64-apple-darwin25.6.0
pre-registration freeze timestamp (UTC): 2026-08-28T02:09:49Z
authored input hashes: work/pre_reg_hashes.txt (34 files)
```

## 6. Timeouts

- Per-case GPU dispatch (`fsrun`): 60 s hard timeout (well under the 300 s cap), enforced
  by `subprocess.run(..., timeout=...)` in `run.py`; a timeout is recorded as
  `status="HANG"`, never silently dropped.
- Per-case host compile (`shdump`/`agxparse`/`agxisa` tokenize): 120 s hard timeout.
- Harness: single-threaded, one case per process, one case fully recorded (both sibling
  files written, `print` + implicit line-buffered flush via `run.py`'s own stdout, and
  `fsrun.m` itself calls `fflush(NULL)`+`ferror` before every exit path) before the next
  case starts.

## 7. What would falsify each frozen hypothesis (summary)

See §1.1–1.7 above for the per-hypothesis falsifier. In addition: any GPU fault, hang,
or command-buffer error during any case is recorded as that case's result and reported
in `RESULTS.md`, not discarded; any of the 25 `splice` cases producing a *different*
outcome on run01 vs run02 (a true intermittency, distinct from the deterministic-
zeroing pattern EXP-0087 found for the unrelated register-move family) blocks promotion
of that specific case to `HW-VALIDATED` pending a third run.
