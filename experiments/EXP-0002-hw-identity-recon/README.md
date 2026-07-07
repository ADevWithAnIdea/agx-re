# EXP-0002: A18 Pro GPU hardware identity & userspace interface surface

- **Date:** 2026-07-06
- **Clean-room category:** HW-PROBE
- **Phase / question:** `../../docs/ROADMAP.md` → Phase 0, item **0.1 Environment recon**
  (GPU codename from device tree, core count, userspace interface inventory).
- **Device state:** Apple A18 Pro (SoC T8140), macOS 26.6 build 25G5043d, kernel
  `xnu-12377.160.70.501.6 RELEASE_ARM64_T8140`. SIP off, no boot-args/nvram changes
  made by this experiment. Nothing written to the GPU.

## Hypothesis

The A18 Pro GPU presents, through the IORegistry / IODeviceTree and the public Metal
API, an internal hardware codename, a core/cluster topology, a set of capability
limits a driver must honor, and a small set of IOKit user-client classes + kexts that
userspace opens. We expect the codename to be a `G1x`/`gpu,tXXXX` string, the feature
family to be Apple9, and the interface to route through `IOGPUFamily` + an AGX-specific
user client — materially newer than the M1/M2 (`AGXAcceleratorG13/G14`) parts Mesa
supports today.

## Method — why it is clean-room legal

Pure **hardware/capability querying** (allowed technique #2, "hardware probing", plus
reading capability *values* from the public Metal API). We read only:

- the **IORegistry / IODeviceTree** (a live kernel data structure describing hardware
  and driver-match state) via `ioreg`;
- kernel-exported hardware parameters via `sysctl`;
- the system configuration report via `system_profiler`;
- **loaded-kext metadata** (bundle id + version strings only) via `kextstat`/`kmutil`;
- read-only **capability property values** of an `MTLDevice` (Metal API).

We do **NOT** disassemble/decompile/introspect the machine code of any binary
(no `otool -tv`, `objdump -d`, Ghidra, lldb, class-dump — nothing). We submit **no**
command buffers and run **no** GPU work (`metal_caps.m` creates the device object and
reads properties; it never builds a queue/encoder/pipeline). Class and property *names*
harvested from the IORegistry are non-copyrightable hardware/driver nomenclature, used
here only as an interface inventory — no code was read to obtain them.

## Procedure (copy-pasteable, re-runnable by a third party)

On the target, under `~/cleanroom_work/exp0002/`:

```bash
# 1+3 device-tree / IORegistry / kext queries -> raw/
bash probe_hw.sh raw

# 2 Metal capability VALUES (no GPU work submitted)
clang -fobjc-arc -framework Metal -framework Foundation metal_caps.m -o metal_caps
./metal_caps > raw/metal_caps.txt
```

- `probe_hw.sh` — all `ioreg`/`sysctl`/`system_profiler`/`kextstat`/`kmutil` queries.
- `metal_caps.m` — the capability dumper (creates default `MTLDevice`, prints values).

Artifacts pulled back to `raw/` in this directory.

## Raw results

See `raw/`. Key files:

| file | what |
|------|------|
| `raw/ioreg_AGXAcceleratorG17P_keyprops.txt` | GPU accelerator node, key properties (IOReportLegend stripped) |
| `raw/ioreg_AGXAcceleratorG17P.txt` | same node, full (incl. IOReport legend) |
| `raw/ioreg_AGXDeviceUserClient.txt` | the userspace connections open on the GPU |
| `raw/ioreg_dt_sgx.txt` | IODeviceTree `sgx@70000000` node (compatible strings, regions, perf states) |
| `raw/ioreg_full_gpu_nodes.txt` | GPU-relevant node hierarchy from the live registry |
| `raw/iogpu_class_names.txt`, `raw/agx_class_names.txt` | IOGPU*/AGX* class-name inventory (interface surface) |
| `raw/classes_gpu.txt` | live GPU-class instance counts |
| `raw/metal_caps.txt` | Metal-reported capability values |
| `raw/sysctl_hw.txt` | CPU/memory/cache/page topology |
| `raw/sysprofiler_displays.txt` | `SPDisplaysDataType` (chipset, cores, vendor, Metal) |
| `raw/kextstat_gpu.txt`, `raw/kmutil_gpu.txt` | loaded GPU kext names + versions |

See `RESULTS.md` for the analysis and the extracted facts.

## Established facts → docs

Feeds the first draft of `../../docs/hardware-overview.md` (identity, topology,
capability table, interface inventory), each value provenance-cited. Rows added to
`../../PROVENANCE.md`.

## Follow-ups

- Decode the `sgx` device-tree GPU virtual-memory-region cells exactly (GART/UAT layout)
  for the kernel-interface notes — deferred; cell encoding is ambiguous and out of scope
  for identity recon.
- `is_sksm=1`, `num_gps=2`, `num_frags=6`, `usc_gen=3` are raw config values whose exact
  semantics are unconfirmed — targets for later phases (TBDR / dispatch).
- Confirm at the interface layer (Phase 0.5 iotrace) which of `AGXDeviceUserClient` /
  `IOGPUDeviceUserClient` selectors carry submission, and the shared-memory ring shape.
