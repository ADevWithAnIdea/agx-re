# Apple M5 (Apple10 / G17G) — Capability Matrix

**Experiment:** EXP-M5-04-capabilities · **Method:** clean-room capability probe (our own
`probe.m` calling public Metal APIs; public SDK headers read for enum names). Raw:
`raw/probe_output.txt`, `raw/gpu_config.txt`.

This is the **expected Metal-exposed capability surface** of the M5 for OBJECTIVE 2 ("know
every hardware capability Metal exposes"). Every row is a capability the driver *advertises*
as present. The rightmost column is the RE status for this project: whether the underlying
hardware mechanism (instruction / descriptor / cmdstream field / kernel-managed resource)
has yet been characterized for the A18/M-series work. On a fresh M5 baseline essentially
everything is **NYC = NOT-YET-CHARACTERIZED** and becomes a work item.

Legend for "HW-RE status":
- **native** — confirmed to map to a decoded ISA op / descriptor / cmdstream field already.
- **kernel-managed** — realized via the userspace↔kernel submit/BO/VM interface.
- **NYC** — NOT-YET-CHARACTERIZED on M5; needs ISA/cmdstream/descriptor RE. (default here)

## 1. Identity / family / limits

| Capability | M5 value | Advertised? | HW-RE status |
|---|---|---|---|
| Metal GPU family | **Apple10 (1010)** | YES | native (family gates feature set) |
| Metal version | **Metal 4** (5002) | YES | NYC (Metal4 cmd model) |
| Highest MSL accepted | **4.1** | YES | NYC |
| GPU cores | 8 | YES (ioreg) | n/a (config) |
| SIMD width | **32** | YES | native (warp size) |
| maxThreadsPerThreadgroup | (1024,1024,1024) | YES | native |
| maxTotalThreadsPerThreadgroup | 1024 | YES | native |
| threadgroup memory | 32 KiB | YES | NYC (imageblock/tg-mem model) |
| maxBufferLength | ~8.88 GiB | YES | kernel-managed (VM/BO) |
| recommendedMaxWorkingSetSize | ~11.84 GiB | YES | kernel-managed |
| unified memory | YES | YES | kernel-managed |

## 2. Argument buffers / resource model

| Capability | M5 value | Advertised? | HW-RE status |
|---|---|---|---|
| `argumentBuffersSupport` | **Tier 2** (=1) | YES | NYC (arg-buffer descriptor layout) |
| `maxArgumentBufferSamplerCount` | 500000 | YES | NYC |
| `readWriteTextureSupport` | **Tier 2** (=2) | YES | NYC (RW texture descriptor) |
| Metal 4 argument tables (`newArgumentTableWithDescriptor:error:`) | present | YES | NYC (Metal4 binding model) |

## 3. Ray tracing (Apple advertises RT for this family)

| Capability | M5 value | Advertised? | HW-RE status |
|---|---|---|---|
| `supportsRaytracing` | **YES** | YES | NYC (RT intersection ISA/descriptors) |
| `supportsRaytracingFromRender` | **YES** | YES | NYC |
| `supportsPrimitiveMotionBlur` | **YES** | YES | NYC |
| Intersection function type (=6) | present | YES | NYC |

RT is a headline Apple-advertised capability for Apple9+; M5 confirms full RT + RT-from-render
+ motion blur. The acceleration-structure build/traversal path and intersection-function ABI
are prime characterization targets.

## 4. Function pointers / dynamic libraries / stitching

| Capability | M5 value | Advertised? | HW-RE status |
|---|---|---|---|
| `supportsFunctionPointers` | **YES** | YES | NYC (call ABI) |
| `supportsFunctionPointersFromRender` | **YES** | YES | NYC |
| `supportsDynamicLibraries` | **YES** | YES | NYC |
| `supportsRenderDynamicLibraries` | **YES** | YES | NYC |
| `functionHandleWithFunction:` | present | YES | NYC |
| `newLibraryWithStitchedDescriptor:error:` | present | YES | NYC |

## 5. Mesh / geometry / vertex amplification

| Capability | M5 value | Advertised? | HW-RE status |
|---|---|---|---|
| **Mesh shading** (object+mesh pipeline builds) | **YES — pipeline build SUCCESS** | YES | NYC (object/mesh stage ISA + cmdstream) |
| Object function type (=8) / Mesh function type (=7) | compiled OK | YES | NYC |
| Vertex amplification 1/2/4/8 | **all YES** | YES | NYC (amplification cmdstream) |

Mesh support is proven the strong way: we compiled our own object + mesh + fragment stages
and the runtime **successfully built** an `MTLMeshRenderPipelineState` (no GPU submission).
This confirms the M5 exposes the mesh pipeline; the stage encodings are unmapped.

## 6. Texture / render feature flags

| Capability | M5 value | Advertised? | HW-RE status |
|---|---|---|---|
| `supports32BitFloatFiltering` | YES | YES | NYC (sampler/filter path) |
| `supports32BitMSAA` | YES | YES | NYC |
| `supportsBCTextureCompression` | YES | YES | NYC (BC formats + tiling) |
| `supportsPullModelInterpolation` | YES | YES | NYC (interpolation ISA) |
| `supportsShaderBarycentricCoordinates` | YES | YES | NYC (barycentric sysvals) |
| `areBarycentricCoordsSupported` | YES | YES | NYC |
| `areProgrammableSamplePositionsSupported` | YES | YES | NYC (sample-position state) |
| `areRasterOrderGroupsSupported` | YES | YES | NYC (ROV/raster-order) |
| `supportsQueryTextureLOD` | YES | YES | NYC (LOD query ISA) |
| `depth24Stencil8PixelFormatSupported` | **NO** | (never on Apple Si) | native-absent (use D32S8) |
| Texture sample counts | **1,2,4,8 = YES; 16 = NO** | YES | NYC (MSAA resolve) |

## 7. Sparse textures / tensors

| Capability | M5 value | Advertised? | HW-RE status |
|---|---|---|---|
| Sparse tile size (default) | **16 KiB** | YES | NYC (sparse/PTE mapping) |
| Sparse tile @ page 16 KiB / 64 KiB / 256 KiB | 16384 / 65536 / 262144 | YES | NYC |
| Metal 4 **tensor** API (`newTensorWithDescriptor:error:`) | **present (responds YES)** | YES | NYC (MTLTensor / neural-accel path) |
| `newTensorWithDescriptor:offset:error:` | absent (NO) | — | — |

The `MTLTensor` device entry point is present on the M5 stack — relevant to Apple's
"Neural Accelerator in each GPU core" claim for this generation. Whether tensors map to a
dedicated matrix/neural instruction path or are lowered to existing SIMD-group-matrix ops is
a high-value characterization target.

## 8. Counters / timestamps

| Capability | M5 value | Advertised? | HW-RE status |
|---|---|---|---|
| counterSets | **timestamp** only | YES | kernel-managed (counter heap) |
| `supportsCounterSampling(AtStageBoundary)` | **YES** | YES | kernel-managed |
| `...(AtDraw/Dispatch/TileDispatch/Blit Boundary)` | **all NO** | — | native-absent |
| `sizeOfCounterHeapEntry:` (Metal4) | present | YES | NYC |

Only **stage-boundary** timestamp sampling is supported — draw/dispatch/tile/blit-boundary
sampling is unavailable, matching prior Apple-Silicon behavior. A driver must not assume
finer-grained counter sampling.

## 9. Metal 4 device surface (selector presence)

All present (respond YES) on M5: `newResidencySetWithDescriptor:error:`,
`newIOCommandQueueWithDescriptor:error:`, `sizeOfCounterHeapEntry:`,
`newCommandQueueWithDescriptor:`, `newLibraryWithStitchedDescriptor:error:`,
`newArgumentTableWithDescriptor:error:`,
`newComputePipelineStateWithDescriptor:options:reflection:error:`,
`functionHandleWithFunction:`, `sparseTileSizeInBytesForSparsePageSize:`.
Absent (NO): `sparsePageSize`, `newTensorWithDescriptor:offset:error:`,
`newCommandQueueWithDescriptor:error:`. → The M5 exposes the full **Metal 4** device object
model (residency sets, IO command queues, argument tables, counter heaps, function stitching,
tensors). The entire Metal 4 command/binding model is **NYC** and is a major cmdstream target.

---

## Objective-2 work queue (everything advertised but NYC)

Highest-value HW characterization targets seeded by this baseline, roughly in Apple-advertised-
capability order:

1. **Ray tracing** — accel-structure descriptors, intersection ISA, RT-from-render, motion blur.
2. **Mesh + object shaders** — new pipeline stages, payload/threadgroup model, cmdstream encoding.
3. **Metal 4 tensors / neural accelerators** — `MTLTensor` lowering; dedicated matrix/neural ops?
4. **Metal 4 binding model** — argument tables, residency sets, argument-buffer Tier-2 layout.
5. **Dynamic Caching / register model** — implied by Apple9+ generation (probe here is silent on it).
6. **Function pointers / dynamic libraries / stitching** — indirect-call ABI.
7. **RW textures Tier 2, ROV, programmable sample positions, barycentrics, pull-model interp.**
8. **Sparse textures** — 16 KiB tile, PTE/mapping model.
9. **SIMD-group matrix / cooperative ops** — (not directly in this device probe; needs MSL probe).

> Note: `supportsFamily`/device flags tell us a capability is **present**, not **how**. Each
> "NYC" row becomes a downstream ISA/cmdstream/descriptor experiment. Absence rows
> (depth24stencil8, sampleCount 16, fine-grained counter sampling, Apple11) are first-class
> negative results: features a Vulkan/GL layer on M5 must emulate or refuse.

## Clean-room attestation

All values are driver-reported responses to our own program's public Metal API calls, or
textual system data, or public SDK-header enum text. No Apple binary was disassembled or
introspected. Reproducible via `./run.sh`.
