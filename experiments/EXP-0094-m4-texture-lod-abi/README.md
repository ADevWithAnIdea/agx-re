# EXP-0094 -- M4 texture bias/gradient/implicit-LOD ABI (addendum Bundle D)

**Closes:** GLTEX-A01 (bias operand / effective-LOD semantics), GLTEX-A02 (explicit-gradient
ABI + bias/gradient-operand register isolation), GLTEX-A03 (implicit LOD + `textureQueryLOD`).
Deepens `TEX-05`, `TEX-24`, `TEX-27`, `FS-04`..`FS-06`.

**Question.** What is the exact Apple9 encoding and runtime behavior of the shader `bias()`
operand and the explicit-gradient (`gradient2d`/`gradientcube`) operand, including their
register-level ABI, their interaction with sampler LOD clamps and mip count, their behavior at
zero/boundary/huge-magnitude/Inf/NaN inputs, and -- for cube maps -- whether native gradient
sampling matches an independently computed OpenGL reference at face boundaries and major-axis
ties (deciding whether Mesa's `lower_txd_cube_map` stays mandatory)?

**Method.**
1. **Own-shader differential compilation** to isolate the bias-operand / gradient-operand
   register field, building on the already-located `op+2` mode selectors (`0x07` bias, `0x04`
   grad, EXP-0016/EXP-0034). See PROGRESS.md for the full method history (three iterations were
   needed: the AGX compiler hoists any operand computed purely from `constant`-address-space data
   into the shader PREAMBLE, so the first two attempts produced byte-identical `_agc.main`
   regardless of register pressure -- the operand had to be routed through a genuinely
   per-invocation-varying source, either a per-vertex interpolated `[[stage_in]]` varying
   (fragment/bias) or a `[[thread_position_in_grid]]`-offset buffer read (compute/grad), to force
   real per-lane residency).
2. **HW splice validation** (downstream-consumer readback, per
   `docs/isa/register-move-and-liveness.md`'s silent-zero warning): the isolated byte is flipped
   in a real compiled archive and the FINAL RENDERED PIXEL (several instructions and a real
   texture-unit LOD computation downstream) is observed to change exactly as the differential
   compilation predicted. `regsplice_bias` backend below.
3. **Public-Metal behavioral sweep** of bias / gradient / LOD-query values: zero, signed zero,
   ordinary +/-, in-range endpoints, first-out-of-range value, very large magnitude, subnormal,
   +-Inf, NaN; sampler `lodMinClamp`/`lodMaxClamp` interaction; texture mip-view (base/max level)
   interaction. `bias_sweep`, `grad_sweep`, `lodquery` backends.
4. **Cube-gradient face-boundary renders** compared against an **independently computed
   reference** (`analysis/reference.py`, derived by us from the public OpenGL cube-map-face and
   rho/lambda LOD formulas -- not copied from any implementation): face centers, all 12 edge
   midpoints, all 8 corners (major-axis ties), and a directions x gradient-magnitude matrix for
   the continuous LOD. `cube_faceid`, `cube_grad` backends.

**Readout technique ("LOD-recovery"):** an R32Float 2D/cube texture whose mip level L is filled
with the CONSTANT value `float(L)` everywhere; with `mipFilter=linear`, the hardware's own
trilinear blend across levels reads back the CONTINUOUS effective LOD it selected, exactly (not
quantized to 8-bit color). Verified end-to-end before use (PROGRESS.md).

**Six backends** (`analysis/casematrix.py` is the single source of truth for the case list and
oracle values; `run.py` executes; `verify.py` gates): `bias_sweep`, `grad_sweep`, `lodquery`,
`cube_faceid`, `cube_grad`, `regsplice_bias`.

**Needs the assembler:** partially, per the addendum's own framing -- the register-isolation
splice (`regsplice_bias`) needed raw byte-level compile+splice (via `harness/bin/shdump`, our own
build of the read-only `tools/shdump/shdump.m`); the boundary-value sweeps stayed public-Metal
behavioral (`harness/texrender`, `harness/texcompute`, both authored for this experiment).

**Target:** Apple M4 / G16G, local host only, per `CLAUDE.md`'s target discipline. A18 Pro is
hands-off; no data from it in this experiment.

**Coordinator update incorporated (2026-08-28):** `apple9_isa_explainer.md` +
`work/COMPILER-EXPLAINER-INTERACTION-20260828.md` document a CONFIRMED bug in
`tools/agx-isa/db.json`'s decoding of the falu2/falu2i (6-byte compact float), 10-byte logic, and
8-byte FMA instruction families' `srcA_reg`/`srcB_reg`/src2 fields (their top bit is a
source-retention flag, not part of the register index -- decoded register numbers >= 64 in that
family are suspect). This experiment's operand-register claim (`regsplice_bias`) does **not** go
through `db.json`'s decode at all: the isolated byte was found by raw differential byte
compilation and validated purely by splice-and-observe-downstream-consumer, with no claim about
its bit-level meaning beyond the observed causal behavior. It is a structurally different
instruction (preceding the texture sampler bundle, not a falu2/logic/FMA compact form) and is
**not assumed** unaffected by the same bug merely by analogy -- see RESULTS.md sec. "clean-room /
decoding-bug note".

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: our own MSL (kernels/*.metal), our own compiled/spliced AGX bytes (via
  harness/bin/shdump, our own build of the read-only tools/shdump/shdump.m), our own harness
  binaries (harness/texrender.m, harness/texcompute.m), public cube-map/LOD sampling math
  (analysis/reference.py, derived by us, not copied)
Apple binary introspection: NONE
Reproduction: harness/build.sh; python3 run.py --run-id <id> --execute; python3 verify.py
  --selftest / --seqtest / --preflight / --between-runs / --captured
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/ (see CAPTURE_CONTRACT.json for hashes)
```
