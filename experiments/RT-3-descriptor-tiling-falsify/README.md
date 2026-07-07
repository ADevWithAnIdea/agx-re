# RT-3: Red-team falsification of descriptor + tiling bit layouts

- **Date:** 2026-07-07
- **Clean-room category:** HW-PROBE + OWN-SHADER + DATA-TRACE (read-only `tools/iotrace`, `-arch arm64e`).
  No Apple binary disassembled. See `../../CLAUDE.md`.
- **Role:** RED-TEAM verifier. Assume `docs/descriptors/README.md` + `format-table.md` and
  `docs/tiling/README.md` may be subtly wrong in bit positions/formulas. Run falsification tests
  (write known patterns, read raw backing, byte-diff descriptors) to **break** the claims.
- **Device:** Apple A18 Pro / G17P, macOS 26.6. Workspace `~/cleanroom_work/rt3/`.

## Hypothesis
Each documented descriptor field and twiddle formula holds on a **different** set of textures than
the originals (NPOT dims, max dims up to 16384, uncommon formats, swizzled/sRGB, non-square/3D/
cube/array/MSAA layouts). Adversarial goal: find any bit/formula that fails.

## Method (why clean-room legal)
- **HW-PROBE:** GPU-write `texel(x,y)=encode(x,y)`, read the raw backing BO, re-derive the byte→coord
  map from scratch, and check the documented offset formula reproduces it (observing hardware behavior).
- **DATA-TRACE:** capture our own process's Tier-2 argument buffer + appended descriptor blocks via the
  read-only `tools/iotrace` interposer (non-copyrightable command/descriptor bytes).
- **OWN-SHADER:** all kernels are our own MSL compiled at runtime.
- **Independent analyzers:** `*check.py` re-derive fields from raw bytes; they do **not** assume the
  doc's claimed bit positions (e.g. `dcheck.py` tests width under both 12- and 14-bit packings;
  `twcheck.py` computes predicted==actual per texel; `twiddle_orig.py` solves the GF(2) bit-perm).

## Procedure
```sh
# on device (~/cleanroom_work/rt3):
sh run.sh all          # or: descr | samp | fmt | pbe | twid | comp
# analyzers (examples):
python3 dcheck.py caps/d_w16384 --obuf <VA> --w 16384 --h 8      # width/height field size
python3 twcheck.py caps/t_2d_256 --mode 2d --w 256 --h 256 --bpp 4 --model doc|tiled
python3 twiddle_orig.py caps/cx_r32_512 --fmt r32uint --w 512 --h 512   # GF(2) solve
python3 fcheck.py caps/f_<fmt> --obuf <VA> --fmt <fmt>           # format→code rule
python3 scheck.py caps/sc_less --obuf <VA> --cmp less            # sampler bitfields
python3 pbecheck.py caps/p_rw_rgba8_64x64 --obuf <VA> --w 64 --h 64 --access readwrite
python3 ccheck.py caps/c_16x16 --w 16 --h 16 --bpp 4 --expect-comp 1
```

## Files
- Probes (our MSL harnesses): `dprobe.m` (extended obscure-format descriptor probe), `tvar.m`
  (sampler + buffer-backed base-VA), `texprobe.m`/`typrobe.m` (twiddle 2D/3D/array/cube/MSAA),
  `svar.m` (PBE storage-image). `iotrace.c` = the read-only interposer.
- Analyzers: `dcheck.py`, `twcheck.py`, `fcheck.py`, `scheck.py`, `pbecheck.py`, `ccheck.py`,
  `twiddle_orig.py` (EXP-0017 GF(2) solver), `descx.py`/`argx2.py` (descriptor extraction).
- Evidence: `analysis/RT3_evidence.txt`, `analysis/format_table.txt`, `raw/map_256x256_*.txt`,
  `raw/desc_*16384.txt`, `caps_out/*.out` (per-capture stdout logs).

## Raw results / Analysis
See **`RESULTS.md`** for the full verdict table and evidence. Headline:
- **DISCREPANCY 1** — sampled texture-descriptor **width/height are 14-bit, not 12-bit** (doc truncates
  any texture >4096). Corrected: width−1 = word0[28:31]‖word1[0:9], height−1 = word1[10:23].
- **DISCREPANCY 2** — 2D twiddle is a **row-major grid of 2^D×2^D Morton tiles** (D=6/64px for ≤4bpp,
  D=5/32px for ≥8bpp), **not** the doc's "pure Morton, no sub-tile"; tile size is bpp-dependent
  (contradicting §1.3). Doc formula fails at 256×256 (32768/65536 texels wrong) and 512×512; the
  corrected tiled model reproduces every capture with 0 mismatch.
- Everything else — type/format/swizzle/sRGB/baseVA/mip/sample fields, the full sampler descriptor,
  PBE packing + read_write dual, the format→code rule on 38 obscure formats, NPOT/3D/array/cube/MSAA
  stacking, and the compression threshold/aux size/placement — **CONFIRMED**.

## Established facts → docs (for the orchestrator; RT-3 does NOT edit docs)
- `docs/descriptors/README.md` + `format-table.md` §5: width−1 field is **word0[28:31]‖word1[0:9]
  (14-bit)**, height−1 is **word1[10:23] (14-bit)**. Fix the `tools/iotrace` twiddle helper's
  `(w1&0xff)<<4` accordingly.
- `docs/tiling/README.md` §1.1–§1.3: replace the "pure Morton / no sub-tile / bpp-independent" model
  with the row-major-tiled-Morton model above (tile edge 64 for bpp≤4, 32 for bpp≥8).

## Follow-ups
- 1 bpp (r8/stencil8) tile edge not directly measurable with a unique-coord pattern (extrapolate 64;
  confirm via allocation of a >4096-wide r8 texture if a lossless tag can be devised).
- word1 bits[30:31] and the exact large-3D/array per-plane tiling (planes >32/64 px) not characterized.
- The bpp→tile-edge break (4 B vs 8 B) and whether any format uses a non-square tile — untested beyond
  the 2/4/8/16 bpp probed here.
