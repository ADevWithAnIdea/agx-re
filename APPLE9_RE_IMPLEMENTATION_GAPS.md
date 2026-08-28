# Apple9 Reverse-Engineering Handoff: Implementation Gaps and Hardware Questions

Status: consolidated RE worklist — **the authoritative task list** for a complete M4 / A18 Pro
Mesa userspace driver and its shader compiler. This document supersedes
`AGX_RE_INFORMATION_GAPS.md` (the 2026-08-17 audit; removed from the tree, retained in git
history). Process rules for working an item live in `CODEX.md`; the per-row closure status
board is `docs/P0-P1-CLOSURE.md`.

Initial coverage-audit date: 2026-08-17. Compiler/texture questionnaire updated: 2026-08-27.

Audited baseline revisions:

- `agx-re`: `30e3d6a226a560314cb4f707e227c21c53dcdb23`
- upstream `mesa`: `3c4d3e46d19f2f4e951f3ae059543b03592f7944`

Re-check the repository before starting each item: another experiment may have closed a gap after
the audited baseline. A later document or a Metal compiler byte diff is not sufficient by itself;
record the executable artifact that closes the item.

## Verdict and target

The current RE is broad enough for research bring-up, disassembly, descriptor/layout work, simple
compute, and a constrained graphics path. It is not yet sufficient to synthesize a complete,
conformant Apple9 userspace driver using the **exact existing Asahi UAPI**, or to compile every
supported portable NIR program independently of Apple-generated instruction templates.

The discovery target is both:

1. a complete factual specification of the hardware-dependent information a later M4/G16G and
   A18 Pro/G17P userspace implementation will require, under the unchanged Asahi UAPI; and
2. a compiler-ready Apple9 instruction/ABI specification from which a separate implementation agent
   can later map portable NIR to machine code.

`APPLE9_COMPILER_DESIGN.md` (a separate deliverable, not part of this repository) records compiler
design decisions. This document records only missing facts, tests, and closure conditions. If
evidence changes a design decision, report the evidence here and update the design document
separately.

## Assignment boundary: discovery and documentation only

This is **not an implementation assignment**. The RE agent owns discovery, falsification, raw
evidence, and precise documentation. The compiler/driver implementation belongs to a separate agent.

In scope:

- inspect existing code, captures, experiments, public specifications, and current documentation;
- design and run narrowly scoped hardware experiments that isolate one fact or boundary;
- write the smallest disposable probe, own-MSL kernel, byte-splice, descriptor injection, or analysis
  script necessary to obtain evidence when existing tooling cannot express the test;
- preserve raw inputs/outputs and document exact encodings, semantics, limits, invalid behavior,
  confidence level, chip/OS/compiler version, and remaining counterexamples;
- state the consequence for a future compiler/driver and identify the kind of fallback it will need,
  without implementing that fallback.

Out of scope:

- implementing or modifying the production Mesa userspace driver, shader compiler, Apple9 IR,
  optimizer, legalizer, scheduler, register allocator, linker, command builder, or kernel driver;
- building a production assembler/disassembler, XML generator, command packer, metadata writer,
  descriptor allocator, helper allocator, epilog generator, or software-emulation library;
- changing the Asahi UAPI, adding production ioctls, or making architectural design decisions on
  behalf of the implementation agent;
- turning a recovered algorithm into shipping code. The deliverable is the tested semantic
  specification and raw evidence needed for someone else to do that work.

Experimental code is evidence scaffolding only. Keep it isolated in the relevant experiment, avoid
production-tree changes, and stop once the hardware fact is established. If an item would require a
substantial implementation merely to test it, document the missing experiment/tooling and the exact
question it must answer instead of implementing the subsystem.

## Scope and priorities

Mesa-independent algorithms already available upstream are not RE gaps. Hardware formats, ABIs,
limits, instruction semantics, command packing, and the mapping to the current Linux UAPI are.

- **P0:** blocks the initial compiler contract, complete driver bring-up, or unchanged-UAPI
  compatibility.
- **P1:** blocks conformance, broad feature coverage, or a compiler path we expect to ship.
- **P2:** optional native feature, performance work, or safely deferrable coverage.

Native compression, tessellation, mesh shading, and ray tracing may remain P2 if they are disabled,
not advertised, or use an already available Mesa emulation path. A missing hard resource limit or
unknown overflow behavior is never merely a performance issue.

## Non-negotiable finite-resource mandate

**Anything finite is an incomplete RE result until both its exact usable capacity and its exhaustion
semantics are known.** A bit-field width, the largest value Apple happened to emit, a Metal feature-
set limit, or one successful stress test is not by itself a hardware-capacity result.

For every finite field, table, heap, register file, namespace, nesting stack, address range, program
extent, and resource count, the RE agent must establish all of the following separately:

1. **Representation:** field width, units, scale/bias, signedness, inclusive/exclusive interpretation,
   sentinel values, reserved encodings, holes, aliases, and chip/stage-specific reservations.
2. **Usable capacity:** exact minimum and maximum legal values, whether the maximum is a count or an
   index, whether capacity is per instruction, shader, stage, pipeline, command, queue, VM, core, or
   device, and whether other enabled features reduce it.
3. **First failure:** test the maximum legal case and the first illegal case. For non-contiguous
   namespaces, test every value or every equivalence class and all boundaries—not just powers of two.
4. **Exhaustion behavior:** distinguish frontend/compiler rejection, API object-creation failure,
   driver allocation failure, fallback to another hardware path, zero/discard, clamp/saturate,
   wrap/alias, partial completion, recoverable command error, GPU fault, and device loss.
5. **“Need more” strategy:** document the correctness-preserving response available to a future
   compiler/driver: spill, recompute, materialize, indirect/bindless access, trampoline, split a
   command/pass/allocation, software emulation, advertise a smaller limit, or reject the operation.
   Establish whether the required hardware mechanism exists and what semantics it has. Do not
   implement the fallback as part of this assignment.
6. **Lifetime and reuse:** determine when an entry may be freed/reused, whether IDs are generation-
   tagged, what happens to stale references, and whether simultaneous users compete for one global
   capacity.

Every completed finite-resource item must add a row to a result table with this schema:

| Namespace/resource | Scope | Encoding | Exact usable range/count | Holes/reserved | First invalid value | Observed failure | Correct “need more” fallback | Evidence |
|---|---|---|---:|---|---:|---|---|---|

At minimum, inventory and close these finite Apple9 resources:

- GPRs, register pairs, packed halves, predicates, execution-mask/reconvergence depth, call depth,
  stack frames, spill/scratch bytes, uniform registers/preloads, immediates, branch reach, instruction
  length, shader/code-block size, and occupancy tiers;
- buffer base slots, texture selectors, sampler selectors, bindless texture entries, sampler resource
  IDs, descriptor sets/arrays, resource-table bytes, high-register addressing, and every invalid or
  destroyed-resource reference;
- texture dimensions, array/depth layers, mip levels, sample counts/indices, texel offsets, LOD
  fields, anisotropy, address/border/swizzle/filter codes, buffer-texture lengths, row/layer pitches,
  sparse tiles/mip tails, and format/component fields;
- shader inputs/outputs, varyings/interpolation coefficients, render targets, color attachments,
  viewports, scissors, depth-bias entries, sample positions, push/uniform data, shared/threadgroup
  memory, tile memory, workgroup sizes/counts, subgroup width, and helper invocations;
- helper scratch blocks/buckets per core, sampler/global heaps, query/occlusion slots, timestamp range
  and wrap, VM ranges, the 4 GiB USC window, executable allocations, BO sizes/alignments, queue and
  command counts, command-stream segment size/link depth, draw/dispatch/count-buffer fields, indirect
  parameter ranges, tile/parameter-buffer budgets, and partial-render storage;
- every PBE, ZLS, PPP, USC, VDM, CDM, descriptor, metadata, or UAPI count/size/offset field even when
  its encoded bit width appears obvious.

The required driver behavior is normally conservative: use a proven wider/indirect path or expose a
smaller verified limit; otherwise reject before emitting invalid machine state. Raw invalid behavior
must still be recorded safely because it determines robustness and fault containment, but it is not
a spill strategy.

## Required response format

Copy this block under every numbered item that is investigated:

```text
Status: [ ] Open  [ ] Partial  [ ] Closed  [ ] Not applicable
Answer, where Yes/No: [ ] Yes  [ ] No  [ ] Unknown
Applies to: [ ] A18 Pro/G17P  [ ] M4/G16G  [ ] both tested independently
Evidence: [ ] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact:
Exact observed semantics or field mapping:
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
Maximum-valid and first-invalid tests:
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more:
Lifetime, destruction, and reuse semantics:
Counterexamples and untested cases:
Driver/compiler consequence:
```

Rules for closing an item:

1. Metal compiler output may locate an encoding or suggest a lowering, but cannot prove execution
   semantics.
2. Tokenization and byte-exact round trip prove instruction boundaries and preservation of observed
   bytes, not that arbitrary semantic operands can be encoded.
3. A claimed operation requires independently assembled or modified code to execute, unless the
   item explicitly asks only for a captured field or userspace structure.
4. Record chip, OS, Metal compiler version, harness commit, raw inputs, and raw outputs. Do not
   silently generalize A18 evidence to M4.
5. Numerical tests require raw bit patterns and exceptional values. Memory-model tests require
   concurrent litmus tests, not single-thread functional output.
6. Every finite namespace requires its exact maximum, all holes/reservations, the first invalid
   value, API behavior at exhaustion, and raw hardware behavior where safely testable.
7. An opcode specification is compiler-ready only when registers/files, widths, modifiers,
   immediates, length,
   reserved bits, side effects, and scheduling/ordering restrictions are known.
8. Distinguish hardware/firmware ABI from Apple Metal userspace bookkeeping and macOS-private
   kernel interfaces.

# Part I — Full userspace-driver information gaps

## Areas already covered well enough to retain

Do not restart these areas from zero; extend or falsify the existing evidence:

- G17P and G16G identity/topology, 16 KiB page size, core-count delta, and shared Apple9 family.
- Basic ALU, load/store, control flow, subgroup, atomic, texture, special-register, 96-GPR, packed-
  half, and hardware-dependency-interlock discoveries.
- Many direct compute/draw fields, indexed draw, primitive, viewport, clip, sample-count, occlusion,
  and stage-timestamp observations.
- Broad sampled-texture, PBE, and sampler descriptor maps; many format codes; argument-buffer and
  sampler-heap observations.
- Uncompressed texture tiling, non-power-of-two padding, array/cube/3D planes, block formats, mip
  tails, and MSAA sample-minor layout.
- Depth/stencil/raster field locations, MRT placement, attachment-format derivation, fixed 32x32
  raster tiles, memoryless observations, and programmable sample-position data.

These are evidence bases, not blanket closure: their synthesis fields, limits, and edge behavior
remain covered by the questions below.

## P0 — Existing-UAPI and end-to-end submission blockers

### DRV-UAPI-01 — Userspace scratch/helper protocol

The current UAPI requires userspace-provided VS, FS, and CS helper programs, tagged binary pointers,
configuration, and scratch-allocator data. Current Mesa constructs the scratch BO in userspace, while
parts of `agx-re` incorrectly assign this work to the kernel.

Required closure:

- Recover and document enough Apple9 helper semantics to exercise VS, FS, CS, and preamble scratch
  with a minimal experimental probe; do not implement the production helper allocator/program.
- Decode helper next/ack/nack/doorbell operations, special registers, and the ABI receiving
  `drm_asahi_helper_program.data`.
- Map every `binary` tag and `cfg` bit for helpers, main shaders, and preambles.
- Specify scratch header, per-core block lists, block descriptors, alignment/address shifts,
  allocation buckets, maximum active subgroups, block sizes/counts, and topology-to-helper-core IDs.
- Establish reset, growth, concurrency, allocation failure, and device-loss behavior.
- Demonstrate an unchanged-UAPI Linux spill test for VS, FS, and CS on both target chips.

### DRV-UAPI-02 — Graphics shader selection and code-BO handoff

Captured Metal draws use a self-describing code BO but expose no obvious shader pointer. The current
Linux UAPI has no per-render code-BO-base field; it has queue-wide `usc_exec_base`.

Required closure:

- Determine whether the captured code BO maps to `usc_exec_base`, another existing field, or
  Metal-only bookkeeping.
- Select among multiple coexisting VS/FS pipelines within the 4 GiB USC window without a new field.
- Specify sized-code-block headers, alignment, stage/type identity, ordering, relocations, entry
  selection, and termination.
- Explain how prologs, main shaders, epilogs, helpers, and multiple pipelines are addressed.
- Demonstrate pipeline switching end-to-end using only the existing UAPI.

### DRV-UAPI-03 — Field-by-field Apple9 mapping of existing render/compute commands

For every field in `include/drm-uapi/asahi_drm.h`, document:

```text
userspace derivation -> UAPI value -> kernel/firmware marshaling -> observed Apple9 behavior
```

Unclosed high-risk fields include `zls_ctrl`, `isp_zls_pixels`, depth/stencil bases and compression
strides, `ppp_ctrl`, `ppp_multisamplectl`, scissor/depth-bias/occlusion bases and array formats,
scratch/empty-tile/no-clustering/integer-depth-bias flags, sampler-heap base/count, control-stream end,
stage timestamp frequency/units, and all reserved/tag bits. Prove how the captured sample-position BO
maps to mandatory UAPI sample control rather than assuming an additional submit parameter.

### DRV-UAPI-04 — BG/EOT and partial-render programs

The UAPI requires BG, EOT, partial BG, and partial EOT program records. Close all of:

- shader ABI, invocation, tilebuffer address, sample/layer inputs and outputs;
- clear/load/resolve/store/depth/stencil/partial-save/partial-restore sequences;
- resource-specifier fields, USC binding tags, and program-pointer tags;
- pack/unpack, sRGB/integer/normalized conversion, write masks, and resolve rules;
- overflow/partial-render state contract and empty-tile requirements;
- memoryless, MRT, layered, mixed-format, depth-only, stencil-only, discard, and load/store/dont-care
  combinations.

### DRV-CMD-01 — Relocatable Apple9 command/state schemas

Document a bit-exact schema for every userspace-emitted VDM, CDM, PPP, USC, ZLS, and command-register
structure, backed by isolated parameter changes and execution evidence. Production schema generators,
packers, and command builders are out of scope. Required coverage includes:

- packet/block types, lengths, alignment, reserved bits, legal ordering, links/calls/returns,
  barriers, and termination;
- absolute, shifted, split, queue-relative, stage-relative, and firmware-private relocations;
- arbitrary uniform/resource bindings, textures, samplers, shared memory, preambles, and fragment
  properties;
- cache/coherency controls and compute/tiler/fragment/texture/PBE/CPU transitions;
- stream size/chaining/pool-rollover limits and multi-draw/multi-dispatch behavior;
- repeated draws with partial state changes, pipeline switches, mixed compute/render, and multiple
  commands per submit.

Fixed-VA captured templates do not close this item.

### DRV-ISA-01 — Compiler-ready ISA specification

Part II is the detailed closure list. In addition, document a semantic opcode/property table with
operand/result types, side effects, eliminability, reorderability, execution class, control-flow
behavior, scheduling restrictions, length selection, and reserved bits. Every initial compiler
family must be independently encoded and executed across its legal register range using existing
experimental tools or minimal probe scaffolding; raw template residue and catch-all length rules are
not acceptable. Implementing the production assembler or opcode database is out of scope.

### DRV-SHADER-01 — Shader container, program extent, metadata, and resource specifications

Determine which captured `__GPU_METADATA`/FlatBuffer records are firmware-consumed and which are
Metal archive data. Then specify the actual existing-UAPI representation of:

- entry point and authoritative program extent;
- GPR/uniform/texture/sampler/shared/tile/scratch usage;
- occupancy, preamble, stage properties, and resource specifiers;
- metadata versions/defaults/checksums/offsets if any captured schema is hardware-facing;
- construction of sized code blocks and uniform-preamble containers.

Document every field and construction rule sufficiently for a later writer/packer implementation.
Validate the specification by minimally constructing and launching experimental shaders without an
Apple-created archive where current tooling permits; do not implement the production writer/packer.

### DRV-ABI-01 — Complete stage ABI, shader linking, and programmable epilogs

Required closure:

- VS fetch/input ABI for all formats, instancing/divisors, base vertex/instance, and robustness.
- FS interpolation and system values: center/centroid/sample, perspective/noperspective/flat,
  coverage, sample mask, point coordinates, primitive/layer/viewport IDs, helpers, and barycentrics.
- FS outputs: color, dual source, depth, stencil, sample mask, discard/demote, and side-effect order.
- CS system values, dynamic shared memory, direct/indirect dispatch, and preamble ABI.
- Prolog/main/epilog live-ins/outs, calls/branches, register allocation, and resource merging.
- Tilebuffer ABI shared by FS, programmable blend, BG, and EOT.
- Recovered and experimentally validated blend/logic/format-conversion semantics for all advertised
  factors, operations, RGB/alpha separation, dual source, write masks, constants, alpha-to-coverage/
  one, min/max, sRGB, normalized/integer/float conversion, NaNs, and MSAA/sample masks. Specify what
  a future epilog generator must emit; do not implement that generator.

## P1 — Correctness and broad feature coverage

### DRV-PBE-01 — Complete PBE and attachment structures

Decode every field in the storage/PBE descriptor and three load/render/store attachment segments:
type/layer/mip/sample/array selection, component mapping, access/control, rotation/mode, coherency,
reserved values, program ID ownership, per-layer/mip/resolve offsets and strides, memoryless,
compression, depth/stencil, mixed MRT, and every load/store/clear/resolve combination.

### DRV-FMT-01 — Per-format capability and conversion table

For every exposed format, test sampled, filtered, storage read/write, atomic, renderable, blendable,
depth/stencil, linear, compressed, MSAA, resolve, sparse, row/layer/depth pitch, mip offset, buffer-
texture, swizzle, normalization, rounding, and pack/unpack behavior. Include RGB32, packed, sRGB
storage, integer filtering, split depth/stencil aspects, YUV, BC/ASTC/ETC/EAC, and any PVRTC exposure.

### DRV-TEX-01 — Texture/image synthesis and edge behavior

Part II `TEX-*` is authoritative for texture instruction semantics and finite selector limits. Also
document format-dependent image atomics, PBE/texture coherency, cube seams, unnormalized coordinates,
and all descriptor-table construction rules a later userspace driver will require.

### DRV-MEM-01 — API memory model and synchronization

Map hardware caches and visibility among USC, texture, PBE, tile memory, tiler, fragment, compute,
and host. Provide litmus tests and required barriers/flushes/invalidates for every producer/consumer
pair, device/workgroup/subgroup/invocation scopes, acquire/release/relaxed/seq-cst behavior, atomic
ordering, cross-queue synchronization, UAPI `vdm_barrier`/`cdm_barrier`, host mapping, and cache
maintenance. Part II `MEM-*` and `ATOM-*` cover the shader-facing subset.

### DRV-ROBUST-01 — Robustness, VM conventions, and sparse residency

Establish G16/G17 `vm_start`, `vm_end`, kernel reservation, shader-window limits, chip/revision/feature
parameters, timestamp frequency, BO alignment/protection/sharing/device-address rules, zero/guard/
scratch pages, buffer/image OOB behavior, soft faults, and maximum load shifts. For sparse resources,
specify page-table and folio geometry, mapping granularity, mip tails, aliasing, residency return,
shadow mappings, and synchronization. A sparse descriptor flag and 16 KiB tile are not sufficient.

### DRV-QUERY-01 — Queries and timestamps

Specify counter-heap layout/alignment/limits, allocation, accumulation, reset, availability, copy,
simultaneous queries, precise stage placement, ordering, tick frequency, wrap, `GET_TIME` calibration,
conversion, and the semantics a later pipeline-statistics implementation or emulation must provide.

### DRV-INDIRECT-01 — Indirect and device-generated commands

Close global/local direct/indirect CDM modes, parameter-memory formats, multi-dispatch/draw links and
barriers, count buffers, indexed/non-indexed forms, base vertex/instance, restart and bounds rules,
writable device-generated command grammar, validation, cache flushes, and stream-limit behavior.

### DRV-RASTER-01 — Numerical, rasterization, and hard limits

Part II `FP-*`, `PACK-*`, `INT-*`, `TRIG-*`, and `SFU-*` are authoritative for shader arithmetic.
Also characterize line/point rasterization, provoking vertex, polygon modes, clip/clamp, depth bias,
conservative rasterization if exposed, coverage, centroid/sample interpolation, early/late depth and
stencil, helper/discard/demote, raster-order/interlock, and every advertised finite limit including
viewports, attachments, dimensions, layers, mips, workgroups, shared/tile memory, descriptors,
uniforms, alignments, and subgroup operations.

## P2 — Optional native features and performance

### DRV-P2-01 — Lossless compression

Decode the 8x4 codec, exact state meanings, MSAA auxiliary ratio, eligibility, placement, size, CPU
access, and interaction with PBE. It may remain disabled if every correctness path can do so.

### DRV-P2-02 — Native tessellation

Decode control-point/partition bits, patch records, factors, indirect modes, generated-buffer ABI,
barriers, domain/parameter buffers, and unchanged-UAPI ownership. Otherwise retain Mesa compute
emulation.

### DRV-P2-03 — Native mesh/object shading

Decode dispatch, object-to-mesh handoff, UVB/output layout and sizing, raster linkage, barriers,
indirect/ICB behavior, and allocation ownership. Otherwise do not expose it.

### DRV-P2-04 — Ray tracing and acceleration structures

Decode traversal operands plus BVH nodes, required userspace builder/reorder-stage contracts,
scratch, update, compaction, serialization, geometry/motion formats, and synchronization. The
unchanged UAPI has no BVH-build command, so firmware ownership cannot merely be assumed; building the
production BVH implementation is out of scope.

### DRV-P2-05 — Metal-unreachable encodings and performance model

Exhaust finite raw sampler/address/swizzle/border/aniso values, arbitrary restart and raster modes,
native geometry-shader/stream-output paths, and other Metal-unreachable descriptor/opcode values.
Then characterize occupancy curves, instruction latency/throughput, scheduling classes, cache
behavior, tile/parameter-buffer sizing, and workgroup repacking. Unknown hard resource capacities
must be promoted to P0/P1 even if the performance model remains deferred.

## Cross-cutting documentation, provenance, and licensing

### DOC-01 — Authoritative specifications and stale references

Fix broken `../mesa` references, mark historical/superseded facts non-normative, reconcile ROADMAP,
reviews, cmdstream open-items, sample positions, and tiling summaries, and document versioned bit-
exact schemas. In particular, bpp1 uses tile edge 128 despite stale `T=64 bpp<=4` wording.

### DOC-02 — Evidence classification

Every field must be labelled as hardware-run/splice, isolated byte diff, corpus correlation,
tokenization only, single-template inference, Metal API accept/reject, macOS/firmware-private, or
untested. Do not use “emittable” for a family whose arbitrary operands have not executed.

### DOC-03 — License/provenance path

`agx-re` code/data/XML is GPL-3.0 and prose is CC-BY-NC-SA-4.0, while upstream Mesa is predominantly
MIT. Before importing material, obtain relicensing/dual licensing, perform a deliberate clean-room
factual re-expression into MIT-compatible schemas/code, or establish a reviewed separation. Record
the provenance requirements for every table or implementation artifact a later agent may derive.

# Part II — Shader compiler hardware questionnaire

Every question below asks what a future portable-NIR-to-Apple9 compiler and assembler may rely on.
The deliverable is the tested fact and encoding documentation, not implementation of Apple9 IR or
compiler passes. `Unknown` is preferable to promoting compiler-output inference to hardware fact.

## P0 — Questions that gate the initial NIR contract

- **OPT-01 — Does preserving NIR `fdiv` allow Apple9 legalization to select two observably distinct
  hardware sequences for relaxed and precise division?**

  Compiler consequence: `Yes` confirms `.lower_fdiv = false`; `No` requires identifying the actual
  selection point before deciding where division may be lowered.

- **OPT-02 — Does precise FP32 division produce the correctly rounded result for all tested normal,
  subnormal, zero, infinite, NaN, overflow, and underflow cases?**

  Close with a directed edge-case suite plus a large randomized comparison against an exact FP32
  reference. Record rounding mode and denormal controls.

  > **Answered 2026-08-27 (EXP-0074, M4/G16G): No.** Plain `/` on `float`, runtime compile,
  > `fastMathEnabled=NO` / Safe math. 4171 cases (75 directed + 4096 LCG); 3956 bit-exact vs a
  > two-implementation cross-checked correctly-rounded binary32 reference (no binary64 paths).
  > Every divergence involves subnormal operands (DAZ) or subnormal correctly-rounded results
  > (FTZ); all normal/zero/inf/NaN/overflow/underflow-to-zero classes are bit-exact, including
  > the exact 2^128 overflow tie. FTZ proven independently of DAZ. A single DAZ+FTZ model
  > predicts 4171/4171 observations. All 58 NaN results are canonical quiet `0x7FC00000`;
  > payloads never propagate. Compiler consequence: `lower_fdiv` decisions cannot assume
  > IEEE-subnormal results from precise division on this path; subnormal-correct division needs
  > software assistance. Evidence: `experiments/EXP-0074-m4-fp32-division-precision/`
  > (HW-PROBE + OWN-SHADER + PUBLIC: authored MSL compiled and dispatched on real M4 silicon with bit-exact readback against an independently implemented correctly-rounded reference — not a spliced/independently-generated encoding, so not the top `HW-VALIDATED` tier; M4 target, no native/ISA/Linux/A18 claim).

- **OPT-03 — Does Apple9 power require a distinct special-case fixup beyond
  `exp2(y * log2(x))` for source-language `pow` semantics?**

  Compiler consequence: `Yes` confirms `.lower_fpow = false` and requires a target `A9_POW` pseudo.

- **OPT-04 — Is dynamic-exponent FP32 `ldexp(x, n)` a directly executable Apple9 instruction with
  completely decoded operands and result semantics?**

  Compiler consequence: `Yes` enables `.has_ldexp = true`. Test exponent boundaries, signed zero,
  subnormals, overflow, infinities, and NaNs.

- **OPT-05 — Can one Apple9 compare/select instruction choose between two arbitrary register values,
  rather than only materializing Boolean 0/1?**

  Compiler consequence: `Yes`, after all operand fields are decoded, enables
  `.has_fused_comp_and_csel = true`.

- **OPT-06 — Does the general compare/select form support FP32, signed I32, and unsigned I32 with all
  equality and relational conditions needed by NIR?**

- **OPT-07 — Can Apple9 directly read a varying/input whose slot is selected dynamically per lane?**

  Compiler consequence: determines the applicable bits of `support_indirect_inputs`.

- **OPT-08 — Can Apple9 directly write a varying/output whose slot is selected dynamically per
  lane?**

  Compiler consequence: determines the applicable bits of `support_indirect_outputs`.

- **OPT-09 — Does fragment discard on Apple9 have SPIR-V demote semantics, including continued
  helper-lane execution for derivatives and implicit-LOD texture operations?**

  Compiler consequence: `Yes` permits `.discard_is_demote = true`; `No` requires separate discard
  and demote lowerings.

- **OPT-10 — Does an ordinary aligned Apple9 memory load satisfy the atomic-load ordering and
  visibility requirements when surrounded by the appropriate Apple9 fences?**

- **OPT-11 — Does an ordinary aligned Apple9 memory store satisfy atomic-store ordering and
  visibility requirements when surrounded by the appropriate Apple9 fences?**

  Compiler consequence of OPT-10 and OPT-11 together: only two `Yes` answers permit
  `.has_atomic_load_store = true`.

## P0 — Packed conversion and narrow arithmetic

- **PACK-01 — Is `pack_half_2x16` implementable by a fully decoded Apple9 native conversion/pack
  sequence without generic integer bitfield lowering?**

- **PACK-02 — Is `unpack_half_2x16` implementable by a fully decoded Apple9 native unpack/conversion
  sequence?**

- **PACK-03 — Is `pack_snorm_2x16` a member of the native `0x97` pack-convert family?**

- **PACK-04 — Is `unpack_snorm_2x16` a member of the native `0x17` unpack-convert family for all
  input bit patterns?**

- **PACK-05 — Does native `pack_unorm_2x16` match NIR rounding, clamping, NaN, and infinity semantics
  for all boundary cases?**

- **PACK-06 — Does native `unpack_unorm_2x16` exactly match NIR for every 16-bit lane value?**

- **PACK-07 — Does Apple9 have a native `pack_32_4x8` or equivalent four-lane format-conversion
  operation?**

- **PACK-08 — Does Apple9 have native UNORM and SNORM 4x8 unpack operations?**

  Compiler consequence: PACK-07/08 determine the four current `lower_*_4x8` settings and whether
  `.has_pack_32_4x8` can be advertised.

- **PACK-09 — Does one FP16 `vec2` add, multiply, or FMA instruction execute both packed lanes with
  independent lane-correct exceptional-value behavior?**

- **PACK-10 — Are packed FP16 lane results independent when one lane contains NaN, infinity,
  subnormal, or a signed zero?**

  Compiler consequence: PACK-09/10 close the correctness side of `.vectorize_vec2_16bit = true`.

- **PACK-11 — Is packed integer `short2` ALU absent for every tested integer add/multiply/logic
  form?**

  A `Yes` confirms that the FP16 vectorizer must never generalize to 2x16 integer operations.

## P0 — Floating-point ALU semantics

- **FP-01 — Is FP32 FMA genuinely fused, with a single final rounding and no intermediate product
  rounding?**

- **FP-02 — Is FP16 FMA genuinely fused at FP16 precision for both scalar and packed-half forms?**

- **FP-03 — Does the FP32 source-negate modifier implement `a - b` for every source class and
  register form supported by fadd?**

- **FP-04 — Do Apple9 FP32 min/max instructions match NIR's required signed-zero choice for
  `+0.0` versus `-0.0`?**

  Compiler consequence: determines whether `lower_fminmax_signed_zero` remains necessary.

- **FP-05 — Do Apple9 FP32 min/max instructions implement the exact NaN behavior required by the
  NIR min/max op selected by the frontend?**

  Record one-NaN, two-NaN, signaling/quiet payload, and operand-order cases.

- **FP-06 — Does Apple9 preserve FP32 input and output subnormals in the default graphics compute
  mode?**

- **FP-07 — Can FP32 denormal behavior be selected per shader or instruction, rather than being a
  fixed device mode?**

- **FP-08 — Does Apple9 preserve FP16 input and output subnormals in scalar and packed modes?**

- **FP-09 — Does the saturate modifier exactly implement the NIR/API clamp contract for NaN and
  signed-zero inputs?**

- **FP-10 — Does FP32-to-FP16 conversion use round-to-nearest-even in the mode intended for
  `pack_half_2x16`?**

- **FP-11 — Does FP32-to-integer conversion truncate toward zero for every signed/unsigned boundary
  and exceptional input?**

- **FP-12 — Does any Apple9 conversion form directly implement NIR saturating float-to-integer
  conversion?**

  Compiler consequence: determines `.has_f2i_sat` and `.has_f2u_sat`.

- **FP-13 — Can `fquantize2f16` be implemented by native narrow-then-widen conversions with exactly
  the SPIR-V/NIR zero, subnormal, infinity, and NaN behavior?**

- **FP-14 — Do FP32 comparisons expose ordered and unordered NaN conditions sufficient to implement
  NIR `ford`, `funord`, and unordered relational forms directly?**

  Compiler consequence: determines `has_ford_funord` and `has_fneo_fcmpu`.

## P0 — Integer, bitfield, and select semantics

- **INT-01 — Does native unsigned bitfield extract return zero when the requested width is zero?**

- **INT-02 — Does native unsigned bitfield extract match NIR for offsets and widths at and beyond the
  32-bit boundary after applying NIR's required masking/clamping?**

- **INT-03 — Is signed bitfield extract always native unsigned extract followed by an explicit sign
  extension, with no hidden signed mode?**

- **INT-04 — Does immediate rotate implement every amount modulo 32, including 0, 31, 32, and values
  greater than 32?**

- **INT-05 — Does the dynamic rotate expansion implement the same modulo-32 semantics for all
  runtime amounts?**

- **INT-06 — Is there no one-instruction dynamic rotate form?**

  Compiler consequence: INT-04 through INT-06 define legalization of preserved NIR `urol`/`uror`.

- **INT-07 — Does native 32-bit IMAD wrap modulo 2^32 exactly like NIR integer multiply-add?**

- **INT-08 — Can all three IMAD sources be arbitrary GPRs over the complete usable 96-register
  range?**

- **INT-09 — Does the native find-MSB primitive return the highest set-bit index, with
  `0x80000000 -> 31`, `1 -> 0`, and zero handled as required by NIR `ufind_msb`?**

  Compiler consequence: a `Yes` confirms that it is not NIR `ufind_msb_rev`.

- **INT-10 — Is CLZ necessarily a compound sequence rather than a separate single instruction?**

- **INT-11 — Is bitfield insert necessarily a mask/shift/combine sequence rather than a separate
  single instruction?**

- **INT-12 — Can the full integer logic-LUT encoding realize all 16 two-input Boolean functions for
  arbitrary GPR operands?**

- **INT-13 — Does the carry-generate operation require a particular immediately preceding add or
  implicit machine state?**

- **INT-14 — Can carry-generate be emitted as a self-contained operation with explicit source
  operands?**

  These answers decide whether NIR carry should remain generically lowered or become an Apple9 IR
  pseudo.

## P0 — 64-bit integer behavior

- **I64-01 — Does one register-pair instruction perform a complete 64-bit add with carry across the
  low/high word boundary?**

- **I64-02 — Does one register-pair instruction perform a complete 64-bit subtract with borrow across
  the low/high word boundary?**

- **I64-03 — Do native 64-bit add/sub work for every legal aligned and unaligned GPR-pair placement
  permitted by the encoding?**

- **I64-04 — Is 32x32-to-64 multiplication a single instruction for both signed and unsigned
  interpretations?**

- **I64-05 — Is there no native 64x64-to-low64 multiplication instruction?**

- **I64-06 — Are all 64-bit compare, shift, min/max, bit-scan, and general select operations compound
  sequences rather than native register-pair operations?**

  These answers validate the current `lower_int64_options` mask instead of merely inheriting it.

## P0 — Memory addressing and robustness

- **MEM-01 — Does `device_load/store` interpret its GPR index as an element index scaled by the
  encoded element size?**

- **MEM-02 — Is the in-instruction immediate offset added in element units rather than bytes?**

- **MEM-03 — Is the complete signedness and legal range of the immediate element offset known and
  hardware-validated?**

- **MEM-04 — Can `device_load/store` directly encode `base + index * stride + offset` for arbitrary
  vertex strides?**

  Compiler consequence: a `No` means arbitrary stride multiplication belongs in ALU/IMAD before the
  memory instruction and weakens the old `has_amul` rationale.

- **MEM-05 — Does 32-bit address/index arithmetic wrap in exactly the way required for legal NIR
  buffer offsets?**

- **MEM-06 — Are unaligned 8-, 16-, 32-, 64-, and 128-bit device loads supported without faults or
  byte corruption?**

- **MEM-07 — Are unaligned 8-, 16-, 32-, 64-, and 128-bit device stores supported without adjacent
  byte corruption?**

- **MEM-08 — Do out-of-allocation device-buffer reads return zero for every scalar/vector width and
  alignment that the compiler may emit?**

- **MEM-09 — Do reads that begin in-bounds but cross the allocation boundary return the API-required
  per-component result?**

- **MEM-10 — Are out-of-allocation device-buffer stores discarded without corrupting another
  allocation or faulting the context?**

  > **Answered 2026-08-27 (EXP-0076, M4/G16G): MEM-06 No · MEM-07 Yes · MEM-08 Yes · MEM-09 No
  > (mix model refuted) · MEM-10 Yes.** Two byte-identical runs, 212/212 executions clean. Unified
  > model with zero residuals: every access executes as independent units (8/16-bit = one unit;
  > 64-bit = two 32-bit units; 128-bit = four) and each unit's effective address is rounded DOWN
  > to its natural alignment (4 bytes for 32-bit units); in-allocation units access exact bytes,
  > units at/past the end read 0x00 / stores discard. Unaligned loads therefore do NOT return the
  > requested bytes (no fault); straddling reads return the aligned-down window's bytes with only
  > fully-OOB components zero; OOB atomic exchange reads 0. MEM-11: mechanism not identifiable
  > through public Metal (bounded behavior only). MEM-12 constraint: clamp byte addresses per
  > component BEFORE unit decomposition. Compiler consequence: unaligned NIR global accesses must
  > be decomposed; load_global_bounded may rely on zero-fill/discard for fully-OOB units.
  > Evidence: `experiments/EXP-0076-m4-buffer-robustness-matrix/` (HW-PROBE + OWN-SHADER; M4
  > target; no native/ISA/Linux/A18 claim).

- **MEM-11 — Is there no descriptor-level buffer bound available to a shader memory instruction?**

- **MEM-12 — Can `load_global_bounded` be implemented entirely in compiler-generated ALU/select code
  with exact robust-buffer semantics for vectors and boundary-straddling accesses?**

- **MEM-13 — Does the hardware guarantee dependency interlocking from every load/texture/atomic
  result to a consuming ALU instruction without an explicit wait?**

- **MEM-14 — Does the same dependency interlock hold for stores and atomics whose source is produced
  immediately before the memory operation?**

- **MEM-15 — What is the maximum number of simultaneously usable device-buffer base slots for one
  Apple9 shader stage?**

  This must be answered by constructing a shader that independently reads distinguishable values
  through every slot up to the first failing slot. The 8-bit `base_slot` encoding and successful
  tests with 1/2/4/8 buffers do not establish the architectural capacity.

- **MEM-16 — Are all encoded `base_slot` values below that maximum independently selectable, with no
  aliasing, holes, or stage-specific reservations?**

  Test the complete claimed range, with particular attention to boundaries 7/8, 15/16, 31/32,
  63/64, 127/128, and 255. Record separately any values reserved for threadgroup or internal ABI
  use.

- **MEM-17 — Does accessing an unpopulated or out-of-range device-buffer base slot return zero,
  alias another slot, or fault the command/context?**

  Test load, store, and atomic operations separately. This is fault-containment information, not a
  license for the compiler to emit an invalid slot.

  > **Answered 2026-08-27 (EXP-0083, M4/G16G, commit `8d47a271`): MEM-15 partial · MEM-16 Yes for
  > 1..30, with a 7-bit selector · MEM-17 zero/mirror, never a fault.** Two byte-identical runs,
  > 351 cases each, zero faults in 702 executions.
  > **MEM-16:** the selector is effectively **7-bit** — slots 128..255 mirror 0..127 on every op
  > path (load/store/atomic), no third behavior across the full 0..255 sweep (buffer 1 is held by
  > slots [1,129], buffer 10 by [10,138], ...). No aliasing or holes among populated slots 1..30;
  > boundaries 7/8 and 15/16 clean. Slot 0 is a reservation candidate whose content is
  > pipeline-configuration dependent (constant-program hoisting -> P(5,0); no hoist -> plain
  > binding 0).
  > **MEM-15:** 31 simultaneously usable, independently-correct slots via direct binding. This is a
  > **direct-binding-population edge** (MSL `[[buffer(N)]]` caps at N=30), NOT a demonstrated
  > architectural ceiling — the finite-resource capacity question stays OPEN pending the
  > uniform/constant-program population path (MEM-18/19).
  > **MEM-17:** LOAD -> zero (non-mirror) or the mirrored value; STORE -> silent discard
  > (non-mirror) or redirect to binding 0 (mirror region); ATOMIC exchange -> returns 0 and
  > discards, or redirects and discards. `byte+4` is live but is not the selector; the selector is
  > `byte+5`. Compiler consequence: an out-of-range slot is fault-contained but silently wrong —
  > never emit one, and never rely on 128..255 as distinct storage.
  > Evidence: `experiments/EXP-0083-m4-base-slot-census/` (HW-PROBE + OWN-SHADER; M4 target; A18
  > validation deferred until the device is available).

- **MEM-18 — Does the instruction's `base_slot` directly index the userspace resource table, or an
  intermediate base-register/preload file populated by the USC binding program?**

  A `No` to direct indexing requires the exact table-to-preload mapping and its independent capacity
  to be documented.

- **MEM-19 — Can the USC constant/uniform program populate every usable base slot, and what happens
  when its declared preload count exceeds the supported capacity?**

- **MEM-20 — Can Apple9 load/store through a 64-bit device address obtained dynamically in a GPR or
  register pair, without first assigning that address to a statically encoded base slot?**

  Compiler consequence: a `Yes` supplies the indirect/bindless fallback for descriptor arrays and
  shaders whose logical resource count exceeds the direct-slot capacity. A `No` requires identifying
  the actual hardware mechanism used for those cases before the Vulkan compiler is implementable.

- **MEM-21 — Can a non-uniform, per-lane descriptor-array index select different buffer base
  addresses for different lanes in one SIMD group?**

  A `Yes` must identify the complete executable sequence and distinguish it from a uniform-program
  selection that chooses only one address for the entire dispatch.

- **MEM-22 — When Apple's compiler is given more live buffer resources than fit in the direct-slot
  path, does it reject the shader, use a descriptor-table/dynamic-address path, or split/preload the
  resources by another mechanism?**

  Compiler-output evidence answers which strategy Apple chooses, but the selected fallback still
  requires independent hardware execution validation.

  > **Answered 2026-08-28 (EXP-0084, M4/G16G, commit `783fe693`): MEM-20 Yes · MEM-21 Yes · MEM-22
  > ceiling 31 with a validated dynamic-address path past it.** Two runs, `04_results.jsonl`
  > SHA-256 identical.
  > **MEM-20:** loads/stores through a dynamically held 64-bit device address with NO statically
  > encoded base slot work — four independent constructions (raw `device ulong*` cast; Metal
  > implicit argument buffer; double indirection; raw pointer without `useResource:`), all
  > byte-exact. Mechanism: each dynamically-loaded pointer gets its own compiler-populated
  > `base_slot` table entry (`index_reg` is shared; `base_slot` differs) — this REFUTED the
  > experiment's own shared-slot hypothesis.
  > **MEM-21:** per-lane divergent selection is real, not broadcast — a selector computed only from
  > `thread_position_in_grid` gave 32 lanes 32 distinct buffer tags, with a uniform control and a
  > single-lane-outlier control ruling out the alternatives.
  > **MEM-22:** MSL rejects a 32nd direct `[[buffer(31)]]` argument at compile time (0..30 ceiling);
  > independently, the dynamic-address mechanism executed correctly at N=64 and N=256 — 2-8x past
  > that ceiling — with every lane reading its own buffer.
  > Compiler consequence: the bindless / descriptor-array fallback EXISTS and is hardware-validated.
  > Direct slots are bounded (see MEM-15/16), dynamic addressing scales past them.
  > Evidence: `experiments/EXP-0084-m4-dynamic-buffer-addressing/` (HW-PROBE + OWN-SHADER; M4
  > target; A18 validation deferred). A non-gated single-run splice (`base_slot` 3->4 flipping the
  > dereferenced buffer) is retained in `analysis/supplementary/` as a successor's H1, not promoted.

## P0 — Texture operations, selectors, and finite limits

- **TEX-01 — Does the Apple9 coordinate-projection setup form implement exactly NIR's projective
  divide, including zero, signed-zero, infinity, NaN, and array-coordinate behavior?**

  Compiler consequence: only `Yes` permits projective sampling to survive as a target operation;
  otherwise `lower_txp` remains enabled.

- **TEX-02 — Is there no one-operation Apple9 form for a gather with four independently specified
  constant offsets?**

  Test a true source `textureGatherOffsets`, not four independent source gathers that the frontend
  has already expanded. `Yes` retains `lower_tg4_offsets`; `No` requires the complete encoding.

- **TEX-03 — Does the native one-offset sample/gather form encode every pair in the API-required
  range -8 through +7 without aliasing?**

  Test all 256 2D pairs and the applicable 1D/array/cube forms. Record the exact signed encoding,
  every instruction byte involved, and whether offset and sampler selection share fields.

- **TEX-04 — Can a texture offset be supplied dynamically from a GPR, including non-uniformly per
  lane, without pre-adjusting the coordinates?**

- **TEX-05 — Does Apple9 accept a dynamic `min_lod` operand natively for ordinary, bias, explicit-
  gradient, comparison, and gather samples?**

  Record unsupported combinations individually; one working ordinary sample is not a `Yes` for all
  forms.

- **TEX-06 — Can `txs`, mip-count, and sample-count queries read the correct descriptor selected by
  a dynamic and non-uniform argument-buffer index?**

  Compiler consequence: determines whether queries are ordinary descriptor loads or require a
  special uniform-only ABI.

- **TEX-07 — Does Apple9 expose a shader-visible primitive equivalent to NIR
  `samples_identical`?**

  A `No` establishes the conservative-false lowering. A `Yes` must identify its correctness for
  compressed, uncompressed, partially resident, and memoryless MSAA images.

- **TEX-08 — Does Apple9 expose a semantically distinct pre-dispatch texture operation usable for
  NIR `tex_prefetch`?**

  A `No` means prefetch is selected as an ordinary sample with no extra guarantee.

- **TEX-09 — Is there no native sampled/texel-buffer format for every `R32G32B32_*` format required
  by Vulkan?**

  A `Yes` confirms the raw device-load fallback. Test raw descriptor codes before treating absence
  from Metal's format enum as proof of silicon absence.

- **TEX-10 — Can every supported Vulkan sampler-YCbCr conversion be expressed by one Apple9
  sample operation and descriptor, rather than multi-plane samples plus shader ALU?**

  A likely `No` must distinguish packed native 4:2:2 formats from general 2/3-plane conversion.

- **TEX-11 — Do arbitrary sampler border colors have no native descriptor/table representation
  beyond the three decoded presets?**

  Confirm by raw descriptor and sampler-table injection. Also determine whether custom-border
  shadow comparison can be emulated exactly with the two-sample clamp-to-zero/clamp-to-one method.

- **TEX-12 — Do sparse samples from mapped and unmapped texels return the API-required color and a
  usable residency code for every filtered, gathered, and fetched form?**

- **TEX-13 — Are out-of-range integer texel coordinates, array layers, mip levels, and MSAA sample
  indices robust for every texture dimension and result width the compiler may emit?**

  Produce a matrix separating zero/discard/fault/alias behavior. Reads, writes, and atomics are
  distinct questions even if they share address preparation.

- **TEX-14 — Are all 128 published direct texture arguments simultaneously and independently
  selectable in one Apple9 shader stage?**

  Use distinguishable resources and exercise every selector, especially 7/8, 15/16, 31/32, 63/64,
  and 127. The successful eight-texture table test is not sufficient.

- **TEX-15 — Is the complete direct texture-selector encoding known for selectors 0 through 127?**

  The `op+4` bit-7 two-way splice is explicitly insufficient: texture 2 changes companion/op fields.
  Decode every co-varying field and distinguish resource selection from coordinate and destination
  registers.

- **TEX-16 — Does attempting a 129th direct texture produce a deterministic API/compiler rejection
  rather than aliasing, truncation, or a GPU fault?**

  Test both source compilation and raw table/selector injection. The driver must not depend on raw
  invalid behavior, but the hardware specification should record it.

- **TEX-17 — Are all 16 published direct sampler arguments simultaneously and independently
  selectable in one Apple9 shader stage?**

  Test all sampler selectors with observably different state, both with and without constant texel
  offsets, because current evidence shows those encodings share instruction bytes.

- **TEX-18 — Does attempting a 17th direct sampler produce deterministic API/compiler rejection
  rather than aliasing, truncation, zero, or a GPU fault?**

  Current splices of selector 2/3 with only two populated samplers returned zero; that does not
  establish the maximum or the general unbound-selector rule.

- **TEX-19 — Can Apple9 dynamically select every argument-buffer texture entry through the
  published limit of 1,000,000, both uniformly and non-uniformly per lane?**

  Sweep powers of two and boundary values, then test the last legal entry. Record the resource-ID or
  descriptor-pointer representation and its reuse/lifetime rules.

- **TEX-20 — What exactly happens for an argument-buffer texture index at or above 1,000,000, an
  unpopulated entry, and a nonresident resource?**

  Record API rejection separately from raw shader behavior: zero, alias, fault, or device loss.

- **TEX-21 — Can Apple9 dynamically select every bindless sampler entry through index 499,999,
  both uniformly and non-uniformly per lane?**

  Existing execution at 4, 8, and 64 entries does not close this question. Test large allocations,
  the final valid ID, descriptor duplication/deduplication, destruction, and ID reuse.

- **TEX-22 — What exactly happens when allocating the 500,001st sampler or indexing entry 500,000,
  an unpopulated entry, or a destroyed sampler ID?**

  Separate userspace allocation failure from raw hardware behavior. Confirm that exhaustion cannot
  silently reuse a still-live ID.

- **TEX-23 — Are the published limits 16,384 for 1D/2D/cube dimensions, 2,048 for each 3D axis,
  and 2,048 array layers independently enforced without field truncation?**

  Test the largest legal object and first illegal object through API creation, descriptor packing,
  and raw injected descriptors. Record the behavior of malformed width/height/depth/layer fields.

- **TEX-24 — Does the 4-bit mip-count field support every legal mip chain through 15 levels, and
  what are the exact sample/fetch results for negative, excessive, infinite, and NaN LOD values?**

- **TEX-25 — Are 1x, 2x, and 4x the complete Apple9 MSAA sample-count set, with 8x and above rejected
  before submission?**

  Also record the raw descriptor and pipeline behavior for unsupported counts and the result of an
  out-of-range runtime sample index.

- **TEX-26 — Is sampler anisotropy limited to 16x even when raw descriptor codes request
  32x/64x/128x, and what does each unsupported code do?**

- **TEX-27 — Is sampler maximum LOD limited to 14.0 even when the raw field encodes values through
  15.875, and what does each above-14 encoding do?**

- **TEX-28 — Are all currently unnamed sampler address, border, swizzle, and filter encodings either
  aliases, deterministic invalid values, or additional supported modes?**

  Exhaust each finite field. Record zero/alias/fault behavior for every code instead of inferring a
  semantic limit from the values Metal happens to emit.

## P0 — Atomics and synchronization

- **ATOM-01 — Is integer atomic subtract a direct operation selector for device memory?**

- **ATOM-02 — Is integer atomic subtract a direct operation selector for threadgroup memory?**

- **ATOM-03 — Are device atomic return values the pre-operation values required by NIR?**

- **ATOM-04 — Does compare-exchange execute as one native transaction with the exact success and
  returned-value semantics required by NIR?**

- **ATOM-05 — Is a uniform-address atomic SIMD pre-combine semantically valid for every operation for
  which Apple's compiler emits it?**

- **ATOM-06 — Is that pre-combine invalid or disabled when individual lanes require distinct return
  values?**

- **ATOM-07 — Are relaxed atomics ordered only by dependencies, with no implicit device-wide fence?**

- **ATOM-08 — Does the identified device-memory fence provide the acquire/release visibility needed
  by supported Vulkan/GL memory semantics?**

- **ATOM-09 — Does the threadgroup barrier combine execution convergence with the requested
  threadgroup memory fence?**

- **ATOM-10 — Does a device-scope barrier require a distinct scope/flag encoding from a standalone
  device-memory fence?**

- **ATOM-11 — Are texture/image memory operations covered by the same fence encoding as device-buffer
  memory?**

  A `No` requires a distinct image/texture barrier legalization path.

## P0 — Fragment execution, interpolation, and derivatives

- **FS-01 — Do `get_sr 0xa0` and `0xa1` return the integer pixel X/Y required by NIR
  `load_pixel_coord`?**

- **FS-02 — Are those pixel coordinates stable across samples and helper invocations in an MSAA
  fragment shader?**

- **FS-03 — Is the exact relationship among pixel coordinate, sample position, center convention,
  and NIR `frag_coord.xy` known for upper-left/lower-left and pixel-center modes?**

- **FS-04 — Does the derivative instruction compute the API-required fine derivative over the
  hardware 2x2 quad?**

- **FS-05 — Is there a distinct coarse derivative mode, or must coarse derivatives use the same
  operation as fine derivatives?**

- **FS-06 — Are derivative results defined correctly when some lanes are helpers, discarded, or
  outside primitive coverage?**

- **FS-07 — Does each derivative instruction operate on one scalar component, requiring
  `scalarize_ddx = true`?**

- **FS-08 — Are flat, smooth, noperspective, centroid, sample, and explicit-offset interpolation
  modes each independently encodable and hardware-validated?**

- **FS-09 — Does convergent interpolation remain semantically distinct from flat interpolation,
  requiring `nir_io_always_interpolate_convergent_fs_inputs`?**

- **FS-10 — Can dynamically indexed fragment inputs be lowered without changing interpolation mode
  or provoking-vertex behavior?**

- **FS-11 — Can dynamically indexed fragment outputs be lowered without emitting an unsupported
  dynamic tilebuffer/render-target selector?**

- **FS-12 — Does `discard_fragment` suppress all color, depth, stencil, and sample-mask writes for
  the discarded lane?**

## P1 — Transcendental and special-function semantics

- **TRIG-01 — Is the complete operand and modifier encoding of the native trigonometric/reduced-range
  primitive hardware-validated?**

- **TRIG-02 — Is the complete operand and modifier encoding of the `0x2b` range-reduction operation
  hardware-validated?**

- **TRIG-03 — Does the native range-reduction operation expose the quadrant information needed to
  implement both sine and cosine without re-reducing the input?**

- **TRIG-04 — Can sine and cosine of the same SSA input share one native range-reduction result?**

- **TRIG-05 — Has a finite input interval been established over which the native Apple9 sin/cos
  lowering meets the required error bound?**

  A `Yes` answer must include the interval, tested error metric, maximum observed error, and search
  method; “moderate inputs” is not sufficient.

- **TRIG-06 — Does native range reduction fail the intended Vulkan/GL accuracy contract for some
  finite FP32 inputs?**

  A `Yes` confirms the need for a software large-argument reducer.

- **TRIG-07 — Does the observed sine/cosine polynomial, with its exact coefficient bit patterns and
  evaluation order, meet the desired error bound over its reduced interval?**

- **TRIG-08 — Are sine and cosine special cases for `+0`, `-0`, infinities, NaNs, and subnormals fully
  characterized on hardware?**

- **TRIG-09 — Can FP16 sine/cosine use the same FP32 reduction and polynomial followed by one native
  FP16 conversion while satisfying the FP16 contract?**

- **TRIG-10 — Does Apple9 fast and precise Metal output use byte-identical sine/cosine arithmetic for
  every tested source form and floating-point mode?**

  This is a compiler-output question; a `Yes` does not by itself prove API conformance.

- **SFU-01 — Are reciprocal, reciprocal-square-root, square-root, exp2, log2, floor, ceil, trunc,
  and round each independently selectable in the native special-function family?**

- **SFU-02 — Are the result semantics and special cases of every SFU selector hardware-validated?**

- **SFU-03 — Is the reciprocal/rsqrt estimate seed deterministic for every input bit pattern and
  floating-point mode?**

- **SFU-04 — Does the target precise reciprocal sequence require exactly two refinement iterations
  to achieve its claimed result accuracy?**

- **SFU-05 — Does precise square root require a final correction distinct from simply
  `x * precise_rsqrt(x)`?**

- **SFU-06 — Does precise division require a remainder correction distinct from
  `a * correctly_rounded_rcp(b)`?**

- **SFU-07 — Are exp2/log2 error bounds and exceptional-value behavior sufficient for the source
  APIs without an additional software correction path?**

## P1 — Register files, immediates, and instruction encoding

- **ENC-01 — Are all GPR source and destination fields decoded for every instruction intended for
  initial compiler use?**

- **ENC-02 — Can every such instruction address every legal register it is architecturally allowed
  to use, including registers above r15 and r63 where applicable?**

- **ENC-03 — Are restrictions on even/odd registers and register pairs completely known for FP16,
  FP32, vectors, and I64 values?**

- **ENC-04 — Are uniform-register sources independently selectable for every ALU family for which
  the compiler may use them?**

- **ENC-05 — Are immediate ranges, encodings, sign rules, and NaN/float literal restrictions fully
  known for each initial ALU family?**

- **ENC-06 — Are all modifier interactions—abs, negate, saturate, width, cache/last-use, and source
  file—hardware-validated for the forms the compiler will emit?**

- **ENC-07 — Are every required constant and reserved bit known well enough that independently
  assembled instructions never rely on copied template residue?**

- **ENC-08 — Is instruction length computable unambiguously from decoded fields for every emitted
  instruction, without a fallback/catch-all rule?**

- **ENC-09 — Is every initial compiler instruction specified completely enough for experimental
  encode/decode round trips without losing operand or modifier information?**

- **ENC-10 — Can independently assembled representatives of every initial instruction family execute
  correctly in one generated shader, rather than only as single-op splices?**

- **ENC-11 — Is the exact program-end/stop encoding and required code alignment known for all shader
  stages?**

- **ENC-12 — Are branch displacement origin, unit, width, sign extension, and legal range
  hardware-validated?**

- **ENC-13 — Are call/return, frame, and reconvergence encodings sufficient to compile nested control
  flow without copying Apple's block layout?**

- **ENC-14 — Is the maximum usable GPR count exactly 96 for every Apple9 shader stage?**

- **ENC-15 — Is the mapping from compiler register pressure to occupancy/resource metadata fully
  determined for every stage?**

- **ENC-16 — Is scratch spill addressing and frame-size metadata fully known for generated shaders?**

## P1 — Control flow and execution masks

- **CF-01 — Can arbitrary reducible NIR `if`/`else` control flow be expressed using the decoded
  predicate and reconvergence operations?**

- **CF-02 — Can arbitrary nested NIR loops with `break` and `continue` be expressed without an
  undocumented compiler-generated helper sequence?**

- **CF-03 — Is the maximum safe hardware reconvergence nesting depth known?**

- **CF-04 — Does divergent return require a distinct lowering from an ordinary branch to a shared
  epilogue?**

- **CF-05 — Are Boolean predicates stored in an independently addressable predicate file rather than
  ordinary GPR values?**

- **CF-06 — Are all predicate-file allocation and lifetime restrictions known well enough for a
  register allocator or late predicate allocator?**

## P1 — Subgroups and quad operations

- **SIMD-01 — Is the executable subgroup width always 32 for every supported Apple9 stage and launch
  shape?**

- **SIMD-02 — Are subgroup ballots exactly 32 bits with one stable bit-to-lane mapping?**

- **SIMD-03 — Do subgroup shuffle, broadcast, rotate, and fill operations define out-of-range lanes
  in the way required by NIR?**

- **SIMD-04 — Are inclusive/exclusive scans and reductions correct for partially active and divergent
  subgroups?**

- **SIMD-05 — Are quad lane numbering and horizontal/vertical/diagonal neighbor mappings completely
  known?**

- **SIMD-06 — Does a SIMD-group barrier compile to no instruction because all 32 lanes execute in
  lockstep with the required memory visibility?**

- **SIMD-07 — Are helper lanes included or excluded correctly by every subgroup and quad operation
  exposed to fragment shaders?**

## P2 — Questions that may remain deferred for the first compiler

- **P2-01 — Is native BF16 scalar and packed arithmetic exposed by portable NIR in a form useful to
  this compiler?**

- **P2-02 — Are BF16 conversion, rounding, denormal, and NaN semantics fully hardware-validated?**

- **P2-03 — Are matrix/cooperative-matrix instructions sufficiently decoded to select them from NIR
  cooperative-matrix operations?**

- **P2-04 — Are mesh/object-stage register, varying, barrier, and termination semantics complete
  enough for independent compilation?**

- **P2-05 — Are ray-query instruction operands, control flow, memory layout, and synchronization
  complete enough for independent NIR lowering?**

- **P2-06 — Is any native FP64 arithmetic operation present beyond integer register-pair machinery
  and software emulation support?**

## Closure criteria for the questionnaire

The initial NIR-to-Apple9 compiler contract is ready to freeze only when:

- every P0 question is answered `Yes` or `No`, not `Unknown`;
- every answer that enables a NIR `has_*` option has an executable independently encoded test;
- every answer that would disable a `lower_*` option documents the complete Apple9 semantics and
  encoding needed by a later legalization implementation, with a minimal experimental execution
  proving the proposed native sequence where applicable;
- the test results distinguish A18 Pro/G17P from M4 wherever both are intended targets; and
- all negative answers document the required future compiler response: generic NIR lowering,
  Apple9 IR legalization, software emulation, or feature non-exposure.

The P1 and P2 sections can close incrementally, but an unanswered item must map to a documented
feature restriction or conservative lowering rather than an assumption.

## Whole-handoff closure gate

This discovery/documentation assignment is complete only when all of the following facts and
specifications exist. None of these items asks the RE agent to implement the production component.

1. A field-by-field Apple9 mapping and Linux end-to-end evidence for every existing Asahi queue,
   render, and compute UAPI field, with no new or repurposed field assumed.
2. A fully documented and experimentally validated Apple9 userspace helper/scratch protocol for VS,
   FS, CS, and preambles, including spill exhaustion and recovery on G16G and G17P.
3. A documented unchanged-UAPI mapping for graphics code selection plus complete code-container,
   extent, metadata, and resource-specification construction rules supporting multiple pipelines.
4. Bit-exact specifications for every userspace-emitted VDM, CDM, PPP, USC, ZLS, PBE, attachment,
   link, barrier, termination, relocation, and reserved field. Production schema generators and
   packers are a later implementation task.
5. A compiler-ready semantic opcode/property specification validated by experimentally encoded
   execution across every initially supported NIR family and legal operand range. Production opcode
   tables and assemblers are a later implementation task.
6. Complete documented VS/FS/CS, prolog/epilog, varying, tilebuffer, helper, BG/EOT, partial-render,
   and programmable blend/logic/format-conversion semantics and ABIs.
7. A tested per-format feature/conversion specification sufficient for a later driver to derive
   every advertised API format property.
8. A documented Vulkan/GL-correct cache, memory, atomic, and barrier model covering every compute,
   render, texture, PBE, and host transition.
9. Documented robustness, sparse residency, VM, query, timestamp, indirect-command, and fault
   behavior for every feature that a later implementation may advertise.
10. Independent G16G and G17P evidence matrices covering simple/complex compute, direct/indexed/
    indirect draw, MRT, MSAA, depth/stencil, pipeline switches, multiple commands, links/barriers,
    spills, partial renders, exhaustion, and fault recovery.
11. A documented license/provenance path permitting a later Mesa implementation and derived tables
    to be upstreamed.
12. A completed finite-resource table for **every** finite namespace identified by this document.
    No row may substitute field width or a published API limit for observed usable capacity. Every
    row must include maximum-valid and first-invalid tests, exact exhaustion behavior, lifetime/reuse
    rules, and the documented, evidence-backed action a future compiler/driver must take when more is
    required.

If any finite resource lacks item 12, document the conservative limit, lowering requirement, or
feature restriction that a later implementation must use. Do not implement it in this assignment,
and do not mark the underlying hardware question complete.
