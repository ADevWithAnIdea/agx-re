# EXP-0018: Atomics + Subgroup / Quad operations (HW-validated)

- **Date:** 2026-07-06
- **Clean-room category:** OWN-SHADER + HW-PROBE
- **Phase / question:** Phase 1 ISA — atomic RMW family, SIMD-group (Vulkan subgroup) ops, quad ops.
- **Device state:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d), 5 GPU cores. SIP disabled.

## Hypothesis
- Atomics use a new op (EXP-0012 noted byte0 `0xbf`) inside an exec-mask CAS/retry loop around a
  `67 01…` access; simple atomics might be native or loop-emulated. Decode operation / address /
  data / return register; device vs threadgroup.
- Subgroup ops (broadcast / shuffle / reduce / prefix-scan / ballot / vote / elect) map to one or
  more new instruction groups; SIMD width expected 32.
- Quad ops are the same permute network at execution width 4.

## Method (clean-room)
Compile OUR OWN MSL (`kernels/atomics.metal`, `simd.metal`, `quad.metal`) with `tools/shdump`,
carve `_agc.main`, tokenize/byte-diff (`tools/agx-isa`, `split.py`, `analyze.py`). **HW-validate**
by (a) running each op with a **distinct known per-lane input** and reading back per-lane outputs
(direct semantic proof), (b) atomic **aggregate** tests (many lanes → one location), and (c)
**splice-and-observe** on the operation field (`hwval.py`, `run_tests.py`, `splice_simd.py`,
persistent runner). No Apple binary is disassembled.

## Procedure
```sh
# device: ~/cleanroom_work/exp0018 (tools + kernels copied there)
./extract.sh                 # compile every kernel, carve _agc.main -> raw/mains.txt
python3 run_tests.py         # subgroup+quad semantics, atomic aggregate, atomic op splice
python3 splice_simd.py       # splice-validate the SIMD-reduce op-select field
# capability probes (expected compile FAILs) -> raw/capability_probes.txt
# host analysis:
python3 analyze.py raw/mains.txt          # structural tokenize
python3 split.py <hex>                     # byte-exact instruction split
```

## Raw results
- `raw/mains.txt` — `_agc.main` hex of all 63 kernels.
- `raw/hwval.txt` — every subgroup/quad/atomic HW test (ALL PASS).
- `raw/splice_simd.txt` — SIMD-reduce op-select splice proofs (ALL PASS).
- `raw/capability_probes.txt` — negative capability probes (float atomic min/max, 64-bit atomic add).

See `RESULTS.md` for the full field maps and operation tables.

## Established facts → tools/docs
- `tools/agx-isa/` gains 5 HW-validated descriptors: `simd_reduce`, `simd_shuffle`, `simd_ballot`,
  `atomic_rmw`, `atomic_mem`; length rule + `byte0_table` updated; `roundtrip_test.py` extended and
  passing (34 descriptors, 31 HW-validated).

## Follow-ups
- Full bit-decode of the shuffle lane/register operands and the reduce `src`/`shape` sub-fields.
- Threadgroup atomic exact encoding (op field position under the barrier-wrapped lowering).
- The standalone `atomic_mem` op-code space (indexed add 0x60 vs reduced add 0x20; 64-bit forms).
- `0x2c` / `0x24` / `0x1b` scaffolding ops in the atomic lowering (elect-lane prep / broadcast).
