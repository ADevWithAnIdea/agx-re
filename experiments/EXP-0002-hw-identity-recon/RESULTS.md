# EXP-0002 Results — A18 Pro GPU identity & userspace interface surface

Clean-room category: **HW-PROBE**. All values below are read from the IORegistry /
IODeviceTree, `sysctl`, `system_profiler`, loaded-kext metadata, and read-only Metal
capability properties. No binary was disassembled; no GPU work was submitted.

---

## 1. GPU identity & internal codename

| Fact | Value | Source (file → property) |
|------|-------|--------------------------|
| Marketing name | **Apple A18 Pro** | `metal_caps.txt` name; `ioreg …_keyprops` `model`; `sysprofiler_displays` |
| SoC | **T8140** | kernel `RELEASE_ARM64_T8140`; DT `compatible="gpu,t8140"` |
| **GPU internal codename** | **G17P** | `metal_caps.txt` `architecture.name = applegpu_g17p`; accel node `IOClass=AGXAcceleratorG17P`, `CFBundleIdentifier=com.apple.AGXG17P`, `MetalPluginClassName=AGXG17PDevice`, `MetalPluginName=AGXMetalG17P` |
| GPU generation / variant | **gpu_gen = 17, gpu_var = "P"** (→ "G17P") | `ioreg …_keyprops` `GPUConfigurationVariable` |
| Device-tree node | **`sgx@70000000`** (`device_type="sgx"`, `name="sgx"`) | `ioreg_dt_sgx.txt` |
| DT `compatible` | **`gpu,t8140`** | `ioreg_dt_sgx.txt` `compatible` |
| PCI-style vendor id | **0x106b** (Apple) | accel node `vendor-id=<6b100000>`; `sysprofiler` `Vendor: Apple (0x106b)` |
| Feature family (max) | **Apple9**, and **Metal 4** | `metal_caps.txt` supportsFamily; `sysprofiler` `Metal Support: Metal 4` |
| AGX kernel driver version | **353.10** (`com.apple.AGXG17P`) | `kextstat_gpu.txt`; accel `IOSourceVersion=353.10` |
| IOGPUFamily version | **130.16.3** | `kextstat_gpu.txt` |
| AGX trace-code version | **3.44.6** | accel node `AGXTraceCodeVersion` |

The driver personality `AGXAcceleratorG17P` advertises `IONameMatch =
("gpu,t8140","gpu,t8015","gpu,t8027","gpu,t8030","gpu,t8103","gpu,t8122")` — i.e. the
same kext binds this and several older SoCs — but the **live matched** name is
`IONameMatched="gpu,t8140"`.

## 2. Core / cluster topology

From the accelerator node's `GPUConfigurationVariable`
(`= {"num_gps"=2,"kickid_qid_shift"=40,"is_sksm"=1,"usc_gen"=3,"kickid_qid_mask"=127,`
`"num_cores"=6,"num_mgpus"=1,"gpu_gen"=17,"core_mask_list"=(61),"gpu_var"="P","num_frags"=6}`):

| Field | Value | Reading |
|-------|-------|---------|
| `num_cores` | **6** | physical GPU cores on the die |
| `core_mask_list` | **(61)** = `0b111101` | cores {0,2,3,4,5} enabled, **core #1 fused/disabled** |
| **enabled cores** | **5** | popcount(61)=5 — matches `gpu-core-count=5`, `sysprofiler` "Total Number of Cores: 5" |
| `num_mgpus` | 1 | single GPU (no multi-die) |
| `num_gps` | 2 | (unconfirmed semantics — "geometry pipes"?) |
| `num_frags` | 6 | (unconfirmed semantics — per-core fragment units?) |
| `usc_gen` | **3** | Unified-Shader-Core generation 3 (cf. `AGXUSCPrivMem*` classes) |
| `is_sksm` | 1 | boolean config flag (semantics TBD) |
| `kickid_qid_shift`/`mask` | 40 / 127 | how a submission "kick id" packs a 7-bit queue id |

> **Notable:** the silicon is a **6-core GPU with one core disabled** on this unit
> (`num_cores=6`, `core_mask=61` → 5 active). The product reports 5 GPU cores.

CPU/memory context (`sysctl_hw.txt`, for the SoC baseline):
- CPU: **2 Performance + 4 Efficiency = 6 cores**; `machdep.cpu.brand_string=Apple A18 Pro`;
  `hw.cpufamily=1976872121 (0x75d4acb9)`, `hw.cpusubfamily=1`.
- **Unified memory 8 GiB** (`hw.memsize=8589934592`); `hw.pagesize=16384` (**16 KiB**);
  `hw.cachelinesize=128`. P-core L2 16 MiB (2/L2), E-core L2 4 MiB (4/L2).

GPU MMIO & perf, from the `sgx` device-tree node (`ioreg_dt_sgx.txt`):
- register aperture: `reg` base **0x70000000**; `IODeviceMemory` mapped at phys
  **0x480000000** len **64 MiB** (0x4000000) + a 2nd region at 0x480D00000 len ~1.2 MiB.
- **15 perf states** (`gpu-num-perf-states=0x0f`, `perf-state-count=0x10`);
  `gpu-perf-tgt-utilization=0x5c`=92%; `perf-states`/`perf-states-sram` tables present.
- `metal-standard=<00010000>` (0x100), `opengl-standard=<00030000>` (0x300) —
  API-level codes (exact meaning unconfirmed).
- `agx-address-space-mgmt-mode=1`, `issue-gmmu-tlbis-at-retype=1` — GPU MMU (GART/UAT) config.

Tiler parameter-buffer (TBDR scene buffer) max sizes, from the accel node:
`AGXParameterBufferMaxSize=439615488` (~419 MiB),
`…EverMemless=293076992` (~279 MiB), `…NeverMemless=146538496` (~140 MiB).

## 3. Capability values (Metal API, `metal_caps.txt`) — driver-relevant limits

| Capability | Value |
|------------|-------|
| `maxThreadsPerThreadgroup` | **(1024, 1024, 1024)** |
| `maxThreadgroupMemoryLength` | **32768** (32 KiB) |
| `maxBufferLength` | **0x100000000** (4 GiB) |
| `recommendedMaxWorkingSetSize` | 5726633984 (~5.33 GiB of 8 GiB) |
| `hasUnifiedMemory` | YES |
| `maxTransferRate` | 0 (N/A — unified memory) |
| `argumentBuffersSupport` | **Tier 2** (=1) |
| `readWriteTextureSupport` | **Tier 2** (=2) |
| `maxArgumentBufferSamplerCount` | 500000 |
| `sparseTileSizeInBytes` | **16384** (16 KiB = page size) |
| `supportsRaytracing` | **YES** |
| `supportsRaytracingFromRender` | **YES** |
| `supportsPrimitiveMotionBlur` | **YES** |
| `supportsFunctionPointers` | YES; `…FromRender` YES |
| `supportsDynamicLibraries` | YES; `supportsRenderDynamicLibraries` YES |
| `supports32BitFloatFiltering` | YES |
| `supports32BitMSAA` | YES |
| `supportsBCTextureCompression` | **YES** (BC/DXT — notable on Apple mobile GPU) |
| `supportsPullModelInterpolation` | YES |
| `supportsShaderBarycentricCoordinates` / `barycentricCoordsSupported` | YES |
| `programmableSamplePositionsSupported` | YES |
| `rasterOrderGroupsSupported` | YES |
| `supportsQueryTextureLOD` | YES |
| `depth24Stencil8PixelFormatSupported` | **NO** (as expected for Apple GPUs) |
| `supportsFamily` | Apple1–**Apple9** YES, Mac1/Mac2 YES, Common1–3 YES, **Metal3 & Metal4 YES** |
| counter sets | `timestamp` |

## 4. Userspace ↔ kernel interface surface (names/inventory only)

**Live GPU node hierarchy** (`ioreg_full_gpu_nodes.txt`):

```
sgx@70000000                 (AppleARMIODevice — device-tree GPU node, compatible "gpu,t8140")
└─ AGXAcceleratorG17P        (the GPU accelerator; IOMatchCategory "IOAccelerator")
   ├─ AGXDeviceUserClient ×5 (userspace connections — see below)
   └─ AGXFirmwareKextG16RTBuddy ×2   (RTBuddy firmware coprocessor endpoints)
AGXArmFirmwareMapper         (firmware mapper, sibling under the GPU)
IOAccelerator                (IOServiceCompatibility shim node)
```

**The user-client class userspace opens: `AGXDeviceUserClient`.** Five live instances
(`ioreg_AGXDeviceUserClient.txt`), each tagged with its creator:
`runningboardd` (pid 174), `WindowServer` (pid 164, ×2), `SecurityAgent` (pid 354),
`loginwindow` (pid 167). The Metal-backed ones carry `AppUsage {"API"="Metal", …}` and
`CommandQueueCount`/`…Max = 2`.

**IOGPUFamily object classes** present (`iogpu_class_names.txt`) — the generic GPU
interface layer under the AGX driver. Notable for the interface map:
`IOGPUDeviceUserClient`, `IOGPUMemoryInfoUserClient`, `IOGPUGLDrawableUserClient`
(the user-client classes), plus `IOGPUCommandQueue`, `IOGPUWorkQueue`,
`IOGPUNotificationQueue`, `IOGPUChannel`, `IOGPUIOCommandBuffer`,
`IOGPUIOCommandQueue`, `IOGPUEventFence`/`IOGPUEventMachine`/`IOGPUFenceMachine`,
`IOGPUMemory`/`IOGPUMemoryMap`/`IOGPUResource`/`IOGPUVirtualMemory`, `IOGPUScheduler`.

**AGX driver class nomenclature** (`agx_class_names.txt`) — maps the internal structure
(names only; used as an interface inventory, not code):
- **Three work-channel families** = the three GPU queue types:
  `AGXTAChannel` (**TA** = tiling / vertex), `AGX3DChannel` (**3D** = fragment/render),
  `AGXCLChannel` (**CL** = compute) — corroborated by the accel node's IOReport
  "TA/3D/CL vChannel" and "CtxSwitch" groups. Variants seen: `…Gen2`, `…SKSM`, `…SKU`,
  `…G16`, `…G16_SKSM`.
- Memory / MMU: `AGXUnifiedAddressTranslator`, `AGXGart`/`AGXSecureGart`/`AGXLegacyGart`,
  `AGXMemoryMap`, `AGXUMASharedPoolContainer`, `AGXVirtualMemory`.
- Shader-core memory: `AGXUSCPrivMemPool`/`…PoolUMA`/`…Block`/`…FList`/`…HWMetrics`
  (**USC** = Unified Shader Core; matches `usc_gen=3`).
- Tiler: `AGXParameterBufferBlock`/`…Virtual`, `AGXParameterManagement`,
  `AGXSpillBufferManager`, `AGXHWParamBufferManager`.
- Device/Metal plugin: `AGXG17PDevice`, `AGXMetalG17P`; legacy `AGXMetalA12` also in-kext.
- Firmware/security: `AGXFirmwareKextRTBuddy`, `AGXFirmwareKextG16RTBuddy`,
  `AGXArmFirmware*`, `AGXSecureMonitor`/`AGXHAL200SecureMonitor`.

**Loaded GPU kexts (name + version only, `kextstat_gpu.txt`):**

| kext bundle id | version |
|----------------|---------|
| `com.apple.iokit.IOGPUFamily` | 130.16.3 |
| `com.apple.AGXG17P` | 353.10 |
| `com.apple.AGXFirmwareKextRTBuddy64` | 353.10 |
| `com.apple.AGXFirmwareKextG17PRTBuddy` | 1 |
| (`com.apple.iokit.IOCryptoAcceleratorFamily` 1.0.1 — AES, not GPU) | |

## Analysis — what's established vs uncertain

**Established:** codename **G17P** (three independent sources: Metal `architecture.name`,
IOKit class/bundle names, `gpu_gen=17`+`gpu_var="P"`); **6-core die, 5 enabled**; feature
family **Apple9 / Metal 4**; the capability limits table; the interface routes through
**`AGXDeviceUserClient`** over **`IOGPUFamily 130.16.3`** + **`AGXG17P 353.10`** with an
**RTBuddy firmware coprocessor**; three work-channel types **TA/3D/CL**.

**Uncertain / deferred:** exact semantics of `num_gps`, `num_frags`, `is_sksm`,
`metal-standard`/`opengl-standard` codes, and the `sgx` VM-region cell layout (GART/UAT).
Recorded as follow-ups; not asserted as fact in `docs/`.

## vs documented M1/M2 (Apple7/G13, Apple8/G14)

- **Codename jump G13/G14 → G17P** (Mesa's `asahi` targets G13/G14). Naming is a clean
  continuation of Apple's `G%d` GPU line; the ISA is a full new instruction set (per ROADMAP premise).
- **Argument buffers Tier 2** and **read-write textures Tier 2**. The high-confidence
  Apple9 additions vs G13/G14 are native **hardware ray tracing** (`supportsRaytracing`
  +`supportsRaytracingFromRender` +`supportsPrimitiveMotionBlur`), **function pointers
  from render**, and **dynamic libraries incl. from render** — capabilities G13 does not
  expose. (Barycentrics, programmable sample positions, and raster-order groups are also
  present here but exist on earlier Apple families too; not asserted as deltas.)
- **BC (DXT/BCn) texture compression = YES.** *Caution:* on macOS an M1 (Apple7) also
  reports `supportsBCTextureCompression=YES`, so this is **not** established as an
  Apple9-specific delta — it is recorded as a present capability, nothing more.
- Page size **16 KiB**, sparse tile **16 KiB** (both match G13/G14's 16 KiB pages),
  tiler parameter buffer up to ~419 MiB.
- Interface modernized: `AGXAcceleratorG13/G14` → `AGXAcceleratorG17P`; the same
  `AGXDeviceUserClient` + `IOGPUFamily` shape persists (submission-path details are the
  Phase 0.5 question, not answered here).
