# EXP-0024: USC shader-entry, PPP header grammar, CDM config + threadgroup-memory

- **Date:** 2026-07-07
- **Clean-room category:** DATA-TRACE + OWN-SHADER (no Apple binary inspected)
- **Phase / question:** Phase 2 cmdstream — close acceptance-gate gaps G-3, G-7, G-8.
- **Device state:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d). SIP off. Reboots: 0.

## Hypothesis
- **G-3:** The graphics USC program `0x10000130000` encodes each stage's machine-code entry as
  some `shaderVA>>N` word (compute analogue at CDM `+0x08`); a VA-shift sweep will expose the
  formula and which words hold the VS vs FS entry.
- **G-7:** The 3D fixed-function state has a header declaring which packets are present + order
  (a present-bit mask or a length/count word); toggling depth/stencil/blend/cull on/off will
  reveal it.
- **G-8:** The compute CDM `+0x00` config word carries more than EXP-0020's bit-23 occupancy
  tier; the threadgroup (shared) memory size is declared in some BO; sweeping
  `[[threadgroup]]`/`setThreadgroupMemoryLength:` will locate it.

## Method (clean-room legal)
Change-one-Metal-parameter, re-capture the registered GPU BOs under the read-only `iotrace`
DYLD interposer (**built `-arch arm64e`**, required on macOS 26), byte-diff the snapshots.
Every shader is our own MSL compiled at runtime (OWN-SHADER); every captured byte crosses the
userspace↔kernel boundary from our own process (DATA-TRACE). No Apple code is disassembled.

- `gvar.m` — parametric OWN draw. Extends EXP-0019 `svar.m` with `--pad N` (compile N dummy
  render pipelines first, to VA-shift the real shaders), `--vsz K`/`--fsz K` (give VS/FS K extra
  live FMA blocks — fine-grained size control that moves a *following* stage's code entry), and
  all depth/stencil/blend/raster toggles for G-7.
- `cvar2.m` — parametric OWN compute dispatch. Extends EXP-0011 `cvar.m` with static-threadgroup
  kernels `tgs64…tgs8192` (compile-time `threadgroup float sh[N]`), a dynamic-tg-mem kernel
  `tgdyn` (`setThreadgroupMemoryLength:`), and config-word probe kernels (`heavy`/`atom`/`barr`/
  `simd`).
- `magloc.py` — locates shader beacons and correlates USC word deltas to code-VA deltas.
- Reused verbatim: `tools/iotrace/iotrace.c`, `bodiff.py`, `bograph.py`, `shptr.py`.

## Procedure
```sh
# on device, ~/cleanroom_work/exp0024
sh run.sh            # builds gvar/cvar2/iotrace (arm64e), runs 3 capture matrices, diffs on-device
```
`run.sh` captures: G-3 pad/vsz/fsz sweep (code BO + USC), G-7 state-group on/off (VDM 0x18000 +
pool 0x58000), G-8 config kernels + static/dynamic tg-mem sweep (all BOs). All 36 captures ran
`status=4` (success). Follow-up per-BO scans were run as inline `python3 - <<PY` one-liners and
their outputs distilled into `raw/FINDINGS_TABLES.txt`.

## Raw results
- `raw/FINDINGS_TABLES.txt` — the derived evidence tables (config word, tg-mem, VDM/pool present,
  USC structure, code-BO block sizes).
- `raw/ana/` — on-device `bodiff` outputs (USC pad/vsz/fsz, VDM/pool per-toggle, tg-mem sweeps).
- `raw/hex/` — trimmed control-BO hexdumps (USC blocks, 0x58000 header, CDM records, code-BO
  headers, the 0x10000090000 tg-mem region).

See `RESULTS.md` for the decoded answer to each gate.

## Established facts → docs
- G-3 graphics shader-binding architecture, G-7 PPP length-word grammar, G-8 config-word map +
  tg-mem encoding → `docs/cmdstream/` (orchestrator merges) → `PROVENANCE.md` (DATA-TRACE, EXP-0024).

## Follow-ups
See `RESULTS.md` §Opaque/next. Deliverables: `gvar.m`, `cvar2.m`, `magloc.py`, `run.sh`,
`raw/` (tables + diffs + trimmed hexdumps), `README.md`, `RESULTS.md`.
