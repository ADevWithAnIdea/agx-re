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

## Operational notes (not doc facts, but part of the paper trail)
- 2026-07-06: Device configured for unattended work — `pmset SleepDisabled 1`; passwordless sudo installed at `/etc/sudoers.d/cleanroom` (`visudo -c` clean). FileVault off, SIP off. Device state persists across reboots (verified: no auto-reset). Host-side reboot lever: `macvdmtool reboot` (wait 20s before re-SSH).
- 2026-07-06: **Reboot recovery validated end-to-end.** `macvdmtool reboot` (Mac type J773gAP) reboots cleanly; device returns at 192.168.170.254 ~30s later with `SleepDisabled` and passwordless sudo intact. NOTE: the device's DHCP address can move on reboot if the static lease isn't held (once observed at 192.168.10.162); the lab network owner maintains a static lease — if a reboot ever fails to recover at .254, re-discover by mDNS/ARP before declaring BLOCKED.
