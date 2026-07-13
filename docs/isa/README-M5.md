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
- Memory (`0x18` load, `0x41`/`0xc1` store), typed/sample (`0x78/0x58/0x50`), call (`0xef/0xff`) — length
  resolved; **per-field semantics are HW-splice-validated in the EXP-M5-07 wave** (in progress).

## Status & provenance
- **Tokenization (leader+length):** DONE — 96.6%/98.0% byte coverage, round-trip green, 0 hangs (EXP-M5-05).
- **Semantics of M5-specific ops:** in progress via splice-and-observe on the M5 (EXP-M5-07); ops inherited
  unchanged from the A18 carry the A18 semantics (spot-checked on M5).
- Everything is HW-grounded: own-shader compile→extract→disassemble, validated against 842 own + 3095
  third-party real programs, and (for changed encodings) splice-and-observe on the live M5.
- Residual undecoded tail: own 3.45% / tp 2.02% (characterized in EXP-M5-05 report).
