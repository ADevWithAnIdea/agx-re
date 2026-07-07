# EXP-0020: Consolidate the register / uniform machine model

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER + HW-PROBE (+ PUBLIC for the applegpu *shape* only)
- **Phase / question:** ROADMAP Phase 1 — pin the GPR file size, 16-bit-half addressing,
  the uniform register file, the shader footprint declaration, and the Dynamic-Caching
  spill model, HW-validated, for the compiler.
- **Device:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9.

## Hypothesis
The register model was fragmentary (EXP-0006 saw "64 GPRs" via a `srcB` fold; EXP-0007 saw
a wider integer `dst=b3`; EXP-0010 found scalar uniforms + buffer base pointers reaching
registers). We expected a single coherent model: a fixed 32-bit GPR file (64/96/128), a
16-bit-half addressing rule, a uniform register file with a selector in the operand
encoding, a footprint declaration the driver hands the HW (EXP-0011 `+0x00` config word),
and — on Apple9 — a register-spill (Dynamic-Caching) mechanism.

## Method (all clean-room)
1. **Register-pressure kernels** (`gen_pressure.py`, `gen_int_pressure.py`): cyclic-FMA
   loops carrying K live 32-bit values (data-dependent trip count so the allocator cannot
   collapse them). Compile with our own `shdump`; read the compiler's own **register
   footprint** out of the compiled shader's `__GPU_METADATA` FlatBuffer (OWN-SHADER — our
   own archive's metadata, walked with our own parser). Run on the **real GPU** with `n=1`
   (loop becomes a K-register copy) and exact-compare int outputs → HW validation that all
   K values survived in registers/scratch.
2. **Half-precision** footprint (same kernels, `half`): compare regs-per-value vs `float`.
3. **Uniform probes** (`gen_uniform.py`): contrast GPR-source vs uniform-source vs mixed
   ALU ops; byte-diff the operand encoding; inspect the `constant_program` (uniform
   datapath) and the uniform→GPR move.
4. **Config-word correlation** (`make_cvar2.py` → `cvar2` + our EXP-0011 `iotrace` — reused,
   not edited): capture the launch-descriptor `+0x00` word for graded register footprints.

## Procedure
On device under `~/cleanroom_work/exp0020/` (tools: our `shdump`, `agxrun`, `agxparse.py`,
`agx-isa`, and the EXP-0011 `cvar`/`iotrace` reused verbatim):
```sh
python3 gen_pressure.py float           # footprint & code vs K (raw/pressure_float.txt)
python3 dump_sections.py; python3 fbstats.py float   # __GPU_METADATA reg-footprint field
python3 gen_int_pressure.py 8 32 48 64 72 80 96 128 160 256   # HW correctness + f0 + scratch
python3 gen_pressure.py half; python3 fbstats.py half         # half packing
python3 gen_uniform.py                  # uniform selector + datapath (raw/uniform_probes.txt)
python3 make_cvar2.py && clang ... cvar2.m && <iotrace capture>   # config word vs footprint
```

## Raw results
`raw/` (text only): `pressure_float.txt`, `sections_float.txt`, `metadata_float.txt`,
`regfootprint_float.txt`, `int_correctness.txt`, `uniform_probes.txt`,
`config_correlation.txt`, `config_threshold.txt`, `mm24.hex`. See `RESULTS.md`.

## Established facts → docs
See `RESULTS.md` for the full table (HW-validated vs inferred marked). Tool refinements
landed in `tools/agx-isa/` (`uniform_mov` descriptor; register-model semantics 64→96;
uniform-select bits; length rule). `roundtrip_test.py` → ALL PASS.

## Follow-ups
- Exact uniform-register count/addressing bit-decode; the native-half `0x10`/`0x11`
  half-select encoding (direct HW read of a high half).
- Whether 96 is a hard silicon limit or an occupancy policy; finer occupancy tiers.
- Where the scratch-base pointer / spill address is supplied to the HW (BO side).
