# agx-isa — clean-room A18 Pro (G17P) AGX instruction database + assembler + disassembler

The A18 counterpart to dougallj/applegpu: a **machine-readable instruction
database** for the Apple A18 Pro (G17P) shader ISA, with a table-driven
**assembler** (fields → bytes) and **disassembler** (bytes → mnemonic+fields),
plus a **round-trip test**. One table (`isadb.py::DB`) drives both directions.

**Clean-room:** every encoding here was learned from the compiled form of MSL
**we wrote** (OWN-SHADER) — by byte-diffing our own shaders and by splicing
bytes and running them on the real GPU (hardware validation). No Apple binary
was ever disassembled or introspected. The *shape* of the table (match bits +
typed bit-fields + per-instruction size) reuses the design of the public MIT
applegpu database; the *contents* are ours, populated from scratch for G17P
(a different ISA from G13/G14 — the public G13 decoder produces nonsense on our
bytes, EXP-0001).

## Files

| file | role |
|---|---|
| `isadb.py` | the database (`DB`), the instruction-length rule (`instr_length`), and the generic table-driven codec (`decode_one`, `disassemble`, `assemble`, `assemble_op`). Run `python3 isadb.py` for a summary, `--json` for the machine-readable dump. |
| `agxisa.py` | CLI: `tokenize <hex>`, `disasm <hex>`, `asm <mnem> k=v...`, `json`. |
| `roundtrip_test.py` | proves `asm(disasm(b))==b`, `disasm(asm(x))==x`, and clean tokenization of whole real `_agc.main` programs. |
| `db.json` | generated machine-readable export of the DB + length rule. |

## Schema (each instruction descriptor)

```
{ "mnemonic", "length"(bytes),
  "match":  [(bit_start, bit_width, value), ...],   # constant identifying bits
  "fields": [ {"name","start","width","type":reg|imm|enum|mod|opcode|raw,"enum"?}, ... ],
  "semantics", "provenance" }
```
Bit numbering: an N-byte instruction is one little-endian integer; bit 0 = bit 0
of byte 0 (offset +0), bit 16 = bit 0 of byte 2 (offset +2), etc.

## Instruction-length rule (G17P, EXP-0005)

Parcels are 2 bytes (all lengths even). **Unlike G13, the first parcel does NOT
encode length on G17P** — `fsub`=`09 01 1c…` (6B) and `fma`=`09 01 1e…` (8B)
share the identical first parcel yet differ in length. Length is a function of
byte 0 (the format/group) plus — for the float-ALU group only — a length bit at
byte +2 bit 1. Observed table (all validated by clean tokenization of our own
shaders):

| byte0 | group | length |
|---|---|---|
| `0x0e` | stop/end | 4 |
| low nibble `0xC` (`0x0C`/`0x1C`) | preamble (get_sr-like) | 4 |
| low nibble `0x7` (`0x67`/`0xE7`) | device load / store | 14 |
| `0x09` | float ALU | **6**, or **8** if `(byte[+2] & 0x02)` (fma) |
| `0x0b` | float unary (fmov/neg/abs) | 10 |
| `0x12` | float min/max | 6 |
| `0x9f` | integer ALU | 10/12 — **not solved (follow-up)** |

## Op-select field (float 2-source ALU, HW-VALIDATED, EXP-0005)

The operation select is the **low 3 bits of the byte at instruction offset +2**
= instruction bits **[16:19]**: `0b100`=fadd, `0b101`=fmul (bit 0 = add/mul, the
originally-validated bit; bit 1 = the length/fma bit; bit 2 = arithmetic-enable).
Bits 3-5 are don't-care for the operation; bits 6-7 select a srcA-passthrough
mode; `0b111` is an illegal op (contained GPU fault). See
`../../experiments/EXP-0005-float-alu-isa/`.

## Use

```sh
python3 agxisa.py tokenize 1ca01006...    # split a raw _agc.main into instructions
python3 agxisa.py disasm   09051c0100c0   # -> falu2 [fadd] dst=.. opsel=0x4 ..
python3 agxisa.py asm      fadd srcA=1 srcB=0
python3 roundtrip_test.py                 # ALL PASS
```

Status: 8 instruction descriptors; **1 HW-validated** (`falu2`: fadd/fmul).
The rest are inferred (byte-diff) or structural — see each descriptor's
`provenance` and `../../PROVENANCE.md`.
