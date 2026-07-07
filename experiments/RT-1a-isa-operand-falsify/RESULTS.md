# RT-1a RESULTS — falsification of ISA operand encodings + D4

All results are **HW-validated** (spliced bytes run on the real A18 Pro GPU). Values below are
verbatim runtime outputs. Raw logs in `raw/`.

## Verdict summary

| # | Claim under test | Verdict |
|---|---|---|
| D4 | memory-op index register byte offset | **DISCREPANCY — both docs wrong; index reg = byte+5** |
| 2a | falu2 srcA_reg [9:16], srcB_reg [25:32], size bit (both operands) | **CONFIRMED** |
| 2b | falu2 srcB immediate-mode (bit39), srcB negate (bit43), negate+imm combined | **CONFIRMED** |
| 2c | iadd2 dst = byte+3 | **CONFIRMED** |
| 2d | iadd2 byte+0 bit7 = "srcA-negate" | **DISCREPANCY — inverted: 0x9f=add, 0x1f=subtract** |
| 2e | float uniform-source select (byte+2 bit4 / byte+5 bit1) | **DISCREPANCY — mis-decoded as a falu2i immediate** |
| 3 | packed minifloat `[exp:4][mant:3][flag:1]`, sign@bit19 | **CONFIRMED across full documented range** |
| 4a | icmpsel condition codes byte+6 (f/u/s × lt/gt, eq) | **CONFIRMED (all codes)** |
| 4b | icmpsel cmpmode byte+4 (0x22 relational / 0x26 equality), negate byte+5+9 | **CONFIRMED** |
| 4c | ilogic 2-input LUT = all 16 boolean functions | **CONFIRMED (16/16 reachable)** |
| 5 | large kernel tokenizes to 0 leftover, disasm matches | **DISCREPANCY — ~84% coverage, not 0 leftover; gaps listed** |

---

## D4 (priority): memory-op (`0x67`/`0xe7`) index register — RESOLVED

**Contradiction:** `docs/isa/README.md` (EXP-0012 memory table) says the index register is in
**byte+1** ("higher bits = index GPR"); `docs/isa/encoding-tables.md` labels **byte+6 = `addr_lo`**
(implying byte+6/+7 hold the address).

**Truth (HW splice, `bank.metal`, `idx3.metal`): the index register is byte+5. BOTH docs are wrong.**

- **byte+6 (`addr_lo`) is INERT.** Sweeping byte+6 across 0x00–0xFF never changes the loaded index
  (out0 constant). byte+6 is not the address low byte — it is a fixed/padding byte. Three different
  loads/stores that use *different* index registers (r0, i0-reg, gid) all carry byte+6=`0x20`; two
  stores that use the *same* index (gid) carry byte+6=`0x20` and `0x21`. → not an address field.
- **byte+1 is the address-SPACE selector, NOT the index GPR.** Sweeping byte+1 only toggles out0
  between the real value and 0 (bit1=`0x02` selects threadgroup / uninitialized space); it never
  selects among the candidate index registers. README's "higher bits = index GPR" is false.
- **byte+5 selects the index register (HW-proven).** With `a[j]=100*j+3` and idxbuf `{40,3,77,12}`,
  sweeping the `a[i0]`-load byte+5 gives:
  `0x00→a[40]=4003, 0x01→a[3]=303, 0x02→a[77]=7703, 0x03→a[12]=1203` — i.e. it reads the *contents*
  of GPR r0/r1/r2/r3 (=i0/i1/i2/i3) as the index. In `idx3.metal` (`out=a[gid*3]`, grid=8, identity
  `a`): byte+5=`0x00`→r0=gid*3 → `[0,3,6,9,…]`; byte+5=`0x01`→r1=gid → `[0,1,2,3,4,5,6,7]`. Definitive.

**Bonus discrepancy — byte+5 is mislabeled "count" (vector width) in BOTH docs.** byte+5 is the
index register. The apparent `count=1,2,3,4` for `uint1..uint4` `a[gid]` loads is a **confound**:
the N-word vector destination occupies r0..r(N-1) so `gid` lands at rN, and byte+5 = N is the
index-register number, not the width. Proof it is not count: the *scalar* `bank`/`idx3` loads have
byte+5=`0x80` (a scalar's count is 1, not 128) yet run correctly reading one word, and sweeping
byte+5 selects registers. The true vector-width/count lives in the byte+8/byte+12 region
(dst_width `0x51/59/5d/57`, elem_size `0x46/48/40/40` for N=1/2/3/4) — exact field a follow-up.

**Bonus discrepancy — there IS an in-instruction immediate index offset**, contradicting README's
"element addressing, NO immediate offset". Sweeping byte+10 gives `a[i0 + 2·v]` (e.g. idxbuf i0=40 →
`0x01→a[42], 0x02→a[44], 0x03→a[46]`); byte+11 adds `512·v`; byte+9 bit7 adds 1. So bytes ~+9bit7/+10/+11
are an additive element-offset field. The compiler leaves it 0 (it adds offsets via a prior ALU op,
as documented), but the hardware field exists.

Raw: `raw/D4_index_register.log`, and the `mapload.py` per-byte classification in the transcript.

---

## Item 2 — float/int ALU operand fields (adversarial)

### falu2 (float 2-source) — CONFIRMED
Clean bank `falubank2.metal`, exposed `99 09 04 0b 00 c0` = r4+r5 (p.x+p.y), v=[10..80]:
- **srcA_reg = byte+1[1:8], srcB_reg = byte+3[1:8], encoding (reg<<1)|size — CONFIRMED.** Sweeping
  srcA byte+1 = `0x09/0b/0d/0f` reads r4/r5/r6/r7 = 10/20/30/40; srcB byte+3 same. Field reaches the
  register file; r8+ read 0 only because they were unused in this kernel.
- **Size bit (bit0) on BOTH operands — CONFIRMED.** Even byte+1/byte+3 (size=0, 16-bit) reads the
  **low halfword**: a 16-bit read of 10.0 (`0x41200000`) returns low half `0x0000` = 0.0 (out=20).
- **srcB negate (bit43 = byte+5 bit3) — CONFIRMED.** 10+20=30 → splice byte+5 `0xc0→0xc8` → −10 (10−20).
- **srcB immediate-mode (bit39 = byte+4 bit7) — CONFIRMED.** Setting byte+4 bit7 switches to the
  falu2i layout (srcA moves to byte+3, immediate at byte+1).
- **negate + immediate combined — CONFIRMED.** `cadd` (a+1.0), splice negate byte+5 bit3 → out=−9 =
  −a+K (negates the register operand in immediate mode). Functional.

### iadd2 (integer 2-source)
- **dst = byte+3 — CONFIRMED.** `iaddbank` exposed iadd2 @+0x34; splicing byte+3 redirects the result
  to another GPR → the store reads a stale reg → out=0.
- **byte+0 bit7 = "srcA-negate" — DISCREPANCY (inverted polarity).** The compiler emits **`0x9f` for a
  plain ADD** (`p.x+p.y`, out=30) and **`0x1f` for a SUBTRACT** (`p.x−p.y`, out=−10). Splicing an add's
  byte+0 `0x9f→0x1f` turns 10+20 into 10−20 = 4294967286 (−10). The DB's canonical `iadd2` matches
  `[0:7]==0x1f` with `srcA_neg=0` and semantics `d = srcA+srcB` — but on hardware `0x1f` (srcA_neg=0)
  **subtracts**, and `0x9f` (srcA_neg=1) is the plain add. So the DB's srcA_neg field reads backward:
  it labels every real ADD as "srcA_neg=1" and every real SUB as "srcA_neg=0", and its `iadd2`
  semantic string is wrong for `0x1f`.
- The srcA/srcB register operands are packed across byte+6..+9 in a non-obvious way (DB already marks
  these "exact widths a follow-up"); sweeps confirm byte+7/+9 participate in the source selection but
  the exact bit layout was not fully decoded here (matches the DB's "inferred" flag).

### High registers r0..r95 — CONFIRMED (semantics)
`hireg80.metal` keeps **80 distinct live ints** simultaneously and computes a fixed expression over
all of them: GPU output **36304** == CPU reference **36304** (and `hireg.metal`, 40 live, 1136==1136).
Correct results with 80 simultaneously-live values exercise the register file well past r15/r63, so
the wide (7-bit) source fields and the 96-GPR file address high registers correctly.

### Uniform-vs-GPR select — DISCREPANCY (DB mis-decodes uniform as immediate)
`uni.metal` = `a[gid] + p.k` (p.k a scalar `constant&` uniform). Compiles to **`09 0d 14 01 80 c0`**,
byte-identical to `a+1.0`'s **`09 b1 14 01 80 c0`** *except byte+1* (0x0d vs 0xb1). Runtime: a=10,
p.k=7 → **17**; p.k=100 → **110** — it adds the *uniform register value*, not an immediate. But the DB
decodes this instruction as `falu2i [fadd]` with byte+1 as a packed minifloat → it reports
`a + imm_decode(0x0d) ≈ a + 0.00085`. So **the DB mis-renders every `GPR + uniform` float add as an
immediate add** (wrong operand, wrong value). The distinguishing signal is byte+4 bit7 (=bit39, the
DB's "srcB immediate") being set for *both* immediate and uniform sources, with byte+1 carrying either
a minifloat (large exponent) or a uniform-register index (small exponent). The DB's documented guess
("float uniform-select ~ byte+2 bit4 / byte+5 bit1") is not the mechanism. Raw: `raw/item2_5_summary.log`.

---

## Item 3 — packed minifloat immediate — CONFIRMED (full range)

`minifloat_verify.py`: a=0 so out=K; swept byte+1 across 0x00–0xFF for both signs (512 points),
compared to the DB `imm_decode`.
- **Every value in the documented representable range (exponent field e≥8, flag bit=1) matches the
  hardware exactly — 0 discrepancies.** Boundary cases verified: `0xb1→1.0`, `0xc1→2.0`, `0xb9→1.5`,
  `0xcd→3.5`, `0x85→0.0625` (subnormal, e=8), `0xff→30.0` (max), and negatives (sign@bit19).
- The only mismatches are **outside the documented encoding**: e<8 → HW returns 0 (these bytes are
  not immediates — see below), and flag bit=0 (undefined). The DB's `imm_decode()` is unguarded and
  extrapolates a bogus nonzero value for e<8, but it never *claims* that range. → Formula CONFIRMED;
  minor robustness note: guard `imm_decode` to its e≥8 domain.
- **Cross-link:** the e<8 "returns 0" region is actually the **uniform-register-index** overload (see
  item 2 uniform result) — with a uniform bound, byte+1=0x0d (e=0) reads uniform reg=7. In `cadd`
  (no uniform bound) those regs read 0. So this is not a formula error, it's a field overload the DB
  doesn't model. Raw: `raw/item3_minifloat.log`.

---

## Item 4 — compare condition codes + bitwise LUT — CONFIRMED

### icmpsel (0x12) condition codes byte+6 — all correct
Int pairs `(3,5)(5,3)(5,5)(-1,1)(1,-1)(-5,-5)`, each code produces its distinguishing pattern:
`0x04=u_gt [0,1,0,1,0,0]`, `0x05=u_lt [1,0,0,0,1,0]`, `0x06=s_gt [0,1,0,0,1,0]`, `0x07=s_lt [1,0,0,1,0,0]`.
Float pairs incl. NaN: `0x02=f_gt`, `0x03=f_lt` (NaN→false), `0x00=f_eq` (in equality mode). No
mislabeled code.

### cmpmode byte+4 + negate — correct
`0x22` = relational; `0x26` = adds equality (f_gt→f_ge, f_lt→f_le, f_eq exact). Result-negate =
byte+5 bit0 **and** byte+9 bit0 flipped **together**: on f_lt `[1,0,0,1,0,0]`, byte+5=0x80 & byte+9=0x81
→ f_ge `[0,1,1,0,1,1]` (individually they force all-0 / all-1, i.e. they are the select's 0/1
operands; both flipped = negation). The compiler itself emits `>=` as f_gt(0x02)+equality(0x26).

### ilogic (0x0b) 2-input LUT — all 16 boolean functions reachable
`lut_combo.py` with a=0xC,b=0xA (so `out&0xF` = the 4-bit truth table): sweeping op_base
byte+2∈{0x1e xor-base, 0x1f and/or-base} × invert byte+4 × byte+5 bit3 reaches **16/16** functions
(FALSE,NOR,andn,~a,~b,XOR,NAND,AND,XNOR,a,b,orn,OR,TRUE,…). op_base bit0 and the byte+4/byte+5 inverts
match the DB description. Raw: `raw/item4_lut.log`.

---

## Item 5 — large-program stress + DB mis-decodes

`big.metal` (mixed fp16/fp32/int/int64, deep nested trees, broad ALU coverage, high pressure) → 980 B
`_agc.main`. Plain `agxisa.py tokenize` **fails** (halts, dumps the whole body as leftover). Resync
census (`census1.py`): **83.7% byte coverage**, 16.3% undecoded — consistent with the docs' honest
"~88%" but **NOT the "0 leftover" the DB README implies** for real shaders. `hireg80` (1788 B) = 82.3%.
Semantics where fully referenceable were correct (hireg 1136==1136, hireg80 36304==36304).

**DB mis-decodes found (report):**
1. **byte0=`0x60`** — instruction-aligned right after the entry `get_sr` in high-pressure/spilling
   kernels (`big.bin`: `8c a0 91 06 | 60 00 00 00 | 9f 11 54 …`). The DB has **no length rule** for
   0x60 → `instr_length` returns None → tokenization **halts** (and desyncs the resync census). Known
   as a "residual leader" in prior census but here it is clearly aligned and load-bearing (spill/frame
   setup). Undecoded.
2. **byte0=0x09 (falu group) with byte+2=`0x18`** — the compact float-accumulate variant
   (`19 0b 18 09` in `falubank.bin`). `instr_length` returns 4 (byte+2∈{0x18,0x38}) but **no DB
   descriptor matches byte+2=0x18** (`falu_acc` requires byte+2==0x38) → `decode_one` raises → the
   tokenizer reports "no descriptor matches" and dumps the remaining 40 bytes as leftover. A real
   compute op (part of an `a2+a3+…` reduction) the DB cannot decode.
3. **Uniform-source float add mis-rendered as a falu2i immediate** (see item 2e) — every `GPR+uniform`
   add disassembles as `a + <bogus tiny immediate>`.
4. **iadd2 add/sub mislabel** (see item 2d) — `srcA_neg` reads inverted; real adds shown as
   `srcA_neg=1`, real subtracts as `srcA_neg=0`.

Raw: `raw/item5_big_census.log`, `raw/item2_5_summary.log`.

---

## Bottom line for the orchestrator (central fixes)
- **D4:** memory-op index register = **byte+5**, not byte+1 (README) and not byte+6 (encoding-tables).
  byte+1 = address space; byte+6 = inert. Also: byte+5 is currently mislabeled "count" — count/width is
  in the byte+8/+12 region; and a real immediate index-offset field exists at ~byte+9bit7/+10/+11.
- **iadd2:** flip the `srcA_neg` polarity / semantics (0x9f=add, 0x1f=subtract).
- **Uniform floats:** add a uniform-source form to `falu2` so `GPR+uniform` stops decoding as an
  immediate; the immediate-vs-uniform split is byte+1's exponent range under bit39.
- **DB length/descriptor gaps:** add byte0=0x60, and the byte+2=0x18 compact-accumulate descriptor.
- **Confirmed & strengthened:** falu2 operand fields (incl. r95, both size bits, negate+imm),
  the packed minifloat formula (full documented range), the compare condition-code table + cmpmode +
  negate, and the 16-function bitwise LUT.
