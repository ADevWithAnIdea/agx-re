# EXP-0133 — M4 full-format capability and conversion matrix

Third increment of DRV-FMT-01 (P1.2), demanding the FULL per-format
capability and conversion table (sampled / filtered / storage read+write /
atomic / renderable / blendable / depth-stencil / linear / compressed /
MSAA / resolve / sparse / pitch / mip offset / buffer-texture / swizzle /
normalization / rounding / pack-unpack) across every exposed
`MTLPixelFormat`, not the 20 formats EXP-0070+EXP-0079 covered.

- **Question / hypotheses / frozen case grammar:** `PRE_REGISTRATION.md`
- **Frozen contract (138-format target matrix, 1548 total cases):**
  `CAPTURE_CONTRACT.json` (derived by `analysis/gen_formats.py` +
  `analysis/gen_contract.py` from the public `MTLPixelFormat.h` header)
- **Harness:** `harness/probe.m` (Obj-C, one process per case; `--mode
  capability|conversion|layout|sparse`), `kernels/capability.metal` +
  `kernels/conversion.metal` (authored MSL)
- **Runner / verifier / manifest / analysis:** `run.py`, `verify.py`,
  `make_manifest.py`, `analysis.py`
- **Results:** `RESULTS.md` (written after both captures)
- **Pre-freeze exploration (process history, not evidence):**
  `provenance/pre_freeze/`

Target: local Apple M4 (G16G) only, public Metal API only, per
`../../CLAUDE.md` / `../../CODEX.md`. No A18/G17P testing (hands-off).
