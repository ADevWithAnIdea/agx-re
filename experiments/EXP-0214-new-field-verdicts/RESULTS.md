# EXP-0214 — RESULTS

**Target of the underlying observations:** G17P (A18 Pro), all of EXP-0199 / 0202 / 0203 /
0205 / 0206. **This experiment:** desk work on the M4 host. **No device contacted.**

```text
Clean-room provenance: analysis of THIS repository's own committed raw observations,
                       authored harnesses and authored MSL. No Apple binary was read,
                       disassembled, decompiled or introspected. No new dispatch.
```

---

## 1. Headline

**1 of 13 promoted. 12 stay `untested`. The emittable-instruction count does not move.**

The one promotion is `half_alu_fma12.srcC`, and it is **emittability-neutral by
construction**: `half_alu_fma12` also holds `lensel`, `mods` and `ext` at `untested`, so it
was not emittable before this verdict and is not after. `half_pack`, `irotate` and
`simd_reduce` each still hold at least one `untested` field and stay out of the set. That
was checked, not hoped: `merge_verdicts.py --dry-run` reports **emittable 37 → 37**.

Three instructions falling out of the set is the honest consequence of learning more about
the encoding. Nothing here puts them back.

---

## 2. Coverage of the NEW span — the question that decides everything

For each field: values of the **new** span that reached the hardware, distinct **actual**
encodings, and how many carriers and gated runs carried them. `values_dispatched` counts
distinct values of *this sub-span*, decoded out of the actual dispatched bytes — not the
parent's case count.

| field | span | encodable | values dispatched | distinct actual encodings | arms | runs | cases |
|---|---|---:|---:|---:|---:|---:|---:|
| `half_alu_fma12.srcC` | (40,8) | 256 | **256** | 256 / arm-run cell | 3 | 9 | 6,144 |
| `half_alu_fma12.lensel` | (32,2) | 4 | **4** | 4 | 3 | 9 | 6,144 |
| `half_alu_fma12.mods` | (34,6) | 64 | **64** | 64 | 3 | 9 | 1,536 at `lensel==3` |
| `half_pack.dst` | (4,4) | 16 | **2** | 2 | 4 | 10 | 0 swept |
| `irotate.rot_dst` | (24,8) | 256 | **256** | 256 / arm | 2 | 4 | 2,048 |
| `irotate.op_enable` | (32,8) | 256 | **256** | 256 / arm | 2 | 4 | 2,048 |
| `irotate.rot_src` | (40,8) | 256 | **256** | 256 / arm | 2 | 4 | 2,048 |
| `irotate.amt_tail` | (56,8) | 256 | **256** | 256 / arm | 2 | 4 | 2,048 |
| `simd_reduce.op_hi` | (11,5) | 32 | **32** | 256 byte+1 / cell | 4 | 6 | 6,144 |
| `frag_depth_store.b1_lo` | (8,1) | 2 | **2** (both inside the accepted set) | 256 byte+1 / cell | 2 | 10 cells | 2,560 |
| `frag_depth_store.b1_hi` | (11,5) | 32 | **32** (all inside the accepted set) | 256 byte+1 / cell | 2 | 10 cells | 2,560 |
| `frag_depth_store.b2` | (16,8) | 256 | **256** | 256 / cell | 2 | 10 cells | 2,560 |
| `pop_reconverge.reserved_hi` | (40,8) | 256 | **9 interpretable** (25 dispatched) | 25 | 3 | 12 cells | 624 |

**Eleven of the thirteen new spans really were covered densely.** The parent sweeps were
byte-wise, so the sub-spans are exactly what varied. Two were not: `half_pack.dst` (2 of 16,
never swept) and `pop_reconverge.reserved_hi` (9 of 256 interpretable, sampled).

**Coverage is not a label.** Eleven dense sweeps produced one promotion.

---

## 3. The six axes, per field

`RE_EXPERIMENT_PROCESS_CORRECTIONS` §2. A result on one axis never implies a result on
another.

| field | geometry | liveness | semantics | recipe | target | reproducibility | label |
|---|---|---|---|---|---|---|---|
| `half_alu_fma12.srcC` | geometry-mapped | live | **semantically-mapped** (bounded) | not-generated | G17P-direct | independently-confirmed (Gate E **inherited**) | **`hardware-run`** |
| `half_alu_fma12.lensel` | geometry-mapped | live | hypothesis | not-generated | G17P-direct | auditable (Gate E inherited) | `untested` |
| `half_alu_fma12.mods` | geometry-mapped | live | unknown | not-generated | G17P-direct | auditable (Gate E inherited) | `untested` |
| `half_pack.dst` | unverified (14/16) | carrier-undecidable | unknown | not-generated | G17P-direct | auditable | `untested` |
| `irotate.rot_dst` | geometry-mapped | live | unknown (predictor refuted) | not-generated | G17P-direct | auditable (Gate E inherited) | `untested` |
| `irotate.op_enable` | geometry-mapped | live | unknown (predictor refuted) | not-generated | G17P-direct | auditable (Gate E inherited) | `untested` |
| `irotate.rot_src` | geometry-mapped | live | unknown (predictor refuted) | not-generated | G17P-direct | auditable (Gate E inherited) | `untested` |
| `irotate.amt_tail` | geometry-mapped | live | unknown (predictor refuted) | not-generated | G17P-direct | auditable (Gate E inherited) | `untested` |
| `simd_reduce.op_hi` | geometry-mapped | accepted-inert | unknown | not-generated | G17P-direct | independently-confirmed (Gate E inherited) | `untested` |
| `frag_depth_store.b1_lo` | geometry-mapped | accepted-inert | unknown | not-generated | G17P-direct | auditable (Gate E **bounded**) | `untested` |
| `frag_depth_store.b1_hi` | geometry-mapped | accepted-inert | unknown | not-generated | G17P-direct | auditable (Gate E **bounded**) | `untested` |
| `frag_depth_store.b2` | geometry-mapped | accepted-inert | unknown | not-generated | G17P-direct | auditable (Gate E **bounded**) | `untested` |
| `pop_reconverge.reserved_hi` | geometry-mapped (9 values) | accepted-inert in a 9-of-256 sample | unknown | not-generated | G17P-direct | auditable (Gate E **partial**) | `untested` |

### Gate E, inherited honestly

EXP-0210's quiet window named specific fields. **Not one of the thirteen is among them** —
they did not exist when EXP-0210 ran. What each new field inherits, and from what:

| field(s) | inheritance |
|---|---|
| `half_alu_fma12.*` | **Inherited, same capture.** EXP-0210 confirmed EXP-0203's `dst`/`dstlo`/`b3` on the `q43`/`q44` pair at 100.0000%. The byte+4 and byte+5 cases are records *in those same two captures*, so it is the same quiet window — but EXP-0210 did not score these fields, and this is stated rather than glossed. |
| `irotate.*` | **Inherited, same records.** EXP-0210 confirmed `irotate.operands` outright on the `quiet03`/`quiet04` pair; all five byte arms carry `field: "operands"`, so the four new sub-fields *are* those records. |
| `simd_reduce.op_hi` | **Inherited, same records.** EXP-0210 confirmed `simd_reduce.op` outright; `op_hi` is the high 5 bits of the same byte+1 sweep. |
| `frag_depth_store.*` | **Bounded**, as EXP-0210 labelled it: "every residual cross-run disagreement is a fault⟷clean flip; 100.00 % on valid payloads". Reconfirmed here — see §5. |
| `pop_reconverge.reserved_hi` | **Partial.** EXP-0210 re-derived that EXP-0206's `run05`/`run07` pair really was quiet — that is the `cf_ifnl` carrier, the only one with detection power. Its `cf_nl2` / `cl_atomic` arms were **NOT REACHED**, because on a quiet machine those encodings hang. So the carrier that matters has a quiet pair and the two that read inert do not. |

---

## 4. The one promotion, and why it clears the bar

### `half_alu_fma12.srcC` (40,8) → `hardware-run`

The old 64-bit `ext` was swept **byte-wise**: 8 bytes × 256 values × 3 arms. Byte +5 *is*
the new `srcC` span, so the coverage is direct, not inherited from a wider field.

| gate | numerator / denominator |
|---|---|
| **Gate A** — requested == decoded from actual bytes | **49,152 / 49,152** over all eight `ext` byte sweeps; 0 mismatches |
| **G1** dense + non-aliased | 256 / 256 values, 256 distinct actual byte+5 encodings per cell |
| **G1** span-only | **6,144 / 6,144** differ from the arm anchor *only* inside byte +5 |
| **G2** valid observation | **6,144 / 6,144** status OK + `seed_ok` + both sentinels + not victim |
| **G3** cross-run agreement | **0 / 768** (arm, value) disagreements |
| **G4** movement | 6,096 / 6,144 moved; the 48 non-movers are the anchor's own value and its bit-7 mirror, one pair per cell |
| **G5** oracle discrimination + agreement | **6,144 / 6,144** full-16-word matches, **29 distinct predicted** post-digests and **29 distinct observed** — a constant oracle was a pre-registered *failure* |
| **G6** falsifiers fired | `__fals_F1_null` 90/90 non-match with `null_match` true · `__fals_F2_opsel` 60/60 non-match · `__fals_F4_dstshift` 90/90 non-match |
| **G7** identity stable | **6,144 / 6,144** `hw_markers == 4`, the anchor's |
| **Gate B** detection power *in this dimension* | `__ctl_live_srcA` **480 / 480** oracle match across 8 distinct seeded source descriptors |
| **Gate B §6** two disjoint readback plans | **MET** — `F12_EXT_A`/`B` on layout HI, `F12_EXT_C` on layout LO with the destination moved r1 → r7 (Amendment 03) |

**Why this is semantics and not liveness.** The oracle is not "did it change". It reads the
case's **own observed pre-dump**, decodes byte +5 as a half-register descriptor
(`bit 0 = half, bits 1..6 = GPR, bit 7 = don't-care`), computes the fp16 FMA on the host in
binary64 with a single final rounding, and predicts the **entire 16-word post-dump**. The
prediction is different for different values — 29 distinct predicted vectors — and the
hardware matched every one. The model was fitted offline on EXP-0180's raw *before this
harness existed* and validated here on held-out gated runs.

**Bit 7 was measured a don't-care, not assumed.** Descriptors `d` and `d | 0x80` produced
**byte-identical 16-word post-dumps on 128 / 128 pairs**.

**The bound that must travel with the label.** Only **64 of 256** descriptors name a GPR
this carrier's 16-register window can see. The other **192** are predicted *and* observed to
contribute `0`, which is a **carrier property** — checked per run by `__ctl_unseeded` — and
**not** a hardware statement about GPRs 16..63. An emitter may name r0..r15 with srcC;
r16..r63 are unvalidated.

**And one caveat stated rather than buried.** EXP-0203's pre-registration bound `ext` to
`untested` "whatever happens", because 2,048 of 2⁶⁴ is 0.0 % coverage. That bound was about
the **64-bit parent**; `srcC` is an 8-bit field EXP-0212 created, and it *is* dense. But the
G1..G7 criteria were frozen against fields that existed at freeze time, and this one did
not — so the criteria are frozen and the *field they are applied to* is not. What rescues it
is that **H2 pre-registered the semantics** ("byte +5 is the third fp16 operand's
half-register descriptor") with an explicit refuter ("a byte +5 value whose observed result
is not the frozen oracle's prediction"), and the refuter **did not fire once in 6,144 cases**.

---

## 5. The twelve that stay `untested`, in the order the evidence is weakest

### 5.1 `half_pack.dst` (4,4) — never swept

**Zero records in the entire experiment carry `field == "dst"` for `half_pack`.** The
destination nibble took exactly **two** values in 15,872 half_pack records, and both are
**fixed arm constants**: nibble 1 on `HP_A`/`HP_B` (layout HI) and nibble 7 on `HP_C`/`HP_D`
(layout LO). A third nibble (14) appears in 20 records but those are `ec00ec00` — the
`__fals_F1_null` falsifier's `mov_imm` pads, i.e. not this instruction at all.

The one falsifier that names the destination, `__fals_F4_dstshift`, **does not change the
bytes**: it dispatches the anchor unmodified and asks the *oracle* to predict a shifted
destination. It is a check on the oracle's discrimination, not a probe of this field.

The trap is symmetry: the sibling `half_alu_fma12.dst` is the same 4-bit position in the
same family and *is* densely swept (16/16 in 4 arms). It would be easy to assume this one is
too. **14 of 16 values are untested.**

### 5.2 `pop_reconverge.reserved_hi` (40,8) — 9 of 256, on carriers that mostly cannot see

The parent sampled **52 of 65,536** values. Those reach 25 distinct high bytes, but only
**9** — `{0,1,2,4,8,16,32,64,128}` — occur with a **zero sibling low byte**, and only those
are interpretable, because the low byte is load-bearing: on `cf_ifnl` all 43 nonzero-low-byte
cases give `wrong_value`. Within the 9 clean points: `ok` 9/9, exactly **one** hardware
signature, on 3 carriers in 12 arm-run cells.

The inert reading is worth very little, and the reason is the sibling. `pop_reconverge.reserved`
(32,8) reads **inert on `cf_nl2` and `cl_atomic`** (43/43 `ok`) and **LIVE on `cf_ifnl`**
(43/43 `wrong_value`) — three carriers that differ essentially only in lane-dependent
divergence. Two of three are **demonstrably blind in this dimension**. So an inert reading of
the high byte rests on one carrier with detection power and nine sampled values, eight of
which are single-bit patterns. EXP-0206 said so itself: `live (1 of 3) · carrier-undecidable
(2 of 3)`, `hypothesis — all 3 models refuted`, and its next-experiment recommendation 2 is to
sweep this region densely on lane-dependent carriers.

### 5.3 The four `irotate` sub-fields — live, and every predictor refuted

Gate A was **re-derived**, because the driver's own `ledger_ok` reads `False` on all 8,192
cases: it compares the requested value against the tokenizer's decode of the **whole 40-bit
parent**. EXP-0202's `analysis/verdicts.py::ledger` already documents and corrects this, and
after EXP-0212's split the sub-span *is* the db field, so the correct assertion —
`requested_bytes == actual_bytes` **and** `bits(actual_bytes, start, 8) == value` — passes
**2,048 / 2,048 on each of the four**, with 0 encoding collisions.

| field | reproduce | fault | cross-run disagreements | pre-registered predictor refuted on |
|---|---|---|---|---|
| `rot_dst` (24,8) | 2 of 256 (values 0, 1) | **64 of 256, contiguous 192..255** | 0 / 512 | **520 / 2,048** |
| `op_enable` (32,8) | 128 of 256 (bit 33 set) | 0 | 0 / 512 | **1,016 / 2,048** |
| `rot_src` (40,8) | 4 of 256 (values 0..3) | 0 | 0 / 512 | **24 / 2,048** |
| `amt_tail` (56,8) | 8 of 256 (even values 0..14) | 0 | 0 / 512 | **56 / 2,048** |

All four arms use the oracle rule `exact_iff_compiled`, which predicts the carrier's vector
at the compiler's own value and a bare `broken` everywhere else. **That is a liveness
hypothesis written as an oracle, not a map from value to effect** — it cannot distinguish
`wrong_value` from `silent_zero` from `fault`, and the buckets it does emit are one bit
wide. It was refuted on every arm. EXP-0202 says it in its own words: *"every arm's
pre-registered predictor was refuted somewhere except the four `operands_b6` arms"*, and it
treats the identical situation on `iunary.b1`/`opsel` as *"live but role unknown — no
promotion"*.

The names carry more than the evidence does. `dst` / `op-enable gate` / `src` / `tail` come
from a census byte-diff and EXP-0139's reading of the same blob in `iunary`/`ibitcount` —
**corpus correlation**. No experiment has ever seeded distinguishable values into the
candidate sources and read a rotate result back out of a register `rot_dst` selected.

Two findings worth carrying forward on their own, neither of which is a label: the
**contiguous 192..255 fault region** on `rot_dst`, reproduced in 4 runs on 2 carriers with 0
disagreements; and the fact that even the *failure class* is carrier-dependent
(`wrong_value` on `rot_alu`, `silent_zero` on `rot_k5`, same 188 values).

### 5.4 `simd_reduce.op_hi` (11,5) — inert, and inertness is not a label

32/32 values, Gate A **6,144 / 6,144** from the raw's own ledger, 0/1,024 cross-run
disagreements. **Period 8 holds in 24 of 24 arm-run cells**: the hardware observable is a
function of byte +1 bits `[2:0]` alone. The positive control is in the *same byte* — the low
3 bits produce 4 to 6 distinct hardware observables per carrier — so the readback
demonstrably sees byte +1 change.

§7's bar is still not met, on four counts:

1. **Four carriers, one class.** `sr_sum` / `sr_max` / `sr_scan` / `sr_fsum` share one stage,
   one readback plan and one 32-lane u32 observation path. §7's own rule — *"two generated
   carriers with the same leaf callee, state shape, or observation path count as one method
   for that dimension"* — makes that **one** carrier class, not three.
2. **No control in the dimension the bit would plausibly control.** Nothing tests an
   opcode-extension role.
3. **No interaction tests** against `dtype`, `shape`, `opcls`, `scope` or `cache`. EXP-0212
   refused to narrow `simd_reduce.dtype` for exactly this reason: its bit 4 is `f16_incl_scan`
   and **no carrier is fp16**. The same blind dimension may hide `op_hi`'s role.
4. **No independent method.**

Safe wording: *inert in 0..31 dense × 4 reduce carriers × 6 gated runs on G17P at fixed
`op[2:0]`; global role unknown.*

**A measurement note that cost this analysis two false negatives.** The period-8 test is only
valid on the hardware observable. Including `observed.gputime_ns` makes period-8 fail in
**24/24** cells — nondeterministic timing, the same defect EXP-0202 found in
`tools/agx-isa/wave_audit.py`. Including the derived `outcome` label *also* makes it fail,
because `outcome` is scored against a **per-value** oracle and therefore varies with `op_hi`
even where the silicon does not. Both were reproduced here before being excluded, and the
first version of this analysis reported "period-8 REFUTED" on the strength of the second one.

### 5.5 The three `frag_depth_store` fields — a good inert reading that still isn't a label

This is the strongest inertness evidence in the set, because **detection power is proven on
the same instruction and the same observable**. EXP-0199 reads the Depth32Float attachment
back per pixel for the first time; `b5` bit 1 collapses depth to 0.0 on 128/256 values, and
byte +1's own match bits discard the tile on 192/256.

| field | coverage | result |
|---|---|---|
| `b1_lo` (8,1) | both values, **inside** the accepted set, in 10/10 cells | **1** distinct hardware signature among the accepted values, in **10/10** cells |
| `b1_hi` (11,5) | all **32** values, **inside** the accepted set, in **10/10** cells | same — the accepted set is exactly 2 × 32, a complete cross product |
| `b2` (16,8) | 256/256 | every value accepted; 1 distinct hardware signature across all 256, in 8 of 10 cells |

The accepted set for byte +1 is exactly `(v & 0x06) == 0x04`, **64 of 256** in 9 of 10 cells and 63 in the tenth (`g17p_conf04`/`c_depth2`, where the missing value 236 is an InnocentVictim fault and is `ok` in the other three runs) —
so the descriptor's declared full-byte `match` of `0x14` is enforced on **two bits**, and
`b1_lo` + `b1_hi` are the six user-visible bits nobody has a role for.

**The two non-clean cells are classified, not counted.** Both are in `g17p_conf04`: four
`kIOGPUCommandBufferCallbackErrorInnocentVictim` faults (a `measurement_failure` under Gate
E, never a hardware outcome — and EXP-0210 measured EXP-0199's InnocentVictim count going
4 and 16 → **0 and 0** on the quiet machine), one genuine hang at `b2 = 249` that does not
repeat in the other three runs, and one `both_moved` at `b2 = 19` that likewise appears in
1 of 4 runs. Gate E requires such claims to be **repeated in isolation**; none is. The one
event that does repeat is a hang at byte +1 = 177 in 2 of 4 runs — and 177 is in the
*rejected* set anyway.

Same §7 shortfall as `op_hi`: `c_depth` and `c_depth2` are a genuinely good adversarial pair
for the *instruction's* role (different depth function, different varying, different colour),
but they are one fragment stage, one attachment configuration and one observation path — one
carrier class. No interaction tests against `b3`/`b4`/`b5`. No independent method. And the
interesting claim here is a **negative** one about a byte the database calls a `match`, which
§7 says needs the *strongest* evidence, not the weakest.

### 5.6 `half_alu_fma12.lensel` (32,2) — live, and it contradicts the database

4/4 values, 1,536 cases each (the nine gated runs; `pilot01` is excluded because EXP-0203's pre-registration §5.5 says it is "not evidence for any field verdict"). The byte +4 sweep is a full **4 × 64 factorial** of
`lensel × mods`, so both marginals are separable — this is the one place where a joint
parent sweep genuinely does resolve two sub-fields.

The observable is `hw_markers`, the count of surviving 2-byte length markers, which is a
**silicon-side measurement of consumed length** and not our tokenizer's opinion — EXP-0203's
Amendment 03b makes exactly that distinction, after finding the frozen G7 conjunct was
counting the disassembler as a hardware signal.

| `lensel` | surviving markers |
|---|---|
| 0 | **2** (1,536 / 1,536) |
| 1 | **4** (1,536 / 1,536) |
| 2 | **2** (1,534 / 1,536; 2 unmeasured) |
| 3 | **4** (1,535 / 1,536; 1 unmeasured) |

The partition is exact and by **bit 32 alone**; bit 33 is inert on this observable. That is a
clean liveness result — and it **contradicts `db.json`**, whose length map makes the 12-byte
form reachable only at `lensel == 3` and reads `lensel == 1` as an 8-byte `half_alu_ext8`.
The silicon consumed the same amount at 1 and 3.

That is a **finding for a successor, not a promotion**: either the length map's 1-vs-3
distinction is wrong, or the marker observable cannot resolve 8 from 12 bytes in this splice
layout. One dense byte +4 sweep with a marker plan that can count 8 and 12 separately settles
it. Until then the honest reading is *live on a 2-valued length observable; the 4-value
length map is unconfirmed*. H2 named byte +4 bits 0..1 "the length selector" but registered
**no per-value length model and no refuter for it**, and the byte +4 sweep was pre-registered
as a declared *hazard*, not as this field's evidence.

### 5.7 `half_alu_fma12.mods` (34,6) — live, no predictor indexed by the field

64/64 values at `lensel == 3`, 24 cases each, hardware identity preserved 1,535/1,536. Only
**6 of 64** values ever reproduce the anchor's arithmetic, and only 2 of those do so in all
24 cells: values 2 and 3 match in 9/24, values 6 and 7 in 15/24 — so **the effect is
carrier-dependent**.

There is real structure in the raw, and it must not be labelled, because it is **post-hoc**:
values 8..31 and 40..63 all fit the frozen alternate model `abs(a)*b` (the addend is dropped)
in 18/24 cells each; values 32..39 produce the correct arithmetic **result**
(`oracle_result_match` up to 24/24) while **failing** the full-vector match (0/24) — the
signature of a correct result plus an extra side effect, consistent with the source-release
behaviour EXP-0203's pre-registration §4.1 measured at byte +4 = `0x93`.

Reading that fit pattern as a modifier map would be the EXP-0169 error precisely: the nine
models were frozen for a **different question**, and which of them happens to fit is a hint,
not an oracle. There is no pre-registered predictor indexed by `mods`.

---

## 6. How this method could have promoted a field whose parent sweep never varied it

The honest answer, because the instrument that prevents it is one line of code and it was
not there at the start.

**The failure is that a field name is a handle, and a sweep is keyed by the handle.** Every
one of these raw corpora records `field: "operands"`, `field: "ext"`, `field: "op"`,
`field: "byte1"` — the **parent's** name. Group by that key and `irotate.rot_dst` looks like
it has 3,212 cases, `half_alu_fma12.srcC` looks like it has 2,048 per arm, and
`half_pack.dst` looks like it has **15,872**. All three numbers are true about the parent and
none of them is about the sub-span. `half_pack.dst`'s is the dangerous one: 15,872 records of
an instruction whose destination nibble **never moved**.

The specific way it would have happened here:

1. **Group by `field`, count rows, call it coverage.** `half_pack` has 15,872 committed
   records across 4 arms and 10 runs, with a full actual-byte ledger, a host oracle, and
   `dstlo` and `b3` both at `hardware-run`. Every surrounding signal says "this instruction
   is well characterised". Nothing in a row count reveals that `dst` took two values, that
   both are layout constants, and that no case ever carried `field == "dst"`.
2. **Trust the parent's label to cover its children.** `irotate.operands` carries
   `isolated-byte-diff` and EXP-0202 earned it — on **byte +6 alone**, which is the one byte
   that kept the name. The other four bytes became `rot_dst`, `op_enable`, `rot_src` and
   `amt_tail`, and inherit exactly nothing. A name-keyed merge would have attached the parent's
   evidence to four fields whose predictor was refuted.
3. **Read a derived report instead of the raw.** `analysis/ext_bytes.json` already contains
   byte +4's numbers, and they are correct. But it reports `hardware_identity_preserved: 128`
   for byte +4 as a single figure, and the whole content of that 128 is *"bit 32 is the length
   selector and half the byte's values change the instruction's length"*. Read as a coverage
   number it looks like a 50 % pass rate. Read stratified it is a clean 4 × 64 factorial with
   a sharp hardware partition. The stratification is not in the derived file.

**What actually prevented it** was making the instrument decode the sub-span out of the
**actual dispatched bytes** and refuse to look at the `field` key for anything but
attribution (`scripts/span_coverage.py`). That is what turned "the parent was swept" into
"2 of 16 nibbles, both constants, zero swept cases" — and it is the same move EXP-0212 made
when it counted `pop_reconverge.reserved`'s sweep out of `sweep.jsonl` and found 52 sampled
values where the summary implied a narrowing.

**Two things I would make mandatory as a result:**

* **A verdict must state `values_dispatched` and `distinct_bytes` for its own span, decoded
  from actual bytes.** `merge_verdicts.py` already carries those keys through and its own
  comment says why (DEF-0166-1: a sweep can dispatch 256 values while the hardware sees 8
  encodings). But it does not *require* them, and `range` is free prose — so
  `half_pack.dst`'s "2 of 16 nibbles exercised" is a sentence no tool can read. Making the two
  counts mandatory for any label above `untested` would make the coverage question
  machine-answerable, which is exactly what DEF-0212-1 did for the *span* question.
* **A sub-field created by a split must name the sweep arm that varied its bits**, not the
  parent field. Four of these thirteen would have been rejected on that requirement alone.

**And one smaller trap, met head-on.** Twice in this analysis a period-8 inertness test
returned "REFUTED" because the comparison key included something that is not a hardware
observation — first `observed.gputime_ns` (nondeterministic timing), then the derived
`outcome` label (scored against a per-value oracle, so it varies with the field even when the
silicon does not). Both directions of that error are live: a stray nondeterministic field
manufactures *liveness*, and — as EXP-0202 found in `wave_audit.py` — it also manufactures
*cross-run disagreement*. The rule that survives is: **compare silicon readback, and nothing
a script computed.**

---

## 7. What was not done

* **No device was contacted.** EXP-0213 held the neo; every number here is desk work on
  committed raw.
* **No raw file was edited.** Raw is append-only.
* **Nothing outside `experiments/EXP-0214-new-field-verdicts/` was written.**
  `tools/agx-isa/validation.json`, `tools/agx-isa/db.json`, `docs/` and `PROVENANCE.md` are
  untouched, and nothing was committed. `merge_verdicts.py` was run **`--dry-run` only**;
  `validation.json`'s checksum is unchanged before and after.
* **Gate D (generate the compiler recipe) is `not-generated` for all thirteen.** Nothing here
  builds a program from documented rules; a field label is not an emittability proof (§2).
* **Gate E was inherited for every field, never established here** — see §3.

## 8. What the next experiment should ask

1. **`half_pack.dst`, 16/16 dense**, with the readback index held fixed and two disjoint
   register plans. It is a 4-bit field on an instruction that is otherwise fully characterised;
   this is the cheapest of the thirteen to close.
2. **`half_alu_fma12.lensel` with a marker plan that resolves 8 from 12 bytes.** The db length
   map and the silicon disagree at `lensel == 1`. That is a db defect or an instrument limit,
   and one sweep decides which.
3. **`pop_reconverge.reserved` byte +4 dense 0..255 on lane-dependent carriers**, which is
   EXP-0206's own recommendation, and then the high byte dense at a zero low byte.
4. **A structurally different carrier for `simd_reduce.op_hi` and `frag_depth_store.b2`** —
   different observation path, and for `op_hi` an **fp16** carrier, since that is the exact
   blind dimension EXP-0212 refused to narrow `dtype` over.
5. **A per-value host oracle for the four `irotate` sub-fields.** `exact_iff_compiled` has now
   been refuted on all four; the successor needs a model that predicts *what* each value does,
   with seeded, distinguishable sources and a destination readback that does not co-vary with
   the swept field.
