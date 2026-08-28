# PRE_REGISTRATION — EXP-0135 M4 mesh/object shading (DRV-P2-03)

Frozen alongside `CAPTURE_CONTRACT.json` (`frozen_at_utc` there is authoritative).
Pinned revision: `cf544b4dd1fb37047c7cfee6a70a0d1a87628666`. Target: local Apple M4
(G16G) only; A18 Pro hands-off; M5 out of scope.

## 0. Build-time calibration (pre-freeze; NOT gated evidence)

Per CODEX §3 ("build the smallest authored probe" / "capture the baseline before
mutation"), the harness (`harness/mesh_probe.m`, the four dispatch modes, the
kernel templates) was built and manually exercised against single points BEFORE
the case matrix was frozen, exactly as prior experiments' "build-time findings"
sections do. This section records what that calibration found, because it
directly determined the checkpoint ladders in `analysis/gen_matrix.py` — an
underspecified frozen contract is an automatic stop, so the ladders needed to
already bracket real boundaries, not guessed ones.

1. **Metal's own compiler/pipeline-creation error text gives exact numeric
   ceilings**, discovered by direct trial: `metal::mesh<V,P,NV,NP,triangle>`
   rejects at MSL-compile time with `number of vertices (N) exceeds maximum
   supported (256)` and `number of primitives (N) exceeds maximum supported
   (512)`; `payloadMemoryLength`/struct size rejects at
   **pipeline-creation** time (not compile time) with `Object shader payload
   size (N) exceeds the maximum payload size allowed (16384)`. Verified exact
   boundaries by direct trial: NV 256 works / 257 COMPILE_FAIL; NP 512 works /
   513 COMPILE_FAIL; payload 16384 works / 16385 PIPELINE_FAIL.
2. **`payloadMemoryLength` override accepts values SMALLER than the object
   shader's declared payload struct** (tried 128 against a 256-byte struct) —
   pipeline creation succeeds, no validation error, and the case still renders.
   Only the upper bound (16384) is enforced; there is no minimum-adequacy
   check. This is a genuine (negative) API-surface finding, not a harness bug.
3. **`mesh_grid_properties::set_threadgroups_per_grid`'s reflected ceiling
   (`maxTotalThreadgroupsPerMeshGrid`, unset attribute/descriptor -> "device
   maximum") is 1,048,576, but the REAL failure boundary is far lower and
   silent.** A manual bisection (values 1..16,777,216) found: coverage grows
   and saturates by AMP_COUNT=64 (all 64 offset cells full), stays saturated
   through AMP_COUNT=65,535, and **drops to COVERED=0 (accepted, `STATUS OK`,
   no error, no fault) starting at exactly AMP_COUNT=65,536** and remains 0 at
   every larger value tried up to 16,777,216 — including values that are NOT
   multiples of 65,536 (ruling out a mod-65536 wraparound reinterpretation;
   this is a hard cutoff, not wraparound). The SAME exact 65,536 boundary,
   with the SAME silent-zero (not fault) failure signature, was independently
   found on the **unrelated top-level indirect-draw mesh-grid mechanism**
   (`-drawMeshThreadgroupsWithIndirectBuffer:`, object-less pipeline) up to
   16,777,216 with no hang. This cross-mechanism agreement is why AMP_COUNT is
   promoted to a full ladder rather than left as an aside.
4. **`newIndirectCommandBuffer` `maxCommandCount` for a mesh-draw-typed ICB
   has a MUCH lower failure ceiling than EXP-0124 found for an ordinary
   (draw/dispatch) ICB.** EXP-0124 found ordinary ICBs allocate fine up to
   4,194,304 and crash (`SIGSEGV` inside `newIndirectCommandBufferWithDescriptor:`)
   only above an exact bisected boundary of 6,391,319/6,391,320. For a
   `MTLIndirectCommandTypeDrawMeshThreadgroups`-typed ICB, calibration found:
   1,024 and 65,536 both allocate+execute fine; **1,048,576 allocates but the
   render command buffer itself fails (`CMDBUF_ERROR`, contained)**; and
   **4,194,304 and above (including 6,391,319/6,391,320, which work for an
   ordinary ICB) SIGSEGV at allocation time**, contained to that one process
   each time, with a clean post-fault sanity re-check every time. The exact
   lower/upper transition points were not yet bracketed at freeze time, so the
   frozen `maxCommandCount` ladder (`CAPTURE_CONTRACT.json`) adds intermediate
   checkpoints (131072/262144/524288 between the OK/CMDBUF_ERROR transition;
   2097152/3145728 between the CMDBUF_ERROR/crash transition) versus the
   narrower ladder this calibration first tried.
5. **A single full non-recorded dry run of the entire frozen matrix**
   (`work/smoke/smoke01/`, the CODEX/dispatch-mandated NON-RECORDED smoke gate)
   completed cleanly: 102 records, statuses `{OK:83, PIPELINE_FAIL:6,
   COMPILE_FAIL:6, CRASH_SIG11:4, CMDBUF_ERROR:3}`, zero TIMEOUTs, zero host
   instability, and every post-fault sanity check (4/4, one per `CRASH_SIG11`
   case) returned `OK`. This run is **not** promoted as evidence (per the
   standing NON-RECORDED-smoke-before-raw/ gate); its only role is validating
   the harness/matrix/timeouts before either official capture.
6. **Non-4-byte-aligned `indirectBufferOffset`** (tested at offset 2) is
   accepted without rejection or fault for the mesh indirect-draw path,
   matching EXP-0098/0124's finding for ordinary compute-indirect-dispatch.
   An out-of-bounds call offset (4096 into a 16-byte allocation) reads as an
   effective zero grid (`COVERED=0`, no fault) rather than crashing — an
   asymmetry against the ICB range-past-max case (which DOES fault), recorded
   as a genuine (not yet root-caused) negative finding, not resolved further
   by this experiment.
7. **`__HAVE_RENDER_COMMAND_MESH__`-gated GPU-authored ICB mesh encoding
   compiles and runs on M4.** The public MSL toolchain header
   (`metal_command_buffer`, distributed with the Metal developer toolchain —
   inspected as a public shading-language interface definition, not Apple
   binary introspection) declares `render_command::draw_mesh_threadgroups()`/
   `draw_mesh_threads()` behind that macro; whether the macro is actually
   defined for this target was unknown until tried. It compiled, encoded, and
   rendered identically (same `COVERED` count) to the CPU-authored
   `id<MTLIndirectRenderCommand>` equivalent.

None of the above are promoted facts yet — they are the basis for the frozen
ladders below and will be re-established as gated, byte-exact-reproduced
evidence in `raw/m4_20260828_run01/` and `raw/m4_20260828_run02/`.

## 1. Questions and falsifiable hypotheses

**H-R (re-validation).** *H0:* the A18 EXP-0030 findings (native pipeline;
`0x43` marker present at object/mesh call sites; graphics-path submission with
IOKit call count approx.= an ordinary draw, greater than compute; emit via
ordinary `0xe7`/`0xd7` stores) hold unchanged on M4. *Falsifier:* any of —
mesh pipeline creation fails outright on M4; the `0x43`/`43 00 00 01` byte
sequence is absent from the object/mesh `_agc.main` streams; mesh IOKit call
count is not within a small margin of the ordinary-draw count, or is close to
the compute count instead; the emit region uses an opcode byte0 absent from
the hand-written compute control.

**H-B (object-to-mesh payload).** *H0:* the payload size ceiling is a single
fixed number enforced at pipeline-creation time (not MSL-compile time), and
`payloadMemoryLength` accepts an explicit override that is NOT validated
against the struct's natural size on the low end. *Falsifier:* the ceiling
value differs between direct-struct-size and explicit-override paths; an
override smaller than the natural struct size is rejected; the enforcement
point is compile-time rather than pipeline-creation-time.

**H-C (UVB output sizing).** *H0:* NV (max_vertices) and NP (max_primitives)
each have a single fixed ceiling, enforced at MSL-compile time with an exact,
compiler-reported number, and the two ceilings differ from each other.
*Falsifier:* either ceiling is enforced at pipeline-creation or dispatch time
instead of compile time; the ceilings match Metal's advertised device-limit
tables exactly (would mean no independent probing was needed) or don't
reproduce across both runs.

**H-D (allocation ownership / raster linkage).** *H0:* (i) grid amplification
via `mesh_grid_properties::set_threadgroups_per_grid` has a real ceiling far
below its reflected `maxTotalThreadgroupsPerMeshGrid`, whose overflow fails
**silently** (no error, `STATUS OK`, zero coverage) rather than via a
compile/pipeline/command-buffer error; (ii) the sel-9-registered BO inventory
(size multiset) is **invariant** across payload/NV/NP/AMP_COUNT checkpoints —
i.e. the UVB/payload/output buffers are not userspace-visible-and-scaling,
matching EXP-0030's "firmware-managed" claim and EXP-0120's TVB methodology.
*Falsifier for (i):* the ceiling matches the reflected value, or overflow
faults/errors instead of silently zeroing. *Falsifier for (ii):* the BO size
multiset differs between the small/near-max/high-amp checkpoints (would mean
a driver-visible buffer scales with these fields, contradicting
"firmware-managed").

**H-I (indirect/ICB).** *H0:* (i) the mesh indirect-draw grid buffer reuses
the exact same 3xuint32 `MTLDispatchThreadgroupsIndirectArguments` grammar
compute indirect-dispatch uses (EXP-0098/0124), including tolerance for a
non-4-byte-aligned offset; (ii) CPU-authored ICB mesh commands and
GPU-authored (`render_command::draw_mesh_threadgroups`) ICB mesh commands both
work and produce identical rendered output for the same case; (iii) ICB
execution-range boundary behavior (`location==maxCommandCount` -> 0 executed,
no fault; `location>maxCommandCount` -> `CMDBUF_ERROR`; oversized `length` ->
silently clamped) matches EXP-0098's ordinary-ICB finding; (iv) the
`maxCommandCount` allocation/crash ceiling for a mesh-typed ICB is materially
**lower** than EXP-0124's ordinary-ICB ceiling (6,391,319/6,391,320).
*Falsifier:* GPU-authored mesh ICB encoding fails to compile (would mean
`__HAVE_RENDER_COMMAND_MESH__` is not actually enabled for this target,
contradicting the build-time-calibration trial); the range boundary behavior
differs from EXP-0098's; the mesh ICB ceiling matches or exceeds the ordinary
ICB's 6,391,319/6,391,320 boundary.

## 2. Independent / controlled variables

One macro or one CLI parameter changes per case (see `analysis/gen_matrix.py`
docstring and per-case `params`); render target size, thread-group
configuration, and topology are held fixed within each ladder. Every case is
a fresh OS process (no persistent runner, no state carried between cases).

## 3. Evidence labels anticipated

- Render/pipeline/compile outcomes: **HW-PROBE** (public Metal API, our own
  MSL, live M4 execution) or **OWN-SHADER** where AGX bytes are inspected.
- IOKit call histograms / BO size multisets: **DATA-TRACE** (our own process's
  IOKit traffic via the `tools/iotrace` interposer, unmodified).
- `_agc.main` byte extraction/opcode census: **OWN-SHADER** (our own compiled
  bytes via `shdump_mesh`/`agxparse.py`, unmodified parser, no Apple binary
  introspected).

## 4. Known confounders

- Metal's compiler/runtime may itself impose a device-independent SDK-level
  ceiling distinct from the silicon's real capacity (a software safety net,
  not a hardware fact) — flagged explicitly wherever the failure is a clean
  API-level rejection rather than a hardware fault, and not asserted as an
  ISA-level hardware limit.
  Any silent-zero-output result cannot, from userspace alone, be
  distinguished between "hardware truncates/ignores the excess" and "the
  Metal runtime silently clamps before reaching the hardware" — flagged as
  such, not resolved (would require an OWN-SHADER/ISA-level splice test, out
  of scope here).
- `set_index()`'s `uchar` parameter type truncates any index value above 255
  mod 256 in the NP (primitives) sweep and the AMP_COUNT (amplification)
  offset-color formula; both are harness design choices, documented in the
  kernel source comments, not hardware findings.
- iotrace's BO inventory reflects only calls THIS process makes; it cannot
  see firmware-internal allocation that never crosses the IOKit boundary
  (same limitation EXP-0120 §5 documents for the TVB).

## 5. Raw-record schema (frozen)

Every `raw/<run_id>/records.jsonl` line is one JSON object with at least
`case_id`, `group`, `role`, `params`, `status`. `mesh_probe`-backed cases add
`argv`, `returncode`, `timed_out`, `elapsed_s`, `stdout`, `stderr`. Group R
static-extraction and Group R/D iotrace cases add their own fact/trace fields
(see `analysis/run.py`). `elapsed_s` and any GPU virtual address appearing
inside `stdout` are recorded but **excluded from the byte-exact gate**
(non-deterministic / non-load-bearing); the gate compares `status` plus the
parsed structural fields only (see `CAPTURE_CONTRACT.json` "gate").

## 6. Two-run + gate plan

`raw/m4_20260828_run01/` and `raw/m4_20260828_run02/`, each a fresh
`analysis/run.py --run-id ...` invocation (fresh processes throughout, no
state reuse), executed after this freeze. `analysis/verify.py --selftest`,
`--seqtest --run01 ... --run02 ...`, and `--captured --run01 ... --run02 ...`
must all PASS before any fact is promoted to `RESULTS.md`.
