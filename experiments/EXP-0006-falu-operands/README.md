# EXP-0006: float ALU 2-source operand encoding (HW-validated)

- **Date:** 2026-07-06
- **Clean-room category:** OWN-SHADER + HW-PROBE (+ PUBLIC for the applegpu *shape* only)
- **Phase / question:** Phase 1 shader ISA — resolve every operand field of the
  `0x09` float 2-source ALU (`falu2`) that a compiler must emit, and validate the
  semantics on real hardware by splice-and-observe. Follow-up to EXP-0005.
- **Device:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9.

## Hypothesis
The 6-byte `falu2` instruction (`d = op(a,b)`, opsel at bits[16:19] from EXP-0005)
carries dst / srcA / srcB register selectors, per-source negate/abs modifiers, and
a packed non-IEEE immediate. Each is a small bit-field we can locate by
differential compilation of our own MSL and pin down by splicing bits and
observing which loaded value / sign / constant appears in the dispatch output.

## Method (all clean-room)
1. Compile OUR OWN MSL (`kernels/*.metal`) with `shdump`; extract `_agc.main`
   with `agxparse.py`; locate the ALU as the byte gap between the load block and
   the store block (`analyze.py`, no assumption about ALU length/opcode).
2. **Splice-and-observe** on the real GPU via the persistent runner
   (`agxrun_persist` + `persistrun.py`, EXP-0005): splice a byte/bit of the ALU,
   dispatch with distinct known inputs, read back float32/float16, classify.
   Only OUR OWN compiled bytes are ever spliced or executed; no Apple binary is
   disassembled or introspected.

## Procedure (reproducible; run in `~/cleanroom_work/exp0006` on the device)
```sh
# build tools (reused from EXP-0005): shdump, agxrun_persist  (CLT only)
python3 sweep.py   --source kernels/add.metal --rel 0x1 --lo 0 --hi 256   # srcA byte
python3 sweep.py   --source kernels/add.metal --rel 0x3 --lo 0 --hi 256   # srcB byte
python3 sweep.py   --source kernels/add.metal --rel 0x5 --lo 0 --hi 256   # modifier byte
python3 imm.py                                   # K -> ALU bytes table
python3 validate.py imm dst size mod mode        # HW splice validations
python3 regmap.py                                # srcB index -> physical register map
python3 analyze.py add negb absb absa nega dstc map5 addhalf   # ALU byte reference
```

## Raw results  → `raw/`
- `add_sweep_rel0x{0,1,3,4,5}.log` — full 256-value byte sweeps of the add ALU.
- `map5_srcB_sweep.log` — srcB index → physical register (reg = idx>>1, bit0=size;
  index bit7 aliases mod 64 ⇒ 64 GPRs).
- `validate_imm_dst.log` — immediate splices (all K PASS) and dst b0[4:8] sweep.
- `validate_size_mod.log`, `validate_mode.log` — 16/32-bit size bit, negate/abs,
  srcB-immediate-mode splices (all PASS).
- `imm_table.txt`, `kernel_alu_ref.txt` — K→bytes table and per-kernel ALU bytes.

See `RESULTS.md` for the full analysis and the resolved bit-layout.

## Established facts → docs
- `falu2` operand encoding (dst/srcA/srcB/size/negate/immediate) → updates
  `tools/agx-isa/db.json` (`falu2`, new `falu2i`) and `docs/isa/` (orchestrator).
- Add rows to `PROVENANCE.md` (orchestrator).

## Follow-ups
- Full **dst width** (only b0[4:8]=reg0–15 exercised; upper dst bits + dst size
  bit not observed — the compiler never emitted dst≥16 here).
- **Uniform-register file** select bit (GPR-vs-uniform) not separately isolated;
  index bit7 aliased to GPR (mod 64) rather than selecting another file.
- The **10-byte extended source-modifier form** (fabs sources) and the dedicated
  **0x10 native-half 2-source group** are distinct encodings noted but not fully mapped.
- `opflags`/`ctrl`/`mod` flag bits (source cache/discard hints) are inferred.
