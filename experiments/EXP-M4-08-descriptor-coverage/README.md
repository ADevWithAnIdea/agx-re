# EXP-M4-08: Descriptor coverage — close gaps DESC-1..DESC-7

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER + DATA-TRACE + HW-PROBE (no Apple binary disassembled)
- **Primary device:** local **Apple M4** (Mac16,10, 10-core, Metal 4, macOS 26.4.1).
- **Cross-confirm device:** remote **A18 Pro** (G17P, macOS 26.6) — for every correction.
- **Owns docs:** `docs/descriptors/README.md`, `docs/descriptors/format-table.md`.

## Hypothesis
The A18/M4 descriptor rules documented in `docs/descriptors/*` were validated at a few points and
stated generally. Each of the 7 coverage gaps (`reviews/COVERAGE-GAPS-01.md` §2) hides either a
surprise in untested arguments or an undecoded field. Probe the full parameter space; CONFIRM or
CORRECT with exact bits.

## Method
Reuse the EXP-0015 / EXP-M4-04 / EXP-G1b harnesses under the read-only `tools/iotrace` interposer
(built locally `-arch arm64e`). All shaders are our own MSL compiled at runtime; every descriptor /
attachment byte is captured from **our own** process's GPU buffer objects (DATA-TRACE) and correlated
to our resources' printed GPU VAs. Sampling/OOB behavior is HW-PROBE. Change-one-parameter byte-diff.

### Harnesses (in `work/`)
- `tvar.m` — sampled texture + sampler descriptor sweep (EXP-0015), **format list extended to 96
  formats** (all uncompressed/packed/XR/YUV/depth-stencil + BC/ASTC/ETC/EAC). Drives DESC-2/3/4/5/6.
- `rtfmt.m` — **new**: render-target attachment format-word sweep across all renderable formats, with
  the fragment output type matched to the format data class (float/uint/sint). Drives DESC-1.
- `svar.m` — storage-image (PBE) descriptor (EXP-G1b). Drives the DESC-2 PBE alternate split.
- `desc7.m` — **new**: plain-buffer out-of-bounds read behavior + texture_buffer descriptor. DESC-7.
- `splice.m` — **new**: explicit-argument-buffer probe for DESC-4 raw-code injection (found the
  explicit arg buffer uses gpuResourceIDs, not inline descriptor bytes — see RESULTS §DESC-4).
- Drivers: `capfmt.sh` (DESC-5/6), `caprt.sh` (DESC-1), `capsamp.sh` (DESC-3/4), `capdims.sh` (DESC-2).
- Analyzers: `fmtparse.py` (byte0 arrangement decode), reused `descauto.py`/`attloc.py` (locate &
  dump the appended descriptors / the 3-segment attachment chain).
- `xconf.sh` — the A18 cross-confirm driver (run over SSH; output in `raw/a18_xconfirm.txt`).

## Procedure
`cd work && sh build.sh` (add `clang -arch arm64e … rtfmt.m desc7.m splice.m`), then run each driver
`sh capfmt.sh` / `caprt.sh` / `capsamp.sh` / `capdims.sh` → `raw/*.txt`; decode with `fmtparse.py`
and the inline python in the driver output. A18: `scp` the sources, build, `sh xconf.sh`.

## Raw results / deliverables
- `raw/format_capture.txt` — 96 sampled-descriptor word0/word1 captures (DESC-5/6).
- `raw/rt_format_capture.txt` — 46 renderable-format attachment LOAD/RENDER/STORE words (DESC-1).
- `raw/sampler_capture.txt` — LOD/aniso/address/border sampler sweeps (DESC-3/4).
- `raw/dims_capture.txt`, `raw/pbe_dims_capture.txt` — 14-bit dims + PBE split (DESC-2).
- `raw/a18_xconfirm.txt` — A18 cross-confirm (0 mismatches vs M4).
- `raw/rt_rgba8_attach.hex` — curated 3-segment attachment BO (evidence).
- `analysis/format_decode.txt`, `analysis/rt_format_decode.txt` — decoded tables.
- See `RESULTS.md` for the full per-gap findings.

## Bottom line
DESC-1 **corrected** (attachment format code is byte+0x21, not +0x22) and fully covered; DESC-5
**decoded** (byte0 arrangement field + ASTC grid; all 96 formats captured); DESC-2/3/6/7 **confirmed +
refined**; DESC-4 Metal-reachable codes confirmed (unused codes need raw injection, out of scope for a
read-only pass). Every correction cross-confirmed on A18 (byte-identical to M4). Zero GPU wedges.
