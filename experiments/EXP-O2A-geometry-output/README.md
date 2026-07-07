# EXP-O2A: geometry-output pipeline (multi-viewport/scissor, clip/cull, point_size, primitive restart, alpha-to-coverage/one, fill mode)

- **Date:** 2026-07-07
- **Clean-room category:** DATA-TRACE + OWN-SHADER
- **Phase / question:** objective-2 cluster O2-A — the Metal-exposed geometry-output/raster-output state
  a real GL/Vulkan pipeline emits, not yet exercised. `docs/capability-completeness.md` items
  (viewport/scissor 16, clip/cull distance, `[[point_size]]`, primitive restart, alpha-to-coverage/one,
  polygon-point fill); `docs/capability-matrix.md` §4.
- **Device:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d), SIP off. Command Line Tools only (runtime MSL).

## Hypothesis
Each geometry-output feature is a distinct PPP/output-select field, a `0x68000` tiling-context field, a
`0x58000` fixed-function bit, or a VDM (`0x18000`) field — and by changing exactly one Metal parameter and
byte-diffing the registered GPU BOs we can localise each. Extends the single-viewport transform
(`0x68000+0x910`, EXP-0014/0021) to arrays; extends the VDM draw record (EXP-0014/0027) to restart/point;
extends the PPP output-select/state pool (EXP-0019/0024).

## Method
Change-one-Metal-parameter DATA-TRACE. A parametric OWN draw (`ovar.m`, every geometry-output parameter a
CLI flag) runs under the read-only `iotrace` DYLD interposer (built `-arch arm64e`); after each submit the
harness snapshots every registered BO; `bodiff.py` word-diffs a variant against a byte-identical baseline.
Clean-room-legal: our own MSL, our own draws, logging non-copyrightable command-buffer/descriptor bytes;
Metal-generated helper/blend/epilog shader code is **located, never disassembled** (CLAUDE.md rule 5).

Tools reused **read-only** (copy into the device workspace before running — they are unmodified verbatim
copies of the repo originals; do not edit them here): `tools/iotrace/iotrace.c`, `tools/iotrace/bodiff.py`.

## Procedure
```sh
# on host: stage harness + read-only tools onto the device
cp tools/iotrace/iotrace.c tools/iotrace/bodiff.py experiments/EXP-O2A-geometry-output/
scp experiments/EXP-O2A-geometry-output/{ovar.m,run.sh,iotrace.c,bodiff.py} user@DEVICE:~/cleanroom_work/exp_o2a/
# on device:
cd ~/cleanroom_work/exp_o2a && sh run.sh      # builds, captures 39 configs, diffs, curates hex
# alpha-to-one confound follow-up (baseline FS emits alpha=1.0 -> a2o is a no-op; re-drive with alpha<1):
./ovar --msaa 4 --calpha 0.5 --a2o --dump     # (+ --a2c, + msaa1) — see raw/ana/a2_alpha_followup.txt
# pull back text diffs + curated hex only (raw BO dumps stay on-device)
scp -r user@DEVICE:~/cleanroom_work/exp_o2a/{analysis,hex} .../raw/
```
`ovar.m` flags: `--nvp N` (setViewports:count:), `--vpmod` (perturb viewport[1]), `--nsc N`/`--scmod`,
`--vpidx K` (`[[viewport_array_index]]`), `--clipdist N` (`[[clip_distance]]`), `--prim point|line|
linestrip|tristrip`, `--pointsize F`, `--indexed --itype u16|u32 --restart`, `--msaa N`, `--a2c`, `--a2o`,
`--calpha F`, `--fill fill|lines`.

## Raw results
`raw/ana/` — byte-diffs (targeted `--va` diffs are clean; full-dir `df` diffs carry the known
`gpu_va=0x0` sel-5 pairing artifact and the render-target pixel BO `0x10000058000`, both filtered in
analysis). `raw/hex/` — trimmed control-BO hexdumps (`vp*_68000`, `*_18000`, `*_58000`, USC/code).
`raw/stdout/` — per-capture logs (all `status=4`, zero exceptions/rejections). Key evidence:
- `vp_68k_*` viewport array (count word, header, 6-float/0x18 stride, slot-1 isolation).
- `sc_68k_*` + `sc_full*` scissor (enable bit + tile-bound only; no rect array in any client BO).
- `clip_full_*` clip-plane mask `0x58000+0x20[7:0]`.
- `pt_*`, `*_vdm` point/primitive path.
- `ix_*` indexed VDM record (cut index, opcode, count, extent).
- `a2c_*`, `a2o_*`, `a2_alpha_followup.txt` alpha-to-coverage/one.
- `fill_*` fill mode.

Full analysis, tables and bit layouts: **`RESULTS.md`**.

## Analysis
See `RESULTS.md`. All six features characterised; 3 are not Metal-exposable (cull distance,
polygon-point fill, custom restart index → capability-matrix); multi-scissor rect array is
kernel-managed (`isp_scissor`).

## Established facts → docs (orchestrator to apply)
- Viewport array layout (`0x68000+0x900` count, 6-float/0x18 stride, control-word header) → `docs/cmdstream/`
  + `docs/pipeline/` (extends single-viewport `+0x910`).
- Scissor = enable bit `0x58000+0x34` bit16 + tile-bound clamp; **rect array kernel-managed** →
  `docs/cmdstream/` + `docs/kernel-interface.md`.
- PPP vertex output-select word `0x58000+0x20`: clip mask [7:0], point_size bit18, viewport-index bit19 →
  `docs/cmdstream/`.
- Indexed VDM record + primitive-restart cut index (`0x18000+0x68` = type-max) → `docs/cmdstream/`.
- Alpha-to-coverage FF bits + shader lowering; alpha-to-one in-shader (no FF field) → `docs/cmdstream/`
  + `docs/pipeline/`.
- Capability-matrix updates: point-fill (INF), cull distance (not exposed), custom restart index (not
  exposed), scissor rect array (kernel-managed) → `docs/capability-matrix.md`, `docs/capability-completeness.md`,
  `docs/hypotheses.md`.

## Follow-ups
See RESULTS.md "Recommended next" (viewport control-word-header role; kernel `isp_scissor` capture;
cmdstream-injection probe for point-fill + custom restart index).
