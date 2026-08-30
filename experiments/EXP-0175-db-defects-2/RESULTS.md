# EXP-0175 — RESULTS

**Type: desk experiment, NO device work.** Nothing was dispatched to the neo (a device
experiment was live there and was not disturbed), to the M4 GPU, or to M5. `macvdmtool` was
not invoked. Every input is committed evidence already in this repository.

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (re-analysis of committed evidence) + PUBLIC
Inputs: experiments/EXP-0171-g17p-ilogic-srca/raw/** (the observed behaviour of OUR OWN
        compiled shaders, spliced by our own tools, run on our own harness on G17P),
        experiments/EXP-0174-g17p-n3mov/raw/** (likewise), tools/agx-isa/{db.json,
        validation.json}, experiments/EXP-M4-13-full-corpus/hex/**.
Apple binary introspection: NONE.
Reproduction: README.md → Commands
Evidence: analysis/def1_rederived.json, def2_def5_rederived.json, def3_rederived.json,
          def4_rederived.json, def0174_1_rederived.json, ab_metrics.json,
          orphan_report.txt, orphaned_validation_rows.json, operand_defects.json,
          operand_report.txt, validate_after.txt
```

---

## 0. Headline

**All six defects survived re-derivation. None was withdrawn — but two came back with a
correction, and the re-derivation found things the source experiments did not report.**

| | |
|---|---|
| defects re-derived | **6 of 6 CONFIRMED**, 0 withdrawn (DEF-0171-1…-5 **+ DEF-0174-1**) |
| corrections to EXP-0171's own statements | **2** (DEF-0171-2's scope; a new byte0 bit-3 don't-care under DEF-0171-1) |
| new defects found while re-deriving | **2** (`DEF-0175-1` `mov_zext16`'s match; `DEF-0175-2` the A/B gate this project has been using) |
| `db.json` | 172 instructions (**unchanged**), 1062 → **1036** fields; sha `322847609de7…` → `a77f8cfa163f…` |
| corpus | **833/1080 clean, 388,604 leftover — IDENTICAL**, tokens 25,419 identical |
| decode change | **7 real corpus instructions** reclassified `b_alu10_lof` → `ilogic`, population conserved |
| round trip | **302 OK / 0 FAIL / ALL PASS** (identical count to baseline; needed a fixture patch, §6) |
| `validate_labels.py` | **exit 1 — 34 FAILs, ALL mechanical**, listed in §4.3; this is the orchestrator's follow-up |
| `ibfe` closure | **recommend NO** — and one of its two promotions is weaker than EXP-0171 stated (§3) |
| the full `ilogic`+`b_alu10_*` merge | measured, corpus-neutral, **NOT landed** — the evidence does not reach it (§2.6) |
| **DEF-0174-1 (`n3_mov` byte+1 one bit off)** | **re-derived and LANDED** — the merge blocker is cleared (§1.6, §2.7) |

---

## 1. What was directly OBSERVED — the six re-derivations

Each verdict below is computed by a script that reads the source experiment's `raw/` and
nothing else; the comparison against its `RESULTS.md` happened only afterwards. §1.1–§1.5 come
from EXP-0171's two gated runs (`g17p_20260830_run01` forward, `run02` reverse, one frozen
matrix, sha `bce0b7de…`); §1.6 comes from EXP-0174's two gated runs × two register plans.
Every re-derivation reports how many cases it dropped as invalid (**0**, in every arm used
here).

### 1.1 DEF-0171-1 — `ilogic` byte0 is `(dst << 4) | 0x0b` — **CONFIRMED**

`analysis/rederive_def1.py` → `analysis/def1_rederived.json`.

256 byte-0 target cases per run on the SYNTH 16-GPR-dump carrier. The anchor computes
`93 & 107 = 73 (0x49)` into r2. For each swept byte0 `v`, which GPRs hold 73:

| byte0 | expected `v>>4` | run01 | run02 |
|---|---|---|---|
| `0x0b` … `0xeb` | r0 … r14 | **exactly r(v>>4), 15 of 15** | **exactly r(v>>4), 15 of 15** |
| `0xfb` | r15 | not observable | not observable |

**0 misses in either run.** r15 is unobservable *in this carrier by construction* — it is the
harness's own `device_store` index register, re-seeded before every dump — so the honest
range is 0..14, not 0..15. Refuters R1a (result stays in r2) and R1b (runs disagree) did not
fire.

> **NEW, and EXP-0171 saw only one instance of it: byte0 BIT 3 is a DON'T-CARE here.**
> My pre-registered R1c asked whether `0x0b` is really the discriminator. It is not the whole
> story. **Low nibble `0x3` shows the identical `dst<<4` behaviour for 15 of 16 destinations**,
> and `23 03 1f 01 00 00 00 80 00 00` reproduces the anchor's **byte-identical 16-register
> state**. EXP-0171 noted `0x23` in one line as "a second low nibble reaching the same
> datapath, not chased here"; it is the entire low-nibble-3 family, in both runs.
> **Not folded into the match**, and the reason is recorded in `db.json`: byte0 low nibble 3
> is a populated, separately HW-validated group (`n3_mov`, `mov_zext16`, `n3_addr_prep`), and
> the observation was made at a single byte+2 value (`0x1f`). What bit 3 selects is `UNKNOWN`.

### 1.2 DEF-0171-4 — `outmod` bit 7 is a SOURCE-READ control — **CONFIRMED**

`analysis/rederive_def4.py` → `analysis/def4_rederived.json`. Dense byte+7 sweep, five NAT
store-consumed carriers plus SYNTH and FRAME, both runs:

| carrier | bit 7 SET (128 values) | bit 7 CLEAR (128 values) |
|---|---|---|
| `NAT:k_and` / `k_or` / `k_xor` / `k_andn` | the correct boolean result | `0x00000000`, ×128 |
| **`NAT:k_nand`** | `~(a & b)` | **`0xFFFFFFFF`, ×128** |
| `SYNTH:k_and`, `FRAME:k_and` | unchanged | **unchanged — inert** |

On **every** bit-7-clear case `poison_out == 0` and `sentinel_bad == false`: the store ran and
wrote something. The pre-registered discriminator fired exactly as designed — a flag that
zeroed the **output** gives `0` for nand too; `0xFFFFFFFF` is `~(0 & 0)`, so the LUT evaluated
and the destination was written and it is **both sources** that read as zero. Identical in
both runs.

### 1.3 DEF-0171-3 — `ibfe.sign_ext` is not the sign control — **CONFIRMED**

`analysis/rederive_def3_and_ibfe.py` → `analysis/def3_rederived.json`. A5 sub-field
decomposition over the dense byte+6 sweep, re-implemented here rather than imported from
EXP-0171's analysis code:

| carrier | `sign_ext` sub-values moved | detection power (whole byte+6) |
|---|---|---|
| `NAT:k_bfe` (unsigned anchor) | **0 of 2** | 254 of 256 |
| `NAT:k_bfe_s` (**signed** anchor) | **0 of 2** | 254 of 256 |
| `SYNTH:k_bfe` | **0 of 2** | 254 of 256 |

Both runs. Inert in the **signed** anchor is the decisive half: the bit `db.json` named as the
sign control does nothing in the program that is actually signed, on a byte where 254 of 256
values do change the observable. Where the two anchors *do* differ, byte for byte:

```
unsigned k_bfe  : a7 00 56 04 02 00 10 00 f0 11 61 00
signed   k_bfe_s: a7 00 56 02 03 00 12 00 f0 10 61 00
                          +3    +4    +6          +9
```

byte+9 (`srcC_flags`) `0x11 → 0x10` is the surviving candidate, and it is **`INFERRED`** —
byte+9 was not swept in that matrix.

### 1.4 DEF-0171-2 — no length rule for byte0 `0x31` — **CONFIRMED, with a scope correction**

`analysis/rederive_def2_def5.py` → `analysis/def2_def5_rederived.json`. All three G17P bfloat
anchors, fed to the live `isadb.decode_one`:

```
31 00 1c 00 11 00 c0 81        -> unknown instruction length at offset 0 (byte0=0x31)
31 00 1d 00 11 00 c0 81        -> unknown instruction length at offset 0 (byte0=0x31)
31 00 1e 00 86 02 10 00 c0 81  -> unknown instruction length at offset 0 (byte0=0x31)
```

`bf_fma_dst.fmt`'s enum `{2: bf, 4: bf2}` does not contain the emitted `0x00`. Both halves of
the defect hold.

> **The scope correction, and it changes who fixes it.** EXP-0171 presented this as
> "`bf_alu`'s match and `bf_fma_dst.fmt`'s enum do not describe what G17P emits". They do not —
> but that is **not why the bytes fail to tokenize**. The blocker is the **length rule in
> `isadb.py`**: its low-nibble-1 bfloat branch is gated on `byte+1 ∈ {0x02, 0x04}` and G17P
> emits `byte+1 == 0x00`. Given a length, the bytes are already claimed **correctly and
> unambiguously** by the dst-parameterised siblings, which I measured rather than assumed:
>
> | anchor | winning descriptor (match bits) | runner-up |
> |---|---|---|
> | `31 00 1c …` | **`bf_add_dst`** (12) | `bf_alu8_var` (4) |
> | `31 00 1d …` | **`bf_mul_dst`** (12) | `bf_alu8_var` (4) |
> | `31 00 1e …` | **`bf_fma_dst`** (12) | `bf_alu8_var` (4) |
>
> So the `db.json` half of this defect is only the enum. `isadb.py` has a different owner and
> the change is **reported, not made** (§5.2).

### 1.5 DEF-0171-5 — `fspecial_est.subop == 0x0f` — **CONFIRMED, and it is stronger than reported**

G17P's precise `rsqrt` anchor is `09 83 25 0f 00 c2`; byte+3 is `0x0f`; the enum listed
`{9, 11, 13}`. I also checked the thing EXP-0171 did not: **is `0x0f` legal under the
descriptor's own match?** The `fspecial_est` match pins byte+3's high nibble to 0, bit 0 to 1
and bit 3 to 1, leaving exactly **two free bits** — so the legal set is
`{0x09, 0x0b, 0x0d, 0x0f}` and `0x0f` is not an anomaly, it is **the fourth member of a
four-member field**. The enum was 3 of 4 complete.


### 1.6 DEF-0174-1 — `n3_mov`'s byte+1 is modelled one bit off — **CONFIRMED**

Dispatched mid-experiment as the highest-priority item: it blocks the merge of EXP-0174's
register-allocator result, because `work/merge_verdicts.py`'s bit-span guard refused a
verdict row claiming `start=8 width=8` against a descriptor saying `width=7`. **The guard
did its job** — so the descriptor had to be corrected, not the guard relaxed.

`analysis/rederive_def0174_1.py` → `analysis/def0174_1_rederived.json`. Arm `B/srcmap`,
dense byte+1 0..255, **two register plans × two gated runs**. Rather than checking
EXP-0174's model, I fitted **both** models against a host-computed oracle on the same data
and let them compete:

| | run01 idx15 | run01 idx7 | run02 idx15 | run02 idx7 |
|---|---:|---:|---:|---:|
| aliasing: byte+1 `v` vs `v+128` give identical 16-register dumps | **128/128** | 128/128 | 128/128 | 128/128 |
| **db.json** model, `S = byte+1 & 0x7f` | **3/32** | 3/32 | 3/32 | 3/32 |
| **EXP-0174** model, `S = bits 1..7`, `hs = bit 0`, 16-bit granular | **32/32** | 32/32 | 32/32 | 32/32 |
| bit 0 = 1 predicted as a HIGH-half read | 16/16 | 16/16 | 16/16 | 16/16 |

**The 16-bit granularity fell out of my own oracle rather than being assumed.** My first
pass scored the naive whole-32-bit-register reading and got **15 of 16** — the single
failure being `byte+1 = 18`, source r9, the *only* seeded register with a non-zero high
half (`0x40200000`). Reading its **low** half gives 0, which is exactly what the hardware
wrote. One decisive case, and it is the one that discriminates.

So: byte+1 is `(S << 1) | hs`, `S` = bits 1..7, `hs` = bit 0 = which 16-bit half of the
source is read; bit 7 is register bit 6 and looks inert only because of the mod-64 aliasing;
**no uniform file is reachable through that byte at any of the 256 values.** An emitter
following the old descriptor wrote `S` into bits 0..6, which the hardware reads as register
`S>>1` with half-select `S&1` — **wrong register and wrong half, silently, no fault.**

---

## 2. What was CHANGED in `db.json`

`tools/agx-isa/db.json`, sha `322847609de79055…` → `7701797ec5c07182ec1d44a35e2ba08332ff382c5ef77390920d1d07597f2e6d`.
Applied by `analysis/apply_defects.py`, which asserts the pre-state of every field it touches.

### 2.1 DEF-0171-1 (the structural one)

| | before | after |
|---|---|---|
| `ilogic.match` | `[[0,8,11],[17,7,15]]` — byte0 pinned to the full byte `0x0b` | `[[0,4,11],[17,7,15]]` — the low nibble |
| `ilogic` fields | **no destination field at all** | `dst` `{start:4, width:4, type:"reg"}` |

An implementer following the old descriptor could only ever write `ilogic` to **r0**; every
other destination fell through to `b_alu10_lof`/`loe`. The semantics record the measurement,
the r15 caveat, and the unmodelled byte0 bit-3 don't-care. `b_alu10_lof` / `b_alu10_loe` gain
a note saying they are the same instruction at `opsel_hi == 1`, **and** a warning for label
auditors that their `hardware-run` rows are aliases (§2.6).

### 2.2 DEF-0171-4, -3, -5, -2 (semantics, enums)

* `ilogic.outmod`, `b_alu10_lof.outmod`, `b_alu10_loe.outmod`: enum
  `{128: "output/store"}` → `{128: "sources-read-enable (NOT an output/store flag)"}`, with the
  nand discriminator, the five carriers, the fresh-process reproduction, the
  not-excluded alternative, and the actionable emitter rule.
* `ibfe`: `sign_ext` is not the sign control; the two anchors' byte-for-byte difference; the
  `srcC_flags` attribution marked `INFERRED`; and the `b2_bit0` detection-power caveat (§3).
* `fspecial_est.subop`: enum gains `15`, plus the four-member legal set and an explicit
  **range caveat** — `validation.json` records "256 of 256 sub-values" for a field with 4 legal
  values.
* `bf_add_dst.fmt`, `bf_mul_dst.fmt`, `bf_fma_dst.fmt`: enum gains `0`; all four bfloat
  descriptors record the length-rule gap and who owns it.

### 2.3 The fold (Task 2) — 25 fields into `match`

Every one of the 25 has **zero free bits**: its span is entirely pinned by its own descriptor's
`match`, so there is exactly one legal value. The name, span, type, pinned value and any enum
are preserved in a new **`match_notes`** block on each of the 19 affected descriptors, so no
documentation is lost. The 34 *partially* pinned rows were **not** touched — they have real
choosable bits.

### 2.4 The measured arithmetic (Task 2's verification)

EXP-0173 predicted **627/1062 → ~611/1037, instruction count unchanged**. Measured against the
live `validation.json`:

| | before | after (fold only) | after (fold + DEF-0171-1) |
|---|---:|---:|---:|
| total fields | 1062 | **1037** | 1036 |
| emitter-grade (`hardware-run` + `isolated-byte-diff`) | 627 | **611** | 612 |
| instructions | 172 | 172 | **172** |

(the right-hand column is the final live state, i.e. the fold **plus** DEF-0171-1's new
`ilogic.dst` **minus** DEF-0174-1's two `srcA_uni` deletions: 1062 − 25 + 1 − 2 = 1036)

**EXP-0173's arithmetic is exactly right.** The extra `+1/+1` is DEF-0171-1's new `ilogic.dst`
row, which I recommend at `hardware-run` (§4.3). Per label:

| label | before | after | delta |
|---|---:|---:|---:|
| `hardware-run` | 541 | 527 | −14 |
| `isolated-byte-diff` | 86 | 85 | −1 |
| `corpus-correlation` | 80 | 78 | −2 |
| `tokenization-only` | 143 | 138 | −5 |
| `single-template-inference` | 27 | 27 | 0 |
| `untested` | 185 | 183 | −2 |

`match_overlap_report.py`: **59 overlapping rows → 34; zero-free-bit 25 → 0; vacuous
emitter-grade 16 → 0.**

### 2.5 The decode change, accounted for byte-for-byte

Widening `ilogic`'s byte0 match moves **exactly 7 real corpus instructions** from
`b_alu10_lof` to `ilogic` (182 → 175 and 16 → 23; population conserved, length unchanged at 10):

| file | offset | bytes | dst |
|---|---:|---|---:|
| `conversions_pack__cvt_f2i__compute.hex` | 164 | `2b051fff100200000000` | r2 |
| `dec2_n6_deriv__rq_pred__compute.hex` | 496 | `5b0b1f13000200800000` | r5 |
| `raytracing__rt_extended_limits__compute.hex` | 760 | `5b071f0b000200800000` | r5 |
| `raytracing__rt_mask_intersect__compute.hex` | 746 | `5b591fff100200200000` | r5 |
| `raytracing__rt_query_candidate_getters__compute.hex` | 498 | `8b0f1f00020a00000000` | r8 |
| `raytracing__rt_query_committed_getters__compute.hex` | 494 | `6b0d1f00020a00000000` | r6 |
| `raytracing__rt_query_params__compute.hex` | 772 | `cb191f01000200000000` | r12 |

All seven are byte+2 `0x1f` — `ilogic`'s own and/or base — with a non-zero destination. They
were the defect.

### 2.6 The full merge — measured, and NOT landed

Merging `ilogic` + `b_alu10_lof` + `b_alu10_loe` into one descriptor is **corpus-neutral and
population-conserving**: 833/1080 clean, 388,604 leftover, 25,419 tokens, and
`b_alu10_lof 175→0`, `b_alu10_loe 52→0`, `ilogic 23→250`. It is left for the orchestrator, for
two reasons that the green gate does not cover:

1. **The hardware evidence does not reach it.** EXP-0171 swept `ilogic` at `opsel_hi == 1`
   only, and *reported the same cases under both key sets*. Nothing in its raw exercises
   `opsel_hi ∈ {2,3,4,6,8,12}`. A merged descriptor would apply `ilogic`'s **LUT2 field names**
   (`lut_a_sel`, `lut_a_free`, `lut_a_z`, `lut_b`, `srcB`) to six op-select families that were
   never touched — precisely the "do not carry an operand model across families" error
   EXP-0139 and EXP-0138 both record.
2. It orphans **24 validation.json rows** across two whole mnemonics, and the two `ilogic`
   round-trip fixtures fail on the added `opsel_hi` key.

**Consequence for the label owner either way:** `b_alu10_lof.*` and `b_alu10_loe.*` currently
carry nine `hardware-run` / `isolated-byte-diff` rows each that are **aliases of the `ilogic`
sweep at `opsel_hi == 1`**. That is now written into both descriptors' semantics. If the merge
is rejected, those rows are claims about one op-select value wearing a family-wide label.


### 2.7 DEF-0174-1 applied — and the "three descriptors" claim checked, not assumed

The dispatch said the byte+1 layout is shared by `frame_marker` **and** `mov_zext16`, so
fixing it once likely fixes three descriptors. **Two of three. `mov_zext16` must not be
touched, and its own committed evidence says why.**

| descriptor | change | evidence status |
|---|---|---|
| **`n3_mov`** | `srcA_reg` 7 → **8 bits** at byte+1 (`(S<<1)\|half`); `srcA_uni` **deleted** | `hardware-run`, G17P, re-derived §1.6 |
| **`frame_marker`** | same | **`STRUCTURAL`/`INFERRED` — flagged as such in the descriptor.** EXP-0174 swept `n3_mov`; it did **not** sweep `frame_marker`. Its fields were copied from the same wrong model, so the correction follows; nothing has executed a `frame_marker` with a chosen source register |
| **`mov_zext16`** | **NO field change** — a relationship note only | Its byte+1 is a *different* field (`src_flag`, one 8-bit byte) and is **HW-tested INERT over all 256 values in two independent register forms** (EXP-0161, re-derived EXP-0165); EXP-0174 reconfirms `93 0a 00 01` leaves r5 untouched. That is consistent — an operand byte the **narrow** sub-form does not read looks exactly like an inert byte. Copying the move sub-form's operand model here without a sweep would be a fresh defect |

Making `srcA_reg` **one 8-bit operand descriptor** is not a compromise for the guard's
benefit — it is the **house convention**: every other 8-bit operand byte in this database
(`falu2.srcA`, `ibfe.srcA`, `ilogic.srcA`, `fspecial_est.srcA`, …) is modelled as one 8-bit
`reg` under `(reg<<1)|size`, and `hs` **is** that convention's size bit. It also matches
EXP-0174's own verdict row (`start=8, width=8`), so the guard passes.

**`srcA_uni` is deleted rather than kept**, because keeping a 1-bit field at bit 15 *inside*
an 8-bit field at bits 8..15 would be a self-overlap — the very defect class Task 2 just
cleared. Its evidence is not lost: EXP-0174's own `srcA_uni` verdict says *"byte+1 bit 7 is
SOURCE-REGISTER BIT 6, not a uniform-file selector"*, which belongs in `srcA_reg`'s note and
is now there. **That does orphan the two `srcA_uni` rows** — listed in §4.3.

Also applied from the same experiment, semantics and enums only (no field boundaries, so no
new orphans):

* **DEF-0174-2** — byte+2 is an **op selector** (narrow / move / xor / or) with a
  source-release bit at `0x08`, not a "source-class/size sub-form"; byte+3 bit 0 is the
  **destination-half select** and the other half is preserved, not a "companion /
  second-operand descriptor". Established over the complete 256 × 256 cross-product,
  65,536 encodings, three runs.
* **The emitter-ready encoding** is written into `n3_mov`'s semantics verbatim, including
  the fact that **a 32-bit copy is two instructions** — an ABI fact, not a footnote.
* **DEF-0174-4** — `reg_move_c0`'s standing claim *"AS OF 2026-08-28 NO VALIDATED
  GPR-TO-GPR MOVE EXISTS ON APPLE9"* is now false and is marked **`SUPERSEDED`** with the
  corrector cited. Per `CODEX.md` §8 the earlier record is **preserved and labelled**, not
  deleted. The weaker `reg_move_c1` observation is recorded as **OBSERVATION, NOT SWEPT**,
  together with the reason EXP-0090's negative is suspect (it used `device_load`, now known
  asynchronous — DEF-0169-1).
* **DEF-0174-3** — `pad_operand`'s contradicting observation (`X0 (2S) 00 01` writes `r[S]`
  into `r[X]`) is recorded **without acting on it**, as instructed. Note for the label
  owner: its phrase *"NOT A STANDALONE HARDWARE OPCODE"* is **checked by
  `validate_labels.py` check 9** against `emitter_role: "data-word"`, and changing the
  classification would move the emittability denominator. Both are left exactly as they
  are; only a note was added, and check 9 still passes.

Gate: corpus **833/1080, 388,604 leftover, 25,419 tokens — unchanged, zero firing delta**
(field boundaries do not affect matching or length); round trip **ALL PASS**.

---

## 3. `ibfe` — my read, and it is NO

EXP-0171 flagged that `ibfe` closes **only** if `ibfe.sign_ext` and `ibfe.b2_bit0` are promoted
from *proven inertness*. The standing rule is that proven-inert-with-unknown-role earns
`single-template-inference`, **not** emitter grade, because emitter grade asserts an implementer
may *choose* the value. I pre-registered a decision rule before looking: emitter grade for an
inert field only if inertness holds across **≥2 carrier styles AND ≥2 independent
compiler-emitted anchors differing in the dimension the field is named for**, *and* the field's
role is known or bounded.

**What the evidence actually is** (`analysis/def3_rederived.json`):

| field | styles with **measured detection power on that byte** | anchors | role |
|---|---|---|---|
| `sign_ext` (byte+6 bit 1) | **2** — NAT 254/256, SYNTH 254/256 | 2 (`k_bfe`, `k_bfe_s`) | **UNKNOWN** — proven *not* to be what it is named |
| `b2_bit0` (byte+2 bit 0) | **1** — NAT 128/256; **SYNTH moves 0 of 256** | 2 | **UNKNOWN** |

Two findings, and the second is new:

1. **`sign_ext` clears the mechanical bar and still should not be promoted.** Its role is
   unknown; the experiment proved the *named* role false. The sweep shows the bit does not
   matter *in these templates*; with no model of what it does, nothing bounds the conditions
   under which it becomes live. This is the same shape as `falu2`'s register top bit —
   "HW-tested inert with its role still unknown" (`docs/evidence-classification.md` §1).
   Recommendation: **`single-template-inference`**, with the honest note that it is at the top
   of that band (2 anchors, 3 carriers, both runs), not the bottom.
2. **`b2_bit0`'s promotion is weaker than EXP-0171 stated, and its own raw shows it.**
   EXP-0171's rule requires ≥2 carrier styles. On **byte+2** the SYNTH carrier has **zero
   detection power** — 0 of 256 whole-byte values move — so it cannot report inertness there
   at all; it reports nothing. Only NAT has power. Once the blind style is discounted, the
   promotion rests on **one carrier style**, and EXP-0171's own criterion is not met.

**Verdict: `ibfe` does NOT close.** Both rows are currently `isolated-byte-diff` in the live
`validation.json` (the merge already landed), and `ibfe` is in `emittable_mnemonics`. I did not
edit that file. **Recommended: downgrade both to `single-template-inference`**, which drops
`ibfe` out of the emittable set — and `b2_bit0` is the one to downgrade first.

---

## 4. Gate results

### 4.1 Corpus — the real check

| tree | clean | strict leftover | tokens | round trip |
|---|---|---:|---:|---|
| `work/pre` (HEAD, sha `322847609de7…`) | 833/1080 | 388,604 | 25,419 | 302 OK / 0 FAIL / ALL PASS |
| **live, after every EXP-0175 edit** | **833/1080** | **388,604** | **25,419** | **302 OK / 0 FAIL / ALL PASS** |

Only firing delta: the 7 instructions of §2.5. The fold changes **no byte** — a zero-free-bit
field contributes no encodable bit, which is why it was not a field.

### 4.2 `emit_worklist.py`, `match_overlap_report.py`

Both run. Overlap 59 → 34, zero-free-bit 25 → **0**, vacuous emitter-grade 16 → **0**.

### 4.3 `validate_labels.py` — **exit 1, and this one is yours**

`analysis/validate_after.txt`. **34 FAILs, every one mechanical and expected, and nothing else:**

* **25** `not a field of this db.json descriptor` — the folded rows;
* **2** more of the same — `n3_mov.srcA_uni` and `frame_marker.srcA_uni`, deleted by
  DEF-0174-1 (§2.7). These are **not** folds and are tagged `"defect_class": "DEF-0174-1"`
  in the JSON so they are not mistaken for one;
* **1** `instructions[ilogic].dst: MISSING label for a db.json field`;
* **6** `coverage.by_label` / `total_fields` count mismatches.

`analysis/orphaned_validation_rows.json` also carries a **`respanned_rows`** block —
`n3_mov.srcA_reg` and `frame_marker.srcA_reg` went from `(start 8, width 7)` to
`(start 8, width 8)`. Those rows are **kept**, not orphaned, but any pending verdict must be
re-checked against the new span. This is the block that unblocks EXP-0174's merge.

Plus the `db_sha256` WARN, which is yours to clear.

This is the one gate in my dispatch I could not leave green, and the reason is structural: the
fold you asked for orphans rows in a file you told me not to edit. Everything needed is in
**`analysis/orphaned_validation_rows.json`** — each orphan with its current label, range,
target, evidence, its pinned value, and where the name is preserved in `db.json`; plus the one
created row with a recommended label and its justification. `analysis/orphan_report.txt` is the
same thing as a table.

The created row, recommended:

```json
"ilogic": {"dst": {"label": "hardware-run",
                   "range": "0..14 dense (15 of 16 destination nibbles; 0x?b byte0)",
                   "target": "G17P",
                   "evidence": ["EXP-0171", "EXP-0175"]}}
```

`0..14`, not `0..15`: r15 was unobservable in that carrier by construction, and EXP-0168
separately found r15 is not writable through a 4-bit `dst` nibble. Claiming 16 would be the
kind of quiet over-reach this project keeps having to retract.

**16 of the 25 orphans carried an emitter-grade label** — the vacuous claims EXP-0173 named:
`falu2_uni.uni_mode`, `rt_intersect.subop`, `ray_move.form`, `iter.c7`, `irotate.b1`,
`pack_convert.fmt_class`, `link_save_restore.{b1,marker,scope}`, `cvt_bf16.{fmt,src}`,
`packed_half2_hi.opsel`, `ray_move_copy6.form`, `ray_move_zero6.form`,
`rtq_state_move.{b3,form}`.

---

## 5. New defects found while doing this

### 5.1 `DEF-0175-1` — `mov_zext16`'s match does not encode its own HW-validated accept rule

Found by my pre-registered R1c. `mov_zext16`'s match is `[[0,4,3],[24,3,1]]` — it says nothing
about byte+2, while its **own committed semantics** record the HW-measured rule
`(byte+2 & 0xC7) == 0x00`, 8 of 256 values (EXP-0161, re-derived EXP-0165). So the descriptor
claims byte+2 values the hardware does not accept — including `0x1f`, which is `ilogic`'s
op-select. `23 03 1f 01 …` currently decodes as a 4-byte `mov_zext16` while the hardware, in
EXP-0171's carrier, executed a 10-byte logic op.

Measured candidate (`work/cand_zext`, match `+[[16,3,0],[22,2,0]]`): corpus **neutral**
(833/1080, 388,604), round trip ALL PASS, population conserved — but with **150
reclassifications in two directions**:

* **80** `mov_zext16` → `n3_mov` (e.g. `83 84 21 c1`, byte+2 `0x21`, correctly rejected — these
  are not the zero-extend);
* **70** `frame_marker` → `mov_zext16` (all `43 00 00 01`), because the extra match bits raise
  `mov_zext16`'s specificity from 7 to 12 and it now outranks `frame_marker`'s 8.

The second direction is an **unresolved `0x43` collision** — `frame_marker` matches byte0
`0x43` exactly, while EXP-0161's sweep says `0xN3` narrows `r[N]` for N = 0..10. The corpus
cannot adjudicate it (clean and leftover are identical either way). **NOT landed**; it needs
its own experiment and its own pre-registration.

### 5.2 `isadb.py`'s length rule for byte0 `0x31` — reported, not patched

Per §1.4 the one-line fix is in the low-nibble-1 branch's `byte+1 ∈ {0x02,0x04}` gate. It is
another file's owner and it would change decode for a family wider than `0x31`, so it is not
mine to slip in. The descriptors are already correct.

### 5.3 `DEF-0175-2` — the A/B gate this project has been using is wrong for more than one tree

`analysis/ab_gate.py`, inherited verbatim from `EXP-0165/analysis/ab_gate.py`, ran
`roundtrip_test.py` **in-process** via `runpy`. `roundtrip_test.py` does `import isadb`, so the
**first** tree measured wins the `isadb` entry in `sys.modules` and every later tree silently
re-measures the first tree's database. It also swallowed real crashes.

This is not a theoretical objection — it fired here. `cand_all` and `cand_merge` were both
reported `ALLPASS=True` while, run honestly, `cand_all` **crashed** (`KeyError` from
`assemble`) and had 2 `[FAIL]`s. My copy now runs each tree in a subprocess; re-running
`cand_merge` under the fixed gate immediately reported `OK=199 FAIL=2 crash=1 ALLPASS=False`.
**Any A/B measurement in EXP-0162 / EXP-0165 or later that used this script and reports a
candidate's round-trip result is measuring the baseline, not the candidate.** The corpus half
of that script is unaffected — it uses a per-tree module loaded under a unique name.

---

## 6. Collateral edits outside `db.json` — both forced, both minimal

1. **`tools/agx-isa/roundtrip_test.py`** (pre-image kept at `work/roundtrip_test.py.before`).
   The SYNTH fixture list hard-codes field names. After the fold it **crashed**
   (`rt_intersect: unknown field(s) ['subop']`) and two `ilogic` cases failed on the new `dst`
   key. I removed five folded keys (`rt_intersect.subop`, `rt_transform_test.{marker,subop,
   cmpmode}`, `ray_move.form`) and added `dst: 0x0` to the two `ilogic` cases. **Fixture keys
   only — every assembled byte string is unchanged** (`d4ea90a68b000000`, `e2952781227a0382207c`,
   `0b051f01000000800000`, … all identical), and a comment records why. 302 OK / 0 FAIL, the
   same count as baseline.
2. **`analysis/ab_gate.py`** — §5.3.

Nothing else outside `db.json` was written. `validation.json`, `docs/`, `PROVENANCE.md`,
`docs/P0-P1-CLOSURE.md` and every other experiment directory are untouched. Nothing was
committed.

---

## 7. Task 3 — the wrong-operand class, enumerated

`analysis/operand_defects.py` → **`analysis/operand_defects.json`** (and
`operand_defects_prefix.json`, the same hunt against the pre-fold tree). Ranked with emittable
instructions first, then by severity.

**Why it has to be structural:** this whole class is invisible to `roundtrip_test.py`.
EXP-0170 proved that suite passes against an assembler that **cannot clear a bit**; EXP-0173
proved it also passes with `falu3.srcA` and `srcB` **swapped**.

**Method.** Every field whose *name* implies an operand (`src*`, `dst*`, `*_reg`, `operand*`,
`srcA/B/C`, `addend`, `coord`, `index`, `usrc`, …), minus names that merely contain such a word
while denoting a flag (`*_imm`, `*_class`, `*_flag`, `*_mask`, …). For each: how many bits of
its span its own `match` leaves free, exactly which bits are pinned and to what, its declared
width, its type, its `validation.json` label and range, and whether the instruction is
emittable. Cross-checked against the register-file facts in `docs/isa/README.md`, which are
carried in the JSON's `_meta` so a reader does not have to trust me for them: **96 GPRs**, hard
boundary; operand bytes are `(reg<<1)|size` so **7 register bits** are needed to span r0..r127;
`fspecial`'s `reg = (byte+3) >> 1` maps 0..191 onto r0..r95; a **4-bit nibble reaches r0..r15
only** and r15 is not writable through it (EXP-0168); and aliasing period is **family-specific**
— mod-64 on `falu2`, **not** on `iadd2.dst`, **period 16** on the fragment stage for
`tex_sample.coord`.

**Validation of the method: it reproduces the four accidental finds.** Run against the pre-fold
tree, `cvt_bf16.src` comes back as `A-fully-pinned` (8 declared bits, **0** free — it cannot be
the source it names); `cvt_f2h_dst.src` as `B`+`C`+`G`; `falu2_uni.usrc` as `B`; `imad` as `E`.
The fourth, `fspecial`'s operand swap, is **already fixed** — EXP-0165 re-pointed `dst`/`src`/
`src_ext` at byte+3 / byte+5 / byte+1-hi — so it correctly does *not* appear.

### 7.1 The classes, and what is in each

| class | rows | in emittable | what it means |
|---|---:|---:|---|
| `A` fully pinned | 0 (was **1**) | — | zero free bits: cannot select anything. `cvt_bf16.src` was the only one; **the Task-2 fold resolved it.** |
| `B` declares more than it can choose | 2 | 1 | declared width > free bits |
| `C` cannot address the file | 1 | 1 | an 8-bit operand byte with < 7 free bits |
| `D` nibble compaction | 69 | 22 | a 4-bit register field: r0..r15 **only** — recorded, not a defect |
| `E` named in the descriptor's own text, absent from `fields` | 8 | 0 | the `imad` class |
| `F` operand name, non-operand type | 9 | 5 | the name promises an operand the `type` denies |
| `G` range claims more values than encodable | 6 | 4 | a **`validation.json` range-string** defect, not an encoding error |
| `H` self-declared operand swap | 2 | 0 | the descriptor's own text already says the names are backwards |

### 7.2 The ranked head — everything inside the emittable set

| instr | field | w | free | label | class |
|---|---|---:|---:|---|---|
| **`cvt_f2h_dst`** | **`src`** | 8 | **4** | `hardware-run` | **B + C + G + F** |
| `bf_add_dst` | `dst` | 4 | 4 | `hardware-run` | G |
| `bf_fma_dst` | `dst` | 4 | 4 | `hardware-run` | G |
| `hminmax` | `dst` | 4 | 4 | `hardware-run` | G |
| `cvt_bf16` | `srcw` | 8 | 8 | `hardware-run` | F |
| `cvt_f2h` | `src` | 8 | 8 | `isolated-byte-diff` | F |
| `fspecial_est` | `srcA` | 8 | 8 | `hardware-run` | F |
| `tex_deriv` | `dstsrc` | 24 | 24 | `hardware-run` | F |

**`cvt_f2h_dst.src` is the worst row in the database.** It is named `src`, declared 8 bits,
labelled `hardware-run` with range *"byte+3 dense 0..255 (256 values actually dispatched)"*,
and sits inside `emittable_mnemonics` — while its own `match` pins byte+3's high nibble to `8`,
so **only 16 of 256 byte values are legal encodings of it**, all of the form
`(v & 0xf0) == 0x80`. An 8-bit operand descriptor is `(reg<<1)|size`; 7 register bits are
needed to reach the 96-register file. An implementer reading that row will believe they can
point this convert at any source register.

Outside the emittable set, `falu2_uni.usrc` is the same shape at 7 free bits of 8, also
`hardware-run`, also with a range claiming 256.

### 7.3 The two systematic patterns worth acting on

1. **The `G` pattern is a range-string convention error, and it is everywhere.** Six rows say
   "0..255 dense (all 256 values)" for a **4-bit** field. The sweep swept the *byte*; the field
   is a nibble. Nothing is wrong with the encoding — the *claim* is 16× too large, and a reader
   cannot tell whether the field or the byte was covered. Same defect class as
   `fspecial_est.subop`'s "256 of 256 sub-values" for a 4-value field (§2.2). Owner:
   `validation.json`.
2. **The `D` pattern is a fact, not a defect, and should be written down as one.** 69 fields
   are 4-bit register nibbles; **22 are in emittable instructions**, including
   `falu2.dst`, `falu3.dst`, `mov_imm.dst`, `iminmax.dst`, `uniform_mov.dst`. Every one reaches
   **r0..r15 only** out of a 96-entry file, and r15 is not writable through it. That is the
   documented compaction — but a driver back-end doing register allocation needs it stated per
   field, not inferred from a prose paragraph. They are `info` in the JSON so they do not drown
   the real defects.

---

## 8. Limitations — what a reader must not over-read

1. **Everything here is G17P.** EXP-0171 ran only on the A18 Pro / G17P. No M4 row is retracted
   and nothing is promoted across targets. The `db.json` semantics say `G17P` where the
   evidence is G17P.
2. **Cross-run agreement is a reproduction, not a second method.** run01 and run02 share one
   frozen matrix (sha `bce0b7de…`) and differ only in dispatch order. I report them separately
   and never treat their agreement as an independent probe.
3. **The re-derivations inherit EXP-0171's carriers.** I re-computed every verdict from `raw/`,
   but a carrier that could not see an effect still cannot see it. Where that matters I said so:
   `b2_bit0`'s blind SYNTH byte+2 (§3), and `outmod`'s invisibility on dump carriers (§1.2).
4. **DEF-0171-1's range is 0..14, not 0..15.** r15 is unobservable in that carrier by
   construction. An emitter that needs `ilogic` → r15 has no evidence here.
5. **The byte0 bit-3 don't-care was observed at ONE byte+2 value** (`0x1f`) on one carrier
   style. It is recorded as an unmodelled degree of freedom with role `UNKNOWN`, not folded.
6. **The `b_alu10_*` rows remain aliases.** Nothing in this experiment exercised
   `opsel_hi ∈ {2,3,4,6,8,12}`. The merge is measured, not justified.
7. **`analysis/operand_defects.json` is a structural enumeration, not a hardware result.**
   Every row is a statement about what `db.json` and `validation.json` say, cross-checked
   against committed register-file facts. No row is evidence about silicon, and the `F` class
   in particular contains judgement calls about names.
8. **`DEF-0175-1` and the `isadb.py` length rule are reported, not landed.** Both change decode
   for real corpus bytes and neither is inside this dispatch.

---

## 9. Verdict

| | |
|---|---|
| DEF-0171-1 … -5, **DEF-0174-1** | **6 of 6 CONFIRMED** by independent re-derivation; 0 withdrawn; 2 refined |
| applied to `db.json` | all six (DEF-0171-2's `db.json` half only) **+** the 25-field fold **+** DEF-0174-2/-3/-4 semantics |
| corpus | **no regression** — identical clean/leftover/token counts; 7 explained reclassifications |
| round trip | ALL PASS, 302 OK / 0 FAIL, same as baseline |
| `validate_labels.py` | **exit 1, 34 mechanical FAILs**, fully enumerated for the label owner |
| Task 2 arithmetic | **EXP-0173 confirmed exactly**: 627/1062 → 611/1037 (612/1038 with `ilogic.dst`), 172 instructions unchanged |
| `ibfe` closure | **NO** — and `b2_bit0`'s promotion rests on a single carrier style |
| the merge | corpus-neutral, **not landed**, evidence does not reach it — the orchestrator's call |
| new defects | `DEF-0175-1` (`mov_zext16` match), `DEF-0175-2` (the shared A/B gate), the `isadb.py` `0x31` length rule |

| EXP-0174's merge blocker | **CLEARED** — `n3_mov.srcA_reg` is now `(start 8, width 8)` |

**`tools/agx-isa/db.json` is stable at sha
`a77f8cfa163fcf720c0c1093e4ddc5815ceb43c218bb64a87c86d3dcf975dc22` — 172 instructions,
1036 fields. WRITING IS FINISHED; readers may take a snapshot.**
