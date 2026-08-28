# PRE_REGISTRATION -- EXP-0123 M4 rasterization limits (DRV-RASTER-01, raster half)

## 0. Method note: calibration precedes the frozen contract (and why)

`APPLE9_RE_IMPLEMENTATION_GAPS.md` DRV-RASTER-01 and `CLAUDE.md`'s "Extrapolate,
then test" methodology both call for hypothesizing a plausible boundary and then
constructing it on hardware -- for a resource-limit census this requires *locating*
the real boundary before a frozen matrix can name it (a matrix that guesses
`{16, 17}` when the true crossover is `{20, 21}` never observes the interesting
case). This experiment therefore ran a first pass of ad hoc, disposable,
OWN-SHADER + HW-PROBE exploration (small standalone `.m`/`.metal` probes, never
committed as evidence, discarded after use, living only transiently under
`harness/work/gen/`) to find the exact numbers below, and only THEN froze
`harness/casematrix.py`, `harness/fixtures/recorded_reality.json`, and this
document. This ordering is disclosed, not hidden: PROGRESS.md timestamps both
phases, and every number below was re-obtained by the FROZEN, matrix-driven,
two-officially-gated-run capture that is the actual evidence of record -- the
exploration only decided *which* values were worth including in the frozen matrix,
it does not itself substitute for the gated runs.

Exploratory findings that determined the matrix (all independently re-confirmed by
the frozen, two-run gated capture in `raw/`):

| area | exploratory finding |
|---|---|
| line rule | horizontal/vertical/diagonal/shallow lines: half-open interval (endpoint excluded); row assignment matches evaluating the line at each column's pixel-center x and flooring; an EXACT integer y boundary (y=4.0) resolves to the LOWER row |
| point rounding | anchored at a true pixel center: size in [0.5, 1.9] -> 1x1; size == 2.0 exactly -> 2x2 (anomalous even footprint); size in [2.1, 3.5] -> 3x3 |
| polygon fill modes | `MTLTriangleFillMode` has exactly `.fill`/`.lines`; both are functionally distinct (72 vs 38 lit px on the fixed reference triangle) |
| wide lines (public API) | the DOCUMENTED, SDK-header-declared `MTLRenderCommandEncoder` surface has no line-width control; every line renders at the same fixed ~1px band regardless of any documented state. (A separate, NOT-clean-room-resolved observation is flagged in RESULTS.md and was excluded from this project.) |
| depth clip vs clamp | `setDepthClipMode:` is real and exact: `.clip` fully discards a primitive entirely outside [0,1] depth; `.clamp` renders it with depth clamped to exactly 0.0/1.0; AT the boundary (z==0.0 or z==1.0 exactly) both modes render (closed interval) |
| conservative raster | a sub-pixel triangle touching only a pixel's corner (not its center) is NOT rasterized under any tested configuration; no API toggle exists -- clean negative |
| coverage/early-late | `alphaToCoverageEnabled` with alpha=0 (zero derived coverage) suppresses the occlusion/visibility counter to 0, extending EXP-0091: A2C-driven coverage is not invisible to early-testing bookkeeping |
| attachments | `colorAttachments` is a fixed 8-slot array; indexing slot 8 triggers an internal Metal assertion that calls `abort()` directly (uncatchable SIGABRT), not a catchable `NSException` |
| viewports | functional up to N=16 (all N tile regions render correctly); N in [17,20] is ACCEPTED by `setViewports:count:` but the subsequent draw's command buffer comes back `CMDBUF_ERROR` "Caused GPU Hang Error" (recovered, no host wedge); N>=21 SIGSEGVs inside `setViewports:count:` itself (uncatchable, kills the process) |
| texture dims | 2D/cube max = 16384 (both axes); 3D per-axis max = 2048; 2D-array max layers = 2048; every boundary rejected via a hard `abort()` from `-[MTLTextureDescriptorInternal validateWithDevice:]` that names the exact limit in its message |
| mip levels | exactly `floor(log2(max(w,h)))+1`, confirmed at two independent scales (16384 -> 15; 64 -> 7) |
| buffer bind index | direct `[[buffer(N)]]` binding is compile-time bounded to N in [0,30] (31 slots) by the MSL frontend itself -- a clean `COMPILE_FAIL`, not a runtime fault |
| texture bind index | direct `[[texture(N)]]` binding is compile-time bounded to N in [0,127] (128 slots), same clean `COMPILE_FAIL` mechanism |
| inline constants (`setFragmentBytes:`) | functionally correct (first AND last byte of the blob both round-trip exactly) up to and including length 32752 bytes; length 32753 aborts (SIGABRT) -- NOT the commonly cited 4096-byte figure |
| buffer offset alignment | arbitrary byte offsets (tested 0..64, including 1,2,3,15,17 -- none 4-or-16-aligned) all bind and read back functionally correct; no alignment requirement observed |
| threadgroup size | `maxTotalThreadsPerThreadgroup` self-reports 1024 on this device; a dispatch requesting more is SILENTLY a no-op (status OK, no error anywhere, output buffer untouched) via both `dispatchThreadgroups:` and `dispatchThreads:` |
| dynamic threadgroup memory | `setThreadgroupMemoryLength:` accepts up to at least 131072 bytes with no visible error in this single-write functional probe (deeper corruption behavior at these sizes for STATIC declarations is already characterized by EXP-0100 and is not re-derived here) |
| SIMD width | `thread_execution_width` = 32, confirmed functionally via per-lane readback at two threadgroup sizes |
| `simd_shuffle` OOB source lane | reproducible but NOT simple `% 32` wrapping for every tested value (33 and 63 diverge from the modulo prediction); exact hardware mapping formula not fully resolved -- recorded as a partial/open item, not oversold |

## 1. Question

Cover the rasterization and hard-limits half of DRV-RASTER-01 (P1.8): line/point
rasterization rules, polygon modes, depth clip vs. clamp, conservative
rasterization, coverage/early-late depth-stencil interaction beyond EXP-0091, and
every advertised finite limit the row enumerates (viewports, attachments,
dimensions, layers, mips, workgroups, shared/tile memory, descriptors, uniforms,
alignments, subgroup operations) -- each constructed and boundary-tested on
hardware, not quoted from a feature table.

## 2. Hypothesis (falsifiable, frozen before the two official runs)

For every case in the frozen `harness/casematrix.py` matrix, the recorded
`status`/`verdict`/`observed` fields will exactly reproduce the exploratory finding
in the table above, and will be byte-identical across two independent captures
(`raw/*_run01`, `raw/*_run02`) for every field except the explicitly nondeterministic
`gputime_ns` (which lives only in the separate, non-gated stream).

**Falsifier:** any case whose `verdict` is `FAIL`/`TIMEOUT` in either official run,
or whose gated fields differ between run01 and run02, refutes the corresponding row
of the table and must be reported as such in RESULTS.md, not silently dropped.

## 3. Independent / controlled variables

- Independent: one parameter per case (line endpoints, point size, fill mode, depth
  clip mode + z, triangle corner offset, alphaToCoverage + alpha + sample count,
  attachment/viewport/texture-dimension/mip/buffer-index/texture-index/inline-byte-
  length/buffer-offset/threadgroup-size/threadgroup-memory-length/SIMD source-lane
  value).
- Controlled: target format (`RGBA32Float` color, `Depth32Float` depth -- exact,
  unquantized readback), Metal compile options (`fastMathEnabled` default,
  `MTLCompileOptions` with no extra flags), device (`MTLCreateSystemDefaultDevice()`,
  the sole local M4), one case = one fresh subprocess.

## 4. Known confounders

- GPU-hang recovery (`CMDBUF_ERROR`) and hard `abort()`/`SIGSEGV` both terminate a
  case's process abnormally; a case that legitimately CRASHES is distinguished from
  a harness bug by `_expect_crash_or_hard_fault()` in `run.py`, itself derived from
  the exploratory table above -- a mismatch is a `FAIL`, not silently reclassified.
- MSAA resolve + `alphaToCoverageEnabled` + a full-coverage alpha + a depth
  attachment + a visibility (occlusion) buffer, read back via the unguarded
  `--readback point` path, showed ONE non-reproducible crash during ad hoc
  exploration (3/3 later re-runs of the identical case succeeded). This exact
  parameter combination is deliberately EXCLUDED from the frozen matrix (the
  `coverage_earlylate` family only uses `sample_count=4` for the already-stable
  `alphaToCoverage=true, alpha=0` case; every `alpha=1` case uses `sample_count=1`)
  to keep the frozen matrix byte-reproducible across the two official runs. This
  single non-reproducible event is reported in RESULTS.md as a named, out-of-gate
  observation, not silently discarded.
- Apple's internal Metal validation frequently traps via `abort()`/`SIGSEGV` rather
  than a catchable `NSException` for out-of-range descriptor values; every
  crash-classification in `run.py` reflects an EXPLICIT prior observation, not a
  blanket "any crash is a pass."

## 5. Target / environment (frozen)

- Target: Apple M4 (G16G), local host only. macOS 26.6.2 (25G82). 16 GB unified
  memory. Apple clang 21.0.0 (clang-2100.1.1.101). SDK: MacOSX26.5.sdk.
  A18 Pro is HANDS-OFF; nothing here touches it. No A18/G17P claim is made anywhere
  in this experiment; every fact is M4/G16G only per CLAUDE.md target discipline.
- Repository revision pinned at contract freeze:
  `6a8d588678a94eedafa215f9ac57bceb7fd4e36e` (working tree otherwise dirty with
  sibling in-flight experiments per repo convention; this experiment's own files are
  new/untracked at freeze time, which is expected for a not-yet-committed
  experiment). Per CODEX.md, the two official captures are validated against the
  AUTHORED BLOB HASHES below, not against live `HEAD` (which the orchestrator may
  advance by landing sibling experiments during this run).

## 6. Frozen source hashes (`shasum -a 256`)

```
c0886473d32618c2d2dbb613a7acda1152f059d8189880b4b13b17ce0779ffcb  harness/casematrix.py
09cd53a8421699184bd87b09a70ea6670c484886aece1470a8a0abbc7328e9c0  harness/genkernels.py
4590110c6f858ff305e94f87cf84a31397015cf42a43ad595ef4bd3045b16728  harness/rasterprobe.m
4d2c849688ab642e4981f4b50085a6b11929aed053b720c91451a43e2df057ce  harness/computeprobe.m
a4bf859892fc6ba07283d49338db3be08ccc4d1c6dd2c629aea3243cb3d255c5  harness/run.py
68c97215883b8665cae0437d7d649c9ac7ebc71eb09e864252a5d6c2c9e23af0  harness/schema.py
9c14aa2063f1327274c442678e0152c583a020691682bec5449b2d1f12151824  harness/verify.py
7bfa5ab7ebbdba2070cef4cecb0c40c6bd60540068e6cb0202e5a9278e5c4000  harness/fixtures/recorded_reality.json
```

## 7. Raw-record schema (frozen)

`GATED_KEYS = {case_id, family, kind, params, status, verdict, observed}` (written
to `02_gated.jsonl`, cross-run byte-compared field by field, `gputime_ns` explicitly
excluded from `observed`). `NONGATED_KEYS = {case_id, gputime_ns, wall_ms, pid,
raw_tail}` (written to `03_nongated.jsonl`, never gated). `case_id` is the
intentional join key present in both. See `harness/schema.py`.

## 8. Timeouts

25.0 s hard subprocess timeout per case (`HARD_TIMEOUT_S` in `run.py`); a timeout
is recorded as `verdict=TIMEOUT`, never silently retried or dropped. Observed wall
time for every one of 98 cases in both official runs was well under 200 ms; the
25 s budget is pure headroom against an undetected hang.

## 9. Clean-room provenance

Clean-room provenance: OWN-SHADER + HW-PROBE.
Inputs inspected: MSL sources generated deterministically by `harness/genkernels.py`
from `harness/casematrix.py`; the public Metal runtime API
(`newLibraryWithSource:`, `newRenderPipelineStateWithDescriptor:`,
`newComputePipelineStateWithFunction:`, `MTLTexture`/`MTLBuffer` readback,
`NSError`/exception text) as exposed by the current public Metal SDK headers.
Apple binary introspection: NONE. No Ghidra/otool/objdump/lldb/class-dump/radare2
was used on any Apple binary, framework, or kext anywhere in this experiment.
Reproduction: `python3 harness/run.py --run <id> --out raw/<id>` (x2), then
`python3 harness/verify.py --captured <run_a> <run_b>`.
