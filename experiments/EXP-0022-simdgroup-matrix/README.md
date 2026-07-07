# EXP-0022: `simdgroup_matrix` (cooperative matrix) — dedicated HW vs FMA/shuffle

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER + HW-PROBE
- **Phase / question:** Phase 1 ISA — Part B5/B6 of `docs/isa/msl-feature-map.md`.
  Does Apple9 have a dedicated matrix instruction, or does `simdgroup_matrix` lower
  to a shuffle+FMA sequence?
- **Device:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d), 5 GPU cores, Metal 4 / Apple9. SIP off.

## Hypothesis
`simdgroup_multiply_accumulate` (8×8) either (a) emits a **new opcode group** unknown
to our tokenizer ⟹ dedicated matrix HW, or (b) lowers to `simd_shuffle` + `fma` over
known groups ⟹ emulated. Decide by diffing its disassembly against a hand-written FMA
matmul of the same shape. If dedicated: decode the MAC (opcode/operands/dims/types) and
the fragment load/store lane mapping; HW-validate a known matmul; check whether MPP
`matmul2d` (§B6) even compiles.

## Method (clean-room)
Compile OUR OWN MSL (`kernels/*.metal`) with `tools/shdump` (runtime
`newLibraryWithSource:`), carve `_agc.main`, tokenize/diff (`tools/agx-isa`, `analyze.py`).
**HW-validate** by dispatching each kernel over one full simdgroup (grid=32, tg=32) with
**known A,B,C** and reading back the 8×8 result (`hwval.py`, via `agxrun_persist`), and by
**splice-and-observe** on the `0xcf` accumulate/operand bytes (`splice_cf.py`,
`swap_probe.py`). No Apple binary is disassembled — only our own compiled/spliced bytes.

## Procedure
```sh
# device: ~/cleanroom_work/exp0022 (tools + kernels copied there)
clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m
clang -fobjc-arc -framework Metal -framework Foundation -o agxrun_persist agxrun_persist.m
# compile + extract each kernel's _agc.main  -> raw/mains.txt
for f in ls_f32 mad_f32 mul_f32 mad_f16 ls_f16 fill_f32 ls_f32_t; do
  ./shdump -o out/mat_$f.bin -f $f kernels/mat.metal
  python3 agxparse.py out/mat_$f.bin --stage compute --extract-hex --symbol _agc.main; done
python3 hwval.py        # T0..T6 known-matmul HW validation (ALL PASS)
python3 splice_cf.py    # prove byte+11 bit0 = accumulate-enable, byte+7 = C src reg
python3 swap_probe.py   # A/B operand-field probe
# data-type / dimension envelope: one function per file (a bad element type poisons
# the whole-file compile), see raw/dtype_envelope.txt for the generator loop.

# host analysis:
python3 analyze.py raw/mains.txt   # structural tokenize; flags the novel 0xcf group
```

## Raw results (`raw/`)
- `mains.txt` — `_agc.main` hex of all matrix / control / MPP kernels.
- `tokenize.txt` — structural tokenization (shows 1× `0xcf` in each simdgroup kernel, 0× in controls).
- `hwval.txt` — known-matmul HW validation, T0–T6 **ALL PASS** (fp32 + fp16 + fill + round-trip).
- `splice_cf.txt` — accumulate-bit / C-operand splice proofs.
- `swap_probe.txt` — A/B operand-field swap probe.
- `dtype_envelope.txt` — element-type (half/float/bfloat accepted; int rejected), mixed-precision,
  dimension (only 8×8), and MPP `matmul2d` availability (compiles, 259× `0xcf`).

See **`RESULTS.md`** for the full field map, encoding, and analysis.

## Established facts → tools
- `tools/agx-isa/`: new HW-validated **`matrix_mac`** descriptor (byte0 `0xcf`, 12 B);
  `0xcf`→12 length rule + byte0-table note; `db.json` regenerated (36 descriptors);
  `roundtrip_test.py` extended with 4 matrix encodings — **ALL PASS**.

## Result (one line)
**DEDICATED matrix hardware.** `simdgroup_matrix` → one new `0xcf` 12-byte cooperative
8×8×8 MAC (`d = a·b + c`); fp16/fp32/bf16 (+ mixed→fp32), 8×8 only, no int; loads/stores
are ordinary memory ops; MPP `matmul2d` tiles the same `0xcf`. HW-validated.

## Follow-ups
Full A/B/dst register bit-packing; exact tile↔lane permutation; `0x54` vs `0x56` mode bit;
whether the silicon supports int8/other dims beyond MSL's surface.
