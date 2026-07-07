# EXP-0013: Round out the scalar ALU (HW-validated)

- **Date:** 2026-07-06
- **Clean-room category:** OWN-SHADER + HW-PROBE (+ PUBLIC for the applegpu *shape*)
- **Phase / question:** Phase 1 ISA — fill remaining scalar arithmetic/logic: conversions,
  float FMA 3-source, float unary, fmin/fmax, bitwise/shift/bitfield/compare condition codes.
- **Device state:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9,
  SIP disabled. No boot-arg/nvram changes.

## Hypothesis
The scalar ALU beyond add/mul (already in the DB) is reachable by the same splice-and-observe
method. Open questions: are numeric conversions explicit convert opcodes or a reuse of the ALU
size bit; what is the FMA 3rd-source encoding; what is the float-unary op-select; the fmin/fmax
op-select + NaN behavior; and the exact bitwise truth-table, shift variants, and compare
condition codes (validating EXP-0007's inferred entries).

## Method (clean-room)
OWN-SHADER: write minimal MSL provoking each op (`gen_kernels.py`), compile on-device with
`tools/shdump` (runtime `newLibraryWithSource:`), extract `_agc.main` with our own `agxparse.py`,
locate the ALU by structural tokenizing (`probe.py`, op-agnostic: the ALU is the byte gap between
the `0x67` load block and the `0xe7` store block). HW-PROBE: splice bytes at absolute `_agc.main`
offsets and dispatch on the real GPU via `agxrun_persist`/`persistrun.py` (persistent runner,
faults logged-and-continued), reading back typed outputs (`validate.py`). No Apple binary was ever
disassembled or introspected — only the compiled form of our own MSL.

## Procedure (reproducible)
Device workspace `~/cleanroom_work/exp0013/` (tools copied from `tools/shdump`, `tools/agxtest`).
```sh
python3 gen_kernels.py                 # write ~90 provocation kernels
python3 dump_alu.py                    # compile+extract+structural-tokenize every kernel  -> raw/dump_*.log
python3 validate.py conv fma           # HW splice-and-observe: conversions + FMA 3rd-source
python3 validate.py unary minmax       # float unary op-select + fmin/fmax + NaN/signed-zero
python3 validate.py bitwise shifts     # bitwise LUT2 sweep + shift/bitfield forms
python3 validate.py compare            # 18 compare kernels + byte+6 condition-code sweep
```
Host-side, after pulling `raw/` back:
```sh
cd tools/agx-isa && python3 roundtrip_test.py     # ALL PASS (extended with EXP-0013 instrs)
python3 isadb.py --json > db.json                 # regenerate machine-readable DB
```

## Raw results
`raw/dump_*.log` — ALU bytes (byte-diff) for every family. `raw/val_*.log` — the HW
splice-and-observe dispatches (PASS/FAIL + observed outputs). `raw/tokenize_acceptance.log` —
62/79 single-op kernels tokenize with 0 leftover under the updated DB. See `RESULTS.md`.

## Established facts → docs
See `RESULTS.md` §Deliverables. Descriptors added/upgraded in `tools/agx-isa/{isadb.py,db.json}`
(24 of 26 now HW-validated); the orchestrator folds the prose into `docs/isa/`.

## Follow-ups
- Multi-instruction lowerings: register-operand shifts (0x2b prep stage), `insert_bits`,
  signed `extract_bits`, and the transcendental Newton-Raphson sequences (frcp/frsqrt/fsqrt/
  fsin/fcos) seeded by a 0x29-group estimate (byte+3 0x09=rcp/0x0b=rsqrt/0x0d=sqrt).
- The `0x09` 8-byte **saturate** form (`fsat`, byte+2=0x1c) breaks the simple float length rule
  (byte+2 bit1) — needs its own length discriminator; left out of the DB to keep the rule stable.
- Full bit-decode of the convert/shift `src` register descriptors; the `0x02`+`0x17` compare-select
  select variant; per-source invert bit-decomposition of the `ilogic` LUT.
