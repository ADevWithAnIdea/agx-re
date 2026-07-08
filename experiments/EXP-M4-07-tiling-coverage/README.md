# EXP-M4-07 — Tiling coverage (close TIL-1..TIL-6)

**Hypothesis:** the tiling rules in `docs/tiling/README.md` were validated narrowly (mostly bpp4,
2D, 4 block formats) and over-generalized. The bpp1/T=128 exemplar is systemic — each tiling rule
hides a bpp/type/block-size-dependent surprise in its untested arguments.

**Clean-room category:** HW-PROBE + OWN-SHADER + DATA-TRACE. No Apple binary disassembled.

**Method:** write/upload a known `element → encode(coord)` pattern into a GPU-optimal (twiddled)
texture; snapshot the backing BO + descriptor via read-only `tools/iotrace`; a host model-checker
GF(2)/full-grid-solves the texel→byte map against every candidate layout model (tile edge T,
cols/granule rule, plane/tail stride) — the 0-mismatch model is the truth; backing-BO size is an
orthogonal check. Primary device **local Apple M4**; every **correction** cross-confirmed on the
**A18 Pro** (`raw/til_a18_verify.txt`).

**Gaps closed:** TIL-1 (3D/array/cube/MSAA per bpp), TIL-2 (17 block formats), TIL-3 (MSAA), TIL-4
(mips per bpp), TIL-5 (compression aux size — memory-safety), TIL-6 (eligibility threshold).

See `RESULTS.md` for verdicts, evidence tables, and the doc corrections. Reproduce: build the
probes in `work/` with `clang -arch arm64e` and run `sweep_til1.sh` / `sweep_msaa.sh` (and the
per-gap loops in `RESULTS.md`).
