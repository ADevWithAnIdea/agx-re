# EXP-0209 — RESULTS

Run id `EXP-0209-20260830T125606`. `db.json` sha256[:16] `2412eac1cad4449e`;
`tools/agx-isa/validation.json` sha256[:16] `a97e974cb35399e1`. Evidence index: 272
experiment cache files. **Tooling and analysis only; the device was not touched.**

`validation.json` is being written concurrently by EXP-0208, so every report pins both
input hashes. Between two runs 25 minutes apart the sidecar's inline `axes` count moved
6 -> 23 -> 28 and **not one of the seven dashboard figures changed**, because the
dashboards are scored from raw rather than from labels. Only the axes census moved.

Nothing here changes a label, a `docs/` page, `PROVENANCE.md`, or `validation.json`.
Per §9, no observation below is called false: rows are scored against the **current**
gates while the fact that they passed **their own frozen gate** is preserved.

---

## 1. The seven dashboards (§9)

Every figure is a numerator over a stated denominator. `no-data` is a **reported bucket
with a reason**, never a silent zero (§5).

On this first run `attained` equals `current` for every dashboard, because the ledger
was created by this run. The monotonicity is demonstrated separately in §3.

### 1. Encoding geometry coverage — denominator **1040** (every `db.json` field)

| rung | status | count | of |
|---:|---|---:|---:|
| 3 | `geometry-mapped` — Gate A holds and every encodable value reached the hardware | **502** | 1040 |
| 2 | `ledger-verified` — Gate A holds; the domain is not fully covered | 55 | 1040 |
| 1 | `bytes-seen` — actual bytes recorded, but Gate A unmet or no caller intent | 63 | 1040 |
| 0 | `no-data` | 420 | 1040 |

**43 of 1040 fields are wider than 16 bits.** For those, `geometry-mapped` is unreachable
by construction (2^24 is 16.7 M dispatches); FIELD-SWEEP-PROTOCOL 3.3 prescribes a sampled
set plus a dense per-byte sweep instead. That is a property of the ladder, not a gap.

### 2. Field/bit liveness coverage — denominator **1040**

| rung | status | count | of |
|---:|---|---:|---:|
| 3 | `decided-multi-carrier` — a detection-power control fired in ≥2 carriers | **99** | 1040 |
| 2 | `decided-one-carrier` | 55 | 1040 |
| 1 | `records-no-control` — dispatched, but no control fired | 466 | 1040 |
| 0 | `no-data` | 420 | 1040 |

`records-no-control` is **not** a negative result about the hardware. Gate B: zero
movement without a firing control is `carrier-undecidable`. These 466 rows need a
control arm, not a re-sweep.

### 3. Semantic-map coverage — denominator **1040**

| rung | status | count | of |
|---:|---|---:|---:|
| 3 | `semantically-mapped` — ≥2 buckets, discriminating oracle, ≥2 runs | **5** | 1040 |
| 2 | `bounded-map` — ≥2 behaviour buckets | 5 | 1040 |
| 1 | `checks-present` — `sem_checked > 0` | 57 | 1040 |
| 0 | `no-semantic-check` | 973 | 1040 |

The five are `falu2i.imm_exp`, `imm_mant`, `imm_sign`, `opsel`, `srcA_reg` — the only
fields in the corpus with a per-value host oracle that discriminates. `imm_exp` carries
528 checks over 3 buckets with 129 distinct oracle payloads across 2 runs.

A semantic check here is an **explicit host prediction compared against the
observation**. A liveness ladder prediction (`predict: "move"`), free prose, and an
oracle equal to the run's baseline are counted separately and are **not** semantic
checks — Gate C: *"A difference from baseline is not a semantic oracle."*

### 4. Canonical generated-recipe coverage — denominator **166** (emitter-relevant instructions)

| rung | status | count | of |
|---:|---|---:|---:|
| 3 | `canonical-recipe-proven` — generated, no donor field, 0 unmeasured fields | **2** | 166 |
| 2 | `generated-no-donor` | 2 | 166 |
| 1 | `generated-point` — generated, donor fields remain | 14 | 166 |
| 0 | `not-generated` | 148 | 166 |

`mov_imm` and `stop` are the two at the top rung; `device_store` and `falu2` are
generated with no donor field but still carry unmeasured fields. This agrees with
EXP-0173's own count (`GENERATED-AND-EMITTABLE: 2`).

**This dashboard has thin data, and the reason is the registry, not the hardware.** The
only committed machine-readable recipe registry is
`EXP-0173-closure-audit/analysis/template_dependency.json`, covering **35 mnemonics**.
The other 131 emitter-relevant instructions score `not-generated` because *no generated
program containing them has been recorded* — a statement about registry coverage as much
as about the silicon. Any experiment can advance this dashboard by committing an
`analysis/generated_recipe.json` in the same shape.

### 5. Direct G17P revalidation coverage — denominator **1040**

| rung | status | count | of |
|---:|---|---:|---:|
| 3 | `G17P-direct-repeated` — ≥2 G17P raw runs | **432** | 1040 |
| 2 | `G17P-direct` | 3 | 1040 |
| 1 | `G16G-direct-only` | 177 | 1040 |
| 0 | `no-direct-target-evidence` | 428 | 1040 |

`G16G-direct-only` is not a failure: committed M4 evidence stays valid on its own target
and is not retracted; it simply does not close a row whose claimed target is G17P.

### 6. Reproducible evidence-chain coverage — denominator **1212** (all `validation.json` claim rows)

| rung | status | count | of |
|---:|---|---:|---:|
| 3 | `independently-confirmed` — ≥2 raw runs and a second carrier or experiment | **264** | 1212 |
| 2 | `auditable` — records in `raw/` | 333 | 1212 |
| 1 | `citation-resolves` — directory, `raw/` and authored probe exist; no record found | 248 | 1212 |
| 0 | `incomplete` — unresolvable citation, no `raw/`, no authored probe, or quarantined | 367 | 1212 |

For the pre-EXP-0138 rows, `citation-resolves` is usually **format-unreadable**, not
absence; `dashboard_detail.json` carries the per-key reason.

### 7. Finite-resource limit and overflow coverage — denominator **987** (fields of width ≤ 8)

| rung | status | count | of |
|---:|---|---:|---:|
| 3 | `limit-mapped` — full domain dispatched AND the legal/rejected boundary crossed | **133** | 987 |
| 2 | `full-domain-swept` — full domain, but no value rejected (or none legal) | 382 | 987 |
| 1 | `partial-sweep` | 79 | 987 |
| 0 | `no-data` | 393 | 987 |

**§6 also requires limits for finite *resources*** — base slots, texture selectors,
register banks, scoreboards, queues, nesting stacks, descriptor tables. The corpus
commits **no machine-readable registry of those**, so they are **0 of 0** here: not
scored zero, not counted as covered. Building that registry is the prerequisite for
scoring them, and this is the dashboard with the largest structural hole.

### The §2 `axes` sidecar — census, reported as absence where absent

| source | rows carrying an `axes` object |
|---|---:|
| `validation.json` (inline) | 28 |
| `EXP-0208-axis-reclassification/analysis/axes.json` | 496 |
| **union (an inline object wins)** | **501** |
| **`db.json` fields with NO axes object** | **539 of 1040** |

Cross-checking the declared axes against this run's independent re-derivation from the
same raw: geometry agrees on **401**, disagrees on **80**, not comparable on 20;
semantics agrees on **435**, disagrees on **51**, not comparable on 15. And the check
that matters most: **128 rows declare a liveness *answer*** (`live` / `accepted-inert` /
`inert`) **while no detection-power control fired in the cited raw** under this
indexer's control detection — Gate B makes that `carrier-undecidable`. Full list in
`reports/axes_crosscheck.md`. A disagreement is not automatically a defect in either
party; it marks a row where two independent derivations from the same raw did not land
in the same place.

---

## 2. What the promotion checker rejects that `validate_labels.py` passes

`python3 tools/agx-isa/validate_labels.py` **exits 0** on the current corpus. The §8
checker examines the same 1212 claim rows and reports, per axis:

| axis | PASS | REJECT | INSUFFICIENT | N/A | rows |
|---|---:|---:|---:|---:|---:|
| geometry (R3, R4) | 530 | 68 | 442 | 172 | 1212 |
| liveness (R6, R9) | 112 | 179 | 580 | 341 | 1212 |
| semantics (R5) | 5 | 42 | 584 | 581 | 1212 |
| recipe (R8) | 41 | 55 | 535 | 581 | 1212 |
| target (R2) | 610 | 2 | 600 | 0 | 1212 |
| audit (R1, R7) | 461 | 562 | 149 | 40 | 1212 |

`REJECT` means the raw **contradicts** the rule; `INSUFFICIENT` means the raw **does not
contain** what the rule needs. Both block promotion; they are counted apart because §9
forbids collapsing "we looked and it is wrong" into "nobody has measured it".

### Over the 631 emitter-grade rows (`hardware-run` / `isolated-byte-diff`)

**631 of 631 have at least one blocking rule.**

| rule | REJECT | blocking (REJECT + INSUFFICIENT) |
|---|---:|---:|
| R1 evidence path / authored input | 55 | 55 |
| R2 target | 2 | 185 |
| R3 actual-byte ledger | 51 | 144 |
| R4 range coverage | 46 | 150 |
| R5 semantics | 42 | **626** |
| R6 detection power | 91 | 495 |
| R7 repetitions / second method | 235 | 416 |
| R8 donor fields | 55 | 590 |
| R9 cascade contamination | 49 | 148 |

And over the **32 mnemonics `validate_labels.py` reports as `emittable`**: for **0 of
32** does every claim row clear all nine rules. R5 blocks every row of all 32
(`analysis/emittable_set_under_section8.json` has the per-mnemonic breakdown).

### Named rows, with the exact finding

| row | label / target | `validate_labels.py` | promotion checker |
|---|---|---|---|
| `falu2.opsel` | `hardware-run` / G17P | passes | R1–R4, R6–R8 **PASS** — geometry is perfect: 80/80 records decoded, 8 distinct actual encodings for 8 claimed values, 6 control arms fired, 2 raw runs, 3 carriers. **R5 INSUFFICIENT: 0 semantic checks; the cited raw carries 80 *liveness ladder* predictions instead.** §2: `sem_checked == 0` can never produce `hardware-run`. This is the EXP-0169 Tier-2 error, still standing. |
| `falu2.srcB_reg` | `hardware-run` / G17P | passes | **R3 REJECT** — 512 records where the requested value ≠ the value decoded from the actual dispatched bytes; the requested values run past the field's **6-bit** encodable range, so `value` is a byte-level intent and the ledger does not establish that the *field* took it. **R5 REJECT** — 512 semantic checks covering **one** behaviour bucket. |
| `atomic_mem.index_reg` | `hardware-run` | passes | **R3 REJECT** — 514 ledger disagreements; requested values exceed the field's **7-bit** range. |
| `cvt_bf16.dst` / `cvt_f2h_dst.dst` | `hardware-run` | passes | **R3 REJECT** — the sweep dispatched `value` as byte 0 (`value=1 → byte0=0x01`, `value=17 → byte0=0x11`), so the 4-bit `dst` nibble only followed the high half: 16 ledger disagreements each. |
| `falu3.dst`, `falu3.srcA`, `falu3_ext.dst`, `falu3_ext.srcA`, `fspecial.dst` | `hardware-run` | passes | **R4 REJECT** — the claim covers 16/253/16/256/192 values but **1 distinct actual encoding** reached the hardware. The DEF-0166-1 signature. |
| `device_load.idx_off` | `hardware-run` | passes | **R4 REJECT** — claim covers 2048 values; 14 distinct actual encodings reached the hardware. |
| `half_alu.dst` | `hardware-run` / **G17P** | passes | **R2 REJECT** — the cited raw ran on **G16G**. |
| `icmp_pred.dst_pred` | `hardware-run` / **M4+A18** | passes | **R2 REJECT** — the cited raw ran on G16G only; the A18/G17P half of the claim has no direct evidence. |
| `falu2_ext.dst`, `.mod_lo`, `.srcA_reg`, `.srcB_neg` (+87 more emitter-grade; 116 rows overall) | `hardware-run` | passes | **R6 REJECT** — a detection-power control arm is present and **none moved**. Gate B: the carrier could not have shown the effect either way. |
| `atomic_mem._instruction`, `atomic_rmw._instruction`, `falu2_ext._instruction` (+52 more emitter-grade; 327 rows overall) | `hardware-run` | passes (the citation *directory* exists) | **R1 REJECT** — the cited experiment (`EXP-M4-10-isa-coverage`) has **no `raw/`** and **commits no authored probe**. `validate_labels.py` checks that the directory exists; it never opens it. |
| `device_load.base_slot`, `.dst_lo`, `.dst_ext9` (+52 more) | `hardware-run` | passes | **R8 REJECT** — the field is still supplied by a **copied donor** in the only generated program that contains the instruction (EXP-0173). |
| `bf_alu.opsel`, `carry_gen.dst`, `atomic_mem.addr_desc_hi` (+46 more emitter-grade; 71 rows overall) | `hardware-run` | passes | **R9 REJECT** — hard outcomes (63/78/24 faults) share the cited raw with cascade markers (`victim`, `sentinel_bad`), and were never repeated in isolation. Gate E: a malformed runner response is `measurement_failure`, never a hardware outcome. |

**The single structural fact:** `validate_labels.py` checks that a cited directory
*exists*. It never opens it. Every rejection above comes from opening it.

### One data-shape hazard found while building the ledger

`EXP-0169` writes `bf_alu.tail` records that **name the field** (`field: "tail"`) while
carrying `byte_index: 5` — the sweep is over byte 5 of a 24-bit field, so `value` is a
byte, not the field's value. A naive Gate A comparison reports **1,536 false
disagreements** on that one row. The indexer therefore routes each record to a *field*
ledger or a *byte* ledger by the caller's own declared bits (`fstart`/`fwidth` first,
`byte_index` next), and both routings are self-tested. The same care removed six further
false R3 rejects.

A second hazard: derived artifacts. `EXP-0197`'s own `work/scan_call_offset.json` and
similar audit outputs contain records that a naive walk indexes as dispatches. The
indexer keeps `raw/` records and derived records in **separate cell sets** and the
promotion checker consumes only the raw one — 4,154,516 cell records are in `raw/`,
150,979 are not, and 33 experiments have cells *only* outside `raw/`.

---

## 3. The dashboards cannot reset themselves — demonstrated on real data

`work/monotonicity_demo/` holds a copy of the production ledger scored against an
**empty evidence index** — the worst case §9 anticipates, "a shared tool had a defect"
taken to its limit, where every citation resolves to nothing.

| dashboard | attained | current after total evidence loss | downgrades enumerated |
|---|---:|---:|---:|
| 1 geometry (`geometry-mapped`) | **502** | 0 | 620 |
| 2 liveness (`decided-multi-carrier`) | **99** | 0 | 620 |
| 3 semantics (`semantically-mapped`) | **5** | 0 | 67 |
| 4 recipe (`canonical-recipe-proven`) | **2** | **2** | **0** |
| 5 target (`G17P-direct-repeated`) | **432** | 0 | 612 |
| 6 audit (`independently-confirmed`) | **264** | 0 | 597 |
| 7 limits (`limit-mapped`) | **133** | 0 | 594 |

`attained` did not move. Every loss is reported as a **scoped downgrade** with the
reason and the run that attained it — reported, never applied (§9: "A broken citation or
missing raw artifact downgrades auditability; it does not by itself prove the hardware
fact false"). Dashboard 4 is untouched at 0 downgrades because it reads the recipe
registry rather than the evidence index: that is cross-dashboard independence
demonstrated on real data, not asserted.

The mechanism is structural, not conventional. The ledger is append-only JSONL, one line
per `(dashboard, key, run)`; `attained` is a **max over its lines**. A later run can only
add lines, so no later run can lower a figure. The production ledger holds 13,050 lines
over 2 runs and was untouched by the demonstration.

---

## 4. How these gates could have failed to say "no"

This corpus produced thirteen checks that could not come out the other way, including
gates that counted a GPU fault, and our own disassembler failing to decode, as hardware
movement. Every gate here is self-tested in **both** directions, and a well-formed input
must be **accepted**, because a gate that refuses everything is as broken as one that
refuses nothing.

- `evidence_index.py --selftest` — **27 assertions.** Gate A decodes a value out of
  actual bytes *and* returns a different value for different bytes *and* refuses
  unparsable bytes; a `predict: "move"` ladder record scores **0** semantic checks while
  an explicit `sem_match` scores 1; free prose scores 0 while a `predict` naming a known
  outcome scores 1; an oracle equal to the baseline is flagged as a baseline comparison
  while one that differs is not; a `role: falsifier` record lands in the control cell and
  a swept-field record does not; a **fault** and an **`undecodable`** are not counted as
  valid payloads while a clean record is; a byte-0 sweep reaches a byte-0 field and a
  byte-9 sweep does not; a `g17p` run dir yields G17P, an `m4` dir G16G, and `pilot01`
  yields **no target rather than a guess**.
- `promotion_check.py --selftest` — **26 assertions** over a synthetic corpus built so
  each of the nine rules can be made to fire one at a time: **13 must-reject cases**,
  **9 must-accept cases**, one **must-be-promotable** whole row, plus two structural
  assertions. The must-accept half is the important half: R1–R8 each accept a
  well-formed claim, and a fully clean row comes out `promotable`. `R6` is tested three
  ways — control fired (PASS), control present but never moved (REJECT), no control at
  all (INSUFFICIENT) — so "failed" and "absent" cannot collapse.
- **The label must not drive the verdict.** A dedicated assertion feeds a row *labelled*
  `hardware-run` whose raw has zero semantic checks and requires it to be **rejected**.
- **§8's explicit prohibition is self-tested.** After writing all six reports the test
  greps them for `N of 166`, `emittable_instructions`, and `emittable: <n>` patterns and
  fails if any appears, and asserts all six report files exist.
- `dashboards.py --selftest` — **16 assertions of its own, 25 printed** (it runs the
  axes cross-check's 9 as well). The reset test: a later run that sees
  nothing must not lower `attained`, *while* `current` falls and both losses appear as
  scoped downgrades with reasons. The opposite test: a better run must **raise**
  `attained` and clear the downgrade list — a counter that can only rise is useless if it
  rises for free, and one that can be talked down is the defect §9 exists to prevent. A
  repeat run must change nothing in either direction. The append-only property is
  asserted by line count and run ids. Cross-dashboard independence is asserted directly:
  a semantic correction must leave geometry untouched *and* be reported as a scoped
  semantic downgrade. A corrupt or unknown ledger line must be skipped, not scored.
- `axes_sidecar.py` — **9 assertions**: agreement and disagreement on both the geometry
  and semantics axes, the "answer asserted without a firing control" flag firing on two
  rows and *not* firing on a `carrier-undecidable` row, and a fully agreeing row
  producing **zero** disagreements.

**Where they could still fail to say "no", stated plainly:**

1. **Control detection is convention-bound.** Gate B controls are found by field-name
   prefix (`__ladder`, `__fals`, `__ctl`, `__power`, `__sens`) or an explicit `role` key.
   Only 20 of 272 experiments use either. An experiment that encodes its positive control
   another way is scored `records-no-control` — an understatement, not an overstatement,
   but a false negative all the same, and it inflates the R6 INSUFFICIENT count.
2. **R2 reads run-directory names.** Target comes from `g17p`/`m4`/`m5` in the raw run
   dir. An experiment naming its runs `run01` yields no target and scores INSUFFICIENT
   (600 rows). That is why R2 shows only 2 REJECTs against 600 INSUFFICIENTs.
3. **R8 is registry-bound.** 590 of 631 emitter-grade rows are blocked by R8, and 535 of
   those are INSUFFICIENT purely because EXP-0173's registry covers 35 of 166 mnemonics.
   That is a missing input, not a hardware finding.
4. **K4 is not run corpus-wide.** The deep hex-blob tokenization is opt-in. The 420
   `no-data` geometry rows include an unknown number whose evidence is real but sits in
   `.txt`/`.hex`; they are reported as `format-unreadable`, not as zero, and a corpus-wide
   `--deep` pass would move some of them up.
5. **The semantic bucket map is a fixed vocabulary.** An experiment that spells its
   outcomes differently scores `no-semantic-check`. Again an understatement.

None of these five can make a gate say "yes" when it should say "no"; all five can make
it say "insufficient" when the evidence exists in a shape the indexer does not read. That
is the safe direction, and each is a named, fixable input gap rather than a judgement.

---

## 5. What this experiment did and did not establish

**New raw observations:** none. No device was touched.

**New geometry facts:** none about the hardware. One about the *evidence*: 502 of 1040
fields have a Gate A ledger that holds over their full encodable domain, 55 more hold
partially, 63 have bytes without a usable caller intent, 420 have no machine-readable
record.

**New liveness facts:** none about the hardware. 466 of 1040 fields have dispatch records
with no firing detection-power control — `carrier-undecidable`, not inert.

**New semantic facts:** none. The corpus contains 5 fields with a discriminating per-value
host oracle over ≥2 runs, all on `falu2i`.

**New generated recipes:** none. 2 of 166 emitter-relevant instructions are
`canonical-recipe-proven` in the committed registry.

**Claims downgraded:** none. This experiment changed no label and retracted nothing. It
reports that 631 of 631 emitter-grade claim rows do not meet the *current* §8 promotion
gate, while §9 requires — and these dashboards preserve — the geometry, liveness and
target evidence those same rows *did* establish under their own frozen gates.

**Bounded unknowns remaining:** the five limits in §4 above; the finite-*resource*
registry that dashboard 7 has no input for; and the 544 of 1040 fields with no §2 `axes`
object at all.

---

## 6. Note on the working tree

This experiment ran no `git` write command. Its files nevertheless appear in commits
`1c3bb747`, `d5d8703c` and `170555c9`: the orchestrator's `git add -A` swept the
directory in while it was being written. Nothing in `tools/agx-isa/validation.json`,
`docs/`, `PROVENANCE.md` or `tools/agx-isa/validate_labels.py` was modified by EXP-0209
— `git status` on those four paths is clean of any change of ours.
