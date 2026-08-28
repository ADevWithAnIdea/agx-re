# PROGRESS — EXP-0117

## Milestone: scope + PRE_REGISTRATION frozen
Read EXP-0109 RESULTS.md's nine-item "still needs" list, EXP-0111 RESULTS.md,
EXP-0097/EXP-0091/EXP-0092 for prior art. Read `docs/isa/encoding-tables.md`'s
`tile_read`/`frag_color_store`/CALL-family entries and EXP-0029/EXP-0035's raw
byte captures for the CALL-ABI discrepancy context. Read the PUBLIC Metal SDK
headers (`MTLRenderPipeline.h`, `MTLPixelFormat.h`, `MTL4PipelineState.h`) for
exact enum values — found the brand-new (macOS 26.0) `Unspecialized` sentinel
family (`MTLBlendFactorUnspecialized=19`, `MTLBlendOperationUnspecialized=5`,
`MTLColorWriteMaskUnspecialized=0x10`, `MTL4BlendStateUnspecialized=2`),
directly relevant to DRV-ABI-01's "what must an epilog generator emit"
question — added as boundary/hole cases to the blend matrix.

Received a coordinator scope-reinforcement message mid-task: construct every
finite field's minimum/maximum/first-invalid/holes, not just observe compiler
output. Revised PRE_REGISTRATION.md's item-1 sub-plan and finite-resource
mandate section accordingly before writing any harness code that mattered.

## Milestone: pilot / harness smoke testing (work/, never raw/)

All of the following ran against `work/bin/dev/*` binaries and scratch output
under `work/`, never `raw/`, before `PRE_REGISTRATION.md`/`CAPTURE_CONTRACT.json`
were frozen.

**Bugs found and fixed during pilot (disclosed, not silently corrected):**
- `fsorder.metal`'s left/right split originally used a hardcoded
  `pos.x < 128.0` window-space threshold, silently wrong for any target
  width other than 256 — fixed to a harness-supplied `params.z` threshold
  (`W/2`), verified against W=8.
- `[[instance_id]]` is a VERTEX-stage-only MSL builtin — a fragment function
  declaring it as an input attribute is REJECTED at compile time (own-
  compiler diagnostic: "invalid 'instance_id' attribute for input
  declaration in a fragment function"). Fixed by relaying it through an
  ordinary `[[flat]]` varying from vertex to fragment.
- `int s [[stencil]]` is REJECTED at compile time ("type 'int' is not valid
  for attribute 'stencil'") — since MSL compiles one source file as one
  translation unit, this failing declaration was moved to its own file
  (`kernels/stencil_i32_negative.metal`) so it does not poison the working
  `uint`/`ushort` forms in `kernels/stencil.metal`.
- `Source1Color`/`OneMinusSource1Color`/`Source1Alpha`/`OneMinusSource1Alpha`
  as a blend factor require the fragment function to declare an `index(1)`
  output ("Fragment shader does not write to render target color(0),
  index(1) that is required for blending") — added `f_solid_dualsrc` and
  `--src1r/g/b/a` CLI plumbing.
- `run.py`'s `NONDET_FORBIDDEN` set includes `"pid"` (intended to catch
  accidental OS process-id leakage into a gated record) — this collided with
  a legitimate semantic field named `"pid"` for `primitive_id` in the
  bary/pid family's readback records. Renamed the JSON field to `"primid"`.

**Genuine hardware/API findings discovered during pilot (verified, then
folded into the frozen matrix as real cases, not just pilot trivia):**
- Enabling `blendingEnabled=YES` while selecting an out-of-documented-range
  `MTLBlendFactor`/`MTLBlendOperation` value, or enabling blending on a
  non-blendable (integer) pixel format, or indexing
  `colorAttachments[8]` (the 9th slot, 0-based, past the documented 8-slot
  array) — ALL raise a FATAL Metal API validation assertion that SIGABRTs
  the whole process, not a catchable `NSError`. Reproduced deterministically
  (identical assertion text) on repeat. `run.py` treats a negative
  subprocess return code as a legitimate `PROCESS_ABORT` status.
- ONE observed transient `kIOGPUCommandBufferCallbackErrorInnocentVictim`
  GPU error on a case run immediately after one of the above aborts, NOT
  reproduced on 3/3 immediate retries in isolation — mitigated by moving
  every confirmed-abort-inducing case to the END of `casematrix.py`'s case
  list (see its module docstring), so no other case can ever be collateral.
- `MTLBlendFactorUnspecialized`(19) and `MTLBlendOperationUnspecialized`(5)
  and `MTLColorWriteMaskUnspecialized`(0x10) all behave EXACTLY per their
  public-header doc comments on the CLASSIC (non-MTL4) pipeline API,
  confirmed by construction: factor-19-as-source behaves as One,
  factor-19-as-destination behaves as Zero, op-5 behaves as Add, mask-0x10
  behaves as All. An out-of-range write-mask bit (0x20) is silently inert
  (no crash) — unlike the STRICTLY-validated factor/op enums.
- `[[stencil]]` overflow: values beyond 255 TRUNCATE to their low 8 bits
  (`value & 0xFF`), not clamp — confirmed for both `uint` (256→0, 257→1,
  511→255, 65535→255, 4294967295→255) and `ushort` (300→44) source types.
- Structural: `blendingEnabled=YES` with factors that reduce to a
  compile-time-constant identity (src=One,dst=Zero) compiles BYTE-IDENTICAL
  to `blendingEnabled=NO` (56 bytes both); src=Zero,dst=One (pure
  dst-passthrough) compiles to a much SHORTER 16-byte stub with NO
  `tile_read`, suggesting the whole color computation/store is
  algebraically eliminated at pipeline-creation time; src=SourceColor,
  dst=DestinationColor (genuinely data-dependent) is 84 bytes and DOES
  contain `tile_read` (`0x67 0x0e`). See RESULTS.md §1 for the full
  analysis.
- CALL-ABI: `k_single` (ONE call site, no nesting) already shows
  `byte+6==0x54` on this M4/toolchain — directly refuting a naive
  "call-site count determines byte+6" reading of EXP-0035's A18 data.
  `k_nested`'s helper region (`l__ZL6mid_fnf`) reproduces EXP-0035's "mid"
  shape byte-for-byte, including the `byte+5` 0x10-then-0x00 pattern across
  its two nested calls. Full analysis in RESULTS.md §7.
- Call-nesting depth 1..128 (14 constructed depths) ALL execute correctly
  against the exact host oracle (`out[gid]==gid+depth`) with zero faults,
  zero timeouts, zero wrong values — no depth limit found in the tested
  range.
- `primitive_id`: an indexed draw with a deliberately shuffled index buffer
  shows `primitive_id` tracks ASSEMBLY order, not raw vertex-index values
  (a triangle submitted first via indices {9,10,11} gets `pid=0`). An
  instanced draw (2 instances, geometrically disjoint via a per-instance Y
  offset added to `v_pidquad`) shows `primitive_id` RESETS to 0 for each
  instance rather than accumulating globally.
- MSAA centroid-vs-sample: within ONE partially-covered pixel (N=4, 2 of 4
  samples covered, EXP-0111's proven geometry), the two live per-sample
  invocations (sid=0, sid=2) report IDENTICAL `centroid` values
  (-0.24705887 both) but DIFFERENT `sample` values (-0.24705887 vs
  -0.74901962) — direct, decisive differentiation.

Full dry run (148 cases) completed in ~8s with zero unexpected failures (the
only two non-OK outcomes were the DESIGNED negative controls: the `int`
stencil-type rejection and, once the case matrix was finalized, the five
designed fatal-abort cases at the end of the list).

## Milestone: post-capture analysis + one supplementary ad hoc probe

`analysis/decode.py` run against `raw/m4-20260828-run01`: 23/23 blend-factor
matches (all 19 factors + 4 dst-role spot checks, including the dual-source
family and `SourceAlphaSaturated`'s RGB-vs-alpha formula split), 5/5 blend
ops, 12/12 stencil-overflow (truncate model), 14/14 sample-mask, 8/8 logic
epilog, 14/14 call-depth, CALL-ABI `byte+6` uniformly `0x54` across all six
topologies, MSAA centroid-uniform/sample-distinct confirmed, `blendstruct`
off==srconly confirmed, FS-order struct-byte-identical + render-identical +
op-selection-tracks-assignment all confirmed. One family did NOT resolve
cleanly: barycentric `sum(b)==1` held, but neither the linear (screen-space)
nor the perspective-corrected candidate model matched the observed raw `b`.

**Supplementary, single-run, non-frozen ad hoc probes** (mirroring
EXP-0109 §3.2's `render_probe_src0test.m` precedent for a post-hoc
gap-closing single probe, explicitly outside the two-run gate,
`work/supplementary/bary_diag*.{metal,m}`): root-caused the mismatch by
incrementally reproducing the official `bary` case's exact kernel/pipeline
shape. Result: a fragment function textually IDENTICAL to the official
`f_bary` (same tags parameter, same two `[[color(0)]]`/`[[color(1)]]`
outputs, no `f_pid`/`v_pidquad` in the file) reproduces the official
`b=(0.24348931,0.13476601,0.62174469)` EXACTLY (`bary_diag4`). Adding a
THIRD output that simply echoes the built-in `float4 pos [[position]]`
value back out to a color attachment (`bary_diag2`/`bary_diag`, otherwise
identical) changes the compiled `barycentric_coord` READBACK to
`b=(0.48697862,0.26953202,0.24348938)` -- which DOES match this
experiment's own host-computed perspective-corrected model
(`[0.48697917,0.26953125,0.24348958]`) to 4 decimal places. Presence/
absence of the unrelated `f_pid`/`v_pidquad` functions in the same source
file was tested and ruled out as the cause (`bary_diag3`, full file, no
pos echo, reproduces the official non-matching value). **This is reported
as a genuine, reproduced-4x anomaly, NOT resolved here**: adding an
unrelated fragment OUTPUT changes the compiled interpretation/value of
`barycentric_coord` in this specific probe shape, on this exact toolchain.
Flagged for a dedicated follow-up (structural byte-diff of the two fragment
variants' compiled code would be the natural next step). The OFFICIAL,
two-run-gated capture is authoritative for this experiment's own verdict
(§4 of RESULTS.md); the diagnostic files are NOT part of the frozen
evidence and are kept in `work/` only, per the ad hoc supplementary-probe
convention.

## Milestone: CAPTURE_CONTRACT.json frozen, official captures

`CAPTURE_CONTRACT.json` written at state `PRE_GPU`, authored-file sha256 set
pinned. Proceeding to `raw/m4-20260828-run01` and `raw/m4-20260828-run02`.
