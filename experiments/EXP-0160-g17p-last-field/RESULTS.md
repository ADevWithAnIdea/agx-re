# EXP-0160 — RESULTS: the last blocking field on eight ALU instructions (**G17P**)

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, Metal family Apple9), `192.168.10.243`. **Every verdict below is `target: G17P`,
measured directly on the documentation target.** No M4 GPU work; no M5.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/probes.metal (8 authored kernels) and kernels/carrier_dag.metal,
  both authored by us for this experiment, and the AGX machine code the PUBLIC Metal runtime
  API compiled from that source. tools/{shdump,agxtest,agx-isa} used READ-ONLY and unmodified.
  EXP-0154's committed raw JSONL was read as prior evidence, for experiment DESIGN only
  (analysis/prior_scan.py, analysis/design_check.py -- desk-only, promote nothing).
Apple binary introspection: NONE.
Reproduction: README.md section "Reproduction".
Evidence: raw/g17p_20260830_run01/, raw/g17p_20260830_run02/            (the gated pair)
          raw/g17p_20260830_confirm{01,02,03,04,05b,06}/                (adjudication)
          raw/g17p_20260830_ext_run01/, ext_run02/, ext_confirm01/      (Addendum A)
          raw/g17p_20260830_smoke01/                                    (retained smoke capture)
          work/anchors/anchor_report.json, work/authored_hashes.txt, work/design_check.txt
```

---

## 1. Headline

| | |
|---|---|
| Fields dispatched (one per instruction, each said to be the last blocker) | **8** |
| Fields actually blocking those instructions in `validation.json` | **10** — `falu3`/`falu3_ext` each had **two** |
| Cases dispatched | **4,064** (main) + **1,028** (Addendum A) x 2 gated runs each |
| Adjudication dispatches | **8,908** across six re-runs |
| Cases gated after adjudication | **4,064 / 4,064** and **1,028 / 1,028** — **0 unresolved, 0 clean disagreements** |
| Fields moved to `hardware-run` | **9 of 10** |
| **Instructions unblocked (become EMITTABLE)** | **7 of 8** |
| db.json defects found and evidenced | **7** |

### The seven instructions unblocked

**`falu2_ext`, `falu2i`, `falu3`, `falu3_ext`, `iminmax`, `isel8`, `half_pack`**

`falu3` and `falu3_ext` are the fused-multiply-add core of the float ALU, so this is the
last piece of the 3-source float family; `falu2i` is the packed-immediate form a compiler
reaches for constantly.

### The one that did not close, and why

**`imad.srcC_desc` — `untested`.** Not for want of data: it was swept densely under two seed
sets and its behaviour is now completely modelled. It fails the frozen promotion rule because
**it is not one field**, and because the thing it selects is not in the instruction at all.
See §5. Chasing it turned up something worth more than the field itself: **db.json's `imad`
has no `srcA` field, and the byte that carries the first multiplicand is documented as part of
an immediate that does not exist** (§5.2, `DEF-0160-6`).

---

## 2. What was directly observed

Per case: the full 16-register architectural state after the tested block, both integrity
sentinels, the command-buffer status, the OS fault-classification string, and the count of
read-back words still holding the `0xDEADBEEF` poison. Every case was run under **two
independent seed sets** with a byte-identical program shape.

**Arm validity (P1) — all eight arms, plus Addendum A's two:**

| arm | instruction | field | w | probe | anchor bytes | block | anchor value | falsifier | host oracle |
|---|---|---|---|---|---|---|---|---|---|
| F2E_CTRL | `falu2_ext` | `ctrl` | 7 | `k_sat_add` | `09011c0501000082` | 32:40 | `0x01` | fired | matched both sets |
| F3_OP | `falu3` | `op` | 8 | `k_fma` | `09011e05810802c0` | 56:64 | `0x1e` | fired | matched both sets |
| F3E_OP | `falu3_ext` | `op` | 8 | `k_sat_fma` | `09011e05820802000082` | 56:66 | `0x1e` | fired | matched both sets |
| IMINMAX_SRCB | `iminmax` | `srcB` | 8 | `k_imin` | `02011e0507c0` | 32:38 | `0xc0` | fired | matched both sets |
| ISEL8_CMPMODE | `isel8` | `cmp_mode` | 8 | `k_rsqrt` | `7281270982040202` | 18:32 | `0x82` | fired | structural only |
| IMAD_SRCC | `imad` | `srcC_desc` | 8 | `k_imad` | `9f00560002080060d02e0a00` | 32:44 | `0x60` | fired | matched both sets |
| HALFPACK_SRC | `half_pack` | `src` | 8 | `k_half2` | `18031805` | 32:42 | `0x18` | fired | matched both sets |
| F2I_CTRLLO | `falu2i` | `ctrl_lo` | 7 | `k_addimm` | `09c9140180c0` | 18:24 | `0x00` | fired | matched both sets |
| F3_SRCB | `falu3` | `srcB` | 8 | `k_fma` | `09011e05810802c0` | 56:64 | `0x05` | fired | matched both sets |
| F3E_SRCB | `falu3_ext` | `srcB` | 8 | `k_sat_fma` | `09011e05820802000082` | 56:66 | `0x05` | fired | matched both sets |

The host oracle is computed from the seeds alone, with no GPU: `saturate(s0+s2)` for
`falu2_ext`, `s0*s2+s4` for `falu3`, `saturate(s0*s2+s4)` for `falu3_ext`, `min(s0,s2)` for
`iminmax`, `s0*s2+1` for `imad`, `s1+s2` (fp16 denormal significand addition) for `half_pack`,
and `s0 + imm_decode(0xc9)` for `falu2i`. All matched the measured baseline in **both** seed
sets. `isel8`'s block is `fspecial_est` + `isel8`, whose result is not host-computable; that
arm's oracle is structural (register roles) only, and it is labelled as such.

---

## 3. The nine fields that closed

### 3.1 `isel8.cmp_mode` — the length selector, and nothing else

Complete 4-class table over the only two live bits; bits 2..7 inert; each class confirmed by
**64** distinct field values, dense over 256, both seed sets.

```
(v & 3) = 00  ->  r7 changed   (length 6: too short; the block's tail decodes as something else)
(v & 3) = 01  ->  correct      (length 8: the anchor)
(v & 3) = 10  ->  correct      (length 10: swallows the following `mov_imm r15,0`, which is
                                a no-op because r15 already holds 0)
(v & 3) = 11  ->  9 poison words (length 12: eats into the following `device_store`)
```

An emitter may put **any** value in bits 2..7 and must put `01` in bits 0..1. Note this is the
`0x02` opcode group, not the float `0x09` group, so the byte+4 length selector is not
float-family-specific.

### 3.2 `falu2_ext.ctrl` and `falu2i.ctrl_lo` — the same byte, the same three roles

`falu2_ext.ctrl`: relevant bits `{0,1,5,6}`, bits `{2,3,4}` inert, 16 classes, ≥8 values each.

```
bits 0,1 = the length selector, exactly as in isel8 above
           00 -> 9 poison words   01 -> correct   10 -> correct   11 -> 9 poison words
bits 5,6 = silent corruptors: with either set (and a legal length) the destination
           reads back 0 instead of the computed saturate(a+b)
bits 2,3,4 = inert across all 128 values, both seed sets
```

This is the same value→behaviour map already `hardware-run` for `falu2.ctrl` on M4
(EXP-0105/0113/0119) — now measured directly on G17P for the 8-byte extended form.

`falu2i.ctrl_lo` has an exact mask rule as well: **`ok ⟺ (v & 0x6b) == 0x00`, 0 exceptions over
all 128 values**, with bits 2 and 4 inert. Its live map differs from `falu2_ext`'s in one
respect worth an emitter's attention: bit 0 does not break framing here, it **changes the
destination value**, so the two forms of the same byte are not interchangeable.

### 3.3 `falu3.op` / `falu3_ext.op` — not one field (`DEF-0160-1`)

**Exact ok-rule `(v & 0xd7) == 0x16`, 0 exceptions over all 256 values, in both seed sets and
both instructions.** Bit 5 is the only inert bit.

The rule is exact because the byte is `falu2`'s `opsel` + `opflags` at `falu2`'s own absolute
bit positions. The **operation** carried by the low 3 bits was identified against a
host-computed function library and required to agree in **both** seed sets:

| `opsel` (byte value bits 0..2) | destination |
|---|---|
| 0 | `a + b` |
| 1 | `a * b` |
| 2 | `a * b + a` |
| 3 | not identified by the library (a real value, recorded per case) |
| 4 | `-b` |
| 5 | `0` |
| 6 | `a * b + c` — the anchor's fma |
| 7 | fault-prone: **50 of 51 dispatches fail** (§4.2) |

and the high 5 bits are the release/publication flags: byte value bit 4 (instruction bit 20)
is **release srcB** — clearing it leaves srcB's register holding its seed instead of being
zeroed by release-on-read — and byte value bits 6,7 (instruction bits 22,23) are the silent
corruptors. An emitter that treats byte+2 as one opaque opcode cannot set the release flags,
which are what make a register reusable.

### 3.4 `falu3.srcB` / `falu3_ext.srcB` (Addendum A) — predicted 256/256 from the seeds

The strongest evidence in this experiment. Exact mask `(v & 0x7f) == 0x05` (bit 7 inert), a
register model matching **22/22 identified releases over 11 distinct registers, 0 wrong**, and
a complete **full-state prediction**:

```
srcB byte = (reg << 1) | is32,   reg = bits[1:7],   bit 7 inert
B  = r[reg]   when is32 = 1
   = 0.0      when is32 = 0   (a 16-bit read of a seed whose low halfword is zero)
r0 = [saturate]( srcA * B + srcC )
```

Predicting the destination word from the seeds alone gives **256/256 hits, 0 misses, in both
seed sets, for both instructions** (`m4_full_state_prediction` in the verdict file).

### 3.5 `iminmax.srcB` — a register selector that is not one (`DEF-0160-2`)

Complete 16-class table over relevant bits `{0,1,2,4}`; bits **3, 5, 6 and 7 are inert** across
all 256 values in both seed sets, and **no** value→register model reaches the ≥90%/≥6-register
bar. A byte with four dead bits and no register map cannot be a register selector.

What it actually is: `iminmax` uses the **same 6-byte slot layout as `falu2`** — byte+1 srcA
descriptor, byte+3 srcB descriptor, byte+5 the source-class/modifier byte — and db.json's
operand names are shifted by one slot. The live bits are exactly `falu2`'s byte+5 roles
(bit 0 srcA class, bits 1-2 srcB class, bit 3 srcB negate — inert here because the operation is
integer, bits 4-7 `mod_hi`), and the anchor value `0xc0` is `falu2`'s standard `mods` default.
Independently, `min(seed[0], seed[2])` reproduces the measured baseline in both seed sets with
byte+1 → r0 and byte+3 → r2.

Reading the table: class `0001` (srcA class = 1) zeroes the destination, because srcA is read
from a non-GPR file and returns 0, so `min(0, 34) = 0`. Classes `0010`..`0111` (srcB class 1/2/3)
do the same to srcB and leave srcB's register **unreleased**.

### 3.6 `half_pack.src` — inert except at `(v & 7) == 6` (`DEF-0160-4`)

Complete 32-class table over relevant bits `{0,1,2,6,7}`; bits 3, 4, 5 inert; 224 of 256 values
reproduce the anchor exactly. The four live classes are all `(v & 7) == 6`, where the
instruction reads r0 (release-on-read zeroes it) and packs r0's low halfword into r1's **high**
lane — observed as `r1 = 0x000A0037` in seed set 1, i.e. `0x000A` = 10 = r0's seed above
`0x0037` = 55 = the half-ALU result.

**Honest limitation:** this field is only weakly live in this carrier. An emitter may rely on
"any value with `(v & 7) != 6` behaves as the anchor does", which is what the dense sweep
establishes; it may **not** read this as "byte+2 selects a source register", because bits 3,4,5
are dead and no register index can live there.

---

## 4. Negative results, honest failures, and method findings — all first-class

### 4.1 The dispatch's premise was wrong for two of the eight

`falu3` and `falu3_ext` were **not** one field from emittable: `validation.json` leaves both
`op` **and** `srcB` below emitter grade. Closing `op` alone would have unblocked nothing. This
was found by checking the emittability arithmetic rather than trusting the brief, and it is why
Addendum A exists.

### 4.2 `opsel == 7` is fault-PRONE, not deterministically faulting — and the earlier "fault" label was contamination

EXP-0154 recorded the `(v & 7) == 7` class as `fault` under majority-of-3 **and** cross-run
agreement. Pooled over five independent runs here (up to **51 dispatches per value**), the
picture is finer:

* the class fails ~98% of the time, but it **does** complete occasionally, and every completion
  shows the same state;
* the failure rate is **value-selective**, which ambient sibling contamination cannot be:

| population | cases | pooled failure rate |
|---|---|---|
| `(v & 7) == 7` | 128 | **0.714 – 0.980** |
| every other value | 896 | **0.000 – 0.500** |

Nothing lies between 0.500 and 0.714. That empty gap is what the `fault-prone` classification
uses (amendment 07); it is measured, not tuned. The ok-partition — which is what the promoted
mask rule states — is unaffected: `opsel == 7` is never `ok` in any of ~50 observations per value.

### 4.3 A contaminated dispatch can report status **OK** and write nothing (`DEF-0160-5`)

**25 observations** (18 in run01, 7 in run02) came back with command-buffer status OK and **all
16 registers *and both integrity sentinels* still holding `0xDEADBEEF`** — the dispatch produced
no stores at all. No `…ErrorInnocentVictim` string fired, so the fault-classification screen
that FIELD-SWEEP-PROTOCOL §7.2 prescribes does not catch this class. A zero-initialised
read-back buffer would have recorded 25 confident `silent_zero`s. This is the strongest
practical argument for §7A's poison-buffer advice, and it is why the gate below is written the
way it is.

### 4.4 The §7A isolation mechanism was removed from the protocol mid-experiment

`experiments/NEO-TARGET-BRIEF.md` and `FIELD-SWEEP-PROTOCOL.md` §7B were revised on disk while
this experiment was running: the GPU lease is **gone** ("Concurrency: unrestricted. There is no
lease", and "a bulk sweep NEVER takes the lease"). Both gated sweeps and all six adjudication
runs therefore ran **unlocked**. The consequence is measurable and was not anticipated by §7A:
**a 5-repetition "isolated" re-run is just another unlocked run, and it manufactures faults of
its own.** `imad.srcC_desc` v=186 / seed set 2 was `silent_zero` in **both** gated runs and came
back `fault` 3/5 on re-run. An earlier version of this analysis (amendment 05) let that re-run
overrule two agreeing clean observations; it was **retracted** (amendment 06).

**What replaced it**, and the rule the promoted labels actually rest on: contamination can only
*destroy* an observation — a discarded or reset command buffer writes nothing — it can never
fabricate a complete, coherent 16-register dump that independently agrees with another run's.
So **two or more valid agreeing observations decide a case outright**, however many failures
accompany them; a failure counts only where fewer than two valid observations exist. Applied to
all 4,064 cases this produced **0 clean disagreements and 0 unresolved cases**, which is itself
evidence that the filter is sound: had it been admitting contamination, conflicting "clean"
dumps would have appeared.

### 4.5 `half_pack` is genuinely 4 bytes — H7 REFUTED

The pre-registered hypothesis was that `half_pack` is two 2-byte half-lane instructions (which
would have explained DEF-0154-1's A18 `18 05 18 03` vs G17P `18 03 18 05` as a reordering).
**It is not.** Splicing our own 2-byte `mov_imm(r6,77)` over bytes +2..+3 leaves the entire
16-register state identical to the anchor — the `mov_imm` never executes, so those bytes are
consumed by the instruction at +0. The positive control rules out a dead probe: replacing
**both** 2-byte halves with two `mov_imm`s executes both, and r6 = 77 **and** r7 = 99 appear in
the dump. So the A18↔G17P byte difference is an operand swap *inside one 4-byte instruction*
(register allocation), and db.json's length gate — byte0 `0x18` is 4 bytes only when
byte+1 == `0x05` — is simply wrong (`DEF-0160-4`).

### 4.6 Concurrency during these runs

Between six and twelve other GPU experiments were active on the neo throughout. At the moment
of the smoke capture, **32 of 40 cases were victim-class discards and 4 genuine
`…ErrorHang`s arrived from a sibling**; six agents were queued on the (then still extant) lease.
run01 saw 206 victim-flagged cases and 254 faults, run02 92 and 128. Zero GPU hangs were caused
by this experiment, and zero baseline failures occurred in either gated run. A reader should
hold this evidence as "taken under heavy concurrent load, with the contamination measured and
filtered", not as "taken on a quiet machine".

---

## 5. `imad.srcC_desc`: why it did not close, and the bigger thing behind it

### 5.1 The field is completely modelled — and is not one field

Dense 256-value sweep, two seed sets, `r0 = m(v)·(srcA·srcB) + A(v)` explains **192 of 192**
non-fault values with **0 exceptions**. This is a test rather than a fit: two seed sets give two
equations for two unknowns *plus one constraint*, so `r0(set 1) − r0(set 2)` must be either 0 or
`P₁ − P₂ = 340 − 133 = 207` and nothing else.

```
bits 0,1 = mode      00 -> product + addend      01,10 -> addend only, product suppressed
                     11 -> FAULT (64 values, unanimous across four independent runs)
bit 2    = inert
bits 3..7 = K, selecting the ADDEND SOURCE:
           K=0 -> 50432   K=1 -> 1   K=2 -> 256   K=12 -> 1   K=13 -> 16256
           K=14 -> 49045  K=15 -> 46038   all other K -> 0
```

It fails the frozen promotion rule (P4) because no single-field model in the frozen class fits:
the mask rule has 12 exceptions and 7 of 8 bits are live, which is exactly what a 2-bit mode
plus a 5-bit selector looks like when you insist on modelling it as one field.

### 5.2 The addend is **not** in the instruction (`DEF-0160-3`)

db.json says `(K<<3) = immediate addend, K in b7[3:8] + mulsel[0:3]`. Three independent
observations refute it:

1. **The `imad` bytes were lifted verbatim from a kernel whose MSL adds `12345`. Run in our
   carrier, the same bytes add `1`.** An inline immediate cannot change.
2. The recovered addends are exactly the 16-bit halves of **the carrier's own float constants**:
   `0x3F800001` (= `1.0000001f`, `carrier_dag.metal`'s multiplier) gives `A = 1` at K ∈ {1,12}
   and `A = 16256` (`0x3F80`) at K = 13; `0xB3D6BF95` (= `−1e-7f`, its other constant) gives
   `A = 49045` (`0xBF95`) at K = 14 and `A = 46038` (`0xB3D6`) at K = 15.
3. `A(v)` is seed-independent and stable across every run, so it is not stale register content.

So bits 3..7 index an **external (uniform / constant-file) addend source**. EXP-M4-13 saw K
co-vary with the source constant because the compiler allocates a slot per constant; adopted as
"the immediate is K<<3", an emitter would emit an `imad` that adds whatever happens to occupy
slot K — silently wrong code, far from its cause. And `mulsel` does not participate at all: the
`__2d_desc_mul` probe (12 × 8 × 2 seed sets) returns a single addend per `srcC_desc`, unchanged
across every `mulsel` point (`DEF-0160-7`).

### 5.3 The larger finding: `imad` has no `srcA` field in db.json (`DEF-0160-6`)

The `__2d_desc_lo` probe (12 `srcC_desc` × 11 `srcC_lo` × 2 seed sets) solves
`obs = m(desc)·(X·srcB) + A(desc>>3)` for the multiplicand `X`. It returns a **single** value per
`srcC_lo`, identical across every `srcC_desc` that keeps the product, and it tracks the register
the model names **in both seed sets**:

| `srcC_lo` | recovered multiplicand (set 1 / set 2) | register |
|---|---|---|
| `0x00`, `0x02`, `0x04` | 10 / 7 | r0 |
| `0x08` | 21 / 13 | r1 |
| `0x10` | 34 / 19 | r2 |
| `0x20` | 58 / 37 | r4 |
| `0x40` | 94 / 73 | r8 |
| `0x7f` | 0 / 0 | r15 |
| `0x01`, `0x03` | 0 / 0 | source suppressed |

**`reg = (byte+6) >> 3`, with bit 0 = 1 forcing the source to read 0, and bits 1,2 inert.**
db.json calls byte+6 `srcC_lo` — the low byte of an immediate that does not exist — and models
no `srcA` at all, so **an implementer following db.json cannot choose the first operand of an
integer multiply.** EXP-0154 labelled this byte `hardware-run` from its ok-set alone (`ok at
{0x0, 0x2, 0x4, 0x6}`) without identifying its role; those four values are exactly the ones
naming r0.

### 5.4 What a successor should do

Fix the `imad` model first, then sweep. `srcC_desc` should be split into `mode` (bits 0,1),
`reserved` (bit 2) and `addend_src` (bits 3..7); byte+6 should be renamed `srcA`; and the
"immediate addend" text should be replaced by the external-source reading. A sweep against the
corrected descriptor is meaningful; a sweep against the current one is not — which is
FIELD-SWEEP-PROTOCOL §6's point exactly.

---

## 6. Limitations and what is NOT claimed

* **Compute stage only, grid 1, threadgroup 1.** Nothing here says anything about the fragment
  or vertex stages, or about wider dispatches.
* **One carrier per arm.** Every verdict is stated against the block lifted from that arm's
  probe kernel. `half_pack.src` in particular is only weakly live in its carrier (§3.6), and
  `falu3_ext.srcB`'s seed set 1 is **not** live for the field at all because `saturate` clamps
  the result — which is why that one field rests on the full-state prediction route rather than
  the signature comparison (amendment 08).
* **`opsel == 7` is bounded, not explained.** We know it fails ~98% of dispatches and what state
  the rare completion leaves; we do not know why, and we did not chase it.
* **`falu3` opsel 3 is unidentified.** The destination is a real, reproducible value in both
  seed sets that no function in our library matches. Recorded, not guessed.
* **`imad`'s addend source space is not characterized.** We know K selects an external source
  and what four of its slots contained *in this carrier*; we did not vary the uniform file, so
  the index→slot mapping is `INFERRED`, not measured.
* **The 3 dead bits of `half_pack.src` and the 4 of `iminmax.srcB` are inert *in these
  carriers*.** That is a strong statement about an emitter's freedom in the tested range; it is
  not proof that they are inert in every carrier.
* **G17P only.** These are direct G17P measurements. Nothing here is promoted to M4/G16G, and
  no M4 result is relabelled.

## 7. Verdict

**9 of the 10 blocking fields move to `hardware-run` on G17P; 7 of the 8 dispatched
instructions become emittable.** `imad` remains blocked, and the reason is a descriptor defect
rather than a sweep gap: `srcC_desc` is a 2-bit mode plus a 5-bit selector for an addend that
lives outside the instruction, and the byte db.json calls `srcC_lo` is the unmodelled first
multiplicand.

Per-field verdicts in FIELD-SWEEP-PROTOCOL §5 schema, with the class tables, register models,
per-value observation counts, and the seven `db_defects`, are in
`analysis/field_verdicts.json`. `tools/agx-isa/db.json`, `tools/agx-isa/validation.json`,
`docs/` and `PROVENANCE.md` were **not** edited, and nothing was committed.
