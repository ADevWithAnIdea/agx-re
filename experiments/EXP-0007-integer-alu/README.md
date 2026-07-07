# EXP-0007: characterize the INTEGER ALU family (byte0 `0x9f`)

- **Date:** 2026-07-06
- **Clean-room category:** OWN-SHADER + HW-PROBE (+ PUBLIC for the applegpu *shape*)
- **Phase / question:** ISA Phase 1 — the last unsolved arithmetic group. Follow-up to
  EXP-0005 (float ALU op-select + length rule) and EXP-0006 (float operand encoding).
- **Device state:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9.
  No boot-args/nvram changes. SIP disabled.

## Hypothesis
The integer ALU (byte0 low-nibble `0xf`, e.g. `0x9f`) is 10/12 bytes; a length bit (like the
float group's byte+2 bit1) distinguishes them. Integer ops likely mirror the float ALU: a
2-source form with an op-select field, `(reg<<1)|is32` operands, a 64-GPR model, source
negate, and an integer immediate (reversed from the float minifloat).

## Method (clean-room legal: OWN-SHADER + HW-PROBE)
1. Write minimal integer MSL kernels (`out[gid] = a[gid] OP b[gid]`, immediate and 3-source
   variants) — all **our own source**. `gen_kernels.py` emits them.
2. Compile on-device with `shdump` (runtime `newLibraryWithSource:`), extract `_agc.main`
   with `agxparse.py`, tokenize structurally (`dump_alu.py`). Byte-diff minimal pairs.
3. **Hardware-validate** every claim by splicing bytes into our own compiled archive and
   running on the real GPU (`agxrun_persist` + `persistrun.py`, the EXP-0005 persistent
   runner), reading back int32 outputs (`intprobe.py`, `intsweep.py`, `intval.py`).
No Apple binary is ever disassembled or introspected.

## Procedure (reproducible)
On the device under `~/cleanroom_work/exp0007/` (tools copied from exp0006):
```sh
python3 gen_kernels.py                 # emit kernels/*.metal (our own MSL)
python3 dump_alu.py <kernel...>        # compile+extract+tokenize -> ALU bytes
python3 smoke.py                       # int I/O sanity: each op unmodified == expected
python3 intsweep.py --source kernels/iadd.metal --rel 0x0   # sweep one ALU byte 0..255
python3 intval.py                      # imm / negate / signedness / lengthbit / dst
```
Analysis / DB update on the host in `tools/agx-isa/` (`isadb.py`, `roundtrip_test.py`).

## Raw results
`raw/` (text logs only): `dump_alu_all.log` (all ALU encodings), `intval.log` (the targeted
validations), and per-byte sweep logs `*_b?.log`. Key observations summarized in `RESULTS.md`.

## Analysis
See `RESULTS.md`. Headline: the 0x9f length rule is **byte+1 bit0** (1→10B 2-source,
0→12B 3-source multiply-add); the integer ops are spread over several byte0 groups (mirroring
the float falu2/fminmax/funary split); integer immediate is a plain 8-bit `(K<<1)` inline
field (NOT a minifloat).

## Established facts → docs
Orchestrator to fold into `docs/isa/` + `PROVENANCE.md` (this experiment does not edit docs/).
Tooling updated: `tools/agx-isa/{isadb.py,db.json,roundtrip_test.py}` (integer length rule +
descriptors, roundtrip extended and passing).

## Follow-ups
- Full bit-decode of the srcA/srcB register descriptors in the 10/12-byte tail (located, not
  fully bit-mapped) and the 64-GPR aliasing confirmation for integer sources.
- Multi-instruction lowerings: shifts (`0x2b`+`0x27`/`0x9f` stages), bitfield-insert,
  reg-reg bitwise AND/OR/XOR op-select (b2 + b4/b5 source-invert truth-table).
- The `0x0b` group disambiguation (float unary vs integer bitwise share byte0 0x0b).
- Integer compare (`0x12`, 14B) condition/sign field bit-decode.
