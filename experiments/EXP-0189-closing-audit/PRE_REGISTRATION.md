# PRE-REGISTRATION — EXP-0189: closing audit of the published 55/166 and 638/1040

**Frozen 2026-08-30 before any verdict was computed.** Repo revision at freeze:
`0de24f4fcaab715fd174ff7610d68f93cdaad57f` (working tree clean except this new,
still-empty experiment directory).

Pinned inputs (copied to `work/` at freeze, sha256 recorded here so a later edit to
`tools/agx-isa/*` cannot silently move the target):

| file | sha256 |
|---|---|
| `work/db.snapshot.json`         | `2412eac1cad4449eb385702062abd03e5c926d04f7d384e6bf3684c9c4c7c6c4` |
| `work/validation.snapshot.json` | `867e4b05dbcd000f98a8ac4705d07f419b1d0a69c4b276e030b0daf225eaf0b7` |

`validation.snapshot.json` self-reports `db_sha256 = 2412eac1…`, which matches the
pinned `db.snapshot.json` — the two snapshots are mutually consistent at freeze.

```
Clean-room provenance: PUBLIC/derived — analysis of already-committed evidence only.
Inputs inspected: tools/agx-isa/{db,validation}.json, experiments/*/raw/** (our own
                  append-only capture records), experiments/*/{RESULTS.md,analysis/*,
                  harness/*} authored by this project.
Apple binary introspection: NONE. No device is contacted. No shader is compiled.
                  THE A18 PRO IS DOWN; this experiment is pure offline analysis and
                  must not attempt any device work.
Reproduction: python3 analysis/collect_raw.py && python3 analysis/audit.py
Evidence: work/raw_index.json.gz, analysis/audit.json, analysis/reclassify.json
```

## 1. Question

`tools/agx-isa/validation.json` currently publishes **55 of 166 emitter-relevant
instructions emittable** and **638 of 1040 fields emitter-grade** (555 `hardware-run`
+ 83 `isolated-byte-diff`). EXP-0164 cut the same headline from 79/166 to 41/166 by
re-deriving every emitter-grade field from `raw/`. Everything merged since commit
`459bb8bd` was merged by the orchestrator under its own policy and **has not been
audited by anyone else**.

**Does 55 survive an independent re-derivation from raw, under EXP-0164's frozen
thresholds?**

## 2. Hypotheses and refuters

- **H1 (the merges hold).** Re-deriving every currently emitter-grade field from
  `experiments/*/raw/**` under EXP-0164's frozen bucket rules leaves the emittable
  count at 55.
  *Refuter:* the strict recomputation lands below 55; the shortfall is the number of
  instructions that must be withdrawn.
- **H2 (post-`459bb8bd` merges are no weaker than the pre-existing corpus).** The
  fraction of emitter-grade fields landing in a withheld bucket is no higher among
  fields whose citing experiments are post-`459bb8bd` than among the rest.
  *Refuter:* the post-`459bb8bd` cohort withholds at a materially higher rate.
- **H3 (the width-1 gate bug is not in the merged tooling).** No merged gate in
  `tools/` or in a post-`459bb8bd` experiment's analysis implements
  `moved >= K * max(disagree, 1)`, which cannot promote any width-1 field.
  *Refuter:* any such expression exists in merged code.
- **H4 (self-consistency of the published rows).** No emitter-grade row's `range`
  or `note` text asserts inertness/absence/"framing only"/"no observable effect"
  while its own attributed raw records movement.
  *Refuter, and the one I most expect to fire:* such rows exist; each is named.
- **H5 (the `_instruction` label refresh is sound).** Every `_instruction` entry
  EXP-0181 refreshed to an emitter-grade label has per-value hardware dispatch
  records attributable to its mnemonic under `raw/`.
  *Refuter:* one or more refreshed labels have no such record.

Each hypothesis is reported on its own evidence; none is allowed to rescue another.

## 3. Method — reuse, do not rebuild

`analysis/collect_raw.py` and `analysis/audit.py` are **verbatim copies** of
`experiments/EXP-0164-inert-audit/analysis/{collect_raw.py,audit.py}`, re-pointed at
this experiment's `work/` snapshots. Copying rather than re-writing is deliberate:
the indexer already handles the per-experiment raw-schema differences and its
bit-exact attribution (fit the instruction offset from `db.json`'s own `match`
constraints, partition by "instruction word with the field's bits cleared") is the
part an audit must not re-litigate silently. Diffs to those two files are limited to:

1. the `EXP`/`WORK` paths (they resolve relative to `__file__`, so no edit is needed);
2. `controls.py` additions listed in §6 — **new outputs only, never a change to a
   bucket rule or a threshold**;
3. removing EXP-0164's hard-coded `validation_snapshot_sha256` string in `_meta`.

Any further change to the two scripts must be recorded in `RESULTS.md` §Deviations.

## 4. Definitions (inherited verbatim from EXP-0164 §4 — restated, not re-derived)

**Universe.** Every field record of `work/validation.snapshot.json` whose `label` is
`hardware-run` or `isolated-byte-diff`, excluding `_instruction` pseudo-entries.
Expected size **638** (555 + 83); a mismatch is a control failure (§6 C4).

**Raw corpus.** `experiments/<EXP>/raw/**` ONLY. `work/`, `analysis/`, `harness/`
are excluded.

**Arm** = `carrier`+`arm` joined where both exist, else whichever exists, else `"-"`.
**Run** = the path component immediately below `raw/`.
**Gated run** = any run whose directory name does not match
`prefreeze|smoke|pilot|quarantine|burned` (case-insensitive) and whose directory
contains no `PARTIAL.md`. If that leaves nothing, all runs are used and the record is
flagged `gating_fallback`.
**Contaminated case** (excluded from every count): `outcome` ∈
{`invalid_run`,`victim`,`skipped`} or the record carries `skip_reason`.
**Effect signature** = `(hard_class, sha1(json(observed)))` with
`hard_class = outcome` when `outcome` ∈ {`fault`,`hang`,`undecodable`,`killed`,
`not_written`,`no_draw`,`lost_7_of_8`,`nondeterministic`}, else `"run"`. Faults and
hangs ARE movement.
**Moved**(field, arm, run) = dispatched values whose signature differs from that
triple's modal signature, counted **within** a partition sharing the same
instruction word outside the field.

## 5. Thresholds (FROZEN — identical to EXP-0164 §5, deliberately not re-tuned)

`STABLE-LIVE(arm)` iff all of:
1. ≥ 2 gated runs cover the arm and `common ≥ 2`;
2. `moved ≥ 1` in **both** runs;
3. `agree_pct ≥ 99.0`;
4. `min(movedA, movedB) ≥ 2.0 × disagreements`.

Note the form: **`>= 2.0 * disagreements`, not `>= 2.0 * max(disagreements, 1)`.**
The `max(...,1)` form cannot promote any width-1 field and is a refuter of H3
wherever it appears in merged code.

**Decision tree over the union of all citing experiments, first match wins:**
1. no dispatched case anywhere → **UNVERIFIABLE**
   (sub-reasons `no-raw` / `no-field-records` / `raw-present-but-unattributable` /
   `field-named-but-unstructured`, reported but all still UNVERIFIABLE);
2. ∃ arm `STABLE-LIVE` → **STABLE-LIVE**;
3. total moved == 0 everywhere → **INERT-MULTI** (≥2 arms tested) else **INERT-SINGLE**;
4. movement exists, no stable-live arm → **SINGLE-RUN** (no arm has ≥2 gated runs)
   else **UNSTABLE**.

**Withheld set (strict)** = `INERT-SINGLE ∪ UNSTABLE ∪ UNVERIFIABLE`.
**Withheld set (lenient)** = strict minus `field-named-but-unstructured`.
`INERT-MULTI` and `SINGLE-RUN` are **not** withheld, matching EXP-0164, so this audit
cannot be accused of having invented a stricter bar than the one that produced 41.

**Emittable rule** (reimplemented against the pinned snapshots): an instruction is
emittable iff every field of its `db.json` descriptor is emitter-grade and not
withheld; a field-less descriptor falls back to its `_instruction` entry; an
`_instruction.note` containing `EMITTABLE VETO` forces non-emittable. Denominator =
descriptors whose `emitter_role` is not `data-word`.

**No threshold, bucket rule, or withheld-set definition may be changed after this
file is committed.** If one is found to be wrong, that is reported in `RESULTS.md`
as a limitation with the number it would have produced, and the frozen number is
still published beside it.

## 6. Controls — falsifiers of THIS audit, declared before running

- **C1 (reproduction of the prior audit).** Restricted to the fields EXP-0164
  withheld and to the same citing raw, this pipeline must reproduce EXP-0164's
  buckets for fields whose validation entry has not changed since. Divergence is
  reported, never tuned away.
- **C2 (positive control).** `iter.dst` must classify `STABLE-LIVE`.
- **C3 (fault-as-movement).** ≥1 field must reach `STABLE-LIVE` on a signature
  change that is a `fault`/`hang` class change, proving the signature is not
  observed-value-only.
- **C4 (no silent skips).** `len(audit.json) == 638` exactly, and every distinct
  evidence id cited by an emitter-grade row appears in `experiment_coverage.json`
  with a parse verdict.
- **C5 (the audit can still say NO).** At least one currently emitter-grade field
  must land in a withheld bucket. If the strict withheld set is empty the pipeline
  is presumed broken, not the corpus presumed perfect.
- **C6 (width-1 sanity).** The gate must be exercised against a real width-1 field
  with 0 disagreements and shown capable of promoting it. If no width-1 field
  reaches `STABLE-LIVE`, that is reported as a possible gate artefact.

## 7. The five directed checks (each has a stated refuter)

1. **Post-`459bb8bd` cohort.** Bucket every emitter-grade field whose citing
   evidence includes an experiment merged after `459bb8bd`; report withheld rate vs
   the rest (H2).
2. **The four ungated orchestrator rulings** — `get_sr.form` →
   `isolated-byte-diff`, `iter_at._instruction` → `hardware-run`, the
   `_instruction` gate applied post-EXP-0181, and the `call.b6` correction. Each is
   re-derived from raw independently of the ruling's own text (H5 covers the third).
3. **UNVERIFIABLE census.** Count remaining UNVERIFIABLE rows and report whether any
   currently-emittable instruction depends on one.
4. **Text-vs-evidence contradiction sweep** (H4). Mechanically parse every
   emitter-grade row's `range`+`note` for inertness/absence assertions
   (`inert`, `no effect`, `no observable`, `framing only`, `never moved`,
   `unused`, `reserved`, `must be`, `ignored`, `don't care`) and cross-check against
   `moved_total` and hard-class outcomes in the attributed raw. Any row asserting
   inertness with `moved_total > 0`, or asserting "framing only" with faults, is
   listed.
5. **Cannot-fail-check hunt.** Static review of gates/controls/ladders/oracles in
   post-`459bb8bd` experiment `analysis/` and `harness/` code for checks that cannot
   come out the other way (the seven known instances are the pattern library). A
   candidate is reported only with the exact file, line, and the argument for why
   the check has no failing branch.

## 8. Known confounders

- **The audit inherits EXP-0164's attribution, including its blind spots.** A field
  whose raw uses a schema the indexer cannot attribute reads UNVERIFIABLE even if
  the underlying hardware evidence is real. UNVERIFIABLE is an **auditability**
  verdict, not a refutation, and is reported as such.
- **`INERT-MULTI` is not withheld here**, so the orchestrator's rule "eight arms that
  cannot express a field are one arm" is *not* applied as a withholding criterion.
  Where the arms plausibly cannot express the field, that is reported as an
  advisory, with the count it would cost, and not folded into the headline.
- **The raw corpus grew since EXP-0164**; new experiments may use schemas the
  indexer handles only at label level (`byte_level_only`). That flag is reported per
  field.
- **A `fault` recorded during a reader-thread cascade (DEF-0178-1) is an artefact,
  not an observation.** The indexer cannot tell them apart, so movement produced
  purely by `hang` signatures in a cascade-suspect run is flagged, not silently
  trusted.
- Analysis is offline and read-only; it cannot resolve a question that needs the
  device. Anything that does is reported as BLOCKED, not guessed.

## 9. Deliverables (fixed here)

`analysis/audit.json` (per-field bucket, citing experiment, per-arm/per-run counts,
source raw files), `analysis/reclassify.json` (flat `<mnemonic>.<field>` with
`start`/`width` from `db.snapshot.json`, per FIELD-SWEEP-PROTOCOL §5),
`analysis/emittability.json`, `analysis/controls.json`, `manifest.json`,
`RESULTS.md` with the honest number beside 55/166 and 638/1040 and a ranked list of
which instructions lose status. **No `git commit`; no edit to `db.json`,
`validation.json`, `docs/`, or `PROVENANCE.md`.**
