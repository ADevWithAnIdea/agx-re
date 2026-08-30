# EXP-0190 — the `_`-prefix discard in the raw indexer, corrected

**Status: COMPLETE. Pure offline analysis — no device, no shader, no GPU.**

## Question

`EXP-0164`'s `collect_raw.py` (inherited verbatim by `EXP-0189`) discards every raw
record whose `field` name starts with `_`. The filter exists for a good reason —
`_baseline`, `_live_control`, `_arm_not_run` are scaffolding — but a harness that names a
genuine per-value field sweep with a leading underscore is silently discarded, and the
field then audits as "no attributable raw record". EXP-0189 found one instance
(`half_alu_ext8.dst`, swept by EXP-0180 as `__dst_nibble`) and reported it against
itself. **Today's published 37/166 and 554/1040 were computed through that filter.**

1. What is the complete set of `_`-prefixed field names, and which are scaffolding?
2. With the filter corrected — not removed — which withheld fields legitimately return?
3. Is there a tenth check in this chain that cannot come out the other way?

## Hypotheses and refuters

Frozen in `PRE_REGISTRATION.md` before any verdict. H1 (calibration): at least one `_`
name is a genuine field sweep — refuter: the corrected indexer fails to re-detect
`__dst_nibble`. H2: the correction restores ≥ 1 field — refuter: it restores nothing,
**which is an acceptable and publishable outcome and is what happened.** H3: a further
cannot-fail check exists — refuter: none found.

## Method

1. **Enumerate** every distinct `_`-prefixed `field` value in `experiments/*/raw/**/*.jsonl`
   with its experiments, runs, arms, record count, distinct values, outcomes and the
   `db.json` fields its varying bits land in (`analysis/census_underscore.py`).
2. **Classify** all 96 by hand from the emitting harness line and the records
   (`analysis/classify_underscore.py`), under a rule fixed before inspection: a name is a
   FIELD-SWEEP only if its records vary the encoding bytes **and** the emitting code shows
   the `value` is what was written into that position. Structure alone is not enough —
   `_ANCHOR_VERDICT` records a boolean verdict and would pass a purely structural test.
   No default bucket; the script asserts its table covers the corpus exactly.
3. **Correct the indexer** with a one-test patch of EXP-0189's file, keeping
   `--legacy-underscore` to reproduce the old behaviour (`analysis/collect_raw.diff`).
4. **Re-run the audit** with EXP-0164's `audit.py` and EXP-0189's `recount.py`, extended
   only to take the index path as an argument and to also audit the 154 rows this repo has
   withdrawn to `untested`. `analysis/verify_inheritance.py` proves by AST comparison that
   every verdict-producing function body and frozen constant is unchanged.
5. **Reproduce the published number before withholding anything** (control C1), then
   apply the frozen restoration policy (`analysis/restore.py`).
6. **Hunt for the tenth cannot-fail check** (`analysis/blind_arm_scan.py`).

## Commands

```
python3 analysis/census_underscore.py
python3 analysis/classify_underscore.py
python3 analysis/collect_raw.py --legacy-underscore
python3 analysis/collect_raw.py
python3 analysis/verify_inheritance.py
python3 analysis/audit.py --index raw_index_legacy.json.gz --suffix _legacy
python3 analysis/audit.py
python3 analysis/recount.py --audit audit_legacy.json --index raw_index_legacy.json.gz --suffix _legacy
python3 analysis/recount.py
python3 analysis/restore.py
python3 analysis/blind_arm_scan.py
```

## Answer, in one line each

1. **96 names, 28,736 records: 14 FIELD-SWEEP, 1 CONTROL-SHAPED, 81 SCAFFOLDING** — and
   only 18 of the 96 have a group that varies its bytes, so for 78 the classification
   cannot change anything (`analysis/underscore_fields.json`).
2. **Nothing comes back from the filter fix.** All 154 withdrawn rows bucket identically
   under the defective and the corrected index. The correction moves exactly two
   *already-published* fields out of `UNVERIFIABLE` — `half_alu_ext8.dst` (known) and
   **`half_alu.dst` (new)** — which changes a strict re-derivation of today's headline from
   **35 back to 37**. One field returns by the other route the dispatch named, the
   committed citation repairs: `falu2i.imm_flag` (`analysis/restore.json`).
3. **Yes — DEF-0190-1**: the inert buckets have no detection-power conjunct, and 128 arms
   in the corpus recorded exactly one distinct observation across every case, so they could
   not have returned anything but "inert". Five currently-emitter-grade fields rest
   entirely on such arms. Its remedy — the `_detect` / ladder controls — is discarded by
   the same filter this experiment repaired (`analysis/blind_arms.json`).

## Clean-room statement

```
Clean-room provenance: derived analysis of already-committed evidence
Inputs inspected: tools/agx-isa/{db,validation}.json, experiments/*/raw/**/*.jsonl,
                  experiments/*/{harness,analysis}/*.py -- all our own
Apple binary introspection: NONE. No device contacted, no shader compiled.
Reproduction: the command block above
Evidence: work/{raw_index,raw_index_legacy}.json.gz, work/underscore_census.json,
          analysis/*.json
```

Nothing outside this directory was written. `db.json`, `validation.json`, `docs/`,
`PROVENANCE.md` and EXP-0164/EXP-0189's committed files are untouched; no `git commit`.

**No `raw/` directory.** This experiment captured nothing: it is a re-derivation over the
raw other experiments committed. Its immutable inputs are pinned by sha256 in
`manifest.json` (`work/{db,validation}.snapshot.json`), and every derived artifact is
regenerated by the command block above.
