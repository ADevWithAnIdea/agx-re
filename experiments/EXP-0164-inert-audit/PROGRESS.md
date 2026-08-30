# EXP-0164 — PROGRESS (append-only)

Pure **analysis** experiment. **No device work, no SSH, no GPU.** Every input is
already committed in this repository.

## 2026-08-30 — M0: briefs read, universe pinned

- Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
  `experiments/FIELD-SWEEP-PROTOCOL.md`, `tools/agx-isa/validate_labels.py`,
  `experiments/EXP-0155-g17p-emit-tex-frag/RESULTS.md` +
  `analysis/withheld_by_orchestrator.json` (the policy this audit generalises),
  `experiments/EXP-0163-g17p-inert-liveness/analysis/audit_0155.py`, and
  `work/UNATTENDED-RUN.md` (the merge-policy revision of 2026-08-30).
- **`tools/agx-isa/validation.json` is being edited concurrently by the
  orchestrator.** It read `hardware-run: 548` at the start of this session and
  `553` twenty minutes later. An audit against a moving file is not reproducible,
  so the universe is **pinned to a snapshot**:
  - `work/validation.snapshot.json` sha256 `c40195cd9f65d9176c5bc518ede1c171cf3904c26ba81f7b93dc2414b1ad7091`
  - `work/db.snapshot.json`         sha256 `83b83a350ece33b8fd9e98b773f02be2da89a5f942824896574ff22827042341`
  - repo revision at snapshot: `b7dedbf0ce37c0a95823923bc70f3cab0f733b3c` (both files clean at HEAD).
- **The dispatch's "659" is already stale.** In the pinned snapshot the emitter-grade
  population is **664 fields** (553 `hardware-run` + 111 `isolated-byte-diff`), over
  **67 / 166** emitter-relevant instructions (`emittable_of_emitter_relevant`).
  All numbers below are against the pinned snapshot.
- Raw-schema reconnaissance completed (keys, outcome vocabulary, run-directory
  layout) — recorded in `PRE_REGISTRATION.md` §3. **No verdict was computed before
  the thresholds were frozen.**

Next: M1 — freeze `PRE_REGISTRATION.md`, then build `analysis/collect_raw.py`.

## 2026-08-30 — M1: pre-registration frozen (+ amendment A1)

- `PRE_REGISTRATION.md` written and frozen before any verdict: universe, raw corpus,
  arm/run/gated definitions, the oracle-INDEPENDENT effect signature, the four
  bucket thresholds, the UNVERIFIABLE sub-reasons, the H2 defect test, and four
  pre-declared controls.
- Amendment **A1** (repeat-value rule) added the same day, still before any verdict:
  11.6% of all indexed cases are repeats of a value inside one (field, arm, run), so
  the contract had to say what happens to them. Modal signature over the repeats;
  disagreeing repeats counted, not discarded.

## 2026-08-30 — M2: collector built; two parse defects found and fixed

`analysis/collect_raw.py` indexes 728 387 per-value raw records. Two defects in the
naive "match the raw `field` name against the db.json field name" approach were found
during construction and are recorded as amendments **A2/A3**, because both would have
manufactured a false headline:

1. **The raw does not name db fields, it names what the harness spliced.** Very often
   that is a whole BYTE (`byte+12`, `b6`, `byte0_lonib`) or a composite
   (`op_lsb|op|per_lane|op_msb`, `fmt_class+match[16:24]=86`). A name match reported
   `tile_read.read_en` as having no raw record when EXP-0147 in fact swept all 256
   values of the byte containing it.
2. **The converse error is also live and is the more dangerous one.** A group labelled
   with ONE field name usually varies a whole byte, so movement credited to that field
   may have been produced by a *different* field sharing the byte.

Both are fixed by attributing from the bytes: varying bit mask from the `bytes` column,
instruction offset inside `bytes` recovered by fitting db.json's own `match`
constraints (EXP-0154's carriers embed the instruction in a 20-byte window, so the
offset is not always 0), then per-field partitioning — records are grouped by "the
whole instruction word with THIS field's bits cleared", and only partitions holding
>= 2 distinct values of the field test it at all.

A third rescue: EXP-0140 logs the whole reg-move family under the single instr name
`regmove`, which is not a db mnemonic. The descriptor is recovered from the bytes by
match-constraint fit (unambiguous fits only, never guessed).

Residual unresolved raw groups: 9 268 records / 117 kinds, all of them non-field
probes (EXP-0159 questionnaire items, EXP-0155's `op57_*` collision probes,
EXP-0146's i64-lowering checks, `SEM` semantic probes). Listed in
`work/raw_index.json.gz` `_meta.unresolved_groups`.

## 2026-08-30 — M3: first full classification; all four controls PASS

- **C1** — restricted to EXP-0155, the pipeline independently withholds all 15 fields
  the orchestrator withheld in `withheld_by_orchestrator.json`. PASS.
- **C2** — `iter.dst` classifies `STABLE-LIVE`. PASS.
- **C4** — exactly 664 field records audited; all 53 cited experiments accounted for. PASS.

Headline (pinned snapshot, 664 emitter-grade fields):
`STABLE-LIVE 356 | UNVERIFIABLE 145 | INERT-SINGLE 85 | UNSTABLE 42 | INERT-MULTI 20 | SINGLE-RUN 16`
Emittable 67/166 published -> **15/166 strict**, **40/166** if only INERT-SINGLE is withheld.

Next: M4 — adversarial self-checks on the classification, then RESULTS.md.

## 2026-08-30 — M4: three more parse defects fixed (amendments A2–A5), ladder computed

Adversarial self-review of the first classification found three ways the audit was
being unfair to the corpus, all fixed before the numbers were written down:

- **A4** — `no-field-records` was wrong for EXP-0140: the raw DOES sweep those
  descriptors, but the sweep varies the descriptor-SELECTING byte itself, so no single
  `reg_move_*` descriptor owns the cases. New reason `raw-present-but-unattributable`.
- **A5** — the arm key was `carrier` alone, which collapsed EXP-0140's and EXP-0156's
  distinct occurrences (`carrier=uni`, `arm=regmove.byte2` / `regmove.usrc`) into one
  arm and manufactured INERT-SINGLE verdicts. The key is now the PAIR. This moves the
  number AGAINST the audit's own hypothesis, which is the only direction an amendment
  is allowed to move it.
- A descriptor-identification cache keyed on `(exp, instr, carrier)` was letting the
  first group on a carrier decide the mnemonic for every other group on it. Removed;
  identification is per group.

`UNVERIFIABLE` records now also carry `evidence_files_outside_raw`, so EXP-M4-14's
`splice_results.json` is named rather than silently counted as "no evidence".

Emittability ladder (denominator 166): published **67** -> INERT-SINGLE withheld **43**
-> +UNSTABLE **33** -> chain-broken **22** -> lenient **17** -> strict **16**.

Next: M5 — RESULTS.md, README.md, manifest.json.

## 2026-08-30 — M5: deliverables written; pipeline re-run clean

- `README.md`, `RESULTS.md` (10 sections, 7 machine-generated tables), `manifest.json`,
  `raw/NO_RAW.md` (this experiment ran no probe; its inputs are other experiments'
  append-only raw, opened read-only, plus two hashed snapshots).
- `analysis/reclassify.json` now emits each withheld field in the
  `FIELD-SWEEP-PROTOCOL.md` §5 shape — `label: "untested"`, the original `range` and
  `target`, the citing `evidence`, and a `note` saying exactly what was dispatched, on
  how many carriers, how much moved, and what would fix it — so it can be merged
  directly and still pass `validate_labels.py`'s "untested-with-evidence needs a note"
  rule.
- Full pipeline re-run end to end: identical bucket counts and withhold set, even though
  the raw corpus grew under it (EXP-0163/0165/0166/0167 writing concurrently; case
  groups 4 198 -> 4 354). Only cited experiments' raw is read, so the verdicts are
  stable.
- **Nothing outside `experiments/EXP-0164-inert-audit/` was written.** `docs/`,
  `PROVENANCE.md`, `db.json` and `validation.json` untouched; no commit made.

FINAL: 664 emitter-grade fields -> STABLE-LIVE 359 (54.1%), UNVERIFIABLE 144 (21.7%),
INERT-SINGLE 81 (12.2%), UNSTABLE 41 (6.2%), INERT-MULTI 23 (3.5%), SINGLE-RUN 16 (2.4%).
Emittable 67/166 -> 43 (INERT-SINGLE withheld) -> 33 (+UNSTABLE) -> 16 (strict).
