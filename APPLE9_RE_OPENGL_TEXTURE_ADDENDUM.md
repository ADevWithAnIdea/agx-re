# Apple9 RE Addendum: OpenGL 4.6 Compiler Questions

Date: 2026-08-27

Purpose: this is a **discovery and documentation handoff only**. Do not write Mesa, compiler, or
driver code as part of this task. The primary questionnaire remains
`APPLE9_RE_INFORMATION_GAPS.md`; this addendum contains OpenGL-relevant compiler questions that are
not asked explicitly enough there.

Target contract: desktop OpenGL 4.6, the extensions normally needed by WineD3D-class Direct3D
translation, and Mesa NIR produced from those APIs. For the texture questions, Vulkan-only YCbCr,
sparse residency, `samples_identical`, and backend-only prefetch operations are out of scope.

## Required answer standard

Use the evidence and finite-resource rules from `APPLE9_RE_INFORMATION_GAPS.md`. For every operand,
field, table, or resource with a finite representation, document:

- the exact width, type, signedness, units, scale, range, and legal combinations;
- the largest legal value and first illegal value;
- what Metal rejects or rewrites, separately from what raw hardware accepts;
- what an unpopulated, out-of-range, reserved, NaN, or infinite value does where applicable;
- whether the result is zero, clamped, rounded, aliased, discarded, faulting, or device-losing;
- a minimal executable hardware test, raw artifacts, and the authoritative document to update.

Do not infer hardware absence merely because Metal does not emit a form. Record `unknown` unless a
raw test or an exact, independently validated equivalent closes it.

## Shader I/O and interpolation questions

### GLIO-A01 — Exact varying and coefficient capacity and exhaustion semantics

What are the exact, independently hardware-validated limits of the vertex-output UVS scalar-slot
namespace and the fragment coefficient/input-slot namespace, and what happens at the first value
beyond each limit?

Distinguish the API-advertised limit, the apparent instruction-field width, and the maximum exercised
simultaneously by an executable producer/consumer pipeline. Test whether the producer and consumer
limits differ; whether smooth, noperspective, flat, special outputs, or coefficient bindings consume
different amounts of the finite namespace; and whether an over-limit pipeline is rejected by Metal,
rejected by pipeline/link state, aliases or wraps a slot, faults, or executes with another observable
result. Determine whether any supported alternate representation exists; do not assume varying slots
can be spilled like GPRs.

### GLIO-A02 — Complete `get_sr` operand and result encoding

What is the complete Apple9 encoding of `get_sr` for every register and result form required by the
OpenGL compiler?

Decode the destination low and high bits across the full legal GPR range, the byte-0 form bit, every
byte-2/byte-3 suffix field, result width, Boolean representation, signedness or extension behavior,
and any stage- or datapath-specific restrictions. Exercise low, boundary, and highest legal
destination registers with ordinary integer IDs, fragment Boolean values, and coverage/helper
values. Test the first unencodable destination and every reserved suffix combination safely. Keep
the SR selector number distinct from destination and width fields.

### GLIO-A03 — Exact vertex, instance, base, and draw-parameter semantics

For indexed and non-indexed, instanced and non-instanced, direct and multidraw operation, what exact
values do Apple9's vertex ID, instance ID, inferred base-vertex SR `0x88`, inferred base-instance SR
`0x8a`, and any draw-ID source return?

Use independently distinguishable nonzero first-vertex, base-vertex, first-instance/base-instance,
instance count, draw ID, and index-buffer values. Determine whether each raw ID includes its base,
how signed base-vertex addition behaves, what non-indexed draws report, and how the results map to
NIR `load_vertex_id`, `load_vertex_id_zero_base`, `load_first_vertex`, `load_base_vertex`,
`load_instance_id`, `load_base_instance`, and `load_draw_id`. Identify every value that must instead
come from driver-uploaded draw state and document that table/preamble ABI. Test the legal boundaries
and first rejected or overflowing values.

### GLIO-A04 — Fragment MSAA system-value ABI

What are the exact Apple9 sources and semantics of NIR sample ID, sample position, input sample mask,
coverage mask, and helper status on executable 1x, 2x, and 4x fragment pipelines?

Decode the currently unresolved `0x97` sample-ID path and any sample-position or coverage loads.
Render patterns that distinguish every sample, programmable sample positions, partial primitive
coverage, alpha-to-coverage, API sample masks, helper invocations, early and late tests, and
discard/demote. Record bit widths, component order, coordinate convention, per-sample versus
per-pixel stability, inactive-bit behavior, and whether any value changes during the invocation.
Test the first invalid sample index and mask bits beyond the active sample count. This question is
about the built-in delivery ABI; interpolation and derivative behavior remains in `FS-02` through
`FS-08` of the primary questionnaire.

### GLIO-A05 — Exact compute grid-count system-value ABI

How is NIR `load_num_workgroups` produced for every dimension in direct and indirect OpenGL compute
dispatches?

The observed Apple compiler sequence using apparent SRs `0xa8` through `0xaa`, a device load, and a
division must be decoded rather than treating a bare SR read as the workgroup count. Identify what
each raw SR actually returns, the loaded address and record layout, the divisor and rounding rule,
and the direct/indirect dispatch differences. Test asymmetric X/Y/Z grids, non-unit and non-power-of-
two local sizes, the largest legal dimensions and product, the first invalid value, and malformed or
overflowing indirect records. Map the final values to NIR `load_num_workgroups` without relying on an
Apple compiler sequence as the specification.

### GLIO-A06 — Finite ranges and overflow behavior of shader system values

For every Apple9 system value exposed to the OpenGL compiler, document its returned bit width and the
maximum executable value independently of the apparent command or instruction field width.

At minimum cover vertex and instance IDs/counts, signed base vertex, base instance, draw ID/count,
primitive ID, workgroup count and size per dimension, global/local invocation IDs, subgroup and
sample IDs, sample and coverage masks, layer, and viewport index. For each controlling draw/dispatch
field, test the largest legal value and first illegal value and distinguish API rejection, userspace
packing truncation, firmware rejection, arithmetic wrap, aliasing, a GPU fault, and successful raw
execution. State the conservative driver-advertised limit and required validation behavior; do not
infer that a 32-bit returned value proves a 32-bit executable launch range.

## Fragment execution and per-sample state questions

The primary questionnaire deliberately asks the broad correctness questions in `OPT-09`, `FS-06`,
`FS-12`, `SIMD-07`, and `DRV-RASTER-01`. The questions below do not replace them. They decompose the
fragment-liveness and sample-resolution state machine far enough for a later compiler implementation
to distinguish live invocations, original helpers, demoted helpers, terminated invocations, and
individually live or killed samples.

For every experiment in this section, observe effects independently through color, depth, stencil,
sample-mask/coverage, occlusion-query results, device-memory stores, image stores, and atomics where
the operation is legal. Do not use absence of color as proof that every other side effect was
suppressed. Include divergent 2x2 quads with distinguishable values in every lane and, for MSAA,
distinguishable values in every sample.

### GLFS-A01 — Exact fragment sample-state operation and finite mask capacity

What Apple9 instruction or instruction sequence kills samples, submits surviving samples to depth
and stencil testing, and makes the final set of samples eligible for tilebuffer output?

Decode every opcode, operand, modifier, predicate, mask, and state field. In particular, determine
whether the physical operation has independent `target` and `live` masks like the current Asahi
model, or has different semantics that require another representation. Establish whether its masks
are immediate, register-sourced, pipeline-sourced, or composed from several sources, and whether an
operation affects the whole fragment, only the active sample, or an explicitly selected subset.

For 1x, 2x, and 4x pipelines, test every mask value, repeated and overlapping operations, an empty
target, an empty live set, already-killed samples, and samples already submitted to depth/stencil.
Determine whether each covered sample must be killed or tested exactly once, whether either action
is idempotent, and what a second or contradictory action does. Record the exact mask width, maximum
hardware sample count, inactive high-bit behavior, first unsupported sample count, and behavior of
every reserved encoding. Separate Metal validation, command/pipeline-state validation, and raw
instruction behavior. If another supported sample count or mask representation exists, include it;
otherwise document the conservative limit a later driver must advertise.

### GLFS-A02 — Demote, discard, terminate, and helper-lane state transitions

What are the exact Apple9 state transitions produced by fragment discard, NIR demotion, and true
invocation termination?

Start with both a covered live invocation and an uncovered original helper. At distinguishable
points in divergent control flow, apply every candidate discard/demote mechanism and then test
whether the invocation continues to execute ALU, ordinary loads, texture operations with implicit
LOD, derivatives needed by neighboring lanes, quad operations, and subgroup operations. Separately
test whether it can subsequently produce any observable framebuffer, depth/stencil, sample-mask,
query, buffer, image, or atomic side effect. Query helper status before and after the transition.

Determine whether demotion is per-invocation or per-sample, whether killing the last live sample
automatically changes helper state, whether a later operation can make a demoted invocation or
killed sample live again, and whether true termination requires a separate branch/halt operation.
Exercise nested and divergent conditionals, loops, function-call-equivalent control flow, and
termination both before and after derivative-producing code. This must close the broad `OPT-09`
question with executable behavior, while retaining `discard`, `demote`, and `terminate` as separate
terms unless the evidence proves them equivalent for all portable-NIR observations.

### GLFS-A03 — Helper-status source and changes during an invocation

What does the inferred helper-status `get_sr 0x84` return in every fragment execution state, and is
it the complete value required by NIR helper-invocation queries?

Validate the selector and complete result encoding with raw execution rather than a compiler byte
diff. Test original uncovered helpers, covered invocations, partially covered MSAA invocations,
per-sample shading, API sample masks, alpha-to-coverage, failed early depth/stencil tests, explicit
demotion, per-sample killing, and killing the final live sample. Read it repeatedly before and after
each transition. Record the Boolean representation and width, whether the result is dynamically
updated, and whether software must combine it with a compiler-maintained demotion mask, current
coverage, or active-sample state. Cross-reference `GLIO-A02` for general `get_sr` encoding and
`GLIO-A04` for delivery of the other MSAA system values.

### GLFS-A04 — Incoming, current, and shader-written sample-mask semantics

What exact values correspond to immutable API-visible incoming coverage, the invocation's current
live-sample state, and shader-written sample-mask output on Apple9?

Independently vary primitive coverage, fixed-function sample coverage, the OpenGL API sample mask,
alpha-to-coverage, sample shading, early depth/stencil pass and failure, discard/demote, and a shader
sample-mask write. Determine the ordering used to combine them and identify which stages affect
NIR's incoming sample-mask value, any current-sample-mask intrinsic used by Mesa lowering, and final
color/depth/stencil eligibility. Read masks before and after demotion and sample killing where an
instruction permits it.

Test zero, every single bit, every legal combination, inactive bits above the framebuffer's sample
count, multiple shader writes, partial component writes, and dynamically selected sample-mask array
elements if more than one word can ever be exposed. Document whether shader output replaces,
intersects, or otherwise combines with prior coverage; when its effect becomes visible; and whether
killing one sample affects helper status or execution of the remaining samples. State the exact
number of implemented mask bits and words, the maximum sample index, the first invalid index, and
all out-of-range behavior rather than assuming OpenGL's 32-bit word size is the hardware capacity.

### GLFS-A05 — Early/late depth-stencil ordering and fragment side effects

What exact Apple9 events perform early and late depth/stencil tests and updates, and what ordering do
they have relative to shader execution, demotion, sample-mask output, tilebuffer output, occlusion
queries, buffer/image stores, and atomics?

Test at minimum ordinary late testing, an explicit early-fragment-tests shader, fragment depth
output, conservative-depth qualifiers, fragment stencil output if supported, discard before and
after a candidate test operation, and a mixture of passing and failing samples in one fragment.
Determine separately when comparisons occur, when depth/stencil values are updated, when an
invocation or sample is prevented from executing, and which effects a later discard can and cannot
undo. Establish whether tests are submitted through the operation from `GLFS-A01` or another
instruction/state field and whether each sample may be tested more than once.

For every relevant pipeline-state field, record its exact width and legal combinations, including
the first rejected or reserved combination. If early and late testing consume finite temporary,
attachment, or per-sample state, measure its exact capacity and exhaustion behavior. The resulting
documentation must be sufficient to decide test placement without relying on Apple compiler
scheduling as the specification.

### GLFS-A06 — Suppression of helper and demoted-lane side effects

Which Apple9 operations automatically suppress side effects from original helper lanes and demoted
lanes, and which require explicit compiler predication or control flow?

Test buffer stores, image stores, every supported atomic family, color output, dual-source output,
depth output, stencil output, sample-mask output, occlusion-query contribution, and any observable
tile-memory operation. Run each first from an original helper and then from a covered invocation
demoted immediately before the operation. Repeat with early and late tests and inside divergent
control flow. Also establish whether loads remain legal and whether helper execution of a faulting
or out-of-bounds access can itself create an observable fault despite write suppression.

For every instruction family, document whether suppression is inherent, controlled by an encoded
predicate or execution-mask bit, or must be synthesized. Decode any predicate field completely,
including its finite register/immediate range and behavior at the first unencodable value. This item
extends `FS-12`: suppression of color alone does not close it.

### GLFS-A07 — Sample shading invocation and liveness model

How does Apple9 execute OpenGL per-sample shading, and how do invocation frequency, sample ID,
coverage, helpers, demotion, and derivative quads interact?

For every supported framebuffer sample count and representative `MinSampleShading` values from zero
through one, count shader invocations and record the active sample ID and every coverage/helper
value. Test full and partial primitive coverage, API sample masks, alpha-to-coverage, mixed
depth/stencil pass results, and demotion of one or all samples. Determine whether Apple9 launches
one invocation per sample, groups samples into invocations, or loops samples in software or a
prolog/epilog; identify the exact pipeline or shader state controlling that choice.

Document the finite invocation/sample grouping capacity, all legal rates, quantization of requested
minimum rates, the first unsupported state, and whether excess or reserved values are rejected,
clamped, aliased, or faulting. Cross-reference `GLIO-A04` for the built-in register ABI, but answer
execution frequency and liveness here.

### GLFS-A08 — Pixel/sample interlock encoding, scope, ordering, and limits

Do the inferred Apple9 `0x07` acquire and release forms implement all ordering required by OpenGL
fragment-shader interlock for actually overlapping fragments?

First fully decode and raw-execute both forms. Then use fragments with deliberate same-pixel and
same-sample read/modify/write hazards to test ordered and unordered pixel and sample interlock,
different pixels, different samples of one pixel, primitive submission order, multiple render
targets, tile-memory accesses, buffer/image accesses, and atomics. Distinguish raster-order
serialization from ordinary device-memory visibility and identify every additional fence required.

Test divergent entry where legal, release on every control-flow exit, discard/demote/termination
inside the protected region, nesting, repeated regions, loops, and a fragment with no surviving
samples. Determine forward-progress and deadlock behavior for malformed or unbalanced sequences
using safe, recoverable experiments. Establish whether there is a finite raster-order-group,
interlock, attachment, sample, or in-flight-fragment namespace; for each, document the exact count,
encoding, allocation scope, largest legal value, first illegal value, exhaustion behavior, and
whether a semantically exact fallback exists. Do not treat Metal acceptance or an isolated byte
diff as proof of overlapping-fragment ordering.

## Compute, shared memory, and software pre-raster pipeline questions

OpenGL geometry shaders, transform feedback, and tessellation will use Mesa's software `poly`
architecture. Do **not** spend this assignment designing production lowering code or searching for a
native Apple9 geometry-shader/transform-feedback implementation. The required RE facts are the
ordinary compute, memory, generated-draw, and vertex-export mechanisms on which that software path
depends. Native tessellation remains optional under `DRV-P2-02` in the primary questionnaire and is
not a prerequisite for this path.

### GLCS-A01 — Complete compute system-value and launch ABI

What exact Apple9 values and encodings implement every compute system value required by OpenGL and
by generated geometry/tessellation helper kernels?

Independently validate local invocation ID in X/Y/Z, linear local invocation index, workgroup ID,
workgroup size, number of workgroups, subgroup ID/count where exposed, and the arithmetic required
for global invocation ID. Establish component order, bit width, dimension linearization order,
whether values are direct SRs or derived from a parameter record, and whether any value differs
between direct, indirect, and variable-local-size dispatch. This extends `GLIO-A05`, which asks in
detail only about `load_num_workgroups`.

Test asymmetric and non-power-of-two local sizes and grids, one-dimensional helper dispatches,
maximum and partial hardware threadgroups where constructible, and all legal OpenGL variable-group-
size states. For every axis and product, document the maximum executable value, first illegal value,
overflow behavior of derived global IDs, dispatch-record field width, and the difference among API
rejection, userspace truncation, firmware rejection, wrap, and a successful raw launch. Include the
exact ABI by which a generated compute program receives its root/parameter-table pointer.

### GLCS-A02 — Threadgroup/shared-memory addressing and finite allocation semantics

What is the complete Apple9 compiler and command ABI for OpenGL `shared` memory?

Decode the threadgroup load/store address calculation, including the inferred `0x1c` address/base
operation, all source and destination fields, byte versus element units, immediate and dynamic
offset ranges, legal access widths and vector lengths, alignment requirements, and interaction with
threadgroup atomics and barriers. Execute independently assembled 8-, 16-, 32-, 64-, and 128-bit
accesses where legal, including unaligned and boundary-crossing cases. Determine the safe behavior
of zero-size, one-past-end, partially out-of-range, and malformed accesses rather than extrapolating
device-memory behavior.

Decode the CDM/USC fields allocating static and dynamic threadgroup memory. Establish the exact
maximum bytes per workgroup on G16G and G17P, allocation granularity, base alignment, combination of
static and dynamic allocation, relationship to local size/GPR/scratch occupancy, zero-allocation
encoding, largest legal value, first illegal value, and exhaustion result. Distinguish pipeline or
dispatch rejection, reduced occupancy, firmware rejection, fault/device loss, and aliasing. Record
the conservative OpenGL limit and validation rule a later driver must use. Cross-reference
`ATOM-02`, `ATOM-09`, `DRV-ABI-01`, and `DRV-RASTER-01`, but do not leave the instruction and
allocation contracts implicit in those broad items.

### GLPRE-A01 — Compute-to-vertex/tiler visibility for generated geometry

Can the unchanged Asahi UAPI express a fully GPU-driven sequence in which one or more compute
dispatches write parameter records, vertex data, an index buffer, and an indirect draw record that a
following vertex/tiler draw consumes without a CPU round trip?

Demonstrate each producer/consumer pair independently and then the complete chain. Identify the
exact CDM/VDM command ordering, UAPI barrier fields, shader fences, cache flushes, invalidates,
control-stream boundaries, and submit/queue restrictions required for visibility. Repeat with
multiple compute-to-draw and draw-to-compute transitions in one submission, aliasing and nonaliasing
buffers, pipeline switches, and direct and indirect generated draws. Establish whether the same
rules cover tessellation factors, geometry count/prefix buffers, transform-feedback counters, and
the final rasterization vertex inputs.

For every finite command, link, barrier, stream, pool, or in-flight dependency resource encountered,
record its exact capacity, lifetime and reuse scope, largest valid sequence, first invalid sequence,
exhaustion behavior, and semantically correct fallback. This question specializes `DRV-CMD-01`,
`DRV-MEM-01`, and `DRV-INDIRECT-01` for the required software pre-raster pipeline.

### GLPRE-A02 — Device-generated draw/index grammar and hard limits

What are the exact Apple9 records and limits for a shader-produced indexed or non-indexed draw that
consumes software-generated geometry?

Validate all address, count, stride, index-type, restart, base-vertex, first-index/first-vertex,
instance-count, first-instance, and draw-count fields after the bytes have been written by a shader,
not merely by CPU-created Metal state. Cover 8-, 16-, and 32-bit indices where supported; zero-count
draws; restart at the first and last index; misaligned records and buffers; the last in-range index;
one-past-end vertex/index fetch; and signed base-vertex boundaries. Determine exactly which fields
are read at execution time and which are captured earlier by command processing.

For every record and buffer, document alignment, address width, record stride, maximum vertex/index/
instance/draw count, maximum reachable buffer range, largest legal value, first illegal value,
integer-overflow behavior, validation/fault behavior, and whether a large generated draw can be
split without changing primitive restart, primitive ID, instance ID, provoking vertex, or ordering.
Include direct and indirect multi-draw/count forms if the OpenGL path may expose them. This is the
executable finite-boundary closure of the broad `DRV-INDIRECT-01` item.

### GLPRE-A03 — Pre-raster special-output ABI and limits

What exact Apple9 vertex-output/PPP ABI carries every nonordinary varying produced by a VS, software
TES, or software-GS rasterization program?

At minimum map position, point size, clip distances, cull distances, layer, viewport index,
primitive ID where forwarded, and edge flag if the selected OpenGL profile exposes it. Decode their
UVS/export slots, component formats and widths, enable/count masks, required defaults, stage
restrictions, and any coupling to command state. Test omitted and partially written outputs,
dynamically indexed clip/cull arrays, NaN/infinity/signed-zero positions and point sizes, out-of-
range layer/viewport values, points/lines/triangles, provoking-vertex modes, and generated indirect
draws. Keep ordinary user varying capacity under `GLIO-A01`.

Establish exact maximum clip plus cull components, viewports, layers, point-size range, and every
finite export or command-state namespace involved. For each, test the largest legal and first
illegal value and distinguish clamping, clipping/culling, aliasing, rejection, discard, and fault.
Do not assume that a published OpenGL limit, a Metal validation limit, and raw hardware capacity are
identical.

### GLXFB-A01 — Compute-emulated transform-feedback ordering, counters, and exhaustion

Are Apple9's documented global-memory, atomic, query, and generated-draw primitives sufficient to
implement OpenGL transform feedback with exact observable behavior using Mesa's software `poly`
path?

Using minimal experimental programs rather than production driver code, validate independent and
interleaved capture into all four OpenGL transform-feedback buffers and all four vertex streams,
including separate and interleaved layouts, arbitrary legal component offsets/strides, multiple
outputs per buffer, rasterizer discard, a passthrough shader when no application GS is present, and
a multistream GS-shaped producer. Verify that capacity is restricted to complete primitives across
every buffer used by a stream and that an undersized buffer never receives a partial primitive.

Exercise begin/end, pause/resume, rebinding, consecutive draws, indexed/restarted input, generated
geometry, transform-feedback draw/replay, primitives-written/generated queries, stream-specific
queries, and overflow/any-overflow queries where exposed. Document the exact widths, alignments,
atomicity, visibility, accumulation and wrap rules of buffer offsets and query counters; maximum
buffer range/stride/offset; first overflowing address or counter; behavior when one stream or buffer
fills before another; and every synchronization step. Distinguish the API-fixed four-stream/four-
buffer model from any lower hardware descriptor, address, atomic, query-slot, or generated-command
limit. Cross-reference `DRV-QUERY-01`, `DRV-MEM-01`, and `GLPRE-A01` rather than treating a successful
global store as end-to-end closure.

## OpenGL storage-image questions

These concern NIR image operations, not sampled textures. Reuse answers from `DRV-FMT-01`,
`DRV-TEX-01`, `DRV-MEM-01`, `DRV-ROBUST-01`, and `ATOM-*`, but provide the missing compiler-facing
operation and resource-selection contract explicitly.

### GLIMG-A01 — Complete image load/store/query operation and coordinate matrix

What is the complete Apple9 encoding and runtime behavior of NIR image load, image store, image size,
and image sample-count operations for every OpenGL-required image dimension and format class?

Cover 1D, 1D array, 2D, 2D array, 3D, cube, cube array, buffer, 2D multisample, and multisample-array
forms wherever OpenGL permits them. Decode handle/selector, coordinates, layer/face, mip, sample,
component mask, source/destination registers, format/type, cache/coherency modifiers, instruction
length, and every reserved field. Establish which operations use texture hardware, a PBE/image-store
path, ordinary buffer memory, or required lowering, without inferring equivalence from a sampled-
texture opcode.

For every advertised format, use `DRV-FMT-01` as the conversion authority but execute representative
float, signed-integer, unsigned-integer, normalized, packed, RGB32, depth/stencil, and multisample
accesses through the actual image instruction path. Test last and first invalid coordinates, layers,
mips, samples, buffer elements, misalignment, partial vector writes, inactive components, unbound
images, and read/write aliasing. Record zero/discard/clamp/alias/fault behavior separately from API
robustness lowering and state exactly which invalid cases the later compiler or driver must guard.

### GLIMG-A02 — Image selector/descriptor capacity and atomic integration

How are bindful, dynamically indexed, non-uniform, and bindless OpenGL images represented on
Apple9, and what finite resource namespaces does one logical image consume?

Determine whether an image consumes one or more texture, PBE, buffer-base, metadata, sampler, or
argument-table entries for load, store, and atomic access; whether read/write/atomic views share an
entry; all selector and handle encodings; required descriptor adjacency/alignment; and whether
different lanes may select different images. Measure the maximum simultaneously usable images for
each access mixture, the largest legal selector, first illegal selector, unpopulated/destroyed-entry
behavior, allocation lifetime/reuse rules, and what happens when a shader requires more entries than
each direct namespace provides. Document the exact bindless or software fallback rather than merely
reporting a field width.

For image atomics, map every OpenGL-required operation and format to the native device-atomic or
software path, including return value, compare-exchange operands, address derivation, alignment,
scope, ordering, helper-lane behavior, and format metadata. Cross-reference `ATOM-01` through
`ATOM-11`; this item must identify how a texel becomes the atomic address and how the image resource
is selected, which the generic atomic questions do not establish.

## Missing OpenGL texture questions

### GLTEX-A01 — Exact bias operand and effective-LOD semantics

What is the complete Apple9 encoding and runtime behavior of a dynamic texture bias operand?

Document its register packing, bit width, numeric type, precision, signed range, and all instruction
fields. Test the complete interaction among:

- the shader-supplied bias operand;
- OpenGL sampler-object LOD bias supplied separately by the driver;
- sampler minimum/maximum LOD;
- texture base/max levels and mip count;
- implicit fragment LOD;
- 1D, 2D, 3D, array, cube, cube-array, shadow-compare, projected, and offset forms.

Test zero, signed zero, ordinary positive and negative values, the advertised OpenGL endpoints,
the first values outside them, very large magnitudes, infinity, and NaN. State exactly where
addition, clamping, and quantization occur. The existing `TEX-05`, `TEX-24`, and `TEX-27` questions
cover minimum LOD and LOD bounds, but not the bias operand or the ordering of these operations.

### GLTEX-A02 — Exact explicit-gradient ABI, especially cube gradients

What is the complete register ABI and instruction encoding for explicit gradients (`txd` /
`textureGrad`) for every OpenGL texture dimension?

Document component order, register count, bit width, precision, array-layer exclusion, cube/cube-
array interpretation, shadow comparison, constant offset interaction, and any operand alignment or
consecutive-register rule. Test independent X/Y gradients rather than compiler-generated symmetric
cases. Include zero, subnormal, large, negative, infinity, and NaN components.

For cube and cube-array textures, compare native Apple9 results against an independently calculated
OpenGL reference across face boundaries and major-axis ties. Explicitly decide whether the existing
Mesa `lower_txd_cube_map` path must remain the correctness path. `TEX-05` mentions gradients only in
combination with dynamic minimum LOD and does not answer this question.

### GLTEX-A03 — Fragment implicit LOD and `textureQueryLOD`

Does Apple9's implicit-LOD sample and its clamped/unclamped LOD-query form implement the exact
OpenGL results in a real fragment shader?

Test varying gradients, minification and magnification, mip transitions, sampler bias, sampler LOD
clamps, texture base/max levels, incomplete mip chains where constructible, anisotropy, helper
invocations, divergent control flow, and primitive edges. For `textureQueryLOD`, document which
result component is unclamped and which is implementation-clamped, and exactly which bias/clamp
operations are reflected in each component.

Cross-reference `FS-04` through `FS-06` for raw derivative behavior, but record texture-unit LOD
selection and query results separately. The current questionnaire tests derivatives and extreme
explicit LOD values, not the final implicit/query LOD semantics.

### GLTEX-A04 — Array-layer conversion and extra-coordinate packing

For every sampled, gathered, compared, and fetched array/cube-array/MSAA form, what is the exact
Apple9 representation and interpretation of the extra coordinate or index?

Decode all co-varying `op+3` and companion fields and test every register boundary they can encode.
For floating-point sampled array layers, determine the exact conversion rule for integer, half-way,
fractional, negative, signed-zero, infinity, and NaN inputs, followed separately by the clamping or
out-of-range rule. Test the first and last legal layer and the first illegal layer for every
advertised array limit.

`TEX-13` covers out-of-range integer layers and `TEX-23` covers the object-size limit, but neither
defines floating layer conversion nor closes the extra-coordinate operand encoding noted as partial
in `EXP-0034`.

### GLTEX-A05 — Complete native 1D and 1D-array operation matrix

Do native Apple9 1D and 1D-array descriptors work for every OpenGL operation without the existing
Mesa 1D-to-2D lowering?

Execute and document implicit sample, bias, explicit LOD, explicit gradient, projective sample,
fetch, size/level query, single offset, four gather offsets where applicable, shadow comparison,
image load/store, and mipmapped minification. Test normalized coordinates and all applicable address
modes at both ends of the image. Record the descriptor type, instruction dimension fields, coordinate
packing, layout, mip offsets, and maximum legal size.

The descriptor type and layout are documented, but the current `TEX-*` questions do not establish
the complete executable operation matrix. A negative answer is acceptable and documents that
Mesa's existing 1D-to-2D lowering remains necessary.

### GLTEX-A06 — Complete shadow/cube/cube-array operation matrix

Are depth comparison and gather-compare forms executable and exact for 2D array, cube, and cube-
array textures with implicit LOD, explicit LOD, bias, gradients, and offsets wherever OpenGL exposes
the combination?

Test all eight comparison functions, nearest and linear PCF, every cube face, face boundaries,
array-layer boundaries, and both ordinary preset borders and arbitrary-border emulation inputs.
Document the complete compare-reference and extra-coordinate packing rather than relying on byte
diffs. Also record whether compare filtering and ordinary filtering select identical footprints and
LOD when their results are used to reconstruct an arbitrary shadow border.

`TEX-11` asks whether arbitrary shadow borders can be emulated, and `DRV-TEX-01` asks for cube seams,
but the current questionnaire does not ask for this complete executable opcode/dimension matrix.

### GLTEX-A07 — Texel-buffer length, range, offset, and exhaustion semantics

What is the largest texel buffer Apple9 can address for every OpenGL-required texel size and format,
and how is that limit represented?

Determine whether the native linear/texture-buffer descriptor can exceed the ordinary 1D dimension,
or whether a 2D remap like current Asahi is required. Exhaustively document:

- descriptor width/height/stride/length fields and their exact finite ranges;
- base-address and texture-buffer-range offset alignment;
- maximum element count for 1-, 2-, 4-, 8-, 12-, and 16-byte texels;
- the largest legal offset-plus-length and the first overflowing combination;
- fetch behavior at the last legal element, one-past-end, unbound, and malformed lengths;
- whether RGB32 changes addressing, alignment, bounds, or robustness behavior.

Separate API validation, descriptor packing overflow, raw hardware behavior, and VM fault behavior.
`TEX-09` asks only about RGB32 format availability, while `TEX-23` asks ordinary texture dimensions;
neither establishes the OpenGL `GL_MAX_TEXTURE_BUFFER_SIZE` contract or range-alignment boundary.
