# EXP-0219 — RESULTS

```
Target:                Apple A18 Pro / G17P (AGXAcceleratorG17P, applegpu_g17p, 5 cores,
                       macOS 26.6, Mac17,5, Metal family Apple9) at 192.168.170.254.
                       NOTHING RAN ON THE M4.
Clean-room provenance: OWN-SHADER + HW-PROBE (our own MSL compiled through the public
                       runtime API, our own bytes spliced and run) + black-box IOKit
                       registry PROPERTY reads for the quiet/counter measurement.
Apple binary introspection: NONE.
Repo HEAD at pre-registration: 3cea1bc4d8d569bcd2ee917d518222188b1fdf9e (tree clean).
Committed:             NOTHING.  Labels changed or proposed: ZERO.  Files touched outside
                       experiments/EXP-0219-named-dispatches/: ZERO.
Captures:              12 run directories, 45,732 records, ALL measured quiet.
Device cost:           recoveryCount 25401 -> 25401.  ZERO device resets, ZERO hangs,
                       ZERO faults, ZERO victims, ZERO measurement failures.
                       macvdmtool NOT used and not needed.
```

## 0. Headline

**Four of the five questions are settled. The fifth is answered in a way the question did
not anticipate: `tex_sample.mode` bit 6 is not nondeterminism at all — it makes the result a
strictly periodic function of the dispatch index.**

| | |
|---|---|
| **A1** | The selector is **byte+9 bit 3**, now **G17P-direct**. `b9 = 0x2c` (bit3=1, bit1=0) fetches, `b9 = 0x22` (bit1=1, bit3=0) takes the immediate — **64/64 each**, both runs. Whole-model: `sel = bit3` **2054/2054**, `sel = bit1` 1040/2054. |
| **A2** | The "index is 5 bits and a non-zero `b8` low nibble suppresses the addend" reading is **REFUTED**. On a carrier whose constant file reaches half-index 75, `b8`'s low bits are the index's high bits: **190/224** held-out against a prediction made from our own MSL source. **Bounded:** bits 0 and 1 of that field are demonstrated (indices 0..75); **bit 2 is still undecidable** — no carrier's file reaches index 128. |
| **A3** | A 32-bit fetch reads **word `K>>1`**, not the pair `(K, K+1)`: it ignores the index's low bit. **64/64 word vs 54/64 pair** on C-DAG and **64/64 vs 38/64** on C-CONST; **all 36 discriminating cases say word**, in every run. |
| **A4** | The immediate branch holds on G17P over **all 32 K** (`b9 = 0x26`, 64/64) and over **all 256 immediate values** (`b8 = 0xd0..0xd7` × 32 K, **512/512** on both carriers, both runs). |
| **B** | Bit 6 is **live on 4 of 9 arms and inert on 5**, and the partition is identical in every capture. On the live arms it makes the payload a **periodic function of the dispatch index** with smallest period **4 or 8** — **240 of 240 sequences**, 0 aperiodic, confirmed **out of sample at N = 24** and with a **single GPU context**. The matched bit6-**clear** control set is **0 unstable of 33 on every arm of every capture**. **What bit 6 MEANS is still unmapped.** |

---

# PART A — `imad`, the four dispatches EXP-0218 named

## A.0 What was dispatched

The 12-byte anchor `9f 00 56 00 02 08 00 60 d0 2e 0a 00` is the sole `imad` in the compiled
form of our own `kernels/probes_imad.metal` (`_agc.main+32` of 62, tokenized with 0 leftover
bytes). It is **byte-identical to EXP-0160's**, which is the first sign the two experiments
are measuring the same thing.

| capture | carrier | order | cases | Gate A | hangs | faults | recoveryCount |
|---|---|---|---:|---|---:|---:|---|
| `g17p_e0219_A_dag_run01` | C-DAG | forward | 2058 | **2058/2058** | 0 | 0 | 25401 → 25401 |
| `g17p_e0219_A_dag_run02` | C-DAG | reverse | 2058 | **2058/2058** | 0 | 0 | 25401 → 25401 |
| `g17p_e0219_A_const_run01` | C-CONST | forward | 1162 | **1162/1162** | 0 | 0 | 25401 → 25401 |
| `g17p_e0219_A_const_run02` | C-CONST | reverse | 1162 | **1162/1162** | 0 | 0 | 25401 → 25401 |

`g17p_e0219_A_pilot01` (80 cases) is retained, supports no verdict, and is never topped up.

**Gate A** is the caller-to-actual ledger with the actual bytes **re-read from the file
handed to Metal** and decoded by the pinned database: requested `byte+7`/`byte+8`/`byte+9`
== decoded, **6440 of 6440**, `bytes_match` 6440/6440, 964 distinct actual encodings on
C-DAG and 548 on C-CONST — equal to the distinct requested counts, so no `match`-bit
collision.

**Gate B — the declared detection-power controls, dispatched first in every capture:**

| control | result | what it shows |
|---|---|---|
| the unmutated anchor | `ok`, `A = 1 = FILE[12]`, reproduces the baseline in every capture | the arm's own oracle is live |
| `b9 = 0x06` and `0x0e` (bit 5 clear) | **`silent_zero` 16 of 16** (2 values x 2 seed sets x 4 captures), r0 = 0 | the arm can produce a NON-baseline result by a mechanism **independent of the addend** |
| `b7 = 0x61 / 0x62` (mode 1/2, product dropped) | r0 = 1 = the addend alone | the addend is readable without any product model |

**Gate E** — designated in the frozen contract *before* any capture as `run01 × run02`
(forward × reverse):

| carrier | shared keys | ledger identical | payload agreement | hard flips |
|---|---:|---:|---:|---:|
| C-DAG | 2058 | **2058/2058** | **2058/2058 = 100.0000 %** | 0 |
| C-CONST | 1162 | **1162/1162** | **1162/1162 = 100.0000 %** | 0 |

**Independent confirmation before any new claim.** The single declared fitted parameter is
`FILE[j]` for j = 0..31, taken from arm `cross`, `b9 = 0x2e`, `b8 = 0xd0`, seed set 1,
`run01` only. On C-DAG it comes out as

```
FILE[0]=0xC500  FILE[1]=0x0001  FILE[2]=0x0100  FILE[12]=0x0001
FILE[13]=0x3F80 FILE[14]=0xBF95 FILE[15]=0xB3D6   all others 0
```

which **reproduces EXP-0218's published table for this carrier exactly, value for value**.
Nothing about that was arranged: EXP-0218 fitted it from EXP-0154/EXP-0160's committed raw,
by a different harness, months of experiments apart.

## A.1 The selector is byte+9 **bit 3** — SETTLED, G17P-direct

The dispatch EXP-0218 named was "`b9 = 0x2c` and `b9 = 0x22` on G17P". This experiment
dispatched the whole low nibble instead: `b9 ∈ 0x20..0x2f` × `K ∈ 0..31` × 2 seed sets, with
`b8 = 0xd0` and the mode bits held at 0. **512 cases per seed set, 64 per `b9` value.**

`A` is recovered model-free as `r0 − m·P` with `P = SEED[b5>>2]·SEED[b6>>3]` (340 for seed
set 1, 133 for seed set 2), and then compared with the two candidate readings
(`analysis/score_a.json` → `A1_b9_branch_by_value`):

| `b9` | bit3 | bit1 | `A == IMM8 == K` | `A == FILE[K]` |
|---|---:|---:|---:|---:|
| `0x20` | 0 | 0 | **64/64** | 2/64 |
| `0x21` | 0 | 0 | **64/64** | 2/64 |
| **`0x22`** | **0** | **1** | **64/64** | 2/64 |
| `0x23` | 0 | 1 | **64/64** | 2/64 |
| `0x24` | 0 | 0 | **64/64** | 2/64 |
| `0x25` | 0 | 0 | **64/64** | 2/64 |
| `0x26` | 0 | 1 | **64/64** | 2/64 |
| `0x27` | 0 | 1 | **64/64** | 2/64 |
| `0x28` | 1 | 0 | 2/64 | **64/64** |
| `0x29` | 1 | 0 | 0/64 | 50/64 \* |
| `0x2a` | 1 | 1 | 2/64 | **64/64** |
| `0x2b` | 1 | 1 | 0/64 | 50/64 \* |
| **`0x2c`** | **1** | **0** | 2/64 | **64/64** |
| `0x2d` | 1 | 0 | 0/64 | 50/64 \* |
| `0x2e` | 1 | 1 | 2/64 | **64/64** |
| `0x2f` | 1 | 1 | 0/64 | 50/64 \* |

\* the odd values are 32-bit fetches (§A.3); a 32-bit word equals the 16-bit half only where
the neighbouring half is 0, which is true at exactly 25 of 32 K in this carrier.

**`0x22` and `0x2c` — the two values EXP-0218 asked for — separate the bits cleanly and in
opposite directions.** Bit 1 is inert for the addend across the whole cross product
(`0x20`/`0x22`, `0x24`/`0x26`, `0x28`/`0x2a`, `0x2c`/`0x2e` are pairwise identical in every
one of 64 comparisons); so is bit 2.

Whole-model, over every scored case in a capture
(`analysis/score_a_final.json`, `analysis/score_a.json`):

| model | C-DAG run01 | C-DAG run02 | C-CONST run01 | C-CONST run02 |
|---|---:|---:|---:|---:|
| **`sel = bit3`, index 8-bit, 32-bit = word** | **2054/2054** | **2054/2054** | **1158/1158** | **1158/1158** |
| `sel = bit3`, index 8-bit, 32-bit = pair | 2014/2054 | 2014/2054 | 1132/1158 | 1132/1158 |
| `sel = bit3`, index 5-bit, 32-bit = word | 2054/2054 | 2054/2054 | 1070/1158 | 1070/1158 |
| `sel = bit1`, index 8-bit, 32-bit = word | 1040/2054 | 1040/2054 | 648/1158 | 648/1158 |
| `sel = bit1`, index 5-bit, 32-bit = pair | 1020/2054 | 1020/2054 | 534/1158 | 534/1158 |

(The four excluded cases per C-DAG capture are the bit5-clear controls, which by construction
do not compute; `(b7 & 3) == 3`, the documented reproducible fault, was never dispatched.)

**Verdict A1: `sel = (byte+9 >> 3) & 1` is now `G17P-direct` as well as `G16G-direct`.**
Byte+9 bits 1, 2, 4, 6, 7 are `accepted-inert for the addend in this envelope; global role
unknown`; bit 5 must be 1 or the block does not compute (dispatched as a control, **16/16**
`silent_zero`).

## A.2 The fetch index is wider than 5 bits — the 5-bit reading is REFUTED, and the answer is BOUNDED at 7

EXP-0218 named the dispatch: *"a carrier whose uniform/constant file holds a non-zero value
above half index 31 — e.g. an authored kernel with >32 distinct 16-bit constants — then
sweep `b8`'s low nibble."* `kernels/carrier_const.metal` is that carrier: 48 constants built
as `as_type<float>((0x3F80+i) << 16 | (0x1000+i))`, so **every one of the 96 halves is a
distinct 16-bit value that identifies which constant it came from and which half of it**.

**Its file, read by 16-bit fetches at `b8 = 0xd0` (the declared fit region, indices 0..31):**

```
0 -> 0xC500   1 -> 0x0001   2 -> 0x0100   3..11 -> 0
12 -> 0xBF95  13 -> 0xB3D6                       (the halves of the -1e-7f the carrier also uses)
14 -> 0x1000  15 -> 0x3F80  16 -> 0x1001  17 -> 0x3F81 ...  30 -> 0x1008  31 -> 0x3F88
```

so the layout is `half 14+2i -> low(i)`, `half 15+2i -> high(i)` — **constants 0..8 exactly
fill the fit region**, and the remaining 39 constants are not visible below index 32.

**The held-out test.** Extrapolating that layout with the constants our MSL *declares* gives
a prediction for every half-index ≥ 32 that uses **no observation at index ≥ 32 at all**.
Sweeping `b8 = 0xd0..0xd7` in fetch mode (`b9 = 0x2e`) over all 32 K:

| `b8 & 7` | index range | non-zero of 64 dispatched | highest non-zero index |
|---:|---|---:|---:|
| 0 | 0..31 | 46 | 31 |
| **1** | **32..63** | **64/64** | **63** |
| **2** | **64..95** | **24** | **75** |
| 3..7 | 96..255 | 0 | — |

and against the MSL-source prediction for indices ≥ 32: **190 / 224**, identical in both
runs. Every one of the 34 differences is at half-index 76..109 — a contiguous run — where the
observation is 0 (verified: 34 of 34) and the extrapolation expected another constant — i.e. **this carrier's file simply ends at
half-index 75**, and above it the fetch reads 0 with no wrap and no aliasing (255 dispatched
indices, all single-valued, none repeating a lower index's value).

**Its own Gate B control is the load-bearing part.** The *same* `b8` low bits, on the *same*
carrier, in **immediate** mode (`b9 = 0x26`) give `A = ((b8 & 7) << 5) | K` in **512/512** —
both carriers, both runs. So those bits demonstrably reach the instruction and are read; a
zero in fetch mode is therefore a fact about the index and the file, not about a dead field.

**And the control carrier reproduces the old artefact.** On C-DAG, whose file is empty above
half-index 15, the same sweep gives **0 of 512** non-zero results at `b8 & 7 != 0` — exactly
the 68/68 "the addend is suppressed" observation the committed corpus rests on. That
observation was **a property of the carrier, not of the instruction**.

**Verdict A2.** `A = FILE[K | (b8 & 7) << 5]`, and `H-A2b` (5-bit index plus suppression) is
**refuted**. **Bounded honestly:** bit 0 and bit 1 of the high field are directly
demonstrated (indices 0..75 read distinct, source-predicted values). **Bit 2 of that field is
STILL UNDECIDABLE** — every index it can reach (128..255) reads 0 in the only two carriers
that exist, so "the field is 8 bits and the file is empty there" and "the field is 7 bits"
remain indistinguishable.

> **The sharper question this leaves:** *does any carrier put a non-zero value at half-index
> ≥ 128?* This carrier declares 48 constants and the file took 31 of them (indices 14..75);
> the other 17 live somewhere the fetch cannot see. So the limit is the **file's own
> capacity**, not the number of constants an author writes, and a successor needs a way to
> make the driver preload ≥ 129 halves — or a different instrument entirely.

**A finite-resource fact, recorded separately** (`RE_EXPERIMENT_PROCESS_CORRECTIONS` §6):
for `carrier_const`, the readable file is **76 halves (38 words)**; all 256 index values are
dispatchable and single-valued; the excess-capacity behaviour is **read 0**, not wrap, not
alias, not fault, not hang.

## A.3 A 32-bit fetch reads WORD `K>>1` — SETTLED, on two carriers

EXP-0218 named the dispatch: `b9` bit 0 = 1 at odd K. All 32 K were dispatched with
`b9 = 0x2f`, on both carriers, in both orders. `FILE[0..31]` is measured by 16-bit fetches
**in the same capture** before the 32-bit cases are scored, so both predictions come from
data and the pairing rule itself is held out.

| capture | 32-bit cases | `pair (K, K+1)` | `word (K & ~1)` | discriminating cases | all say |
|---|---:|---:|---:|---:|---|
| C-DAG run01 | 64 | 54 | **64** | 10 | **word** |
| C-DAG run02 | 64 | 54 | **64** | 10 | **word** |
| C-CONST run01 | 64 | 38 | **64** | 26 | **word** |
| C-CONST run02 | 64 | 38 | **64** | 26 | **word** |

Worked discriminators on C-DAG (`analysis/score_a.json` → `A3_fetch32_pairing`):

```
K = 13:  observed 0x3F800001   pair would be 0xBF953F80   word = FILE[12] | FILE[13]<<16
K = 15:  observed 0xB3D6BF95   pair would be 0x0000B3D6   word = FILE[14] | FILE[15]<<16
K =  1:  observed 0x0001C500   pair would be 0x01000001   word = FILE[0]  | FILE[1] <<16
K =  3:  observed 0x00000100   pair would be 0            word = FILE[2]  | FILE[3] <<16
```

`0x3F800001` is `1.0000001f` and `0xB3D6BF95` is `-1e-7f` — the carrier's own two constants,
recovered whole from an odd index. **Verdict A3: `A32 = FILE[i & ~1] | FILE[(i & ~1)+1] << 16`;
the index's low bit is ignored in 32-bit mode.**

## A.4 The immediate branch holds on G17P over all 32 K and all 256 values — SETTLED

EXP-0218's §6.4 rested the G17P immediate branch on **K = 12 only, 10 cases, 1 experiment**.
Here, on G17P:

* `b9 = 0x26`, `b8 = 0xd0`, **all 32 K**, both seed sets: `A = K` in **64/64** (and the same
  for `0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x27` — 512/512 over the whole bit3 = 0 half);
* `b9 = 0x26`, `b8 = 0xd0..0xd7`, all 32 K, both seed sets: `A = ((b8&7)<<5) | K` in
  **512/512** on C-DAG and **512/512** on C-CONST, in **both** runs.

That is **all 256 values of the 8-bit immediate, generated and read back correctly on G17P**,
on two structurally different carriers.

## A.5 The `imad` addend, as it now stands (G17P-direct)

```
dest = m * (SEED[byte+5 >> 2] * SEED[byte+6 >> 3]) + A       m = 1 if (b7 & 3) == 0 else 0
                                                             (b7 & 3) == 3 faults (not dispatched here)
sel  = (byte+9 >> 3) & 1                     byte+9 bit 5 must be 1 or nothing computes
IDX  = ((byte+7 >> 3) & 0x1f) | ((byte+8 & 7) << 5)          the SAME 8-bit field in both modes
sel == 0 :  A = IDX                                          an immediate, 0..255
sel == 1 :  A = FILE[IDX]                    if (byte+9 & 1) == 0   16-bit half
            A = FILE[IDX & ~1] | FILE[(IDX & ~1)+1] << 16    if (byte+9 & 1) == 1   32-bit word
```

Scored **2054/2054** and **1158/1158**, in two runs each, on two carriers, over two seed sets,
with one fitted table of 32 halves declared in advance.

---

# PART B — `tex_sample.mode` bit 6

## B.0 The desk step, before any dispatch

`analysis/desk_mode_instability.py` and `analysis/desk_class_maps.py` read only EXP-0213's
three **committed** quiet orders and establish, offline:

* **every** unstable value on all four unstable arms has **bit 6 set** — 89 of 89 — and
  **none** has bit 3 set;
* the instability is confined to `bit6 = 1 & bit3 = 0 & bit2 = 0`, **32 of 256 values per
  arm**, of which 20–26 were unstable;
* the alternative payloads are **structured, not noisy**: a result channel reading 0, or a
  channel whose 32-bit float has its **low 16 bits zero** — `10000.0f` `0x461C4000` →
  `9984.0f` `0x461C0000`, `20100.0f` → `20096.0f`, `10201.0f` → `10176.0f`. That is exactly
  *only the high 16-bit half of the destination register was written*;
* on `msfilt` and `mscmp` the bit-6 rows are byte-for-byte identical to the bit-6-clear rows.

This is what the dispatches below were designed against, and it is why the value sets are
**matched pairs**: the 32 values with `bit6=1, bit3=0, bit2=0` against the same 32 with bit 6
cleared.

## B.1 §3z — the stop-ruler, run BEFORE any sweep

Three of the nine arms are **signature-derived** (`located_via: scan`): `msfilt/0`,
`mslodq/0`, `mslodq/1`. `decode_one` never answers "does an instruction start here", and
EXP-0200 found 0 of 7 such sites were boundaries — so the ruler ran first.

A 4-byte `stop` was spliced at each arm's own offset, at ±2/±4/±6, and at +14; a `stop` at
the fragment stage's **offset 0** calibrates what a halt looks like on that carrier (an
all-zero surface, hash `ad7facb2586fc6e9…`, identical on all nine carriers, and different
from every arm's baseline).

| arm | located via | `stop` at +0 | `stop` at +14 |
|---|---|---|---|
| `msread/0`, `msread/1`, `msread/2` | tokenize | **HALT** | **HALT** |
| `mslodq/0`, `mslodq/1`, `mslodq/2` | **scan** | **HALT** | **HALT** |
| `msfilt/0` | **scan** | **HALT** | **HALT** |
| `mscmp/0` | tokenize | **HALT** | **HALT** |
| `msread1/0` (new carrier) | tokenize | **HALT** | **HALT** |

**9 of 9 arm offsets are boundaries the hardware honours, and the 14-byte span is consistent
at all nine independent sites.** The claim is kept one-sided: several ±2/±4/±6 offsets also
halted (a `stop` written into an operand tail can still resynchronise the stream) and those
are recorded as **INCONCLUSIVE**, not as extra boundaries. The confound named in §3z is
recorded too: here the "halted" observable is the render target holding its clear value,
which is a *fourth* producer of "nothing was written" — it is admissible only because it was
**calibrated** against a stop at a known boundary, on the same carrier, in the same capture.

## B.2 The measurement EXP-0213 could not make: repeats INSIDE one process

Every earlier capture dispatched each (arm, value) **once per process**. That cannot separate
a race from per-process state. Here each (arm, value) is dispatched N times back to back in
one process, each dispatch recorded separately.

| capture | phase | order | N | records | Gate A | hangs/faults |
|---|---|---|---:|---:|---|---|
| `g17p_e0219_B_rep_run01` | repeat | forward, adjacent | 16 | 9405 | **9369/9369** | 0 / 0 |
| `g17p_e0219_B_rep_run02` | repeat | reverse, **interleaved** | 16 | 9405 | **9369/9369** | 0 / 0 |
| `g17p_e0219_B_rep_run03` | repeat | forward, adjacent | **24** | 14085 | **14049/14049** | 0 / 0 |
| `g17p_e0219_B_rep_ctl04` | repeat, **1 arm / 1 GPU context** | forward | 24 | 1565 | 1561/1561 | 0 / 0 |
| `g17p_e0219_B_sweep_run01/02` | full 256 sweep, 9 arms | fwd / rev | — | 2331 each | full | 0 / 0 |

Gate B: **every arm's positive control (`mode = 8`) moved the observable, in every capture**,
and every arm's end-of-arm baseline re-check reproduced its opening baseline.

### The three pre-registered models

| model | prediction | outcome |
|---|---|---|
| **M-B2** per-process state | 100 % within-process agreement | **REFUTED** — 32/32 and 16/32 of the bit6 values disagree inside one process |
| **M-B3** harness/readback artefact | the bit6-**clear** control set disagrees at a comparable rate | **REFUTED** — **0 of 33 on every arm of every capture** (9 arms in each of the three full captures, and the 1 arm of the single-context control) |
| **M-B1** race | within-process disagreement > 0 | **confirmed in its prediction, but its framing is wrong** — see §B.3 |

### Which arms bit 6 is live on

Liveness is measured against the **matched twin**: does the payload set at value `v` differ
from the payload set at `v ^ 0x40`, over the 32 pairs? (`analysis/score_b_partition.json`)

| arm | `tex_sample` count / position | rep_run01 | rep_run02 | rep_run03 | 256-value sweep, bit 6 |
|---|---|---:|---:|---:|---:|
| `msfilt/0` | 1 of 1 | 0/32 | 0/32 | 0/32 | **0/128 INERT** |
| `mscmp/0` | 1 of 2 | 0/32 | 0/32 | 0/32 | **0/128 INERT** |
| `msread/0` | 1 of 3 | 16/32 | 32/32 | 16/32 | 112/128 **LIVE** |
| `msread/1` | 2 of 3 | 16/32 | 32/32 | 16/32 | 112/128 **LIVE** |
| `msread/2` (new arm) | **3 of 3, last** | 0/32 | 0/32 | 0/32 | **0/128 INERT** |
| `mslodq/0` | 1 of 3 | 32/32 | 32/32 | 32/32 | 116/128 **LIVE** |
| `mslodq/1` | 2 of 3 | 16/32 | 16/32 | 16/32 | 20/128 **LIVE** |
| `mslodq/2` (new arm) | **3 of 3, last** | 0/32 | 0/32 | 0/32 | **0/128 INERT** |
| `msread1/0` (**new carrier**, 1 read) | 1 of 1 | 0/32 | 0/32 | 0/32 | **0/128 INERT** |

**The live/inert partition is identical in all four captures, 9 arms of 9.**

## B.3 What the instability actually is: a PERIOD, not noise

The repeat sequences are not random. Writing each (arm, value)'s 16 or 24 payloads as symbols
(`analysis/score_b_period.json`):

```
mslodq/0  0x40  0120001001200010          period 8
mslodq/0  0x60  0111011101110111          period 4
msread/1  0x40  1111110111111101          period 8      (run02)
msread/0  0x42  0001000100010001-shaped   period 4      12 of 16 majority
```

| capture | N | unstable (arm,value) | smallest period 4 | period 8 | aperiodic | counts violating the pre-registered divisibility rule | unstable at bit6 CLEAR |
|---|---:|---:|---:|---:|---:|---:|---:|
| `rep_run01` | 16 | 64 | 48 | 16 | **0** | **0** | **0** |
| `rep_run02` | 16 | 112 | 32 | 80 | **0** | **0** | **0** |
| `rep_run03` | **24** | 64 | 48 | 16 | **0** | **0** | **0** |

**`AMENDMENT-01`, frozen before the N = 24 capture, predicted exactly this**: 24 is divisible
by 4 and 8 but **not** by 16, so a "period 16" or "warm-up" explanation predicts something
different. Every one of 64 sequences came back with smallest period 4 or 8 and every payload
count divisible by 24/P. **0 violations, 0 aperiodic.**

**The phase follows the GLOBAL dispatch counter, not the repeat counter.** In the interleaved
capture the sequence for value `v+1` is the sequence for `v` rotated by exactly one step —
`0x40: 0120001001200010`, `0x41: 0012000100120001`, `0x42: 1001200010012000` — which is what
advancing one dispatch per value produces and what a per-value effect cannot.

**`AMENDMENT-02`, frozen before its capture, killed the obvious confound.** Every repeat
capture kept **five** of our own renderer children alive (one per carrier), four of them idle
but holding GPU contexts; a period of 4 or 8 could have been a property of context residency.
Re-run with **one arm, one child, one context**: `msread/0` still shows **32 of 32** bit6-set
values unstable, **31 of them with smallest period exactly 4**, and the bit6-clear control
still **0 of 33**. The sibling-context explanation is refuted. (The 32nd value, the first
dispatched in that capture, is period 4 after a **12-dispatch warm-up prefix** — recorded as
an observation, not smoothed away.)

**The alternatives are partial writes at sub-dispatch granularity.** On `msread/0` at
`mode = 0x42` the two payloads differ only in *which probe pixels* carry the effect: in 12 of
16 dispatches channel `c` has its low 16 bits cleared at every probe pixel (`20100.0f` →
`20096.0f`, `20001.0f` → `19968.0f`), and in the other 4 — repeats 3, 7, 11, 15, i.e. exactly
every fourth — probe pixels 2 and 3 keep their baseline `20100.0` and `20001.0` while pixels
0, 1, 4 and 6 do not. On `mslodq/0` at `0x40` there are three payloads, differing in how many
pixels' second channel survives (all / the first two / none). So the effect is applied per
**pixel or quad**, and which of them get it is what the period selects.

## B.4 Why only `msread` and `mslodq` — and the limit of that answer

The five inert arms include one EXP-0213 never had: `msread1/0`, a carrier this experiment
authored with **exactly one** texture instruction. They also include the two arms nobody had
ever swept — the **last** `tex_sample` of `msread` and of `mslodq`.

The rule consistent with all nine arms is:

> **bit 6 is live on a `tex_sample` only when it belongs to a chain of at least THREE
> `tex_sample` instructions and is not the last of them.**

Support: live on 4 arms that satisfy it (`msread/0,1`, `mslodq/0,1`), inert on 5 that do not
— the last of a 3-chain (`msread/2`, `mslodq/2`), the sole instruction of a program
(`msfilt/0`, `msread1/0`), and **the first of a 2-chain (`mscmp/0`)**, which is the case that
rules out the simpler "any non-final instruction" reading.

**This is `INFERRED`, not proven.** It rests on one carrier per condition and five carriers
in total, and `mscmp` differs from `msread` in more than chain length. It is the strongest
statement the nine arms support and it is not promoted further.

A structural hint recorded and **not** pursued (it would be a new question): the three
chained instructions carry byte+0 = `0x05`, `0x0d`, `0x15` in *both* `msread` and `mslodq`,
i.e. the descriptor's `kind`/`chain` nibbles step through a fixed sequence; `mscmp`'s two are
`0x05`, `0x0d`.

## B.5 This is exactly what broke EXP-0213's Gate E

This experiment's own forward × reverse **sweep** pair disagrees on 14, 8 and 12 of 256
values on `mslodq/0`, `mslodq/1` and `msread/1`, and agrees 256/256 on the other six arms.
**Every single disagreeing value has bit 6 set and bit 3 clear.** Reversing the case order
changes the dispatch index at which each value is dispatched, which changes the phase, which
changes the payload — deterministically.

> **So Gate E in its payload-equality form cannot be met for this field by any capture, on
> any machine, however quiet.** EXP-0213's 2507/2560 was not a measure of machine noise; it
> was a measure of how many bit-6 values happened to land on a different phase in the second
> order. A quiet machine halved it (359 → 53 disagreements) because a quieter machine
> executes a more regular dispatch sequence, not because the effect is load-dependent.

What **is** reproducible, and what this experiment offers in Gate E's place:

| reproducible claim | evidence |
|---|---|
| the live/inert **partition**, per arm | 9/9 identical across 4 captures, 3 orders, 2 repeat counts, 1- and 5-context |
| the **period structure** | 240/240 sequences, P ∈ {4,8}, 0 aperiodic, out-of-sample at N = 24 |
| the bit6-**clear** control | 0 unstable of 33, every arm, every capture (9+9+9+1 arm-captures) |
| the actual-byte ledger | **38,974 / 38,974** across all part-B captures |

## B.6 The `mode` byte, as this experiment measured it (bit liveness per arm, 256 values)

`analysis/score_b_sweep.json`, run01, "how many of the 128 flip-pairs move the payload":

| arm | bit0 | bit1 | bit2 | bit3 | bit4 | bit5 | **bit6** | bit7 | distinct payloads |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `msfilt/0` | 0 | 0 | 32 | 64 | 0 | 64 | **0** | 0 | 3 |
| `mscmp/0` | 0 | 0 | 32 | 64 | 0 | 64 | **0** | 0 | 3 |
| `msread/0` | 8 | 128 | 32 | 128 | 0 | 0 | **112** | 0 | 10 |
| `msread/1` | 8 | 72 | 64 | 128 | 0 | 0 | **112** | 0 | 9 |
| `msread/2` | 0 | 0 | 64 | 128 | 0 | 0 | **0** | 0 | 3 |
| `mslodq/0` | 8 | 8 | 64 | 112 | 8 | 64 | **116** | 0 | 10 |
| `mslodq/1` | 4 | 4 | 64 | 112 | 4 | 64 | **20** | 0 | 6 |
| `mslodq/2` | 0 | 0 | 32 | 128 | 0 | 64 | **0** | 0 | 4 |
| `msread1/0` | 0 | 0 | 64 | 128 | 0 | 0 | **0** | 0 | 3 |

Bit 7 is inert on all nine arms (0/128 × 9). Bit 4 is inert on eight and moves 8 and 4 pairs
on the two `mslodq` arms where bit 6 is live — i.e. **inside the periodic region**, so it is
reported as part of that region and not as an independent finding. Bit 5's split
(live on every implicit-LOD arm, inert on the explicit-level `msread` arms) reproduces
DEF-0204-2 exactly, on a different harness.

## B.7 What bit 6 DOES — and what is still not known

**Established (G17P-direct, this experiment):**

1. bit 6 is **not** a sample-operation-class selector; on five of nine arms it is inert over
   all 128 flip pairs;
2. where it is live it makes the destination write **conditional on a device-side state that
   cycles with period 4 or 8 in the dispatch index**, at pixel/quad granularity;
3. the two outcomes at a given phase are "the channel is written" and "the channel is not
   written / only its high 16-bit half is written";
4. so **an emitter must not set `tex_sample.mode` bit 6**: on a carrier where it is live the
   shader returns a different, order-dependent answer on successive draws of the identical
   program.

**Still UNKNOWN, and named as such:**

* **what the periodic state is.** Candidates this experiment can neither confirm nor exclude:
  a rotating allocation made when each request builds a fresh pipeline from a fresh archive
  (`gfrun4.m` writes a new scratch archive per request, so a per-pipeline placement really
  does rotate), a rotating scoreboard/queue slot, or a quad-scheduling rotation. Separating
  them needs an instrument that can hold the pipeline fixed across dispatches, which this
  harness cannot.
* **whether "chain of ≥3, not last" is the real predicate** (§B.4) — `INFERRED` from nine
  arms.
* **whether bit 6 has a legitimate meaning at all** in a program the compiler would emit. No
  compiler-emitted `tex_sample` in this corpus has it set.

---

## C. Hang classification and device cost

**There were no hangs.** Across all 12 captures: **0 hangs, 0 faults, 0 `InnocentVictim`,
0 measurement failures, 0 cascades.** The declared hang budget (8 per arm, 32 for the
experiment) was never touched, and the cascade guard (6 consecutive hangs with
`recoveryCount` frozen) never fired.

`recoveryCount` was **25401 before the first capture and 25401 after the last** — the device
was never reset, by us or by anyone. Per-capture pre/post counters are in each
`raw/<run>/gpu_pre.json` / `gpu_post.json` and collected in `analysis/quiet_table.json`.

> **A caveat on the two hang classes, stated because it matters for reading this number.**
> EXP-0213's distinction — driver-recoverable (`recoveryCount` advances) versus accumulating
> (`recoveryCount` frozen and every later value hangs) — is only diagnostic **when hangs are
> occurring**. A frozen `recoveryCount` here means "nothing ever reset the device", which is
> the healthy case, not the pathological one. This experiment therefore contributes **no**
> evidence about either class; it contributes the observation that 45,732 dispatches of
> `imad` addend-mode encodings and `tex_sample.mode` values produced none.

## D. Quiet, as a measurement

Every capture was wrapped in EXP-0210's sampler (`harness/quietsample.py`, copied
byte-identical, sha256 `47e2829e6d99…`) at a 2 s interval and bracketed by device-counter
snapshots (`analysis/quiet_table.json`):

| | |
|---|---|
| `n_foreign_runner` | **0 in every sample of every capture** |
| `n_compiler_svc` | **0 in every sample of every capture** |
| `fBusyCount` | **0** in every sample |
| `recoveryCount` across every sample | **25401**, unchanged |
| submitter PIDs seen | only the idle login-window process (328) and our own runners |
| `ioreg` errors | 0 |

**Two limitations of that measurement, both real.** (1) The sampler runs at 2 s and the
part-A captures took **1.4 s** — so `A_dag_run01` has *two* samples and `A_const_run01` has
*one*. Quiet is therefore well measured for the long part-B captures and thinly measured for
the very short part-A ones; what carries part A instead is that both orders agree
**100.0000 %** and `recoveryCount` did not move. (2) A GPU client that starts, submits and
exits between two samples is invisible to it — the same hole EXP-0210 disclosed.

## E. How this method could have produced a FALSE verdict

1. **`bytes` trusted to be what ran.** Gate A here re-reads the spliced window **from the
   file handed to Metal** and decodes it independently, which is stronger than an in-memory
   assertion — but the standing EXP-0215 §7.6 caveat still applies to the last hop.
2. **A single carrier would have given a clean, exact, wrong answer to A2** — and did, to the
   whole corpus, for months. C-DAG alone says "0 of 512 non-zero at `b8 & 7 != 0`", which
   reads as "the field suppresses the addend". Only C-CONST separates it. This experiment
   dispatched the same 512 cases on both carriers *precisely* so the artefact would be
   visible next to the signal.
3. **Fitting and scoring the same population.** The one fitted parameter (32 half-values) is
   declared in `CAPTURE_CONTRACT.json` before any capture, taken from one run, one seed set,
   one `b9` value; the other **6,408 of 6,440** part-A records are held out from it, and A2's index test is scored
   against a prediction derived from **our own MSL source**, not from any observation at
   index ≥ 32.
4. **A control that cannot fail.** Part B's Gate B control (`mode = 8`) moves on every arm in
   every capture. That proves detection power and *nothing else*, and it is not counted as a
   result. The load-bearing control is the **matched bit6-clear twin set**, which can and does
   discriminate: 0 of 33 unstable while its twin is 32 of 32.
5. **An inertness verdict with no detection power.** Five arms read bit 6 inert. Each of them
   has bits 2 and 3 moving the same observable in the same capture (32–128 flip pairs), so
   "the observable did not move" is not true by construction there. It is still bounded to
   the tested envelope and is written that way.
6. **Reading the period off N = 16 only.** Sixteen repeats can only show a period dividing
   16, so the periodicity claim would have been circular. `AMENDMENT-01` was frozen before the
   N = 24 capture for that reason, and the prediction is what makes the result out-of-sample.
7. **The five sibling GPU contexts.** They were in every part-B capture and the quiet metric
   cannot see them because they are ours. `AMENDMENT-02` removed them; the effect survived.
   Had I not looked at my own `procs.jsonl`, "period 4 or 8" could have been a fact about my
   harness.
8. **The stop-ruler's `not_written` confound.** The halt observable here is a cleared render
   target, which has more producers than a halt. It is admissible only because it was
   calibrated against a `stop` at a known boundary on the same carrier in the same capture,
   and because the claim is kept one-sided. A no-halt is reported as INCONCLUSIVE everywhere.
9. **Part A ran at ~1,470 dispatches/second**, which is fast enough to deserve suspicion that
   the GPU was not really re-executing. Three things say it was: the recovered `FILE` table
   reproduces EXP-0218's published values exactly; the recovered addend tracks `K` case by
   case; and the bit5-clear control produces `silent_zero` where its neighbours produce a
   correct result.
10. **Where it can still be wrong.** A2's null above index 75 is weak by construction and is
    reported as **undecidable**, not as "the field is 7 bits". B's "chain of ≥3, not last"
    rule is `INFERRED` from nine arms. And B says nothing at all about what bit 6 *means* —
    only that an emitter must not set it.

## F. Progress accounting (`RE_EXPERIMENT_PROCESS_CORRECTIONS` §9)

* **New raw observations:** 45,732 records in 12 capture directories, all G17P, all quiet,
  0 hangs, 0 faults, 0 device resets.
* **New geometry facts:** `imad`'s addend field is **one 8-bit quantity**
  `byte+7[3:8] | byte+8[0:3] << 5` used as a value or as an index; `byte+9` bit 3 selects
  which, **on G17P**; `byte+9` bit 0 selects a 16-bit half or a 32-bit word and the word form
  **ignores the index's low bit**. `tex_sample`'s 14-byte length is confirmed as a hardware
  boundary at **nine** independent sites.
* **New liveness facts:** `byte+8` bits 0 and 1 are live as index bits in fetch mode
  (bit 2 untested-in-effect); `byte+9` bits 1, 2, 4, 6, 7 are `accepted-inert for the addend
  in this envelope`. `tex_sample.mode` bit 6: **live on 4 arms, accepted-inert on 5** in the
  tested envelope; bit 7 inert on all nine arms.
* **New semantic facts:** the corrected two-mode `imad` addend model scores **2054/2054** and
  **1158/1158** in two runs each over two carriers and two seed sets, with rivals at
  1040/2054 and 534/1158. `tex_sample.mode` bit 6 is **NOT** a sample-class selector and its
  effect is dispatch-index-periodic — a **liveness and behaviour characterisation, not a
  semantic map**.
* **New generated recipes:** none. Gate D was not attempted.
* **Claims downgraded:** one, and it is other people's data, not a retraction of it. The
  committed `mulsel` note's "a non-zero low nibble instead yields addend 0 in 68/68 cases" is
  shown to be **a property of EXP-0160's carrier**, not of the instruction; the observation
  stands, its generalisation does not. **No label was changed or proposed by this
  experiment.**
* **Bounded unknowns remaining:** (i) `byte+8` bit 2's role in the fetch index — needs a
  carrier whose file reaches half-index ≥ 128, which this instrument may not be able to
  produce; (ii) what `tex_sample.mode` bit 6's periodic state physically is; (iii) whether
  "chain of ≥ 3 and not last" is the real predicate for its liveness; (iv) EXP-0218 §6.6's
  A-vs-B multiplicand ordering, untouched here and still undecidable under commutativity.
