# PRE_REGISTRATION — EXP-0093 M4 fence/barrier instruction family + raster-order-group interlock

Target: **local Apple M4 (G16G) only.** No A18 Pro claim anywhere (A18 hands-off per
`CLAUDE.md`). macOS 26.6.2 (25G82), Metal 4, `xcrun` version 72, `clang` 21.0.0
(clang-2100.1.1.101). Device: Mac16,10 / Apple M4, 10 GPU cores.

**Pinned revision:** `14017e25641402e10f98100d1a3696175fc0e982` (0 tracked
modifications; untracked sibling-experiment files present, not gated on — per
`experiments/SUBAGENT_BRIEF.md`, repo `HEAD` moving because a sibling experiment lands
is not contamination; only the authored source-file hashes below are load-bearing).

Answers `GLFS-A08` (`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md:253-271`) and `ATOM-07`
through `ATOM-11` (`APPLE9_RE_IMPLEMENTATION_GAPS.md`, "P0 — Atomics and
synchronization"). Builds directly on, and does not redo:

- `experiments/EXP-0085-m4-memory-interlock-atomics/RESULTS.md` — closed ATOM-01..06;
  explicitly deferred ATOM-07..11 to "a dedicated splice campaign against the `0x07`
  family's `mem_scope`/`kind` fields", flagging an unexplained `scoreboard_fence
  kind=0x22` op as raw evidence for this successor.
- `experiments/EXP-0091-m4-fragment-sample-discard/RESULTS.md` — located a 6-byte
  companion op in the same `0x07` family (`07 02 54 01 <B4> <B5>`) after the fragment
  kill/mask submission op, and a distinct unconditional epilog (`07 02 54 0c 02 00`).
- `experiments/EXP-0025-scoreboard/RESULTS.md` — HW-splice-proved the compute
  `threadgroup_barrier` (`07 04 54 <mem_scope> <flags> 00`) is the only explicit
  compute ordering op; A18/G17P.
- `experiments/EXP-0029-fragment-isa/RESULTS.md` — byte-diff (not splice-proved)
  located a `pixel_order` acquire/release pair for raster-order-groups:
  `07 14 54 50 06 00` (acquire) / `07 04 54 d0 06 00` (release); explicitly flagged
  "not splice-proven for a stale read — needs overlapping-fragment geometry". This
  experiment supplies exactly that missing overlapping-fragment geometry.
- `experiments/EXP-0051-m4-synchronization-litmus/RESULTS.md` — API-level litmus
  methodology (mailbox message passing, bounded spin-wait); found 0 mismatches for
  BOTH relaxed and device-fenced cross-threadgroup publication at 1-2-threadgroup
  scale, explicitly left as "not isolated... not an isolated native fence-instruction
  semantics" (PARTIAL, P1.4 not closed).
- `docs/isa/register-move-and-liveness.md` — methodological warning honored throughout:
  every splice below is validated with a LATER-READ / cross-lane invariant, never just
  the spliced instruction's own immediate result; every dispatch has a hard timeout;
  one change isolated per splice comparison.

## 1. Questions and falsifiable hypotheses

### H-DECODE (0x07-family selector map)

**Claim.** The `0x07`-family fence/barrier group is disambiguated primarily by
`byte+2` (`0x54` selects the 6-byte "long" sub-family shared by
`threadgroup_barrier`/`mem_fence`/`pixel_order`/the fragment epilog/kill-companion,
vs `0x00`/`0x02` selecting the unrelated 4-byte `scoreboard_fence` CF-edge family),
and within the 6-byte sub-family by `byte+1` (sub-op) and `byte+3` (scope, whose bit0
toggles "adds an execution barrier" — see H-ATOM10). A `mem_texture`
`threadgroup_barrier` compiles to a genuine ACQUIRE(`byte+1=0x14`)/RELEASE
(`byte+1=0x04`) instruction PAIR, structurally identical in shape to the fragment-side
`pixel_order` pair — not the single-instruction shape of `mem_none`/`mem_threadgroup`/
`mem_device`.

**Falsifier.** Own-compile census (`kernels/c_barrier_mem_texture.metal`,
`kernels/c_fence_device_seqcst.metal`, `kernels/census_rog_*.metal`) produces bytes
inconsistent with this map (e.g. `mem_texture` compiles to one instruction, or its
`byte+1` values don't match the `0x14`/`0x04` acquire/release split already observed
for `pixel_order`).

**Method.** Own-MSL differential compilation only (`OWN-SHADER-DIFF`/`STRUCTURAL`) —
no GPU dispatch needed for pure byte-shape claims; captured as `structural_compile`
cases with a SHA-256 fingerprint of the extracted stage hex (deterministic given
frozen source, therefore exactly cross-run-reproducible with no exclusion needed).

### H-ROGIDX (raster-order-group index namespace, finite-resource mandate)

**Claim.** `[[raster_order_group(N)]]` compiles to structurally distinct bytes only
for `N ∈ {0,1,2}` (a bit-shifted tag, `<<2` per step, in three per-kernel tile-bracket
`byte+3` fields); every tested `N ≥ 3` (through `65535`) compiles BYTE-IDENTICAL to
`N=0` — silent aliasing to group 0, not a compile rejection.

**Falsifier.** Any `N ≥ 3` produces bytes distinguishable from `N=0`, or the compiler
rejects some `N` outright.

**Method.** Own-compile sweep, `ROG_INDEX_SWEEP` (20 points), SHA-256 fingerprint per
index; identical fingerprints across `N≥3` and `N=0` is itself dispositive (same
compiled bytes on this hardware/toolchain necessarily produce the same runtime
behavior — no further GPU run is needed to establish the aliasing fact once byte
identity is shown). `STRUCTURAL`.

### H-ROGTEX (GLFS-A08 primary: texture raster-order-group is a real mutual-exclusion
primitive)

**Claim.** N overlapping fragments (same target pixel, N instances of one
full-screen-triangle draw) each doing a non-atomic read-modify-write increment of a
shared `read_write texture2d<uint>` counter, protected by `[[raster_order_group(0)]]`,
produce a FINAL counter value of EXACTLY N regardless of N (deterministic invariant).
Removing the tag (WEAK control) breaks this at N > 1. Splicing the compiled ACQUIRE
and/or RELEASE op's `byte+3` scope field to `0x00` (on the otherwise byte-identical
"strong" binary) ALSO breaks it — the causal, HW-VALIDATED tier of evidence.

**Falsifier.** Strong case final ≠ N at any tested N; OR the weak control's final ==
N (no race observed, refuting "ordinary device-memory visibility ≠ raster-order
serialization"); OR a spliced-neutered binary still produces final == N (the byte
field is not causally load-bearing).

**Method.** `harness/roglitmus.m`, `kernels/litmus_rog_tex*.metal`; splice via
`harness/splice.py`. Interactively probed at N ∈ {16, 4096, 65536} before freezing —
strong: exact N every time; weak: collapsed to 1 (near-total loss) every time;
splice-neutered (acquire-only, release-only, or both): collapsed to 1, matching the
weak control; splice-identity (same bytes, re-copied through the splice pipeline):
still exact N (rules out the splice mechanism itself as a confound). `HW-VALIDATED`.

### H-ROGBUF (GLFS-A08, buffer/image distinction — ATOM-11 fragment side)

**Claim.** The SAME invariant (final == N) holds for a `device uint*` buffer counter
tagged `[[raster_order_group(0)]]`, but the CAUSAL MECHANISM DIFFERS from the texture
case: the actual serializing primitive is a pair of `0x87 02 54 <08|04> 00 00`
tile-access "bracket" ops (shared in BYTE SHAPE with the texture case, and — per
H-ROGIDX — the same bytes the ROG index selects), not the single `07 04 54 c4 08 00`
fence-shaped op also present in the buffer-ROG compiled output. Concretely:
neutering the bracket ops' `byte+3` fields breaks the invariant; neutering ONLY the
`07 04 54 c4 08 00` fence's `byte+3` (or `byte+4`) does NOT.

**Falsifier.** Neutering the bracket ops leaves final == N; OR neutering only the
`c4` fence also breaks it (would refute the claimed mechanism split).

**Method.** Same harness, `kernels/litmus_rog_buf*.metal`. Interactively probed at
N=4096: identity splice → exact N; `fence_scope_only` (byte+3 `0xc4→0x00`) → still
exact N (4096); `brackets_only` (both bracket `byte+3` → `0x00`) → collapsed to
~280/4096 (partial, not total, loss — recorded as-is, not over-interpreted); `all`
(brackets + fence) → ~277/4096, consistent with the brackets carrying the effect.
`HW-VALIDATED` for "bracket bytes are causally necessary"; `HW-VALIDATED` (negative)
for "the `c4` fence's own scope/flags bytes are not, on their own, sufficient to
explain the invariant's breakdown when removed".

### H-ATOM0708 (relaxed atomics carry no implicit device fence; the fence is what
restores acquire/release visibility)

**Claim.** A cross-threadgroup message-passing mailbox (payload words + relaxed
ready/ack flags, `kernels/litmus_devfence_pairs.metal`, generalizing EXP-0051's
1-2-threadgroup mailbox to `PAIRS` independent producer/consumer threadgroup pairs in
one dispatch) shows: (a) at `PAIRS=1` (EXP-0051's own scale), 0 mismatches even fully
relaxed — reproducing EXP-0051's finding and explaining why it did not observe a
violation; (b) at `PAIRS≥4`, fully-relaxed (RR) shows REAL, large-magnitude payload
corruption (message words not matching what the flag-observation should have
guaranteed); (c) fully-fenced (`atomic_thread_fence(mem_device, seq_cst,
thread_scope_device)` on both producer-before-flag-store and consumer-after-flag-load,
FF) shows 0 mismatches at every tested scale; (d) asymmetric fencing (FR, RF) is
NOT a full fix — both sides matter, and do not contribute equally.

**Falsifier.** RR at `PAIRS≥4` shows 0 mismatches (no violation to explain); OR FF
shows any mismatch at any tested scale (the fence would not be suffient — would
falsify the safe driver fallback).

**Method.** `harness/fencelitmus.m`. Interactively probed: PAIRS=1,2 RR → 0/50, 0/100
mismatches; PAIRS=4 RR → 200/200 (100%); PAIRS=8 RR → 200/400 (50%, repeat: 200/400);
PAIRS=8 FF → 0/400 (repeated); PAIRS=8 FR (producer-fenced only) → 12/400; PAIRS=8 RF
(consumer-fenced only) → 202/400 (~= RR). Spin bound 500,000 iterations
(NEVER unbounded — a timeout is recorded as data, never a hang) confirmed sufficient
(0 producer/consumer timeouts observed in every build-time probe). `HW-VALIDATED`.

### H-ATOM09 (threadgroup barrier convergence is coupled to, but not gated by, the
requested memory-fence class)

**Claim.** `threadgroup_barrier(mem_none)` compiles to the SAME 6-byte instruction
shape as `mem_threadgroup`/`mem_device` (own-compile census: `07 04 54 41 09 00`),
and — HW-validated via EXP-0025's own `tgdiv2` per-lane variable-delay convergence
kernel, ported unmodified except for the requested `mem_flags` — still provides FULL
threadgroup-memory execution convergence and visibility (0/256 stale reads, byte-exact
match to the `mem_threadgroup` baseline), even though its `mem_scope` tag nominally
requests no memory class. There is no separate "convergence-only, no instruction"
form.

**Falsifier.** `mem_none` compiles to a structurally different (or absent) op; OR the
`tgdiv2`-style convergence test shows stale reads under `mem_none` (would mean the
memory-class tag genuinely gates visibility, not just an inert label).

**Method.** `kernels/tgdiv2_mem_none.metal` vs `kernels/tgdiv2_baseline.metal`/
`kernels/tgdiv2_baseline_none.metal`, run via `tools/agxtest/agxtest.py` (read-only
tool usage), 256-lane grid, exact-value comparison against the closed-form LCG
recurrence (`casematrix.tgdiv_expected_output()`), not just a sentinel/stale check.
Interactively probed: `mem_none` output byte-identical to `mem_threadgroup` baseline
(0 mismatches vs. the 128/256 the no-barrier control shows). `HW-VALIDATED`.

### H-ATOM10 (a device-scope barrier requires a distinct encoding from a standalone
device fence — and the distinguishing bit is a genuine execution-convergence enable,
not just a scope-tag difference)

**Claim.** `byte+3` bit0 (`0x85` barrier+device-fence vs `0x84` fence-only,
`0x1000_0101` vs `0x1000_0100`) is the execution-convergence bit. Splicing it OFF on
a compiled `threadgroup_barrier(mem_device)` (using `kernels/tgdiv2_dev.metal`, a
DEVICE-memory port of `tgdiv2`) reintroduces the exact 128/256 stale-read race of the
no-barrier control. Splicing it ON on a compiled standalone
`atomic_thread_fence(mem_device, seq_cst, thread_scope_device)`
(`kernels/tgdiv2_dev_fenceonly.metal`, which races 128/256 unspliced, matching the
no-barrier control) ADDS full convergence (0/256), symmetric to the forward direction.

**Falsifier.** Either splice direction fails to change the race outcome as predicted.

**Method.** `tools/agxtest/agxtest.py --splice _agc.main@133=84` (forward) and
`@133=85` (reverse) against the two archives, `--buf 2=<0xdeadbeef sentinel>` to make
a stale (unconverged) read unambiguous, output compared against the exact LCG
recurrence. Interactively probed and reproduced exactly as predicted in both
directions. `HW-VALIDATED`.

### H-GLFSA08 (compiler-facing verdict)

**Claim.** Apple9 provides fragment-ordered ("raster-order-group" / pixel-interlock)
access via a resource-scoped acquire/release fence PAIR (texture case) or a
tile-access bracket-pair mechanism (buffer case) emitted automatically by the
compiler around any access to a resource declared with a matching
`[[raster_order_group(N)]]` tag on both the read and the write; a compiler targeting
this hardware must emit the SAME acquire/release-or-bracket pair around every access
to a `raster_order_group`-tagged resource inside the interlocked region, using ONLY
`N ∈ {0,1,2}` as independently addressable groups (H-ROGIDX). This is answered to the
depth this experiment's matrix reaches; GLFS-A08's full requested matrix (MSAA
per-sample granularity, multiple render targets, nesting, discard-inside-region
release-on-every-exit, deadlock/forward-progress under malformed sequences) is
explicitly OUT OF SCOPE for this increment — see PROGRESS.md/RESULTS.md "Deferred".

## 2. Independent / controlled variables

- Independent: ROG source-level presence/tag (strong/weak), splice target byte(s),
  raster_order_group index, device-fence presence/scope/side (producer/consumer),
  `mem_flags` argument, `PAIRS` concurrency scale, instance count `N`.
- Controlled: toolchain/OS build (frozen above), `fastMathEnabled=YES` (matches
  `tools/shdump/shdump.m`'s default — required for AIR-hash identity between the
  splice-mode identity compile and the archived binary), grid/threadgroup shapes,
  RNG-free deterministic payload generators (`asymmetric()`, the LCG recurrence).

## 3. Confounders considered

- **AIR-hash mismatch silently falling back to unspliced code.** Mitigated: every
  splice-mode run asserts `PIPELINE_SOURCE archive` (from `MTLPipelineOptionFailOnBinaryArchiveMiss`
  — a mismatch FAILS pipeline creation outright rather than silently recompiling),
  and `roglitmus.m`/`fencelitmus.m` use the exact same `fastMathEnabled=YES` as
  `shdump.m` for exactly this reason (an earlier build-time attempt using
  `MTLMathModeSafe` reproducibly hit `PIPELINE_MISS`).
- **GPU occupancy / scheduling determining whether a race is even reachable.**
  Directly why `PAIRS` is swept (1/2 too small to reproduce EXP-0051; 4/8 large
  enough) rather than fixed at one scale.
- **Coincidental non-serialization at small N.** Mitigated by the `ROG_N_SWEEP`
  (64/4096/65536) and repeats (3x); the invariant is exact-equality, not a
  statistical threshold, so any single N=1 case failing at any repeat is already
  dispositive of "not exact".
- **Nondeterministic race detail across the two official runs.** `mismatch`/
  `producer_timeouts`/`consumer_timeouts`/`completed` (family `devfence_pairs`) and
  `final_hex` for WEAK/neutered ROG cases are DECLARED order-sensitive
  (`casematrix.case_order_sensitive_keys`) and excluded from the strict cross-run
  byte-identity gate; the coarse PASS/FAIL verdict (did the invariant/expectation
  hold) is never excluded. `tgdiv`/structural/STRONG-ROG/identity-splice cases are
  fully gated (build-time repeats showed byte-exact reproduction with no declared
  exclusion needed).
- **`tools/agxtest` buffer content interpretation.** `--int` prints signed int32;
  the LCG recurrence and its sentinel are compared via a shared `s32()` helper in
  both the runner and the fixture-grounded selftest, avoiding a sign-convention
  mismatch between producer and checker.
- **Metal's own scheduler placing a small `PAIRS` count entirely on one core.**
  Not directly controllable through the public API (no explicit core affinity);
  this is exactly the reason `PAIRS` is swept rather than asserted from a single
  point, and is stated as a limitation, not resolved.

## 4. Frozen case matrix

`harness/casematrix.py::build_matrix()` — **128 cases**, families `rog_tex` (18),
`rog_buf` (18), `rog_tex_splice` (16), `rog_buf_splice` (8), `devfence_pairs` (24),
`tgdiv` (16), `structural` (28). Full listing: `python3 harness/run.py --list`.
Every case's expected verdict (PASS/FAIL semantics per family) is frozen in
`casematrix.py` itself (`expect_exact`/`expect_race`/`expect_converge` fields per
case), not decided post-hoc from the captured data.

## 5. Raw-record schema (frozen, `harness/schema.py`)

Gated record keys (byte-compared across runs, minus declared order-sensitive
`observed` sub-keys): `case_id, family, kind, params, status, verdict, observed`.
Non-gated sibling record keys (never gated, carries exact race/timing detail):
`case_id, gputime_ns, wall_ms, pid, raw_tail`. One shared schema module imported by
both `run.py` and `verify.py` — standing gate (a).

## 6. Environment / timeouts

- `RUN_TIMEOUT_S = 90` (GPU dispatch, per case, hard `subprocess.run(..., timeout=)`).
- `COMPILE_TIMEOUT_S = 120` (own-MSL compile, per case).
- Every case is its own process (`roglitmus`/`fencelitmus`/`agxrun` invoked fresh via
  `subprocess.run`); a timeout is recorded as `status=HANG, verdict=TIMEOUT`, never
  silently dropped, never retried in a loop.
- Spin bound inside `msg_pairs_*` kernels: 500,000 iterations per wait — bounded,
  never an unbounded loop; a spin exhaustion increments a timeout counter and returns,
  it does not hang the dispatch.
- Smoke gate (`run_smoke()`): one real GPU dispatch (`litmus_rog_tex`, N=16, plain
  mode), 30s timeout, written to `work/<run_id>_smoke.json` — NEVER to `raw/`
  (standing gate (c)). A failing smoke gate aborts the run before any `raw/`
  directory is created.

## 7. Two capture runs

`raw/m4_20260828_run01/`, `raw/m4_20260828_run02/` — distinct, never-reused run ids
per the standing rule (EXP-0085 precedent: never overwrite/reuse a run id; a defective
capture is retained and superseded by a new id, never repaired in place).

## 8. Clean-room provenance

```text
Clean-room provenance: HW-PROBE / OWN-SHADER
Inputs inspected: authored MSL (kernels/*.metal), authored ObjC harnesses
  (harness/roglitmus.m, harness/fencelitmus.m), authored Python
  (harness/schema.py, harness/casematrix.py, harness/run.py, harness/verify.py,
  harness/splice.py), read-only use of tools/shdump, tools/agxtest, tools/agx-isa
  (unmodified) on our own compiled kernel bytes.
Apple binary introspection: NONE.
Apple auxiliary/helper code inspection: NONE.
Command/BO scan or pointer following beyond our own allocated buffers: NONE.
Target qualification: local M4/G16G only; no A18 Pro claim.
```
