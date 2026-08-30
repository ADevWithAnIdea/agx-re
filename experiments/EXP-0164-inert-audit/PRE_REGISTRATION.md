# PRE-REGISTRATION — EXP-0164: adversarial audit of every emitter-grade field

**Frozen 2026-08-30, before any verdict was computed.** Thresholds in §5 are fixed
here so they cannot be tuned to a pleasing answer. Controls in §8 are pre-declared
falsifiers of the audit method itself.

```
Clean-room provenance: (analysis of already-committed evidence)
Inputs inspected: tools/agx-isa/validation.json, tools/agx-isa/db.json,
                  experiments/*/raw/** (our own append-only capture records),
                  experiments/*/RESULTS.md, experiments/*/analysis/*
Apple binary introspection: NONE. No device is contacted. No shader is compiled.
Reproduction: python3 analysis/collect_raw.py && python3 analysis/audit.py
Evidence: work/validation.snapshot.json, work/db.snapshot.json (hashes in PROGRESS.md)
```

---

## 1. Question

`tools/agx-isa/validation.json` promotes 664 ISA fields to the two emitter-grade
labels (`hardware-run`, `isolated-byte-diff`). The orchestrator's audit of EXP-0155
showed that **"the field is inert" was repeatedly an artefact of the single carrier
the analysis happened to report**, not a property of the silicon: `tex_sample.samp_extra`
reads inert on nine arms and moves 128/256 values on the tenth; `frag_color_store.flags`
reads inert on `fcs@iter0` and moves 128/256 on `fcs@pack0`.

**How much of the 664 rests on the same defect, or on evidence that cannot be
re-derived from raw at all?**

## 2. Hypotheses and falsifiers

- **H1 (the suspect class exists at scale).** A material fraction of the 664 was
  promoted from a sweep in which the field never moved any observable and only ONE
  carrier was ever tried.
  *Refuter:* fewer than 5% of the 664 land in `INERT-SINGLE`.
- **H2 (the representative-arm defect is not unique to EXP-0155).** There exist
  merged fields where a fully inert arm coexists in the same raw with a
  stable-live arm.
  *Refuter:* zero fields outside EXP-0155 show mixed arm liveness.
- **H3 (chain integrity).** Every emitter-grade field can be re-derived from
  append-only raw.
  *Refuter, and the finding I most expect to have to report:* some promoted fields
  have no per-value raw record at all, in which case H3 is false and the count is
  named loudly rather than skipped.

H1/H2/H3 are independent; each is reported on its own evidence.

## 3. Raw-schema facts established BEFORE freezing (reconnaissance only)

Recorded so the parser cannot be accused of being fitted after the fact.

- Per-field, per-value machine-readable sweep records exist **only** for
  `EXP-0138, 0139, 0140, 0141, 0142, 0143, 0144, 0146, 0147, 0153, 0154, 0155,
  0156, 0157, 0159, 0160, 0161, 0162` — JSON-Lines under `raw/<run>/…`, one object
  per case, carrying at minimum `instr`, `field`, `value`, `observed`, `outcome`,
  and an arm identifier (`carrier`, or `arm` where `carrier` is absent — EXP-0159
  and part of EXP-0162).
- **No experiment numbered below EXP-0138 emits a `field` key in its raw records.**
  EXP-0090/0092/0099/0101/0105/0112/0113/0119 record `01_results.jsonl` keyed by
  *case name* (`name`, `group`, `notes`), not by field. EXP-M4-14's raw is a single
  narrative `splice_results.json` (prose `evidence` strings, no per-case records).
  EXP-0006/0016/0029/O2C/O2D/RT-* raw is `.log`/`.txt`/`.hex` text.
- `outcome` vocabulary observed across all field-record raw: `ok`, `wrong_value`,
  `silent_zero`, `fault`, `hang`, `invalid_run`, `skipped`, `undecodable`,
  `not_written`, `no_draw`, `lost_7_of_8`, `killed`, `victim`, `unstable`,
  `inert_or_unreached`, `nondeterministic`, `live`, `foreign`, `exploratory`,
  `cascade_suspected`.
- `observed` is a dict, a string, or null. `value` is an int, a string, or a list.
- Run identity = the directory name immediately under `raw/`.

## 4. Definitions (frozen)

**Universe.** The field records of `work/validation.snapshot.json` whose `label`
is `hardware-run` or `isolated-byte-diff`, excluding the `_instruction`
pseudo-entries. Key form `<mnemonic>.<field>`.

**Raw corpus.** Files under `experiments/<EXP>/raw/**` ONLY. `work/`, `analysis/`
and `harness/` trees are not raw and are excluded, so a smoke run promoted out of
`work/` cannot be mistaken for gated evidence.

**Citing experiments of a field.** The `evidence` list of its validation entry,
mapped to directories by prefix (`EXP-0154` → `EXP-0154-g17p-emit-alu`,
`EXP-M4-14` → `EXP-M4-14-a18-splice`, `RT-*` → the identically named directory).

**Arm.** `carrier` when present and non-empty, else `arm`, else `"-"`. Two
occurrences of the same instruction in one carrier program are DIFFERENT arms —
this is deliberate and it is exactly what EXP-0155's `tex_sample@lo_0` vs `@lo_1`
proved (same program, different texture op, opposite liveness).

**Run.** The path component immediately below `raw/`.

**Gated run.** Any run EXCEPT one whose directory name matches (case-insensitive)
`prefreeze|smoke|pilot|quarantine|burned`, or whose directory contains `PARTIAL.md`.
If that rule leaves no run for a field, all runs are used and the record is flagged
`gating_fallback: true`.

**Contaminated case (excluded from every count).** `outcome` ∈ {`invalid_run`,
`victim`, `skipped`}, or the record carries a `skip_reason`. These are other
contexts' errors or cases that never ran; counting them as movement would inflate
liveness. Their number is reported per field as `n_contaminated`.

**Dispatched case.** A non-contaminated selected record. Distinct dispatched values
= the number of distinct `value` payloads (canonicalised as JSON text) actually
present. "Planned" coverage in a case matrix is never counted.

**Effect signature** (the observable, deliberately oracle-INDEPENDENT):

```
signature = ( hard_class , sha1(json(observed, sort_keys=True)) )
hard_class = outcome  if outcome ∈ {fault, hang, undecodable, killed, not_written,
                                    no_draw, lost_7_of_8, nondeterministic}
             else "run"
```

`ok` / `wrong_value` / `silent_zero` all collapse to `"run"` and are separated only
by what was actually read back, so a field whose oracle is a host-computed
per-value prediction (match=True on every case) is NOT miscounted as inert — the
failure mode of a purely `match`-based audit. Faults and hangs ARE movement: "GPR ≥ 96
faults" is the field doing something.

**Moved** on (field, arm, run) = the number of dispatched values whose effect
signature differs from that triple's modal effect signature.

**Cross-run comparison** for (field, arm): take the two gated runs with the most
distinct dispatched values; `common` = values present in both; `agree` = common
values with identical effect signature; `disagreements = common − agree`;
`agree_pct = 100·agree/common`.

## 5. Bucket thresholds (FROZEN — mirrors the merge policy in `work/UNATTENDED-RUN.md`)

`STABLE-LIVE(arm)` holds iff **all** of:
1. ≥ 2 gated runs cover the arm, and `common ≥ 2`;
2. `moved ≥ 1` in **both** of those runs;
3. `agree_pct ≥ 99.0`;
4. `min(moved_runA, moved_runB) ≥ 2 × disagreements`.

Advisory flag only, never a bucket determinant: `thin_cross_run` when `common < 8`.

**Decision tree, evaluated over the union of ALL citing experiments, first match wins:**

1. no dispatched case anywhere → **UNVERIFIABLE**
2. ∃ arm with `STABLE-LIVE` → **STABLE-LIVE**
3. total moved == 0 everywhere:
   - ≥ 2 distinct arms tried → **INERT-MULTI** (envelope = the arm list, recorded)
   - exactly 1 arm tried → **INERT-SINGLE**
4. movement exists but no arm is stable-live:
   - no arm has ≥ 2 gated runs → **SINGLE-RUN**
   - otherwise → **UNSTABLE**

**UNVERIFIABLE sub-reasons** (all three are UNVERIFIABLE; the split is reported):
- `no-raw` — no citing experiment has any file under `raw/`;
- `no-field-records` — raw exists, parses, and never names the field, structurally
  or textually;
- `field-named-but-unstructured` — the field name occurs in raw text (case names,
  notes, narrative splice evidence) but no per-value record exists, so distinct
  dispatched values, movement and cross-run agreement are all unmeasurable.

## 6. Representative-arm defect test (H2)

Flag `mixed_arm_liveness` on any field that has, **within one experiment's gated
raw**, at least one arm with `moved == 0` in every gated run AND at least one arm
satisfying `STABLE-LIVE`. Report the inert arm(s), the live arm, and the moved
counts. This is the EXP-0155 defect stated mechanically and without needing to know
which arm the experiment chose to report.

## 7. Recomputed emittability

Reimplement `tools/agx-isa/validate_labels.py`'s emittable rule against the pinned
snapshots: an instruction is emittable iff every field of its `db.json` descriptor
is emitter-grade, or (field-less descriptors) its `_instruction` entry is; and its
`_instruction.note` does not contain `EMITTABLE VETO`. Denominator = descriptors
whose `emitter_role` is not `data-word` (166).

Two withheld sets are reported, both computed the same way:
- **strict** — withhold `INERT-SINGLE ∪ UNSTABLE ∪ UNVERIFIABLE`;
- **lenient** — strict minus the `field-named-but-unstructured` UNVERIFIABLE rows
  (i.e. give hardware splice evidence that is real but unstructured the benefit of
  the doubt).

Fields whose emitter-grade `_instruction` entry is itself unverifiable are reported
but do not by themselves demote an instruction unless the descriptor is field-less.

## 8. Controls / falsifiers of the AUDIT (declared before running)

- **C1 (reproduction).** Restricted to EXP-0155's gated runs
  (`g17p_20260829_run03`, `run04`), the pipeline must reproduce the orchestrator's
  15 withheld fields in `EXP-0155-g17p-emit-tex-frag/analysis/withheld_by_orchestrator.json`.
  Any difference is REPORTED, not tuned away.
- **C2 (positive).** `iter.dst` must classify `STABLE-LIVE` (EXP-0155 §2.1: it moves
  on ~190 of 256 values and faults/hangs above GPR 96, twice).
- **C3 (fault-as-movement).** At least one field must reach `STABLE-LIVE` whose only
  movement is a `fault`/`hang` class change, proving the signature is not
  observed-only.
- **C4 (no silent skips).** `len(audit.json) == 664` exactly, and every one of the
  53 distinct evidence ids in the snapshot is accounted for in
  `analysis/experiment_coverage.json` with a parse verdict.

## 9. Known confounders

- Two occurrences of one instruction in one program count as two arms, so
  `INERT-MULTI` is a weaker guarantee than "two structurally different shaders".
  Recorded per field as the arm list; not silently upgraded.
- An `observed` payload containing a non-deterministic component would inflate
  disagreements and push fields to `UNSTABLE`. Mitigation: `n_baseline_signatures`
  (distinct effect signatures of the experiment's own `_baseline`/`_live_control`
  pseudo-fields on the same arm) is reported; > 1 means the harness itself is noisy
  on that arm and the UNSTABLE verdict is attributed to the harness, not the field.
- This audit measures **auditability from raw**, not truth. A field marked
  `UNVERIFIABLE` may well be correct; the claim is only that the committed chain
  `documented fact → RESULTS.md → analysis → immutable raw` cannot be walked for it.
- `validation.json` is under concurrent edit; everything here is against the pinned
  snapshot and will drift.

---

## Amendment A1 — 2026-08-30, before any verdict was computed

**Gap found in the frozen contract.** §4 defined a dispatched case but not what to do
when the SAME value is dispatched more than once inside one `(field, arm, run)`.
11.6% of all indexed cases (84 482 of 728 387) are such repeats — replicate/majority
passes — so the rule is load-bearing and leaving it implicit would be exactly the
"underspecified frozen contract" the subagent brief forbids.

**Rule adopted (implemented in `analysis/collect_raw.py`, no verdict computed before
this was written):** a value dispatched more than once inside one `(field, arm, run)`
contributes ONE entry whose effect signature is the **modal** signature over its
repeats. The number of values whose repeats disagreed is carried per triple as
`n_within_run_unstable` and reported in `analysis/audit.json`.

Rejected alternatives and why: "keep the first observation" silently discards the
replicate evidence the harnesses went to the trouble of collecting; "treat any repeat
disagreement as movement" would let a single victim-class flake manufacture liveness,
which is the failure mode this whole audit exists to catch.
