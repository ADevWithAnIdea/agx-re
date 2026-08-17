# AGX-RE information-coverage audit for an M4 / A18 Pro Mesa userspace driver

Date: 2026-08-17

Audited revisions:

- `agx-re`: `30e3d6a226a560314cb4f707e227c21c53dcdb23`
- upstream `mesa`: `3c4d3e46d19f2f4e951f3ae059543b03592f7944`

## Verdict

**No: `agx-re` does not currently contain enough information to implement a complete, conformant M4/A18 Pro userspace driver while preserving the exact existing Asahi UAPI and its division of responsibilities.**

It contains enough high-quality evidence for a research bring-up, a substantial disassembler, broad device and format identification, texture layout, descriptor experiments, simple compute, and likely a constrained triangle path assembled from captured templates. It does not yet provide all of the information needed to synthesize arbitrary legal shaders and command streams, populate every field the existing UAPI assigns to userspace, or implement the helper/background/end-of-tile programs required by that UAPI.

This conclusion is stricter than the repository's final `PASS` reviews for two reasons:

1. A byte-tokenizing disassembler or a byte-exact round trip of an observed program is not necessarily an assembler/compiler specification. A compiler must synthesize operands and state combinations that were not present in the captured corpus.
2. The reviews classify several unknowns as “kernel-managed” and therefore non-blocking. That is incompatible with the stated constraint of retaining the existing UAPI semantics: the existing UAPI explicitly requires userspace to supply helper programs, scratch data, BG/EOT programs, ZLS control, sample control, and other render state.

The repository's own master checklist corroborates the shortfall. `docs/mesa-userspace-requirements.md:67-71` still reports **5 done, 39 partial, and 8 not-started** rows. Later documents close some individual parameter sweeps, but they do not close the interface and synthesis gaps below.

## Audit criterion and scope

“Enough information” here means enough generation-specific hardware knowledge to implement the hardware-dependent portions of the current Mesa Asahi Gallium and Honeykrisp paths, for arbitrary valid workloads rather than only replaying captured Metal templates. Mesa-independent software policies and algorithms can be reused from upstream Mesa; they are not counted as missing RE.

The hard compatibility condition is the current `include/drm-uapi/asahi_drm.h`, without adding a new ioctl, command type, submit field, or changing which side owns a field. The current command vocabulary is render, compute, and three synthetic attachment-setting commands. Queue creation has `usc_exec_base`; render and compute commands contain userspace-provided helper programs; render additionally contains ZLS, PPP/sample control, BG/EOT, and partial BG/EOT values.

Native Metal 4 features beyond the current M1/M2 Mesa feature surface are listed separately. Lack of native ray tracing, mesh, or tessellation information should not block a first driver if existing Mesa compute-emulation paths are used and those features are not advertised.

Priority terminology:

- **P0**: blocks a complete driver or contradicts the unchanged UAPI.
- **P1**: blocks API correctness or broad feature coverage, but a deliberately reduced bring-up may avoid it.
- **P2**: optional feature, performance, or unsupported-encoding coverage.

## What is covered well enough to retain

The following areas contain substantial and useful RE, although some still have edge-case gaps listed later:

- A18 Pro G17P and M4 G16G identity, topology, page size, core-count delta, basic limits, and the observation that both use the Apple9 ISA family.
- Basic ALU, load/store, control-flow, subgroup, atomic, texture-family, and special-register discovery; the 96-GPR/two-half model; hardware interlocking rather than the older software scoreboard model.
- Direct compute-dispatch record fields, direct and indexed draw record fields, several indirect forms, primitive types, viewport counts, clip masks, sample counts, occlusion modes, and stage-boundary timestamps.
- Broad 32-byte texture and 8-byte sampler descriptor tables, many format codes, PBE width/height/base/stride fields, argument-buffer observations, and sampler-heap observations.
- A strong uncompressed texture-layout model: bpp-dependent tile edge, page-row granule, non-power-of-two padding, array/cube/3D planes, block formats, mip-tail alignment, and MSAA sample-minor layout.
- Depth/stencil/raster state locations and many exact fields; MRT placement and attachment-format derivation; fixed 32x32 raster tiles; memoryless behavior; programmable sample-position data as observed on Metal.
- The M4 experiments support a broad “same Apple9 encodings as A18” hypothesis, with device-capacity differences. They do not eliminate the synthesis gaps shared by both parts.

## P0: unchanged-UAPI and end-to-end submission gaps

### P0.1 Userspace scratch/helper protocol is missing and is assigned to the wrong side

This is the clearest incompatibility.

The existing UAPI's `drm_asahi_helper_program` says that the helper program is supplied by userspace. Render carries separate vertex and fragment helpers; compute carries a compute helper. Each includes a tagged binary address, configuration bits, and an uninterpreted 64-bit data value normally pointing at userspace's scratch allocator data.

Current Mesa confirms that this is not nominal data:

- `mesa/src/asahi/lib/agx_scratch.c` lays out the scratch BO, per-core headers, block lists, blocks, topology walk, and allocation buckets in userspace.
- Gallium fills `vertex_helper` / `fragment_helper` / compute `helper` from userspace scratch BOs.
- Honeykrisp does the same in `hk_queue.c`.

In contrast, `agx-re/docs/kernel-interface.md:360-365` says the kernel allocates scratch, binds the heap, and owns the per-core geometry. `docs/mesa-userspace-requirements.md:135` admits that the scratch base, per-core geometry, and doorbell/stack-map mechanism are un-RE'd.

Missing information:

- A18/M4 helper-program machine code or enough ISA/ABI knowledge to generate it.
- Helper special-register or doorbell operations corresponding to next/ack/nack allocation and their exact encodings/semantics.
- The helper input/output ABI and special registers used to receive `drm_asahi_helper_program.data`.
- Exact tagged-pointer low bits for `binary` and all `cfg` bits, for VS, FS, CS, main shader, and preamble scratch.
- Scratch BO header, per-core block-list, block descriptor, alignment, address-shift, block-count, and bucket rules for Apple9.
- Maximum active subgroups per core and maximum block size/count; the analogous old Mesa values are themselves partly marked uncertain and cannot be assumed.
- Mapping from `drm_asahi_params_global` topology/core masks to Apple9 helper core IDs.
- Reset, growth, concurrency, allocation-failure, and device-loss semantics.
- Proof that the existing helper fields retain their meaning on G16/G17, or a documented unchanged-UAPI-compatible way for the kernel to consume them.

Until this is closed, shaders that spill, stack-using programs, and some preambles cannot be supported correctly.

### P0.2 Graphics shader selection and code-BO handoff are not mapped to the existing UAPI

The docs say an Apple Metal draw contains no shader pointer and that firmware walks a self-describing `[size-header][machine-code]` code BO. They then require an out-of-band “code-BO base” submit parameter (`cmdstream/README.md:167-180`, `kernel-interface.md:196-204`).

The unchanged UAPI has no per-render code-BO-base field. It has only the queue-wide `usc_exec_base`, which establishes a 4 GiB shader VA window. Therefore the following must be established, not assumed:

- Whether the observed Metal code BO base maps exactly to queue `usc_exec_base`, to an existing render field, or to a kernel-private value.
- How arbitrary VS/FS pipeline selection works when multiple compiled pipelines coexist in the 4 GiB queue window.
- Whether the sized-block walk is truly hardware/firmware ABI, Apple compiler archive framing, or Apple userspace-driver bookkeeping.
- Complete code-BO header/block layout, alignment, stage ordering, block type/stage identity, sizes, relocations, and termination.
- How helpers, prologs, main shaders, epilogs, and multiple pipelines are addressed or selected.
- How the queue-wide base and 32-bit USC addresses/tags used by the existing UAPI are translated on G16/G17.

This may be resolvable without changing UAPI—for example if `usc_exec_base` is the missing handoff—but the repository does not demonstrate that mapping. The current statement that a new submit parameter is needed is not compatible with the constraint.

**M4 interim evidence (EXP-0042, still open):** 36 live multi-pipeline draws show
separable selectors rather than an unselected positional walk. A VS change emits the VDM
pair `(0x500, token)`; the two observed tokens follow VS creation order. The FS selector at
`0x58000+0x08` is a 32-bit offset in the code window, not an FS byte size, and points to the
payload of a `0x80` record immediately following the selected authored FS code record. The
code BO remained at `0x10000000000` under a 17-allocation perturbation. This materially
narrows selection and record framing but does not prove the Linux `usc_exec_base` mapping,
the consumer of the adjacent record, a general VS-token rule, or A18 behavior.

### P0.3 The Apple9 meaning of every existing render/compute UAPI field is not known

`kernel-interface.md:264-287` mostly repeats the current UAPI field list. Listing fields is not the same as documenting the Apple9 value userspace must compute.

Still missing or insufficiently mapped:

- Exact Apple9 `zls_ctrl` bit encoding for load/store, depth/stencil formats, tiling, compression, MSAA, layers, and partial renders. `mesa-userspace-requirements.md` explicitly treats it as partial/un-RE'd.
- `isp_zls_pixels` packing and all edge cases.
- `depth` / `stencil` base, compression base, stride, and compression-stride interpretation on G16/G17.
- Apple9 `ppp_ctrl` values and their relationship to state in the userspace stream.
- The meaning of the existing `ppp_multisamplectl`. The RE instead locates f32 sample pairs in a client BO at `+0x40`; it does not explain how that observation maps onto this mandatory 64-bit UAPI field or how the kernel finds the BO.
- Scissor-descriptor layout addressed by `isp_scissor_base`, including multiple viewports/scissors and empty rectangles.
- Depth-bias array layout addressed by `isp_dbias_base` and its relation to float/integer depth-bias mode.
- Complete occlusion heap allocation/addressing/availability rules behind `isp_oclqry_base`.
- All Apple9 render flags corresponding to scratch, empty-tile processing, no-vertex-clustering, and integer depth bias.
- Sampler heap base/count limits and whether the observed Apple global table is the object the existing UAPI expects.
- Correct `cdm_ctrl_stream_end` calculation for linked/chained Apple9 streams.
- Stage timestamp units and `command_timestamp_frequency_hz`. The docs call captured timestamps nanoseconds/period 1.0, while the UAPI explicitly requires conversion from a queried firmware tick frequency; this needs an end-to-end Linux mapping.

Every field needs an authoritative “userspace value -> kernel marshaling -> observed Apple9 behavior” test. The present work mostly traces the macOS side and extrapolates the Linux contract.

**M4 interim evidence (EXP-0043, still open):** for the tested direct-dispatch
shape, 732 contiguous 0x2c CDM records are followed by `0x40000000`; record 733
replaces that terminal with a two-word link to a second captured segment, whose
last record terminates normally. This locates the stream end and rollover
boundary on macOS but does not yet establish how Linux must populate
`cdm_ctrl_stream_end` for arbitrary linked pools.

### P0.4 Background, end-of-tile, and partial-render programs are not specified

The unchanged UAPI requires userspace to provide four `drm_asahi_bg_eot` records: BG, EOT, partial BG, and partial EOT. Each includes a tagged USC program address and a packed resource specifier.

The RE describes the high-level load/render/store attachment chain, but it does not provide enough information to construct all four programs for arbitrary render-pass state. Missing:

- The BG/EOT shader ABI, inputs, outputs, tilebuffer addressing, sample/layer handling, and invocation rules.
- Exact tile load, clear, resolve, store, depth/stencil, and partial-render instruction sequences or compiler lowerings.
- Resource specifier field layout and derivation for each program.
- USC bind words/tags and tagged pointer low bits used by the four UAPI records.
- Per-format pack/unpack, integer/sRGB conversion, clamping, write masks, and MSAA resolve behavior.
- Partial-render save/restore programs and the state/data contract with firmware overflow handling.
- Empty-tile/clear behavior and when `PROCESS_EMPTY_TILES` is mandatory.
- Validation for memoryless, MRT, layers, mixed formats, depth/stencil-only, discard/load/store/dont-care, and partial render combinations.

This is required even if the firmware decides when a partial render occurs; the UAPI still assigns the programs to userspace.

### P0.5 No complete, relocatable Apple9 command/state packing specification exists

There is no Apple9 equivalent of Mesa's `src/asahi/genxml/cmdbuf.xml`. Under `agx-re/docs`, the only machine-readable specification is the ISA XML. By comparison, the existing Mesa command schema contains 84 structures and 37 enums covering CF/USC, PPP, VDM, CDM, ZLS, and command-register state.

The command-stream prose contains valuable field discoveries, but its own introduction still says the individual structures are only partially correlated. Much of the presentation is a captured Metal memory layout at fixed VAs such as `0x18000`, `0x58000`, and `0x68000`, rather than a complete relocatable packet grammar.

Missing command/state information includes:

- Packet/block type encoding, length rules, alignment, reserved-zero requirements, legal order, and termination for complete VDM and CDM streams.
- VDM/CDM stream link, call/return, terminate, and barrier packets.
- Cache-control and coherency bits for barriers and transitions between compute, tiler, fragment, texture, PBE, and CPU visibility.
- Safe stream size limits, chaining, command-pool rollover, multi-draw/multi-dispatch behavior, and recovery from a full segment.
- A complete PPP/state schema rather than offsets into a single fixed state-pool template.
- Region clip, viewport-control headers, scissor, depth bias, output/varying counts, fragment control, fragment shader words, and every enable/presence interaction.
- Full USC program grammar for arbitrary uniform ranges, textures, samplers, shared memory, shader resources, preshaders, and fragment properties.
- Relocation rules and which addresses are absolute, shifted, split, queue-relative, stage-relative, or firmware-private.
- Separation of hardware-consumed packets from Apple Metal userspace bookkeeping and macOS firmware queue-context data.
- State transition tests: repeated draws with partial state changes, pipeline changes, multiple render passes, mixed compute/render, secondary command buffers, and device-generated commands.
- Exact indirect global/local dispatch modes and barrier forms; the current “Open items” section still carries these gaps even though some earlier direct-dispatch fields were later resolved.

Captured fixed templates may bring up one workload but are not a sufficient basis for a general packer.

**M4 interim evidence (EXP-0043, bounded partial):** 22 successful live cases
establish 0x2c CDM repetition and `0x40000000` termination, variable-prefix VDM
draw repetition and `0xc0000000` termination, plus exact rollover for the tested
shapes. CDM record 733 replaces the first-segment terminal with
`[0x20000100, 0x00158000]` naming captured VA `0x10000158000`; VDM draw 329
similarly emits `[0x80000000, 0x00088000]` naming VA `0x88000`. The 1024-dispatch
and 384-draw cases completed across both segments. Link packing remains
STRUCTURAL until controlled mutation/replay, and no general pool-capacity,
barrier, call, indirect, PPP/USC, or A18 rule is claimed. Generic all-BO analyses
were quarantined; conclusions use only an eight-VA explicit evidence allowlist.

### P0.6 The ISA database is a disassembly/tokenization database, not yet a compiler-ready encoding specification

`docs/isa/agx3.xml` is large: 329 instruction entries. It also contains 130 `inferred / not yet bit-decoded` comments and 6 placeholder/fallback entries labelled `NOT A STANDALONE HARDWARE OPCODE`. Its header warns that some `<zero>` elements represent unresolved bits rather than known hardware zeros.

The M4 document's “100% byte coverage” means all corpus bytes can be tokenized with a known length. The same document says only about 79% had full mnemonic descriptors at that point and the rest were family-labelled/length-only. Whole-program round-trip reproduces existing bytes; it does not prove arbitrary operands can be encoded.

Missing compiler information:

- Complete operand fields for every instruction form and all registers r0-r95, especially high-register integer, memory, texture, atomic, control-flow, and fragment forms.
- Definitive source/destination widths, alignment constraints, immediate ranges, modifier availability, type interpretation, and short/long-form selection.
- Complete texture/image operands for array, 3D, cube, MSAA, comparison, gather, LOD, face/layer/sample index, and result registers.
- Exact fragment interpolation, tile load/store, sample-mask, depth/stencil emission, raster-order/interlock, and helper-thread encodings and ordering.
- Complete call/return/frame/spill/fill and stack/scratch address semantics.
- Exact memory scope, ordering, cache/coherency, barrier, atomic, and image-store semantics.
- Complete special-register enum, preload rules, and which operations may read uniforms.
- Complete subgroup/quad/reduction subop/type inventory and inactive-lane semantics.
- Semantics of range-reduction/SFU/pad/compound sequences currently preserved as raw or inferred tokens.
- A compiler opcode-properties table analogous to Mesa's `agx_opcodes.py`: numbers and types of destinations/sources, side effects, eliminability, reorderability, execution class, control-flow behavior, and scheduling constraints.
- Hardware behavior needed by NIR lowerings: float rounding/denorm/NaN/minmax behavior, robust/OOB accesses, interpolation precision, 16/64-bit corner cases, texture/image errata, and late-Z/sample-mask interactions.

At minimum, every instruction a supported NIR path can emit must be constructible from semantic operands and tested independently of an Apple compiler-generated byte template.

### P0.7 Shader container, program extent, metadata, and resource-spec generation are incomplete

The docs use captured `__GPU_METADATA` / FlatBuffer fields for program length, GPR count, uniform count, scratch size, threadgroup memory, and occupancy classification. They identify individual field numbers but do not contain a full schema or writer.

Missing:

- Determination of which captured metadata is consumed by hardware/firmware and which exists only in Metal binary archives.
- If firmware-consumed: complete schema, versions, defaults, checksums/offsets, stage records, alignment, and writer rules.
- If not firmware-consumed: the exact Apple9 replacement values that the existing UAPI/kernel command context needs.
- Exact program extent/entry selection, since the docs say the in-band stop token is not authoritative and extent is out-of-band.
- Resource-spec encoding from compiler results: GPRs, uniforms, textures, samplers, shared/tile memory, scratch, preamble, and stage properties.
- Complete sized-block code header and uniform-preamble container construction.

Without resolving this layer, successfully compiling instruction bytes does not produce a launchable shader.

**M4 interim evidence (EXP-0042, still open):** exact authored shader bytes occur in live
records with a `0x40`-byte zero-reserved header, aligned total record size in word 0,
authored constant program, authored main, and padding. Distinct equal-sized FS records have
distinct relative selectors and distinct output. The adjacent `0x80` record is only
STRUCTURAL evidence; whether hardware, firmware, or macOS userspace consumes either header
is unknown. Resource-spec generation and an independent container writer remain missing.

### P0.8 Complete shader-stage ABI and programmable epilogs are missing

The RE has useful pieces of the uniform preload and UVS/varying path, but not the complete driver/compiler ABI for all stages.

Missing:

- Full VS input/preload ABI, vertex-fetch descriptor/table layout for all formats, instancing/divisors, base vertex/instance, and robust access.
- Full FS input ABI: interpolation modes, center/centroid/sample, perspective/noperspective/flat, front-facing, coverage/sample mask, point coordinates, primitive/layer/viewport IDs, helper lanes, and barycentrics.
- FS output ABI for color, dual-source color, depth, stencil, sample mask, discard/demote, and ordering with tests.
- Compute sysvals, grid/workgroup/local IDs, dynamic shared memory, indirect dispatch, and preamble ABI.
- Prolog/main/epilog linking, live-in/live-out registers, branch/link mechanics, register allocation across parts, and resource-spec merging.
- Shader-key sideband such as early/late Z, side effects, interlocks, helper behavior, no-epilog-discard, and format conversion.
- Tilebuffer ABI shared by FS, programmable blend, BG, and EOT programs.

Programmable blend is a specific blocker. The docs establish that blend equations live in a compiler-generated FS microprogram and intentionally do not decode it. They sweep all factors/operations only to prove that the fixed-function pool does not encode the equation. A driver still needs:

- Lowerings for all blend factors and operations, separate RGB/alpha, dual-source, logic ops, write masks, blend constants, alpha-to-coverage/one, and min/max rules.
- Tilebuffer read/write and per-format conversion instructions/ABI.
- sRGB, normalized/integer/float clamp and rounding rules, NaN behavior, and MSAA/sample-mask handling.
- A derivation for the observed blend/store program-class values and extended-source flag, not just three example constants.

This can be independently implemented rather than copied from Apple's microprogram, but the necessary hardware ABI and conversion semantics must still be characterized.

## P1: correctness and broad feature-coverage gaps

### P1.1 Render-target/PBE and attachment structures remain only partially described

The later 46-format attachment-word sweep is strong, and PBE dimensions/base/stride are known. The full 32-byte PBE/storage descriptor and the three 0x300-byte load/render/store structures are not fully specified.

Missing:

- Every PBE field: type/layer/mip/sample/array selection, component mapping, access/control word, rotate/flip/mode, coherency, and all reserved requirements.
- Complete layout of all bytes in each 0x300 segment, including which values are invariant hardware requirements versus Apple-driver data.
- Meaning/ownership of store program ID `0x6f`; the docs call it firmware-managed but the exact unchanged UAPI has no store-program field.
- Surface offsets/strides for layers, mip levels, resolve targets, memoryless, compression, depth/stencil, and mixed MRT formats.
- Load/store/dont-care/clear/resolve behavior over all formats and sample counts.

### P1.2 Format capability data is incomplete even where descriptor codes are known

A descriptor-code table does not by itself establish which API features are valid.

Needed per-format data:

- Sampled, filtered, storage-read, storage-write, atomic, renderable, blendable, depth/stencil, linear-layout, compressed, MSAA, resolve, and sparse support.
- Required feature/emulation rules for RGB32, packed formats, sRGB storage, integer filtering, depth/stencil aspects, YUV, BC/ASTC/ETC/EAC, and PVRTC if exposed.
- Exact pack/unpack, normalization, rounding, and swizzle behavior.
- Limits and alignments for row pitch, layer/depth pitch, mip offsets, and buffer textures.

### P1.3 Texture/image ISA breadth and edge behavior are incomplete

Although many texture families tokenize, exact synthesis and behavior are incomplete for non-2D operands and uncommon modes. Needed:

- 1D array, cube array, MSAA array, buffer/typed-buffer, 3D, gather, comparison, projected, explicit/implicit LOD, derivatives, offsets, and sparse-result encodings.
- Result component/mask/type, coordinate widths, face/layer/sample/reference operands, and high registers.
- LOD/clamp/aniso edge behavior, unnormalized coordinates, border behavior, cube seams, integer/sRGB rules, and OOB/robust semantics.
- Image access ordering/coherency and format-dependent atomics.

### P1.4 Memory model and synchronization are not specified to Vulkan/GL correctness level

The hardware-interlock finding addresses instruction result readiness; it does not replace an API memory model.

Missing:

- Cache domains and visibility between USC loads/stores, textures, PBE, tile memory, tiler, fragment, compute, and host.
- Device/workgroup/subgroup/invocation scope mappings and acquire/release/relaxed/seq-cst behavior.
- Barrier/fence encodings and required flush/invalidate bits for every producer/consumer transition.
- Atomic ordering and availability by type/width/address space.
- Cross-queue and in-submit interaction between UAPI `vdm_barrier` / `cdm_barrier` and control-stream barriers.
- Host-map coherency, writeback/write-combine rules, and cache maintenance expectations.

### P1.5 Robustness, sparse residency, and VM conventions are incomplete

The Linux kernel supplies VM bounds at runtime, so fixed observed Metal VAs should not be treated as ABI. Needed:

- Confirmed G16/G17 values/constraints for `vm_start`, `vm_end`, `vm_kernel_min_size`, command/attachment limits, feature bits, revision, chip ID, and timestamp frequency.
- 4 GiB shader-window mapping and all USC relative-address limits.
- Robust buffer/image access behavior, zero/scratch pages, guard regions, maximum load shifts, and soft-fault behavior.
- Sparse page-table/folio geometry, read-only/read-write shadow mapping, tile mapping granularity, mip tails, residency/aliasing, and synchronization. A sparse descriptor flag plus 16 KiB page size is insufficient.
- BO alignment, executable/read-only/writeback behavior, sharing, and device-address rules as used through the existing VM_BIND/GEM UAPI.

### P1.6 Queries and timestamps need complete API semantics

The RE locates occlusion mode/offset and observes stage-boundary timestamps, but a driver also needs:

- Counter heap layout, alignment, allocation limits, accumulation, reset, availability, copy, and simultaneous-query behavior.
- Precise start/end stage placement and ordering guarantees.
- Timestamp tick frequency, wrap behavior, calibration with `GET_TIME`, and conversion rules under the existing UAPI.
- Pipeline-statistics implementation/emulation and synchronization.

### P1.7 Indirect and device-generated command coverage is incomplete

Needed:

- Complete direct/indirect global-vs-local CDM modes and parameter-memory formats.
- Multi-dispatch and multi-draw stream construction with links/barriers.
- Count-buffer, indexed/non-indexed, base instance/vertex, restart, and error/bounds rules.
- Device-generated command emission grammar, writable command memory, cache flushes, validation, and interaction with command stream limits.

### P1.8 Conformance-relevant numerical and rasterization behavior is under-characterized

`EXP-0047-m4-numerical-behavior` supplies a narrow M4/G16G source-path baseline:
two exact repeats of authored no-fast-math Metal kernels show DAZ/FTZ-like fp32
add/multiply behavior, preserved representable fp16 add/multiply subnormals,
operand-B selection for tested equal/both-quiet-NaN min/max cases, and the tested
`rint` ties-even / `round` ties-away behavior. Raw-bit identity controls exclude
buffer transport as the source of the subnormal result. This is compiler-emitted
Metal-path evidence, not independently generated native-instruction semantics,
not A18 validation, and not conformance closure.

Needed for honest Vulkan/GL capability advertising:

- Float16/float32 rounding, denorm, NaN, signed-zero, conversion, min/max, reciprocal/transcendental accuracy, and integer overflow/shift rules.
- Line/point size/rasterization, provoking vertex, polygon modes, depth clip/clamp, depth-bias formulas, conservative rasterization if exposed, and multisample coverage rules.
- Interpolation precision and centroid/sample selection.
- Early/late depth/stencil tests, discard/demote/helper interaction, side effects, and raster-order/interlock behavior.
- Limits: viewports, attachments, image dimensions/layers/mips, shared memory, workgroups, descriptors, push uniforms, alignments, and subgroup operations.

## P2: optional/performance/advanced coverage gaps

These do not have to block a first driver if disabled or emulated, but they prevent the broad “whole Apple9 userspace stack” claim.

### P2.1 Lossless-compression codec

Aux placement, size, eligibility, and some state bytes are known. The 8x4 block codec and exact state-byte meanings remain opaque, as does the precise per-sample MSAA auxiliary ratio. Compression can be disabled for correctness, so this is a performance/CPU-access feature unless firmware/PBE enables it unavoidably.

### P2.2 Native tessellation

The high-level native path is observed, but the packed control-point/partition sub-bits, complete patch record, factor/indirect modes, generated-buffer ABI, barriers, and firmware-owned domain/parameter buffers are not specified. Existing Mesa compute tessellation is the safe unchanged-UAPI fallback until this is closed.

### P2.3 Native mesh/object shading

The mesh opcode and basic record are observed, but the complete dispatch descriptor, object-to-mesh handoff, output/UVB layout and sizing, rasterizer linkage, memory barriers, indirect/ICB details, and kernel allocation contract are not. The existing UAPI has no explicit UVB service; use emulation or do not expose the feature.

### P2.4 Ray tracing and acceleration structures

Traversal op families are partly identified, but operand subfields remain inferred/inert in places. BVH node format, builder, reorder stage, scratch, compaction/update/serialization, geometry formats, motion data, and synchronization are missing. The docs assign BVH build to firmware but the exact UAPI provides no BVH-build command. Under the unchanged UAPI, native RT therefore needs either a fully userspace compute builder plus the node format, or must remain unexposed.

### P2.5 Sparse, custom border, stream output/GS, and Metal-unreachable codes

Some of these can be emulated with current Mesa infrastructure. Raw sampler address codes 4/6/7, swizzle 6/7, border code 3, anisotropy above 16, arbitrary restart, polygon-point fill, native GS/XFB, and several unreachable descriptor/opcode combinations remain untested. Do not advertise native behavior based on unused bit capacity.

### P2.6 Performance model

Full occupancy curves, latency/throughput, scheduling classes, register-pressure threshold derivation, cache behavior, tile/parameter-buffer sizing, and optimal workgroup-repacking heuristics are incomplete. Wrong values may be slow rather than incorrect, provided hard resource limits are separately known.

## M4-specific qualification

`docs/m4-deltas.md` provides good evidence that G16G and G17P share Apple9 encodings. The statement at line 5 that A18 docs plus the delta are enough for a driver is nevertheless stronger than the evidence because the shared baseline has the P0/P1 gaps above.

Known M4-specific facts to retain are G16G identity, ten cores, larger maximum Metal buffer length, and the same observed Apple9 stream/descriptor/tiling behavior. Still needed for Linux are exact kernel-reported params and end-to-end validation of the helper, UAPI render fields, and firmware context on G16G.

There is also a stale wording conflict: `m4-deltas.md:86` starts with `T=64 bpp<=4`, while the authoritative `tiling/README.md:23-40` and the later text correctly establish bpp1 uses T=128. Implementers must follow the authoritative formula, not the summary sentence.

## Documentation, provenance, and licensing issues that affect usability

These are not hardware RE gaps by themselves, but they prevent the current pile from being a safe implementation specification.

### Broken and stale cross-references

- Many docs refer to `../mesa` from inside `agx-re/docs`; that resolves to `agx-re/mesa`, which is empty in this checkout. The actual upstream tree is sibling `/home/user/asahi/mesa` and is reached as `../../mesa` from the docs.
- `cmdstream/README.md` begins by saying full bit-level decode is deferred and ends with open items that later paragraphs partly resolve.
- `mesa-userspace-requirements.md` retains the 5/39/8 coverage count and several stale pre-M4 gaps.
- ROADMAP and review status text mixes historical and current conclusions.
- Derived documents sometimes preserve superseded tiling and sample-position claims. The authoritative source for each corrected fact is not always mechanically enforceable.

Before implementation, consolidate the final facts into versioned, machine-readable schemas and make stale historical sections clearly non-normative.

### Evidence classification

Each claimed field should distinguish:

- hardware-splice/run validated;
- isolated parameter byte-diff;
- corpus correlation;
- structural tokenization/length only;
- inferred from one captured template;
- Metal API accept/reject only;
- firmware/macOS-private rather than hardware ABI;
- untested or unreachable.

The current reviews sometimes promote tokenization and template round-trip to “emittable,” which hides precisely the operand/state combinations a compiler must create.

### License boundary

`agx-re/README.md` licenses code, scripts, machine-readable data, XML, and captures under GPL-3.0, and prose documentation under CC-BY-NC-SA-4.0. Mesa's core and Asahi sources are predominantly MIT-licensed.

That means direct copying of generators, tables, XML, or prose into Mesa is not automatically compatible with the intended MIT-licensed driver. This is not legal advice, and hardware facts may be independently implementable, but the project needs one of:

- relicensing/dual-licensing from the copyright holder;
- a deliberate clean-room factual re-expression into MIT-licensed schemas/code; or
- a reviewed separation that satisfies both projects' licenses.

Resolve this before treating `agx3.xml`, tools, or prose tables as material that can be imported upstream.

## Minimum evidence required to close this audit

The information-coverage gate should not pass until all of the following exist:

1. A field-by-field Apple9 mapping for every existing Asahi queue/render/compute UAPI field, with no new field assumed and an end-to-end Linux test for each nontrivial value.
2. A working Apple9 userspace scratch/helper allocator and helper shader using the existing `drm_asahi_helper_program` ABI, tested for VS/FS/CS spill and preamble scratch on both A18 Pro and M4.
3. A demonstrated mapping of graphics code-BO selection to existing `usc_exec_base`/USC fields, plus a complete code/container/resource-spec packer that can switch among multiple pipelines.
4. Machine-readable Apple9 command/state schemas covering all VDM, CDM, PPP, USC, ZLS/CR values userspace emits, including links, barriers, termination, relocations, and reserved bits.
5. A compiler-ready Apple9 opcode/property database and assembler validated by generating—not replaying—representative shaders across all supported NIR operations and register ranges.
6. Complete stage ABI documentation and tests for VS, FS, CS, prologs/epilogs, varying linkage, tilebuffer access, helper programs, and BG/EOT/partial programs.
7. Independently generated programmable blend/logic/format-conversion epilogs covering every advertised blendable format, factor, operation, dual-source mode, write mask, and sample mode.
8. Exact ZLS, depth/stencil, scissor, depth-bias, occlusion, PPP/sample control, BG/EOT, and partial-render values for the existing render command.
9. A format feature table and broad texture/image/PBE tests sufficient to derive every advertised API format property.
10. A defined memory/cache/barrier model and tests for all compute/render/texture/PBE/host transitions.
11. Robustness, sparse, query, timestamp, indirect-command, and device-limit behavior sufficient for the extensions actually advertised.
12. A test matrix on both G16G and G17P covering simple and complex compute, indexed/indirect/MRT/MSAA/depth-stencil draws, pipeline changes, multiple commands per submit, links/barriers, spill, partial renders, and fault recovery.
13. A license/provenance path under which the resulting Mesa implementation and generated tables can be upstreamed.

Native compression, mesh, tessellation, and RT may be excluded from the first gate if they are disabled or use already-available Mesa emulation. They should not be counted as complete merely because Metal accepts a shader or a captured record can be tokenized.

## Bottom line

The RE pile is valuable and unusually broad, but its strongest evidence is concentrated in observation and decoding. The missing layer is the one a driver most needs: complete synthesis specifications and the exact Linux UAPI contract for helper/scratch and render-pass programs/state. The fastest way to turn the pile into sufficient coverage is to close the unchanged-UAPI blockers first; more exotic opcode or capability sweeps do not compensate for those omissions.
