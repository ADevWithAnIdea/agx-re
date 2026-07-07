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
| 2026-07-06 | Raw G17P AGX machine code is extractable from our own MSL: `MTLBinaryArchive` → Metal fat binary (0xCBFEBABE) → AppleGPU image (cputype 0x1000013) → nested Mach-O `__TEXT,__compute`/`__text` → symbols `_agc.main` + `_agc.main.constant_program`. Deterministic (sha256-stable). Confirmed machine code not AIR (BC magic only in AIR64 image). | isa/README §"How we get the bytes" | OWN-SHADER + PUBLIC | EXP-0001: `tools/shdump/{shdump.m,agxparse.py}`; parser is our own impl informed by public/MIT applegpu extractor |
| 2026-07-06 | G17P shader-code byte observations: 2-byte instruction parcels; `0e000000` terminates every main (empty kernel = just this); fixed `1ca01006…` preamble; 64-byte constant-program prolog. Interpretations pending HW round-trip. | isa/README §"Preliminary encoding observations" | OWN-SHADER | EXP-0001: `raw/*info.txt`, `raw/determinism.txt` |
| 2026-07-06 | G17P differential-compilation field localizations: float ALU op-select byte (bit0: 1c=add/1d=mul); packed non-IEEE float immediate (bits4-6 of one byte); two source-register selector bytes; int vs float ALU use distinct encodings. NEGATIVE: buffer *binding index* not present in shader code (buffer(0) vs buffer(1) → identical bytes) — resolved at bind time. Interpretations pending HW round-trip. | isa/README | OWN-SHADER | EXP-0001: `raw/diffs.txt` |
| 2026-07-06 | dougallj/applegpu (G13) decoder fails/garbles on G17P bytes → wholly different ISA; applegpu is a structural template + testbed, not a decoder to extend | isa/README | OWN-SHADER + PUBLIC | EXP-0001: `raw/applegpu_attempt.txt` |
| 2026-07-06 | Hardware testbed works: splice arbitrary bytes into our own compiled shader's `_agc.main` and run on the real GPU. Metal runs **tampered code with no integrity check** (given a bound `MTLBinaryArchive` + `MTLPipelineOptionFailOnBinaryArchiveMiss`, which forces instantiation from archived machine code, not AIR recompile). | tools/agxtest, isa/README | OWN-SHADER + PUBLIC | EXP-0003: `tools/agxtest/{agxrun.m,agxtest.py}`; identity + no-op splice round-trips |
| 2026-07-06 | **✅ HARDWARE-VALIDATED:** float ALU op-select = byte at program offset `0x22`, bit 0: `1c=fadd`, `1d=fmul`. Splicing `1c→1d` in `c=a+b` yields `a*b` on hardware, byte-identical to compiler's fmul output. | isa/README | OWN-SHADER | EXP-0003: `raw/` dispatch logs (a=1..8,b=10..80 → 11..88 vs 10,40,90,…) |
| 2026-07-06 | Revised: `0e000000` is NOT a required trailing stop (corrupting it past the store did not fault); program extent bounded by metadata/final store. GPU faults from illegal ops are **contained** (MTLCommandBufferStatusError, no device wedge, 0 reboots). | isa/README | OWN-SHADER | EXP-0003: fault-behavior logs |

## Operational notes (not doc facts, but part of the paper trail)
- 2026-07-06: Device configured for unattended work — `pmset SleepDisabled 1`; passwordless sudo installed at `/etc/sudoers.d/cleanroom` (`visudo -c` clean). FileVault off, SIP off. Device state persists across reboots (verified: no auto-reset). Host-side reboot lever: `macvdmtool reboot` (wait 20s before re-SSH).
- 2026-07-06: **Reboot recovery validated end-to-end.** `macvdmtool reboot` (Mac type J773gAP) reboots cleanly; device returns at 192.168.170.254 ~30s later with `SleepDisabled` and passwordless sudo intact. NOTE: the device's DHCP address can move on reboot if the static lease isn't held (once observed at 192.168.10.162); the lab network owner maintains a static lease — if a reboot ever fails to recover at .254, re-discover by mDNS/ARP before declaring BLOCKED.
