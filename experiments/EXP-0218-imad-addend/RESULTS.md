# EXP-0218 — RESULTS

```
Clean-room provenance: derived analysis of already-committed artifacts in this repository.
Device contacted:      NONE.  EXP-0213 holds the A18 Pro for quiet Gate E confirmations.
Apple binary read:     NONE.  Shader compiled: NONE.  Raw files written or modified: NONE.
Repo HEAD:             f66060f91e35a790db7007d35f4756daf8862d61
Frozen inputs:         work/db_frozen.json          sha256 90166d96…
                       work/validation_frozen.json  sha256 7e90e4d5…
                       work/raw_inputs.sha256       sha256 of all 13 raw JSONL files read
                       PRE_REGISTRATION.md          sha256 d577b9ac0a19f0bf9bc3b56530c00677f57784b941948a8cfcb4150c35b6ab22
Files edited in tools/agx-isa, docs/, PROVENANCE.md:  ZERO.  Labels changed/proposed: ZERO.
Committed:             NOTHING.
Population:            13,937 committed `imad` records / 4,118 distinct 12-byte encodings
                       C-M4   (M4 / G16G)      EXP-0139                       5,142 records
                       C-G17P (A18 Pro / G17P) EXP-0154 + EXP-0160            8,795 records
```

## 0. Headline

**The addend is encoded in the instruction — and it is also not encoded in the instruction.
`imad` has two addend modes and one bit chooses between them.**

```
K      = (byte+7 >> 3) & 0x1F          5 bits
hi3    =  byte+8 & 7                   3 bits          IMM8 = K | (hi3 << 5)
mode   =  byte+7 & 3                   0 = product + addend, 1/2 = addend only, 3 = FAULT
sel    = (byte+9 >> 3) & 1             0 = IMMEDIATE   1 = EXTERNAL FETCH
width  =  byte+9 & 1                   fetch only: 0 = 16-bit half, 1 = 32-bit word

sel == 0 :  addend = IMM8                       the value IS in the instruction (8 bits, 0..255)
sel == 1 :  addend = FILE[K]                    the value is NOT in the instruction; K indexes
                                                an external scalar (uniform/constant) file
```

The two anchors this corpus was built on differ in **exactly two bytes**, and one of them is
that bit:

```
C-M4    anchor  9f 00 56 00 02 08 00 38 d0 26 0a 00     byte+9 = 0x26  -> sel = 0  IMMEDIATE
C-G17P  anchor  9f 00 56 00 02 08 00 60 d0 2e 0a 00     byte+9 = 0x2e  -> sel = 1  FETCH
                                          ^^     ^^
```

`analysis/s7_adversarial.json` → `anchor_diff`: the only differing byte positions are **7 and
9**, and byte+9's difference is **exactly bit 3**. That is the whole disagreement between the
two prior readings in `db.json`:

| prior claim | where it came from | this experiment |
|---|---|---|
| EXP-M4-13 R6: "`(K<<3)` is an immediate addend, K in b7[3:8] + mulsel[0:3]" | compile-only, C-M4-shaped anchor | **right that it is an immediate; the split is b7[3:8] + b8[0:3] (3 bits, not 4), and it holds only while `sel == 0`** |
| EXP-0160 / DEF-0160-3: "the addend is **not** in the instruction; bits 3..7 index an external source" | dense G17P sweep at `byte+9 = 0x2e` | **right for `sel == 1`, which is the only mode its anchor could reach** |

Neither was wrong. Neither was general. Nobody compared the two anchors.

---

## 1. What the census showed before any model was fitted

`scripts/s1_census.py` recovers the addend by two routes that need no addend model:

* **C-M4** — lanes 5 (`a=0, b=32`) and 7 (`a=0x7FFFFFFF, b=0`) have a **zero product under
  low-32, unsigned-high and signed-high multiply alike**, so their output word *is* the addend
  whatever the swept byte did to the multiply. This is the route a byte that changes the
  **product** cannot fool.
* **C-G17P** — when `byte+7`'s mode bits are 1 or 2 the product is dropped, so the destination
  *is* the addend. No product model is used.

Distinct addends per swept byte (full table `analysis/s1_census.json`):

| swept byte | C-M4 distinct addends | C-G17P distinct addends | reading |
|---|---:|---:|---|
| +1, +2, +11 | 1 | 1 | no addend role in this envelope |
| +3 (dst), +4 | 2 (`7`, `0`) | 2 (`1`, `-340`) | the second value is "nothing was written"/"zero written", not an addend |
| +5, +6 | 3 \* | 1 | multiplicands — on C-G17P the addend never moves at all |
| **+7** | **32** | **7** | **the addend moves, and differently on the two carriers** |
| **+8** | **25** | 3 | **moves on C-M4; on C-G17P only kills it or widens it** |
| **+9** | 4 | 5 | **the mode bit** |
| +10 | 14 | 5 | the multiply variant changes; the addend does not (§4.4) |

\* On **C-M4** the byte+5 / byte+6 sweeps move the multiplicand *registers*, so lanes 5 and 7
are no longer guaranteed zero-product and the model-free readout is not valid there; those two
populations were pre-registered as **not usable** for scoring addend models on that carrier and
are reported, not scored. On **C-G17P** the register file is seeded, the product is computed
exactly (126/126 and 290/290), and the addend is measured to be constant across both sweeps.

Step 0 first re-derived the product map rather than assuming EXP-0216's:
`P = SEED[b5>>2] * SEED[b6>>3]` (byte+6 bit 0 forces that source to 0) reproduces the
destination **126/126** on the byte+5 sweep, **290/290** on the byte+6 sweep, **38/38** at the
anchor, **50/50** on byte+1, **48/48** on byte+2 and **56/56** on byte+11
(`analysis/s0_product.json`).

---

## 2. The model scoreboard — every pre-registered model, exact numerator/denominator

Hit means the **destination** was predicted exactly (`dest = mode==0 ? P : 0` plus the model's
addend). On C-M4 a hit requires **all eight lanes**. Full matrix, including all 45 register
models: `analysis/s3_models.json`, `analysis/s6_scoreboard.json`.

**What `U` is, exactly, in this table:** the two-mode model in its **16-bit** form only —
`A = IMM8` when `byte+9` bit 3 is 0, else `A = FILE[K]`. It deliberately does **not** model the
32-bit width bit, the byte+9 bit-5 compute enable, the byte+4 write enable, or the byte+8 /
byte+10 multiply variants, so the populations that sweep *those* are where it fails, and the
failures are informative rather than swept under the rug: C-G17P `byte+8` 50/538 (the high
nibble changes the multiply and `0xf0` widens the fetch), `byte+9` 14/58 (30 cases have bit 5
clear so the block does not compute; 6 are 32-bit fetches), `byte+4` 18/56 (bit 0 gates the
write), `byte+10` 4/58 (mulhi), `byte+3` 58/62 (the destination moves). The 32-bit width is
scored separately, out of sample, in §5 (8/8).

### C-M4 (M4 / G16G) — where `sel == 0`

| model | anchor | byte+7 | byte+8 | byte+9 | byte+11 | byte+1 |
|---|---:|---:|---:|---:|---:|---:|
| **U** `IMM8 if b9 bit3==0 else FILE[K]` | **30/30** | **381/382** | 62/510 | **190/510** | **510/510** | **254/254** |
| `M-IMM-IMM8 = (b8&7)<<5 \| b7>>3` | **30/30** | **381/382** | 62/510 | 126/510 | **510/510** | **254/254** |
| `M-IMM-K = b7>>3` | 30/30 | **381/382** | 6/510 | 126/510 | 510/510 | 254/254 |
| `M-IMM-K9` (db.json's `(b8&0xF)<<5\|K`) | 30/30 | **381/382** | 30/510 | 126/510 | 510/510 | 254/254 |
| `M-NONE-EXT(K) = FILE[K]` | 0/30 | 0/10 | 0/510 | 64/510 | 0/510 | 0/254 |
| `M-NONE-FIXED` (constant addend) | 30/30 | 10/382 | 6/510 | 126/510 | 510/510 | 254/254 |
| `M-IMM-B9 = b9` | 0/30 | 0/382 | 0/510 | 0/510 | 0/510 | 0/254 |
| `M-IMM-B10 = b10` | 0/30 | 12/382 | 0/510 | 0/510 | 0/510 | 0/254 |

### C-G17P (A18 Pro / G17P) — where `sel == 1`

| model | anchor | byte+7 **[FIT]** | byte+7 **held out** | byte+6×+7 | byte+7×+8 | byte+5 | byte+6 | byte+11 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **U** | **38/38** | **208/208** | **1832/1832** | **396/396** | **308/308** | **126/126** | **290/290** | **56/56** |
| `M-NONE-EXT(K)` | 38/38 | 208/208 | **1832/1832** | 396/396 | 308/308 | 126/126 | 290/290 | 56/56 |
| `M-IMM-IMM8` | 0/38 | 10/208 | 42/1832 | 72/396 | 56/308 | 0/126 | 0/290 | 0/56 |
| `M-IMM-K` | 0/38 | 10/208 | 42/1832 | 72/396 | 56/308 | 0/126 | 0/290 | 0/56 |
| `M-IMM-K9` (db.json) | 0/38 | 10/208 | 42/1832 | 72/396 | 56/308 | 0/126 | 0/290 | 0/56 |
| `M-NONE-FIXED` | 38/38 | 16/208 | 114/1832 | 108/396 | 84/308 | 126/126 | 290/290 | 56/56 |
| best of the 45 `M-REG-bN(>>k)` | 0/38 | 12/208 | 161/1832 | 20/396 | 0/308 | 0/126 | 0/290 | 0/56 |

**Only one fitted parameter exists in the whole experiment:** the external file table
`FILE[K]`, fitted on **EXP-0160 `run01`, seed set 1, byte+7 sweep alone (208 cases)**. Every
other C-G17P number above is a held-out prediction. Broken out by run and seed set
(`analysis/s5_finalize.json`):

```
EXP-0154 run02 sset1  191/191      EXP-0160 run01 sset2  205/205
EXP-0154 run04 sset1  183/183      EXP-0160 run02 sset1  211/211
EXP-0160 confirm03    14/14, 28/28 EXP-0160 run02 sset2  209/209
EXP-0160 confirm04    18/18, 23/23 EXP-0160 confirm06    278/278, 472/472
                                   ------------------------------------
                                   held out total       1832 / 1832
```

The `M-IMM-IMM8` model has **no fitted parameter at all**: `A = ((b8 & 7) << 5) | (b7 >> 3)`
is read straight out of the instruction. Its 381/382 on C-M4's byte+7 sweep is therefore a
pure out-of-sample prediction over 32/32 values of K.

---

## 3. The five pre-registered discriminators (`analysis/s4_discriminators.json`)

| # | test | result | what it rules out |
|---|---|---|---|
| **a** | same byte+7 value, two carriers | **32 K values in both; the two carriers agree at 1** | a *carrier-independent* literal in byte+7 |
| **b** | GPR seed set 1 vs 2, same target, same carrier | **384 encodings run under both; 384/384 identical addend, 0 differ** | **every Group III register model** |
| **c** | per-lane spread on C-M4 | one addend explains all 8 lanes in 381/382 byte+7 cases | a *per-lane* (GPR) addend source |
| **d** | process launch `run01` vs `run02` on C-M4 | 2,360/2,361 encodings give the same addend | a launch-varying source (e.g. a buffer address) |
| **e** | width vs field | C-M4 addends reach **231** (8 bits); a 5-bit K cannot hold it | `A = K` as the complete rule |

Group III in full: every `M-REG-bN(>>k)` for N ∈ {3..11}, k ∈ {0..4} — **45 models, best score
167 / 4,126** on C-G17P. The shift was derived, not assumed, precisely because the two
multiplicand bytes already use two *different* shifts (`>>2` and `>>3`).

---

## 4. The four facts the verdict is built on

### 4.1 On C-M4 the addend is literally `K` — over all 32 values of K

`analysis/s4_discriminators.json` → `a_C_M4_byte7_A_equals_K`:

```
A == (byte+7 >> 3) in 381 of 382 scored cases, 32 / 32 distinct K covered, all 8 lanes exact
```

The single exception is `9f00560002080024d0260a00`: `run01` returns
`product + 4` on all eight lanes (a clean hit), `run02` returns all zeros (`silent_zero`), and
the `reval02` re-run returned no words. Cross-run disagreement on one encoding, in an
experiment that itself found 44 % of its faults irreproducible — recorded as
**measurement instability**, not as a model failure.

### 4.2 byte+8 bits 0..2 are the immediate's high three bits — and bit 3 is not

C-M4 byte+8 sweep restricted to the documented low-32 `mulsel` high nibble
(`analysis/s4_discriminators.json` → `b_C_M4_byte8_immediate_high_bits`):

```
high nibble 0xd :  A == ((b8 & 7) << 5) | K   in  60 / 60
0xd0 -> 7   0xd1 -> 39  0xd2 -> 71  0xd3 -> 103  0xd4 -> 135  0xd5 -> 167  0xd6 -> 199  0xd7 -> 231
0xd8 -> 7   0xd9 -> 39  0xda -> 71  0xdb -> 103  0xdc -> 135  0xdd -> 167  0xde -> 199  0xdf -> 231
high nibble 0xc / 0xe / 0xf / 0x0 :  0 / 32 each — these change the MULTIPLY, not the addend
```

Byte+8 bit 3: **8 of 8** bit-flip pairs leave the addend identical
(`analysis/s6_scoreboard.json`). So the immediate is **exactly 8 bits**, not 9 — `db.json`'s
`mulsel[0:3]` (four bits) is one bit too wide.

### 4.3 byte+9 bit 3 is the mode selector, and it is confirmed on **both** targets separately

This is what breaks the carrier/target confound: each target shows **both** modes.

```
C-M4   (G16G), byte+9 dense 256-value sweep, K = 7 fixed, byte+9 bit5 == 1:
   bit3 == 0 (64 values, 156 cases)   A == IMM8 == 7   in 156 / 156
   bit3 == 1 (64 values, 128 cases)   A == IMM8        in   0 / 128   (A is 0 or 256)
   bit-flip pairs that move the addend:  bit3 64/64   bit0 32/64   bits 1,2,4,6,7  0/64

C-G17P (A18 Pro), byte+9 sweep (EXP-0154 run02 + run04), K = 12 fixed, byte+9 bit5 == 1:
   bit3 == 0  byte+9 in {0x20,0x21,0x60,0xa0,0xe0}   A == K == 12   in 10 / 10
   bit3 == 1  byte+9 in {0x2e,0xaa,0xfe}             A == FILE[12] == 1        (42 cases)
              byte+9 in {0x3f,0x7f,0xff}             A == 0x3F800001           (6 cases)
```

The same byte+7 value `0x60` (K = 12) gives **12** on C-M4 and **1** on C-G17P — and flipping
byte+9 bit 3 on C-G17P restores **12**. The difference is the bit, not the target.

### 4.4 What the addend is **not**

* **Not a register.** 384/384 encodings run under both G17P seed sets give an identical
  addend; the best of 45 register models scores 167/4,126; and on C-M4 one scalar addend
  explains all eight lanes.
* **Not byte+5 or byte+6.** Those are the multiplicands (EXP-0216, re-derived here at 126/126
  and 290/290); the addend is constant across both sweeps.
* **Not byte+10 or byte+11.** Byte+11's sweep leaves the addend unchanged (C-M4 510/510,
  C-G17P 56/56). Byte+10 changes the *multiply* — at `b10 = 0x00` the destination is `1`,
  which is `mulhi(34,10) + 1`: the product went to zero and the addend stayed 1. Subtracting
  the low-32 product there makes the addend *look* like it moved to `-339`. It did not.
* **Not byte+3 or byte+4.** Byte+3 is the destination; byte+4 bit 0 gates whether anything is
  written at all (`A` reads as `-340` there, i.e. the destination is 0).

---

## 5. The external file, measured (C-G17P) — and why it is carrier state, not encoding

`FILE[K]`, fitted on 208 cases and confirmed on 1,832 held-out ones, is exactly the
**carrier's own constants**, in 16-bit halves:

| K | value | what it is in `EXP-0160/kernels/carrier_dag.metal` |
|---:|---:|---|
| 0 | 50432 = `0xC500` | — |
| 1, 12 | 1 = `0x0001` | low half of `1.0000001f` = `0x3F800001` |
| 2 | 256 = `0x0100` | — |
| 13 | 16256 = `0x3F80` | high half of `1.0000001f` |
| 14 | 49045 = `0xBF95` | low half of `-1e-7f` = `0xB3D6BF95` |
| 15 | 46038 = `0xB3D6` | high half of `-1e-7f` |
| 3–11, 16–31 | 0 | empty in this carrier |

**An out-of-sample prediction that the fit could not have produced.** `FILE` was fitted only
from 16-bit fetches. If a 16-bit fetch returns *half* K of a 32-bit word file, then a 32-bit
fetch at even K must return `FILE[K] | FILE[K+1] << 16`. Predicted `1 | 16256<<16` =
**1065353217** = `0x3F800001`:

```
via byte+9 bit0 = 1  (0x3f, 0x7f, 0xff)   6 / 6   exact
via byte+8 = 0xf0                          2 / 2   exact
```

C-M4's fetch mode agrees structurally at its one reachable K: 16-bit → 0 (64 cases), 32-bit →
256 (64 cases), i.e. a 32-bit word `0x00000100` whose **high** half is 0. Consistent with a
32-bit word file read by half index; the pairing rule itself is **not** scoreable on C-M4
because half 8 was never dispatched.

**Why this is not "an immediate we failed to decode":** the value is seed-independent
(384/384), launch-stable (2,360/2,361), scalar across 8 lanes, and identical for encodings
whose byte+7 differs — while being *different* for the same encoding in a different carrier
(discriminator **a**: the two carriers agree at 1 of 32 K). A number that changes when only
the surrounding program changes is not carried by the instruction.

---

## 6. What remains UNDECIDABLE, and exactly what would settle it

These are real answers, not gaps in effort. Each names the dispatch that would decide it.

1. **On C-G17P, bit 1 and bit 3 of byte+9 cannot be separated.** Every literal-mode value
   EXP-0154 dispatched (`0x20, 0x21, 0x60, 0xa0, 0xe0`) has *both* bits 0; every fetch-mode
   value (`0x2e, 0x3f, 0x7f, 0xaa, 0xfe, 0xff`) has *both* bits 1
   (`analysis/s7_adversarial.json` → `candidate_selector_bits`: `bits_that_separate_them
   perfectly = [1, 3]`). The C-M4 dense sweep decides it there — bit 3 moves the addend in
   **64/64** flip pairs, bit 1 in **0/64** — so *the selector is bit 3* is a **G16G-direct**
   fact and *there is a selector in byte+9* is direct on both targets.
   **Settles it:** dispatch byte+9 = `0x2c` (bit3=1, bit1=0) and `0x22` (bit1=1, bit3=0) on
   G17P at any K.
2. **In fetch mode, is the source index 5 bits or 8?** `K` alone, or `K | (b8&7)<<5`? Of
   **4,086** scored fetch-mode cases, **0** separate the two readings, because this carrier's
   file reads 0 at every half-index ≥ 32 and a non-zero `b8` low nibble therefore looks
   identical to "the addend is suppressed" (`analysis/s6_scoreboard.json` →
   `fetch_index_width_ambiguity`). The literal mode shows the field *is* 8 bits wide, which is
   suggestive and is not evidence.
   **Settles it:** a carrier whose uniform/constant file holds a non-zero value above half
   index 31 — e.g. an authored kernel with >32 distinct 16-bit constants — then sweep `b8`'s
   low nibble.
3. **Does a 32-bit fetch pair `(K, K+1)` or read word `K>>1`?** Identical at even K, and the
   corpus contains **no odd-K 32-bit fetch** (all 8 observed 32-bit fetches are at K = 12).
   **Settles it:** byte+9 with bit 0 = 1 at K = 13.
4. **The (byte+7 × byte+9) cross product was never dispatched.** `A = IMM8` over all 32 K is
   verified only on **C-M4** (at byte+9 = `0x26`); on **C-G17P** the literal branch rests on
   **K = 12 only**, 10 cases, 5 byte+9 values, 2 runs, 1 seed set, 1 experiment.
   **Settles it:** sweep byte+7 on G17P with byte+9 = `0x26`.
5. **byte+9 bits 1, 2, 4, 6, 7 are `accepted-inert for the addend` in these carriers; global
   role unknown** (0/64 flip pairs each on C-M4). Bit 5 must be 1 for the block to compute at
   all in both carriers; that is a bound, not a characterization.
6. **Which multiplicand is A and which is B remains undecidable** (EXP-0216, commutativity).
   Nothing here touches it.

---

## 7. Traps this corpus has paid for, and how they were handled

* **The `field` key and the mnemonic were never used.** Every byte is decoded by **position**
  from the record's own `bytes`. EXP-0139 labels byte+5 `srcB` and byte+6 `srcC_lo` from a
  `db.json` that has since swapped them; not one number here depends on that.
* **A record's declared span was never read.** `fstart`/`fwidth` are ignored entirely, so a
  stale harness `db.json` cannot move a count.
* **The constant-byte artefact, live in this very analysis.** `A = byte+11` scores
  **1,506/1,832** on the C-G17P byte+7 sweep — purely because byte+11 is `0x00` there and
  1,662 of 2,040 cases have addend 0 (`analysis/s7_adversarial.json`). It scores **0/38** at
  the anchor and **2/56** on the byte+11 sweep itself. A model that "fits" a population where
  the field never moves has decided nothing.
* **The poison destination.** Un-written destinations still holding `0xDEADBEEF` initially
  produced 6 "ambiguous" entries in the fitted `FILE` table. Excluding them made the table
  single-valued at all 32 K and moved byte+7 from 1,832/1,843 to **1,832/1,832**.
* **Fitting and scoring the same population.** `FILE` is fitted on one run and one seed set
  (208 cases) and scored on 1,832 held-out ones plus two width predictions it could not have
  produced.
* **`measurement_failure` is not a hardware outcome.** 2,059 C-G17P and 124 C-M4 cases carry
  `InnocentVictim`; every one is excluded and counted, never scored.

## 8. How this method could have fitted an addend that is not there

1. **Analysing one carrier.** C-G17P alone gives `M-NONE-EXT(K)` at **2,040/2,040** and would
   have "confirmed" DEF-0160-3 as a general fact. C-M4 alone gives `M-IMM-K` at **381/382** and
   would have "confirmed" EXP-M4-13 R6. Each is a clean, exact, wrong general conclusion. **This
   is the failure that actually happened in the corpus, twice, and it is why the two claims sit
   contradicting each other inside one `db.json` field today.**
2. **Subtracting a product model blindly.** On byte+10 the multiply becomes `mulhi`; subtracting
   the low-32 product makes the addend appear to move from 1 to `-339`. The zero-product lanes
   (5 and 7) exist precisely so a product change cannot be read as an addend change.
3. **Reading one lane.** On C-M4 lane 5 alone, "the addend is 0" and "the product is 0" are the
   same observation. Requiring all eight lanes to agree is what separates them.
4. **Importing a shift.** `imad`'s own two multiplicands use `>>2` and `>>3`. Had I assumed the
   project-standard `>>1`, `M-REG-b7(>>1)` at 167/4,126 would have been the best register model
   on offer and nothing would have shown it was noise. All 45 (byte, shift) pairs were scored.
5. **A constant byte scoring well** — §7, and it scored 1,506/1,832 here.
6. **Fitting the slot table on the population being scored** — held out, 208 vs 1,832.
7. **Trusting a single-run outcome.** The one C-M4 byte+7 miss is a `silent_zero` in `run02`
   that `run01` contradicts. Reported as instability, and it is 1 of 382.
8. **Where it can still be wrong.** `bytes` is trusted to be what actually ran (the standing
   EXP-0215 §7.6 caveat); if a harness recorded the *requested* encoding, every count here is
   circular. The C-G17P literal branch rests on one K and one experiment. And the external
   file's *contents* are a property of two carriers we happen to have, not a hardware fact —
   what is established is that the addend comes from **outside the instruction** in that mode,
   not what any particular slot holds.

---

## 9. Progress accounting (RE_EXPERIMENT_PROCESS_CORRECTIONS §9)

* **New raw observations:** none. No device was touched.
* **New geometry facts:** `imad`'s addend field is an **8-bit immediate split
  `byte+7[3:8]` (low 5) + `byte+8[0:3]` (high 3)**; `byte+8` bit 3 is **not** part of it
  (8/8 flip pairs identical), so `db.json`'s `mulsel[0:3]` is one bit too wide. `byte+9`
  bit 3 is the addend-source-class selector (G16G-direct; on G17P bit 1 and bit 3 are not
  separable by the committed records). `byte+9` bit 0 selects a 16-bit half vs a 32-bit word
  of the external file.
* **New liveness facts:** `byte+9` bits 1, 2, 4, 6, 7 are `accepted-inert for the addend in
  the C-M4 byte+9 sweep; global role unknown` (0/64 flip pairs each). `byte+11` is
  addend-inert in both carriers (510/510, 56/56).
* **New semantic facts:** `dest = m·(SEED[b5>>2]·SEED[b6>>3]) + A` with the two addend modes
  above — **381/382** on C-M4's byte+7 sweep (no fitted parameter), **2,040/2,040** on
  C-G17P's (208 fit / 1,832 held out), **60/60** on C-M4's byte+8 immediate high bits,
  **156/156** and **10/10** on the two mode-selector branches, **8/8** on the 32-bit width
  prediction.
* **New generated recipes:** none. This experiment dispatched nothing; §6.4 names the sweep an
  emitter-grade recipe would need.
* **Claims downgraded:** none, and **no label was changed or proposed**. Two `db.json`
  statements are shown to be **mode-restricted rather than false** — neither is retracted; a
  proposal to scope both is in `analysis/proposed_db_edits.json`.
* **Bounded unknowns remaining:** the six items in §6.
