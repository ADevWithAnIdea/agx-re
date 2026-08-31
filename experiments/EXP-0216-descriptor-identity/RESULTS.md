# EXP-0216 — RESULTS

```
Clean-room provenance: derived analysis of already-committed artifacts in this repository.
Device contacted:      NONE. EXP-0213 held the A18 Pro for quiet Gate E confirmations.
Apple binary read:     NONE.  Shader compiled: NONE.  Raw files written: NONE.
Inputs frozen:         work/db_frozen.json         sha256 02a47fc6…  (byte-identical to
                                                    EXP-0215's frozen copy)
                       work/validation_frozen.json sha256 6e7ff3f1…
                       repo HEAD d8b4b63b
Files edited in tools/agx-isa, docs/, PROVENANCE.md:  ZERO.  Labels changed: ZERO.
Committed:             NOTHING.
```

## 0. Headline

**All three questions are decided from the bytes, and the two that were framed as dangerous
are not dangerous.**

* **Q1.** All 22 span disagreements have one mechanical cause: the harnesses read their spans
  from `db.json` **at run time**, and five later commits moved those spans. 21 of 22 sweeps
  moved *exactly* the bits they declared (Gate-A agreement **100 % at the declared span**,
  0.4–4 % at the current one), and **21 of the 22 declared spans are byte-identical to the
  experiment's own `work/frozen/db.json`** (the 22nd experiment ships no frozen copy). Not one is a harness bug. On the harder
  question — *which naming is right* — the register dumps decide **16 of 22**, and
  **6 are genuinely undecidable**, five of them because the match bits and the narrowed field
  *tile* the swept byte.
* **Q2.** **The operand hazard that stopped EXP-0215 does not exist.** Per swept byte,
  `bf_alu`, `bf_add_dst` and `bf_mul_dst` assign **identical** `(start, width)` to every field
  the suspect rows name: byte 3 is `srcA` in all three, byte 4 is `srcB` in all three, bytes
  5–7 are `tail (40,24)` in all three. The premise "byte 3 is `bf_alu.srcA` but
  `bf_add_dst.srcB`/`.tail`" comes from aggregating field counts across bytes 3–7. Same for
  `cvt_f2h`: `b1`/`src`/`b4`/`tail` sit on the same bits as `cvt_f2h_dst`'s
  `srcfmt`/`src`/`dhalf`/`tail`. **No re-attribution is proposed anyway** — because the
  hardware question underneath is a *descriptor over-fit*, not a wrong instruction.
* **Q3.** **The descriptor's match is wrong, and the bytes say exactly how.** `cvt_f2h`'s
  match spends a full 8 bits on byte 0. Its **low nibble — the opcode group — holds on 6 515
  of 6 555 committed encodings**. Only the **high nibble** differs, and that nibble is a
  destination register in every dst-parameterised sibling in this database. EXP-0144 even
  swept byte 0 through `0x11`, and those 5 cases *do* satisfy the match and *do* tokenize as
  `cvt_f2h`. The records are the same instruction with `dst = r0`.
* **And one finding neither EXP-0215 nor the dispatch predicted:** in EXP-0171's own
  bfloat carrier the hardware accepted **eight** byte-2 values with **bit-identical output**,
  and **`isadb._n1_len` can size only one of them**. That is a live **length-rule** defect in
  `isadb.py`, not a `db.json` defect — reported, not patched.

---

## 1. Q1 — the 22 pairs

### 1.1 First, the mechanism: nobody declared a wrong span

`scripts/q1_operand_identity.py` decodes every record's own bits at the span it declares and
at the span `db.json` holds today.

| row | citation | declared | current | n | Gate A @ declared | Gate A @ current |
|---|---|---|---|---:|---:|---:|
| `falu3.srcA` | EXP-0154 | (24,8) | (8,8) | 768 | **768** | 3 |
| `falu3_ext.srcA` | EXP-0154 | (24,8) | (8,8) | 768 | **768** | 3 |
| `imad.srcB` | EXP-0154 | (40,8) | (48,8) | 512 | **512** | 2 |
| `imad.srcC_lo` | EXP-0154 | (48,8) | (40,8) | 512 | **512** | 2 |
| `iminmax.srcA` | EXP-0154 | (24,8) | (8,8) | 512 | **512** | 2 |
| `iminmax.srcB` | EXP-0154 / EXP-0160 | (40,8) | (24,8) | 512 / 1024 | **512 / 1024** | 2 / 4 |
| `mov_zext16.src_reg` | EXP-0161 | (8,7) | (4,4) | 896 | **896** | 7 |
| `mov_zext16.src_flag` | EXP-0161 | (15,1) | (8,8) | 14 | **14** | 7 |
| `mov_zext16.extend` | EXP-0161 | (24,8) | (27,5) | 1792 | **1792** | 7 |
| `fspecial.dst` | EXP-0161 | (12,4) | (24,8) | 64 | **64** | 4 |
| `fspecial.src` | EXP-0161 | (24,8) | (40,8) | 832 | **832** | 4 |
| `fspecial.src_ext` | EXP-0161 | (40,8) | (12,4) | 1024 | **1024** | 4 |
| `iter_at.grp` | EXP-0168 | (0,8) | (7,1) | 71 | **71** | 24 |
| `half_alu.srcA` | EXP-0169 | (24,8) | (8,8) | 512 | **512** | 2 |
| `half_alu.srcB` | EXP-0169 | (32,8) | (24,8) | 512 | **512** | 2 |
| `reg_move_cb.form` | EXP-0169 | (16,8) | (20,4) | 1024 | **1024** | 4 |
| `half_alu_ext8.dst` | EXP-0180 | (8,8) | (4,4) | 2560 | **2560** | 10 |
| `half_alu_ext8.srcA` | EXP-0180 | (24,8) | (8,8) | 2560 | **2560** | 10 |
| `half_alu_fma12.srcA` | EXP-0180 | (24,8) | (8,8) | 1536 | **1536** | 6 |
| `shift_amt_move.kind` | EXP-0154 | (16,8) | (20,4) | 512 | **512** | 2 |
| `half_alu_fma12.ext` | EXP-0203 | (32,64) | (48,48) | 49664 | n/a — byte-wise sweep, `value` is a byte (see §1.5) | |

Then the part that settles the "whose bug is it" question: **each experiment pins its own
`work/frozen/db.json`** (`isa_helpers._find_isadb` prefers it precisely because "the repo
host's `tools/agx-isa/db.json` DRIFTS while sibling experiments extend the ISA"), and the
declared span equals that frozen descriptor in **21 of the 21 rows where a frozen copy
exists**. The 22nd, `iminmax.srcB` ← EXP-0160, ships no frozen copy; its declared (40,8) is
the repo `db.json` value that predates commit `4a54e9bb`. (The four `cvt_f2h` rows carry no
`fstart` at all — they are Q3.) Git confirms the other end — five commits moved these spans
*after* the runs:

```
cf544b4d 2026-08-28  the spans EXP-0154/0161/0168 ran against
d1b00422 2026-08-29  falu3/falu3_ext srcA (24,8) -> (8,8)
4a54e9bb 2026-08-30  fspecial dst/src/src_ext rotated; imad srcB<->srcC_lo; iminmax; mov_zext16
29fb7378 2026-08-30  iter_at.grp; reg_move_cb.form; shift_amt_move.kind
9b8d88f9 2026-08-30  half_alu, half_alu_ext8, half_alu_fma12 srcA/dst
55b307e4 2026-08-30  half_alu_fma12.ext (32,64) -> (48,48)
```

**So EXP-0215's category D is not 22 suspicious citations. It is the exact footprint of five
descriptor repairs, and every one of the underlying observations is intact — it is simply an
observation about a row that has since been renamed.** That is a citation-graph fact, and it
is why EXP-0215 was right to refuse the additions and wrong to file them as "records name the
field but do not carry its current bits" without the second half of the sentence.

### 1.2 The harder question: which naming is right

Gate A cannot answer that; only behaviour can. Two instruments, both already committed:

* **release-on-read** (EXP-0154 H3, positively controlled in its own pilot S3): reading a GPR
  as a 32-bit source zeroes it, so the register that comes back 0 *names the operand the
  descriptor selected*;
* **host arithmetic oracles** that score the rival descriptor versions against the same
  records.

Verdict tally over the 22 (full table: `analysis/q1_verdicts.json`):

| | rows |
|---|---:|
| current db.json **confirmed** by hardware | **7** |
| current db.json **refuted** by hardware | **1** |
| frozen name refuted, current name not confirmed | **7** |
| partitioned cleanly (no adjudication needed) | **1** |
| **undecidable — no detection power in the carrier** | **1** |
| **undecidable — geometry (match bits tile the swept span)** | **5** |

#### `imad` — the "swap" is real, and it fixed nothing

The dispatch named `imad.srcB` / `.srcC_lo` as looking swapped. They are, in `db.json` — and
the hardware says **both names are on multiplicands, so neither placement is right**.

`k_imad`'s lifted block over `SEED_I = {0:10, 1:21, 2:34, …}`, baseline
`9f00560002080060d02e0a00` → `r0 = 341`:

```
byte 5 sweep (declared srcB, now srcC_lo)   reg = value>>2
  v=0..3  -> r0 = 101 = SEED[0]*10 + 1      (r0 is the dst; no release visible)
  v=4..7  -> r0 = 211 = SEED[1]*10 + 1      r1 released
  v=8..11 -> r0 = 341 = SEED[2]*10 + 1      r2 released   <- baseline, `ok`
  v=12..15-> r0 = 471 = SEED[3]*10 + 1      r3 released
byte 6 sweep (declared srcC_lo, now srcB)   reg = value>>3, bit0 kills the product
  v=8     -> r0 = 715 = 34*21 + 1           r1 AND r2 released
  v=16    -> r0 = 1157 = 34*34 + 1
```

`dest = SEED[b5>>2] * SEED[b6>>3] + 1` scores **64/64** and **68/128** in-domain (the other 60
are the bit0-killed cases). Both addend models score **0**. An addend at byte 5 would have
given `340 + SEED[reg]` — 350, 361, 374, 387 — and the observation is 101, 211, 341, 471.

> `srcC_lo` names an addend's low half. Byte 5 is not an addend and byte 6 is not an addend.
> EXP-0165's swap **moved a wrong name from byte 6 to byte 5**. `imad` also has **no `srcA`
> field at all**, and the real addend is elsewhere: byte 7 moves the destination in steps of
> {0, 1, 256, 16256, 46038, 49045} above the unchanged product 340 — none of them a GPR seed —
> and byte 8 gates the addend between 1 (12 of 256 values, all with low nibble 0) and 0
> (240 of 256; 4 values give a non-integer result). Proposal only —
> `analysis/proposed_db_edits.json` P1.

**Which multiplicand is A and which is B is `undecidable` here**, and this experiment does not
guess: multiplication is commutative and the carrier has no non-commutative probe.

#### `fspecial` — the "rotation" is real and it is CORRECT

Three names moved in a cycle at `4a54e9bb`. Two legs are confirmed outright:

```
byte 3  (declared `src`, now `dst`)      RELOCATES THE DESTINATION, index == value>>1, 26/26
        v=0,1 -> r0 keeps 0.5   v=2,3 -> r1 = 0.5   v=4,5 -> r2 = 0.5   v=6,7 -> r3 = 0.5
byte 5  (declared `src_ext`, now `src`)  SELECTS THE SOURCE,      index == value>>2, 56/56
        v=4..7 -> r1 released, dest = rsqrt(9)   = 0.33333343
        v=8,9  -> r2 released, dest = rsqrt(0.25)= 2.0
(12,4)  (declared `dst`, now `src_ext`)  INERT: all 16 values, ONE identical register vector
```

`experiments/EXP-0161-g17p-carry-fspecial/raw/g17p_20260829_run01/sweep.jsonl:6365` and
`:7069`. The third leg is `inert in the EXP-0161 rsqrt carrier; global role unknown` — the old
name `dst` is refuted by elimination (byte 3 is the destination), the new name `src_ext` is
neither confirmed nor refuted.

#### `falu3` / `falu3_ext` / `iminmax` / `half_alu` — the repairs are confirmed

`falu3`'s complete operand map falls out of one host model.
Baseline `09011e05810802c0`, seeds `{0:5.0, 1:1.5, 2:3.0, 3:0.5, 4:7.0, …}`, `r0 = 22.0`:

```
dest = A*B + C     A from byte1, B from byte3, C from byte5     reg = byte>>1
                   bit0 = operand width; a 16-bit read of these exact float seeds is 0
baseline:  5.0 * 3.0 + 7.0 = 22.0                             <- `ok`
byte1 v=3  -> 1.5*3+7 = 11.5    v=5 -> 3*3+7 = 16    v=17 -> 0.25*3+7 = 7.75
byte3 v=1  -> 5*5+7   = 32      v=9 -> 5*7+7  = 42   v=11 -> 5*9+7   = 52
byte5 v=0  -> 5*3+5   = 20      v=2 -> 15+1.5 = 16.5 v=10 -> 15+9    = 24
even v on byte1/byte3 -> that operand contributes 0: dest = 7.0
```

Exact on every in-domain case of every arm (`srcA` 32/32, `srcC` 32/32, `dst` 13/13,
`dst_lo` 13/14). The **frozen** model — `srcB` at byte 4 — is out of domain on *every* record:
byte 4's baseline is `0x81`, i.e. register 64, while the instruction demonstrably computes
from r0, r2 and r4.

The same shape holds for `iminmax` (release map 56/56 at byte 3; `min` model 32/32 for the
current layout against 2/32 for the frozen one) and `half_alu` (release map 26/26 at byte 1
*and* byte 3). In all three, the byte the frozen descriptor called `srcB` — byte 4 or byte 5 —
**selects no register at all**: `half_alu` byte 4 poisons the whole program at v ∈ {2,6,10,…}
and silently writes nothing at v ∈ {3,7,11,…}; `iminmax` byte 5 is correct only at v ∈ {0,8}.
Those two names are **refuted**; their replacements (`ctrl`, `dst_full`) are **not confirmed**
by anything here.

#### `half_alu_fma12` — decided by EXP-0203's own committed oracle

EXP-0203 wrote a host oracle beside every case (`oracle.a/.b/.c/.dst`), independent of any
field name. Decoding the committed `pre` dump with `reg = byte>>1, half = byte&1`:

| model | hits |
|---|---:|
| `a,b,c` from bytes **1, 3, 5** — the current db.json layout | **47 030 / 51 220** |
| `a,b,c` from bytes **3, 4, 5** — EXP-0180's frozen layout | **0 / 51 220** |
| `oracle.dst == byte0 >> 4` | **51 096 / 51 220** |

Worked case, `raw/g17p_run21/sweep.jsonl:16`, bytes `100d06111312000000800100`, layout `HI`:
`byte1=0x0d` → r6 high half `0x4130` = **16688 = oracle.a**; `byte3=0x11` → r8 high half
`0x3E80` = **16000 = oracle.b**; `byte5=0x12` → r9 **low** half `0xB780` = **46976 =
oracle.c**. This is a second experiment and a second method relative to EXP-0180, and it also
establishes the half-group operand encoding: **`reg = byte>>1`, `half = byte&1`**.

#### `mov_zext16.src_reg` — EXP-0197 §4.1 re-derived from registers, not prose

The frozen span (8,7) is **inert across all 128 values in two independent experiments**
(EXP-0154 and EXP-0161: one identical register vector, every case). The current span (4,4) is
byte 0's high nibble, and EXP-0161's `__raw_b0` arm shows what it does:

```
byte0 = 0xN3  ->  register N receives zext16 of ITS OWN pre-value
   N=2: pre 0x0A2C51E7 -> 0x000051E7 (20967)      N=3: pre 0xA7D50B49 -> 0x00000B49 (2889)
   N=4: pre 0x161594AB -> 0x000094AB (38059)      N=1: baseline, `ok`
   N >= 11: nothing is written anywhere in r0..r15
```

**Confirmed** — and with a bonus the descriptor does not model: that nibble is the
**destination as well as the source**, and `mov_zext16` has no `dst` field. Proposal P5.

### 1.3 The five narrowings are undecidable, and that is a geometric fact

`mov_zext16.extend` (24,8)→(27,5), `reg_move_cb.form` and `shift_amt_move.kind`
(16,8)→(20,4), `iter_at.grp` (0,8)→(7,1). The pre-registered test was: *if the narrowing is
right, two encodings that share the sub-span value agree; if it is wrong, they disagree.*

Restricted to match-preserving records (a byte value that breaks the match is no longer this
instruction) and to encodings identical outside the swept span, the answer is the same in
every case: **`max_distinct_encodings_per_group == 1`.** The match bits and the narrowed field
**tile** the swept byte, so exactly one encoding exists per sub-span value and no comparison
is possible.

| row | records | match-preserving | groups | encodings/group |
|---|---:|---:|---:|---:|
| `mov_zext16.extend` (EXP-0154) | 512 | 64 | 32/32 | 1 |
| `mov_zext16.extend` (EXP-0161) | 1792 | 224 | 32/32 | 1 |
| `reg_move_cb.form` | 1024 | 64 | 16/16 | 1 |
| `shift_amt_move.kind` | 512 | 32 | 16/16 | 1 |
| `iter_at.grp` | 71 | 14 | 2/2 | 1 |

The evidence is not lost — **every** match-preserving value of each narrowed field was
dispatched — but the narrowing itself is neither confirmed nor refuted from these records. The
honest status is `UNDECIDABLE-GEOMETRY`, and the match-preserving counts (64 of 512, 224 of
1792, …) are the numbers a re-scored citation should carry, not the raw record counts.

`mov_zext16.src_flag` is the mirror image: a **widening** (15,1)→(8,8). Its 14 records are a
2-point sample of a 256-value field.

### 1.4 One arm has no detection power at all

`half_alu_ext8.dst` and `.srcA` in EXP-0180: two of five arm/run slices produce **one
identical register vector across all 136–256 values**; the rest move but follow no index law.
Per Gate B that is `carrier-undecidable`, not "inert". The `dst` **name** is nevertheless
settled by the same experiment's `__dst_nibble` arm, which relocates the written register with
`index == value`: the register whose index equals the nibble is the one that changes in
**60 of 64** cases (C_HI, and the value written is the single constant 7.05859375) and **56 of
64** (C_LO) — so the destination is byte 0's high
nibble, and the (8,8)→(4,4) repair is confirmed *for that name*. What byte 1 and byte 3 are in
`half_alu_ext8` is **inferred** from the identical layout of `half_alu` and `half_alu_fma12`,
not measured.

### 1.5 `half_alu_fma12.ext` needs no adjudication — it partitions

The declared (32,64) is bytes 4–11; the current (48,48) is bytes 6–11. EXP-0203 swept `ext`
**byte-wise**, so the 49 664 records split exactly by which byte each case perturbed relative
to its own anchor:

| swept byte | records | field that owns it today |
|---|---:|---|
| 4 | 6 630 | `lensel (32,2)` + `mods (34,6)` |
| 5 | 6 120 | `srcC (40,8)` — and §1.2 confirms byte 5 *is* srcC |
| 6, 7, 8, 9, 10, 11 | 6 120 each = **36 720** | `ext (48,48)` |

**36 720 records are still `ext`; 12 750 are a sweep of the two fields EXP-0212 carved out.**
Nothing is misattributed once the split is applied.

---

## 2. Q2 — the two experiments keyed to a mnemonic their bytes do not decode to

### 2.1 The stated hazard is not present

`scripts/q2_sibling.py` computes the span overlay **per swept byte**, which is the test the
dispatch asked for:

| swept byte | records | `bf_alu` | `bf_add_dst` | `bf_mul_dst` |
|---|---:|---|---|---|
| 0 | 520 | *(match)* | `dst (4,4)` | `dst (4,4)` |
| 2 | 2 048 | `opsel (16,8)` | *(match 0x1c)* | *(match 0x1d)* |
| **3** | 2 048 | **`srcA (24,8)`** | **`srcA (24,8)`** | **`srcA (24,8)`** |
| **4** | 2 048 | **`srcB (32,8)`** | **`srcB (32,8)`** | **`srcB (32,8)`** |
| **5, 6, 7** | 2 048 each | **`tail (40,24)`** | **`tail (40,24)`** | **`tail (40,24)`** |

> **Byte 3 is `srcA` under all three descriptors.** The dispatch's premise — "byte 3 is
> `bf_alu.srcA` but `bf_add_dst.srcB`/`.tail`" — comes from EXP-0215's
> `sibling_mnemonics.json`, which counts sibling fields across **all** swept bytes at once
> (bytes 3–7 together produce `srcA 1530, srcB 1536, tail 4608`). Per byte the two readings
> are identical, so on the three suspect rows a re-point could not move a verdict onto a
> different operand even if one were proposed.

A second fact matters more than it looks: **12 808 of these 13 144 records carry
`field: null`.** They are keyed by `byte_index`, not by a field name. The field names in the
suspect list were *derived* by EXP-0215's indexer applying `bf_alu`'s field map to the byte
index — and because the two field maps agree on bytes 3–7, the derivation is the same either
way. The only rows where the two readings genuinely differ are byte 0 (520 records) and byte 2
(2 048 records), and **neither is on the suspect list**.

### 2.2 Which reading the hardware supports

**S-bytes**, decisively, and the failing bits say why:

```
13 144 committed encodings, all 8 bytes long
  0      satisfy bf_alu's match
  7 972  satisfy bf_add_dst           2 652  satisfy bf_mul_dst
  bits[8:+8] want 2 got 0   -> ALL 13 144 records.  G17P emits byte1 == 0x00.
  bits[0:+8] want 17 got 49 -> 12 626 records.      byte0 == 0x31, i.e. dst r3, group 1.
```

Both facts are already written in `db.json`'s own `bf_alu` semantics string (DEF-0171-1,
DEF-0171-2). This experiment supplies the counts. **The instruction that ran is the native
bfloat add/mul; `bf_alu`'s match is over-fit on a destination register and on a byte-1
constant this target never emits.** No re-attribution is proposed: for the three suspect rows
the bits are the same either way, and the honest fix is the descriptor, not the citation.

`cvt_f2h` is the same shape (see §3) and its overlay is also identical on the suspect rows:

| byte | `cvt_f2h` | `cvt_f2h_dst` |
|---|---|---|
| 0 | *(match, all 8 bits)* | `dst (4,4)` + match `(0,4)=1` |
| 1 | `b1 (8,8)` | `srcfmt (8,8)` |
| 2 | `op (16,8)` | `opsel (16,8)` |
| 3 | `src (24,8)` | `src (24,8)` + match `(28,4)=8` |
| 4 | `b4 (32,8)` | `dhalf (32,8)` |
| 5 | `tail (40,8)` | `tail (40,8)` |

### 2.3 The tokenizer defect the dispatch asked about

EXP-0171 swept byte 2 of the native bfloat add through all 256 values in its `NAT` carrier.
**Eight values are accepted by the hardware with bit-identical output words:**

```
byte2  0x04 0x0c 0x14 0x1c 0x24 0x2c 0x34 0x3c   -> outcome `ok`,
       first four output words = 1083195520, 1091584016, 1061176011, 1101021608, identical
byte2  0x1d                                       -> `wrong_value`, a different COHERENT
                                                     result (the multiply)
byte2  0x44, 0x5c, 0x7c (bit 6 or 7 set)          -> silent_zero
byte2  0x1f, 0xff                                 -> fault
```

`experiments/EXP-0171-g17p-ilogic-srca/raw/g17p_20260830_run01/sweep.jsonl:25540` (0x04) vs
`:25564` (0x1c). Bounded wording, per RE_EXPERIMENT_PROCESS_CORRECTIONS §7: **bits 3–5 of
byte 2 are accepted-inert aliases of the bfloat add in the EXP-0171 NAT carrier; global role
unknown.**

Now run those eight encodings through our own tokenizer:

```
310004001100c081 -> ERR unknown instruction length at offset 0 (byte0=0x31)
31000c001100c081 -> ERR unknown instruction length at offset 0 (byte0=0x31)
310014001100c081 -> ERR unknown instruction length at offset 0 (byte0=0x31)
31001c001100c081 -> bf_add_dst  len 8
310024001100c081 -> ERR unknown instruction length at offset 0 (byte0=0x31)
31002c001100c081 -> ERR unknown instruction length at offset 0 (byte0=0x31)
310034001100c081 -> ERR unknown instruction length at offset 0 (byte0=0x31)
31003c001100c081 -> ERR unknown instruction length at offset 0 (byte0=0x31)
```

**7 of the 8 hardware-accepted encodings have no length at all.** `isadb._n1_len` gates the
bfloat branch on `byte2 in (0x1c, 0x1d, 0x1e)`. That is precisely the failure its own
docstring says EXP-0182 fixed for byte 1 — keying the length on a byte that selects an
*operation variant* rather than identifying the instruction — reintroduced one byte over. It
accounts for **2 162 of 13 144** `unknown instruction length` tokenizations in this corpus.

> **This is a defect in `isadb.py`'s length rule, not in `db.json`'s descriptors.** It is
> reported (proposal P4), not patched: the length rule is its owner's file, and today's
> `icmpsel` byte+2 `0x2d` → 10-byte change shows how far a corpus decode shifts when it moves.

---

## 3. Q3 — four `cvt_f2h` citations whose bytes fail its match on all 1 280 records

**The descriptor's `match` is wrong. The records are the same instruction.** The bytes:

| row | records | satisfy `cvt_f2h` | satisfy `cvt_f2h_dst` | byte0 low nibble == 1 |
|---|---:|---:|---:|---:|
| `cvt_f2h.b1` | 1 280 | **0** | **1 280** | **1 280** |
| `cvt_f2h.src` | 1 280 | **0** | 80 | **1 280** |
| `cvt_f2h.b4` | 1 280 | **0** | **1 280** | **1 280** |
| `cvt_f2h.tail` | 1 280 | **0** | **1 280** | **1 280** |
| whole `cvt_f2h`-keyed corpus | 6 555 | 5 | 5 315 | 6 515 |

Every failure is the same single constraint, `bits[0:+8] want 17`, and the dominant observed
value is **`got 1`** — byte 0 = `0x01`. Decomposed:

* **low nibble = 1 on 6 515 of 6 555** — the opcode group is right;
* **high nibble = 0** where the descriptor demands 1 — and in `cvt_f2h_dst`, `cvt_bf16`,
  `bf_add_dst` and `bf_fma_dst` that nibble is `dst (4,4)`.

The carrier is `c_f2h`, baseline `010114810402`, `outcome: ok`
(`raw/m4_20260828_run03/sweep.jsonl:1824`) — a *correct* fp32→fp16 convert whose destination
is r0.

And the harness swept byte 0 itself, which turns this into a direct demonstration rather than
an inference:

```
b0=0x01 010114810402  ok            word0 = 15872 (0x3E00, the packed half)
b0=0x11 110114810402  wrong_value   word0 = 16320 -- the half is no longer in this slot
b0=0xa1 a10114810402  wrong_value   word0 = 16320, word2 = 15872  -- it moved
b0=0xff ff0114810402  silent_zero
```

The companion `cvt_f2h_dst` arm in the same experiment (carrier `c_f2h_dst`, baseline
`c10114810402`, dst r12) behaves identically in mirror image: only `0xc1` is `ok`, every other
high nibble leaves the observed word at its unwritten value.

> **Verdict: `cvt_f2h`'s match is over-fit on a destination register (the DEF-0171-1
> pattern).** The four rows are safe to keep where they are — their spans are identical to
> `cvt_f2h_dst`'s — but the descriptor should be repaired or retired. One caveat is recorded
> and not glossed: `cvt_f2h.src` sweeps byte 3, and `cvt_f2h_dst` pins `(28,4)==8`, so only
> **80 of those 1 280** cases are inside the sibling's match. That row is *not* freely
> re-pointable even though its bits coincide.
>
> This is **M4/G16G-direct** evidence (EXP-0144). It is not promoted to G17P.

---

## 4. What this experiment did and did not establish

* **New raw observations:** none. No device was touched.
* **New geometry facts:** the operand encodings of five instruction families, re-derived from
  committed bytes — `reg = byte>>1` with `bit0` = width/half for the float and half-float
  groups; `reg = byte>>2` and `byte>>3` for `imad`'s two multiplicand bytes;
  `reg = byte>>1` for `fspecial`'s destination and `byte>>2` for its source; byte 0's high
  nibble as the destination in `falu3`, `iminmax`, `half_alu*`, `fspecial`(byte 3 instead),
  `mov_zext16`, `cvt_f2h*` and `bf_*`. Plus the exact byte partition of
  `half_alu_fma12.ext` (36 720 / 12 750).
* **New liveness facts:** eight accepted byte-2 encodings of the native bfloat add, seven of
  them bit-identical aliases; `half_alu_ext8`'s `dst`/`srcA` arms have **no detection power**
  in EXP-0180's carriers.
* **New semantic facts:** `imad` computes `X * Y + K` with X, Y from bytes 5 and 6 — refuting
  the `srcC_lo` naming at both its historical and its current span; `falu3` computes
  `A*B + C` from bytes 1/3/5, exact on every in-domain case.
* **New generated recipes:** none.
* **Claims downgraded:** none, and **no label was changed or proposed**. Six of the 22 pairs
  are reported `undecidable`; that is a bounded status, not a downgrade.
* **Tool defects reported, not patched:** the `isadb._n1_len` bfloat length gate (P4).
* **Bounded unknowns remaining:** which multiplicand of `imad`/`falu3`/`iminmax`/`half_alu` is
  A and which is B (commutativity); where `imad`'s addend actually lives; what `(12,4)` is in
  `fspecial`, `(40,8)` in `iminmax` and `(32,8)` in `half_alu` (old names refuted, new ones
  unconfirmed); whether the five narrowings are right; what bytes 1 and 3 of `half_alu_ext8`
  are directly rather than by family inference.

---

## 5. How this method could have confirmed a swap that is not real

Stated so the next reader can attack it. **Four of these fired during the work and changed the
answer.**

1. **Trusting the `field` key.** If I had grouped by `field` I would have concluded that
   `imad`'s two names are swapped and stopped — "confirming" EXP-0165's repair. The bytes say
   something stronger *and different*: both names sit on multiplicands, so the swap fixed
   nothing. Grouping by key would have produced a confident, wrong endorsement.
2. **Reading `fstart`/`fwidth` as the harness's opinion.** They are not. They are the frozen
   `db.json`'s spans, and I checked all 20 available against each experiment's own
   `work/frozen/db.json`. Without that check, "the harness declared the wrong span" was an
   available story for all 22 rows, and it is completely false. **This is the single load-
   bearing check in the experiment.**
3. **A purity test that compares repetitions.** *(fired)* My first sub-span run reported
   `NARROWING-REFUTED` on **5 of 5** cases — a "the descriptor repair broke five fields"
   headline. It was comparing the *same encoding* across runs, and in one case two different
   arm baselines. Requiring two *distinct* encodings that are identical outside the swept span
   turned all five refutations into `NO-POWER`. One bug away from a false accusation against
   `4a54e9bb` and `29fb7378`.
4. **A destination assumed to be r0.** *(fired)* My first slot fit hard-coded the destination
   register and returned `not-a-selector` for almost every arm, including fields that are
   unambiguously operands. Published as-is, half the table would have read "the current name is
   refuted". The fix was to *discover* the destination index by scanning all 16 registers.
5. **Reading a commutative operation as an ordered pair.** `a*b` and `min(a,b)` cannot tell A
   from B. If I had let the arithmetic oracle assign the slots it would have "confirmed" a
   specific `srcA`/`srcB` assignment on evidence that cannot support one. Five rows carry
   `A vs B undecidable` for this reason.
6. **Aggregating field coverage across swept bytes.** *(fired — in the input)* This is exactly
   what produced the premise I was handed. Per byte, all three bfloat descriptors put `srcA` at
   `(24,8)`. Summing across bytes 3–7 manufactures an operand hazard that does not exist.
7. **A saturating carrier.** *(fired)* `falu3_ext`'s destination is `1.0` on every case. Any
   affine fit over a constant "succeeds" with `A = 0`; only the release map carries information
   there, and the slot stays `carrier-undecidable`.
8. **A single-record hand check.** My first `half_alu_fma12` oracle run scored **0/51 220** for
   both rival layouts because I used `oracle.dst_half` to choose the register half instead of
   the operand byte's own bit 0. A hand check on one record had already "worked". The corrected
   run scores 47 030 vs 0 — but a lazier author would have reported "neither layout fits" and
   filed a false mystery.
9. **Where it can still be wrong.** `bytes` is trusted to be what actually ran, exactly as in
   EXP-0215 §7.6 — if a harness wrote the *requested* encoding into that column, every Gate-A
   number here is circular. The release-on-read oracle is one mechanism used in several
   carriers, so five of my confirmations share a blind dimension (Phase 5: two carriers with
   the same observation path count as one method). And the `undecidable` verdicts are bounded
   by what these particular carriers can see, not by what the hardware does.
