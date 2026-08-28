# RESULTS — EXP-0135 M4 native mesh/object shading (DRV-P2-03)

**Target: local Apple M4 (G16G) only**, macOS 26.6.2 (25G82), Metal 4, 10 GPU
cores. No A18 Pro claim anywhere in this document except where explicitly
labeled "A18 (EXP-0030)" for comparison — A18 Pro is hands-off per CLAUDE.md.
No M5 evidence. **Two official capture runs**
(`raw/m4_20260828_run01/`, `raw/m4_20260828_run02/`), **107 records each**,
pinned revision `cf544b4dd1fb37047c7cfee6a70a0d1a87628666`.

**Gate results:** `analysis/verify.py --selftest` PASS (5/5 checks).
`--seqtest --run01 m4_20260828_run01 --run02 m4_20260828_run02` PASS
(PRE_GPU/RUN01_PRESENT/RUN02_PRESENT). `--captured` PASS, **107/107 case
records byte-exact reproduced** on the gated fields (`status` +
`n_bo`/`sel9_calls`/`size_multiset` + the R-bytes-* extraction facts).
One incidental, disclosed non-determinism was found and excluded from the
gate — see §7. **Zero TIMEOUT, zero host wedge**, in either official run or
the pre-freeze smoke run (`work/smoke/smoke01/`, non-recorded). Every
anomalous case (4x `CRASH_SIG11` per run, all in the `I-cpu-maxcount` ladder)
was followed by an automatic post-fault sanity re-check that returned `OK`
every single time (8/8 across both runs).

---

## Headline

**Mesh shading is STILL a native hardware pipeline on M4, and every A18
(EXP-0030) structural claim this experiment could re-test reproduced exactly**
— same helper-subroutine byte lengths (128B `write_childcount`, 576B
`write_uvb`), the same `43 00 00 01` marker at the same call sites, the same
IOKit-call-count signature (mesh approx.= draw, both > compute). **No
A18-vs-M4 divergence was found for the re-validated claims** (contrast
EXP-0119 §3.2's disclosed, unresolved A18-vs-M4 `ibitcount` discrepancy — this
experiment found none). One interpretive **correction, not contradiction**: the
`0x43` marker is not object/mesh-exclusive (EXP-0030's necessarily narrower
framing, since it tested only mesh/object stages); `tools/agx-isa`'s DB
(EXP-M4-13, M4 corpus work postdating EXP-0030) already generalizes it to a
"pre-call frame-setup marker" that appears before every out-of-line CALL in
any stage — object/mesh happen to hit it because their compiler-generated
helper subroutines are call sites.

**Object-to-mesh payload:** exact ceiling **16,384 bytes**, enforced at
**pipeline-creation time** (not MSL-compile time), with an exact,
compiler-generated failure message (`"Object shader payload size (16385)
exceeds the maximum payload size allowed (16384)"`). The explicit
`payloadMemoryLength` override accepts values SMALLER than the declared
struct with no validation — a real, disclosed gap in the API's safety net.

**UVB output sizing:** exact ceilings **256 vertices** and **512 primitives**
per meshlet, BOTH enforced at **MSL-compile time** with exact,
compiler-generated messages, and **not equal to each other** (256 != 512) —
these are two independently-capped fields, not one shared limit.

**Allocation ownership:** **CONFIRMED firmware-managed**, by the EXP-0120
TVB methodology directly: the sel-9-registered BO size multiset (37 BOs) is
**byte-identical** across a small/near-max/high-amplification checkpoint
sweep of payload size, vertex count, primitive count, and grid-amplification
count. No userspace-visible buffer scales with any of the four independent
variables this experiment swept.

**Raster linkage:** grid amplification (`mesh_grid_properties::set_
threadgroups_per_grid`) genuinely drives the rasterizer — coverage grows
monotonically with amplification count and every amplified threadgroup's
independently-offset geometry appears in the final image — but the REAL
ceiling is **65,536 threadgroups**, silently (`STATUS OK`, zero error) far
below the API's own reflected ceiling of 1,048,576. The exact same 65,536
silent-zero boundary was independently found on the unrelated top-level
indirect-draw mesh-grid mechanism.

**Indirect/ICB:** the indirect-draw grid buffer reuses the exact
`MTLDispatchThreadgroupsIndirectArguments` grammar EXP-0098/0124 characterized
for compute; BOTH CPU-authored and **GPU-authored** (`render_command::
draw_mesh_threadgroups`, a genuinely new confirmed capability) ICB mesh
commands work and render identically; the ICB execution-range boundary
behavior matches EXP-0098's ordinary-ICB finding exactly EXCEPT the
range-past-max failure mode is a GPU **Hang** error here, not the **Page
Fault** EXP-0098 found for an ordinary ICB — a real, disclosed divergence.
The `maxCommandCount` failure ceiling for a mesh-typed ICB is dramatically
LOWER and has a THIRD failure region EXP-0124's ordinary-ICB sweep never saw:
OK up to 524,288; a contained `CMDBUF_ERROR` region from 1,048,576 to
3,145,728; `SIGSEGV` at allocation time from 4,194,304 up (including
6,391,319/6,391,320, which is the exact value EXP-0124 found still WORKS for
an ordinary ICB).

---

## 1. Group R — re-validation of the A18 (EXP-0030) findings on M4

### 1.1 Native pipeline / structural match

`R-bytes-mesh-baseline` (both runs, identical): compiled
`kernels/mesh_sweep.metal` at `NV=3,NP=1,PAYLOAD_BYTES=16,AMP_COUNT=1` (the
same 1-triangle shape as A18's `mesh_tri.metal`) via `harness/shdump_mesh.m`,
extracted each stage's `_agc.main` via `mesh_extract.py`/`agxparse.py`:

| stage | length (M4) | A18 (EXP-0030) | match |
|---|---:|---:|---|
| `_agc.object.write_childcount` helper | **128 B** | 128 B | **exact** |
| `_agc.mesh.write_uvb` helper | **576 B** | 576 B | **exact** |
| object `_agc.main` | 376 B | 110 B | differs (our payload-write loop adds bytes A18's `pl.scale=1.0f` single-float assignment didn't have — an expected difference in OUR test shader, not a hardware divergence) |
| mesh `_agc.main` (1-triangle emit) | 402 B | 306 B | differs (same reason: our per-index-computed `set_index` writes vs A18's fixed `lane` write) |

The two FIXED-SIZE compiler helper subroutines — the actual hardware/firmware
interface points (amplification child-count write; UVB address/slot
computation) — are **byte-length-identical to A18**, while the two
CALLER-authored stages differ only by the amount each experiment's own MSL
source asked the compiler to generate. This is the correct signature for "the
firmware-facing contract is unchanged; the caller code differs because the
callers differ."

**`43 00 00 01` present in both object and mesh streams, exactly once each,
byte-identical whether or not the mesh emits a triangle**
(`emit0_object_frame_marker_43000001_count`==`base_object_frame_marker_
43000001_count`==1, `emit0_mesh_...`==`base_mesh_...`==1; the object stage is
in fact **byte-identical** between the emit/no-emit variants:
`obj_stage_identical_base_vs_emit0: true`) — reproducing A18's exact
invariance finding.

**Interpretive correction (not a contradiction):** cross-checking against
`tools/agx-isa/db.json`'s existing `frame_marker` entry (read-only, not
modified) shows this byte sequence was already generalized by a later, M4-side
own-MSL corpus census (`EXP-M4-13`, cited inline in the DB) to a general
**pre-call/frame-setup marker** — `43 00 00 01` precedes every out-of-line
CALL in ANY shader stage, and the object/mesh-stage instances precede the
`write_childcount`/`write_uvb` helper CALLs specifically because those are
call sites, not because the marker is mesh-exclusive. EXP-0030's original
framing ("the only object/mesh-exclusive opcode group") was a correct
description of what that experiment's narrower A18 corpus (mesh/object stages
only) could see; the broader M4 corpus work has since refined — not
refuted — it. Tokenizing our mesh bytes with the (unmodified, read-only)
`tools/agx-isa/agxisa.py tokenize` CLI decodes the marker cleanly as
`frame_marker` with `companion=1` at exactly this position, confirming the DB
and our new bytes agree.

**Vertex/primitive emit still lowers to ordinary stores, not a dedicated
opcode:** `base_mesh_e7_count: 10` (ten byte0=`0xe7` device-store occurrences
in the mesh stage) vs `compute_control_e7_count: 3` (our hand-written
compute-emulation control, `kernels/compute_emul.metal`, copied verbatim from
EXP-0030) — more occurrences in the mesh stage because our test shader writes
more fields (`set_index` per-primitive in a loop) than the 3-store control,
but the SAME opcode family, exactly matching EXP-0030's "mesh emit = ordinary
memory-store family, not a dedicated emit instruction" conclusion.

### 1.2 DATA-TRACE — graphics-path submission (both runs identical)

`R-trace-{mesh,draw,compute}` (`tools/iotrace` interposer over `iohello_mesh`/
`iohello_draw`/`iohello_compute`, all unmodified or copied verbatim from prior
experiments):

| target | total IOKit calls | sel-9 (resource-map) calls |
|---|---:|---:|
| mesh draw | **58** | **39** |
| ordinary draw | **58** | **39** |
| compute dispatch | 49 | 30 |

**Mesh and ordinary draw are call-count IDENTICAL (58==58, 39==39, both
runs)**, and both are well above compute (49/30) — the same qualitative
signature A18 (EXP-0030: "mesh 59 approx.= draw 58 >> compute 49") found, now
an EXACT match on M4. **Interpretation: mesh dispatch still reuses the
graphics submission path, not a compute-plus-draw emulation, on M4.** This
experiment did not re-derive the "no separate CDM launch-descriptor BO"
sub-claim independently (no BO-role graph analysis was performed here, unlike
EXP-0030's dedicated `bograph.py` pass); it is INFERRED consistent with the
call-count match but not independently re-validated this round — flagged, not
silently promoted.

### 1.3 Verdict

**H-R CONFIRMED, no falsifier triggered.** Every structural claim this
experiment could re-test (helper-region lengths, marker presence/invariance,
emit-opcode family, IOKit call-count signature) reproduced exactly on M4. The
only nuance is an interpretive refinement already present in the existing,
unmodified `agx-isa` DB (generalizing the marker's role), not a divergence
this experiment discovered fresh.

---

## 2. Group B — object-to-mesh payload handoff (finite-resource mandate)

`B-payload-*` (11 checkpoints, `PAYLOAD_BYTES` = declared `uchar data[N]`
struct size in the object shader's `[[payload]]` argument), both runs
identical:

| PAYLOAD_BYTES | result |
|---:|---|
| 16 .. 16,384 | `OK` (compiles, pipeline creates, renders) |
| **16,385** | **`PIPELINE_FAIL`** — first invalid value |
| 16,400 .. 65,536 | `PIPELINE_FAIL` |

Exact failure text (both runs): `"Object shader payload size (16385) exceeds
the maximum payload size allowed (16384)"`. **The ceiling is enforced at
MTLRenderPipelineState creation time, not at MSL-compile time** — a
16,385-byte payload struct compiles cleanly (`COMPILE OK`) and only fails when
`newRenderPipelineStateWithMeshDescriptor:` is called. **A driver must
validate this at pipeline-build time, not shader-compile time.**

`B-override-*` (8 checkpoints, `payloadMemoryLength` explicit descriptor
override against a FIXED 256-byte struct), both runs identical:

| override | result |
|---|---|
| unset (natural=256) | `OK` |
| `0` (explicit "use natural") | `OK` |
| **128 (< natural 256)** | **`OK`** — accepted, no validation error, renders |
| 256, 512, 16,384 | `OK` |
| **16,385, 1,048,576** | **`PIPELINE_FAIL`**, same exact ceiling/message as the struct-size path |

**Finding: the maximum (16,384 bytes) is the ONLY thing validated.** An
override smaller than what the object shader's own declared payload struct
actually needs is silently accepted with no error — the API provides no
protection against a driver under-declaring `payloadMemoryLength` relative to
what the shader writes. This is a genuine (negative) safety-surface finding:
**a driver computing `payloadMemoryLength` from anything other than the
shader's own declared struct size must get it exactly right itself; Metal
will not catch an under-declaration.**

**Verdict: H-B CONFIRMED.** Single fixed ceiling (16,384 B), enforced at
pipeline-creation (not compile) time, with no independent lower-bound check.

---

## 3. Group C — UVB output layout and sizing (max vertices / max primitives)

Following EXP-0120's "does userspace supply a size, or does it just appear"
methodology (there, applied to the TVB with a negative/firmware-managed
verdict): this experiment applies it to `metal::mesh<V,P,NV,NP,topology>`'s
own compile-time NV/NP declaration, PLUS the sel-9 BO-inventory check in §4.

`C-nv-*` (14 checkpoints, NP=1 fixed), both runs identical:

| NV | result |
|---:|---|
| 1 .. 256 | `OK` |
| **257** | **`COMPILE_FAIL`** — first invalid value |
| 300, 1024 | `COMPILE_FAIL` |

Exact message: `"number of vertices (257) exceeds maximum supported (256)"`.

`C-np-*` (15 checkpoints, NV=256 fixed — the vertex-addressing ceiling, since
`set_index()` takes a `uchar`), both runs identical:

| NP | result |
|---:|---|
| 1 .. 512 | `OK` |
| **513** | **`COMPILE_FAIL`** — first invalid value |
| 600, 1024 | `COMPILE_FAIL` |

Exact message: `"number of primitives (513) exceeds maximum supported
(512)"`. **The two ceilings are independent and unequal (256 vertices, 512
primitives — 2x)**: a driver cannot assume a single shared "meshlet size"
constant; it must track both fields separately when validating a compiled
mesh pipeline against the hardware's actual capacity.

**Index-addressing-width finding (not previously characterized):**
`metal::mesh<...>::set_index(uint i, uchar v)` takes the vertex-slot reference
as an unsigned 8-bit value — **256 is not merely the observed ceiling, it is
also the largest value a primitive's index array can even address.** The 256
vertex ceiling and the 8-bit index type are consistent with each other (a
driver could never usefully declare NV>256 even if the compiler allowed it,
since no index could reference vertex 256+) — INFERRED from the public MSL
header signature (`metal_mesh`, read-only), not independently splice-tested
against a hypothetical NV>256 case (none compiles, per above, so this
inference cannot be falsified by direct construction; flagged as such).

**Verdict: H-C CONFIRMED.** Both ceilings enforced at MSL-compile time with
exact, compiler-reported numbers; NV != NP.

---

## 4. Group D — allocation ownership and raster linkage

### 4.1 Grid amplification ceiling — silent, not the reflected value

`D-amp-*` (13 checkpoints, `mesh_grid_properties::set_threadgroups_per_grid
(uint3(AMP_COUNT,1,1))` in the object stage; no `max_total_threadgroups_
per_mesh_grid` attribute and no descriptor override set, so per
`MTLRenderPipeline.h` "the device's maximum supported value is used"), both
runs identical, 64x64 target:

| AMP_COUNT | `STATUS` | `COVERED` (of 4096 px) |
|---:|---|---:|
| 0 | OK | 0 |
| 1 | OK | 15 |
| 2 | OK | 30 |
| 4 | OK | 60 |
| 64 .. 65,535 | OK | **917 (saturated — all 64 distinct offset cells filled)** |
| **65,536** | OK | **0** |
| 65,537 .. 1,048,576 | OK | **0** |

`REFLECT meshGridMax=1048576` in every case's own stdout (the API's own
reported ceiling). **The reflected ceiling (1,048,576) and the real behavioral
ceiling (65,535) differ by a factor of 16, and the real ceiling fails
SILENTLY** — no compile error, no pipeline error, no command-buffer error;
`STATUS OK` and `CMDBUF_STATUS 4` (Completed) every time, with zero rendered
output. **This is the sharpest and most operationally important finding in
this experiment: a driver that trusts `maxTotalThreadgroupsPerMeshGrid`'s
reflected value for validation will pass through amplification counts that
silently produce nothing on real hardware.** 65,536 = 2^16 is consistent with,
but not proven to be, a 16-bit internal count field; ruled out mod-65536
wraparound specifically (65,600 does NOT behave like 65,600 mod 65,536 = 64,
which would render 16 px; it renders 0, matching every other value >= 65,536)
— a hard cutoff, not an overflow-wraparound.

The exact same 65,536 boundary, with the exact same silent-zero signature,
reproduces independently on the UNRELATED top-level indirect-draw mesh-grid
mechanism (§6, object-less pipeline) — cross-mechanism agreement that this is
a real, shared ceiling rather than an artifact of this one code path.

**INTERPRETED, not independently isolated further:** whether this ceiling is
a genuine silicon/firmware limit or a Metal-runtime-imposed software safety
net cannot be distinguished from userspace alone (PRE_REGISTRATION.md §4
confounder) — would require an ISA-level splice test (out of scope here,
follow-up candidate).

### 4.2 Raster linkage — amplified threadgroups genuinely reach the rasterizer

`COVERED` growing monotonically 0->15->30->60->917 as `AMP_COUNT` increases
from 0 to 64 (each amplified threadgroup's `mesh_main`'s `tgid`-dependent
offset places its triangle at a DIFFERENT 1-of-64 grid cell — see
`kernels/mesh_sweep.metal`) is direct, positive evidence that **every
amplified mesh threadgroup's own emitted geometry independently reaches the
rasterizer/fragment stage**, not just the first one — extending A18's
single-triangle-only validation (EXP-0030 §5) to genuine multi-threadgroup
amplification for the first time on either target.

### 4.3 Allocation ownership — CONFIRMED firmware-managed (EXP-0120 methodology)

`D-trace-{small,nearmax,highamp}` (iotrace + `--dump`/BODUMP snapshot after
each mesh draw, `analysis/iotrace_parse.py` copied verbatim from EXP-0120),
both runs identical:

| checkpoint | NV | NP | PAYLOAD_BYTES | AMP_COUNT | `n_bo` | `size_multiset` |
|---|---:|---:|---:|---:|---:|---|
| small | 3 | 1 | 16 | 1 | 37 | `[14336, 32768x15, 65536x3, 131072x14, 475136, 786432, 1048576]` |
| near-max | 256 | 512 | 16384 | 1 | 37 | **identical to small** |
| high-amp | 3 | 1 | 16 | 65,535 | 37 | **identical to small** |

**Byte-for-byte identical BO count and size multiset across the smallest
legal configuration, the largest legal (NV/NP/payload) configuration, and the
largest still-effective (pre-65,536-cliff) amplification configuration.** No
userspace-registered buffer's size tracks payload size, vertex count,
primitive count, or amplification count. **This directly confirms, by
construction (not by absence of evidence), EXP-0030's A18 claim that the UVB
and object-payload intermediates are firmware/driver-allocated and not
user-visible buffers** — the exact verdict shape EXP-0120 reached for the TVB
("no userspace surface at all"), now independently reached for the UVB via
the identical method.

**Verdict: H-D CONFIRMED for both (i) and (ii).**

---

## 5. Allocation ownership / userspace-vs-firmware split (summary table)

| object | who allocates/sizes it | evidence |
|---|---|---|
| UVB (mesh vertex/primitive output buffer) | **firmware** — no userspace-visible BO scales with NV/NP/payload/amplification | §4.3 |
| object-payload buffer | **firmware** — same BO-invariance evidence (payload IS one of the three swept axes) | §4.3 |
| `payloadMemoryLength` | **userspace supplies it** (an explicit `MTLMeshRenderPipelineDescriptor` field a driver must compute and set) — but Metal validates only the upper bound, not adequacy | §2 |
| grid amplification count (`AMP_COUNT`) | **userspace/object-shader supplies it** (a plain `uint3` argument to a builtin call) — but its real ceiling (65,536) is far below and NOT reported by the API's own reflection (`maxTotalThreadgroupsPerMeshGrid`) | §4.1 |
| ICB for mesh commands (CPU- or GPU-authored) | **userspace allocates it explicitly** (`newIndirectCommandBufferWithDescriptor:maxCommandCount:`) — an ordinary, fully userspace-owned Metal object, unlike the UVB | §6 |

---

## 6. Group I — indirect and ICB mesh dispatch

### 6.1 Indirect draw — same grammar as compute indirect dispatch

`I-indirect-x*` (object-less mesh pipeline, `drawMeshThreadgroupsWithIndirectBuffer:`,
grid X written by a tiny compute kernel into a `MTLDispatchThreadgroupsIndirectArguments`-
shaped buffer), both runs identical:

| X | `COVERED` (of 4096, 64x64 target) |
|---:|---:|
| 0 | 0 |
| 1 | 15 |
| 2 | 30 |
| 65,535 | 917 (saturated) |
| **65,536, 1,048,576, 16,777,216** | **0** |

**The same exact 65,536 silent-zero boundary as the object-stage amplification
mechanism (§4.1)** — independent confirmation via a structurally unrelated
code path (no object shader at all here). `I-indirect-misaligned-offset2`
(`indirectBufferOffset=2`, not 4-byte-aligned): `OK`, `COVERED 15` — accepted
and correct, matching EXP-0098/0124's finding for ordinary compute-indirect
dispatch, now confirmed for the mesh indirect-draw grammar too.
`I-indirect-oob-calloffset` (call offset 4096 bytes into a 16-byte
allocation): `OK`, `COVERED 0` — reads as an effective zero grid rather than
faulting, a real asymmetry against the ICB range-past-max case (§6.2, which
DOES fault) that this experiment did not root-cause further.

### 6.2 ICB — both CPU- and GPU-authored mesh commands work

`I-{cpu,gpu}-baseline`: both `OK`, `COVERED 15` (identical to each other and
to the direct-draw baseline). **This is a genuinely new confirmed capability
this experiment set out to test empirically, not merely assumed from the
public header's existence**: the public MSL toolchain header
(`metal_command_buffer`) declares `render_command::draw_mesh_threadgroups()`/
`draw_mesh_threads()` gated behind `__HAVE_RENDER_COMMAND_MESH__` — whether
that macro is actually defined for Apple9/M4 was unknown until compiled;
**it compiled, encoded, and executed correctly on M4**, following the exact
`ICBContainer`/argument-encoder/`render_command(icb, idx)` pattern EXP-0124
validated for ordinary draw/dispatch ICB commands (`kernels/mesh_icb_gpu.metal`,
directly modeled on EXP-0124's `kernels/i_common.metal`).

**Range/barrier boundary — matches EXP-0098's ordinary-ICB finding, with one
divergence:**

| case (maxCommandCount=8) | icb_cpu | icb_gpu |
|---|---|---|
| `loc=0,len=8` (full range) | OK, COVERED 15 | OK, COVERED 15 |
| `loc=8,len=1` (`location==maxCommandCount`) | OK, **COVERED 0** (0 commands executed, no fault) | same |
| `loc=9,len=1` (`location>maxCommandCount`) | **`CMDBUF_ERROR`** | same |
| `loc=0,len=20` (oversized length) | OK, COVERED 15 (silently clamped to 8) | same |

The `location==maxCommandCount` -> 0-executed-no-fault vs
`location>maxCommandCount` -> fault split, and the oversized-length silent
clamp, are an **exact match** to EXP-0098's `GLPRE-A02` finding for ordinary
draw ICBs (`n_executed = max(0,min(length,maxCommandCount-location))` if
`location<maxCommandCount`, else 0 if equal, else FAULT). **Divergence:**
EXP-0098's ordinary-ICB fault was `kIOGPUCommandBufferCallbackErrorPageFault`;
this experiment's mesh-ICB `range-past-max` fault text (both runs, identical)
is `"Caused GPU Hang Error (00000003:kIOGPUCommandBufferCallbackErrorHang)"`
— a genuinely different underlying GPU-level error class for the same logical
violation, applied to a mesh-typed command. Both are fault-CONTAINED
(`CMDBUF_ERROR`, process returns normally, host unaffected) but a driver must
not assume the ordinary-ICB error code generalizes to mesh ICBs.

### 6.3 `maxCommandCount` — a materially lower, three-region ceiling

`I-cpu-maxcount-*` (12 checkpoints), both runs identical:

| maxCommandCount | result |
|---:|---|
| 1,024 .. 524,288 | `OK` |
| **1,048,576 .. 3,145,728** | **`CMDBUF_ERROR`** (allocates; the render command buffer referencing it fails, contained) |
| **4,194,304 and up (incl. 6,391,319 / 6,391,320)** | **`CRASH_SIG11`** (process-level SIGSEGV inside `newIndirectCommandBufferWithDescriptor:`, contained to the process, clean recovery every time) |

EXP-0124 established, for an ORDINARY (draw/dispatch) ICB, a single sharp
crash boundary at exactly 6,391,319 (works) / 6,391,320 (crashes), with
**4,194,304 explicitly confirmed working**. For a
`MTLIndirectCommandTypeDrawMeshThreadgroups`-typed ICB, this experiment found
**a third, intermediate failure region** (`CMDBUF_ERROR`, not present at all
in EXP-0124's ordinary-ICB sweep) starting at 1,048,576, AND the crash region
starts far earlier (4,194,304, the exact value that still works for an
ordinary ICB) — **the boundaries are not exact numbers shared with EXP-0124's,
they are a materially lower and structurally different (three-region, not
two-region) envelope specific to the mesh command type.** Both boundary
transitions (OK/CMDBUF_ERROR between 524,288 and 1,048,576; CMDBUF_ERROR/crash
between 3,145,728 and 4,194,304) are **bracketed, not exactly bisected** — a
disclosed limitation, not a silently narrowed claim.

### 6.4 Verdict

**H-I CONFIRMED for (i) grammar reuse, (ii) both authoring paths work, (iii)
range boundary logic matches with a disclosed fault-signature divergence, and
(iv) the mesh ICB ceiling is materially lower than the ordinary-ICB ceiling —
all four sub-hypotheses held, with (iii)'s error-code divergence and (iv)'s
un-bisected exact boundaries as the disclosed nuances.**

---

## 7. Disclosed non-determinism (standing-gate finding)

`analysis/verify.py --captured` initially FAILED on exactly one case,
`D-trace-nearmax`: run01's `selector_histogram` recorded selector `32` (0x20,
an incidental IOKit selector unrelated to sel-9 resource-map registration)
firing **twice**; run02 recorded it firing **once** (`total_calls` 59 vs 58,
otherwise byte-identical, including the full 37-element `size_multiset` and
`sel9_calls`). Root-caused as far as userspace evidence allows: a single
incidental, non-reproducible IOKit call, plausibly a low-frequency
housekeeping/notification selector whose exact firing count is not fully
deterministic across independent process launches — this experiment did not
determine (and does not claim to know) the selector's specific role. Per the
standing gate's own "NO nondeterministic field in byte-compared records"
requirement, `total_calls`/`selector_histogram` were removed from the
strict-equality gate (kept in the raw records and reported for context); the
fields the allocation-ownership hypothesis (§4.3) actually depends on
(`n_bo`, `sel9_calls`, `size_multiset`) were byte-identical in this case and
every other, both before and after this change. Documented per CODEX §7
("never silently drop negative or inconvenient outcomes") rather than quietly
patched away.

---

## 8. Answering the row's escape clause

DRV-P2-03: *"Decode dispatch, object-to-mesh handoff, UVB/output layout and
sizing, raster linkage, barriers, indirect/ICB behavior, and allocation
ownership. **Otherwise do not expose it.**"*

**This experiment's evidence supports exposing native mesh/object shading in
a first driver**, with the following items now closed or bounded by
construction (not merely decoded from a captured template):

- **Dispatch decode:** re-confirmed on M4 — graphics-path submission, real
  fixed-function amplification+rasterization, ordinary-store emit (§1).
- **Object-to-mesh handoff:** exact payload ceiling (16,384 B),
  enforcement point (pipeline-creation), and the min-adequacy gap a driver
  must self-enforce (§2).
- **UVB/output sizing:** exact, independent NV (256) / NP (512) ceilings,
  compile-time enforced (§3).
- **Raster linkage:** positively demonstrated for genuine multi-threadgroup
  amplification, not just a single triangle (§4.2).
- **Allocation ownership:** UVB and object-payload buffers are
  firmware-managed by direct construction-based evidence, not absence of a
  captured example (§4.3, §5).
- **Indirect/ICB behavior:** both authoring paths characterized, with the two
  divergences from ordinary (non-mesh) command behavior explicitly flagged
  for a driver to respect (§6).

**What a first driver still needs before shipping mesh shading, beyond this
experiment's scope:**

- **The 65,536 amplification ceiling is unexplained and untrusted by its own
  reflection API** (§4.1) — a driver exposing mesh shading MUST clamp/validate
  amplification counts itself below 65,536 rather than trusting
  `maxTotalThreadgroupsPerMeshGrid`, and should treat any larger request as a
  silent-failure hazard until root-caused at the ISA/firmware level (follow-up,
  not answered here: hardware truncation vs. Metal-runtime software clamp,
  PRE_REGISTRATION.md §4).
- **`0x43`'s field-level semantics were not independently splice-validated
  this round** (EXP-0030 marked it "inferred (byte-diff), role not
  splice-validated" on A18; this experiment only re-confirmed byte-level
  presence/invariance on M4, via the SAME non-splice method).
- **The mesh-ICB `maxCommandCount` boundaries are bracketed, not exact**
  (§6.3) — a driver should stay well clear of the entire 524,288-4,194,304
  region rather than rely on a specific cutoff.
- **Barriers between object/mesh stages and downstream consumers** (the row's
  explicit "barriers" item) were **not tested this round** — this experiment
  covered dispatch/handoff/sizing/linkage/ownership/indirect-ICB but not
  synchronization ordering guarantees for mesh output; flagged as the clearest
  remaining gap for DRV-P2-03, a natural EXP-0098/EXP-0124-style follow-up
  (their GLPRE-A01/`i_icbbarrier` synchronization-contract method, not yet
  applied to mesh-stage output).
- The A18-vs-M4 re-validation in §1 covers structural/DATA-TRACE claims only;
  it does not re-run EXP-0030's own splice-based HW-VALIDATED render
  correctness proof independently beyond this experiment's own baseline
  render (§1.1's shape match + this experiment's own `D-amp`/`I-indirect`
  correct-triangle renders serve that role here).

**Conclusion: mesh/object shading should be exposed by a first Apple9
driver** — the pipeline is real, its finite envelopes are now measured with
exact or tightly-bracketed numbers and disclosed failure modes, and its
allocation ownership is settled — **conditional on** the driver (a) treating
the 65,536 amplification ceiling and the mesh-ICB `maxCommandCount` envelope
as hard, self-enforced software limits rather than trusting Metal's own
reflected maxima, and (b) a follow-up experiment closing the barriers/
synchronization sub-item before final sign-off.

---

## 9. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE + DATA-TRACE + PUBLIC (bounded)
Inputs inspected:
  - Our own authored MSL: kernels/mesh_sweep.metal, kernels/mesh_indirect.metal,
    kernels/mesh_icb_gpu.metal, kernels/compute_emul.metal (copied verbatim
    from EXP-0030, our own prior work).
  - Our own authored ObjC harness: harness/mesh_probe.m, harness/shdump_mesh.m,
    harness/iohello_mesh.m (copied verbatim from EXP-0030).
  - Public Metal.framework headers (MTLRenderPipeline.h, MTLRenderCommandEncoder.h,
    MTLIndirectCommandBuffer.h, MTLIndirectCommandEncoder.h) and public MSL
    toolchain headers (metal_mesh, metal_command_buffer) -- read for public
    API/language interface signatures only (method names, parameter types,
    documented default-value semantics), never for implementation/hardware
    behavior; every hardware behavior claim in this document comes from live
    execution, not from reading these headers.
  - tools/agx-isa/db.json + agxisa.py -- read-only cross-check of the
    `frame_marker` entry and tokenize CLI; not modified.
  - tools/shdump/, tools/iotrace/ -- read-only, compiled from source into this
    experiment's own work/bin/, never modified, never written into.
Apple binary introspection: NONE. No Metal/AGX/IOGPU/IOAccelerator framework,
  dylib, kext, or firmware binary was disassembled, decompiled, or otherwise
  introspected. Every compiled AGX byte inspected in Sec. 1 is the output of
  our own MSL compiled via the public newLibraryWithSource: runtime path.
Reproduction: analysis/run.py --run-id <id> (x2), analysis/verify.py
  --selftest / --seqtest / --captured (see README.md "Commands").
Evidence: raw/m4_20260828_run01/records.jsonl (sha256
  1b2205caad6fb1a4644c975cd0685057d45a11a1d23c275c6804aef7ef907528),
  raw/m4_20260828_run02/records.jsonl (sha256
  721218cfe4eb5497135be6fe331d099f98cb1608df272c4ef21fff39f697762b),
  manifest.json, CAPTURE_CONTRACT.json.
```

## 10. Evidence labels

- Group R structural (§1.1): **OWN-SHADER** (our own compiled bytes, our own
  parser, cross-checked against the existing read-only `agx-isa` DB).
- Group R DATA-TRACE (§1.2): **DATA-TRACE**.
- Groups B/C/D.1/D.2/I compile/pipeline/render outcomes: **HW-PROBE** (public
  Metal API, our own MSL, live M4 execution, byte-exact reproduced across two
  independent runs).
- Group D.3 allocation ownership: **DATA-TRACE** (EXP-0120 methodology reused
  verbatim).
- `0x43` field-level semantics, the 65,536 ceiling's hardware-vs-software
  origin, and the un-bisected ICB boundaries: **INFERRED / UNKNOWN**, flagged
  explicitly in §8, not promoted to HW-VALIDATED.

## 11. Files

- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` — frozen hypotheses/matrix/hashes.
- `kernels/mesh_sweep.metal`, `kernels/mesh_indirect.metal`,
  `kernels/mesh_icb_gpu.metal`, `kernels/compute_emul.metal`.
- `harness/mesh_probe.m`, `harness/shdump_mesh.m`, `harness/agxparse.py`,
  `harness/mesh_extract.py`, `harness/iohello_mesh.m`.
- `analysis/gen_matrix.py`, `analysis/run.py`, `analysis/verify.py`,
  `analysis/iotrace_parse.py`, `analysis/fixtures/`.
- `raw/m4_20260828_run01/`, `raw/m4_20260828_run02/`.
- `work/smoke/smoke01/` (non-recorded, not evidence), `work/bin/` (build artifacts).
