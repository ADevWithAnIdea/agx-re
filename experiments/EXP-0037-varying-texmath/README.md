# EXP-0037: Vertex/mesh varying-store + texture coordinate/interp math (census wrap-up W2)

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER (+ PUBLIC for the ISA DB / Mach-O format)
- **Phase / question:** ROADMAP G-13 (instruction census → ~0 undecoded groups). Closes the two
  census-undecoded frontier groups EXP-0036 flagged: the vertex/mesh varying-emit stores
  (`0x57` / `0x05` / `0x06`) and the texture coordinate/interpolation math (`0x2e` / `0x92` /
  `0x26`), plus the `0xb0` sampler-op mis-tokenization.
- **Device state:** A18 Pro (G17P), macOS 26.6 (25G5043d), Command Line Tools only. No reboot
  (all faults contained).

## Hypothesis
1. The vertex stage writes `[[position]]` + varyings to the UVS/parameter buffer that the FS
   interpolates (EXP-0029's `iter` op). That store is a real opcode with a source-register and an
   output-slot field; position and user varyings should be distinguishable.
2. `0x2e/0x92/0x26` are the coordinate/address/LOD math feeding `tex_sample`; `0xb0` is the
   EXP-0016 sampler op the census mis-tokenized (a gating/length bug, not a new instruction).

## Method (clean-room: OWN-SHADER)
- Compile **our own** MSL with `tools/shdump --render` (vertex+fragment) and extract each stage's
  `_agc.main` with our own `agxparse.py`. Byte-diff variants to localize fields.
- **Splice-and-observe** on the real GPU with `tools/agxtest/agxrender`: draw a bufferless
  full-screen triangle (positions/varyings computed from `[[vertex_id]]`, so the render testbed
  needs no vertex buffer), splice one byte of a store/sampler op, and read back the pixel. The
  `PIPELINE_SOURCE archive` line proves the spliced OWN-SHADER machine code ran.
- Reuse the EXP-0036 census archives (`~/cleanroom_work/exp0036/build/k_tex_*.bin`, `r_*.bin`) for
  the texture kernels; tokenize with the current `tools/agx-isa` length rule vs the proposed fixes
  and require **byte-exact re-serialization**.
No Apple binary was disassembled; only our own compiled shader bytes are inspected/spliced.

## Procedure
- `kernels/vary.metal` — varying-store probe (2 float4 varyings, distinct per-vertex gradients).
- `kernels/texvary.metal` — texture-sample probe (samples a bound texture).
- `harness/vsplice.py` — copy archive → splice at an absolute offset → `agxrender` → print corner
  pixels. `harness/tok0037.py` / `harness/toklen.py` — candidate length function + tokenizer used
  for the coverage measurement.
- Device workspace: `~/cleanroom_work/exp0037/` (tools copied from exp0036/exp0008/exp0016 builds).
- Reproduce:
  ```sh
  # on device (~/cleanroom_work/exp0037)
  ./shdump -o vary_va.bin --render --vertex v_main --fragment f_va vary.metal
  python3 agxparse.py vary_va.bin --stage vertex --locate _agc.main      # -> 12160 168
  A="--archive vary_va.bin --source vary.metal --vertex v_main --fragment f_va --width 4 --height 4"
  python3 vsplice.py $A --label baseline                                  # RGB gradient
  python3 vsplice.py $A --label vz->vx.slot --splice 12312=80             # R shows va.z gradient
  python3 vsplice.py $A --label posSlot --splice 12280=80                 # black (geometry killed)
  ```

## Raw results
- `raw/hw_validations.txt` — every splice + pixel (Part 1 varying store, Part 2 sample bundle).
- `raw/vertex_mains.txt` — extracted vertex `_agc.main` hex (vary_va, vary_vb, v_basic).
- `raw/tokenization_report.txt` — per-kernel byte-coverage, current rule vs EXP-0037 fixes,
  re-serialization check.

## Analysis
See `RESULTS.md`. Headline: the VS varying store is **`0x57`** (8 bytes, HW-splice-proven fields);
`0x05`=psel / `0x06`=`0f06` reconverge (already decoded, not a store family); `0xb0`/`0x90` is the
10-byte sampler op fixed by **widening the companion gate**; `0x2e/0x26` are float fused-mul
coordinate ops the float-ALU length rule mis-lengthed. Overall texture+render byte coverage
75% → 89% (byte-exact), with the core texture kernels going to 97-100%.

## Established facts → docs
Validated descriptors + length/gating fixes in `new_descriptors.json` (schema-compatible with
`tools/agx-isa/db.json`) for the orchestrator to merge; the prose facts belong in `docs/isa/`.

## Follow-ups
- The VS per-vertex value-computation select family (`0x40/0x1a/0x21`) that feeds the `0x57`
  stores (not a store; separate group).
- Full bit-decode of the coordinate-math ALU (`coord_madf`/`tex_coord_setup`) — needs a
  multi-texel texture harness (EXP-0016 `texr.m`) to make a coordinate splice observable.
- `k_tex_atomic` texel-address atomic math (densest residue, 71→74%).
