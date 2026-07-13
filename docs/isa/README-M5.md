# M5 (Apple10 / G17g) Shader ISA

The M5 GPU (`MTLGPUFamilyApple10`, arch `applegpu_g17g`, SoC T8142) runs a **G17-family sibling** of
the A18 Pro (G17P/Apple9) ISA documented in `README.md` + `encoding-tables.md` (this dir). Empirically
(EXP-M5-02/03) **~84% of M5 instruction bytes decode with the unmodified A18 DB**, and after fixing the
G17P→G17g deltas the M5 DB reaches **96.6% (own) / 98.0% (third-party) byte coverage with round-trip
identity** (EXP-M5-05). So the M5 ISA is documented as **"the A18 ISA (see `README.md`/`encoding-tables.md`)
plus the deltas below"**, not re-specified from scratch.

## Machine-readable DB
`../../tools/agx-isa-m5/` — the M5 (dis)assembler DB (`isadb.py` + generated `db.json`), forked from the
A18 `tools/agx-isa/`. `db.json` is the exhaustive, machine-readable per-instruction encoding table
(match bits + typed bit-fields + lengths + semantics + provenance). Use `agxisa.py tokenize/disasm/asm`.

## G17P → G17g ISA deltas (the M5-specific part)
Source: EXP-M5-02 (census) + EXP-M5-05 (fork). The divergence is concentrated in a small set of
**length-rule** changes plus a few new/relocated leaders, in the low-nibble byte0 families `_6 _e _0 _f _7`
(high nibble = dst register):
- **`n3_mov` and other multi-word ops** — length rules changed on G17g (the top delta lever; the A18
  length under/over-counted on M5). Fixed in the fork's `instr_length`.
- **The `0xNe` byte0 column** (`0x3e/0x5e/0x7e/0x9e/0xbe/0xde/0xfe/0xae`) — a generational format change;
  re-lengthed/added on G17g.
- **`0xb7`** — a leader the A18 DB never resolves; new/relocated on G17g.
- **Memory access is SPLIT on M5** (HW-splice-validated, EXP-M5-07): A18's monolithic 14-byte
  `device_load`(0x67)/`device_store`(0xe7) becomes **three ops** — an ADDRESS-GEN op (`?f <slot<<2> 03
  <idxmode>`, 4B), a LOAD (`0x18/0x38/0x58/0x78` = 1/2/3/4-component, 10B/4B), and a STORE (`0x01/0x21/0x41/
  0x61` = 1/2/3/4-component, 4B/6B). base-slot / index-mode / element-size / store-format fields are all
  splice-proven; LOAD-vs-STORE is distinct opcodes, not a direction bit. (This corrected the census guesses:
  the "0x41 store" was a load *tail*, "0x78 typed" was vec4 *load*.) See EXP-M5-07 for the field maps.
- **Matrix / neural (HW-validated, EXP-M5-09 — marquee):** the matrix path **SPLITS** on M5. Unlike A18
  (everything → `0xcf`), `simdgroup_matrix` MAC emits **zero `0xcf`** — it lowers to a low-nibble-`0xf` **tile
  load/store family** (`?f ..07..`) plus a **`2f 00 05` MAC** op; only the MPP `tensor_ops::matmul2d` path
  keeps `0xcf`. **There is NO new dedicated "neural" ISA leader** — the Apple10 Neural Accelerator rides the
  existing matrix family, not a new opcode. (Op identity splice-proven; full 8×8 operand packing is splice-TODO.)
- **Ray tracing (EXP-M5-09):** `rt_intersect` (byte0 low-nibble `0x4` + byte+1 `0xea`) **transfers unchanged
  from A18** (traverse + result-read, 2×/kernel; inline query too). `rt_as_load`/`ray_mem` no longer distinct
  leaders — migrated into the M5 memory family; **exact AS-load encoding OPEN**.
- **Atomics + subgroup/quad (EXP-M5-09):** UNIFIED reduction selector `2f 00 <scope> 0a 27 80 <OP> 02 <mode>`
  — byte+6 OP (`a0`and/`a1`or/`a2`xor/`a3`add/`a6`min/`a7`max/`ac`float-add), byte+2 scope, byte+9 reduce/scan;
  shuffle = `2f 00 21`. **Texture (EXP-M5-09):** sample family = byte0 low-nibble `0xf` + byte+2 (`0x12`
  sample-class / `0x1a` read). (These are documented; their DB descriptors are the next integration wave —
  they need length disambiguation in the overloaded `0x2f`/`0x0f` space.)
- **INTEGRATED into `db.json` (EXP-M5-11, HW-validated):** the M5 op-selector families are now emittable
  descriptors — **`m5_reduce`** (10B, subgroup/quad reduce+scan + device-atomic-on-uniform; op byte+6
  a0/a1/a2/a3/a6/a7/ac, scope byte+2, mode byte+9), **`m5_shuffle`** (10B, `2f 00 21`), **`m5_alu`** (12B,
  general compute ALU byte0=0x27, op byte+6 hi-nibble 0xa), **`m5_iadd`** (12B, split-memory index add). The
  split-memory field maps are resolved: **m5_load byte+5 = index register** (splice-proven), the `a[i+k]`
  immediate offset is **folded into a preceding `m5_alu` add** (no offset field — a negative vs A18), and the
  store/load **data register is implicit/positional**. `0x67`/`0xe7` (A18 device_load/store) **still occur on
  M5** alongside the split model; A18 atomics migrated to `m5_reduce`.
- **Still open:** matrix MAC/tile operand packing + length; texture sample lengths (a regressing length variant
  was reverted per the no-regression gate — leader/op-class documented); call ABI `0xef/0xff` (needs
  pipeline-`linkedFunctions` extraction — the standalone archive yields a link-time stub); RT AS-load (migrated
  off `0xdf` into the memory family — needs an AS-bound splice testbed); `m5_alu` operand bit-packing (raw).

## Status & provenance
- **Tokenization + op families:** DB = **180 descriptors**; byte coverage **97.4% (own) / 98.4% (tp)**, named
  **93.4% / 95.5%**, round-trip green, 0 hangs (EXP-M5-05 + EXP-M5-11).
- Everything is HW-grounded: own-shader compile→extract→disassemble, validated against 842 own + 3095
  third-party real programs, and (for changed encodings) splice-and-observe on the live M5.
- Residual undecoded tail: own 2.60% / tp 1.61%. Remaining named-but-raw fields (operand packing of the
  unified-op families) are marked raw per clean-room rule 5 rather than guessed.
