# RT-7 — Red-team falsification of the register/uniform machine model + special-register/ABI

**Role:** RED-TEAM verifier. Assume the machine-model + SR/ABI sections of `docs/isa/README.md`
(consolidated from EXP-0020 register model + EXP-0031 SR/ABI, refined by RT-1a-FIX) may be
**subtly wrong**. Craft falsification tests to BREAK each claim; report discrepancies. Finding
nothing strengthens the docs. **Did NOT edit `docs/`, `tools/agx-isa/`, `tools/iotrace/`,
PROVENANCE, reviews/; did not commit.**

**Clean-room category:** OWN-SHADER + HW-PROBE (+ DATA-TRACE for the tier-bit attempt, reusing the
existing `iotrace.dylib` read-only). Every byte inspected/spliced/executed and every metadata field
read is from a shader **we compiled from our own MSL**. No Apple binary was disassembled. Device:
Apple A18 Pro / G17P, macOS 26.6. Device workspace `~/cleanroom_work/rt7/`.

## Claims under test (docs/isa/README.md → "Machine model" + "Special-register enum + shader ABI")
1. **96 addressable 32-bit GPRs (r0–r95)**; cap is exactly 96; r96+ alias-or-fault?
2. **16-bit halves packed 2-per-GPR** (64 halves → 50 GPRs); low/high half addressing.
3. **Uniform register file + GPR-vs-uniform select** (RT-1a-FIX `falu2_uni`, bit39 + byte+1 exp<8).
4. **Spill to scratch** above 96 GPRs; **occupancy tier bit** (launch +0x00 bit23) flips at ~12 GPRs.
5. **SR-number table** (`get_sr` byte1): tpig 0xa0.., simd_lane 0x82, simd_group 0x85, vertex_id 0xdd,
   instance_id 0xd8, front_facing 0xc5, simd_is_helper 0x84, …
6. **Vertex attribute fetch = in-shader software** (stride/offset/format live in the VS).

## Method
Compile our MSL → extract `_agc.main` + `__GPU_METADATA` (`tools/shdump`) → splice bytes → run on the
real GPU and read back (`tools/agxtest`: `agxrun`, persistent `agxrun_persist` + `persistrun.py`).
Two novel probe techniques used here:
- **Physical-register readout by splice**: keep K known values live, then sweep a *validated*
  register-selector field (memory-index byte+5, or float srcA byte+1) across r0..r127 and read back
  each physical register's content — directly maps the file and its out-of-range behaviour.
- **SR read-off**: compile one kernel per builtin storing to `out[0]` (a single `get_sr`), read the
  compiler's own byte1 → the code→builtin map, then HW-splice the value `get_sr` to prove semantics.

## Harness (`harness/`)
- `t1_gpr_meta.py` — fine f0 metadata sweep (cap) + n=1 correctness.
- `t1c_regmap.py` — r96+ via the HW-validated memory-index field (byte+5).
- `t1d_alu_confirm.py` / `t1f_alias_decisive.py` — r96+ via the ALU srcA field (byte+1); r64≠r0.
- `t2_half.py` — float-vs-half f0 (2/GPR re-proof); `t2b_half.py` (device) — low-half splice.
- `t3b_uniform.py` / `t3c_uniform_form.py` / `t3d_falu2uni.py` — uniform forms, select bits, index.
- `t4_tierbit.py` + `cfgcap.m` — SIGUSR1 launch-descriptor capture attempt for the tier bit.
- `t5a_sr_readoff.py` (compute read-off) / `t5b_sr_hwsplice.py` (HW splice) / `t5c` (tgpg disambig)
  / `t5d_graphics_sr.py` + `t5e_graphics_readoff.py` (vertex_id/instance_id/front_facing/simd_is_helper).
- `t6_attr.py` (+ `attrdump.m` reused from EXP-0031) — vertex-attribute descriptor sweep.

Raw logs in `raw/` (text only). See `RESULTS.md` for per-claim CONFIRMED / DISCREPANCY verdicts.
**Reboots: 0** (all GPU faults were contained per-command-buffer `CMDBUF_ERROR`s — themselves data).
