# EXP-0202 — RESULTS

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6
build 25G5043d, Metal family Apple9), `192.168.170.254`. **Nothing ran on the M4.**
**Clean-room:** `OWN-SHADER` + `HW-PROBE`. Every byte spliced, decoded or inspected is the compiled
form of our own MSL in `kernels/`. **No Apple binary was disassembled or introspected.**
**Governing gate:** `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` (normative; it landed mid-experiment and
`PRE_REGISTRATION.md` AMENDMENT v3 was frozen before its first dispatch), implemented by
`analysis/verdicts.py` and nothing else. Verdicts are recomputed from `raw/` on every invocation.

---

## 0. Headline

| field | before | axes now (geometry / liveness / semantics) | proposed label |
|---|---|---|---|
| `irotate.operands` | `untested`, withheld **UNSTABLE** | ledger-verified / **live** / **byte+6 semantically mapped** | `isolated-byte-diff` |
| `shift_amt_move.src_flag` | `untested`, withheld **INERT-SINGLE** | ledger-verified / **carrier-undecidable** / — | `untested` (unchanged, now for a *measured* reason) |
| `ibitcount.cache` | `untested` | ledger-verified / **live, asymmetric** / predictor refined | `isolated-byte-diff` |
| `ibitcount.dst` | `untested` | ledger-verified / **live** / two model corrections | `isolated-byte-diff` |
| `iunary.b1` | `untested`, **no raw had ever existed** | ledger-verified / **live** / role unknown | `untested` (liveness recorded) |
| `iunary.opsel` | `untested`, **no raw had ever existed** | ledger-verified / **live** / role unknown | `untested` (liveness recorded) |
| `cvt_f2i.b9` | `single-template-inference`, refused **INERT-SINGLE** | ledger-verified / **accepted-inert over a much wider envelope** / live model refuted | `single-template-inference` (unchanged, envelope widened) |
| `cvt_f2i._instruction` | `corpus-correlation` | ledger-verified / live / **bounded-map** | **`hardware-run`, target G17P** |
| *(new)* `b_alu10_lo7.src_flag` | — | ledger-verified / accepted-inert, 2 carriers | `untested` |

**Three results are worth more than the labels.**

1. **`irotate`'s immediate rotate amount is now a formula an emitter can use.**
   `byte+6 = 4·(32−K)` gives rotate-**left**-by-`K`. Confirmed against an **exact host-computed
   vector** at all 33 modelled values on four carriers in two runs — **264 exact vector matches,
   zero misses** — and, independently, by searching all 32 amounts for one that reproduces each
   observation: a single rotate-left amount is recovered at exactly those 33 values, **32 distinct
   amounts**, every one agreeing with the formula. The input codewords are asymmetric
   (`0x8000000B + t·0x01234567`), so direction and amount are both determined by the data rather
   than assumed.
2. **`irotate.operands` is not one field.** Its five bytes carry exactly the meanings EXP-0139
   established for the identical blob in `iunary` (DEF-0139-1), plus the amount. `db_defects`
   DEF-0202-1.
3. **`shift_amt_move.src_flag` is `carrier-undecidable`, and that is the honest answer.** It did
   not move on 11 occurrences across 9 carriers spanning **seven operand-producer classes**, at
   both flag values, across all 128 source indices. But the positive control **in the dimension the
   bit is believed to select** — `b_alu10_lo7.src_flag`, the same bit, same split, same enum, same
   family, and one the compiler emits at **both** values — did not move either. Nothing here shows
   the harness can observe a source-class change at all, so zero movement is **not** evidence of
   inertness.

---

## 1. Runs, and what each is allowed to support

| run | contract | arms | cases | s | order | status |
|---|---|---|---|---|---|---|
| `raw/g17p_20260830_run01` | v2 | — | 0 | — | — | **BURNED and RETAINED.** A chained `cd … && mkdir … && nohup … &` backgrounded its own `cd`; `run.py` then ran from `$HOME` and failed, while the `mkdir` had already claimed the id. Never topped up or reused. Its 63 kB of gpuwatch samples are kept. |
| `raw/g17p_20260830_run02` | v2 | `arms202.json`, 148 | 9140 | 665 | forward | **DISCOVERY only.** Cited for liveness and geometry, never for a promotion. |
| `raw/g17p_20260830_run03` | v3 | `arms202b.json`, 184 | 10162 | 405 | **forward** | confirmation A |
| `raw/g17p_20260830_run04` | v3 | `arms202b.json`, 184 | 10162 | 423 | **reverse** | confirmation B |

`raw/prefreeze/` holds the two censuses and the pilot. **No verdict cites `raw/prefreeze/`.**

**Run hygiene, all three runs:** 0 hangs, 0 watchdog timeouts, 0 malformed responses, 2 `invalid_run`
per run (re-measured), 642–706 contained faults, 160–262 cases that saw at least one
`InnocentVictim` response — every one **retried up to 3× before being scored**.

**All three runs finished at 19:46 UTC.** EXP-0204's ~18 declared device hangs are in the
**20:00–20:25** window, entirely after this raw; none of it is in these observations.

---

## 2. Gate A — the actual-byte ledger

Every case in run03/run04 records the requested value, the **complete requested bytes**, the
**complete actual bytes taken from the final dispatched `_agc.main`**, an **independently decoded**
value (the pinned tokenizer's own field extraction — a different code path from the patcher), the
`sha256` of the mutated main, the instruction offset, and the db/arms/harness/driver revisions.

**Result: 20 324 of 20 324 ledger-verified. Zero requested/actual mismatches, zero encoding
collisions.** Per field, distinct requested values equal distinct **actual** encodings everywhere.

**Gate A caught its first thing immediately, and it was in the check.** The driver compared the
requested value against the tokenizer's decode of the **whole db field**; the arms that sweep a
**sub-span** of a wider field (`irotate.operands` is 40 bits and its byte-wise arms request 8 of
them; `irotate.tail` is 32) therefore compared 8 bits against 40 and "failed" 3232 cases — with
`requested_bytes == actual_bytes` **true in all 3232**. Per §9 of the corrections document this is
reclassified from raw, not re-run: `analysis/verdicts.py` re-derives Gate A offline from
`actual_bytes` + `start` + `width` with a **third** independent bit extractor.

## 3. Gate E — NOT MET, and it was measured rather than assumed

`harness/gpuwatch.py` sampled the neo's process table every 2 s for the whole of every run.

| run | samples | samples with a foreign GPU process | quiet? |
|---|---|---|---|
| run02 | 329 | 213 | no (EXP-0200/0201/0205/0206) |
| run03 | 201 | **201** | no (EXP-0206, EXP-0200) |
| run04 | 209 | 209 | no |

**`reproducibility: INCOMPLETE — Gate E not met` on every row.** This is the only axis left open,
and it is not achievable while the fan-out runs.

**What stands in its place, and it is strong.** Across the pair, in **opposite case order**:

> **10 156 of 10 156 shared cases agree. ZERO disagreements** — and zero even without collapsing
> `ok`/`unexpected_ok`.

Contamination can destroy an observation but never fabricate a coherent one (EXP-0160); an
order-reversed pair with a byte-identical partition on every case is the strongest thing a busy
machine can produce.

### 3.1 `tools/agx-isa/wave_audit.py` reports 0–25 % agreement here. Both causes are in the checker.

Its output is committed verbatim as `analysis/wave_audit.txt`;
`analysis/wave_audit_recheck.py` re-derives it three ways:

| field | wave_audit's key (value, whole `observed`) | keyed by (arm, value) | (arm, value), `gputime_ns` excluded |
|---|---|---|---|
| `shift_amt_move.src_flag` | 1/2 disagree | 92/112 | **0/112** |
| `b_alu10_lo7.src_flag` | 2/2 | 6/6 | **0/6** |
| `irotate.operands` | 268/320 | 2818/3212 | **0/3212** |
| `ibitcount.cache` | 2/2 | 20/20 | **0/20** |
| `ibitcount.dst` | 151/256 | 782/1280 | **0/1280** |
| `iunary.b1` | 203/256 | 266/512 | **0/512** |
| `iunary.opsel` | 246/256 | 439/512 | **0/512** |
| `cvt_f2i.b9` | 239/256 | 1452/1536 | **0/1536** |
| `cvt_f2i.signflag` | 247/256 | 247/256 | **0/256** |

1. It pools by `value` **across every arm of a field** (`runs[run][value] = observed`), so with six
   arms per value the last one written wins — and run04 iterates in **reversed** order by design,
   so a different arm wins in each run. It compares different arms.
2. It compares the **whole `observed` dict, which contains `gputime_ns`** — a nondeterministic
   hardware timing measurement. Two byte-identical dispatches of the same program differ in it
   essentially always.

**Reported, not fixed** (`tools/agx-isa/` is not this experiment's to edit). It is worth attention
on its own: this line will silently read near-total disagreement for **any** experiment whose raw
carries a timing field inside `observed`. `cvt_f2i._instruction` also shows "NO RAW RECORDS" there,
because `_instruction` is a row about the instruction, not a field name that appears in raw.

---

## 4. Per field

### 4.1 `irotate.operands` — LIVE, and byte+6 is semantically mapped

`irotate` is `27 01 56 | dst opEn src AMT tail | tail×4`. The census byte-diff over compiled
amounts {1, 5, 7, 13, 19, 31} showed **byte+6 is the only byte that moves with the amount**, at
`byte+6 = 4·(32−K)`.

| evidence | numerator / denominator |
|---|---|
| modelled values matched the **exact** host rotate vector, both runs, 4 carriers | **33/33 per carrier, 132 per run, 264 total, 0 misses** |
| a single rotate-**left** amount recovered without using the formula | 33 of 64 low-2-aligned values; **32 distinct amounts**; formula disagreements: **none** |
| values with `byte+6 >> 2 > 32` reproduced by *any* rotate amount | **0 of 31** — bounded negative, role unknown |
| joint 40-bit arm (the first this field has had) | 70 values: {0,1,2,max−1,max}, all 40 powers of two, compiled ±1, 24 fixed asymmetric interiors; reproduces at exactly {compiled, compiled+1}; 11–15 contained faults; **0 hangs**, abort budget never reached |

**The five-byte split (DEF-0202-1), both carriers, both runs:** byte+3 = `dst` (reproduces at
{0,1}, faults 192–255) · byte+4 = an **op-enable gate** (128 of 256 reproduce) · byte+5 = `src`
(reproduces at 0–3) · byte+6 = **the immediate amount** · byte+7 = tail (reproduces at the 8 even
values 0–14). These are exactly `ibitcount`'s meanings, which is what EXP-0139 found for the same
blob in `iunary`.

**EXP-0189's `UNSTABLE` refusal does not reproduce**: 0 of 3212 (arm, value) pairs disagree.

**Field-level label stays `isolated-byte-diff`** — one of five bytes is mapped. **byte+6 bits[6:2]
alone meets the `hardware-run` bar**, and the descriptor should be split.

### 4.2 `shift_amt_move.src_flag` — CARRIER-UNDECIDABLE

**The carrier dimension built:** *which register file supplies the staged shift/rotate amount* —
because that is what the inherited enum (`0 = gpr`, `1 = uniform/class`) claims the bit selects.
Nine carriers, **seven operand-producer classes**: device memory load · thread-invariant
`constant uint&` · ALU chain · thread-position system value · SIMD lane index · overwrite with an
intervening independent ALU op · control-flow merge. Plus a `<<` and a `>>` form, and one program
holding a GPR amount and a uniform amount at once.

| observation | numerator / denominator |
|---|---|
| boundary-aligned `shift_amt_move` occurrences found | 11, on 9 of 56 carriers |
| occurrences where the **compiler** chose `src_flag = 1` | **0 of 11** |
| index/flag comparisons where both flag values give byte-identical output | **768 of 768**, both runs |
| field-keyed arms (2 values × 56 arms) with any difference | **0** |
| the same-dimension control `b_alu10_lo7.src_flag` moving | **0 of 3 occurrences**, though its own `src_reg` control moves at 19 of 20 values |

Two carriers that are identical in the dimension the field controls are one carrier — and here even
the *sibling descriptor where the compiler emits both values* is indistinguishable. So the safe
statement is **`inert in this envelope; global role unknown`**, and even that is bounded by the
missing control. **Label unchanged at `untested`, now for a measured reason.**

### 4.3 `ibitcount.cache` — LIVE and ASYMMETRIC

byte+2 bit 1 is the **only free bit** of byte+2 under this descriptor's match (byte+2 ∈ {0x54,
0x56}), so 2 of 2 encodable values **is** the full range. Ten occurrences on nine carriers spanning
standalone-store, ALU-consumed, compare-consumed, two-occurrence, find-msb, reverse-bits,
threadgroup-memory + barrier (grid 64 / tg 32) and wide-readback forms — and **the compiler emits
both values across them**, so the routing dimension is spanned by demonstration.

* on the **7** occurrences compiled to 1, forcing 0 breaks the result (`wrong_value`), both runs;
* on the **3** compiled to 0, **both** values reproduce the host vector.

Value 1 is universally safe here; value 0 is context-dependent — the same asymmetry `irotate.b2`
has. The pre-registered symmetric writeback-enable model is **refuted at 3 of 20 checks**; the
refinement is post-hoc and is offered as a hypothesis, not as a mapped semantic.

### 4.4 `ibitcount.dst` — LIVE, with two corrections to `db.json` (DEF-0202-2)

Dense 0..255 on five occurrences under **two disjoint readback plans** (four single-word carriers,
plus `pc_dump`, which holds four mutually distinct live values per lane at fixed store indices).

1. **The program reproduces at exactly two values, {compiled, compiled+1}, on all five
   occurrences** → bit 0 of `dst` is **not** part of the register index.
2. **192..255 fault, contiguously, all 64 values, on all five occurrences, in both runs** →
   `dst[7:6] == 0b11` is illegal. Exactly the shape already established for `frag_color_pack.dst`
   (a hang wall there, a **contained fault** wall here). The region was mapped deliberately with
   **no abort path**; the device survived, there were no hangs, and the case after each fault runs
   clean.
3. **Cross-target:** EXP-0139 found the same byte on M4 (`iunary.dst`) faulting at 192–241 **and**
   243–255 — with **242 not faulting**. On G17P **242 does fault**. The pre-registered
   M4-transferred prediction is refuted at exactly that one value, which is why it was made.
   sem: **1268/1278 in each run** (the 10 misses are 242 and compiled+1, ×5 arms).

### 4.5 `iunary.b1` and `iunary.opsel` — LIVE; role unknown. No raw had ever existed.

**No `iunary` instruction exists in our compiled code.** Requiring instruction-**boundary**
alignment, **0 of 56** authored carriers emit one (EXP-0139 found 0 in 30 of its own); every
`byte0 == 0x27` instruction our compute MSL produces is claimed by a tighter descriptor. The
apparent hits before the boundary check were **interiors of longer instructions** — a
`b_alu10_lo7` at `cvt_i64@46` contains the bytes `27 11 00 02 …`. Census pass 1 is retained as
`raw/prefreeze/census_v1.json` beside the corrected pass 2.

So the fields were reached by **synthesis**: an 8-byte `ibitcount` occurrence rewritten in place to
`27 2d 22 …`, which tokenizes as `iunary` and — confirmed by each arm's own baseline in both runs —
**still computes the popcount**.

| field | structure, identical in both runs, both carriers |
|---|---|
| `b1` | the low **three** bits alone decide: `b1 & 7 == 5` delivers the correct count (**32 of 256**); `b1 & 7 == 6` delivers a different coherent value (**32**); the other **192** do not deliver, and their hardness is **carrier-dependent** — `not_written` on the store carrier, `ErrorPageFault` on the ALU-consumed carrier |
| `opsel` | **128 of 256** deliver and 128 do not, and the deciding bit is **bit 1 of byte+2** — the same bit the tight `ibitcount` descriptor models as `cache`. 0x54–0x57 re-tokenize as `ibitcount`, so the encodable range is **252 of 256** and those four are excluded rather than counted as movement |

Both maps are post-hoc, so the label stays at liveness: `untested`, `liveness: live`.

### 4.6 `cvt_f2i.b9` — ACCEPTED-INERT over a materially wider envelope

EXP-0168 refused it as INERT-SINGLE; EXP-0184's five carriers all varied **destination width/sign**,
which is byte+8's dimension, so for byte+9 they were one carrier. The six occurrences here span
**result routing** (byte+2 = 0x54 and 0x56), **convert op** (0x96 / 0xac / 0xb4), **source class**
(2 and 3), **source width** (float and half), a **vector** form and four destination registers; each
has a control (`dst`) that moves and fails the oracle.

**256 of 256 `ok` on all six, one distinct payload per arm, in both runs — 3072 ledger-verified
cases.** The pre-registered **live** model is refuted at 255 of 256 values per arm; that refutation
is the result. Safe wording: **inert in this envelope; global role unknown.** Untested: the
fragment and vertex stages, which need a render harness.

### 4.7 `cvt_f2i._instruction` — raised to `hardware-run` on G17P

(a) Seven authored convert carriers — stored, ALU-consumed, `rint`-rounded, vector, uniform-sourced,
half-sourced, and an out-of-range carrier — each reproduce a host-computed **truncate-toward-zero**
vector at their unmutated baseline, in both runs.

(b) With lane 7 fed `2147483904.0 = 2³¹ + 2⁸` (exactly representable in f32, **outside** int32), the
signed convert returns **`0x7FFFFFFF`**: **the hardware saturates, it does not wrap.** No in-range
test can reach that fact.

(c) Sweeping byte+7 dense 0..255 gives an exact, reproducible **seven-way map** of that lane:

| byte+7 | lane 7 | reading |
|---|---|---|
| 0x08–0x1F | `0x0000FFFF` | unsigned 16-bit, saturate high |
| 0x40–0x5F | `0x7FFFFFFF` | signed 32-bit, saturate high |
| 0x60–0x7F | `0x80000000` | signed 32-bit, saturate low |
| 0x80–0x9F | `0x000000FF` | unsigned 8-bit, saturate high |
| 0xC0–0xDF | `0x00007FFF` | signed 16-bit, saturate high |
| 0xE0–0xFF | `0x00008000` | signed 16-bit, saturate low |
| everything else | `0` | |

always with **bit 3 set** and **bit 4 a don't-care**. Read as a descriptor: bit 3 = enable,
bits 7..5 = destination class, and the observed bounds are exactly the {u8, u16, s16, s32} maxima
and their minima. This **confirms EXP-0013's "bit 6 selects signed vs unsigned" only in part and
refines it**: byte+7 is a destination width + signedness + saturation-bound descriptor, and bit 6
alone does not isolate the sign. Corroborated by our own compiler, which emits `0x48` for
`float→int` and `0x08` for `half→ushort`.

**The bit-field row `cvt_f2i.signflag` is deliberately NOT relabelled.** Its arm carries no
pre-registered control on that occurrence, so the mechanical gate returns `carrier-undecidable` for
the **field** even though the instruction-level claim stands. That arm-design gap is recorded rather
than papered over.

---

## 5. How this could have failed to say "no" — and the four times it nearly did

1. **The movement key included the outcome label.** `ok` and `unexpected_ok` are the *same* hardware
   observation (the carrier's vector was reproduced) differing only in what the oracle **predicted**.
   Without collapsing them, `shift_amt_move.src_flag` scores as **moved** at the compiled source
   index on four carriers — purely because the prediction differs there — while the observed word
   vectors are byte-identical. Found by re-deriving from raw. Fixed (`OUTCOME_NORM`). **This alone
   would have promoted the field this experiment ended up declining.**
2. **The census found `iunary` in three carriers and it was not there.** Signature-scan hits inside
   longer instructions decode cleanly. Adding an instruction-boundary walk removed all of them.
   Without it, two field verdicts would have rested on instruction interiors.
3. **The inertness verdict had no control in its own dimension** until the census found
   `b_alu10_lo7.src_flag`. With only the per-arm `kind`/`op_desc` controls, `src_flag` scores
   **ACCEPTED-INERT on ≥3 carriers** — a false inert claim, the kind that fails silently forever.
   The dimension-control dependency in `analysis/verdicts.py` is what turns it into
   `carrier-undecidable`.
4. **A semantic-check threshold that a 1-bit field cannot meet.** The first cut demanded ≥8 semantic
   checks per arm; `ibitcount.cache` has **two** encodable values, so it was refused by arithmetic.
   The threshold now scales as `min(8, encodable_range)` — the same shape as the width-1 defect
   `FIELD-SWEEP-PROTOCOL` §5b records.

**Where the criterion did return "no":** `shift_amt_move.src_flag` and `b_alu10_lo7.src_flag`
(carrier-undecidable), `cvt_f2i.b9` (accepted-inert; the pre-registered live model refuted at 255 of
256), `cvt_f2i.signflag` (declined for want of a control on its own occurrence, despite obvious
movement), `iunary.b1`/`opsel` (live but role unknown — no promotion), and every arm's pre-registered
predictor was refuted somewhere except the four `operands_b6` arms.

## 6. Limitations

* **Gate E is not met.** No quiet window existed; it was measured, not assumed.
* Compute stage only. `cvt_f2i.b9`, `ibitcount.cache` and `shift_amt_move.src_flag` are untested in
  the fragment and vertex stages, and the texture/interpolator producer class for `src_flag` needs a
  render harness.
* The `iunary` results are on a **synthesized** encoding (`27 2d 22 …`), reached because no compiled
  one exists. Its operand bytes are the host carrier's.
* `irotate.operands` is exhaustively covered **byte-wise**, not jointly: 70 of 2⁴⁰.
* The refined models for `ibitcount.cache`, `iunary.b1` and `iunary.opsel` are **post-hoc** and are
  offered as pre-registerable hypotheses for a successor, not as mapped semantics.

## 7. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (authored by us) and the _agc.main bytes the public Metal
                  runtime compiled from them
Apple binary introspection: NONE
Reproduction: analysis/census_b.py -> analysis/gen_arms_b.py -> harness/gated2.sh <id> <order>
              -> analysis/verdicts.py raw/g17p_20260830_run03 raw/g17p_20260830_run04
              -> analysis/report.py  -> analysis/wave_audit_recheck.py
Evidence: raw/g17p_20260830_run0{2,3,4}/sweep.jsonl + gpuwatch.jsonl (append-only), manifest.json
```
