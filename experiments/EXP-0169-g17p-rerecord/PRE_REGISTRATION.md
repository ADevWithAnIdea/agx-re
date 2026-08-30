# EXP-0169 — PRE-REGISTRATION (frozen before any device dispatch)

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, Metal family Apple9). Every claim produced here is a **G17P** claim.

**Frozen:** 2026-08-30, before `harness/anchors.py` was ever run on the device.
Source hashes, the raw record schema, the coverage rule, the oracles, the falsifiers,
the liveness ladder and the promotion gate below are fixed. The only thing that is *not*
fixed at this moment is the **resolved** case matrix, because it depends on where the
compiler puts each anchor; the **rule** that resolves it is frozen (§4), and the resolved
matrix sha256 is written into `raw/<run>/00_env.json` **before the first gated dispatch**
and must be identical in both gated runs.

---

## 1. The question

EXP-0164 (commit `459bb8bd`) re-derived every emitter-grade field in
`tools/agx-isa/validation.json` from committed `raw/` and found **144 fields — 21.7% of
everything labelled emitter-grade — with no per-value raw record attributable to them**.
Their promotions cannot be reproduced from committed evidence, which fails `CLAUDE.md`'s
Definition of Done by construction ("the final audit *positively reproduces* the claimed
generation paths").

> **This is an auditability gap, not a refutation.** The fields may well be correct. The
> job is to make the claims auditable — by **re-sweeping**, never by re-labelling.

### 1a. What the offline analysis already settled (no device needed)

`analysis/recitation.py` re-runs **EXP-0164's own gate** (`stable_live`, thresholds copied
verbatim) over the *whole* raw index rather than only the experiments a field's `evidence`
array happens to cite — because `EXP-0164/analysis/audit.py::gather()` consults only the
cited experiments. Result (`analysis/recitation_recovery.json`):

| | |
|---|---|
| `RECOVERABLE-BY-CITATION` | **12** — an *uncited* experiment already carries per-value records that clear EXP-0164's own gate |
| `RECORDS-BUT-FAILS-GATE` | **3** — `icmp_pred.cond` (97.66% cross-run, below the 99% bar), `pixel_order.kind` (one gated run), `ray_move.b3` (255 values, 0 moved) |
| `NO-RECORDS-ANYWHERE` | **129** |

The 12 need a **citation fix in `validation.json`**, which is the orchestrator's file, not
a device. Several of them also *move the field's target*: `falu2.opsel`, `falu2.srcA_reg`,
`falu2.srcB_reg`, `falu2.srcB_reg_top` are recoverable from **EXP-0153, which ran on
G17P** — strictly better than the M4/A18 evidence currently cited. `ibitcount.*`,
`falu_srcmod12b.*`, `device_load.*` are recoverable from M4 experiments, so a citation fix
would relabel their `target` from A18 to M4. **That call is the orchestrator's.**

### 1b. Scope of the device work

Coordinator directive 2026-08-30: **EXP-0168 owns the field name `dst` on all 14
descriptors that carry it, plus the 12 "one-field-away" fields** (including
`mov_imm.imm_top`, `pixel_order.kind`, `stop.reserved`). This experiment owns everything
else in the 144.

`dst` is nevertheless **swept** here, because *which register slot changed* is this
experiment's primary detection instrument. **No verdict is emitted for any `.dst` field**
(`analysis/verdicts.py` emits `label: untested` with an explicit hand-off note), so the
two experiments remain verdict-disjoint while both raws stay attributable.

**57 fields are in device scope** (order of attack in §2):

| wave | fields | why this order |
|---|---|---|
| **A** `falu2` 8, `falu2i` 8, `falu2_uni` 1 | **17** | `falu2` is the most-cited descriptor in the DB; 13 of its 15 withheld fields are in this class, and every emitter that does float arithmetic emits it. It also carries three *published* semantic claims (§6) that are not auditable at value level anywhere in the corpus. |
| **B** `half_alu` 4, `half_alu_ext8` 7, `half_alu_fma12` 2, `iunary` 2 | **15** | the EXP-M4-14 citations that are ALU-shaped. **EXP-M4-14 has no `raw/` tree at all** — one run, a narrative `splice_results.json` at the experiment root, no per-case records — so these are the emptiest evidence in the whole withheld set. |
| **C** `reg_move_c0` 4, `c1` 3, `c2var` 4, `c9` 4, `cb` 3 | **18** | EXP-0140 is the second-most-cited experiment (20 withheld fields). Its raw exists but logs `instr` as `regmove`, which is not a db mnemonic, so per-value attribution mostly fails. Pure register moves suit the 16-GPR dump oracle exactly. |
| **D** `bf_alu.opsel`, `icmp_pred.cond`, `get_sr.dst_hi`, `get_sr.sr_sel`, `device_store.{base_slot,idx_off,index_reg}` | **7** | cheap on the same harness; `icmp_pred.cond` in particular already has attributable records and fails *only* the 99% gate, so a quiet-window gated pair is exactly the right fix. |

**Explicitly OUT of scope and handed on** (needs a graphics / texture / RT / control-flow /
spill-frame harness this experiment does not build): `tex_addr_setup` 11, `matrix_mac` 10,
`link_save_restore` 6, `tex_sample` 5, `frag_color_pack` 3, `frame_prologue` 3,
`rt_query_traverse` 3, `simd_shuffle` 3, `spill_frame_marker` 3, `frag_color_store` 2,
`iter` 2, `simd_reduce` 2, `vary_store` 2, `call` 1, `if_push_pred` 1, `imageblock_load` 1,
`imageblock_store` 1, `jump` 1, `ray_move` 1, `rt_intersect` 1, `simd_ballot` 1,
`tex_deriv` 1 — **64 fields**. Naming them here is part of the result: an honest bound
beats a half-swept arm.

**Open question for the orchestrator:** is `get_sr.dst_hi` one of EXP-0168's 12
"one-field-away" fields? If so, drop it from wave D; the raw stays valid either way.

---

## 2. Hypotheses (falsifiable, with refuters)

**H1 (the experiment's own claim).** For each of the 57 fields, a fresh two-run gated
sweep in the EXP-0138+ per-case schema produces records that **EXP-0164's own
`collect_raw.py`, unmodified, attributes bit-exactly to that db field**, on ≥2
structurally different carriers.
*Refuter:* `analysis/reindex_check.py` reports a field ruled on in
`field_verdicts.json` with no bit-exact attribution under `EXP-0169`. That is a **failure
of this experiment**, printed as one, not a footnote.

**H2 (reproduction).** Every field whose original `validation.json` label is
`hardware-run` or `isolated-byte-diff` shows, in the fresh capture, behaviour consistent
with the original `range` claim.
*Refuter:* a field that is exhaustively swept, cross-run stable, on ≥2 carriers **whose
liveness ladder passed**, and shows **no observable effect** while the corpus claims a
live one — or a value-level disagreement with the host-computed oracle (§6). Either is a
`DOES-NOT-REPRODUCE`, and **those are reported first and loudest**: it means the corpus has
been carrying a wrong fact.

**H3 (detection power is the real variable).** The standing finding — an apparently-inert
field usually means the carrier could not express what the field controls — predicts that
some fields read inert on `C1_alu` and live on `C2_load`.
*Refuter:* no field differs between the two carriers, i.e. provenance and operand width buy
nothing. That would be a real (negative) result about the carrier design, and is recorded
as one.

**H4 (`falu2` published semantics).** The three published `falu2` claims hold at value
level on G17P: (a) EXP-0138's source-class model and the **inline 8-bit minifloat
immediate** at `srcB_class==1`, `srcB_reg` 64..127; (b) EXP-0158's finding that the inline
immediate's **sign is negative at `srcB_neg==0`**; (c) EXP-0158's finding that
`falu2.mod_hi` is **operand-provenance-dependent** — inert for an ALU-sourced operand, only
`0xC` of 16 working for a load-sourced one.
*Refuters:* (a)/(b) any value in 64..127 where the observed destination word differs from
`isa_helpers.inline_minifloat(v)` (negated per `srcB_neg`) added to / multiplied by the
seed; (c) `mod_hi` behaving identically on `C1_alu` and `C2_load`, or a value other than
`0xC` working on `C2_load`.

---

## 3. Variables

**Independent:** exactly one db.json field (or one constituent byte of a wider field) per
case. **Controlled:** every other byte of the instruction, the whole surrounding program,
the seed table, the dispatch shape (grid=1, tg=1 except the NATIVE arm at 8/8), the
carrier binaries, the input buffers, and the pinned `db.json`/`isadb.py`.

**Carrier axis (deliberately varied, never held):**

| id | seeds | why it is not the same carrier as the others |
|---|---|---|
| `C1_alu` | `mov_imm` / `falu2i` | ALU-sourced operands; float seeds have **zero** low halves |
| `C2_load` | `device_load` from a ramp | **LOAD-sourced** operands with **non-zero low halves**: the provenance dimension EXP-0129/EXP-0158 identified, and the only way a `b16` source read is a *different non-zero value* instead of `0.0` |
| `C3_uni` | `mov_imm` / `falu2i`, uniform file preloaded | the only carrier where `falu2_uni.uni_mode` and `falu2.srcB_class==1` (non-GPR file) exist; also a different buffer signature, which `reg_move`'s read-back is documented to depend on (EXP-0087) |
| `C4_store` | as `C1_alu`, 8256-word read-back | so a `device_store` `idx_off`/`base_slot` sweep that lands in range is seen as a store, not misread as a fault |
| `NAT_kcmp` | none — the probe kernel's own program | `icmp_pred` sets a predicate only a divergent block consumes; a straight-line synthesized program is structurally blind to it |

**Two carriers identical in the dimension the field controls are one carrier.** Every
carrier above differs from the others in a dimension some withheld field is known or
suspected to control.

---

## 4. Method (frozen)

**Program shape** (`harness/isa_helpers.py::synth_program`):

```
seeds r0..r15 (16 distinct values, provenance per carrier)
PRE  sentinel -> stored to memory                <- before the block; immune to
[ INSTRUCTION UNDER TEST, exactly ONE field mutated ]   release-on-read
dump ALL 16 registers -> 16 output words
POST sentinel (its register written AFTER the block) -> stored
stop
```

* **`mode='lift'`** — the block is lifted **byte-for-byte** from the compiled form of our
  own MSL (`kernels/probes.metal`), so every executed byte is either a compiler-valid
  anchor byte or the one field this case is sweeping.
* **`mode='synth'`** — the instruction is **assembled from db.json's own field rules**
  (`reg_move_*`): an independently generated encoding executed on hardware, the strongest
  evidence level in `CODEX.md` §3.
* **`mode='store'`** — the probe `device_store` runs *after* the dump, so wherever it lands
  is visible against the poison while the dump still proves the program ran.
* **`mode='nat'`** — spliced in place in its own compiled kernel (`icmp_pred` only).

**Anchor resolution rule (this is the frozen part).** Arms name a target **mnemonic**, not
a byte offset. `casematrix.resolve_arms()` takes the first occurrence of that mnemonic, in
the frozen `KERNEL_ORDER`, whose widened window contains no `NON_LIFTABLE` instruction and
no unresolved length. **An arm that does not resolve is dropped and reported as a miss**
(`raw/<run>/00_arm_resolution.json`), never patched around.

**Coverage rule (FIELD-SWEEP-PROTOCOL §3.3).** width ≤ 8 → **all 2^w values**; width > 8 →
each constituent byte swept **0..255**. Byte-wise sweeps still yield per-field attribution
under `collect_raw.py`, which partitions records by "the instruction word with the field's
bits cleared" and counts movement only *within* a partition.

**Departure from EXP-0154, recorded deliberately:** `get_sr` is treated as liftable. It
names no buffer binding, and at grid=1/tg=1 every SR this harness reaches is deterministic.

---

## 5. Instruments (all three are mandatory, per FIELD-SWEEP-PROTOCOL §7)

1. **Poison.** The read-back buffer is filled with `0xDEADBEEF` before **every** dispatch.
   Without it "wrote 0" and "never executed" are indistinguishable, and on this ISA a wrong
   field value usually yields a silent zero.
2. **Two sentinels, neither reachable by the instruction under test.** PRE is in memory
   before the block runs; POST's register is written after it. Reading a GPR as a 32-bit
   source *zeroes* it, and EXP-0138 lost six sweeps by seeding its sentinel in a register
   the instruction then read. Release-on-read is thereby converted from a trap into an
   **oracle**: the register that went to zero is the register the swept operand named.
3. **The OS fault-classification string is recorded verbatim** on every non-`ok` case;
   `...ErrorInnocentVictim`-class failures are flagged `victim`. Per EXP-0158/EXP-0160 this
   is **not a complete defence** — contamination can arrive with no victim string, and a
   contaminated dispatch can report `STATUS OK` and write nothing — which is why the poison
   and the sentinels are adjudicated offline as well.
4. **The oracle is the FULL 16-GPR dump**, plus both sentinels, plus every other word that
   is no longer poison. A single-word read-back is blind to any field whose effect is
   *where* a result lands; the audit's `uniform_mov.dst` "16 values dispatched, 0 moved" is
   the signature of exactly that blindness.

**Quiet window.** Both gated runs are confirmation-grade captures, so per
FIELD-SWEEP-PROTOCOL §7 they run in an orchestrator-coordinated quiet window, and
concurrent GPU activity is **sampled into `raw/<run>/03_procsample.jsonl`** so "the machine
was quiet" is a measurement rather than a claim.

---

## 6. Oracles

**Tier 1 — host-computed, GPU-independent** (`harness/run.py::sem_oracle`). Applies to the
arms where the point of the sweep is a *published semantic claim*:

* `falu2`, `srcB_class==1`, `srcB_reg` 64..127 →
  `k = inline_minifloat(v)`, `k = -k if srcB_neg==0`, expected `r[dst] = seed op k`.
  Derivation: db.json's own `falu2` semantics (EXP-0138), reproduced in
  `isa_helpers.inline_minifloat`, cross-checked in `harness/selftest.py` against EXP-0138's
  ten HW-confirmed points (k=0→0.0, 2→0.0625, 31→1.875, 32→2.0, 48→8.0, 56→16.0, 63→30.0).
* `falu2i` → `isadb.imm_decode(b1, sign)` over the **whole** packed immediate space
  (exp × mant × sign × flag = 512 combinations), expected `r[dst] = seed op K`.

`sem_match` is recorded per case. **Any value-level disagreement is an H4 refutation.**

**Tier 2 — the unmutated anchor's full architectural state** (EXP-0154's oracle) for every
other arm: 16 registers + both sentinels + the stray-word map must match the baseline for
`ok`. This is strictly stronger than a single output word, and it is honestly weaker than
Tier 1: it detects *difference*, not *correctness*. `RESULTS.md` states which tier each
field was ruled on.

---

## 7. Falsifiers and the liveness ladder (pre-registered to fail / to move)

Per **(arm, carrier)**:

* **Falsifier** `__falsifier_byte0`: byte0 of the instruction under test forced to `0x00`.
  **MUST NOT** score `ok`. If it does, that arm's sweep proves nothing and is reported so.
* **Ladder** — each step **MUST** move the observation:
  `L_dst` (destination slot), `L_srcA_reg`/`L_src`/`L_src_reg` (operand selection),
  `L_opsel`/`L_form` (operation select — the seeds are chosen so `a+b ≠ a*b`),
  `L_srcA_size`/`L_srcB_size` (operand width — has detection power **only** where the
  seed's low half is non-zero, i.e. on `C2_load`; recorded on every carrier so the
  *difference between the carriers* is itself in the raw),
  `L_idx_off`/`L_extmode` (`device_store`: where it lands, what it stores),
  `L_known_move` (`reg_move` only: EXP-0140's HW-validated `byte+1=0xD5, byte+2=0x01,
  byte+3=0x08`, which writes 85 to the destination — if *that* does not move, the carrier
  cannot see a `reg_move` write at all).

**Gate zero.** A field is ruled on **only** on (arm, carrier) pairs whose ladder passed.
An inert reading on a carrier with no demonstrated detection power is reported `untested`,
never as `hardware-run` and never as "the field is inert". This is the `iter_at.loc`
failure mode: every arm of that experiment was `samples=1`, where centroid and sample are
the same point, so an inert reading was guaranteed regardless of the hardware.

---

## 8. Promotion gate (frozen, not tunable)

Identical to EXP-0164's `audit.py::stable_live`, so the two are directly comparable:

```
common values >= 2
per-value cross-run agreement >= 99.0%
movedA >= 1 and movedB >= 1
min(movedA, movedB) >= 2.0 x disagreements
```

Verdict classes and the label each maps to (`docs/evidence-classification.md` §2 labels
only):

| class | condition | label |
|---|---|---|
| `LIVE` | gate passes on ≥1 ladder-passing carrier | `hardware-run` |
| `INERT-MULTI` | exhaustive, cross-run stable, **zero** movement on **≥2** ladder-passing carriers | `hardware-run`, range says "no observable effect" |
| `INERT-SINGLE` | as above but only **one** carrier had detection power | `untested` |
| `UNSTABLE` | movement does not reproduce at ≥99% | `untested` |
| `NO-DETECTION-POWER` | no (arm, carrier) passed its ladder | `untested` |
| `SEMANTIC-ORACLE-FAILED` | any Tier-1 value-level disagreement | `untested` + `DOES-NOT-REPRODUCE` |

Never any other label. A sweep that is inconclusive says `untested`; it is not rounded up.

---

## 9. Known confounders, and what is done about each

| confounder | mitigation |
|---|---|
| A sibling experiment's GPU hang resets the device and discards our command buffers | quiet window; victim string recorded verbatim; baseline re-acquired with backoff; majority-of-3 before any `fault`; `victim` cases segregated in analysis |
| A contaminated dispatch reports `STATUS OK` and writes nothing (EXP-0160 saw 25 such) | poison + both sentinels; `sentinel_bad` recorded per case; such cases are adjudicated offline, never counted as `silent_zero` |
| Release-on-read destroys the witness (EXP-0138 lost six sweeps) | neither sentinel lives in a register the instruction can name while it runs |
| The mutated instruction re-tokenizes as a *different* descriptor (`reg_move_c2var.subform`, `reg_move_cb.form`) | `instr` stays the descriptor the arm is testing (so attribution is per-descriptor); `tok_instr` records what `isadb` makes of the mutated bytes; `rt_ok` records round-trip |
| `tools/agx-isa/db.json` drifts under us (EXP-0165 owns it and is editing it now) | the exact `db.json`/`isadb.py` the hardware ran against is pulled back into `work/frozen/` and sha256-recorded; verdicts are keyed to that, not to the live repo copy |
| Repo `HEAD` moves because a sibling experiment lands | the gate is the **authored blob hashes** in `CAPTURE_CONTRACT.json`, not live `HEAD` (SUBAGENT_BRIEF) |
| `mov_imm` seed pitfalls | seeds are all 0..127 (≥128 does not write and consumes the next instruction, EXP-0140) and avoid `imm7 == 12` (does not tokenize) |
| `falu2i` `mods` | `0xC0` is required only for a LOAD-sourced operand and *breaks* a `mov_imm`-sourced one (EXP-0101 / EXP-0141 amendment 1); the seeder passes `mods=0` |
| `device_load` `idx_off` unit unknown | calibrated in the pilot against a ramp image in which every word is self-identifying, frozen into `work/calib.json` **before** the gated runs, and recorded in `00_env.json` |
| Sweeping `device_store.base_slot` 0..255 writes through unbound slots | expected to fault; faults are results; flagged in `PROGRESS.md` as a courtesy per FIELD-SWEEP-PROTOCOL §7 |
| Laundering old evidence into the new schema | **no old record is ever transcribed.** Every record in `raw/` comes from a dispatch this experiment issued. `analysis/recitation.py` is kept strictly separate and its output is labelled an *auditability* finding about citation lists, never a hardware claim. |

---

## 10. Raw record schema (frozen)

One JSON object per dispatched case, appended to `raw/<run_id>/sweep.jsonl` and
**flushed + fsynced immediately**:

```json
{"idx":0,"seq":1,"t":0.0,
 "arm":"FALU2","carrier":"C2_load","instr":"falu2","field":"mod_hi","value":12,
 "bytes":"09051c0100c0","mode":"lift","kind":"load","cross":"opsel=4",
 "observed":{"regs":[...16...],"pre":90,"post":111,"stray":[],"n_stray":0},
 "oracle":{"digest":"...","sem":{"dst":1,"srcA":2.126,"srcB":-0.0625,
                                 "want_bits":1073217,"claim":"..."}},
 "match":false,"sem_match":null,"outcome":"wrong_value",
 "rt_ok":true,"tok_instr":"falu2","victim":false,"sentinel_bad":false,
 "attempts":[{"status":"OK","outcome":"wrong_value","error":null,"victim":false}],
 "predict":"","byte_index":null,"fstart":44,"fwidth":4,"foreign":false,"note":""}
```

`outcome` ∈ `ok | silent_zero | wrong_value | fault | hang | undecodable`.
`instr` is always a **db.json mnemonic** and `field` a **db.json field name** — that is
precisely what EXP-0140's raw got wrong (`instr: "regmove"`) and why its records could not
be attributed.

Also per run: `00_env.json` (target, OS, db/isadb sha256, **matrix sha256**, calibration,
input files), `00_arm_resolution.json`, `01_progress.json`, `02_summary.json`,
`03_procsample.jsonl` (concurrent GPU activity), `baseline.jsonl`.

---

## 11. Runs

| run id | role |
|---|---|
| `pilot01` | S1–S5: carriers, baseline, `idx_off` calibration, **liveness ladder**, store shape. A `pilot` id, which EXP-0164's `NONGATED` filter excludes from any promotion by construction. |
| `g17p_20260830_run01` | gated run A, forward arm order |
| `g17p_20260830_run02` | gated run B, **reverse** arm order (so the two are not hitting the same illegal encodings at the same moment) |

Estimated ~38,700 cases per gated run; at EXP-0154's measured G17P throughput (44.9
cases/s) that is ~15 min per run. **A partial run is retained exactly as it stopped, never
topped up, never reused, and its successor takes a new run id.**

---

## 12. Acceptance test for this experiment

`python3 analysis/reindex_check.py` — runs `analysis/collect_raw.py`, which is asserted
**byte-identical** to `EXP-0164-inert-audit/analysis/collect_raw.py`
(sha256 `aa15cd24d69d6ab5f06a34f0dda6467c3325105402b1ed112b2a10e0b0c06cde`), over the whole
`experiments/*/raw/**` tree, and reports for every field ruled on whether EXP-0164's own
indexer attributes records to it **bit-exactly**, on how many carriers and gated runs.
A field ruled on with no bit-exact attribution is a **failure**, printed as one.

---

## 13. Clean-room attestation

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/probes.metal, kernels/carrier_dag.metal and
  kernels/carrier_uni.metal (authored by us in this project; carrier_uni's body is a
  verbatim copy of our own EXP-0138 carrier), and the AGX machine code the PUBLIC
  runtime API compiled from that source. tools/{shdump,agxtest,agx-isa} used
  READ-ONLY and unmodified. analysis/collect_raw.py is a byte-identical copy of
  EXP-0164's.
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled,
  symbol-dumped, strings-scanned or debugged. The only machine code inspected or
  spliced is the compiled form of our own MSL.
Reproduction: see README.md
Evidence: raw/pilot01, raw/g17p_20260830_run01, raw/g17p_20260830_run02
```

---

## 14. Amendments (this section is append-only; the text above is NOT edited)

Four amendments were made **after** this document was frozen and **before** any device
dispatch. Each is recorded in full — what changed, why, what it touches, and what it does
NOT touch — in `CAPTURE_CONTRACT.json` → `amendments`. Summary:

1. **`amendment_01` — the gated runs execute UNLOCKED and concurrently.** §5 above asked
   for an orchestrator-coordinated quiet window for both. Superseded by orchestrator ruling
   2026-08-30: FIELD-SWEEP-PROTOCOL §7's standing directive is that ordinary sweeps run
   unlocked and only *confirmation* passes need a quiet machine. **Consequence, stated
   plainly:** offline adjudication becomes the primary defence rather than the quiet
   machine — the poison, both sentinels and the 16-GPR dump decide whether a dispatch
   really ran (EXP-0160's filter: two agreeing clean dumps win outright, because
   contamination can destroy an observation but never fabricate a coherent one) — and
   `harness/procsample.py` records what was *actually* running for the duration.
2. **`amendment_02` — `get_sr.dst_hi` is in scope; `get_sr.form` is EXP-0172's.**
   `FOREIGN_FIELDS` becomes per-descriptor. Device field count unchanged at 57.
3. **`amendment_03` — two gated pairs, not one.** The DSTORE arm runs LAST, in its own
   pair, after pair 1's raw is pulled back and after telling the orchestrator, because it
   stores through unbound binding slots. `analysis/verdicts.py` accepts N runs and pairs
   **per field** by most-distinct-values — EXP-0164 `cross_run`'s own rule — so the DSTORE
   pair is not diluted.
4. **`amendment_04` — the §1a offline finding is reported with a COVERAGE column,** after
   self-falsification: EXP-0164's gate has no coverage term (`THIN_COMMON=8` sets an
   informational flag and `stable_live` never consults it), so `RECOVERABLE-BY-CITATION`
   means "clears EXP-0164's gate", not "meets the `hardware-run` range bar". **Only 4 of
   the 12 clear it over the full encodable range**; the other 8 clear it on as little as 2
   of 64 values. Their *attribution* defect is fixed by a citation change; their *range*
   question stays open.

None of the four touches program construction, splicing, poisoning, majority-of-3, victim
classification, the sentinels, the oracles, outcome classification, the coverage rule, or
the promotion gate.
