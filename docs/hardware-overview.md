# A18 Pro GPU — Hardware Overview (identity, topology, capabilities, interface)

**Status:** first draft (baseline recon). **Provenance:** every value here is a
*hardware/config value* read from the IORegistry / IODeviceTree, `sysctl`,
`system_profiler`, loaded-kext metadata, or a read-only Metal capability property.
No binary was disassembled; no GPU work was run. Source experiment:
`../experiments/EXP-0002-hw-identity-recon/` (clean-room category **HW-PROBE**).
Rows also logged in `../PROVENANCE.md`.

Device under test: "MacBook Neo", Apple A18 Pro, SoC **T8140**, macOS 26.6 (25G5043d),
kernel `RELEASE_ARM64_T8140`.

---

## 1. GPU identity & internal codename

| Property | Value | How obtained |
|----------|-------|--------------|
| Marketing name | **Apple A18 Pro** | Metal `MTLDevice.name`; accel node `model`; `system_profiler SPDisplaysDataType` |
| SoC | **T8140** | kernel build string; device-tree `compatible = "gpu,t8140"` |
| **GPU internal codename** | **G17P** | Metal `MTLDevice.architecture.name = "applegpu_g17p"`; kernel class `AGXAcceleratorG17P`; kext `com.apple.AGXG17P`; Metal plugin `AGXG17PDevice` / `AGXMetalG17P` |
| GPU generation | **17** (`gpu_gen=17`) | accel node `GPUConfigurationVariable` |
| GPU variant | **"P"** (`gpu_var="P"` → G17**P**) | accel node `GPUConfigurationVariable` |
| Device-tree node | **`sgx@70000000`** (`device_type/name = "sgx"`) | `ioreg -p IODeviceTree -n sgx` |
| DT `compatible` | **`gpu,t8140`** | device-tree `sgx` node |
| Vendor id | **0x106b** (Apple) | accel `vendor-id=<6b100000>`; `system_profiler` "Vendor: Apple (0x106b)" |
| Feature family (max) | **Apple9** | Metal `supportsFamily:` (Apple1–Apple9 all YES) |
| Metal support | **Metal 4** (Metal3 & Metal4 families YES) | `system_profiler`; Metal `supportsFamily:` |

The G17P codename is the successor to the **G13 (M1/Apple7)** and **G14 (M2/Apple8)**
parts that Mesa's `asahi` driver currently supports. The A18 Pro GPU ISA is a new
instruction set (see `ROADMAP.md` "Known premises").

## 2. Core / cluster topology

Read from the accelerator node's `GPUConfigurationVariable`:

```
{"num_gps"=2, "kickid_qid_shift"=40, "is_sksm"=1, "usc_gen"=3, "kickid_qid_mask"=127,
 "num_cores"=6, "num_mgpus"=1, "gpu_gen"=17, "core_mask_list"=(61), "gpu_var"="P",
 "num_frags"=6}
```

| Field | Value | Interpretation (confidence) |
|-------|-------|------------------------------|
| `num_cores` | **6** | physical GPU cores on the die *(established)* |
| `core_mask_list` | **(61)** = `0b111101` | cores {0,2,3,4,5} enabled, **core #1 fused off** *(established)* |
| **active cores** | **5** | `popcount(61)=5`; independently confirmed by `gpu-core-count=5` and `system_profiler` "Total Number of Cores: 5" *(established)* |
| `num_mgpus` | 1 | single GPU / single die *(established)* |
| `usc_gen` | **3** | Unified-Shader-Core generation 3 (corroborated by `AGXUSCPrivMem*` classes) *(established)* |
| `num_gps` | 2 | raw config value — semantics unconfirmed *(uncertain)* |
| `num_frags` | 6 | raw config value — semantics unconfirmed *(uncertain)* |
| `is_sksm` | 1 | boolean config flag — semantics unconfirmed *(uncertain)* |
| `kickid_qid_shift` / `_mask` | 40 / 127 | submission "kick id" packs a 7-bit queue id at bit 40 *(observed)* |

> **Notable finding:** this unit's GPU is a **6-core design with one core disabled**
> (`num_cores=6`, `core_mask=61` → **5 active**). The product reports 5 GPU cores.

**SoC context** (`sysctl hw`):
- CPU: **2 Performance + 4 Efficiency** cores; `hw.cpufamily=0x75d4acb9`, `cpusubfamily=1`.
- Memory: **8 GiB unified** (`hw.memsize`); **16 KiB pages** (`hw.pagesize=16384`);
  128-byte cache lines.

**GPU register aperture & power** (device-tree `sgx` node):
- `reg` base **0x70000000**; mapped `IODeviceMemory` at phys **0x480000000**, length
  **64 MiB**, plus a second ~1.2 MiB region at 0x480D00000.
- **15 perf states** (`gpu-num-perf-states=0x0f`, `perf-state-count=0x10`), target
  utilization 92% (`gpu-perf-tgt-utilization=0x5c`); `perf-states`/`perf-states-sram`
  tables present in the node.
- GPU MMU config: `agx-address-space-mgmt-mode=1`, `issue-gmmu-tlbis-at-retype=1`
  (corroborated by `AGXUnifiedAddressTranslator` / `AGXGart` classes).

**Tiler parameter buffer (TBDR scene buffer) max sizes** (accel node):
`AGXParameterBufferMaxSize` ≈ **419 MiB** (439615488),
`…EverMemless` ≈ 279 MiB, `…NeverMemless` ≈ 140 MiB.

## 3. Capability values (driver-relevant hardware limits)

All from the read-only Metal `MTLDevice` capability properties
(`experiments/EXP-0002…/raw/metal_caps.txt`). No command buffers were submitted.

| Capability | Value |
|------------|-------|
| `maxThreadsPerThreadgroup` | **(1024, 1024, 1024)** |
| `maxThreadgroupMemoryLength` | **32768** (32 KiB) |
| `maxBufferLength` | **4 GiB** (0x1_0000_0000) |
| `recommendedMaxWorkingSetSize` | ~5.33 GiB (5726633984, of 8 GiB) |
| `hasUnifiedMemory` | YES (`maxTransferRate`=0, N/A) |
| `argumentBuffersSupport` | **Tier 2** |
| `readWriteTextureSupport` | **Tier 2** |
| `maxArgumentBufferSamplerCount` | 500000 |
| `sparseTileSizeInBytes` | **16384** (16 KiB, = page size) |
| `supportsRaytracing` | **YES** |
| `supportsRaytracingFromRender` | **YES** |
| `supportsPrimitiveMotionBlur` | **YES** |
| `supportsFunctionPointers` / `…FromRender` | YES / YES |
| `supportsDynamicLibraries` / `supportsRenderDynamicLibraries` | YES / YES |
| `supports32BitFloatFiltering` | YES |
| `supports32BitMSAA` | YES |
| `supportsBCTextureCompression` | YES *(also YES on M1/macOS — not an Apple9-specific delta)* |
| `supportsPullModelInterpolation` | YES |
| `supportsShaderBarycentricCoordinates` | YES |
| `programmableSamplePositionsSupported` | YES |
| `rasterOrderGroupsSupported` | YES |
| `supportsQueryTextureLOD` | YES |
| `depth24Stencil8PixelFormatSupported` | **NO** (typical for Apple GPUs) |
| `supportsFamily` | Apple1–**Apple9** YES · Mac1/Mac2 YES · Common1–3 YES · **Metal3 & Metal4** YES |
| counter sets | `timestamp` |

## 4. Userspace ↔ kernel interface surface (inventory)

**Node hierarchy** (live IORegistry):

```
sgx@70000000               device-tree GPU node (AppleARMIODevice, compatible "gpu,t8140")
└─ AGXAcceleratorG17P      the GPU accelerator service (IOMatchCategory "IOAccelerator")
   ├─ AGXDeviceUserClient  ← the class userspace opens (5 live: WindowServer, SecurityAgent,
   │                          loginwindow, runningboardd); Metal clients show CommandQueueCount=2
   └─ AGXFirmwareKextG16RTBuddy ×2   RTBuddy firmware-coprocessor endpoints
AGXArmFirmwareMapper       firmware mapper (GPU sibling)
IOAccelerator              IOServiceCompatibility shim node
```

**User-client classes a userspace driver opens:**
- **`AGXDeviceUserClient`** — the AGX-specific device user client (the one actually
  instantiated per client process).
- IOGPUFamily generic user clients also present: `IOGPUDeviceUserClient`,
  `IOGPUMemoryInfoUserClient`, `IOGPUGLDrawableUserClient`.

**Three GPU work-channel (queue) types** — inferred from the driver's channel-class
families and the accelerator's IOReport "vChannel"/"CtxSwitch" groups:
| Channel | Class family | Role |
|---------|--------------|------|
| **TA** | `AGXTAChannel*` | tiling / vertex ("TA") |
| **3D** | `AGX3DChannel*` | fragment / render ("3D") |
| **CL** | `AGXCLChannel*` | compute ("CL") |

**Other AGX driver subsystems (class-name inventory, names only):**
GPU MMU / address translation — `AGXUnifiedAddressTranslator`, `AGXGart`/`AGXSecureGart`,
`AGXMemoryMap`, `AGXVirtualMemory`, `AGXUMASharedPoolContainer`;
shader-core memory — `AGXUSCPrivMemPool`/`…PoolUMA`/`…Block`/`…FList` (**USC**, gen 3);
tiler — `AGXParameterBufferBlock`, `AGXParameterManagement`, `AGXSpillBufferManager`,
`AGXHWParamBufferManager`;
Metal plugin — `AGXG17PDevice`, `AGXMetalG17P`;
firmware/security — `AGXFirmwareKextRTBuddy`, `AGXArmFirmware*`, `AGXSecureMonitor`.

**Loaded GPU kexts (bundle id + version only):**

| kext | version |
|------|---------|
| `com.apple.iokit.IOGPUFamily` | **130.16.3** |
| `com.apple.AGXG17P` | **353.10** |
| `com.apple.AGXFirmwareKextRTBuddy64` | 353.10 |
| `com.apple.AGXFirmwareKextG17PRTBuddy` | 1 |

> The submission mechanism (per-call `IOConnectCallMethod` vs IOGPU shared-memory rings)
> is **not** determined by this recon — it is the Phase 0.5 (`iotrace`) question. This
> document only inventories the classes/kexts a later phase will trace.

---

### Clean-room note
Everything above is a value or a name read from a runtime data structure (IORegistry /
device tree), a kernel-exported parameter, a system report, kext *metadata*, or a Metal
capability property. Class/property/kext *names* are used solely as an interface
inventory (non-copyrightable hardware/driver nomenclature). No Apple binary was
disassembled, decompiled, or otherwise introspected, and no GPU work was submitted.
