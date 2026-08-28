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

  > **Answered 2026-08-28 (EXP-0091, M4/G16G, commit `4c2df727`): YES.** A demoted lane's
  > post-discard `uv += 1000` mutation appears in a surviving neighbour's `fwidth()` as exactly
  > **999.0** (the predicted value), against exactly `1.0` in both a no-discard control and a
  > statement-order control. Cross-validated by `quad_shuffle_xor` retrieving the demoted lane's own
  > live post-discard register, and by a measurable shift in a surviving neighbour's implicit-LOD
  > texture sample. Two runs, 78/78 cases byte-identical. **Compiler consequence: permits
  > `.discard_is_demote = true`.** Evidence: `experiments/EXP-0091-m4-fragment-sample-discard/`
  > (HW-PROBE + OWN-SHADER; M4 target; A18 deferred).

- **OPT-10 — Does an ordinary aligned Apple9 memory load satisfy the atomic-load ordering and
  visibility requirements when surrounded by the appropriate Apple9 fences?**

- **OPT-11 — Does an ordinary aligned Apple9 memory store satisfy atomic-store ordering and
  visibility requirements when surrounded by the appropriate Apple9 fences?**

  Compiler consequence of OPT-10 and OPT-11 together: only two `Yes` answers permit
  `.has_atomic_load_store = true`.

  > **Answered 2026-08-28 (EXP-0121, M4/G16G, commit `1143ec55`) — OPT block (OPT-02 and OPT-09
  > answered separately above/below):**
  > **OPT-01 YES** — relaxed and precise division compile to structurally distinct sequences
  > (66 vs 300 bytes; a single `fspecial` SFU estimate vs. `fspecial` plus a multi-instruction
  > integer-domain refinement block). Confirms `.lower_fdiv = false`; the selection point is the
  > `fast::`/`precise::` namespace, **not** the global compile flag alone.
  > **OPT-03 YES** — `pow` genuinely needs a fixup: the naive `exp2(y*log2(x))` composition
  > returns NaN for **22 of 53** directed edge cases (negative base, zero base, zero exponent)
  > that `pow` gets IEEE/C99-correct, and `pow`'s compiled body is ~27x larger (2102 vs 76
  > bytes). Confirms `.lower_fpow = false` and the need for an `A9_POW`-style pseudo.
  > **OPT-04 PARTIAL / NO for "single instruction"; YES for numerical correctness** — the
  > dedicated `fldexp` opcode in `tools/agx-isa/db.json` was **never observed** across 4 fresh
  > compile variants of `ldexp(x,n)` with runtime `n`; the compiler emits a ~200-byte
  > integer-bit-manipulation composition instead. That composition is numerically correct
  > (451/452 exact against a DAZ+FTZ-adjusted oracle; the sole residual is a boundary-rounding
  > edge at the exact min-normal/max-subnormal threshold). **`.has_ldexp = true` is NOT supported
  > by this evidence for this calling pattern.**
  > **OPT-05 YES** — all 18 (type x condition) forms compile to exactly ONE fused `isel8`
  > (`get_sr, device_load x4, isel8, device_store, stop`, 86 bytes) whose `selTrue`/`cmpA`/`cmpB`
  > are independent register operands carrying arbitrary non-Boolean sentinel values. Enables
  > `.has_fused_comp_and_csel = true`.
  > **OPT-06 YES** — the same fused `isel8` serviced FP32, signed I32 and unsigned I32 for all six
  > of eq/ne/lt/le/gt/ge including signed/unsigned-distinguishing bit patterns; **825/825** corpus
  > rows matched the host oracle.
  > **OPT-07 NO (bounded structural negative), functionally correct via ALU-select** —
  > `iter`/`iter_flat`'s slot field is a compile-time `imm` in every observed instance
  > (0,6,8,10,12,14,16 — small constants, never a register). Dynamic 8-way indexing (extending
  > EXP-0111 FS-10's 4-way test) reads every candidate via ordinary fixed-slot interpolation then
  > selects via ALU, 8/8 exact. No register-sourced slot path exists even at 8 candidates.
  > **OPT-08 UNKNOWN/PARTIAL mechanism, positive-leaning structurally** — genuinely
  > per-fragment-divergent 2-way AND 3-way `[[color(n)]]` output both compile to exactly **ONE**
  > `frag_color_store` (not scaling 1:1 with target count, which the pre-registered falsifier
  > required for a negative reading), `rt_index=0` (imm) in both, yet hardware readback proves
  > correct independent routing to 2 and 3 distinct render targets. MSL still offers **no syntax**
  > for a dynamic-output store, so a compiler must keep lowering to a branch/select chain over
  > static `[[color(n)]]`; this experiment cannot license a NIR-level dynamic-output primitive.
  > **OPT-10 NO** — an ordinary aligned load does **not** reliably observe a cross-thread write
  > even surrounded by `atomic_thread_fence(mem_device, seq_cst, thread_scope_device)`: every
  > plain-consumer-load combination (`AP_fenced`, `PP_fenced`) showed massive producer/consumer
  > timeouts at every `PAIRS>=1` in both runs (e.g. `AP_fenced` PAIRS=1: 300/300 iterations never
  > completed), while the identical protocol with an atomic consumer load (`AA_fenced`,
  > `PA_fenced`) is fast and 100% clean at every scale.
  > **OPT-11 YES** — an ordinary aligned store observed by a *trusted atomic* load satisfies store
  > ordering/visibility under the same fence: `PA_fenced` is 0 mismatches / 100% completion at
  > every `PAIRS` in {1,4,8,16}, both runs, and its unfenced control `PA_unfenced` breaks at
  > `PAIRS>=4` exactly as required.
  > **Joint consequence: `has_atomic_load_store` must stay FALSE** — the gate needs both OPT-10
  > and OPT-11 to be `Yes`, and OPT-10 is `No`. A compiler must never lower an atomic load to a
  > plain load, fenced or not.
  > Open sub-items deliberately left UNKNOWN: OPT-04 was tested only for the exact
  > `ldexp(x[gid], n[gid])` MSL idiom (plus a uniform-`n` variant) — a different idiom might reach
  > the unobserved `fldexp` opcode; OPT-08's actual hardware mechanism behind the single
  > `frag_color_store` is not decoded (flagged for a dedicated splice-level follow-up); OPT-10/11
  > used `PAIRS` in {1,4,8,16} only, and `PAIRS=1` is uniformly too small to expose reordering for
  > any access method (matching EXP-0093), so the litmus threshold is a design fact, not a limit.
  > Evidence: `experiments/EXP-0121-m4-nir-contract/` (HW-PROBE + OWN-SHADER + STRUCTURAL mix;
  > M4 target; A18 deferred).

---

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

  > **Answered 2026-08-28 (EXP-0102, M4/G16G, commit `958f8307`) — PACK block.** Two capture runs,
  > 51/51 cases `OK` in both, all 51 gated records byte-identical.
  > **PACK-01 YES** — `float2 -> half2 -> as_type<uint>` compiles to TWO native `cvt_f2h_dst`
  > converts and **zero** `ibfins`/mask-shift-combine ops; functionally exact on all 7 directed
  > rows including fp16 max/min-normal and overflow-to-inf.
  > **PACK-02 YES** — the unpack direction compiles to TWO `falu2` instances (native, but via the
  > general float-ALU convert mode rather than a dedicated "unpack" mnemonic); exact on all 10
  > rows including NaN(0x7E00)/Inf(0x7C00) lanes.
  > **PACK-03 YES** — `pack_float_to_snorm2x16` compiles to a SINGLE `pack_convert`, the same
  > mnemonic and byte-identical body length (46 B) as `pack_float_to_unorm2x16`.
  > **PACK-04 YES** — `unpack_snorm2x16` is a single `unpack_convert`; **65536/65536** 16-bit lane
  > bit patterns bit-exact against an exact-Fraction oracle.
  > **PACK-05 YES** — `pack_unorm_2x16` matches `round(clamp(x,0,1)*65535)` with ties to EVEN
  > (confirmed at the one true exact tie, N=32767 -> 32768), NaN -> 0, negative -> 0, >1 -> 65535,
  > +/-Inf clamping like any out-of-range value; 10/10 directed rows.
  > **PACK-06 YES** — `unpack_unorm_2x16` is **65536/65536** bit-exact against `u/65535.0`.
  > **PACK-07 YES (normalized) / NO (generic)** — `pack_float_to_{unorm,snorm}4x8` compile to a
  > native two-instruction `pack_convert` + `frag_color_pack` pair; the hand-written GENERIC
  > (non-normalized) 4x8 integer gather is NOT native (15 instructions, `ibfins`-based).
  > `.has_pack_32_4x8` must be split: TRUE for normalized, FALSE for generic integer packing.
  > **PACK-08 YES** — `unpack_{unorm,snorm}4x8_to_float` each compile to TWO `unpack_convert`
  > instances, functionally exact on 8/8 rows each.
  > **PACK-09 YES** and **PACK-10 YES** — all 24 rows (8 exceptional-value pairs x add/mul/fma)
  > exact against a from-scratch exactly-rounded binary16 reference (genuinely fused for fma);
  > no cross-lane corruption for NaN, +/-0, subnormal or +/-Inf in any row. Closes the
  > correctness side of `.vectorize_vec2_16bit`.
  > **PACK-11 YES (packed short2 integer ALU is absent)** — `add` -> two independent `iadd2`;
  > `mul` -> two independent `imad`; `and` -> a different non-packed shape (two `mov_zext16` +
  > `mov_imm` + `pad_operand`, no `ilogic`). None reaches a packed 2-lane integer ALU op.
  > Open sub-items deliberately left UNKNOWN: PACK-04/06's exhaustive sweeps fixed the OTHER lane
  > equal to the tested lane, so the full 2^32 (lane0,lane1) cross-product is untested (PACK-09/10
  > cover cross-lane independence by targeted directed cases instead); PACK-05's tie rule rests on
  > 3 constructible exact ties, not a full tie sweep; PACK-08 is 8 directed rows, not exhaustive
  > over the 2^32 packed-word domain; PACK-07's `frag_color_pack` mnemonic appearing in a
  > COMPUTE-only kernel is reported as observed and flagged for `tools/agx-isa/db.json` provenance
  > review, not resolved; PACK-11's `and` decomposition (why `mov_zext16` rather than `ilogic`) is
  > observed but unexplained.
  > Evidence: `experiments/EXP-0102-m4-int-pack-semantics/` (HW-PROBE + OWN-SHADER, with PUBLIC
  > NIR/GLSL/MSL/IEEE-754 definitions used only to author the host oracle; M4 target; A18
  > deferred).

---

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

  > **Answered 2026-08-28 (EXP-0103, M4/G16G, commit `bbb1e9fc`) — FP block.** Two capture runs,
  > 47/47 cases byte-identical, zero faults/timeouts.
  > **FP-01 YES (fused), with an uncharacterized subnormal edge** — `fma_f32` 508/509 exact
  > against a genuinely-fused exact reference, including the canonical `(1+2^-23)^2 - 1`
  > fused-vs-separate-rounding vector. The one divergence has a subnormal `c` operand and is
  > consistent with — but on n=1 not an exhaustive characterization of — the DAZ+FTZ pattern.
  > **FP-02 YES** — `fma_f16` **2012/2012** exact (2000 random + every FP16 special triple).
  > **FP-03 PARTIAL (as pre-registered)** — `sub_f32` 818/820 exact against an IEEE `a+(-b)`
  > reference; both divergences are subnormal-operand DAZ. Whether this is literally a
  > negate-modifier bit on `fadd` or a separate op was NOT disassembled.
  > **FP-04 CHARACTERIZED, not "correct"/"incorrect"** (IEEE leaves it open) — of 620 pairs the
  > 2 genuine `+0`/`-0` ties returned **operand B's sign for BOTH `fmin` and `fmax`**
  > (`fmin(+0,-0)=fmax(+0,-0)=-0`; `fmin(-0,+0)=fmax(-0,+0)=+0`): on a magnitude tie this
  > hardware resolves to "the second operand", not to a sign rule. Non-tie: 618/618 `fmin`,
  > 617/618 `fmax` exact (the one `fmax` miss is subnormal DAZ).
  > **FP-05 YES** — every one-NaN pair returned the non-NaN operand for both `fmin` and `fmax`
  > (canonical / payload / negative-payload NaN, both operand orders). NaN-avoiding min/max.
  > **FP-06 NO — extensive, consistent DAZ+FTZ.** Every FP32 case touching a subnormal operand or
  > producing a correctly-rounded subnormal diverges, and every such divergence is explained by
  > DAZ+FTZ (`add`/`sub`/`mul`/`div_precise`: 3/3/32/39 divergences). **New here:** `saturate()`
  > also DAZs (49/1886 divergences, each a small positive subnormal returning `+0`), and FP32
  > relational compare DAZs too (`0x7fffff` vs `0x1` compare EQUAL). DAZ is not confined to
  > arithmetic — it extends through `fmax`/`fmin` (hence `saturate`) and relational compare.
  > **FP-07 YES, evidence points to per-instruction not device-fixed** — the same
  > `precise::rcp` kernel compiled with global `fastMathEnabled=YES` and `=NO` produced
  > **byte-identical** results (same DAZ+FTZ divergence set, same 1856/1886 exact count): the
  > global math-mode flag did not change `precise::` behavior, while `fast::` and `precise::`
  > differ from each other. Does NOT rule out a lower-level mode register the compiler always
  > sets identically; no register-level evidence collected.
  > **FP-08 YES** — FP16 subnormals preserved, scalar and packed; corroborated by the exhaustive
  > FP16 SFU result (zero DAZ/FTZ across all 65536 patterns for `rcp`/`rsqrt`/`sqrt`).
  > **FP-09 PARTIAL** — `saturate(NaN)` returned `+0.0` for every tested NaN class, exactly
  > matching the falsifiable prediction from composing `clamp(x,0,1)=fmin(fmax(x,0),1)` with
  > NaN-avoiding min/max; but subnormal inputs do NOT pass through (the FP-06 DAZ effect,
  > 49 divergences). 1837/1886 exact.
  > **FP-10 YES, perfectly** — FP32->FP16 is **1886/1886** exact round-to-nearest-even, including
  > explicit tie vectors; the narrowing conversion does NOT flush subnormal inputs or outputs.
  > **FP-11 YES in range; out-of-range characterized** — in-range truncation is 1177/1177 (int32),
  > 1077/1077 (uint32), 1011/1011 (int8), 988/988 (uint8) exact. Out-of-range/special behavior is
  > **saturating**, not wrapping: `+Inf -> *_MAX`, `-Inf -> INT*_MIN`/`0`, **NaN -> 0** in every
  > signed/unsigned 8/32-bit form.
  > **FP-12 YES (upgraded PARTIAL -> HW)** — `int(char(x))` and `int(char(clamp(x,-128,127)))` are
  > numerically identical for **1874/1886** cases (differing only on the 12 NaN inputs, exactly as
  > `clamp`'s NaN-avoiding composition predicts), and the PLAIN form compiles SHORTER (80 vs 92
  > bytes) — so the saturation is not a fused compiler-inserted clamp. FP32->int8 truncating
  > conversion saturates natively. Exact instruction encoding NOT decoded (OWN-SHADER-DIFF +
  > HW-PROBE, not splice-level ISA evidence).
  > **FP-13 YES, perfectly** — `fquantize2f16` via `float(half(x))` is **1886/1886** exact against
  > `widen(narrow(x))`, including every NaN/Inf/subnormal/boundary vector.
  > **FP-14 YES for NaN handling (419/420)** — `<,>,==,!=,<=,>=` and `isnan` all match an
  > IEEE-ordered reference across every NaN/Inf/normal/subnormal pairing; the sole divergence is
  > the FP-06 DAZ case, not a NaN issue. Whether the ISA exposes a *dedicated* unordered-compare
  > instruction (vs. software-composed `isnan`+select) was NOT disassembled.
  > Open sub-items deliberately left UNKNOWN: FP-01's subnormal-operand FMA behavior is not swept
  > to exhaustion; FP-02's packed `fma_f16x2` results were captured but not rescored (per-lane
  > unpack metadata not persisted — a scoring-tool gap, not a missing observation); FP-03's
  > negate-modifier-vs-separate-op question; FP-07's possible always-set lower-level mode register;
  > FP-14's dedicated-unordered-compare-instruction question. No FP64, no non-default rounding
  > modes (not exposed by the public API), and no claim about behavior inside a larger expression
  > graph the compiler might contract differently than these isolated single-op kernels.
  > Evidence: `experiments/EXP-0103-m4-fp-transcendental-semantics/` (HW-PROBE + OWN-SHADER +
  > PUBLIC MSL function names; M4 target; A18 deferred).

---

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

  > **Answered 2026-08-28 (EXP-0102, M4/G16G, commit `958f8307`) — INT block.** Two capture runs,
  > 51/51 cases `OK` in both, all 51 gated records byte-identical.
  > **INT-01 YES** — `extract_bits(data, off, 0) == 0` for every tested `(data, off)` pair
  > (6 data patterns x 4 offsets); width 0 is a legal, deterministic zero-producing case.
  > **INT-02 NO — and the real contract is a three-way one, not NIR's.** Over a 122-row boundary
  > sweep the observed rule ("MODEL D") is: **`cnt==32` EXACTLY bypasses the offset** (verbatim
  > passthrough, even for `off == 2^32-1`); `cnt` in `{1..31}` or `{33..2^32-1}` applies `off` as
  > a **LITERAL, unmasked** shift, with `off>=32` zeroing the contribution. This is NOT NIR's
  > presumed "mask offset mod 32, clamp width to 32". **Scope note carried from the source:** this
  > is the SOURCE-LEVEL compiled behavior of Metal's `extract_bits` with runtime `off`/`cnt`
  > (compiled body: `ibfe` + `ibfins` + `b_alu10_loe` + `n2_op6` + store) — whether the `cnt==32`
  > bypass is raw `ibfe` hardware behavior or software the compiler adds around a plainer `ibfe`
  > was NOT distinguished. A NIR backend must emit an explicit `cnt==32` check rather than trust
  > hardware clamping.
  > **INT-03 YES** — the signed result equals MODEL D's unsigned result sign-extended over
  > `min(cnt,32)` bits in all 122 rows; no hidden signed mode. Lower signed extract to
  > unsigned + explicit sign-extend.
  > **INT-04 YES** — `rotl32(a, K mod 32)` for all 7 tested `K` (0,1,31,32,33,63,64) x 4 bases;
  > byte-identical compiled bodies prove the mod-32 reduction happens **at compile time**
  > (`imm0==imm32==imm64` fold to identity with no rotate op emitted; `imm31==imm63`;
  > `imm33==imm1`). Constant-amount rotate is a single 12-byte `irotate`.
  > **INT-05 YES** — `rotl32(a, n mod 32)` exact in all 64 rows (4 bases x 16 runtime amounts
  > incl. 0,1,16,31,32,33,63,64,65,127,128,255,256,1000,2^31,2^32-1).
  > **INT-06 YES (no one-instruction dynamic rotate)** — the runtime-amount kernel disassembles to
  > 10 instructions / 98 bytes vs. the immediate kernel's single `irotate` / 48 bytes.
  > **INT-07 YES** — `(a*b+c) mod 2^32` exactly, unsigned and two's-complement signed, at every
  > tested boundary triple (incl. `0xFFFFFFFF*2+1`, `INT32_MIN*-1+0`, `-1*-1*-1`); 14 rows.
  > **INT-08 PARTIAL / UNKNOWN — the probe design could not answer it.** The 40-live-temporary
  > register-pressure kernel produced a functionally exact result, but the compiler restructured
  > the 40-term reduction as a TREE of paired multiply-adds, so IMAD `dst` never exceeded r26.
  > **IMAD's own high-register reachability has never been tested by any experiment.** Do NOT
  > assume IMAD can address the full 0-95 range. (Note the still-open r>=64 addressing blocker is
  > a DIFFERENT instruction family — `falu2`/`falu2i` — see the ENC block.)
  > **INT-09 YES (DERIVED, not directly isolated)** — `clz` is HW-exact (0 -> 32, 1 -> 31,
  > 0x80000000 -> 0; 13 rows) and its compiled body (`ibitcount` -> `iadd2` -> `isel10`) is
  > structurally consistent with find-MSB + 31-minus + zero-clamp, i.e. the `ufind_msb`
  > (index-from-LSB) convention, NOT `ufind_msb_rev`. The find-MSB primitive's own standalone
  > output was never read back.
  > **INT-10 YES** — `clz` = `ibitcount` + `iadd2` + `isel10` (64 bytes, 3 non-trivial ops) vs.
  > popcount = `ibitcount` alone (44 bytes, 1 op). CLZ is necessarily compound.
  > **INT-11 YES (necessarily multi-instruction)** — one source-level `insert_bits` compiles to
  > THREE `ibfins`-family instances (distinguished by an internal `form` sub-field: 0, 16, 32)
  > plus TWO `b_alu10_loe` helper ALU ops. 256/256 rows match MODEL D. This refines EXP-0033's A18
  > mnemonic naming (three differently-named byte0 values there; one family + `form` here) without
  > changing the claim.
  > **INT-12 PARTIAL / UNKNOWN (nuanced) — NOT a uniform yes.** A real `ilogic` instruction with a
  > varying `lut_a` (2 bits, 0-3) + `lut_b` (1 bit, 0/8) selector plus operand-order swapping
  > realizes **10 of the 16** two-input functions (AND, NAND, OR, NOR, XOR, XNOR, AND-NOT and
  > OR-NOT in both orders). The 2 projections never reach any ALU op (free passthrough); the 2
  > negations route through a different dedicated `funary` op; the 2 degenerate constants fold to
  > `reg_move`/`mov_imm`+`iminmax`. The FULL field width — and whether `ilogic` could encode the
  > other 6 directly — is NOT established (no splice sweep of the raw `lut_a`/`lut_b` field).
  > **INT-13 YES for every compiler-emitted instance observed** — in BOTH compiled expression
  > shapes, every `carry_gen` is immediately preceded by the specific low-word `iadd2` whose
  > overflow it tests and immediately followed by `psel` then the dependent high-word add(s),
  > re-confirming EXP-0038's A18 finding fresh on M4. This is compiler-emitted evidence; it does
  > not prove the hardware *requires* adjacency (that is INT-14).
  > **INT-14 PARTIAL / UNKNOWN, deferred by design** — no new work: `carry_gen`'s operand-register
  > field layout has never been characterized (only its position/length), and the project-wide
  > silent-zero-on-wrong-operand-field warning makes a guessed splice liable to produce a false
  > result. Until closed, emit `carry_gen` ONLY in the adjacent pattern of INT-13; do not attempt
  > to synthesize a standalone carry-generate.
  > Open sub-items deliberately left UNKNOWN: INT-02/INT-11 are closed only at the
  > compiler-contract tier (a bare spliced `ibfe`/`ibfins` with an explicit width-32 field was not
  > constructed); INT-08's high-register IMAD question; INT-09's directly-isolated find-MSB
  > readback; INT-12's raw `lut_a`/`lut_b` field width and the 6 non-`ilogic` functions; INT-14
  > entirely. INT-11 also leaves a 40-byte `<unknown>` tokenizer tail (almost certainly the
  > `device_store`+`stop` epilogue) flagged as a `tools/agx-isa` DB coverage gap.
  > Evidence: `experiments/EXP-0102-m4-int-pack-semantics/` (HW-PROBE + OWN-SHADER, with PUBLIC
  > definitions used only for the host oracle; M4 target; A18 deferred).

---

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

  > **Answered 2026-08-28 (EXP-0082, M4/G16G, commit `311d3f3e`) — MEM-01..MEM-05 block:**
  > **MEM-01 PARTIAL YES** — the GPR index scales as an element index for `elem_size` codes 0/3/4
  > (16B/4B/8B, exact linear scaling); codes 1/2 (nominal 1B/2B) do NOT give true sub-word
  > addressing — the address rounds down to 4-byte granularity, `floor(idx*nominal_scale/4)*4`
  > (independently echoes EXP-0076's per-unit align-down from the encoding side).
  > **MEM-02 NO** — `idx_off` is neither element- nor byte-scaled: it is a FIXED 4-byte unit for
  > load and a FIXED 16-byte unit for store, independent of `elem_size` (5 discriminating cases).
  > **MEM-03** — the immediate offset is **UNSIGNED 11-bit, 0..2047, zero holes** (2048/2048 dense
  > sweep); the signed model is refuted exactly at f=1024. No first-invalid encoded value; OOB
  > addressing is silent zero-fill (load) / silent discard (store), never a fault.
  > **MEM-04 NO** — no non-power-of-two stride form exists (48 load+store cases). Arbitrary strides
  > must be lowered to ALU/IMAD before the memory instruction; this weakens the old `has_amul`
  > rationale.
  > **MEM-05 NO** — 11 wrap-family cases refute exact mod-2^32 wraparound; overflowing addresses
  > behave as genuine out-of-allocation, not fold-back.
  > Open sub-items deliberately left UNKNOWN: `byte+11` bits 2..7 are not uniformly inert (3/6
  > probed values broke or relocated the read), and the store-side `elem_size` code space beyond
  > the default is largely unresolved.
  > Evidence: `experiments/EXP-0082-m4-mem-offset-semantics/` (HW-PROBE + OWN-SHADER splice; M4
  > target; A18 deferred).

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

  > **Addendum 2026-08-28 (EXP-0122, M4/G16G, commit `f2b8ef66`) — refines MEM-05, MEM-08 and
  > MEM-12 above.** 74 guard cases (37 offsets x {load, store}) per run, two runs, 0 mismatches
  > across all 87 gated cases; 0 hangs, 0 faults, 0 command-buffer errors in 148 executions, and
  > no OOB store ever corrupted an adjacent allocation.
  > **MEM-05 refinement — the wrap period is EXACTLY 2^43 bytes.** For the
  > `(device uchar*)base + (uint64_t)off` idiom, all 12 discriminating cases match
  > `(base+off) mod 2^43` then align-down-4, including the two designed to exclude competing
  > periods (`1.5*2^43` rules out 2^42; `5*2^43+4` rules out anything larger), and the model
  > correctly predicts landing inside a real neighbouring allocation three times from three
  > different large offsets (`2^43-4`, `2^64-32`, `2^64-256` all read `5a5a5a5a`, our guard fill).
  > This does not contradict EXP-0082's MEM-05 `No` (mod-2^32 wrap is still refuted) — it names
  > the actual period. **Alternatives explicitly not excluded:** the 2^43 figure could reflect
  > (a) the GPU's real VA bus width, (b) a 43-bit addressing-operand width specific to this load
  > encoding, or (c) a firmware/driver address-space window. Untested for other access widths
  > (8/16/64/128-bit) and other idioms (texture addressing, argument-buffer-indirect pointers).
  > **MEM-08 refinement — "OOB reads return zero" is NOT page-wide and must not be relied on.**
  > EXP-0076's near-boundary model reproduces exactly under an independently authored harness
  > (offset 32 -> `05203b56`, 60 -> `f9142f4a`, 64 -> `00000000`, 1088 -> `00000000`), and 4096 B,
  > 32 KiB, 1 MiB, 16 MiB, 256 MiB, 4 GiB, 64 GiB, 1 TiB, 2 TiB and 4 TiB past the base all read
  > zero — **but at exactly 16384 B past the base (one sparse tile / the platform page quantum)
  > and its +/-256 B neighbourhood, reads return live, non-zero, non-guard-pattern data**
  > (`d166d8b1`, `0cda71aa`, `39ada2a3`, ... — not our `0x5A`/`0xC3` fills, so not our own guard
  > buffers). Both a "guard page around the allocation" model and an "everything unmapped reads
  > zero" model are falsified.
  > **MEM-12 consequence:** a `load_global_bounded` lowering must perform its own explicit bounds
  > check; it may NOT lean on address space adjacent to an owned allocation being safe or zero.
  > The zero-fill behaviour is real and reproducible at the tested small and very-large distances,
  > but it is not a property of "outside the allocation" in general.
  > Open sub-items deliberately left UNKNOWN: the owner of the live data at the 16384 B quantum is
  > not identified (most plausibly another `MTLBuffer`/`MTLLibrary`/queue-internal object);
  > `vm_start` / kernel-reserved-region boundaries are unbounded by this experiment (the lowest
  > address seen anywhere was `0x10000018000`, suggestively near 2^40, but allocation volume was
  > never driven high enough to bound the window); the allocator determinism observed
  > (byte-identical addresses across 3 alloc/free passes) is an observed behaviour within one
  > process, not an architectural guarantee, and was not tested across processes or under
  > concurrent allocation pressure.
  > Evidence: `experiments/EXP-0122-m4-sparse-vm-conventions/` (HW-PROBE + OWN-SHADER; M4 target;
  > A18 deferred).

---

- **MEM-13 — Does the hardware guarantee dependency interlocking from every load/texture/atomic
  result to a consuming ALU instruction without an explicit wait?**

- **MEM-14 — Does the same dependency interlock hold for stores and atomics whose source is produced
  immediately before the memory operation?**

  > **Answered 2026-08-28 (EXP-0085, M4/G16G, commit `2e693a58`) — MEM-13/MEM-14 block:**
  > **MEM-13 YES — HW-VALIDATED.** Six cases, PASS on both runs: device load -> immediate `fma`;
  > dependent/gather load -> immediate `fma`; atomic RMW result -> immediate ALU (N=8192,
  > permutation invariant); **48 independent loads per thread with zero waits**, summed and
  > consumed with no intervening statement, at N=4096 AND N=65536 (the adversarial
  > register-pressure/occupancy stress case); and `texture2d::read` -> immediate `fma` over 4096
  > texels. Structural tokenization shows the consuming ALU byte-adjacent to its producer
  > (`device_load` -> `falu3`, 0 intervening bytes) with **no wait/scoreboard opcode anywhere** in
  > the chain — including through the compiler's multi-instruction SIMD-reduce/broadcast tail for
  > the atomic case. This extends EXP-0025's A18 finding to two operation classes it did not test
  > compute-side: texture `read()` and "atomic RESULT consumed by ALU" under real contention.
  > **MEM-14 YES — HW-VALIDATED.** The interlock is bidirectional: `il_store_src` (ALU-computed
  > `a[i]*b[i]-a[i]` stored with zero gap, N=8192, deterministic) compiles to
  > `device_load, device_load, falu3[fma], device_store, stop` with 0 intervening bytes, and
  > `il_atomic_src` (ALU-computed addend fed directly as the atomic operand, N=8192, commutative
  > sum invariant) shows no wait instruction between the ALU computation and the atomic. Both PASS
  > byte-identical on both runs.
  > **Driver consequence:** on M4 a driver need not reason about scoreboard/wait insertion in
  > either direction for ordinary compute memory or atomic instructions; the omission that would
  > be a silent-corruption bug on G13-style hardware cannot occur here for these classes.
  > Open sub-items deliberately left UNKNOWN: this is observational (a construction attempt that
  > produced correct results at every scale tried), NOT a proof that no register-pressure regime
  > beyond N=65536 / 48-deep chains could expose a hazard. Only the presence/absence of an opcode
  > between producer and consumer is treated as evidence — the atomic reg-pack tail's DB field
  > names (`ret_flag`, `addr_desc`, `data_desc`) remain unvalidated placeholders.
  > Evidence: `experiments/EXP-0085-m4-memory-interlock-atomics/` (HW-PROBE + OWN-SHADER +
  > STRUCTURAL tokenization; M4 target; A18 deferred).

---

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

  > **Answered 2026-08-28 (desk pass over EXP-0010 / EXP-0020 / EXP-0083 / EXP-0141 / EXP-G1a) —
  > MEM-18 PARTIAL, leaning "intermediate preload file", with the mapping itself still undocumented.
  > [DESK-AUDIT over HW results]**
  > **The evidence points at the intermediate base-register/preload file, not at a direct index
  > into the userspace resource table — but no experiment has framed or tested it as MEM-18, and
  > the exact table-to-preload mapping the item demands does not exist.**
  > Three committed observations, each hardware-backed, point the same way:
  > (1) **The pointer is not in the code and not in the constant program.** "Buffer base pointers
  > are preloaded into a uniform/binding slot, selected by `device_load` byte+4 (HW-proven:
  > splicing the slot changes which bound buffer is read). The pointer is *not* in the shader code
  > and *not* in the constant_program — it is supplied by the command stream / USC" (EXP-0010).
  > The general statement of the ABI is: *"no stage preloads IDs into GPRs ... only buffer/vertex
  > base pointers + scalar uniforms are preloaded into the **uniform register file** (selected by
  > `device_load` byte+4 `base_slot`; the **vertex-buffer base = slot `0x03`**)"*.
  > (2) **The slot file's CONTENT is program-dependent, which a direct resource-table index could
  > not be.** EXP-0083 (M4/G16G, commit `8d47a271`, 351 cases x 2 runs = 702 executions, zero
  > faults) found slot 0's anomalous content *"tied to whether the compiler hoisted thread-invariant
  > loads into the constant program for that specific kernel, not to a hardware-fixed 'slot 0 is
  > always X' rule"* — in one kernel shape slot 0 reads the hoisted witness value, in another
  > (gid-variant indices, no hoist) it reads the plain bound buffer 0.
  > (3) **The selector's shape is a file, not a table.** The selector is **effectively 7-bit**:
  > values 128..255 mirror 0..127 **byte-for-byte** on every op path tested (census31 load 256/256,
  > census4 load, store, atomic), which explicitly *refutes* the naive "slots outside 0..30 are
  > simply zero" framing — slots 128..158 are not zero, they mirror 1..30's non-zero content.
  > Out-of-range or unpopulated access never faults in 702 executions: LOAD reads zero (non-mirror
  > region) or mirrors; STORE and ATOMIC discard silently or redirect to the mirrored binding.
  > `device_load.base_slot` is confirmed live and per-EXP-0083 in the current emitter spec
  > (EXP-0141, M4), and on the `atomic_mem` carrier it is **inert (256/256) with one bound target**.
  > **What is missing for a `No`-to-direct-indexing to be complete, in the item's own words —
  > "the exact table-to-preload mapping and its independent capacity":** EXP-0083 states plainly
  > that *"full characterization of the constant-program slot table is out of scope"* and makes
  > **no constant-program/uniform-pipe slot-table claim** beyond the slot-0 load-path observation.
  > The USC side is only structurally known: buffers reach the GPU as a flat table of 8-byte LE
  > GPU VAs at `0x10000100000 + 0xa0`, one per bound buffer in index order, while the uniform
  > preload is done by the USC program **body** (`0x67` loads), *not* a fixed tag list, under
  > per-stage header tags `0x0088_00XX` (register/shader-config), `0x0042_XXXX` (uniform-data
  > pointer) and `0x0020_00XX` (uniform-slot count/id) (EXP-G1a/EXP-0042). Nobody has connected
  > "binding index N" to "preload slot S" as a rule.
  > **Capacity, as far as it is known:** 31 usable slots via the direct `[[buffer(N)]]` API
  > (MEM-15), a 7-bit selector space (MEM-16), and EXP-0083's explicit note that whether an
  > architectural ceiling exists above 31 via a non-direct population mechanism (argument buffers /
  > bindless) **cannot be probed** through that API path.
  > **Conservative driver response:** treat `base_slot` as an index into a program-specific
  > preload file that the USC/uniform program populates, not as the API binding index; never rely
  > on slot == binding index; and bounds-check, because an out-of-range slot **silently aliases a
  > real binding** rather than faulting.
  > M4 target for EXP-0083/EXP-0141; the EXP-0010/EXP-0020/EXP-G1a statements are A18-era and are
  > cited as the structural model, not as M4 measurements. A18 deferred.
  > Evidence: `experiments/EXP-0083-m4-base-slot-census/RESULTS.md` (§H2, the 7-bit finding, and
  > "Remains open / flagged for the successor (MEM-18/19)"),
  > `experiments/EXP-0141-m4-emit-mem/RESULTS.md` §8, `docs/isa/README.md` "How uniforms & buffer
  > pointers reach registers (EXP-0010)" and "Preloaded-register ABI",
  > `docs/cmdstream/README.md` "USC / resource bind grammar — RESOLVED (EXP-G1a)".

---

## Items deliberately left UNANSWERED by this wave

No block is proposed for these. Each genuinely needs hardware; writing an answer from the
adjacent evidence would be a fabrication.

| item | why no block | what would close it |
|---|---|---|
| **P2-06** (native FP64) | The only thing on record is `docs/capability-completeness.md`'s "(absent) — not exposed by MSL on Apple GPUs", sourced to a **premise**, not a probe. No experiment ever compiled a `double` kernel or searched the opcode space for an FP64 op. Corpus byte0-census coverage proves nothing here: the corpus is compiled from an MSL that has no `double`. EXP-0146's native 64-bit integer ADD is integer register-pair machinery — exactly what the question excludes. | An MSL `double` compile-rejection probe (cheap) **plus** an opcode-space search, on M4. |
| **TEX-01** (projective divide) | `tex_addr_setup.form = 0x01` is identified as "coordinate projection (samples level 0)" and the whole op was byte-swept — but on **A18** (EXP-M4-14), and no numeric edge case (zero, signed zero, inf, NaN, array coordinate) was ever fed to it. MSL exposes no `sample`-with-w-divide entry point, so there is no compiler-emitted evidence to read. | `op+2` bit-space fuzzing on a spliced valid `tex_sample` bundle plus directed edge-case inputs, on M4. `lower_txp` stays enabled meanwhile. |
| **TEX-19** (bindless texture to 1,000,000) | EXP-0095 closed only the *shape* at `CAP = 256` / `K = 8` (feasibility exploration to N = 4096); EXP-0106 recorded it DEFERRED because confirming the documented ceiling is a large allocation-and-sweep campaign. The per-lane non-uniform half is separately supported by EXP-0106 TEX-06 (4 lanes, 4 distinct textures, correct `get_width`/`get_num_mip_levels` per lane) but only at 4 entries. | Re-run EXP-0095's GLIMG-A02 methodology at boundary values near 1,000,000, on M4. |
| **TEX-21** (bindless sampler to 499,999) | The only evidence is **A18** (EXP-O2B): `maxArgumentBufferSamplerCount = 500000` as a queryable capability, the 8-byte `gpuResourceID` = dense sequential index representation, and dynamic shader-computed indexing shown for a handful of entries. It explicitly did not sweep the range or the boundary, and it predates the M4-only directive. | M4 re-run of EXP-O2B §4's methodology at boundary values near 499,999. |
| **TEX-22** (500,001st sampler / destroyed ID) | EXP-O2B's own "Recommended next" section names exactly this gap (dedup/reuse check); it was never executed on any target. | The same successor as TEX-21, extended to allocation failure, ID reuse after destruction, and dedup. |
| **MEM-19** (USC preload capacity) | EXP-0083 flagged it and deferred it; nothing since has touched it. The USC side is known only structurally (per-stage `0x0020_00XX` uniform-slot count/id tag; preload performed by the program body's `0x67` loads, not a tag list) and **no experiment has driven the declared preload count past capacity**. | A USC uniform-program probe that varies the declared preload count across and beyond the supported capacity, on M4 — the successor EXP-0083 named. |

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

  > **Answered 2026-08-28 (EXP-0122, M4/G16G, commit `f2b8ef66`) — TEX-12 PARTIAL: the *unmapped*
  > *fetched* quadrant is closed; mapped, filtered, gathered and the residency code are open.
  > [HW]**
  > **UNMAPPED, fetched form — CLOSED.** Across 4 configurations (single-tile page16, multi-tile
  > 4x4 page16, single-tile page64, and a degenerate tile-larger-than-texture page256 case) x 3-5
  > coordinates each, **every coordinate in every configuration** read back all-zero component
  > bytes with `cb_status = 4` (completed) and **no error**, in all 4x2 = 8 executions
  > (`analysis/summary.json: sparse_unmapped_read.every_case_all_zero == true`). Unmapped
  > sparse-texture access is **fault-free and reads as zero** — the same quiet-zero model already
  > established for buffer OOB (EXP-0076), holding uniformly across all four tile-size/texture-size
  > relationships.
  > **MAPPED — a confirmed, reproducible NEGATIVE that this item must not lose.** Mapping one tile
  > via `MTLResourceStateCommandEncoder updateTextureMapping:mode:region:mipLevel:slice:` has a
  > real, correctly-sized effect (`heap.usedSize` grows by **exactly** one tile: 16384 B for the
  > single-tile case, one 16384 B tile of the 65536 B four-tile case). But a compute-kernel write
  > into a coordinate inside that freshly-mapped tile, read back on a separate
  > `waitUntilCompleted`-serialized command buffer, returns **all-zero, not the written pattern**
  > (`write_appears_to_persist == [false, false]`), and a three-stage read-after-write /
  > read-after-unmap / read-after-remap probe reads all-zero at **every** stage. Every
  > public-API synchronization explanation was tried and ruled out (`hazardTrackingMode = .tracked`,
  > an explicit `MTLFence`, `useResource:`/`useHeap:`, a 500 ms delay, reduction to one tile in a
  > single-tile texture, `setPurgeableState: .nonVolatile`), and an identical non-sparse
  > heap-allocated private texture writes and reads back correctly through both a compute read and
  > a blit copy — isolating the negative to the `MTLHeapTypeSparse` path specifically. **Root cause
  > is not established.** The named untested candidate is the macOS 26 `placementSparsePageSize` /
  > `MTLHeapTypePlacement` / `MTL4UpdateSparseTextureMappingOperation` path, which this experiment
  > never touches.
  > **Still open, explicitly:** (a) the **residency code** — EXP-0122's kernels are
  > `tex.read(coord)` on `access::read` only, so no `sparse_color` / `.resident()` form was ever
  > exercised; (b) the **filtered** and **gathered** forms — no sampler was bound in any sparse
  > case; (c) mapped-texel colour correctness, which is blocked behind the write-persistence
  > negative above; (d) sparse aliasing between two resources (only single-resource mapping tested).
  > Supporting geometry established in the same experiment: `sparseTileSizeInBytes = 16384`, and
  > `sparseTileSizeInBytesForSparsePageSize:` returns **16384 / 65536 / 262144** for
  > `MTLSparsePageSize{16,64,256}` — at least three page-size classes exist, so a driver must query
  > rather than assume the legacy 16 KiB tile.
  > **Conservative driver response meanwhile:** a Vulkan `sparseResidency*` implementation gets
  > non-faulting zero-return for unmapped fetches for free on M4, but must not advertise
  > residency-code queries or filtered/gathered sparse sampling, and must not assume a mapped tile
  > is writable through the classic `MTLHeapTypeSparse` path.
  > M4 target; A18 deferred. Runs `raw/m4-20260828-run01`, `raw/m4-20260828-run02`, 87/87 cases,
  > **0 mismatches** on the cross-run gate.
  > Evidence: `experiments/EXP-0122-m4-sparse-vm-conventions/RESULTS.md` §3.1-3.5,
  > `analysis/summary.json`, `kernels/sparse_access.metal`.

---

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

  > **Answered 2026-08-28 (EXP-0095, M4/G16G) — TEX-20 PARTIAL: the unpopulated-entry sub-question
  > has a recorded M4 verdict; the >= 1,000,000 and nonresident sub-questions remain DEFERRED as
  > EXP-0106 recorded. [HW]**
  > **Unpopulated / out-of-range bindless texture entry — recorded verdict (EXP-0095's
  > finite-resource table, M4, HW):** with a genuine runtime `uint` selector into a
  > driver-declared array of size `CAP`, entries `[K, CAP-1]` that were never encoded **behave
  > identically to true out-of-bounds**, and both they and `index >= CAP` give **silent zero on a
  > load** and are **silently dropped, with no aliasing, on a store or atomic**. Explicitly: *no
  > mirroring or aliasing risk was observed*, which is the opposite of the buffer base-slot family,
  > where an out-of-range base slot silently **aliases** a real slot (EXP-0083). Tested at
  > `CAP = 256` with `K = 8` populated canaries, with feasibility-only exploration to `N = 4096`.
  > Practical consequence: it is **safe to leave argument-buffer texture entries unbound**.
  > **Still open (both recorded DEFERRED by EXP-0106, commit `2858c20f`):** (a) behaviour at an
  > index **at or above 1,000,000** — EXP-0095 established the pattern only to index 512, and
  > confirming it at the documented ceiling is a large allocation-and-sweep campaign, not a small
  > addition; (b) the **nonresident-resource** case — no experiment in the corpus exercises a
  > texture made non-resident (`useResource:` withheld) behind a bindless index.
  > No API-rejection half was observed to separate here: the failures above are raw shader
  > behaviour, and no Metal-level rejection occurred at any tested index.
  > **Conservative driver response meanwhile:** rely on silent-zero/silent-drop only within the
  > declared `CAP`; bounds-check any index a shader could drive past the declared array size, and
  > do not assume the ceiling behaviour extrapolates from `CAP = 256` to 1,000,000.
  > M4 target; A18 deferred.
  > Evidence: `experiments/EXP-0095-m4-texture-image-matrix/RESULTS.md` (bindless rows of the
  > finite-resource table, and §"Bindless capacity beyond the declared CAP=256 array"),
  > `experiments/EXP-0106-m4-texture-isa-semantics/RESULTS.md` (TEX-19/TEX-20 deferral scope).

---

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

  > **NOT one of the 27 open items — this is a refinement that UPGRADES the existing TEX-26
  > `PARTIAL` (raw-field half) to a full answer. Splice at the orchestrator's discretion.**
  > **Answered 2026-08-28 (EXP-0136, M4/G16G, commit `2e2bc21a`) — TEX-26 raw half CLOSED: NO,
  > anisotropy is NOT limited to 16x. [HW]**
  > **The sampler hardware natively resolves anisotropy to at least 128x; Metal's 16x cap has zero
  > hardware backing.** Patching the sampler descriptor's 3-bit log2 `maxAnisotropy` field
  > (byte2 bits[4:6]) to codes 5/6/7 (= 32x/64x/128x, values the public API can never produce) and
  > sampling a hand-authored mip chain under an explicit `gradient2d` derivative gives a
  > **measured, monotonic, threshold-exact quality effect**, not merely "does not fault"
  > (16/16 cases, byte-identical across both runs):
  > at derivative ratio 16, real aniso 1/2/4/8 blur to 0.498 and real aniso 16 resolves to 1.000;
  > at ratio 64, real aniso 16 blurs (0.498) and patched 64x/128x resolve (1.000);
  > at ratio 128, only patched 128x resolves. The patched value resolves **exactly when it is
  > `>=` the ratio** — the signature a genuine unclamped anisotropic filter produces.
  > This does not contradict the previously recorded API half (EXP-M4-08, M4+A18 cross-confirmed):
  > requesting `maxAnisotropy = 32` through the public API still clamps all the way to **field 0
  > (1x)**, not to 16x. Both are true — the clamp is pure software.
  > **Finite-resource row:** sampler max anisotropy, 3-bit log2 field, **HW-usable 1x..128x, all 8
  > codes functionally distinct and correctly resolving**, Metal-exposed 1x..16x, first
  > Metal-unreachable value that works = **32x (code 5)**. An implementer may expose anisotropy
  > above 16x. Tested range: aniso codes 0-7, ratios 16/64/128 only (power-of-two ratios at the
  > code boundaries; intermediate ratios such as 20:1 or 48:1 were not swept and would refine the
  > crossover shape without changing the headline).
  > **TEX-27's raw half (lodMax field > 112, i.e. above 14.0, up to 127 = 15.875) was NOT tested by
  > this experiment and remains open.**
  > M4 target; A18 deferred. 97/97 cases per run x 2 runs, `cross_run_gate_pass: true`,
  > `issues_total: 0`.
  > Evidence: `experiments/EXP-0136-m4-unreachable-encodings/RESULTS.md` §1 and §9.

---

- **TEX-27 — Is sampler maximum LOD limited to 14.0 even when the raw field encodes values through
  15.875, and what does each above-14 encoding do?**

- **TEX-28 — Are all currently unnamed sampler address, border, swizzle, and filter encodings either
  aliases, deterministic invalid values, or additional supported modes?**

  Exhaust each finite field. Record zero/alias/fault behavior for every code instead of inferring a
  semantic limit from the values Metal happens to emit.

  > **Answered 2026-08-28 (EXP-0136, M4/G16G, commit `2e2bc21a`) — TEX-28 PARTIAL: address, border
  > and swizzle are CLOSED; the filter sub-field is not. [HW]**
  > This supersedes the "TEX-28 DEFERRED — address codes 4/6/7 and border code 3 remain untested"
  > line in the EXP-0106 block for the address and border halves.
  > **Address modes — all three unnamed codes are exact, deterministic hardware ALIASES.** A
  > 4-point signature (u = 1.2, 1.7, 2.6, -0.4; v = 0.5; `address_t = clampToEdge` throughout),
  > 32/32 cases, byte-identical across both runs: **code 4 is byte-identical to code 0
  > (clampToEdge)** at all 4 points; **codes 6 and 7 are both byte-identical to code 3
  > (clampToBorder)** at all 4 points. Not garbage, not faults, not new modes. The method has
  > proven power to see a real difference: code 5 (`mirrorClampToEdge`) in the same test shows
  > itself **genuinely distinct**, matching code 0 at 3 of 4 points and diverging at u = -0.4.
  > **The 3-bit/8-value address field is hardware-limited to exactly 5 distinct behaviours** — the
  > same 5 Metal exposes. Tested range: 8 codes x 4 UV points, all outside [0,1]; in-range u and
  > the 3D `address_r` axis were not tested.
  > **Border colour — code 3 is an exact alias to preset 0 (transparent black),** adversarially
  > confirmed across **3 different creation contexts** (samplers created transparentBlack /
  > opaqueBlack / opaqueWhite all read (0,0,0,0) when patched to code 3), 12/12 cases. The same
  > test carries its own falsifier: codes 0/1/2 read their expected preset regardless of the
  > creation-time value, so the patch — not the creation value — controls the field. **There is no
  > 4th preset and no room for an arbitrary RGBA border colour**, so Vulkan
  > `VK_EXT_custom_border_color` must be software-emulated.
  > **Swizzle — the unnamed codes are deterministic INVALID values, the one family here where the
  > hardware actively rejects rather than aliases.** Codes 0-5 reproduce the predicted channel
  > routing exactly (R, G, B, A, constant-1, constant-0), upgrading EXP-0015's DATA-TRACE-only
  > swizzle table to **HW-VALIDATED by direct construction**; **codes 6 and 7 hard-fault the
  > command buffer** (`CMDBUF_ERROR`, GPU-hang class, fault-contained, no host wedge), tested on
  > component0 (both codes) and component1 (code 6). 11/11 cases.
  > **Filter — NOT closed, and this is the item's remaining half.** EXP-0136 did not probe the
  > filter enums. From the committed descriptor map (`docs/descriptors/README.md`, EXP-0015):
  > `magFilter` is bit 23 and `minFilter` is bit 25 (1 bit each, no unnamed encodings), but
  > **`mipFilter` is a 2-bit field at bits[27:28] with only 3 named values (none / nearest /
  > linear), leaving code 3 unnamed and untested**, and **bits 24 and 26 are unassigned in that
  > table**. Also still undecoded: the MSL 4.0 per-sampler **`bias(float)` STATE field** (spec
  > §2.7), distinct from the per-instruction `bias()` operand EXP-0094 characterized — its raw bit
  > location is unknown and is a concrete probe target. Anisotropy, if counted as a filter
  > encoding, goes the other way: its unnamed codes 5/6/7 are **additional supported modes**
  > (32x/64x/128x) — see the TEX-26 refinement block.
  > **So the answer to TEX-28 as posed is "yes for three of the four sub-fields, and the
  > classification differs per field": address = alias, border = alias, swizzle = deterministic
  > invalid (hard fault), filter = UNTESTED.**
  > M4 target; A18 deferred. 97/97 cases per run x 2 runs, `cross_run_gate_pass: true`,
  > `issues_total: 0`; the descriptor-patch technique is validated by a bit-exact positive control
  > and by a disclosed prior failure mode (patching between two dispatches is silently reverted by
  > Metal's own re-bind, so patches are applied inside the single observed command buffer).
  > Evidence: `experiments/EXP-0136-m4-unreachable-encodings/RESULTS.md` §2, §3, §4, §8, §9;
  > `docs/descriptors/README.md` "Sampler descriptor — 8 bytes".

---

  > **Answered 2026-08-28 (EXP-0106, M4/G16G, commit `2858c20f`; TEX-15/TEX-16's raw half by
  > EXP-0114, commit `72c2dde8`) — TEX block.** EXP-0106: 56 cases per run x 2 runs,
  > `repeat_exact: true`, 40 match / 9 abort_confirmed / 7 rejection_confirmed / 0 deviation /
  > 0 unexpected. EXP-0114: 49/49 cases per run x 2 runs, `repeat_exact: true`, zero faults.
  > **TEX-01 DEFERRED** — Metal exposes no `sample`-with-w-divide entry point anywhere in the MSL
  > spec's texture function lists, so no compiler-emitted evidence is reachable; answering it
  > needs `op+2` bit-space fuzzing on a spliced valid `tex_sample` bundle. Not attempted.
  > **TEX-02 NO (no compiler-reachable one-op 4-offset gather)** — `gather()`/`gather_compare()`
  > take exactly one `int2 offset`; no 4-offset overload exists. `lower_tg4_offsets` remains
  > necessary. Whether the *hardware* has an unexposed native 4-offset form is deferred with
  > TEX-01/07/08.
  > **TEX-03 YES (partial-exhaustive)** — a 32x32 `r32uint` texture gathered at a fixed
  > grid-intersection with constant `int2` offsets at 12 boundary/corner points gives exactly
  > `(16+dy)*32 + (15+dx)` in every case, all 12 values pairwise distinct (`injective: true`) —
  > a clean signed affine encoding with **no aliasing** at the `[-8,+7]` extremes in both axes.
  > **Declared scope: 12 points, NOT the full 256-pair sweep.**
  > **TEX-04 YES (both halves)** — MSL accepts a non-constant, buffer-loaded, per-thread `int2`
  > offset, and a 4-thread dispatch each reading its own offset produced `[527, 466, 758, 263]`,
  > matching the corresponding constant-offset cases word-for-word. Dynamic, per-lane-divergent
  > texture offset is native — richer than the GLSL/Vulkan constant-offset convention.
  > **TEX-05 — a genuine, unexpected NEGATIVE result: `min_lod_clamp()` is functionally broken in
  > the COMPUTE stage for 3 of its 4 forms on this software stack.** Only
  > `gradient2d() + min_lod_clamp()` works end to end (sampled level tracked a runtime-supplied
  > `x` in {0,1,2,3} exactly, `0xE0..0xE3`). Standalone `min_lod_clamp()`, `bias(0)+min_lod_clamp()`
  > and `sample_compare()+min_lod_clamp()` all **deterministically crash
  > `newComputePipelineStateWithFunction:`** — not the library compile, which succeeds — with
  > `AGXMetalG16G_B0 Code=2 ... XPC_ERROR_CONNECTION_INTERRUPTED`, i.e. a compiler-service process
  > crash, reproduced 5/5 in isolation. `level()+min_lod_clamp` and `gather+min_lod_clamp` have no
  > MSL overload at all. **Software-stack finding (this macOS/Metal build), not necessarily a
  > permanent silicon limitation; fragment stage NOT tested.**
  > **TEX-06 YES** — a 4-entry bindless argument-buffer texture array queried by 4 threads at
  > genuinely non-uniform per-lane indices returned `get_width() = [8,16,32,64]` and
  > `get_num_mip_levels() = [1,2,3,4]` — every lane its own texture's true dimensions, not a
  > broadcast. `txs`/`query_levels` need no special uniform-only ABI.
  > **TEX-07 NO** and **TEX-08 NO** — no `samples_identical`-equivalent and no prefetch primitive
  > exist anywhere in the MSL spec. Conservative-false lowering / ordinary-sample selection are
  > the only options at this API surface; a hidden HW-only primitive is a separate deferred
  > opcode-fuzzing question.
  > **TEX-09 YES (no native R32G32B32 format)** — cited from EXP-0095/EXP-M4-08: no
  > `MTLPixelFormatRGB32*` constant exists, and the closed 31/96-format code table has max texel
  > size 16 bytes with no 12-byte entries at any size class. Raw device-load fallback confirmed.
  > **TEX-10 NO for general conversion / YES for packed 4:2:2** — no Y'CbCr/planar sampler
  > conversion type exists in MSL; Metal exposes YUV only as packed native formats
  > (`gbgr422`/`bgrg422`, sizeclass `0x10`). General 2/3-plane conversion must be shader ALU.
  > **TEX-11 YES (no arbitrary border beyond 3 presets)** — cited from EXP-0015/EXP-M4-08: exactly
  > 3 presets in a 2-bit field, code 3 Metal-unreachable. The two-sample clamp-to-zero/one
  > emulation (including shadow-compare) is answered **analytically** from already-HW-validated
  > building blocks, **not empirically re-confirmed here** (declared scope trim).
  > **TEX-12 DEFERRED** — needs `MTLHeap`-backed sparse textures and `updateTextureMapping:`
  > residency lifecycle; EXP-O2B decoded the sparse-tier descriptor bit but never exercised
  > `sparse_sample`/`sparse_read`/`sparse_gather` residency codes.
  > **TEX-13 PARTIAL/CLOSED with a declared remainder** — new: a 4x4x4 `r8uint` 3D texture read at
  > `z=3` returns `3`, at `z=4` returns `0` (silent zero on the depth axis specifically, first
  > tested here). Prior coverage cited from EXP-0016 / EXP-0095 (array-layer fetch-vs-sample
  > divergence: `read()` silently zeroes, `sample()`/`gather()` clamp to the last legal layer;
  > 2D/cube image OOB read+write with zero corruption). **NOT exercised: MSAA sample-index OOB**
  > (MSL exposes no compute-side per-sample write path, so the case would be indistinguishable
  > from reading never-written content — a declared harness limitation, not a result).
  > **TEX-14 YES** — a freshly generated 65-argument `[[texture(0..64)]]` kernel with all 65 slots
  > simultaneously bound to distinguishable canaries read exactly `0xD00D0000, ...0007, ...0008,
  > ...000F, ...0010, ...001F, ...0020, ...003F, ...0040` at indices {0,7,8,15,16,31,32,63,64} —
  > zero cross-talk. Combined with EXP-0095's {0,63,127}, every boundary point the gap doc names
  > is now confirmed simultaneously live.
  > **TEX-15 — the question's PREMISE is falsified; `op+4` is not a texture selector.** EXP-0114:
  > a 128-arg kernel reading only textures 5, 50 and 100 compiles to `op4_sequence: [0, 128, 0]` —
  > neither the MSL binding index nor a compacted use-order index, and the first and third reads
  > share an `op+4` value while addressing different textures. **`op+4` is a short-lived,
  > compiler-reused register/uniform-slot reference, not a per-resource identifier.** What IS
  > closed by construction: `op+4` is a **4-bit field (upper nibble, bits 7:4)** whose lower
  > nibble is inert (12/12 constructed low-nibble values at both populated slots); a full 16-value
  > splice sweep shows the 2 populated nibbles ({0x0, 0x8}) select t0/t1 and **all 14 holes give a
  > deterministic silent zero — zero faults, zero aliasing, zero garbage**. Bidirectional positive
  > control passed (`0x80 -> 0x00` gives t0+t0; `0x00 -> 0x80` gives t1+t1). A register-pressure
  > census shows the compiler itself reaching 8 of 16 nibbles at N=127. **The true 0-127
  > binding-index-to-pointer mapping lives in a PRECEDING 4-byte pointer-materialization
  > instruction (byte0 low nibble `0xb`), which is NOT decoded.**
  > **TEX-16 YES (both halves)** — compile-time: a 129-argument kernel is an MSL error (EXP-0095).
  > Raw injection: EXP-0114's 14-hole sweep IS an out-of-population selector injection at the AGX
  > instruction level — deterministic silent zero every time, never a fault or an alias.
  > **TEX-17 YES** — 16 samplers simultaneously bound (even -> `clampToZero`, odd ->
  > `clampToEdge`), all sampling the same out-of-range coordinate `u=-0.25`: every even slot read
  > exactly `0.0`, every odd slot exactly `3.0`, perfect zero-cross-talk alternation across all 16.
  > (EXP-0063's own filter-distinction probe was **falsified** — texel-center and fully-OOB UVs do
  > not discriminate filter mode — but it established the address-mode technique used here.)
  > **TEX-18 YES** — a 17-sampler kernel fails `newLibraryWithSource:` with
  > `"'sampler' attribute parameter is out of bounds: must be between 0 and 15"` — a named,
  > deterministic compile-time rejection, first tested at exactly n=17.
  > **TEX-19 / TEX-20 / TEX-21 / TEX-22 DEFERRED** — EXP-0095 GLIMG-A02 closed the *shape* of the
  > texture answer (silent zero, no aliasing, no period-256 mirroring) at CAP=256/K=8 with
  > feasibility exploration to N=4096; confirming the documented 1,000,000 / 500,000 ceilings is a
  > large allocation-and-sweep campaign not attempted. **Target-discipline note: the sampler-side
  > prior evidence (EXP-O2B, `maxArgumentBufferSamplerCount = 500000`, dynamic heap indexing for a
  > handful of entries) is A18, not M4-validated.**
  > **TEX-23 YES** — varying ONE axis at a time, the last-legal value (16384 for 1D/2D/Cube; 2048
  > for 3D-width, 3D-depth, array-length) is always accepted and `+1` always fails identically
  > with a hard `validateWithDevice:` assertion (`SIGABRT`, exit `-6`, uncatchable), for every one
  > of the 6 axes. The limits are exactly correct and **independently enforced per axis**.
  > **TEX-24 YES (both halves)** — a 16384-wide texture with `mipmapLevelCount=15` is accepted,
  > `get_num_mip_levels()` returns 15, `read()` at level 14 returns the per-level canary and at
  > level 15 returns 0. Explicit dynamic `level()`: `-5.0 -> 0`, `99.0 -> 3`, `+Inf -> 3`,
  > `-Inf -> 0`, **`NaN -> 0`** (recorded `OBSERVED_NO_ORACLE` — no a-priori prediction was
  > committed). No fault, no hang, no out-of-range index for any value. **The NaN result is a
  > third data point in EXP-0094's open NaN-polarity question: `bias(NaN)` and now `level(NaN)`
  > clamp LOW, while `gradient(NaN)` clamps HIGH.**
  > **TEX-25 — the complete creatable MSAA set is {2,4}, NOT {1,2,4}, and there is a real
  > query/creation discrepancy.** `supportsTextureSampleCount(1)` returns **true** while
  > `MTLTextureType2DMultisample` creation at sampleCount=1 always **fails**
  > (`"sampleCount must be > 1 for multisample textures."`); 3 and 8 fail with a different, generic
  > `"not supported by device"` message; 2 and 4 succeed. All rejections are hard assertion aborts
  > before any GPU submission. **A driver must not use `supportsTextureSampleCount` alone to
  > predict whether an MS-typed descriptor will be accepted.**
  > **TEX-26 / TEX-27 PARTIAL (API half closed, raw-field half deferred)** — cited from EXP-M4-08
  > (M4+A18 cross-confirmed): requesting `maxAnisotropy=32` does NOT clamp to the 16x field value,
  > it clamps all the way to **field 0 (1x)**; requesting `lodMaxClamp > 14.0` saturates the field
  > at exactly `112` (14.0), not its 7-bit maximum 127 (15.875). **The raw 3-bit aniso field
  > holding 5/6/7 and the raw 7-bit lodMax field holding >112 remain genuinely untested** — both
  > are unreachable through any public Metal call and need write-capable descriptor injection.
  > EXP-0106 adds only an interpretive cross-reference (not new evidence): TEX-24's 15-level
  > maximum means mip index 14 is the highest any Apple9 texture can have, so a 14.0 LOD ceiling
  > may simply BE the maximum addressable mip index.
  > **TEX-28 DEFERRED** — address codes 4/6/7 and border code 3 remain untested. **Newly noted:**
  > MSL 4.0 adds a per-sampler `bias(float)` STATE field (spec §2.7), distinct from the
  > per-instruction `bias()` operand EXP-0094 characterized; its raw bit location is undecoded — a
  > concrete new probe target. Successor spec is written out in EXP-0106 §2 (EXP-M4-08's explicit
  > `MTLArgumentEncoder` path fails because the sampler slot is an opaque `gpuResourceID`; the
  > direct `[[sampler(n)]]` per-stage table is the untried path).
  > Open sub-items deliberately left UNKNOWN, beyond the DEFERRED items above: TEX-03's full
  > 256-pair sweep; TEX-04's raw operand-register field for a directly assembled dynamic offset;
  > TEX-05 in the fragment stage; TEX-11's empirical border-emulation confirmation; TEX-13's MSAA
  > sample-index OOB; TEX-15's preceding pointer-materialization instruction; EXP-0114's
  > `bundle_count` undercount at N=64 (32 of 64) and N=127 (84 of 127), which is unexplained and
  > recorded as open.
  > Evidence: `experiments/EXP-0106-m4-texture-isa-semantics/` and
  > `experiments/EXP-0114-m4-texture-deferred/` (HW-PROBE + OWN-SHADER + HW splice + PUBLIC MSL
  > spec API-surface checks; M4 target; A18 deferred).

---

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

  > **Answered 2026-08-28 — ATOM block. ATOM-01..06: EXP-0085, commit `2e693a58`. ATOM-07..11:
  > EXP-0093, commit `d3e7d1ba`** (which is EXP-0085's own named successor — EXP-0085 recorded
  > ATOM-07..11 as DEFERRED and they were closed by the later fence/barrier campaign).
  > **ATOM-01 YES — HW-VALIDATED.** Device atomic subtract has its own op selector `0x1b`,
  > distinct from add's `0x10` and from every other op, confirmed structurally (a single
  > `atomic_mem` instruction, no negate-then-add ALU pre-step) and functionally (per-slot finals
  > match `(init - delta) mod 2^32` exactly). Every M4 device selector equals exactly HALF the
  > corresponding EXP-0018 A18 `byte+12` value — the same hardware field at a different DB bit
  > offset, not a different encoding.
  > **ATOM-02 YES — HW-VALIDATED.** `atomic_tg` is a distinct instruction FORM (`byte+1` mode bits
  > `0x03` vs `0x01`/`0x11`) that reuses the identical op-selector encoding; the one-threadgroup
  > contention test (N=256, own-slot and shared-slot) matches the combine-order-independent
  > invariant exactly for add/sub/min/max.
  > **ATOM-03 YES — HW-VALIDATED, two independent invariant forms.** Own-slot (no contention):
  > every `old_out[i]` equals the init value exactly. Shared-slot (real contention to N=65536):
  > the multiset `{old_out} U {final}` equals exactly `{deltas/tags} U {init}` for every
  > RMW/exchange case — a bijective linearizable-history proof (no duplicate "old", no lost delta).
  > **ATOM-04 YES — HW-VALIDATED under real contention.** Uniform-address compare-exchange at
  > N=65536 (device) / N=256 (threadgroup): exactly ONE lane succeeds, the final value equals that
  > winner's tag, and every losing lane's observed `old` equals that same final value (never torn).
  > Structurally a **single** `atomic_mem[cmpxchg]` (selector `0x12`) with no backward branch —
  > no software retry loop.
  > **ATOM-05 YES, with a sharpened boundary — HW-VALIDATED.** The uniform-address SIMD
  > pre-combine (`simd_reduce -> elect -> atomic_rmw -> broadcast -> rebuild`) is applied and
  > functionally exact for every reducible op (add, xor, min, and by EXP-0018 or/max) — **but only
  > when the compiler can prove the address uniform at COMPILE time.** A data-dependent address
  > that merely happens to be runtime-uniform (loaded from an all-zero index buffer) is NOT
  > optimized; it takes the same per-lane path as a genuinely varying index. This is a sharper
  > boundary than EXP-0018 established.
  > **ATOM-06 YES — HW-VALIDATED structurally.** The pre-combine is unconditionally DISABLED for
  > exchange and compare-exchange even at a compile-time-provable uniform address — the compiler's
  > own codegen, not merely absence of a counterexample, shows the optimization is scoped to
  > reducible ops. The optimization is semantically invisible either way: every functional
  > invariant held identically with and without the reduce path.
  > **ATOM-07 YES — HW-VALIDATED (relaxed atomics carry NO implicit device fence).** Cross-core
  > message passing with fully relaxed atomics shows large-magnitude reproducible payload
  > corruption once concurrency exceeds ~4 producer/consumer pairs — **up to 100% of messages
  > corrupted** (`PAIRS=4` RR: 200/200 mismatches, both runs). At `PAIRS=1` no violation is
  > observed in any configuration, which **explains rather than contradicts** EXP-0051's earlier
  > null result: 1-2 threadgroups are too small a footprint to expose cross-core reordering.
  > Structurally, `memory_order_relaxed` emits no `0x07`-family op at all.
  > **ATOM-08 YES, but ONLY for SYMMETRIC fencing — HW-VALIDATED.** Both sides fenced (FF) is the
  > only configuration with **zero** mismatches at every tested scale (12/12 cells across both
  > runs). **Neither asymmetric configuration is a safe substitute:** producer-only (FR) and
  > consumer-only (RF) both still corrupt at `PAIRS>=4` (98% in all four `PAIRS=4` cells; 49-74%
  > at `PAIRS=8`). A compiler must emit the device-scope fence on BOTH the release and the acquire
  > side.
  > **ATOM-09 YES, and more strongly than the question implies: convergence is UNCONDITIONAL.**
  > `threadgroup_barrier(mem_none)` compiles to the identical instruction shape
  > (`07 04 54 41 09 00`) as `mem_threadgroup`/`mem_device` — NOT to "no instruction" — and still
  > provides full execution convergence and threadgroup-memory visibility (0/256 mismatches vs.
  > 128/256 for the no-barrier control). The `mem_scope` tag governs only which ADDITIONAL memory
  > class is fenced. **Note this is not in tension with SIMD-06: `simdgroup_barrier` is the op that
  > can compile away, `threadgroup_barrier` is not.**
  > **ATOM-10 YES, and the exact bit is identified — HW-VALIDATED BIDIRECTIONALLY.** `byte+3` bit0
  > (`0x85` barrier-with-fence vs `0x84` fence-only) is the execution-convergence enable bit:
  > splicing it OFF on a real barrier reintroduces the exact 128/256 no-barrier race; splicing it
  > ON on a real fence-only op (which races 128/256 on its own) eliminates the race entirely
  > (0/256), on an otherwise byte-identical instruction stream. A device-scope barrier and a
  > standalone device fence are NOT interchangeable at the encoding level. This upgrades
  > `tools/agx-isa/db.json`'s `mem_fence` entry from `inferred (byte-diff)` to `HW-VALIDATED`.
  > **ATOM-11 NO — HW-VALIDATED NEGATIVE; a distinct image/texture barrier legalization path IS
  > required.** Two independent demonstrations: (1) fragment raster-order-group protection uses a
  > dedicated acquire/release `pixel_order` pair (`byte+4=0x06`) for a TEXTURE resource but a
  > bracket-open-pair mechanism (shared with the ROG-index encoding, not a dedicated fence) for a
  > device BUFFER resource — each splice-proven causally load-bearing in its own case, and the two
  > are not interchangeable; (2) compute-side, a standalone `mem_texture` fence compiles to a
  > genuine two-instruction acquire/release PAIR, structurally unlike the single-instruction
  > `mem_device`/`mem_none`/`mem_threadgroup` forms.
  > **Operand-width / return-form findings folded in (EXP-0085):** 32-bit has the full op set with
  > a return form in both scopes; 32-bit float exposes only `fetch_add`; **64-bit exposes ONLY the
  > void, no-return `atomic_min/max_explicit` — there is no return-value-producing 64-bit atomic
  > RMW anywhere in this MSL surface** (`fetch_add`, `fetch_min/max`, even `atomic_load` on
  > `atomic_ulong` are all compiler-rejected). `atomic_store_explicit` and a return-discarded
  > `atomic_exchange_explicit` compile to **byte-identical** `atomic_mem[xchg]` instructions — the
  > "no-return store" is not a separate hardware operation. Only `memory_order_relaxed` is accepted
  > on an RMW call site (`seq_cst` rejected, `acq_rel` undeclared) — a language-exposure fact, not
  > a hardware ordering answer.
  > Open sub-items deliberately left UNKNOWN: ATOM-01's `and`/`or`/`xor`/`smin`/`smax` threadgroup
  > selectors were confirmed functionally but not separately re-tokenized; the raster-order-group
  > index `N` silently aliases to group 0 beyond `N` in {0,1,2} (a finite-resource limit with no
  > rejection); MSAA per-sample ROG granularity, multiple render targets, ROG nesting/repetition,
  > and discard/demote release-on-every-exit-path are all `UNKNOWN` (a build-time attempt at the
  > last was inconclusive — full-body compiler reshuffling defeated a prefix/suffix byte-diff);
  > forward-progress/deadlock behaviour under malformed ROG sequences is untested; a
  > `scoreboard_fence kind=0x22` seen around the SIMD-reduce election machinery is recorded as raw
  > evidence and explicitly NOT interpreted.
  > Evidence: `experiments/EXP-0085-m4-memory-interlock-atomics/` and
  > `experiments/EXP-0093-m4-fence-barrier-interlock/` (HW-PROBE + OWN-SHADER + HW splice +
  > STRUCTURAL; M4 target; A18 deferred).

---

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

  > **Answered 2026-08-28 (EXP-0111, M4/G16G, commit `9739d612`) — FS block.** 56 cases per run,
  > two runs, every `*.gated.json` record byte-identical; zero GPU faults, hangs, command-buffer
  > errors or host wedges across 112 case executions.
  > **FS-01 YES — HW splice, decisive.** `get_sr 0xa0` returns the fragment's integer pixel X and
  > `0xa1` the integer pixel Y. A single-pixel-coverage triangle writing fixed buffer slots gave
  > baseline `(x=2.5, y=1.5)`; splicing the first `get_sr`'s SR-select byte `0xa0 -> 0xa1` gave
  > `(1.5, 1.5)` and splicing the second `0xa1 -> 0xa0` gave `(2.5, 2.5)` — a clean mutual swap.
  > The compiler emits `cvt_i2f_src` immediately after, i.e. it treats the SR value as an INTEGER.
  > A backend can implement `load_pixel_coord` as a direct SR read with no conversion; the `+0.5`
  > float centre convention is the compiler's own downstream arithmetic, not the SR's value.
  > **FS-02 YES in both senses.** At N=2 and N=4 every per-sample invocation of a given pixel read
  > IDENTICAL raw `pos.xy` bits (0 deviations across 8+16 sample-invocations). A never-covered
  > ORIGINAL helper, relayed out via `quad_shuffle_xor`, read exactly `(1.5, py+0.5)` — the true
  > extrapolated grid coordinate, not zero, frozen or garbage.
  > **FS-03 PARTIAL.** Pixel-centre convention and axis origin are CLOSED: centre = `px+0.5`,
  > `py+0.5` (FS-01); origin is **UPPER-LEFT with y increasing DOWNWARD** (a triangle covering
  > NDC `y<0` colours framebuffer rows 2-3 of a 4x4; NDC `x<0` colours columns 0-1) — HW-confirmed
  > rather than asserted from documentation. **Exact raw MSAA sample POSITIONS remain UNKNOWN:**
  > MSL exposes no `gl_SamplePosition`-equivalent, so they cannot be queried through the public
  > API; a `gl_SamplePosition`/`VK_EXT_sample_locations` consumer must treat them as UNKNOWN
  > rather than assume any standard grid.
  > **FS-04 YES — decisive.** A step function differenced with `dfdx`/`dfdy` on a 4x4 target:
  > splitting WITHIN a quad column-pair gives `d=1000.0` for columns {0,1} and `0.0` for {2,3};
  > splitting exactly BETWEEN quad column-pairs gives `d=0.0` for **all 16 pixels** — the global
  > step is entirely invisible. Y axis identical, transposed. This is genuine 2x2-quad-scoped
  > computation, not merely "some neighbouring-pixel difference".
  > **FS-05 NO at the API/compiler surface; UNKNOWN at the ISA level.** MSL exposes exactly one
  > derivative granularity per axis — no `dFdxCoarse`/`dFdxFine` pair — so **no MSL-level probe can
  > distinguish "the hardware has one mode" from "the hardware has a second mode Metal never
  > emits"**; there is no compiler-reachable starting point to perturb. An undirected blind-bit
  > sweep of the `0x37` op's unexplored `byte+7/+8/+9` was explicitly declined as unfalsifiable.
  > Lower `fddx_coarse` and `fddx_fine` to the SAME primitive.
  > **FS-06 YES for both tested lane categories.** Demoted lanes: cited from EXP-0091 (a surviving
  > lane's `fwidth()` read exactly `999.0`, matching the discarded neighbour's post-discard
  > `+1000` mutation). Original never-covered helpers (this experiment's remainder, closing a gap
  > EXP-0091 explicitly flagged): the live lane's `dfdx(pos.x)` read exactly `1.0` at all 4 tested
  > rows. No separate legalization path is needed for the two helper categories.
  > **FS-07 YES (`scalarize_ddx = true`).** `dfdx()` on float1/2/3/4 with algebraically independent
  > components produced EXACTLY 1, 2, 3, 4 instances of the 10-byte `0x37`/`byte+2==0x54` op; a
  > combined `dfdx+dfdy` on float4 gave 8. Every instance handles one scalar component; no vector
  > width modifier was ever observed. **Genuine anomaly reported, NOT resolved:** every dfdx-ONLY
  > kernel (5/5, no `dfdy` anywhere in source) emitted axis byte `0x90` — not `0x92` as
  > `docs/isa/encoding-tables.md`'s "0x92=dfdx / 0x90=dfdy" labelling predicts — while a
  > ground-truth kernel calling both in one shader (HW-verified readback `[1.0, 0.0, 0.0, 1.0]`)
  > shows `0x92` for both dfdx calls and `0x90` for both dfdy calls. **The axis byte correlates
  > with call-site identity only when both appear in the same program.** Flagged for the `docs/isa`
  > owner as a correction candidate: the current table entry is INCOMPLETE, not simply wrong.
  > **FS-08 YES, with a significant API-behaviour anomaly.** Flat/smooth/no-perspective cited from
  > EXP-0029. New: centroid genuinely differs from centre under partial coverage (a pixel covered
  > by exactly 2 of 4 samples with its geometric centre provably outside the covered region read
  > `v_center = 0.0039215...` — within ~1/255 of the true unclamped extrapolated 0.0 — vs.
  > `v_centroid = -0.24705886...`). **`interpolate_at_offset` VIOLATES its documented contract:**
  > across >=17 offsets in X-only, Y-only and combined sweeps, every measured value matches, to
  > sub-ULP, the plane evaluated at an **absolute pixel-local coordinate equal to `(dx,dy)`
  > directly** — origin at the pixel's TOP-LEFT corner, y DOWNWARD — not MSL's documented signed
  > offset from the pixel CENTRE. `interpolate_at_offset(float2(0,0))` reads `-1.0` where
  > `interpolate_at_center()` and `center_perspective` both read `0.0` **in the same shader on the
  > same value** (the internal control ruling out a harness bug). No clamping or wraparound up to
  > `|offset| = 2.0`. **A backend must transform `(dx,dy) -> (dx+0.5, 0.5-dy)` (or equivalent)
  > before calling it.** Whether this is hardware wiring or an AIR->AGX backend bug on this
  > toolchain is not distinguished. **PARTIAL:** `sample` vs `centroid` were not behaviourally
  > separated from each other (EXP-0029's structural byte-diff `byte+7` `0x01` vs `0x03` is the
  > only evidence for that sub-claim).
  > **FS-09 YES — convergent interpolation is NOT provably bit-identical to flat.** Across 5
  > `(w0,w1,w2,attr)` configurations with an identical attribute at all 3 vertices, no-perspective
  > interpolation diverged from flat in 3 of 5 configurations (16/16 pixels each, 1-2 ULP);
  > perspective matched flat bit-exactly in 80/80 sampled pairs (a narrower observation, not
  > proven universal, and NOT a licence to fold it to flat either).
  > `nir_io_always_interpolate_convergent_fs_inputs` is justified and necessary. **Open curiosity
  > flagged, not chased:** config D (uniform w) shows no linear divergence despite sharing config
  > A's exact attribute value, and no-perspective interpolation is mathematically w-independent —
  > this w-dependence of its rounding is unexplained.
  > **FS-10 YES.** `arr[px%4]` with a runtime, non-foldable index gave exactly `[10,11,12,13]` for
  > `px=0..3`. The compile-scan shows an `icmp_pred`+`sel` ALU pair after the varying-read block
  > and ordinary fixed-slot `iter`/`iter_flat` instructions — no register-sourced slot field in
  > either the dynamic or the static-index control. Lower as "materialize every candidate via its
  > normal static interpolation instruction, then select", with no change to interpolation mode or
  > provoking-vertex behaviour. (A minor unexplained duplication — `iter_flat` count 2 for one
  > declared flat varying — is flagged, not load-bearing.)
  > **FS-11 YES for both sub-claims; PARTIAL on the ISA mechanism.** `struct FOut { float4
  > colors[2]; }` as a fragment return type is REJECTED (`"invalid return type 'FOut' for fragment
  > function"`) — MSL has no grammar path to even attempt a dynamically-indexed fragment output.
  > The branch-unrolled workaround with a genuinely per-fragment-DIVERGENT selector
  > (`(uint)pos.x & 1`) is correct on hardware: pixel(0,0) -> RT0 red / RT1 clear, pixel(1,0) ->
  > RT0 clear / RT1 green, exact 2/2 pixels x 2/2 RTs. **Structurally surprising and left
  > UNKNOWN:** the compiled program contains only **ONE** `frag_color_store` (`rt_index_bytes=[0]`,
  > `store_count=1`) and TWO `frag_tile_setup` brackets with selector bytes `0x0` and `0xc` (the
  > latter outside EXP-0029's `0x0`/`0x4`/`0x8` static-MRT table), yet both RTs receive correct
  > per-fragment-divergent data. Whether that is a genuine dynamic RT selector or an unmodelled
  > static encoding was NOT bit-decoded.
  > **FS-12 YES for every channel where a shader-driven write exists; PARTIAL for stencil.**
  > Color/depth/buffer/atomic cited from EXP-0091. New: a demoted lane's `[[sample_mask]]=0xF`
  > write is suppressed just as completely — the discarded pixel resolves to exactly `0.0` (fully
  > clear) while the survivor reads exactly `1.0`, with no partial mask leakage. **Stencil is
  > explicitly INFERRED, not HW-validated:** MSL exposes no fragment-writable stencil output at
  > all (only `[[color(n)]]`, `[[depth(qualifier)]]`, `[[sample_mask]]`), so there is no API
  > surface to attempt it; do not cite stencil suppression as HW-VALIDATED downstream.
  > Open sub-items deliberately left UNKNOWN: FS-03's exact MSAA sample positions; FS-05's
  > ISA-level coarse-mode question; FS-07's `0x90`/`0x92` axis-byte rule; FS-08's sample-vs-centroid
  > behavioural separation and the hardware-vs-compiler-bug attribution for `interpolate_at_offset`;
  > FS-09's config-D anomaly; FS-10's extra `iter_flat`; FS-11's single-store mechanism;
  > FS-12's stencil channel.
  > Evidence: `experiments/EXP-0111-m4-fragment-semantics/` (HW-PROBE + OWN-SHADER + HW splice +
  > encode/decode round trip; M4 target; A18 deferred).

---

## P1 — Transcendental and special-function semantics

- **TRIG-01 — Is the complete operand and modifier encoding of the native trigonometric/reduced-range
  primitive hardware-validated?**

  > **Answered 2026-08-28 (desk audit of `tools/agx-isa/validation.json` against EXP-0103) —
  > TRIG-01 NO and TRIG-02 NO. [DESK-AUDIT]** (One block answers both; TRIG-02's own last line is
  > not unique in the file.)
  > **Neither the trigonometric/reduced-range primitive nor the `0x2b` range-reduction operation
  > has a single hardware-run operand or modifier field.** Per-field state, from the labelling
  > standard in `docs/evidence-classification.md`:
  > `tex_coord_setup` — the 10-byte `0x?b`-leader member of the `0x2b`/`0x3b`/`0x5b` register/
  > shift-prep family, which is the op `docs/isa/README.md` identifies as the range-reduce step in
  > `sin`/`cos`/`tan` (`a 0x2b reduce op + quadrant select`, then an fma polynomial): instruction
  > level `corpus-correlation` (M4, EXP-M4-13, "polymorphic 10-byte 0x2f form located over the
  > own-MSL corpus"); `srcA`, `form` and `idx` `corpus-correlation`; `dst_lo`, `b1`, `subop`, `b5`,
  > `b6`, `b8`, `b9` all **`untested`**.
  > `shift_amt_move` (the 4-byte member of the same family): every field `corpus-correlation`
  > except `op_desc`, which is `untested`.
  > `sfu_marker`: `tokenization-only` — "byte-invariant 2-byte token (06 02); **exact micro-op NOT
  > characterized**".
  > `fspecial_est` (the SFU seed op): instruction level `isolated-byte-diff` (A18, EXP-0026) and
  > `subop` `corpus-correlation` (`0x09` rcp / `0x0b` rsqrt / `0x0d` sqrt); `dst` `untested`;
  > `srcA`, `b4`, `b5` `tokenization-only`.
  > This is consistent with what EXP-0103 (M4/G16G, commit `bbb1e9fc`) itself recorded: its TRIG-03
  > and TRIG-04 answers are **PARTIAL — structural (198 vs 238 bytes), not field-level**, and its
  > limitations section states outright that *"TRIG-01/02 (full encoding of the trig primitive and
  > the `0x2b` range-reduction op) ... were not attempted"*. Nothing in the corpus has since
  > attempted them.
  > **Consequence for an emitter:** under the `emittable` rule, both ops are **decodable, not yet
  > emittable**. A backend must not synthesize a range-reduction op with chosen operands; it must
  > lower `sin`/`cos`/`tan` through the ordinary ALU/SFU sequence whose *numerics* EXP-0103 did
  > establish (`precise::` accurate to <= 2 ULP up to `FLT_MAX`; `fast::` correct only below a
  > cliff located at `(6587824, 6588825]` and a total failure above it; `fast::sin(NaN) = +0` vs
  > `precise::` propagating qNaN). Flipping TRIG-01/02 to Yes requires field-level splice-and-observe
  > on the `0x2b` family, on M4.
  > A18 target for `fspecial_est`'s one executed level; M4 target for the corpus locations; **no
  > operand field of either op is executed on either target.**
  > Evidence: `tools/agx-isa/validation.json` (`tex_coord_setup`, `shift_amt_move`, `sfu_marker`,
  > `fspecial_est`), `experiments/EXP-0103-m4-fp-transcendental-semantics/RESULTS.md` (TRIG-03/04
  > and Limitations), `docs/isa/README.md` (`0x2b` family, sin/cos/tan lowering).

---

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

  > **Answered 2026-08-28 (EXP-0103, M4/G16G, commit `bbb1e9fc`) — TRIG block.** Two runs, 47/47
  > cases byte-identical.
  > **TRIG-01 / TRIG-02 DEFERRED, as pre-registered.** Not attempted: the full operand/modifier
  > encoding of the native trig primitive and of the `0x2b` range-reduction op require field-level
  > splice validation beyond black-box MSL execution. `docs/isa/encoding-tables.md` already marks
  > the `0x2b` op's internals `INFERRED`.
  > **TRIG-03 / TRIG-04 PARTIAL, upgraded to HW-leaning STRUCTURAL — still short of a field-level
  > proof.** Numeric: a kernel feeding one `x` to both `fast::sin(x)` and `fast::cos(x)` is
  > self-consistent (380/400 exact; the 20 divergences are the TRIG-06 cliff, not a sharing
  > artifact). Structural: the shared-input kernel compiles to **198 bytes** vs **238 bytes** for
  > an otherwise-identical kernel taking two independent inputs — 40 bytes less work when sin and
  > cos of the same value are requested together, consistent with (but not proof of) a shared
  > range-reduction stage.
  > **TRIG-05 CHARACTERIZED — and `fast::` and `precise::` behave very differently.**
  > `precise::sin`/`cos`: **<=2 ULP over the entire tested range up to and including FLT_MAX**
  > (+/-3.4e38) — no accuracy cliff anywhere in the corpus (specials, magnitude sweep 2^-4..2^128,
  > 300 random samples); `sin` ULP histogram over 1294 samples is `{0: 972, 1: 302, 2: 8}`.
  > `fast::sin`/`cos`: **<=2 ULP for |x| <~ 6.588e6, then identically +/-0 for every input at or
  > above that threshold** (and for every NaN/Inf input). A 501-point dense follow-up sweep
  > (supplementary, outside the two-run contract) bracketed the transition to
  > **(6587824.0, 6588825.0]** — ~0.015% relative resolution. No relationship to a power of two or
  > a simple multiple of pi was found by inspection.
  > **TRIG-06 YES, for `fast::` only.** Every `fast::sin`/`fast::cos` input at or above ~6.588e6
  > returns exactly `+/-0` regardless of the true value — a total accuracy failure for that entire
  > half-line, not merely reduced accuracy. `precise::` shows no such failure anywhere tested up to
  > FLT_MAX. **This REFINES the CITED A18 result EXP-0026**, which reported `sin(2*pi)` error
  > ~5e5 ULP without separating fast from precise or locating a cliff. A software large-argument
  > reducer is required for `fast::`.
  > **TRIG-07 PARTIAL, as pre-registered.** Achieved accuracy over the reduced interval (small
  > |x|, e.g. |x|<10) is <=1 ULP for both namespaces — numerically the polynomial meets a tight
  > bound in range. **Exact coefficient bit patterns and evaluation order were deliberately NOT
  > extracted** (that would mean transcribing a compiler-generated fma chain, which clean-room
  > rule 5 forbids); `docs/isa/encoding-tables.md` flags them `not reconstructed`.
  > **TRIG-08 YES, fully characterized — and it is a genuine finding, not merely "expected NaN".**
  > `sin(+/-0) = +/-0` and `cos(+/-0) = +1` for both namespaces, matching the reference exactly.
  > **`fast::sin(NaN) = fast::sin(+/-Inf) = +0` — NOT NaN** (same for `cos`), while
  > `precise::sin(NaN) = precise::cos(NaN) = precise::sin(+/-Inf) = canonical qNaN 0x7FC00000`.
  > `precise::` propagates NaN correctly; `fast::` does not. Subnormal inputs behave as ordinary
  > small |x| with no distinct subnormal-specific behaviour.
  > **TRIG-09 PARTIAL, as pre-registered, but the numeric evidence is unusually strong.**
  > `sin_fast_f16`/`cos_fast_f16`: **1496/1552 exact against a correctly-rounded FP16 reference,
  > `max_ulp = 0`** — every finite non-special FP16 sin/cos in the corpus is exactly correctly
  > rounded; all 56 divergences are the same NaN/Inf -> `+0` special case seen in FP32. Fully
  > consistent with "compute at FP32 accuracy, narrow once", but the mechanism (vs. a native
  > FP16-width reduction that happens to also be exact) was not independently verified.
  > **TRIG-10 NO on this M4 — this UPDATES the CITED A18 result EXP-0026.** Numerically, `sin`
  > 742/1294 and `cos` 740/1294 outputs are identical between namespaces — i.e. the majority
  > differ. Structurally, compiled AGX byte lengths differ substantially (`sin`: 136 B fast vs
  > 456 B precise; `cos`: 138 B vs 462 B — precise is >3x longer) and the byte sequences diverge
  > **from the very first instruction**, not merely in a longer tail. Most divergence is the
  > NaN/Inf/cliff special-case handling plus a smaller population of ordinary 1-2 ULP in-range
  > differences. EXP-0026's A18 claim was evaluated on a much narrower input set and plausibly
  > never exercised this control flow — the two are not necessarily contradictory, **but the
  > driver-facing conclusion on M4 must be "not interchangeable", not "byte-identical".**
  > Open sub-items deliberately left UNKNOWN: TRIG-01/02 entirely; TRIG-03/04's field-level proof
  > of range-reduction sharing; TRIG-07's coefficients and evaluation order (deliberately, per
  > clean-room rule 5); TRIG-09's mechanism; the sin/cos cliff threshold is bracketed to ~1000 out
  > of ~6.59M, not pinned to the exact bit; FP16 `sin`/`cos` used a ~1500-point stratified sample,
  > not the 65536-point enumeration applied to `rcp`/`rsqrt`/`sqrt`.
  > Evidence: `experiments/EXP-0103-m4-fp-transcendental-semantics/` (HW-PROBE + OWN-SHADER +
  > PUBLIC MSL function names; M4 target; A18 deferred).

---

- **SFU-01 — Are reciprocal, reciprocal-square-root, square-root, exp2, log2, floor, ceil, trunc,
  and round each independently selectable in the native special-function family?**

- **SFU-02 — Are the result semantics and special cases of every SFU selector hardware-validated?**

- **SFU-03 — Is the reciprocal/rsqrt estimate seed deterministic for every input bit pattern and
  floating-point mode?**

- **SFU-04 — Does the target precise reciprocal sequence require exactly two refinement iterations
  to achieve its claimed result accuracy?**

  > **Answered 2026-08-28 (confirmation of EXP-0103's recorded disposition) — SFU-04 remains
  > DEFERRED, and the block is a clean-room rule, not an effort gap. [DECISION, not evidence]**
  > **The question as posed asks us to count the refinement iterations in Apple's
  > compiler-generated reciprocal sequence. That is exactly what `CLAUDE.md` FORBIDDEN rule 5
  > prohibits** — "do not lift long compiler-generated instruction sequences and present them as an
  > algorithm to copy". EXP-0103 (M4/G16G, commit `bbb1e9fc`) pre-registered SFU-04 as `DEFERRED`
  > for this reason and recorded it as **the sole `DEFERRED` item** in its 31-item scoring
  > (`DEFERRED = 2 (TRIG-01,02; SFU-04, counted once)`), noting that EXP-0026's A18 answer is *"an
  > inferred precision-doubling argument (8 -> 16 -> >= 24 bits), explicitly not a literal
  > instruction count"*. **This wave confirms that reading and does not work around it.**
  > **The two hardware facts that let an implementer answer the underlying engineering question
  > themselves, without us transcribing anything:**
  > (1) the **seed accuracy** — `fspecial_est` delivers a **~7.5-8 mantissa-bit** Newton-Raphson
  > seed for rcp/rsqrt/sqrt (EXP-0026, A18, `isolated-byte-diff`); and
  > (2) the **final accuracy that must be reached** — `precise::rcp` on FP32 is **0 ULP over the
  > normal range**: 1856/1886 corpus values bit-exact, and all 30 mismatches are subnormal,
  > DAZ+FTZ-explained (**0 normal-range divergences**); `fast::rcp` by contrast is 1742/1886 with
  > 114 normal-range divergences at max 1 ULP (EXP-0103, M4, HW). Determinism is
  > proven black-box: **47/47 cases, every input in every case, byte-identical between run01 and
  > run02**, including all 65536x4 rcp/rsqrt FP16/FP32 fast+precise combinations.
  > From (1) and (2) an implementer derives their own iteration count for their own sequence
  > (each Newton-Raphson step roughly doubles the correct mantissa bits, so reaching fp32's 24
  > requires two from a ~8-bit seed) — **that derivation is theirs to make, and it is not a
  > transcription of Apple's code.** We state the hardware endpoints; we do not state Apple's
  > sequence.
  > Also recorded and carried: `rcp`/`rsqrt`/`sqrt` share division's DAZ+FTZ model **exactly**
  > (184/184 divergences predicted, zero residual), and FP16 SFU **neither DAZs nor FTZs** across
  > all 65536 patterns — so the FP32 flushing is a datapath property, not a global mode.
  > **This item needs a decision (accept the reframing above, or close it as permanently
  > out-of-scope), not more evidence.** Recommendation: mark SFU-04 **OUT-OF-SCOPE (clean-room
  > rule 5)** in the questionnaire, with facts (1) and (2) as the documented substitute, rather
  > than leaving it as an open experimental gap that implies a future experiment could close it.
  > M4 target for the accuracy and determinism results; A18 target for the seed-accuracy result.
  > Evidence: `experiments/EXP-0103-m4-fp-transcendental-semantics/RESULTS.md` (SFU-03/SFU-04
  > entries, accuracy table, Limitations), `experiments/EXP-0026-transcendentals/`,
  > `tools/agx-isa/validation.json` (`fspecial`, `fspecial_est`), `CLAUDE.md` FORBIDDEN rule 5.

---

- **SFU-05 — Does precise square root require a final correction distinct from simply
  `x * precise_rsqrt(x)`?**

- **SFU-06 — Does precise division require a remainder correction distinct from
  `a * correctly_rounded_rcp(b)`?**

- **SFU-07 — Are exp2/log2 error bounds and exceptional-value behavior sufficient for the source
  APIs without an additional software correction path?**

  > **Answered 2026-08-28 (EXP-0103, M4/G16G, commit `bbb1e9fc`) — SFU block.** Two runs, 47/47
  > cases byte-identical.
  > **SFU-01 YES** — all nine (rcp, rsqrt, sqrt, exp2, log2, floor, ceil, trunc, round) compile,
  > dispatch and produce correct-shaped results as distinct MSL builtins/namespace calls.
  > **SFU-02 YES** — every SFU case's corpus includes the shared directed special block (+/-0,
  > +/-Inf, canonical/payload/signaling-pattern NaN, min/max subnormal, min/max normal); results
  > are itemized per function.
  > **HIGH-VALUE result: `rcp`/`rsqrt`/`sqrt` share division's DAZ+FTZ model exactly.** Every one
  > of `precise::rcp`/`rsqrt`/`sqrt`'s 30 / 77 / 77 divergences from a correctly-rounded IEEE-754
  > reference is subnormal-related, and **every one of those 184 divergences is exactly predicted
  > by the same DAZ+FTZ substitution model EXP-0074 found for division** (flush a subnormal
  > operand to signed zero before the op; flush a correctly-rounded subnormal result to a signed
  > zero). **Zero unexplained divergences; zero divergences at all outside the subnormal classes**
  > (1856/1886, 1809/1886, 1809/1886 exact). This closes `encoding-tables.md`'s `fspecial_est`
  > UNKNOWN flag for these three: their precise path IS correctly rounded, subject to the identical
  > DAZ+FTZ carve-out as division.
  > **`exp2`/`log2` have NO refined path at all** — categorically different, on two independent
  > kinds of evidence. `fast::` and `precise::` produce **byte-identical FP32 output for all 1362
  > cases each (0 differences)**, and their **compiled AGX byte streams are identical too (46 bytes
  > each)**. `precise::exp2`/`log2` is the same single SFU-estimate instruction as `fast::`.
  > Subnormal *inputs* still read as zero (1/1 and 73/73 subnormal-involving divergences match the
  > DAZ input-flush prediction), but there is no correctly-rounded result to flush, so FTZ is not
  > separately observable here.
  > **FP16 is a clean contrast:** `rcp`/`rsqrt`/`sqrt` (fast + precise) tested **EXHAUSTIVELY over
  > all 65536 bit patterns** show **zero** mismatches against a correctly-rounded non-flushing
  > reference — including 4094/4094 cases whose correctly-rounded result is a genuine FP16
  > subnormal, returned unflushed. **FP16 SFU ops neither DAZ nor FTZ; FP32 SFU ops do both.**
  > **SFU-03 PARTIAL, as pre-registered, with a comprehensive black-box determinism proof.**
  > **47/47 cases — every input in every case — byte-identical between run01 and run02**,
  > including all 65536x4 `rcp`/`rsqrt` FP16/FP32 fast+precise combinations. At the OUTPUT level
  > this hardware is deterministic for every bit pattern tested. Direct estimate-REGISTER readback
  > (proving the seed itself, pre-refinement, is deterministic — as CITED A18 EXP-0026 did via
  > splice) was NOT repeated on M4.
  > **SFU-04 DEFERRED, as pre-registered.** EXP-0026's A18 answer is an inferred
  > precision-doubling argument (8 -> 16 -> >=24 bits), explicitly not a literal instruction count
  > (clean-room rule 5). This experiment's 0-ULP precise-`rcp` result is *consistent* with
  > sufficient refinement but does not count iterations.
  > **SFU-05 YES (upgraded PARTIAL -> HW).** `precise::sqrt` is not simply `x * precise_rsqrt(x)`:
  > computed from the same `x` in the same dispatch, 1656/1884 identical, **228 differ**. Beyond
  > the trivial `x=0` structural case (9 instances), genuine non-trivial divergences exist for
  > ordinary finite `x` — e.g. `x=0x7F7FFFFE`: `sqrt = 0x5F7FFFFF` vs `x*rsqrt(x) = 0x5F800000`,
  > exactly 1 ULP apart.
  > **SFU-06 YES (upgraded PARTIAL -> HW).** `precise::divide` requires a correction beyond
  > `a * correctly_rounded_rcp(b)`: from the same `(a,b)` in the same dispatch, **650/820
  > identical, 170 (20.7%) differ, uniformly by exactly 1 ULP**. Since `precise::divide` is itself
  > 0-ULP correctly rounded (DAZ+FTZ aside) while `a * precise::recip(b)` is not always equal to
  > it, the divide path does something beyond reciprocal-then-multiply for ~1 in 5 random inputs —
  > consistent with CITED A18 EXP-0026's separate "remainder correction" finding.
  > **SFU-07 NO — bounded but never correctly rounded, in EITHER namespace.** `exp2`: <=1 ULP
  > always (1308/1362 exact, `max_ulp=1`). `log2`: <=2 ULP always (1036/1362 exact, `max_ulp=2`).
  > A consumer requiring correctly-rounded `exp2`/`log2` cannot rely on either namespace; 1-2 ULP
  > is the hardware ceiling. Special cases all matched exactly (`exp2(NaN)=NaN`,
  > `exp2(+Inf)=+Inf`, `exp2(-Inf)=+0`, `log2(+0)=-Inf`, `log2(negative)=NaN`, `log2(NaN)=NaN`,
  > `log2(+Inf)=+Inf`; 0 divergences in the special block).
  > **Supporting detail for SFU-01/02, `round_family_f32`:** `trunc` 1165/1172 exact (the only 7
  > divergences are NaN-payload canonicalization to `0x7FC00000`); `floor` 1140/1172 (7 NaN-canon +
  > **25 subnormal-input DAZ** — every negative subnormal gives `-0` instead of `-1`); `ceil`
  > 1118/1172 (7 NaN-canon + **47 subnormal-input DAZ**, mirror image); `round` 938/1172 —
  > **234 divergences, all sign-of-zero**: `round(-0.0)` and `round(any negative subnormal)`
  > return `+0` instead of `-0`. `round`'s zero-sign loss is a NEW, narrower finding: unlike
  > `floor`/`ceil` it loses the sign for `-0.0` itself, not merely as a DAZ side effect.
  > *(This section was rewritten after a disclosed post-freeze fix to the host oracle's
  > `floor`/`ceil` reference — which had used `trunc`'s rule. No hardware data changed.)*
  > Open sub-items deliberately left UNKNOWN: SFU-03's direct estimate-register readback on M4;
  > SFU-04 entirely (literal NR iteration count). No FP64, no non-default rounding modes (not
  > exposed by the public API), and no claim about behaviour inside a larger expression graph the
  > compiler might contract differently than these isolated single-op kernels.
  > Evidence: `experiments/EXP-0103-m4-fp-transcendental-semantics/` (HW-PROBE + OWN-SHADER +
  > PUBLIC MSL function names; M4 target; A18 deferred).

---

## P1 — Register files, immediates, and instruction encoding

- **ENC-01 — Are all GPR source and destination fields decoded for every instruction intended for
  initial compiler use?**

- **ENC-02 — Can every such instruction address every legal register it is architecturally allowed
  to use, including registers above r15 and r63 where applicable?**

- **ENC-03 — Are restrictions on even/odd registers and register pairs completely known for FP16,
  FP32, vectors, and I64 values?**

  > **Answered 2026-08-28 (desk audit over EXP-0020 / EXP-0141 / EXP-0146 / EXP-0113) — ENC-03 NO,
  > with an exact per-type inventory of what IS known. [DESK-AUDIT over HW results]**
  > **FP16 / half registers — largely known.** 16-bit halves are **independently addressable,
  > packed 2 per GPR** (64 `half` values occupy 50 GPRs); native-half access is via the `0x10` /
  > `0x11` groups, and the restriction that matters is that **the `0x09` 32-bit form's size bit
  > reaches only the LOW half** (EXP-0020). `half_alu`'s `srcA`, `srcB` and `src_modifier` are
  > `hardware-run` (A18, EXP-M4-14/EXP-0033), but its `dst` and `opflags` are `untested`.
  > **FP32 / GPR indices — known per instruction form, and the forms differ.** There is no single
  > register-field width: the 6-byte `falu2` destination is a **4-bit nibble (r0-r15 only)**, a
  > high float destination requires the 8-byte `falu3` form (`dst = byte+1`, 7-bit, r64 observed),
  > and integer `dst = b3` plus all source fields are 7-bit `(reg<<1)|size` spanning r0-r127 over a
  > 96-entry file (EXP-0020). The addressable file is ~96 GPRs, and this is corroborated from two
  > independent families: `device_load`'s destination is `extmode = 2*R` for **R in 0..63**, with
  > 128..255 (r64+) **silently zero** and bit 0 a don't-care (EXP-0141, M4, `hardware-run`); its
  > `index_reg` accepts r0..r95 with bit 7 ignored (128..255 mirror 0..127) and **r96..r127 FAULT**;
  > and the 64-bit `iadd2` form faults for destination byte values `0xBE..0xFF` (register index
  > >= 95) (EXP-0146, M4). Note the asymmetry: a too-high *destination* is a silent zero on
  > `device_load` but a **contained GPU address fault** on the 64-bit `iadd2`.
  > **I64 register pairs — explicitly NOT known, and the owning experiment says so.** EXP-0146
  > (M4/G16G, commit `f36b2ac4`) established that the 64-bit form's destination is a
  > **register-PAIR base encoded `(reg<<1)|size` in byte+3 whose size bit is a don't-care**, and
  > that in the source-A descriptor (byte+7) **every value with bits 0 and 1 both set faults**
  > (64 of 256). What it explicitly did **not** establish is *"whether the operation works at other
  > pair placements"* — because moving a source descriptor also changes which register is read, so
  > in a carrier whose loads write fixed registers a relocated operand reads garbage and is
  > indistinguishable from an illegal placement. Its verbatim instruction to the implementer:
  > **"Do not assume unaligned pairs work."** Closing this needs the `device_load` destinations
  > co-mutated with the `iadd2` operands — EXP-0146's own named successor.
  > **Vectors — no evidence at all.** No committed experiment establishes a consecutive-register or
  > alignment requirement for multi-component (vec2/vec3/vec4) operands as such; `device_load`'s
  > multi-element forms are characterized by `ld_format` / `elem_size` accepted-value sets
  > (21 and 48/96 accepted codes respectively, EXP-0141) rather than by a register-tuple rule.
  > **One live constraint an emitter must not miss** (EXP-0141, M4): the `dst_lo`/`dst_ext9` pair
  > rule is *mostly* `ld_format`-independent but tightens for narrow formats —
  > `dst_lo == 1` and `dst_ext9` bit 0 == 1 hold under **all 21** accepted formats, but
  > `dst_ext9`'s upper don't-cares shrink from `v & 0x181 == 0x081` (16 codes) to
  > `v & 0x1C1 == 0x081` (codes 3/7/9/13) to `v & 0x1E1 == 0x081` (code 39).
  > **Also on record and NOT to be re-derived:** EXP-0113 (M4) decisively **refuted** its own
  > candidate mechanism for reading r64-95 as an ALU source — the same spliced bytes gave
  > *different* results across two independent process launches for 4 of the singlehop/mismatch
  > cases, which
  > is outright nondeterminism and rules out indexed register-file addressing; **the only validated
  > path to r64-95 anywhere in this repository remains `get_sr`'s WRITE-side `dst`/`dst_hi`
  > mechanism (EXP-0092)**. And per the dispatch-level retraction list, EXP-0139 showed EXP-0112's
  > `r(R mod 64)` aliasing does **not** transfer to `iadd2.dst`.
  > **Answer: No — completely known for FP16 and for FP32 GPR indexing per form, NOT known for I64
  > pair placement, and untouched for vectors.** Conservative rule: emit only aligned pairs at the
  > placements EXP-0146 executed; stay within r0..r63 for `device_load` destinations.
  > M4 target for EXP-0141/EXP-0146/EXP-0113; A18 target for `half_alu` and the `frame_prologue`
  > family; A18 deferred elsewhere.
  > Evidence: `experiments/EXP-0146-m4-emit-int-misc/analysis/I64_answers.md` (I64-03),
  > `experiments/EXP-0141-m4-emit-mem/RESULTS.md` §H1/§H8/§8,
  > `experiments/EXP-0113-m4-register-file-model/RESULTS.md` §0, `docs/isa/README.md`
  > "Machine model" / "Register-field widths", `tools/agx-isa/validation.json`.

---

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

  > **Answered 2026-08-28 (desk audit over EXP-0020 / EXP-0024 / EXP-M4-09 CMD-8) — ENC-15 NO.
  > [DESK-AUDIT over HW results]**
  > **Only one occupancy field is decoded, it belongs to the compute stage alone, and its
  > predictor is a compiler property rather than a register count.**
  > What is known: the CDM launch-descriptor config word (`0x100000b0000 + 0x00`) is
  > `0x00080000` (bit19 always set) plus **bit 23 = a single-bit, 2-tier occupancy/register-class
  > flag**. Across ~50 kernels (footprint f0 = 2..96) the word is *only ever* `0x00080000` or
  > `0x00880000` — no higher bit ever lights — so it is **not** the LSB of a GPR-count field; the
  > actual GPR count lives in the shader BO / USC config. Atomics, barriers, simd ops and
  > threadgroup memory do not touch it.
  > **The obvious model is recorded as FALSE.** EXP-M4-09/CMD-8 corrected it: *"the earlier
  > interpolated 'clear <= 11 / set >= 12 GPRs' is FALSE"*. The flip is driven by the compiler's
  > **peak register-pressure / occupancy class**, not the total-GPR (metadata field-0) count, and
  > it happens far below 12 — an f0 = 8 kernel with two loop-carried chains (`N2E0`) is **SET**
  > while other f0 = 8 kernels (`N1E3`, `N0E7`) are **CLEAR**; f0 = 9 likewise splits
  > (`N1E4`/`N3E0` set, `N0E8` clear); the **lowest SET is a half-datapath kernel at f0 = 5**.
  > bit 23 correlates **1:1** with the presence of our own shader's `__GPU_METADATA` field-32 — a
  > compiler-computed occupancy property, not a quantity a driver can read off a register count.
  > The recorded driver instruction is therefore: *"A Mesa driver must set bit23 from its own
  > register allocator's occupancy decision (peak-GPR class), not from a `>= 12` test."*
  > **"For every stage" fails outright.** No committed experiment establishes a register-pressure ->
  > metadata mapping for the **vertex** or **fragment** stages; the per-stage USC uniform-preamble
  > header carries a `0x008800XX` register/shader-config tag (XX = stage x 0x0c) whose
  > register-count field is not decoded (EXP-0024/EXP-0042). And the surrounding model is recorded
  > as incomplete in the deliverable itself: `docs/capability-completeness.md` lists **Dynamic
  > Caching** (register file as cache; dynamic alloc/dealloc; occupancy vs live-set) and the
  > **full halfregs -> max-threads occupancy curve** as **NOT-YET-CHARACTERIZED**, and
  > `docs/mesa-userspace-requirements.md` records the occupancy/cycle model as *partial* with
  > "no full halfregs->max-threads occupancy curve, no per-op latency/throughput/cycle model".
  > **Answer: No.** Documented conservative response (already in `docs/porting-guide.md`): use the
  > **static** model that *is* decoded — 96 GPRs before spill, the spill threshold, and the
  > peak-pressure occupancy tier — and accept that a wrong occupancy choice is a performance
  > defect, not a correctness one.
  > Compute-stage evidence is A18-measured (the f0 splits above) and M4-cross-confirmed via
  > EXP-M4-09; the M5 figure (bit23 set for f0 >= 20) is **not** Apple9 evidence and is excluded.
  > Evidence: `docs/cmdstream/README.md` "Compute config word + threadgroup-memory size (EXP-0024;
  > occupancy tier CORRECTED EXP-M4-09/CMD-8)", `docs/isa/README.md` "Footprint declaration",
  > `docs/capability-completeness.md`, `docs/mesa-userspace-requirements.md`.

---

- **ENC-16 — Is scratch spill addressing and frame-size metadata fully known for generated shaders?**

  > **Answered 2026-08-28 (desk audit over EXP-0107 / EXP-0125 / EXP-M4-14 / EXP-0041) — ENC-16 NO,
  > with the exhaustion ceiling now exact. [DESK-AUDIT over HW results]**
  > **Frame-size metadata: known in outline, NOT resolved at the sub-field level.**
  > `frame_prologue` is `hardware-run` (A18, EXP-M4-14 — every byte of the prologue swept on an
  > executed non-leaf callee frame): `subop` runs only for values with **bits[1:0] == 0b11**
  > (`0x03`/`0x0b`/`0x13`/`0x23`/`0x43` run; `0x00`/`0x01`/`0x02`/`0x04` fault); `marker` is
  > reserved/inert. But `frame_size` carries an explicit unresolved note: it is **16-byte
  > granular**, **over-allocation is tolerated** (`0x20 -> 0x30`) while too-small or misaligned
  > **faults**, and it is **NOT cleanly monotonic — `0x40` faults while `0x30` runs — so the
  > sub-field layout is NOT fully resolved.**
  > `spill_frame_marker`'s **exact role is UNRESOLVED**: byte0/+1/+2 sweeps are runtime no-ops and
  > only byte+3 = `0xff` faults, and EXP-0041 found this exact word **absent from all nine
  > retained M4 own mains including 208-576 B of declared scratch** — so it is **not** a universal
  > spill marker.
  > `link_save_restore` is the one part that is fully mapped, and it corrects the database: in a
  > race-free frame it is a no-op fence with every payload field inert, but in a **spilling** frame
  > (12 live temporaries) byte0 `0x07 -> 0x00` corrupts the SAVE and **hangs** the RESTORE; `scope`
  > passes only when bit7 AND bit0 are both set (`0x81`/`0x83`), corrupts+hangs at
  > `0x00`/`0x80`/`0x01`, and page-faults at `0xff`; **`dir_offset` is 16-bit (bytes +5/+6), NOT
  > the DB's former 24-bit field** — byte+7 is reserved and inert on both instances.
  > **Scratch spill ADDRESSING: not located, at every point in the userspace lifecycle this
  > project's tooling can reach — a strong, bounded negative.** EXP-0107 (M4) pushed declared
  > per-thread scratch from 0 to **261,728 B** (~454x beyond EXP-0041's 208-576 B range) across
  > CS/VS/FS, 64 to **4,194,304** dispatched threads, threadgroup shapes 32/256/1024, and up to
  > 1,000 runtime spill/fill passes — 30 cases, captured twice, both fully hardware-run — and found
  > **no scratch-correlated BO, helper-program record, or doorbell/ABI structure** through the
  > widened DATA-TRACE boundary. EXP-0125 (M4) confirmed the same negative at a **third** point,
  > before dispatch and before compile: the full address-free BO inventory is **byte-identical**
  > between a never-spilling process and one spilling 98,320 B/thread at **all six** lifecycle
  > checkpoints in both gated runs, and the single code-shaped region (VA `0x10000000000`) is
  > exactly `0x10000` B at every checkpoint **including `DEVICE_CREATED`, before a line of MSL is
  > compiled**. Selector-5 ("shared pages") was never observed to be called at all.
  > **What IS now exact, and is new to this row: the exhaustion boundary.** All three stages
  > (CS/VS/FS) **independently bisect to the identical ceiling — last success K = 65,431
  > (261,740 B declared scratch), first failure K = 65,432 (261,744 B)** — a 4-byte (one array
  > element) resolution, byte-identical across both gated runs for all three stages. The failure
  > is clean, at pipeline-creation time (`newComputePipelineStateWithFunction` -> *"Compute
  > function exceeds available stack space"*), with **no device fault, timeout, or corruption**.
  > That is **~2.003x below** mesa's own `AGX_MAX_SCRATCH_DWORDS` (131,072) and is not fully
  > explained by a units artifact.
  > **Answer: No.** Conservative response: a driver may size scratch up to the measured
  > stage-uniform ceiling and expect a clean creation-time rejection above it, must over-allocate
  > rather than under-allocate the 16-byte-granular frame field, must not emit
  > `spill_frame_marker` as if it were a required spill marker, and must treat the scratch base /
  > helper handoff as an open userspace<->kernel coordination item rather than a discovered
  > userspace structure.
  > M4 target for EXP-0107/EXP-0125 (the ceiling and the negatives); A18 target for the
  > `frame_prologue` / `spill_frame_marker` / `link_save_restore` sweeps (EXP-M4-14); A18 deferred
  > elsewhere.
  > Evidence: `experiments/EXP-0107-m4-scratch-helper-abi/RESULTS.md`,
  > `experiments/EXP-0125-m4-scratch-helper-init/RESULTS.md` (H1/H2/H3),
  > `experiments/EXP-0041-scratch-helper-abi/`, `tools/agx-isa/validation.json`
  > (`frame_prologue`, `spill_frame_marker`, `link_save_restore`).

---

  > **Answered 2026-08-28 (EXP-0105, M4/G16G, commit `79ab3da9`) — ENC block. Read the
  > supersession notes: this cluster's headline r64-95 result was overtaken by EXP-0112 (commit
  > `d5d8fbee`), and two adjacent claims were retracted by EXP-0101 (`2cf96b56`) and EXP-0099
  > (`de4e4a81`).** EXP-0105 itself: 16/16 cases per run, two runs, `01_results.jsonl`
  > byte-identical (sha256 `b193274a...`); 8/16 matched their oracle and every one of the other 8
  > is a deliberate positive control or a hypothesis-testing case whose oracle recorded a
  > *prediction*, not a pass/fail claim.
  > **ENC-02 REFUTED for `falu2`/`falu2i`'s packed source field at r64-95; UNKNOWN overall.**
  > Field value 67 (low 6 bits == 3, weight-64 bit set; register 67 never written) reads register
  > **3**'s seeded value 30.0, never the unwritten register 67's zero — by INDEPENDENT CONSTRUCTION
  > on `falu2i`, and reproduced on `falu2`'s own register-register form in a freshly built
  > carrier/harness. Two sibling instructions, two runs, deterministic. **SUPERSEDED /
  > STRENGTHENED by EXP-0112 (`d5d8fbee`):** a 28-point sweep of the consuming instruction's 7-bit
  > `srcA_reg` shows R = 0..63 correct (dense 15-point sweep), **R in [64,112] silently ALIASES to
  > `r(R mod 64)`** — proven by 4 poison-register controls that make the aliased read return the
  > poison value 30.0 rather than 0.0, i.e. it is genuine field aliasing, **not** the "silent zero"
  > EXP-0105 could not distinguish — and **R in {126,127} FAULTS the command buffer**, a second,
  > qualitatively different failure mode. Net: the field is 6 load-bearing bits in this context;
  > no mechanism has been found that reaches registers 64-95 through this family.
  > **ENC-06 PARTIAL, extended: 7 previously untested bits classified — 5 corrupting, 2 inert.**
  > `opflags` bit22, `opflags` bit23, `mod_hi` bit44, `ctrl` bit0 and `ctrl` bit1 each silently
  > change the read from 30.0 to exactly 0.0. Because the effect is IDENTICAL whether the register
  > field nominally selects 3 or 67, these are **general corruptors, not register-bank selectors**
  > — the `get_sr`-inspired "bank-unlock bit" hypothesis is REFUTED for all three cross-checked
  > candidates. `ctrl` bits 2 and 3 are the only two confirmed inert, for this construction only.
  > **ENC-07 PARTIAL, extended — general answer: NO, reserved bits are not safely known.** Five of
  > seven previously-unexamined bits turned out load-bearing. Policy reaffirmed with new specific
  > data: never synthesize or normalize an undocumented field in this family; emit only values
  > copied verbatim from a compiler-observed pattern for the same operand shape.
  > **ENC-10 OPEN, extended with a new negative data point.** A second, structurally different
  > register-addressing method (`iminmax`, plain 8-bit register fields) was attempted in EXP-0105's
  > pilot phase and **ABANDONED** after producing two unexplained, uninterpretable hardware
  > behaviours — recorded as a first-class unresolved negative, not dropped. **Partially offset by
  > EXP-0112 (`d5d8fbee`):** an independent program GENERATOR built 161 programs (DAG size 2-35
  > nodes, 44/100 main cases with more dataflow values than the 14-register pool, peak
  > `max_live_registers` 13) and ran **140/140 `expect_match` cases correct and 21/21
  > `expect_match=False` cases as predicted, 159 OK / 2 deliberate CMDBUF_ERROR** — a genuine
  > multi-instruction, multi-family generated-shader execution result, though not a census of
  > "every initial instruction family".
  > **ENC-01, ENC-04, ENC-05, ENC-08, ENC-09, ENC-11, ENC-12, ENC-13, ENC-14 — PARTIAL by
  > DESK-AUDIT (no new hardware evidence in this cluster).** ENC-01: several families remain
  > `db.json`-flagged inferred. ENC-04: float uniform sources covered by EXP-0020/RT-1a-FIX; the
  > integer ALU is still inferred. ENC-05: minifloat (EXP-0006) and `mov_imm` (EXP-0031) covered;
  > **NaN-literal handling is a gap not found documented anywhere.** ENC-08: ~87-91% tokenization
  > per the RT-ISA-FIX census. ENC-09: all 16 of this experiment's own cases round-trip. ENC-11:
  > compute closed (EXP-0003/EXP-0010 E4); other stages not. ENC-12: EXP-0010 E6 (jump) plus
  > EXP-0035/RT-ISA-FIX (call/jump_cond). ENC-13: substantially closed for tested depth
  > (EXP-0035/EXP-0038). ENC-14: compute doubly closed (EXP-0006/EXP-0020 + EXP-0092 GLIO-A02).
  > **ENC-03, ENC-15, ENC-16 UNKNOWN / DEFERRED.** ENC-03 was not probed. ENC-15 and ENC-16 are
  > `docs/isa/README.md`'s own disclosed gaps (ENC-16's sibling workstream is EXP-0107).
  > **Retractions that bear on this cluster and must not be lost:**
  > (a) **EXP-0101 (`2cf96b56`) refutes EXP-M4-13's `dst` formula.** The register a subsequent ALU
  > instruction must reference is `device_load`'s **`extmode` field divided by 2**
  > (`extmode = 2 * target_register`) — **NOT** the `dst_lo`/`dst_ext9`-derived value EXP-M4-13
  > predicted. `dst_lo`/`dst_ext9` remain real and independently required but must be **copied
  > verbatim** from a compiler-observed value for the same `addr_mode`/`ld_format` shape, never
  > derived from the target register; and `falu2i`'s own `mods` byte must be `0xC0` (not the naive
  > default 0) when the operand it modifies is load-sourced. HW-VALIDATED over two gated runs,
  > 6 positive constructions and 6 adversarial falsifications of the next-most-plausible repairs.
  > (b) **EXP-0099 (`de4e4a81`) refutes BOTH competing bit-15/31 lifetime models**, and the
  > attribution was retracted from `docs/isa` in commit `88fa4953`. `falu2`'s
  > `srcA_reg`/`srcB_reg` top bit (instruction bit 15 / bit 31) has **zero observed effect** on
  > either which register is read or on retention behaviour, in all 8 decisive cases across two
  > runs — a third outcome distinct from both models as stated. EXP-0099 also refuted the claimed
  > `mod_hi` bits 1-3 "consumer route" field (all 8 values) and all three candidate `reg_move`
  > fixes, and found by static analysis alone that the explainer's own 10-byte "retain source 0"
  > example does not decode under any `db.json` family.
  > Open sub-items deliberately left UNKNOWN: whether registers 64-95 are reachable through this
  > field family by ANY encoding not yet tried — the positive falsifier (a genuinely seeded,
  > distinctly-valued r67 read back through the same field) has never been achieved; `ctrl` bits
  > 0/1 were corruption-tested only at reg=3, not cross-checked at reg=67 (a disclosed time-boxed
  > narrowing); `reg_move` reading an ALU- or load-written GPR remains blocked (EXP-0090 blocker
  > #2), with the instruction's `src_flag=0` output HW-shown to depend only on `src_reg` quantized
  > in register PAIRS — the signature of a fixed per-kernel preloaded/uniform slot, not a GPR read;
  > ENC-03/15/16 entirely.
  > Evidence: `experiments/EXP-0105-m4-encoding-registers/` (HW splice, independently constructed),
  > with `experiments/EXP-0112-m4-program-generator/`, `experiments/EXP-0101-m4-synthesis-blockers/`
  > and `experiments/EXP-0099-m4-lifetime-field-model/` for the supersessions and retractions above
  > (HW-VALIDATED + OWN-SHADER + DESK-AUDIT mix; M4 target; A18 deferred).

---

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

  > **Answered 2026-08-28 (EXP-0104, M4/G16G, commit `574ee96f`; deferred items closed by
  > EXP-0115, commit `fec9315a`) — CF block.** EXP-0104: 92 cases per run x 2 runs, cross-run gate
  > 0 issues, 71 OK/MATCH, 0 mismatch, 4 contained `CMDBUF_ERROR`, 1 contained hang (8 s timeout,
  > zero host impact). EXP-0115: 308 cases per run x 2 runs, 295/308 byte-identical.
  > **CF-01 YES, with a sharp structural correction.** All 8 authored shapes (diamond join, 5-way
  > if-elseif chain, if-nested-in-else, a 21-point depth sweep, two nested-loop shapes) tokenize
  > with **0 leftover bytes** and match a Python host oracle exactly. The correction: the compiler
  > uses **two qualitatively different lowerings, selected by the presence of
  > `return`/`break`/`continue` — not by nesting shape or depth.** Ordinary if/else with no
  > early exit (`plain_join`) is **pure predication: 8 instructions, ZERO
  > `icmp_pred`/`if_push`/`pop_reconverge`** (a compare-select only). The same values with a
  > `return` (`ret_early`) is 13 instructions **with** the full mask-stack machinery. A kernel
  > designed to force two simultaneously-live predicates (two nested if/else regions each holding
  > a data-dependent loop, no early exit anywhere) tokenized to **ZERO `icmp_pred` instances** —
  > recorded as a genuine negative result, and the reason the CF-05 splice target had to move.
  > **CF-02 YES.** One data-dependent loop containing both a `continue` (k==3) and a `break`
  > (k==7) tokenizes cleanly and matches an exact host re-implementation
  > (`bc_a = [0,1,2,5,8,10,3,7]`). No dedicated loop-exit helper instruction exists or is needed.
  > **CF-03 PARTIAL — bounded from below by hardware, bounded from above only by the TOOLCHAIN.**
  > EXP-0104 found no failure to depth 128 (divergent-return if-chain), 64 (pure loop-nest) or 12
  > (genuinely divergent nested loops) — 21 depth points, all MATCH, both runs. EXP-0115 pushed to
  > the wall: **exact max-compilable depths are 254 (if-chain), 255 (pure loop-nest), 255
  > (bounded-divergent nest)**, all HW-dispatched correctly at their maximum, with the next depth
  > up a deterministic `COMPILE_FAIL` — `"bracket nesting level exceeded maximum of 256"`. **That
  > is Metal's Clang front end (`-fbracket-depth=256`), not AGX silicon**, and it is not adjustable
  > through the public `MTLCompileOptions` surface this project may use. **No AGX hardware fault,
  > hang, or silent-wrong-result was observed at ANY depth that compiled.** The true hardware
  > reconvergence-stack ceiling remains **UNKNOWN** beyond ~254-255. (An NIR-based Mesa backend
  > does not go through Clang's parser at all, so this specific limit is almost certainly not
  > inherited by that path.) *Disclosed defect: EXP-0115's `loopnestD2` oracle assumed additive
  > rather than multiplicative nested-loop growth, so all 9 of its depths show a deterministic,
  > understood MISMATCH in both runs; hand verification confirms the hardware output matches
  > `PRODUCT(1 + bit((j-1) mod 32)(v))` exactly. The load-bearing CF-03 fact — `STATUS OK` at every
  > depth — is unaffected, and run02 deliberately reused the unmodified oracle to keep the
  > cross-run determinism gate meaningful.*
  > **CF-04 YES, decisively.** `ret_early` (100 bytes, 13 instructions) uses
  > `icmp_pred`+`if_push`+`pop_reconverge`; the semantically equivalent `plain_join` without a
  > `return` (66 bytes, 8 instructions) uses ONLY a compare-select. **Neither contains the `0x8f`
  > subroutine CALL/RETURN opcode** (verified by full disassembly, not a raw byte scan), confirming
  > EXP-0035's finding that `0x8f` is reserved for real function calls. A `multi_return` kernel
  > with three early-return points at three nesting depths matched a 5-way host oracle exactly,
  > proving a genuinely shared epilogue. Lower divergent return as an execution-mask-narrowing
  > `if_push`, never as a call-frame return.
  > **CF-05 NO — there is no independently addressable predicate file.** Compiler census:
  > **18/18 `icmp_pred` instances across nesting depths 1-16 and an asymmetric if-in-else shape
  > have `dst_pred = 0`**, zero exceptions. HW splice (downstream read, not self-read): `dst_pred`
  > spliced to 1 gives a unique corruption `[-1003,-1003,-1001,-1001,-1001,-1001,-1001,-1001]`,
  > while 5 and 0xf both give `[-1001]*8` (every lane takes the outermost else). EXP-0115 extended
  > this to a **25-point joint (dst_pred, if_push.pred) matrix plus a full 0-15 `dst_pred`
  > census**, with a decisive result: **output depends ENTIRELY on `dst_pred` and NEVER on
  > `if_push.pred`** — the sibling `if_push_pred` opcode's 4-bit `pred` nibble is **completely
  > INERT at every value, matched or mismatched**. `dst_pred` splits exactly three ways: 0 correct,
  > 1 a unique corruption, {2..15} (14 values, zero exceptions) one uniform corruption. Both live
  > hypotheses are REFUTED: `if_push`'s predicate consumer is not parameterized by an independent
  > address at all, and nonzero `dst_pred` is ordinary wrong-operand-field corruption.
  > **Flagged for the `docs`/`tools` owner: `db.json`'s current `if_push_pred` "predicate-register
  > PUSH variant" characterization is not supported by this splice evidence for this
  > producer/consumer pairing.**
  > **CF-06 YES — but the answer is "there is nothing to allocate."** Always emit `dst_pred = 0`;
  > the real finite, lifetime-managed resource is the `if_push`/`pop_reconverge` execution-mask
  > STACK (LIFO by construction), which CF-03 stress-tested correctly to the toolchain ceiling. A
  > late-predicate-allocator pass is not needed for this ISA as currently understood.
  > **Branch reach (not a numbered item, but part of CF-01/CF-02's core question) — MAPPED, with a
  > major correction and a new first-class finding.** EXP-0104: a +4096 B forward perturbation ran
  > to completion with `STATUS OK` and **silently ZEROED output** — a driver must never treat
  > "no CMDBUF_ERROR" as proof a jump target is correct. EXP-0115's 162-point sweep sharpens it:
  > **forward has ZERO slack (delta=+1 already faults)**; **backward has exactly ONE alias hole
  > (delta=-2 is also fully correct)**; the region past the function's 146-byte extent is a genuine
  > **CHECKERBOARD** of fault / hang / silent-zero, not a threshold (e.g. +1024/+1536/+2048/+2176
  > silent-zero while +1280/+1408/+2432 fault, interleaved); **backward is uniformly fault/hang
  > with zero silent-zero points anywhere**; and **13 of 162 points (8%) are genuinely
  > NON-DETERMINISTIC run-to-run** — same compiled bytes (verified byte-identical from both runs'
  > independently compiled archives), different observable outcome, including `STATUS` flips
  > (`OK` silent-zero vs `HANG`) and GPU error-code flips (`PageFault` / `Hang` /
  > `InnocentVictim`). The `InnocentVictim` code additionally shows a command buffer can be
  > reported as the victim of a NEARBY dispatch's fault — real operational noise for any harness
  > firing many faulting dispatches back to back.
  > Open sub-items deliberately left UNKNOWN: the true hardware reconvergence-depth ceiling beyond
  > the toolchain wall; mixed if+loop nesting and nesting combined with real function calls;
  > `dst_pred`/`if_push.pred` were cross-matrixed at only 25 of 256 pairs and at exactly ONE
  > nesting position (the outermost `icmp_pred`/`if_push`, not a nested nonzero-`scope` occurrence);
  > the exact byte where a forward jump transitions from fault to silent-zero was not bisected; the
  > mechanism behind the 13 non-deterministic points is `INFERRED` only (landing on a real
  > instruction boundary via an unintended entry path, so the outcome depends on uninitialized
  > resident state); shapes with more than 2 simultaneously-live non-return-gated predicates were
  > never constructed.
  > Evidence: `experiments/EXP-0104-m4-controlflow-simd/` and
  > `experiments/EXP-0115-m4-controlflow-simd-deferred/` (HW-PROBE + OWN-SHADER + HW-VALIDATED
  > splice + clean tokenization; M4 target; A18 deferred).

---

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

  > **Answered 2026-08-28 (EXP-0104, M4/G16G, commit `574ee96f`; deferred items closed by
  > EXP-0115, commit `fec9315a`) — SIMD block.**
  > **SIMD-01 YES, for compute AND fragment.** EXP-0104 (compute): at tg=64 every thread reports
  > `threads_per_simdgroup = 32`; at **tg=48** (one full 32-thread group plus a **PARTIAL
  > 16-thread** final group) `thread_index_in_simdgroup` correctly resets to 0..15 and
  > `simdgroup_index_in_threadgroup` is 1, yet `threads_per_simdgroup` **still reports 32** — it is
  > a fixed architectural constant, not a live occupancy count. EXP-0115 closes the deferred
  > fragment sweep: `[[threads_per_simdgroup]]` compiles in the fragment stage (not previously
  > established here) and reports **32 at every one of 12 render-target sizes** from 1x1 (a single
  > real fragment) through 64x64, crossing the fixed 32x32 tile boundary repeatedly — **10784 total
  > pixel readings, zero exceptions.** Safe to constant-fold to 32 in both stages.
  > **SIMD-02 YES.** Three predicates genuinely derived from `thread_position_in_grid`
  > (`i%3==0`, `i%7<2`, `5<=i<19`) at grid=tg=32: all 32 lanes read the identical 32-bit mask and
  > it equals `SUM pred(j)*2^j` exactly. Bit `i` = lane `i`; no lane renumbering needed.
  > **SIMD-03 — defined and deterministic, but NOT a simple wraparound, and NOT uniform across the
  > family. THREE different out-of-range behaviours exist, and the static and dynamic encodings
  > disagree.** Dynamic (runtime-register index) `simd_shuffle`: for idx >= 32 the effective source
  > lane is **`idx & 0x1C`** — only bits 2-4 are used, bits 0-1 and every bit >= 5 dropped — fitting
  > all 14 out-of-range points with zero exceptions (32->0, 33->0, 40->8, 63->28, 64->0, 127->28,
  > 4095->28, 65535->28, plus a per-lane `idx=lane+32` case matching on all 32 lanes). **This is
  > NOT modulo-32** (which would predict 33->1, 63->31, 127->31 — all wrong), not clamping, not
  > pass-through, not a fault. Dynamic `simd_shuffle_xor` (masks 32,33,63) and dynamic
  > `quad_shuffle` (idx 4,5,8,255): **every lane reads a hard ZERO** — a qualitatively different
  > mode. EXP-0115 then closed the static/immediate form by splicing the raw `lane` byte directly
  > (the compiler PRE-MASKS an illegal literal, e.g. literal 40 compiles to `(40 & 0x1F) << 1`, so
  > only a raw splice tests the hardware): **static `simd_shuffle` gives HARD ZERO for all 28
  > out-of-range/odd raw values from 64 through 255 — it does NOT alias like the dynamic form** —
  > while static `simd_shuffle_xor` and `quad_shuffle` match their dynamic forms (hard zero either
  > way, the `quad_shuffle` case additionally confirmed via a naturally-compiled unmasked literal
  > `quad_shuffle(v,(ushort)7)`). **Two genuinely different hardware behaviours for what MSL
  > exposes as the same builtin**, depending only on which encoding the compiler chose. NIR
  > lowering must mask the index in software, or at minimum never assume any single fallback rule.
  > **SIMD-04 YES.** With odd lanes taking an `else` arm that calls NO subgroup op at all,
  > `simd_prefix_exclusive_sum`, `simd_prefix_inclusive_sum` and `simd_sum` on the even lanes all
  > match a closed-form active-lane-order oracle exactly (excl/incl = 0..15 at positions 0,2,..,30;
  > reduce = 16 at every active lane). No special legalization for the "some lanes skip the call"
  > divergence shape.
  > **SIMD-05 YES, fully resolved — on real 4x4 render-target geometry, all 16 pixels per kernel.**
  > `quad_shuffle_xor` mask **1 = horizontal `(x^1, y)`**, **2 = vertical `(x, y^1)`**,
  > **3 = diagonal `(x^1, y^1)`**. Within-quad linear order is **row-major**: lane0 top-left,
  > lane1 top-right, lane2 bottom-left, lane3 bottom-right. `quad_shuffle_up`/`_down`'s "fill"
  > clamps at the quad's own lane-0 / lane-3 boundary. Quads tile the screen in fixed
  > non-overlapping 2x2 blocks aligned to even (x,y) — confirmed by (2,0)/(3,0)/(2,1)/(3,1) forming
  > their own self-consistent quad. The compute linear half independently confirms
  > `thread_index_in_quadgroup = lane % 4`. `quad_swap_horizontal/vertical/diagonal` map directly
  > to masks 1/2/3.
  > **SIMD-06 — EXP-0104 said YES; EXP-0115 NARROWS that to "not universally".** EXP-0104
  > (structural): `sgbar_none`, `sgbar_memnone`, `sgbar_memtg`, `sgbar_memdev` all compile to the
  > **IDENTICAL 46-byte `_agc.main`**, byte for byte — `simdgroup_barrier` adds zero instructions
  > for every memory class, stronger than `threadgroup_barrier`, which EXP-0093 showed DOES emit a
  > real instruction even for `mem_none`. EXP-0104 itself flagged its functional corroboration as
  > weaker than the structural result (grid=tg=32 means the kernel's own control flow already
  > reconverged every lane before the cross-lane read, so the test could not distinguish "truly
  > unnecessary" from "never mattered here"). **EXP-0115 resolves that flag in the negative:**
  > under **DIVERGENT** call patterns the compiler retains real machinery — `sgbar_loop`
  > (per-lane divergent call COUNT) 124 vs 110 bytes and 18 vs 11 instructions; `sgbar_ifdiv`
  > (divergent call PRESENCE) 76 vs 46 bytes and 10 vs 5 instructions, the barrier-present twin
  > keeping a real `if_push`/`pop_reconverge` pair and a `scoreboard_fence` where the no-barrier
  > twin is entirely dead-code-eliminated. Under UNIFORM patterns (heavy register pressure, two
  > consecutive barriers, depth-8 non-divergent nesting) it stays byte-identical, reproducing
  > EXP-0104. **Honest caveat carried forward:** the mechanism may be the barrier acting as an
  > optimization barrier / side-effect anchor rather than proof of a dedicated opcode; both
  > readings support the same driver conclusion. Functionally, both deadlock-risk shapes dispatched
  > correctly under a hard 10 s timeout with exact oracle matches — no deadlock. **Net: treat
  > `simdgroup_barrier` as free only at non-divergent call sites.**
  > **SIMD-07 PARTIAL, with a genuine refutation — helper lanes are INCLUDED, not excluded.**
  > EXP-0104: with one fixed pixel discarding on a 4x4 target, every surviving pixel's **raw low-16
  > mask bits are `0xFFFF`, byte-identical to the no-discard baseline** — `simd_active_threads_mask()`
  > does NOT clear a just-demoted neighbour's bit. Combined with EXP-0091 (data-movement ops also
  > include the demoted lane), the narrower "vote ops exclude helpers" hypothesis is **REFUTED**.
  > EXP-0115 extends this to three more ops: `simd_all` still sees the demoted lane's FALSE
  > predicate, `simd_any` still sees its TRUE predicate, and an explicit `simd_ballot(predicate)`
  > reproduces the same behaviour. **The popcount 16 -> 24 puzzle is NARROWED, not resolved:** an
  > ordinary divergent `return` at the same pixel does **not** trigger the jump (survivors report
  > 16), decisively ruling out "generic to any divergent control flow"; two discards give the same
  > 24 as one (not count-proportional); moving the discard to pixel (1,1) gives the same 24 (not
  > location-dependent). The extra 8 bits live in mask bits 16-23, outside the raw R/G readback,
  > and the exact bit-level mechanism is **UNKNOWN** — the discard/return fragment prologue has
  > undecoded residue (an `<UNKNOWN>` byte0 `0xa6`/`0x54`-family leader absent from
  > `tools/agx-isa/db.json`). **The +8 magnitude must not be relied on for anything.**
  > Open sub-items deliberately left UNKNOWN: SIMD-03's sparse sample points between the tested raw
  > values (the "hard zero" pattern is assumed, not proven, to continue between them), and
  > `simd_shuffle_up/down`'s fill behaviour at out-of-range magnitudes (only the quad-scope up/down
  > fill was tested); SIMD-06's isolation of the barrier's own compiled cost from the
  > optimization-barrier confound; SIMD-07's exact bit mechanism, multi-quad-crossing discard
  > patterns, and a full byte-level decode of the discard/return fragment prologue.
  > Evidence: `experiments/EXP-0104-m4-controlflow-simd/` and
  > `experiments/EXP-0115-m4-controlflow-simd-deferred/` (HW-PROBE + OWN-SHADER + HW-VALIDATED
  > raw-byte splice; M4 target; A18 deferred).

## P2 — Questions that may remain deferred for the first compiler

- **P2-01 — Is native BF16 scalar and packed arithmetic exposed by portable NIR in a form useful to
  this compiler?**

  > **Answered 2026-08-28 (desk pass over EXP-O2D / EXP-M4-13 / EXP-M4-02) — P2-01 PARTIAL. [HW +
  > DESK-AUDIT]**
  > **The hardware half is YES; the emit half is NO.**
  > **Native BF16 scalar AND packed arithmetic exists and is a distinct instruction group** —
  > byte0 `0x11`, *not* the `0x10` native-fp16 group and *not* an fp32 widen/narrow lowering
  > (a single `0x11` op does the add; no widen-add-narrow sequence appears). `byte+1 = 0x02`
  > selects the **scalar** form, `byte+1 = 0x04` the **packed `bfloat2`** form; `byte+2` opsel
  > `0x1c` add / `0x1d` mul / `0x1e` fma (the fma form is 10 bytes, add/mul 8). The add/mul
  > selector is the only bf16 field ever executed: splicing `byte+2 0x1c -> 0x1d` flipped a
  > native bfloat `1+2` into `1x2` (EXP-O2D, **A18 target**). Conversion is a separate 8-byte
  > `cvt_bf16`: `byte+1` source width (`0x03` f32, `0x02` f16), `byte+6` direction (`0x40` result
  > bfloat, `0x80` result half); bfloat->float is a free widen because bf16 is the top 16 bits of
  > fp32 (EXP-M4-13, **M4 target**, corpus-correlation). `bf_add_dst`/`bf_mul_dst`/`bf_fma_dst`
  > generalise the group to any destination register (EXP-M4-13, M4, corpus-correlation).
  > BF16 also reaches the matrix unit: every correct bf16 `simdgroup_matrix` spelling compiles on
  > M4 and is **identical to A18** (EXP-M4-02; the one apparent M4 delta was a flaw in our own MSL
  > — a `1.0` *double* literal where the scalar-broadcast constructor wants `vec<bfloat,64>` — not
  > a hardware or compiler difference).
  > **Why the answer is not a plain Yes: no bf16 operand field has ever been executed.** In
  > `tools/agx-isa/validation.json`, `bf_alu.srcA`/`srcB` are `untested`, its `tail` is
  > `tokenization-only`; `bf_add_dst`/`bf_mul_dst`/`bf_fma_dst` have `dst`/`srcA`/`srcB`/`srcC`/
  > `tail` all `untested`; `cvt_bf16` has 5 of its 8 fields `untested`; `bf_alu8_var` is
  > `tokenization-only` throughout. Per `docs/evidence-classification.md`'s **`emittable` rule**,
  > the whole bf16 family is therefore **"decodable, not yet emittable"** — a backend can be told
  > the group exists and which opsel byte selects add/mul/fma, but cannot yet be told which byte
  > carries an arbitrary source register, and on Apple9 a wrong operand field yields a **silent
  > zero, not a fault**.
  > **Conservative compiler response until that changes:** do not expose a native NIR bf16 ALU
  > type; keep bf16 as a storage/convert type (widen to fp32 for arithmetic), and route
  > cooperative-matrix bf16 through the `0xcf` matrix path (P2-03), which *is* emittable.
  > A live successor exists: `EXP-0145-m4-emit-bf16-half` was running at the time of this pass and
  > had no committed `RESULTS.md`; it is the experiment that would flip this to a plain Yes.
  > Targets as stated per fact (A18 for the executed opsel splice; M4 for the corpus location);
  > no bf16 claim here is M4-executed.
  > Evidence: `experiments/EXP-O2D-compute-frag-tail/`, `experiments/EXP-M4-13-full-corpus/`,
  > `experiments/EXP-M4-02-capabilities/`, `tools/agx-isa/validation.json`
  > (`bf_alu`, `bf_add_dst`, `bf_mul_dst`, `bf_fma_dst`, `bf_alu8_var`, `cvt_bf16`).

---

- **P2-02 — Are BF16 conversion, rounding, denormal, and NaN semantics fully hardware-validated?**

  > **Answered 2026-08-28 (desk audit of the committed evidence record) — P2-02 NO. [DESK-AUDIT]**
  > **No committed experiment has measured a single BF16 numeric result.** The FP semantics work
  > (EXP-0103, M4/G16G, commit `bbb1e9fc`) is explicitly FP32 and FP16 only — its own limitations
  > section records "No FP64, no non-default rounding modes" and it never lists a bfloat kernel;
  > the packed-conversion work (EXP-0102, commit `958f8307`) covers unorm/snorm/half packing, not
  > bf16. The exhaustive sweeps that exist for the neighbouring types — 65536/65536 bit-exact for
  > the packed converts, 1886/1886 RTE for fp32->int, the 65536-pattern FP16 subnormal survey —
  > have **no bf16 counterpart anywhere in `experiments/`**.
  > What *is* on record is structural only: the `0x11` group's existence and its add/mul opsel
  > (EXP-O2D, A18 splice), and `cvt_bf16`'s source-width and direction bytes located over an
  > own-MSL corpus (EXP-M4-13, M4, `corpus-correlation`). Nothing states bf16's rounding mode, its
  > denormal handling (fp32's DAZ+FTZ model established by EXP-0074/EXP-0103 must **not** be
  > assumed to transfer — FP16 already contradicts it, preserving subnormals where FP32 flushes),
  > or its NaN contract.
  > **Required compiler response:** treat bf16 rounding/denormal/NaN as `UNKNOWN`. Where the
  > result is observable, widen to fp32, operate, and convert once — do not rely on a native bf16
  > op reproducing any particular rounding. A future experiment closing this must run the same
  > shape EXP-0103 ran for fp32/fp16: directed exceptional values plus a dense sweep, scored
  > against a host oracle, on M4.
  > M4 target for the corpus location; A18 target for the one executed splice; **no bf16 numeric
  > observation on either target.**
  > Evidence (absence is the finding; these are the files that would have contained it):
  > `experiments/EXP-0103-m4-fp-transcendental-semantics/RESULTS.md`,
  > `experiments/EXP-0102-m4-int-pack-semantics/RESULTS.md`, `tools/agx-isa/validation.json`.

---

- **P2-03 — Are matrix/cooperative-matrix instructions sufficiently decoded to select them from NIR
  cooperative-matrix operations?**

  > **Answered 2026-08-28 (EXP-0147, M4/G16G, commit `487caaad`; operand semantics EXP-0022 /
  > EXP-O2C / RT-10, A18) — P2-03 YES, upgraded this wave. [HW]**
  > **`matrix_mac` is now EMITTABLE.** EXP-0147 swept the two fields that were blocking it and
  > promoted both, so all **12 of 12** fields are `hardware-run` or `isolated-byte-diff` and the
  > family clears `docs/evidence-classification.md`'s `emittable` rule
  > (`analysis/emittability.json`: `blocking_after: []`, `emittable_after: true`).
  > `dst_desc` (byte+9): all **256/256** values, twice, 100 % cross-run agreement — correct
  > `A*B+C` iff **bit6 = 1 and bit7 = 0** (64 values); `0x00-0x3f` and `0x80-0xbf` give a **silent
  > zero**; `0xc0-0xff` give a wrong value. `b11hi` (byte+11 bits 1-7): all **128/128** values,
  > twice — correct iff **`(b11hi & 3) == 0`** (32 of 128). Liveness was proven, not assumed:
  > forcing the op-enable byte+10 `0x24 -> 0x00` drops the multiply and the read-back becomes C
  > passthrough, in both runs, on M4.
  > **A hardware capability Metal never emits was found in the process:** `b11hi`'s two low bits
  > are **accumulator sign controls**, resolved per tile row — `0` = `+C` everywhere, `1` = `-C`
  > on rows 0-3 only, `2` = `-C` everywhere, `3` = `-C` on rows 4-7 only. So the matrix unit does
  > **`A*B - C`** and a **half-tile** variant, neither of which
  > `simdgroup_multiply_accumulate` ever produces.
  > Selection constraints a NIR cooperative-matrix lowering must respect, from the prior decode:
  > one `0xcf` = one full **8x8x8** tile MAC (512 MACs), row-major
  > `d[i][j] = C[i][j] + sum_k A[i][k]*B[k][j]`; `byte+1` dtype `0x00` = 16-bit half, `0x02` =
  > 32-bit float (bfloat shares the 32-bit datapath with input conversion); `byte+2` mode `0x56`
  > standalone vs `0x54` tiled, and **mode is semantic, not a hint** — splicing standalone->tiled
  > **zeroes** the result because tiled mode sources its accumulator from the MPP tile context;
  > `byte+11` bit0 = accumulate-enable (`simdgroup_multiply` clears it); operand identity is
  > unambiguous (byte+5 = A, byte+6 = B, byte+7 = C, byte+8 = dst, proven by splicing A to B's
  > register -> `B*B` and swapping +5/+6 -> `B*A`, matmul being non-commutative). **Only 8x8 is
  > exposed** (16x16 / 8x16 / 4x4 / 32x32 rejected); element types half, float, bfloat including
  > mixed half/bfloat -> fp32 accumulate; **all integer matrices are REJECTED** (no int8
  > cooperative matrix), so a Vulkan int8 cooperative-matrix path must be emulated in the ALU.
  > All MPP tensor ops (`matmul2d` multiply / multiply_accumulate / transpose / f32 / 16x16x16 /
  > 2-simdgroup) lower to this same opcode — there is no separate tensor opcode; transpose is
  > data movement (`ray_move`-family 4-byte ops), and `simdgroup_load`/`store` (including
  > `transpose:true`) are ordinary `0x67`/`0xe7` memory ops.
  > **Target split, stated rather than blurred:** the two newly promoted fields and the liveness
  > proof are **M4**; the operand-selector, dtype, mode, `a_desc` and accumulate-enable results
  > are **A18** (EXP-0022 / EXP-O2C / RT-10-isa-pass2), and `matrix_mac`'s rows in
  > `tools/agx-isa/validation.json` still carry `target: A18` because that file has not yet been
  > regenerated with EXP-0147's promotions. The baseline encoding executes correctly on M4.
  > One recorded caveat carried forward: the `0x24` op-enable value is **fp32-datapath-specific** —
  > the half datapath (dtype `0x00`) uses byte+10 `0x8c` / byte+11 `0x00` and **its accumulate
  > byte is uncharacterized**.
  > Evidence: `experiments/EXP-0147-m4-emit-pipeline-misc/` (§2.1, `analysis/field_verdicts.json`,
  > `analysis/emittability.json`; 2 gated runs, 12 532 cases each, 98.37 % cross-run agreement),
  > `experiments/EXP-0022-simdgroup-matrix/`, `experiments/EXP-O2C-rt-tensor-tail/`.

---

- **P2-04 — Are mesh/object-stage register, varying, barrier, and termination semantics complete
  enough for independent compilation?**

  > **Answered 2026-08-28 (desk pass over EXP-0135 / EXP-0147 / EXP-0030 / EXP-M4-13) — P2-04 NO.
  > [HW + DESK-AUDIT]**
  > **The mesh/object *pipeline* contract is well characterized on M4; the mesh/object *stage ISA*
  > is not, and that is what this question asks for.**
  > What IS established (EXP-0135, M4/G16G, commit `661f1258`, 107 records per run x 2 runs,
  > 107/107 byte-exact on the gated fields): mesh is a **native hardware pipeline on M4**, with
  > both fixed-size compiler helper subroutines **byte-length-identical to A18** (128 B
  > `write_childcount`, 576 B `write_uvb`) and the `43 00 00 01` pre-call frame marker present
  > exactly once in each of the object and mesh streams, byte-identical whether or not the mesh
  > emits a triangle. Hard capacities: object->mesh payload **16,384 B**, enforced at
  > *pipeline-creation* time; UVB output **256 vertices** and **512 primitives** per meshlet, two
  > independently-capped fields (256 != 512), both enforced at *MSL-compile* time. Grid
  > amplification genuinely drives the rasterizer but **silently dies at exactly 65,536**
  > threadgroups (`STATUS OK`, zero error) against Metal's own reflected ceiling of 1,048,576 —
  > independently reproduced on the unrelated top-level indirect-draw mesh-grid mechanism. Buffer
  > allocation is **firmware-managed** (the 37-BO sel-9 size multiset is byte-identical across a
  > payload / vertex-count / primitive-count / amplification sweep).
  > What is NOT established, and blocks "independent compilation": **no field of any mesh-stage
  > instruction has ever been executed.** `mesh_out_src` (the 2-byte compact source op feeding the
  > following `0xe7` store) is `corpus-correlation` with its `sel` field `untested`, and EXP-0147
  > **pre-registered `mesh_out_src.sel` as not attempted** because it needs an object/mesh render
  > pipeline that harness does not build — it remains `untested` with that reason recorded.
  > `ibfe_mesh_attr` (bitfield-extract of a packed flat per-primitive mesh attribute, source-address
  > mode `byte+2 == 0x66`) is likewise `corpus-correlation` only. So the mesh **varying/output**
  > encoding is located but not emittable, and no experiment has isolated mesh/object-stage
  > **register** conventions, a stage-specific **barrier**, or the stage **termination** sequence
  > as distinct from the generic `threadgroup_barrier`/`stop`.
  > One interpretive correction EXP-0135 recorded and this block carries: the `0x43` marker is
  > **not** object/mesh-exclusive — `tools/agx-isa`'s DB already generalizes it to a pre-call
  > frame-setup marker appearing before every out-of-line CALL in any stage; object/mesh merely
  > hit it because their compiler-generated helpers are call sites. EXP-0030's narrower framing is
  > superseded on this point, not contradicted.
  > **Required compiler response:** treat the mesh/object stages as pipeline-level capabilities
  > with documented capacities, not as an independently compilable stage; a driver must still
  > obtain mesh-stage code from a path it does not synthesize field-by-field. Closing this needs a
  > mesh-pipeline splice harness — the same successor EXP-0147 names.
  > M4 target throughout (EXP-0030's A18 figures are cited for comparison only); A18 deferred.
  > Evidence: `experiments/EXP-0135-m4-mesh-object-shading/`,
  > `experiments/EXP-0147-m4-emit-pipeline-misc/RESULTS.md` §1 and §5,
  > `experiments/EXP-0030-mesh/`, `tools/agx-isa/validation.json` (`mesh_out_src`,
  > `ibfe_mesh_attr`).

---

- **P2-05 — Are ray-query instruction operands, control flow, memory layout, and synchronization
  complete enough for independent NIR lowering?**

  > **Answered 2026-08-28 (desk audit over EXP-0023 / EXP-M4-14 / EXP-O2C / EXP-M4-13) — P2-05 NO.
  > [DESK-AUDIT]**
  > **Ray tracing is proven native and end-to-end functional, but only 2 of the ~13 committed
  > ray/query instructions have any hardware-run field, and both were validated on A18.**
  > Established: `raytracing::` kernels emit opcode groups a hand-written software Moller-Trumbore
  > loop never produces (dedicated ray-intersect op, byte0 low-nibble `0x4` / `byte+1 0xea`, and
  > dedicated AS/ray-data loads byte0 `0xdf`; the software control contains **zero** of either),
  > so the silicon is real — but traversal is a **compiler-generated software BVH loop**
  > (a back-edge at offset -88), not a fire-and-forget trace instruction (EXP-0023, **A18**).
  > `rt_intersect` is `hardware-run` (6 known rays against a built acceleration structure returned
  > correct t / prim / barycentrics; EXP-0023 + RT-5, **A18**) and `rt_query_traverse` is
  > `hardware-run` (`intersection_query` committed-distance against a 2-triangle AS, near `t=1` /
  > far `t=5`, with every byte of the load swept; EXP-M4-14, **A18**).
  > Everything else in the family is decode-only in `tools/agx-isa/validation.json`:
  > `rt_as_load` and `rt_ray_mem` are `corpus-correlation` with the explicit note *"the traversal
  > loop they drive was executed end to end, but no field of this op was independently"* validated;
  > `rt_ray_mem_ldidx`, `rt_ray_mem_short`, `rt_transform_test`, `rt_query_traverse2`,
  > `ray_move_copy6`, `ray_move_zero6`, `ray_move_zinit` are "located and length-anchored over the
  > own-MSL RT corpus" (M4, `corpus-correlation`); `n4_rt_word` is `tokenization-only`.
  > That maps onto the question's four parts as: **operands** — not established beyond the two
  > executed ops; **control flow** — the traversal loop shape is observed, not specified;
  > **memory layout** — the ray/query struct marshalling ops are located but no field is decoded,
  > and the **BVH node format is GPU/firmware-authored and opaque to userspace** in a layout
  > userspace never constructs (EXP-0023 §"the BVH build is GPU/firmware-managed"), which is a
  > kernel/firmware coordination item rather than a userspace lowering input;
  > **synchronization** — untouched.
  > **Required compiler response:** do not attempt an independent NIR ray-query lowering. Consume
  > ray-tracing through whatever path supplies compiled traversal code, and coordinate the BVH
  > builder with the kernel/firmware team. Flipping this needs the ray/query family's operand
  > fields swept the way EXP-0147 swept `matrix_mac` — on **M4**, since the two executed results
  > are A18-era.
  > A18 target for both executed results; M4 target for the corpus locations; **no ray/query
  > operand field is M4-executed.**
  > Evidence: `experiments/EXP-0023-raytracing/`, `experiments/EXP-M4-14-a18-splice/`,
  > `experiments/EXP-O2C-rt-tensor-tail/`, `tools/agx-isa/validation.json` (`rt_*`, `ray_move*`,
  > `rtq_*`, `n4_rt_word`).

---

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

> **Target scope (user directive, 2026-08-28): this gate is measured against G16G (the local Apple
> M4) only.** The A18 Pro / G17P is hands-off (`CLAUDE.md`) and its replication is a later, separate
> pass expected to be inexpensive because every experiment here is committed and re-runnable. Where
> an item below names both parts, read it as G16G for closure purposes; G17P evidence remains
> welcome and, where it exists, is recorded — but its absence does not block a row.

1. A field-by-field Apple9 mapping and Linux end-to-end evidence for every existing Asahi queue,
   render, and compute UAPI field, with no new or repurposed field assumed.
2. A fully documented and experimentally validated Apple9 userspace helper/scratch protocol for VS,
   FS, CS, and preambles, including spill exhaustion and recovery on G16G (G17P deferred, per the target-scope note above).
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
10. A **G16G** evidence matrix covering simple/complex compute, direct/indexed/
    indirect draw, MRT, MSAA, depth/stencil, pipeline switches, multiple commands, links/barriers,
    spills, partial renders, exhaustion, and fault recovery.
    > **AMENDED 2026-08-28 (user directive).** This item originally demanded *"Independent G16G and
    > G17P evidence matrices"*. That predated the 2026-08-27 hands-off directive on the A18 Pro, and
    > the two could not both stand: every result in this repo is M4/G16G-only by that directive, so
    > requiring a G17P matrix made all sixteen P0/P1 rows permanently uncloseable. **Closure is now
    > measured against G16G alone.** G17P replication is deferred, not abandoned — it is expected to
    > be cheap precisely because the experiments are committed and re-runnable, so the work is
    > re-running them on a G17P host rather than re-deriving anything. Until that happens, every
    > G17P claim stays `INFERRED` per CODEX target discipline, and no row may silently generalize an
    > M4 result to A18.
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
