# EXP-0015: Texture / Sampler / Buffer descriptor bit layouts (Phase 3)

- **Date:** 2026-07-06
- **Clean-room category:** DATA-TRACE + OWN-SHADER (+ HW-PROBE by change-one-parameter)
- **Phase / question:** ROADMAP Phase 3 (resource descriptors) — decode the 32-byte
  texture descriptor, the sampler descriptor, and the inline buffer form seeded by
  EXP-0011 (`docs/cmdstream/README.md`, "Argument buffer (Tier-2)").
- **Device:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d), Command Line Tools only.

## Hypothesis
The texture/sampler descriptors that Metal appends into the Tier-2 argument buffer
(EXP-0011: BO `gpu_va 0x100000e0000`, table at `+0x14a0`, texture/sampler = 8-byte
pointer to a descriptor block in the same BO) are fixed-layout hardware structures. By
varying exactly ONE Metal descriptor parameter and byte-diffing the appended block, each
field (pixel format, dims, type, mips, swizzle, base VA, sRGB; and for samplers the
filters, address modes, compare func, LOD/aniso, border color) can be localised and its
encoding read off directly. We also probe for capabilities richer/poorer than Metal
surfaces (arbitrary border color, address modes, compare modes).

## Method (clean-room legality)
- **OWN-SHADER + public Metal API:** `tvar.m` is our own MSL compiled at runtime; the
  texture/sampler come from public `MTL*Descriptor` APIs. We print our own resources'
  GPU VAs for correlation. Nothing disassembles any Apple binary.
- **DATA-TRACE:** the descriptor bytes are captured with the existing, **read-only**
  `tools/iotrace` interposer (used unchanged) which snapshots the CPU-side bytes of the
  GPU buffer objects our own process registers. Descriptors are non-copyrightable
  hardware data per the Asahi clean-room policy.
- **HW-PROBE (change-one-parameter):** every field is confirmed by a clean single-word
  byte-diff between two captures differing in exactly one Metal parameter. Fields so
  confirmed are marked **HW-validated**; anything read but not independently varied is
  **inferred**.

## Procedure (reproducible)
On the device under `~/cleanroom_work/exp0015/` (files: `tvar.m`, `descx.py`, `run.sh`
+ read-only `iotrace.c`, `dumpscan.py`, `bodiff.py` copied from `tools/iotrace`):

```sh
sh run.sh          # builds iotrace.dylib + tvar, runs the whole capture matrix,
                   # extracts + diffs every appended descriptor block into analysis/ + raw/
```

`tvar` binds a texture+sampler+buffer into a compute kernel (arg layout identical to
EXP-0011's `tex` kernel: `[[texture(0)]] [[sampler(0)]] [[buffer(0)]]`) with all
descriptor parameters as CLI flags; `--dump` SIGUSR1s the interposer after
`waitUntilCompleted`. `descx.py` follows the `+0x14a0`/`+0x14a8` arg-buffer pointers to
the appended texture/sampler descriptor blocks and dumps/diffs them (robust to layout
shifts). The capture matrix sweeps: 31 pixel formats; width/height/depth; texture type
(1D/2D/3D/cube/2DArray/2DMS); mip count; array length; sample count; swizzle; base VA
(buffer-backed texture, VA = printed `gpuAddress`+offset); and for the sampler:
min/mag/mip filters, s/t/r address modes, anisotropy, compare function (depth kernel),
LOD min/max clamps, unnormalized coords, and the 3 border-color presets.

## Raw results
`raw/diffs/` — per-group one-parameter byte diffs (`diff_format.txt`, `diff_dim.txt`,
`diff_type.txt`, `diff_swizzle.txt`, `diff_va.txt`, `diff_sampler.txt`,
`diff_compare.txt`). `raw/descriptors/` — per-capture descriptor word-dumps.
`raw/lod_aniso.txt` — LOD/anisotropy disambiguation. `raw/va_correlation.txt` — base-VA
tracking. Summary + full field maps in `RESULTS.md`.

## Analysis / established facts
See `RESULTS.md`. Texture descriptor = 32 bytes; sampler descriptor = **8 bytes**;
buffer = inline 8-byte GPU VA (no length/format word). Format→code table, swizzle codes,
type codes, address-mode/compare/border codes all HW-validated. Feeds `docs/descriptors/`.

## Follow-ups
- The "large-texture" layout bits (word1 bit27, word3 bit31) + the secondary VA at
  descriptor `+0x10` correlate with texture size → the tiling/twiddling story (Phase 4,
  `docs/tiling/`).
- Cube-array / 1D-array / 2DMS-array type codes (6/0/... extrapolation) untested.
- Non-2D buffer-backed base-VA (VA field confirmed for 2D; other types inferred to share).
