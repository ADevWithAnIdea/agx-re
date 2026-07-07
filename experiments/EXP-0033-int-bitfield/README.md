# EXP-0033: integer / bitfield instruction completeness (capability backlog #12)

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER + HW-PROBE (+ PUBLIC for the applegpu *shape*)
- **Phase / question:** capability completeness — close the integer/bitfield gaps a
  compiler needs (bit-count/scan, bitfield insert/extract, rotate, min3/max3/median3,
  pack/unpack + 16-bit-packed, 64-bit integer lowering).
- **Device:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9.
  Device workspace `~/cleanroom_work/exp0033/`.

## Hypothesis
The AGX integer ISA (EXP-0007/EXP-0013) has dedicated ops for the common bit
manipulations (popcount seen as `0x27`, extract as `0xa7` ibfe), and the higher-level
compiler builtins (clz/ctz/reverse/rotate/insert/min3/64-bit) are some mix of *dedicated
single ops* and *multi-instruction lowerings*. Probe each with a minimal MSL kernel;
extract the compiled `_agc.main`; byte-diff/ tokenize to find the opcode+form; run
unmodified to HW-validate semantics; splice key op-select / size bits to lock them down.

## Method (clean-room legal)
1. **OWN-SHADER:** write minimal MSL kernels (one target op each), compile on the device
   with our own `shdump` (runtime `newLibraryWithSource:`), extract the raw AGX
   `_agc.main` bytes with our own `agxparse.py`. (`gen_kernels.py`, `dumpall.py`.)
2. **Analyse** the extracted bytes with our READ-ONLY `tools/agx-isa` length rule +
   decoder to tokenize each program (`analyze.py`); byte-diff opcode/form fields.
3. **HW-PROBE:** run each kernel unmodified with known inputs on the real GPU
   (`agxrun_persist` + `persistrun`/`intprobe`) and compare to a Python reference
   (`runval.py`, `halfpack_val.py`, `cmp64.py`) — behaviour HW-validation.
4. **Splice-and-observe:** for the highest-value claims, splice op-select / size bytes
   and observe the output change (`splice_count.py` op-select map; `splice_u64.py`
   native-64-bit add/sub). No Apple binary is ever disassembled — only our own bytes.

## Procedure (re-runnable)
```sh
# device workspace already has our OWN-SHADER tools (shdump, agxparse.py, agxrun_persist,
# persistrun.py, intprobe.py) copied from a prior experiment.
python3 gen_kernels.py                 # write kernels/*.metal (our own MSL)
scp kernels + *.py  -> ~/cleanroom_work/exp0033/ on the device
ssh device: python3 dumpall.py        > raw/hex_dump.log     # compile+extract every kernel
python3 analyze.py <kernel...>                                # host: tokenize/byte-diff
ssh device: python3 runval.py         | tee raw/runval.log   # behaviour HW-validation
ssh device: python3 splice_count.py   | tee raw/splice_count.log   # bit-count op-select
ssh device: python3 splice_u64.py     | tee raw/splice_u64.log     # native 64-bit add/sub
ssh device: python3 halfpack_val.py   | tee raw/halfpack_val.log   # half/pack/unpack
ssh device: python3 cmp64.py          | tee raw/cmp64.log          # 64-bit compare
```

## Raw results
- `raw/hex_dump.log` — 45/45 kernels compiled; `_agc.main` (+ constant_program) hex each.
- `raw/runval.log` — 20/20 behaviour checks pass (bit-count/scan, extract/insert, rotate,
  min3/max3/median3/clamp, 64-bit add/sub/mul/shl/shr/cmp/widen).
- `raw/splice_count.log` — bit-count/scan op-select map (splice-proven).
- `raw/splice_u64.log` — **native single-op 64-bit add with hardware carry** (splice-proven).
- `raw/halfpack_val.log` — 4/4 half-packed + pack/unpack behaviour pass.
- `raw/cmp64.log` — 64-bit signed/unsigned compare (mixed 0/1) pass.
- **0 reboots**; a couple of contained faults on degenerate spliced op-selects, logged-and-continued.

## Analysis / established facts
See `RESULTS.md` for the full write-up. Headline findings (HW-validated unless marked):
1. **Bit-count/scan** is a single-op family (byte0 `0x27`/`0xa7`, byte+2 `0x56`, 8 B),
   op-select = (byte0 bit7, byte+1): **popcount** `(0x27,0x05)`, **reverse_bits**
   `(0xa7,0x04)`, **find-MSB / bit-scan-reverse** `(0xa7,0x05)` — all splice-proven.
   **clz/ctz are multi-instruction lowerings** on find-MSB + subtract + clamp (+ a `0x2b`
   low-bit-isolate prep for ctz).
2. **extract_bits (unsigned)** = single `0xa7` 12 B ibfe (EXP-0013 confirmed);
   **signed extract** = ibfe + a sign-extension shift pair (multi-instruction).
   **insert_bits** = **mask (`0x0b`) + shift (`0x2b`) + combine (`0x9f`)** — no dedicated op.
3. **Rotate by immediate** = a single 12 B `0x27` funnel op (`byte+1==0x01`); **rotate by
   register** = shift-prep + shifts + OR (multi-instruction; hand-written idiom lowers
   identically).
4. **min3/max3/median3 are exposed by MSL but have NO dedicated silicon** — they lower to
   sequences of the 2-input integer min/max (`0x02` group; the first op is the `0x22`
   variant). `clamp` = max-then-min.
5. **as_type bitcast = free (no op).** Native **fp16** arithmetic = the **`0x10`** group
   (`0x1c` hadd / `0x1d` hmul); **half2 packs both lanes into ONE `0x10` op** (packed
   2-lane). **int16 does NOT pack** (short2 = two 32-bit `0x9f` adds). `pack_*_2x16` =
   single `0x97` op, `unpack_*_2x16` = single `0x17` op.
6. **64-bit = register pairs.** **Native single-op 64-bit add/sub exists** (splice-proven:
   `0x1f`→`0x9f` gives correct 64-bit add with carry-out); the compiler also emits an
   explicit carry chain (`0x32` carry-generate) for add. 32×32→64 mul = one 12 B `0x9f`
   mul; 64×64 mul = 3 mul(-add)s; 64-bit shift/compare = multi-instruction.

Deliverables: `new_descriptors.json` (7 new/refined descriptors + 6 length-rule additions),
this `README.md`, `RESULTS.md`, harness scripts, `raw/` text logs.

## Follow-ups
- Full bit-decode of the bit-count/scan and rotate operand fields; the `0x2b/0x3b/0x5b/0x8b`
  shift-prep family lengths and semantics.
- The `0x32` 64-bit carry-generate op and whether the compiler *always* has a native
  64-bit add path (why add sometimes uses the carry chain vs the native pair op).
- `0x97`/`0x17` pack/unpack: the snorm/half variants and byte+2 disambiguation from
  frag_color_pack / simd_ballot (collision gating for the DB).

## Clean-room status
Clean. Only our own MSL was compiled and only our own compiled bytes were inspected/
spliced/executed. Reused OWN-SHADER tools `shdump`, `agxparse.py`, `agxrun_persist`,
`persistrun.py`, `intprobe.py`; READ-ONLY `tools/agx-isa` for tokenizing. `raw/` holds
text logs only; `.bin` archives stay on the device under `~/cleanroom_work/exp0033/`.
