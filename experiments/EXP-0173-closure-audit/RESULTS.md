# EXP-0173 — RESULTS: the acceptance-gate audit

**Verdict: the completion gate is NOT PASSED, and it is further from passing than the field
count suggests.** 0 of 16 P0/P1 rows are CLOSED. The strongest positive in the corpus
(EXP-0167) and the headline metric (35 of 166 emittable) turn out to describe **almost
disjoint sets of instructions**: their intersection, after removing the two that appear only
as copied tokens, is **two instructions — `mov_imm` and `stop`.**

Frozen at `2792d7ca`. Pure analysis, no device. Every number below has a command.

---

## 0. Observation vs interpretation

Everything in §1–§7 marked **OBSERVED** was produced by a command in `analysis/` at the frozen
revision and is reproducible with `sh analysis/run_all.sh`. Everything marked
**INTERPRETATION** is my reading of those observations. This audit cannot run hardware, so it
can never *re-observe* a HW-VALIDATED claim — only check that the record exists, is internally
consistent, and supports what is written on top of it. That limit is real and is stated again
in §8.

---

## 1. Rule-by-rule verdict against the six closure rules

`python3 experiments/EXP-0173-closure-audit/analysis/closure_rules.py` → `analysis/closure_rules.json`

Rules 2, 3 and 5 are mechanically checkable and were computed. Rules 1, 4 and 6 are
substantive; they are answered from §2–§3 rather than asserted.

| Rule | Verdict | Established by |
|---|---|---|
| **1. value/behaviour GENERATED, not merely decoded** | **NOT MET for 31 of the 35 emittable instructions.** Met for `mov_imm` and `stop`; met-but-outside-the-metric for `device_store`, `falu2` (+ `device_load`, `falu2i`, `iadd2` partly). | `analysis/template_dependency.py` — §2 |
| **2. complete authored probe, commands, raw, failures, analysis committed** | **MET for 10 of 16 rows.** Gaps: P0.3 (`EXP-0044` has no `manifest.json`, no derived analysis), P0.6 (`EXP-0170` has an **empty `raw/`**), P0.8 (cites no experiment at all), P1.3 (`EXP-0063`/`EXP-0066` have no `manifest.json`), P1.4 (`EXP-0093` no derived analysis), P1.8 (`EXP-0047` no derived analysis). | `analysis/closure_rules.py` |
| **3. evidence chain recorded in `PROVENANCE.md`** | **MET for 13 of 16 rows** in the forward direction — but see §4: the **reverse** chain is broken, with 11 CODEX §9 violations. | `analysis/closure_rules.py`, `analysis/provenance_audit.py` |
| **4. normative docs carry exact fields, ranges, fallbacks, target status** | **NOT MECHANICALLY CHECKABLE**, but one concrete failure found: `cvt_bf16.src` being fully match-pinned is **absent from `docs/isa/README.md`** and lives only in a status-board cell. | `grep -n cvt_bf16 docs/isa/README.md` |
| **5. adversarial reproduction or second method passes** | **MET for 6 of 16 rows.** No adversarial/second-method text in the RESULTS of `EXP-0041` (P0.1), `EXP-0043`/`EXP-0049` (P0.5), `EXP-0070` (P1.2), `EXP-0066` (P1.3), `EXP-0051` (P1.4), `EXP-0053` (P1.7). | `analysis/closure_rules.py` |
| **6. userspace object independently generated and consumed without a captured Apple template** | **MET for the ISA object only, and only over 6 families.** EXP-0167 is real and strong, but it covers `const`/`device_load`/`falu2`/`falu2i`/`device_store` + `iadd2` register mode. No other row has an independently generated object at all. | §2 |

**Completion gate: NOT PASSED.** H1 as pre-registered.

---

## 2. The captured-template question — per instruction, not per percentage

`python3 experiments/EXP-0173-closure-audit/analysis/template_dependency.py` → `analysis/template_dependency.json`

**OBSERVED. Three populations, and they are nearly disjoint.**

| population | size | source |
|---|---:|---|
| **E — EMITTABLE** (every field labelled `hardware-run`/`isolated-byte-diff`) | **35** | `validation.json` `coverage.emittable_mnemonics` |
| **G — GENERATED** (a zero-copied program using it actually ran on G17P) | **18** | EXP-0167 `analysis/assemble_defect_check.json` `mnemonics_used` |
| **E ∩ G** | **4** | `isel10`, `mov_imm`, `pop_reconverge`, `stop` |

And two of that four — `isel10` and `pop_reconverge` — appear in the corpus **only inside
`cf.py`, whose every field is emitted through `_copied()`** with the citation
`"EXP-0090 P3 skeleton (verbatim)"`. The auditable test is one grep: the mnemonic string
occurs in `cf.py` and in none of `synth.py` / `families.py` / `generator.py` / `casematrix.py`.

> **So the set of instructions that are both labelled emittable AND have ever been built from
> rules and executed is: `mov_imm` and `stop`.**

### 2.1 Where the donor dependency bites — named

**DONOR-DEPENDENT (11 mnemonics).** Every one is built only from copied tokens:
`get_sr`, `icmp_pred`, `if_push`, `if_push_pred`, `isel10`, `jump`, `jump_cond`,
`pop_reconverge`, `reg_move_c0`, `ret`, `scoreboard_fence`.
EXP-0167's own `summary.json` names **81 `(mnemonic, field)` donor pairs**, including all 8
fields of `icmp_pred`, all 10 of `isel10`, all 3 of `jump_cond`, all 3 of `pop_reconverge`.
**Two of these — `isel10` and `pop_reconverge` — are inside the emittable 35.** An implementer
reading the metric would believe they can emit an `isel10`; the only `isel10` this project has
ever run was copied byte-for-byte out of a compiled shader.

**PARTLY-DONOR (3).** `device_load`, `falu2i`, `iadd2` — rule-generated elsewhere, but their
fields are still copied inside the 12 CF programs.

**GENERATED-NOT-EMITTABLE (2).** `device_store`, `falu2` — a zero-copied program using them
ran correctly, yet the metric excludes them because a field is unlabelled. **The metric
under-counts these.**

**EMITTABLE-NOT-GENERATED (31).** Every field labelled emitter-grade; no generated program
containing the instruction has ever executed. Closure rule 1 is not established for any of
them by EXP-0167.

### 2.2 A published figure is inverted, and I am correcting it

The reading I was given says *"60 of the 233 rest on rules the experiment did not itself
measure."* EXP-0167's own `analysis/summarize.py` defines `N0` as **"the subset of N that also
contains zero PILOT fields, i.e. rests only on rules published by earlier experiments"**, and
`N0 = 60`. The statement is the other way round:

> **Only 60 of the 233 rest on previously published rules. The other 173 contain at least one
> field whose value EXP-0167 had to measure in its own pre-freeze pilot, because no prior rule
> existed.**

From the immutable raw record (`raw/g17p-20260830-iso01/01_results.jsonl`, `prov.pilot`), that
field is **`falu2.mod_hi` in 163 of them**, and nine `iadd2` fields (`b2_bit0`, `b2_fmt`,
`opc_tail`, `opc_tail2`, `opmode`, `srcA`, `srcB_ext`, `srcB_reg_hi`, `store_en`) in the other
16. **INTERPRETATION:** this does not weaken EXP-0167 — a pilot-measured value is still
hardware-derived, not donor-derived, which is the property the gate cares about. It changes
*who can reproduce it*: an implementer working only from `docs/` has the published rules
(the 60), not EXP-0167's pilot. `falu2.mod_hi` has since been promoted to `hardware-run` on
G17P (0..15 dense), so the fix is a documentation one, not an experiment.

---

## 3. What each tool gate actually proves

`python3 experiments/EXP-0173-closure-audit/analysis/gate_sensitivity.py` → `analysis/gate_sensitivity.json`

Each gate was run unmodified, then given a defect it is claimed to protect against. **A gate
that still passes does not gate that class.**

| gate | baseline | injected defect | result |
|---|---|---|---|
| `roundtrip_test.py` | ALL PASS | **M1** `assemble()` reverted to bare-OR (DEF-0166-1) — cannot clear a bit | **STILL ALL PASS — INSENSITIVE.** Independently reproduces EXP-0170 by construction. |
| | | **M2** `assemble()` silently forces `dst`/`srcA`/`src` to 0 | FAILS — so it *does* catch gross operand loss |
| | | **M3** `falu3.srcA` ↔ `srcB` swapped in a `db.json` copy | **STILL ALL PASS — INSENSITIVE. NEW.** An operand SWAP — the exact `fspecial` defect class — is invisible to a symmetric round trip, because the same descriptor drives both directions and cancels. |
| `validate_labels.py` | exit 0 | **V1c** a field promoted `untested`→`hardware-run` with a fabricated range and the evidence path `EXP-9999/raw/does_not_exist/run.json`, all coverage arithmetic recomputed | **exit 0 — INSENSITIVE. NEW.** **The validator never opens an evidence path.** It is a schema and arithmetic checker, not an evidence checker. V1/V1b fail only on coverage arithmetic, which is easy to satisfy. |
| `match_overlap_report.py` | 59 / 25 / 16 | — | reproduced exactly. Its committed `match_overlap.json` is **3 rows stale** vs the current `validation.json` (2 label drifts, 1 `instruction_emittable` true→false). |
| `emit_worklist.py` | 35 / 131 / 166 | — | reproduced. `dst` blocks 46, `srcA` 16, `tail` 13; 32 instructions are one field away. |
| `work/merge_verdicts.py --dry-run` over `experiments/EXP-01*/analysis/field_verdicts.json` | exit 1 | — | The downgrade refusal works. But it reports **588→692 emitter-grade and 35→66 emittable**: the documented merge command, run over the 22 committed verdict files, **reconstructs the discredited headline**, because the superseded verdict files were never retracted in place. |

**INTERPRETATION.** Of the five gates, exactly one — `merge_verdicts.py`'s downgrade refusal —
is sensitive to the class of error that has actually cost this project fields. The round trip
is a tokenizer regression test. The label validator is a spreadsheet checker. Neither can see
a wrong operand or a fabricated citation.

---

## 4. `PROVENANCE.md` — and the direction nobody was checking

`python3 experiments/EXP-0173-closure-audit/analysis/provenance_audit.py` → `analysis/provenance_audit.json`

**171 rows audited. The worst thing I was told to look for is not there.**

- **`artifacts_exist`: 168 of 171 true. ZERO rows cite an artifact that is absent.** Every
  experiment directory, raw path, glob and git commit resolves on disk. (Reaching that
  required four extractor fixes — `EXP-G1a`-style ids, bare `RT-*`/`REVIEW-*` directory names,
  `work/`+`raw/`+`analysis/` being ambiguous between repo root and experiment dir, and
  `file.c:171-172` line suffixes. All four are in the committed script.)
- **3 rows cite nothing resolvable at all** — no experiment id, no path, no commit:
  **L17** (target identity), **L18** (runtime MSL under CLT only), **L104** (`agx3.xml` W3
  render). L17/L18 are separately corroborated by later EXP-0002 rows; L104's claim is
  re-derivable from `tools/agx-isa/gen_agx3_xml.py` + `docs/isa/agx3.xml`, both present — the
  row simply points at neither.
- **1 row cites the wrong artifact for its own literal.** **L28** claims `0e000000` and
  `1ca01006` and cites `raw/*info.txt` + `raw/determinism.txt`; those bytes live in
  `raw/k05_fma.text.hex` and siblings. Citation precision, not fabrication.

### 4.1 The chain is complete in one direction only — 11 CODEX §9 violations

CODEX §9: *"No hardware fact enters `docs/` unless the same change provides an auditable
evidence link… add or update its row in `PROVENANCE.md`."*

**OBSERVED: 36 of 169 committed `EXP-NNNN` experiments have no `PROVENANCE.md` row, and 11 of
those are cited in `docs/`:**

`EXP-0068`, `EXP-0078`, `EXP-0080`, `EXP-0104`, **`EXP-0105`**, `EXP-0106`, `EXP-0111`,
`EXP-0114`, `EXP-0115`, `EXP-0142`, **`EXP-0170`**.

Two matter most:
- **`EXP-0105`** is cited in `docs/isa/encoding-tables.md` for *"`opflags` bits 22/23 and
  `mod_hi` bit 44 are general silent CORRUPTORS"* — an **emitter-safety** fact an implementer
  will act on — with no provenance row.
- **`EXP-0170`** has **no provenance row and an empty `raw/`**, while its conclusions are
  quoted verbatim in the `docs/P0-P1-CLOSURE.md` P0.6 cell (the two corrected figures, the two
  restored fields, the four tooling defects). It is a pure-analysis experiment, so an empty
  `raw/` is defensible; the missing row is not.

### 4.2 The real weakness of the provenance chain

**`claim_reproduced` is `not-mechanically-checkable` for 162 of 171 rows.** The chain proves an
artifact **exists**; nothing proves the artifact **says what the row says**. Only 5 rows
offered a (text artifact × distinctive literal) pair I could grep, and all 5 passed at
analysis level. **INTERPRETATION:** this is exactly the failure mode that cost 125+ fields in
the last day, and no tool in the repository closes it — §3 shows `validate_labels.py`
explicitly does not.

---

## 5. The vacuous-field question — both ways, and a recommendation

`python3 experiments/EXP-0173-closure-audit/analysis/vacuous_fields.py` → `analysis/vacuous_fields.json`

| accounting | emitter-grade / total fields | emittable instructions |
|---|---|---|
| **as published** | **588 / 1062** (55.37%) | **35 of 166** |
| **fold the 25 zero-free-bit fields into `match`** | **572 / 1037** (55.16%) | **35 of 166 — UNCHANGED** |
| also fold the 34 partially-pinned fields *(not recommended)* | 555 / 1003 | 37 of 166 |

7 of the 25 sit inside currently-emittable instructions: `link_save_restore.b1/.marker/.scope`,
`cvt_bf16.src/.fmt`, `rtq_state_move.form/.b3`.

**RECOMMENDATION: fold the 25.** It costs nothing — the instruction headline does not move,
because removing a field can only remove a blocker and none of these 25 was blocking — and it
removes 16 emitter-grade labels that assert a choice the implementer does not have. The
fraction barely moves (55.37% → 55.16%), which is the point: this is an honesty fix, not a
metric fix. **Do NOT fold the 34 partially-pinned fields** — those have a real choice, just a
narrower one; the correct repair there is to fix `start`/`width`, not to delete the field.

---

## 6. Fields that cannot do what their name promises

`python3 experiments/EXP-0173-closure-audit/analysis/operand_sanity.py` → `analysis/operand_sanity.json`

**Two NEW members of the class, found on purpose:**

| field | test | label | emittable? | in `docs/isa/README.md`? |
|---|---|---|---|---|
| **`cvt_f2h_dst.src`** | **P1c PARTIALLY PINNED** — declares 8 bits, only **4** are choosable (16 legal values, not 256) | `hardware-run` | **YES** | no |
| `falu2_uni.usrc` | P1c — 7 of 8 bits choosable | `hardware-run` | no | no |
| `cvt_bf16.src` | P1 ZERO FREE BITS (the known member) | `hardware-run` | **YES** | **no — see below** |

**INTERPRETATION:** a `hardware-run` label on `cvt_f2h_dst.src` with a range describing 256
values would over-state its coverage 16×; the field can only take 16.

**Clean negatives, worth having:** **0** descriptors have two fields whose spans overlap each
other, and **0** have a field span running past `length * 8`. Those two whole failure modes are
absent from `db.json`.

**Advisory (not a defect): 10 of the 35 emittable instructions cap their destination at
r0..r15** — a 4-free-bit `dst` with no extension-named sibling in the descriptor
(`bf_add_dst`, `cvt_bf16`, `cvt_f2h_dst`, `falu3`, `h_coord_hi`, `hminmax`, `iminmax`,
`mov_imm`, `n2_op6`, `rtq_state_move`). A 4-bit dst nibble is a real AGX compact form, so this
may be correct — but "emittable" currently means "emittable into the first 16 registers" for
those ten, and nothing in the metric says so.

### 6.1 Are the four named defects recorded where an implementer looks?

`docs/isa/README.md` L341–L380 carries a genuinely good emitter-safety block. It records
**three of four**: the `fspecial` operand swap (with both mask rules and the "silently writes
the wrong register" consequence), `fspecial` dst ≥ 96 faults/hangs, `imad` with no `srcA`
modelled, and the `op04_len8` EMITTABLE VETO. It **additionally** warns that `falu3`/
`falu3_ext` field NAMES are misleading — `dst` is the first source and `srcB` is a control
byte — which is a fifth member of the same class and affects two instructions inside the
emittable 35.

**`cvt_bf16.src` being fully match-pinned is NOT in `docs/isa/README.md`.** It appears only in
the `docs/P0-P1-CLOSURE.md` P0.6 status cell, which is a board, not the normative spec.
An implementer reading the deliverable will not learn it.

---

## 7. What an implementer can actually emit today

`python3 experiments/EXP-0173-closure-audit/analysis/compiler_readiness.py` → `analysis/compiler_readiness.json`

### 7.1 The `nir_op_mov` first-blocker claim STILL HOLDS

No descriptor that moves one GPR to a **different** GPR is emittable.
- `mov_zext16` is emittable, but its own committed semantics say it operates **in place on one
  register used as both source and destination** — it cannot express a copy.
- `n3_mov` is the real candidate: `dst`, `srcA_reg`, `srcA_uni` are all `corpus-correlation`.
- `reg_move_c0` ran in a generated program — but every field is `untested`, and it is the
  const-zero form (`src_reg` is 0 in all 1545 corpus instances).
- `uniform_mov` reads the uniform file, not a GPR, and `dst` is `untested`.
- `n2_op6` is emittable and its semantics mention "compact select/move" — but the descriptor's
  own text says it is a **"genuine catch-all bucket"** whose **"per-sub-op value maps are mixed
  and needs-splice"**, and its provenance says **"NOT HW-dispatch validated (M4 compile-only)"**.
  There is no rule for which `opsel`/`opA` value performs a move of which register.

**So `docs/compiler-readiness.md`'s headline survives today's withdrawals unchanged.**

### 7.2 A NEW metric defect: the emittability rule never reads `_instruction`

**OBSERVED.** `validate_labels.py` and `merge_verdicts.py` decide "emittable" from the **field**
labels plus the `EMITTABLE VETO` note. Neither consults the `_instruction` label, which is
where the instruction's own identity/semantics evidence lives.

> **21 of the 35 emittable instructions carry an `_instruction` label WEAKER than
> emitter-grade** — 20 `corpus-correlation`, and **`sfu_marker` is `tokenization-only`**, the
> weakest useful rung on the CODEX ladder.
>
> `bf_add_dst`, `cvt_bf16`, `cvt_f2h_dst`, `cvt_i2f`, `falu3`, `falu3_ext`, `frag_depth_store`,
> `h_coord_hi`, `h_coord_hi_ext`, `hminmax`, `iter_flat`, `mov_imm`, `mov_zext16`, `n2_op6`,
> `psel`, `ret_luse`, `rtq_state_move`, `sel`, `sfu_marker`, `sr_read_wide`, `vtx_coord_xform`.

Separately, **18 of the 35 carry descriptor text that warns about themselves** —
`needs-splice`, `NOT HW-dispatch validated`, `compile-only`, `catch-all`, `unresolved` —
including `falu3`, `falu3_ext`, `isel10`, `iunary`, `n2_op6`, `psel`, `sr_read_wide`,
`tex_addr_setup`, `spill_frame_marker`.

**INTERPRETATION:** this is a fifth tooling defect of the same family as the four already
found. It inflates the instruction headline in a way that no field-level audit can catch,
because every field really was swept. The fix is one line in the emittable rule: require the
`_instruction` label to be emitter-grade too. **I did not apply it** — `validation.json` and
`db.json` are the orchestrator's.

---

## 8. Limitations

1. **No hardware.** This audit cannot re-observe any HW-VALIDATED claim. `claim_reproduced:
   true` means the cited artifact contains the claimed literal — analysis-level corroboration,
   explicitly weaker than a G17P re-run.
2. **162 of 171 provenance rows are `not-mechanically-checkable`.** The audit therefore does
   **not** establish that PROVENANCE.md is truthful; it establishes that its citations resolve.
3. **Membership in the "generated" corpus is per mnemonic**, not per field. EXP-0167 used 2,396
   distinct `(mnemonic, field-values)` pairs across 18 mnemonics — not the full operand space
   of any of them. `mov_imm` and `stop` being "generated" does not mean their whole encodable
   range was generated.
4. **The donor classification rests on a grep** of the mnemonic string across EXP-0167's
   generator modules. It is directly auditable but it is a textual test, not an execution
   trace.
5. **Three device experiments were writing during this run.** `validation.json` was hashed at
   freeze and is recorded in `CAPTURE_CONTRACT.json`; if it moved, the counts move with it.
   The committed `tools/agx-isa/match_overlap.json` was already 3 rows stale when I started,
   which is direct evidence that it does.
6. **`gate_sensitivity.py` needed three harness fixes** before its results were valid (an
   `isadb` name error in the exec shim made M1/M2 look sensitive when the suite had merely
   crashed; the coverage-block recompute used the wrong key). The first, wrong run is recorded
   in `raw/mutation_runs.txt` and was not deleted.

---

## 9. What I would tell the implementation team today

You cannot write a back end from this yet. Here is the honest state.

**Two instructions are proven end-to-end: `mov_imm` and `stop`.** Those are the only ones
where every field is measured *and* somebody built the instruction from rules and ran it on
the real GPU against an independent oracle. Everything else is one of: measured fields with no
generated program (31 instructions), a generated program whose fields aren't all measured
(5 instructions), or a copied template (11 instructions).

**You cannot write a register move.** There is no validated GPR-to-GPR copy. That blocks
`nir_op_mov`, phi lowering, parallel copy, register-allocator coalescing, and spill reload —
which is to say it blocks the register allocator, which is to say it blocks the back end. This
was the reported first blocker before today's withdrawals and it is still the first blocker
after them. Nothing else on the list matters until it is fixed.

**You cannot write control flow without copying Apple's bytes.** Every field of `icmp_pred`,
`jump_cond`, `if_push`, `if_push_pred`, `jump`, `pop_reconverge`, `isel10`, `ret`,
`scoreboard_fence` and `reg_move_c0` is still lifted verbatim from a compiled shader. The
project has executed control flow exactly once, and that program was a donor. Do not be
reassured that `isel10` and `pop_reconverge` appear in the "emittable" list — that list is
about field labels, not about whether anyone has ever built one.

**Do not trust the round trip, and do not trust the label validator.** I broke the assembler so
it could not clear a bit: the round trip passed. I swapped two operand field names in the
database: the round trip passed. I promoted an untested field to `hardware-run` citing a raw
file that does not exist: the label validator exited 0. If you are relying on a green gate in
this repository to tell you an encoding is safe, you are relying on nothing.

**Read the emitter-safety block in `docs/isa/README.md` before you emit anything.** It is the
best thing in the deliverable — it will stop you putting a destination in a byte that does
nothing (`fspecial`), emitting an integer multiply you cannot give a first operand (`imad`),
desynchronising the whole instruction stream (`op04_len8`), and reading `falu3`'s field names
literally. It is missing one item: `cvt_bf16.src` is fully pinned by the opcode and cannot be
the source it names.

**Where a `dst` is four bits, assume r0..r15 until told otherwise.** Ten of the thirty-five
"emittable" instructions cannot address a register above 15 as modelled, and the metric does
not say so.

**Treat "35 of 166" as an upper bound with a wide error bar, not a coverage figure.** Twenty-one
of those thirty-five have an instruction-level evidence label weaker than emitter-grade — one
of them is merely tokenized — and eighteen carry descriptor text that warns about themselves.
The number counts swept bytes. It does not count instructions anybody has successfully built.

**What is genuinely solid and worth building on:** EXP-0167. A generator produced **265**
programs containing zero copied tokens over `const` / `device_load` / `falu2` / `falu2i` /
`device_store` plus `iadd2` register mode; **237** of those were pre-registered to match, and
**233 of the 237** hit their exact host-computed oracle on the A18 Pro — reproducibly, in two
byte-identical runs, with a 204,044-call ledger showing every emitted field equals the value
the generator asked for. That is a real synthesis result and it is the template for how the
rest of the ISA should be closed. It is also six instruction families out of the hundred and
sixty-six emitter-relevant descriptors.

---

## 10. Recommended next actions (for the orchestrator, who owns the files)

1. **Fix the emittability rule** to require an emitter-grade `_instruction` label. Expect the
   headline to fall from 35 toward 14. That is the correct number, not a worse one.
2. **Fold the 25 zero-free-bit fields into `match`** (588/1062 → 572/1037; instruction count
   unchanged).
3. **Add `cvt_bf16.src` and `cvt_f2h_dst.src` to the emitter-safety block** in
   `docs/isa/README.md`.
4. **Write the 11 missing `PROVENANCE.md` rows**, starting with `EXP-0105` (an emitter-safety
   fact in `docs/isa/encoding-tables.md`) and `EXP-0170`.
5. **Retract the superseded `field_verdicts.json` files in place**, or the documented
   `merge_verdicts.py` command will keep reconstructing 692/66.
6. **Point the next device experiment at `n3_mov`.** `dst`, `srcA_reg`, `srcA_uni` — three
   `corpus-correlation` fields standing between this project and a register allocator.
