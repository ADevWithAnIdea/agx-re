# EXP-M5-17 — M5 texture SAMPLE + READ operand mapping (closes OBJ-1 blocker B-1)

**Device:** Apple M5 / G17g / T8142. **Method:** clean-room splice-and-observe via `agxrender2` (fragment→pixel)
on OUR OWN compiled MSL. Every field = an observed PIXEL delta, not inference. No Apple binary inspected.

## VERDICT: texture SAMPLE + READ are now EMITTABLE — OBJ-1 blocker B-1 CLOSED.
A driver knows the exact byte for every operand it must place: coordinate register, texture slot, sampler slot,
LOD/bias immediate — each pixel-proven. Only the descriptor-**bank** nibble (byte+4) for dense slot≥2 and the
coordinate scoreboard token (byte+7, proven inert) stay raw (rule 5).

## Emittable byte map (canonical fragment sample, 22B; DB tokenizes the 6-byte leader)
```
off0  Rf  low-nibble 0xf = tex op; HIGH nibble = RESULT reg
off1  06  op: 04 explicit-LOD / 05 bias|compare / 06 implicit|gather / 07 register-LOD
off2  16  class: 12 compute-sample / 16 FRAGMENT sample / 1a image-read
off3  00  *** COORDINATE REGISTER (reg32<<1; float2 → +0x04) ***           splice RED→BLUE
off4  41  texture/sampler descriptor-bank word (low nibble present/array/MSAA)  partly raw
off5  80  *** byte+5[6:0] = SAMPLER SLOT ***  bit7 = last/scoreboard        splice BLUE→RED
off6  60  *** TEXTURE SLOT (slot0=0x60, +0x08/slot) ***                     splice RED→GREEN
off7  29  coordinate scoreboard token (splice-proven INERT)                 splice = no-op
off8-11 01 18 01 00 (off9 = 18 implicit-LOD / 00 explicit)
off12 00  *** LOD/BIAS immediate = round(level*0x40) ***                    splice RED→BLUE(mip)
off13-21 gradient/pad
```
Image read (8B): `Rf 06 1a <coord> 40 80 60 <sb>` (off3=int coord reg, off6=tex slot). Gather = 14B.

## Per-field HW evidence (dual-sample kernels defeat DCE; splice output op → pixel flip)
| field | byte | splice | pixel | conclusion |
|---|---|---|---|---|
| coord reg | +3 | 00→04 | RED→BLUE | coordinate register |
| coord ctl | +7 | 29→49 | no change | inert scoreboard |
| tex slot | +6 | 60→68 | RED→GREEN | texture slot (unbound slot1 → contained CMDBUF_ERROR) |
| samp slot | +5 | 00→01 | BLUE→RED (clamp vs repeat) | sampler slot [6:0] |
| LOD imm | +12 | 00→40 | RED→BLUE (mip L→L+1) | LOD = round(level·64) |
Scale (byte-diff multi-resource): coord reg32<<1 {00,04,08}; sampler dense [6:0] 0..3; texture +0x08/slot (slot≥2
also bumps +4 bank); LOD 00/40/80.

## Key correction vs EXP-M5-16
The old gate only accepted `byte+2∈{0x12,0x1a}` / result reg 0-1. **Fragment samples use `byte+2==0x16` and ANY
result register** — the most common texture op was unrecognized. Gate widened to low-nibble-0xf byte0 / byte+1∈
{04,05,06,07} / byte+2∈{12,16,1a}; the disjoint tight tail (byte+4 hi-nibble 0x4 AND byte+5==0x80) unchanged.
byte+3 was mislabeled "operand descriptor" — it is the coordinate register.

## Validation — NON-REGRESSING
Census FLAT both corpora (own 93.43% named / 97.41% cov, tp 95.51% / 98.41%; zero new desync). Round-trip ALL PASS.
db.json → **189 descriptors** (`m5_tex` ×2: 0x12 compute + 0x16 fragment). Zero hangs (one intentional bad splice
faulted, contained, next dispatch fine). Kept the tight `byte+5==0x80` tail (relaxing risks mis-lengthing for no gain).

## Resolved vs raw
- **Resolved (pixel-validated):** coord reg (+3), texture slot (+6), sampler slot (+5[6:0]), LOD/bias (+12), op
  sub-class (+1), class (+2), result reg (byte0 hi), implicit-vs-explicit-LOD (+9); per-variant lengths (22/14/8).
- **Raw (rule 5, honest):** descriptor-bank nibble (+4) for dense slot≥2 (slots 0/1 mapped; higher slots co-vary
  the bank — argument-buffer/binding-table addressing, out of scope); coord scoreboard (+7, inert); gradient/pad (+13..).

## Tooling
`kernels/agxrender2.m` extends `agxrender` (2×2 texture / 2nd texture / 2nd sampler / mipmap / address-mode
binding) — a reusable render-splice testbed; candidate for promotion to `tools/agxtest/`.

## Clean-room attestation
Every byte inspected/spliced is our own on-device-compiled MSL; every field = a pixel delta observed on real HW
with our own agxrender2 + agxparse. No Apple binary disassembled/introspected; no compiler sequence lifted;
unresolved bits raw. Validated non-regressing before delivery.
