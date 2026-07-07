# Clean-Room Provenance Log

Auditable paper trail. **Every fact that enters `docs/` gets a row here** explaining *how*
it was learned — so a third party can confirm nothing came from Apple's code. This is the
clean-room defense; keep it complete and honest.

Allowed provenance categories (see `CLAUDE.md`):
- `HW-PROBE` — observed hardware behavior (input → output).
- `DATA-TRACE` — black-box capture of data at the userspace↔kernel boundary.
- `OWN-SHADER` — disassembly of a shader **we compiled** from **our** source.
- `PUBLIC` — a public document / open-source project (cite it).

**Never** `BINARY-RE` of any Apple binary — that category does not exist here.

| Date | Fact (as documented) | Where in docs | Category | Experiment / source |
|------|----------------------|---------------|----------|---------------------|
| 2026-07-06 | Target is Apple A18 Pro, SoC T8140, macOS 26.6 (25G5043d), 5 GPU cores, Metal 4 / feature family Apple9 max | ROADMAP | HW-PROBE | bring-up: `sysctl`, `system_profiler`, Metal `supportsFamily` probe |
| 2026-07-06 | Runtime MSL compilation (`newLibraryWithSource:`) works with Command Line Tools only (no full Xcode / `metal` CLI) | ROADMAP / tooling | HW-PROBE | bring-up: `mtltest.m` built with `clang -framework Metal` |
| 2026-07-06 | GPU internal codename **G17P** (gpu_gen=17, gpu_var="P") | hardware-overview §1 | HW-PROBE | EXP-0002: Metal `architecture.name=applegpu_g17p`; IOKit class `AGXAcceleratorG17P`, kext `com.apple.AGXG17P`; accel `GPUConfigurationVariable` |
| 2026-07-06 | Device-tree GPU node `sgx@70000000`, `compatible="gpu,t8140"`, vendor-id 0x106b | hardware-overview §1 | HW-PROBE | EXP-0002: `ioreg -p IODeviceTree -n sgx`; `raw/ioreg_dt_sgx.txt` |
| 2026-07-06 | GPU topology: **6 physical cores, core #1 fused off → 5 active** (num_cores=6, core_mask_list=(61); gpu-core-count=5) | hardware-overview §2 | HW-PROBE | EXP-0002: accel node `GPUConfigurationVariable`, `gpu-core-count`; `system_profiler` |
| 2026-07-06 | usc_gen=3, num_gps=2, num_frags=6, num_mgpus=1, is_sksm=1 (num_gps/num_frags/is_sksm semantics unconfirmed) | hardware-overview §2 | HW-PROBE | EXP-0002: accel `GPUConfigurationVariable` |
| 2026-07-06 | 15 GPU perf states; register aperture DT base 0x70000000 / phys 0x480000000 (64 MiB); tiler PB max ~419 MiB | hardware-overview §2 | HW-PROBE | EXP-0002: `raw/ioreg_dt_sgx.txt`, accel node `AGXParameterBufferMaxSize` |
| 2026-07-06 | SoC context: 8 GiB unified memory, 16 KiB pages, 2P+4E CPU | hardware-overview §2 | HW-PROBE | EXP-0002: `sysctl hw`; `raw/sysctl_hw.txt` |
| 2026-07-06 | Metal capability limits (maxThreadsPerThreadgroup 1024³, maxThreadgroupMemoryLength 32 KiB, maxBufferLength 4 GiB, arg-buffers Tier2, RW-textures Tier2, sparse tile 16 KiB, supportsRaytracing/FromRender/PrimitiveMotionBlur, function-pointers/dynamic-libraries incl. from render, Apple1–9 + Metal3/4) | hardware-overview §3 | HW-PROBE | EXP-0002: `metal_caps.m` (reads MTLDevice capability values; no GPU work); `raw/metal_caps.txt` |
| 2026-07-06 | Userspace interface: user-client `AGXDeviceUserClient` (+ IOGPU* user clients) over kexts IOGPUFamily 130.16.3 / AGXG17P 353.10 / RTBuddy firmware; three work-channel types TA/3D/CL | hardware-overview §4 | HW-PROBE | EXP-0002: `ioreg` node hierarchy + class-name inventory; `kextstat`/`kmutil`; `raw/ioreg_full_gpu_nodes.txt`, `raw/agx_class_names.txt`, `raw/kextstat_gpu.txt` |

## Operational notes (not doc facts, but part of the paper trail)
- 2026-07-06: Device configured for unattended work — `pmset SleepDisabled 1`; passwordless sudo installed at `/etc/sudoers.d/cleanroom` (`visudo -c` clean). FileVault off, SIP off. Device state persists across reboots (verified: no auto-reset). Host-side reboot lever: `macvdmtool reboot` (wait 20s before re-SSH).
- 2026-07-06: **Reboot recovery validated end-to-end.** `macvdmtool reboot` (Mac type J773gAP) reboots cleanly; device returns at 192.168.170.254 ~30s later with `SleepDisabled` and passwordless sudo intact. NOTE: the device's DHCP address can move on reboot if the static lease isn't held (once observed at 192.168.10.162); the lab network owner maintains a static lease — if a reboot ever fails to recover at .254, re-discover by mDNS/ARP before declaring BLOCKED.
