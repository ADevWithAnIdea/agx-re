# Apple M5 GPU — Hardware Overview (baseline)

**Experiment:** EXP-M5-04-capabilities
**Method:** Clean-room HW/capability probe. A program we wrote (`probe.m`) creates the
default `MTLDevice` and prints only the values the Metal driver reports to a normal API
caller, plus textual `ioreg`/`system_profiler`/`sysctl` data. No Apple binary was
disassembled or introspected. Public Metal SDK **headers** (`.h` text) were read to confirm
enum names/values. See `raw/probe_output.txt` and `raw/gpu_config.txt` for verbatim output.
**Date:** 2026-07-10. **Target:** `user@192.168.170.253`, macOS 27.0 (build 26A5368g),
kernel `xnu-13432.0.5.501.1` `RELEASE_ARM64_T8142`.

---

## Identity

| Property | Value | Source |
|---|---|---|
| Marketing name | **Apple M5** | `MTLDevice.name`; `system_profiler`; `ioreg "model"` |
| SoC | **T8142** | kernel `RELEASE_ARM64_T8142` (uname) |
| Board id | **Mac17,3** | `sysctl hw.model` |
| GPU architecture name | **`applegpu_g17g`** | `MTLDevice.architecture.name` |
| GPU IOKit class | **`AGXAcceleratorG17G`** | `ioreg -rc AGXAccelerator "IOClass"` |
| **Metal GPU family (DEFINITIVE)** | **`MTLGPUFamilyApple10` (1010)** | `supportsFamily` probe + SDK header |
| Metal version | **Metal 4** (`MTLGPUFamilyMetal4`, 5002) | `supportsFamily`; `system_profiler` |
| GPU core count | **8** | `ioreg "gpu-core-count"`; `system_profiler` |
| registryID | `0x1000003de` | `MTLDevice.registryID` |

### The headline result: M5 is **Apple10**, a new GPU generation

The M5 reports **`MTLGPUFamilyApple10`** and **not** `Apple9`. For comparison, the M4
(EXP-M4-02, SoC T8132, `applegpu_g16g`) reports `Apple9` as its highest family and returns
**NO** for `Apple10`. The M5 returns **YES** for every family `Apple1..Apple10` and **NO**
for `Apple11`/`Apple12` (which are not defined in the SDK).

`MTLGPUFamilyApple10 = 1010` is a **real, named constant** in the public SDK header
(`.../Metal.framework/Headers/MTLDevice.h:242`), i.e. this is a genuine driver-recognized
family, not an out-of-range integer accidentally returning YES:

```
MTLGPUFamilyApple9  = 1009,
MTLGPUFamilyApple10 = 1010,     <-- highest defined Apple family; M5 = this
...
MTLGPUFamilyMetal4 API_AVAILABLE(macos(26.0), ios(26.0)) = 5002,
```

Generational summary: **M1=Apple7 (G13), M2=Apple8 (G14), M4=Apple9 (G16g), M5=Apple10 (G17g).**
The M5 is one Metal-family generation newer than the M4 and two newer than the currently
Mesa-supported M2. Any documentation that assumed "Apple9 is the ceiling" must be revised.

---

## Memory model

| Property | Value (bytes) | Human | Source |
|---|---|---|---|
| Unified memory | YES | — | `hasUnifiedMemory` |
| Physical RAM | 17,179,869,184 | 16 GiB | `sysctl hw.memsize` |
| Page size | 16,384 | 16 KiB | `sysctl hw.pagesize` |
| `recommendedMaxWorkingSetSize` | 12,713,115,648 | ~11.84 GiB | `MTLDevice` |
| `maxBufferLength` | 9,534,832,640 | ~8.88 GiB | `MTLDevice` |
| `maxThreadgroupMemoryLength` | 32,768 | 32 KiB | `MTLDevice` |

Notes: this unit is a 16 GiB part. `recommendedMaxWorkingSetSize` and `maxBufferLength`
are byte-identical to the 16 GiB M4 unit measured in EXP-M4-02, i.e. these limits track the
16 GiB memory tier, not the GPU generation. `maxBufferLength` (~8.88 GiB) is the single-BO
allocation ceiling a driver must respect; it is **less than** total RAM.

---

## Compute / threadgroup limits

| Property | Value | Source |
|---|---|---|
| SIMD / thread-execution width | **32** | compute pipeline `threadExecutionWidth` (our own kernel) |
| `maxThreadsPerThreadgroup` | (1024, 1024, 1024) | `MTLDevice` |
| `maxTotalThreadsPerThreadgroup` | 1024 | pipeline (our own kernel) |
| Threadgroup memory | 32 KiB | `maxThreadgroupMemoryLength` |

SIMD width is **32**, unchanged from G13/G14/G16 — the AGX warp/quad size is stable across
the M5 generation.

---

## Toolchain observed on target

- Apple clang 21.0.0 (clang-2100.3.25.1), Command Line Tools; SDK 27.0.
- **No `metal` CLI** — runtime MSL compilation via `newLibraryWithSource:` confirmed working.
- Highest accepted MSL language version: **Metal 4.1** (`-std=metal4.1` accepted; `4.2`
  rejected). The M4 unit topped out at MSL 4.0, so the M5 stack ships one MSL minor newer.

---

## Provenance / clean-room attestation

Every fact above is either (a) a value the Metal driver returned to our own program via a
public API, (b) textual `ioreg`/`system_profiler`/`sysctl` output (data, not code), or
(c) an enum name/value read from a **public** Metal SDK header. No Apple binary, dylib,
kext, or firmware was disassembled, decompiled, or otherwise introspected. Reproduce with
`./run.sh`.
