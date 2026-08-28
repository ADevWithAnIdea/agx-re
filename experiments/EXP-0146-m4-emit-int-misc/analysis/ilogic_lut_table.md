# `ilogic` — the complete 2-input boolean LUT encoding (EXP-0146, M4/G16G)

**Evidence:** `EXP-0146` arms `B_ilogic` (per-field dense sweeps) and `B2_ilogic_lut2d`
(`lut_a` 0..15 x `lut_b` 0..15 x `op_base` 0..1). Carrier: `kernels/k_logic_and.metal`, whose
only ALU instruction is the `ilogic` at `_agc.main+0x20` and whose result is stored directly.
Both gated runs (`run01`, `run03`) had to agree case-for-case; disagreements were adjudicated
5x serially in `run04` and are excluded from this table.

**How the function was read off, not guessed.** Each of the 8 dispatched threads carries a
different `(a, b)` 32-bit pair, and every pair covers all four `(bit_a, bit_b)` combinations
(asserted in `harness/oracles.py::_assert_covering`). The realized truth table is therefore
recovered bit-exactly from one output word per row and cross-checked across all 8 rows
(`harness/oracles.py::derive_lut2` returns `None` if the output is not a consistent bitwise
function of `(a, b)` — that check never had to be waived for a promoted row).

**Result: all 16 two-input boolean functions are reachable from the `ilogic` instruction
alone.** This refines EXP-0102's `INT-12` verdict, which reported 10 of 16 — that was a
statement about what MSL *source* provokes the compiler to emit, not about the encoding.

**Minimal selector:** `(op_base, lut_a & 3, lut_b & 0x0f)` determines the function with
**zero collisions** over the whole agreed map. `lut_a` bits 2-4 are don't-care and bits 5-7
must be clear; `lut_b` bits 5-7 are don't-care.

| # | function | truth table (aa,ab,ba,bb) | `op_base` | `lut_a` | `lut_b` | agreed encodings |
|---:|---|---|---:|---:|---:|---:|
| 0 | `0` | `0000` | 0 | `0x00` | `0x00` | 150 |
| 1 | `and` | `0001` | 1 | `0x00` | `0x00` | 8 |
| 2 | `a_and_not_b` | `0010` | 0 | `0x00` | `0x08` | 4 |
| 3 | `a` | `0011` | 0 | `0x00` | `0x09` | 12 |
| 4 | `not_a_and_b` | `0100` | 0 | `0x02` | `0x00` | 3 |
| 5 | `b` | `0101` | 0 | `0x02` | `0x02` | 43 |
| 6 | `xor` | `0110` | 0 | `0x02` | `0x08` | 3 |
| 7 | `or` | `0111` | 1 | `0x02` | `0x08` | 4 |
| 8 | `nor` | `1000` | 0 | `0x01` | `0x00` | 4 |
| 9 | `xnor` | `1001` | 1 | `0x01` | `0x00` | 4 |
| 10 | `not_b` | `1010` | 0 | `0x01` | `0x02` | 45 |
| 11 | `a_or_not_b` | `1011` | 1 | `0x01` | `0x08` | 3 |
| 12 | `not_a` | `1100` | 0 | `0x01` | `0x01` | 11 |
| 13 | `not_a_or_b` | `1101` | 1 | `0x03` | `0x00` | 4 |
| 14 | `nand` | `1110` | 0 | `0x03` | `0x08` | 2 |
| 15 | `1` | `1111` | 0 | `0x01` | `0x05` | 118 |

Every row above is one concrete encoding that **executed on the M4 and produced exactly that
boolean function** in both gated runs. The `agreed encodings` column counts how many distinct
`(op_base, lut_a, lut_b)` triples in the swept 2-D subspace produced that function.

## Emitting `ilogic`

Take the carrier instruction `0b 05 1f 01 00 00 00 80 00 00` and set, from the table above:
`op_base` = byte+2 bit 0, `lut_a` = byte+4, `lut_b` = byte+5. The rest of the fields, all
hardware-run in `analysis/field_verdicts.json`:

- byte+1 `srcA`, byte+3 `srcB` — source-operand descriptors, `(reg<<1)|is32`; **bit 7 is inert**.
  248 of 256 values SILENTLY ZERO the result, which is the canonical Apple9 wrong-operand
  failure mode — get these right or fail quietly.
- byte+7 `outmod` — only bit 7 is load-bearing (`0x80` = publish the result); every value with
  bit 7 clear silently zeroes. Bits 0-6 don't-care.
- bytes +6, +8, +9 (`z6`, `z8`, `z9`) — **HW-tested inert over all 256 values each**.
- byte0 must be `0x0b`; `0x0a` faults the command buffer (pre-registered falsifier F2).
