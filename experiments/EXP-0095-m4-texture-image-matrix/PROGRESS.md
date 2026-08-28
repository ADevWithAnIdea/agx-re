# PROGRESS — EXP-0095 (Bundle E: GLTEX-A04/A05/A06/A07, GLIMG-A01/A02)

Timestamps UTC. Append-only; each entry added after a real milestone.

## 2026-08-28T20:10Z — relaunch after host/terminal interruption
Coordinator confirmed the interruption was environmental, not caused by prior work, and that
the directory held scaffolding only (no PRE_REGISTRATION.md, no CAPTURE_CONTRACT.json, no
raw/ captures) at relaunch — consistent with what was actually on disk: kernels/matrix.metal,
kernels/direct128.metal + its generator, and work/explore/* (pre-freeze, non-evidence
feasibility probes) survived and needed no recovery. Nothing was lost because nothing had been
frozen or captured yet.

New instruction before freezing the contract: read `apple9_isa_explainer.md` and
`work/COMPILER-EXPLAINER-INTERACTION-20260828.md` (repo root / repo work/). Summary relevant to
this experiment: an external compiler engineer's ALU-operand source-retention model, cross-checked
against `tools/agx-isa/db.json`, found that field's 7-bit `srcA_reg`/`srcB_reg` decode is wrong for
the compact float ALU form — the top bit is a retention flag, not part of the register index, so
register numbers >= 64 from our disassembler are suspect. EXP-0099 is validating this on hardware
now (not this experiment). **Applicability check: this experiment never invokes the ISA
assembler/disassembler (`tools/agx-isa`) or `tools/agxtest` splicing anywhere — the entire matrix is
public-Metal API behavior (compile / pipeline-create / dispatch / readback).** The one place this
experiment's design brushes ISA register semantics is GLTEX-A04's question of whether the hardware's
array-layer "extra coordinate" register is float-typed or a pre-rounded integer; that was already
scoped OUT to UNKNOWN/deferred-to-assembler-successor before this message arrived, for unrelated
reasons (no public-Metal float-layer overload exists to probe it). This caveat is recorded verbatim
in PRE_REGISTRATION.md and RESULTS.md.

## Milestones already completed (pre-freeze, not evidence; work/explore/ only)
- Confirmed compile-checker tool `work/explore/compilecheck.m` (public Metal, own-authored).
- 1D/1D-array MSL surface: only implicit-LOD `sample`, `read`, `write`, `get_width`/
  `get_num_mip_levels`/`get_array_size` exist; no bias/level/gradient/offset/gather/shadow
  compiles for texture1d(_array); no `depth1d` type exists.
- depth2d_array/depthcube/depthcube_array: compare implicit/level/bias/gradient/offset(2darr
  only)/gather_compare all compile; depth textures reject `access::write` (populate via CPU-side
  `replaceRegion:` instead, not a populate kernel).
- Native texture atomics (`atomic_fetch_add` etc.) are exposed by MSL on 1D/1D-array/2D/2D-array/
  3D/texture_buffer but the AIR backend rejects (unlowered call) `texturecube`/`texturecube_array`
  atomics at pipeline-creation time — real Metal-level negative result for GLIMG-A02.
- Direct `[[texture(N)]]` argument-table ceiling for a compute function = exactly 128 (127 OK,
  128 OK, 129 is an MSL compile-time "out of bounds" error) — reproduced 17-point sweep.
  A SEPARATE, narrower ceiling: `access::read_write` textures are capped at exactly 8 per
  function regardless of the 128 direct-table size (7 OK, 8 OK, 9 fails to compile);
  `access::write` (write-only) is NOT subject to this narrower cap (scales to 128 like read).
  Atomics require read_write, so the direct-binding atomic capacity kernel is RW_N=8, not 128.
- Bindless (argument-buffer, `array<texture2d<float>,4096>`) texture array: compiles and creates
  a pipeline at N=4096, far beyond the 128 direct ceiling (tested feasibility only, not capacity
  saturation).
- Texel-buffer width ceiling: exactly 2^28 = 268,435,456 elements, uniform across texel byte
  sizes tested (1/2/4/8/16 bytes; RGB32 is not an available MTLPixelFormat at all — no
  `MTLPixelFormatRGB32*` constant exists in the public enum, confirmed by compile-time lookup).
  Width 2^28+1 aborts the PROCESS (SIGABRT) inside `-[MTLTextureDescriptor validateWithDevice:]`
  before any GPU submission — uncatchable by `@try/@catch` (assertion, not an NSException).
- `kernels/matrix.metal` (72 kernel functions) and `kernels/direct128.metal` (5 functions,
  generated deterministically by the committed `kernels/gen_direct128.py`) both compile clean
  and every function creates a `MTLComputePipelineState` (`work/explore/compilecheck`, itself
  not part of the frozen evidence — a feasibility gate only).

## Next
Write harness/probe.m (generic per-family dispatcher driven by a `--case-args` JSON blob),
CAPTURE_CONTRACT.json (frozen matrix), PRE_REGISTRATION.md, run.py/verify.py/analysis.py/
make_manifest.py (adapted from EXP-0079's five-gate template), then two capture runs.

## 2026-08-28T21:10Z — matrix design finalized (85 cases), harness built and validated pre-freeze
Built the generic JSON-driven ObjC harness (`harness/probe.m`): one case = one process, resources
(textures/samplers/uniform-buffers/argument-buffers) and a dispatch sequence described by one JSON
blob, uniform 96-byte guarded output-buffer convention across every family. Authored 74 MSL kernels
(`kernels/matrix.metal`) + 5 generated (`kernels/direct128.metal` via `kernels/gen_direct128.py`).
Iteratively validated end-to-end against real M4 hardware in `provenance/pre_freeze/` (NOT frozen
evidence) and fixed three real bugs found this way before freezing: (1) the OUT buffer offset was
bound at byte 0 instead of byte 16, corrupting the prefix guard; (2) same-thread same-invocation
write-then-read needs an explicit `t.fence()` call on this hardware/Metal stack (13 kernels fixed);
(3) `k_a02_direct_atomic`'s frozen case bound plain `texture2d` resources where the kernel declares
`texture_buffer<uint, access::read_write>` arguments (type mismatch, silently wrong result) — fixed
by adding a dedicated `direct_texture_buffers()` case-generator helper. Also corrected two
mis-derived "expected value" bugs in the case generator itself (a06 compare-function polarity was
backwards; a02_bindless_write's per-word expected-value list was miscomputed) after the real
hardware output disagreed with my own arithmetic — re-derived correctly from EXP-0034's established
`ref COMPARISON storedDepth` convention and confirmed the corrected values now match. Final pre-freeze
dump: 85/85 cases run to completion, 0 real mismatches against the (corrected) hypotheses.

## 2026-08-28T21:15Z — froze PRE_REGISTRATION.md, CAPTURE_CONTRACT.json (85 cases, pinned revision
`b05383c5a40653b1176b0345806af1955bb87659`), README.md; wrote run.py/verify.py/analysis.py/
make_manifest.py adapted from EXP-0079's proven five-gate pattern to this experiment's uniform
generic case schema.

## 2026-08-28T21:20Z — PRE_GPU gates all passed on the first attempt
`make_manifest.py --write/--check`, `verify.py --selftest`, `verify.py --seqtest` (4/4/5 real
subprocess checks), `verify.py --preflight` — all PASS, no repairs needed.

## 2026-08-28T21:22Z — run01 captured
`run.py --execute --run-id m4-20260829-run01`: completed in 6.3s wall-clock, 85/85 case receipts
(83 exit 0, 2 exit -6/SIGABRT as pre-registered), no STOP.json. `make_manifest.py`,
`verify.py --between-runs` PASS.

## 2026-08-28T21:24Z — pre-run02 gates re-passed with run01 present
`verify.py --selftest` (the exact invocation class that quarantined EXP-0075) and `--seqtest` both
PASS with `raw/m4-20260829-run01` on disk.

## 2026-08-28T21:25Z — run02 captured; analysis + final gate
`run.py --execute --run-id m4-20260829-run02`: 4.0s wall-clock, identical shape to run01.
`analysis.py --write`: `repeat_exact: true`, 83 match / 0 deviation / 2 abort_confirmed out of 85.
`make_manifest.py`, `verify.py --captured` PASS. **Experiment COMPLETE.**

## 2026-08-28T21:35Z — RESULTS.md written; final gate re-verification after the RESULTS.md edit
`make_manifest.py --write/--check`, `verify.py --selftest`, `--seqtest`, `--captured` all re-PASS
after replacing the RESULTS.md placeholder with the full observed/interpreted writeup and finite-
resource table. No further changes to any hash-frozen file after this point.
