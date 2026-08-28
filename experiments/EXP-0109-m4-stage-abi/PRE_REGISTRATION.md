# EXP-0109 Pre-registration — M4 VS/FS/CS stage ABI (DRV-ABI-01 / P0.8)

Frozen before any official (`raw/`) GPU capture. Git revision at registration:
`75eb840a011ffbfa3fe2eb1721e2acbbcc24c1e7` (recorded for provenance only — per
`experiments/SUBAGENT_BRIEF.md`'s pinned-revision rule, the cross-run gate below
compares **authored file sha256 hashes** frozen in `CAPTURE_CONTRACT.json`, never
live repo `HEAD` — a sibling experiment landing between run01 and run02 is not a
gate failure).

Target: **Apple M4 / G16G, local host only**, macOS 26.6.2 (25G82), Metal 4 (Apple9),
`xcrun` 72, Python 3.14.6, Apple clang 21.0.0. A18 Pro is hands-off (no data collected
from it here). M5 is out of scope.

Harness code (`kernels/*.metal`, `harness/*.m`, `casematrix.py`, `run.py`, `verify.py`)
was written and manually smoke-tested against ad hoc scratch output under `work/`
(never `raw/`) before this document was frozen — this is CODEX step 3 ("build the
smallest authored probe") and step 4 ("capture the baseline before mutation"), not a
capture. No official evidence exists yet at freeze time; `raw/` is empty.

## Scope and honest boundary

DRV-ABI-01 is large (complete VS/FS/CS ABI, linking, programmable epilogs). This
experiment targets a **bounded, high-value slice**, chosen to extend what prior
experiments already established (EXP-0031 A18 SR/ABI table, EXP-0092 M4 sysval ABI,
EXP-0029 A18 fragment ISA, EXP-0097 M4 varying capacity, EXP-0091 M4 discard/sample-mask,
`docs/isa/register-move-and-liveness.md`) toward the specific fields a compiler backend
still needs and that are NOT yet M4-validated or not yet characterized at all:

1. **VS fetch ABI**: format-driven fetch-code shape for a representative format matrix
   (float/half/int/uint/normalized/packed categories), stride/offset/step/divisor
   effects, and — the item EXP-0031/EXP-0092 did not test — **out-of-range vertex/
   instance fetch** (does the generic buffer-robustness model from EXP-0076 apply to
   the VS's own generated attribute-fetch `device_load`?).
2. **FS input ABI**: M4 confirmation that the interpolation-qualifier family (EXP-0029,
   A18-only) exists on M4, pull-model presence, barycentric-coordinate availability
   (untested previously), and `primitive_id` presence.
3. **FS output ABI**: MRT count scaling, dual-source (does `index(1)` actually feed the
   blend unit — never HW-validated before, only structural), depth output (does an
   explicit `[[depth(...)]]` value actually land in the depth attachment — never
   HW-validated before), and **fragment stencil output** — not previously characterized
   at all; this experiment's own working hypothesis going in was that MSL has **no**
   fragment-stencil-output attribute (by analogy with the already-established
   cull-distance absence in EXP-0097). That hypothesis is stated below and is
   falsifiable by a clean compile.
4. **CS ABI**: whether `[[threadgroup(n)]]` dynamic shared-memory capacity
   (`setThreadgroupMemoryLength:atIndex:`) is a genuine dispatch-time parameter against
   a SINGLE compiled pipeline (never tested), and whether a preamble
   (`_agc.main.constant_program`) section is present regardless of whether the kernel
   binds a `constant`-address-space argument (extends EXP-0020, A18-only, to M4).
5. **Prolog/main/epilog linkage**: whether Metal's own compiler ever produces separate
   linked segments for attribute-fetch/blend vs. the CALL/RETURN ABI (EXP-0035,
   A18-only) reproduces on M4 for a `noinline` function call.

Not attempted here (left as open items for a follow-up experiment, stated as such in
RESULTS.md, not silently dropped): exhaustive format coverage beyond the 7-format
matrix, MSAA-dependent centroid/sample pixel-level differentiation, raster-order-group
fence re-validation, full CALL-ABI byte-level re-decode, and a from-scratch programmable-
blend-epilog synthesis (that is a downstream compiler-team deliverable, not ours per
CLAUDE.md's "specify what a future epilog generator must emit; do not implement it").

## Hypotheses and falsifiers

**H1 (VS fetch, format).** Different `MTLVertexFormat` categories (float-decoding,
half-decoding, signed/unsigned-integer, packed-normalized) bound to the SAME `[[stage_in]]`
attribute slot produce **measurably different compiled VS bytes** (different load width /
format-convert ALU), consistent with EXP-0031's A18 finding that attribute fetch is
in-shader software, not fixed-function. *Falsifier:* any two format categories that
compile to byte-identical VS code would refute "format drives generated code" for that
pair.

**H2 (VS fetch, layout).** Stride/offset/step-function/step-rate changes each move a
distinguishable, bounded region of the compiled VS bytes (the fetch address computation
and/or the vertex-vs-instance index source), analogous to EXP-0031's A18 result.
*Falsifier:* a layout change that produces byte-identical VS code.

**H3 (VS fetch, out-of-range).** An out-of-range fetch index (vertex index or
base-vertex-shifted index beyond the bound vertex buffer's element count) reads back
**zero** at the fetched attribute, per EXP-0076's general owned-buffer robustness model
(independent naturally-aligned units, OOB reads zero) applied to the VS's own
`device_load`-based fetch. *Falsifier:* an OOB fetch that reads back nonzero/garbage,
faults the command buffer, or hangs.

**H4 (FS interpolation, M4).** Each of the seven interpolation-qualifier MSL spellings
(`[[user(locn)]]`-implicit default/perspective, `center_no_perspective`,
`centroid_perspective`, `centroid_no_perspective`, `sample_perspective`,
`sample_no_perspective`, `flat`) compiles cleanly on M4 and the resulting fragment
programs are not all byte-identical (i.e., the qualifier is not silently ignored).
*Falsifier:* a compile failure, or all seven fragment programs collapsing to one byte
pattern.

**H5 (FS barycentric).** `MTLDevice.supportsShaderBarycentricCoordinates` is queryable
(public API) and, if true, a fragment function declaring `float3 b [[barycentric_coord]]`
compiles. *Falsifier:* the property reads true but the shader fails to compile, or vice
versa in a way inconsistent with the query.

**H6 (FS output, MRT).** `f_mrt1`/`f_mrt2`/`f_mrt4` each compile and, when actually
rendered with N real color attachments, each attachment's readback differs according to
its own distinct shader-computed value (not all identical, not the clear color).
*Falsifier:* any attachment reading back the clear color (unwritten) or an unrelated
attachment's value.

**H7 (FS output, dual-source).** With blend factors `sourceRGBBlendFactor =
Source1Color, destinationRGBBlendFactor = Zero`, the rendered pixel matches the
shader's `index(1)` output value, not its `index(0)` output nor the destination clear
color. *Falsifier:* the output matching `index(0)` or the clear color instead.

**H8 (FS output, depth).** An explicit `[[depth(any)]]`/`[[depth(less)]]`/
`[[depth(greater)]]` output value, deliberately different from the rasterizer-
interpolated `position.z` (which is held at a constant 0.0 in the probe geometry),
overrides what lands in a real `Depth32Float` attachment under
`MTLCompareFunctionAlways` + `depthWriteEnabled=YES`. *Falsifier:* the depth buffer
reading back the built-in 0.0 (or the clear value) instead of the requested value.

**H9 (FS output, stencil) — working hypothesis going in is a NEGATIVE.** By analogy
with EXP-0097's cull-distance finding ("MSL has no such attribute; the frontend warns
and a downstream type error follows"), the pre-registered expectation is that MSL has
**no** fragment-stencil-output attribute and a `[[stencil]]` field either fails to
compile or is silently dropped with no effect on a real stencil attachment.
*Falsifier:* `[[stencil]]` compiles AND a real stencil-attachment readback shows the
shader-supplied value rather than the fixed-function `setStencilReferenceValue:`
constant. (Note: ad hoc pre-freeze prototyping already observed a clean compile for this
attribute during harness development — see the confounder note below. The falsifier
condition is written here exactly as it would have been before that observation, and
the OFFICIAL two-run capture is what actually decides H9's status in RESULTS.md, not the
prototyping run.)

**H10 (CS, dynamic threadgroup memory).** ONE compiled pipeline
(`cs_tgmem_probe`), dispatched multiple times with different
`setThreadgroupMemoryLength:atIndex:0` + matching `threadsPerThreadgroup` pairs,
produces the numerically-correct wraparound result (`buf[(lid+1) mod N]`) at every
tested `N`, where `N` is read from the RUNTIME `threads_per_threadgroup` builtin, never
a compile-time constant. *Falsifier:* any `N` producing an incorrect wraparound value,
a fault, or a hang — this would show the compiled shader silently assumed a fixed
threadgroup-memory extent.

**H11 (CS, preamble).** A compute kernel binding a `constant`-address-space argument,
and a compute kernel with NO such argument (only a plain `device` output buffer),
**both** produce a distinct `_agc.main.constant_program` region in the compiled archive
(matching EXP-0020's A18 "thread-invariant state, including a plain buffer base
pointer, lives in the preamble" model). *Falsifier:* either kernel lacking the
`constant_program` region.

**H12 (linkage, CALL ABI on M4).** A `noinline`-attributed helper function call in a
compute kernel produces the same CALL-family opcode group (`byte0` low-nibble `0xf`)
EXP-0035 documented on A18, reproducing on M4 (extends the A18-only finding).
*Falsifier:* no such opcode group present, or a materially different encoding shape
(e.g., full inlining with no call at all).

**H13 (linkage, prolog/epilog segmentation).** Metal's own compiler, for a render
pipeline whose VS performs `[[stage_in]]` attribute fetch, does **not** produce any
additional linked code segment beyond `_agc.main` and `_agc.main.constant_program` per
stage — i.e., attribute-fetch code is inlined into `_agc.main`, not split into a
separately-addressed "prolog" object, consistent with EXP-0031's A18 finding.
*Falsifier:* a third region/symbol appearing in the vertex-stage structural report.

## Independent / controlled variables

- VS fetch: `MTLVertexFormat` (7 values), `offset`/`stride`/`stepFunction`/`stepRate`
  (paired single-variable changes), vertex-buffer element count vs. fetched index
  (in-range vs. deliberately out-of-range), `baseVertex`/`baseInstance` (zero, nonzero,
  large).
- FS input: interpolation qualifier spelling (7 values), pull-model call (4 values),
  barycentric-coordinate declaration (present/absent via device capability gate).
- FS output: attachment count (1/2/4), blend factor selecting `index(0)` vs `index(1)`,
  explicit depth/stencil value vs. the built-in/clear baseline, a genuinely-invalid
  attribute name as a compile-failure control.
- CS: `setThreadgroupMemoryLength` / `threadsPerThreadgroup` pair (1,2,4,8,16,32,64,
  same compiled pipeline), presence/absence of a bound `constant` argument.
- Held fixed per sub-probe: everything not named above (kernel source text is the
  single frozen file per family; only the CLI-driven pipeline/draw parameters vary).

## Expected observation if each hypothesis holds

Encoded directly in `casematrix.py`'s case list (deterministic parameters chosen before
any run) and in this document's falsifier text above; no oracle is computed from an
observed run and then retrofitted.

## Known confounders

- **H9 pre-freeze observation.** During harness construction (before this document was
  frozen, no `raw/` capture involved), a manual one-off compile of the `[[stencil]]`
  candidate attribute in `kernels/mrt_interp.metal` succeeded, contrary to H9's stated
  working hypothesis. This is disclosed here rather than silently rewriting H9 to match
  — the falsifier text above is left exactly as it would read before that observation.
  The OFFICIAL two-run capture (not the prototyping compile) is the evidence that
  decides H9 in `RESULTS.md`; both official runs independently re-execute the identical
  frozen case, so this is not "peeking" at held-out data, only an honest disclosure of
  development history.
- **Compiler determinism.** Metal's `newLibraryWithSource:` is assumed deterministic
  for identical source text + identical toolchain/OS revision; the cross-run gate
  itself is the test of this assumption (both runs use the same pinned host/toolchain,
  so any divergence would show up as a gate failure, not be silently accepted).
- **Rasterization-disabled vertex-only pipelines** (`vsfetch` mode,
  `rasterizationEnabled = NO`): this is a real, documented Metal capability
  (`MTLRenderPipelineDescriptor.rasterizationEnabled`), not a workaround outside the
  public API — used here purely to observe VS-only output without fragment/raster
  side effects, mirroring EXP-0092's `agxvdraw.m` atomic-append pattern.
- **Full-coverage probe geometry.** `common_vertex_data`'s triangle deliberately
  over-covers the viewport (a standard "fullscreen triangle" trick) so every sampled
  pixel is inside the primitive; this means depth/stencil "corner" samples are NOT an
  outside-primitive control — the built-in `position.z = 0.0` constant is the control
  value instead (see RESULTS.md for how this is used).
- **`vsfetch` mode's vertex-buffer fill is hard-coded to 4-byte `UChar4Normalized`
  layout** regardless of the `--format`/`--stride` CLI flags on `render_probe`'s
  `vsfetch` mode — those flags exist for future reuse but this experiment's HW-PROBE
  vsfetch cases all use format 9 (UChar4Normalized) with a matching stride of 4; the
  wider format matrix is covered by the STRUCTURAL `vfetch_extract` backend instead
  (compile-only, no execution correctness claim beyond compiled-code presence).
- **`MTLDepthStencilDescriptor`/`MTLStencilDescriptor` public-API semantics** for
  `MTLStencilOperationReplace` writing the encode-time `stencilReferenceValue` are
  themselves being used as the CONTROL for H9 (a fragment with no `[[stencil]]` output,
  `f_mrt1`, under the identical depth-stencil state) — this is a deliberate paired
  control, not an assumption asserted without a check.
- **primitive_id / centroid / sample pixel-level differentiation** is NOT independently
  HW-validated in this experiment (only structural compile presence) — MSAA or
  multi-primitive per-pixel geometry would be required and is flagged as an open item.

## Evidence-record schema (frozen)

Each case produces one JSONL record `{i, id, family, gated, meta}`. `gated` is the
byte-exact cross-run-compared payload (backend, case id, params, status, and — on
success — extracted hex / structural report / parsed JSON result). `meta` (duration,
timestamps, raw stderr tail, return code) is explicitly excluded from the cross-run
comparison and is where all timing/process-identity nondeterminism is confined. The gate
in `verify.py`/`run.py`'s `check_no_nondet()` statically rejects any of
`{duration_ms, pid, timestamp, started_utc, address, elapsed}` appearing inside `gated`.

## Environment / timeouts frozen at registration

- Per-case subprocess timeout: 30s. Per-binary build timeout: 60s.
- Toolchain: Apple clang 21.0.0 (clang-2100.1.1.101), Metal 4, macOS 26.6.2 (25G82),
  `xcrun` 72, Python 3.14.6, host Apple M4 / Mac16,10 / 10 GPU cores.
- Two required runs: `m4-20260828-run01`, `m4-20260828-run02`, each a fresh process
  invocation of `run.py` producing its own `raw/<run_id>/` tree.
