# EXP-0170 — assembler under-coverage, round-trip blindness, and disowned-run selection

**Pure analysis. No device, no SSH, no GPU, no `macvdmtool`.** Nothing outside this
directory was written. **Nothing is promoted** — this experiment only withholds and reports.

## Question

Three defects in our own tooling, and how much of the emitter-grade record each actually costs:

- **A/B — `DEF-0166-1`.** The pre-fix `isadb.assemble()` OR-ed the descriptor's `match`
  constants and then OR-ed field values into the same word. An OR cannot clear a bit, so
  every `match` bit inside a field's span was stuck at 1 for every caller. Silent
  under-coverage: a sweep counts *N* dispatched values while the hardware sees *N/2^p*.
- **C — round-trip blindness.** `assemble(disassemble(b)) == b` is invariant under any
  defect symmetric across encode and decode. Who relied on that idiom, and what did it prove?
- **D — disowned-run selection.** `EXP-0164/analysis/audit.py:78-80` picks the two runs with
  the most distinct values, ties alphabetical, with no test of whether the source experiment
  still stands behind the run; and `collect_raw.py:42` scored never-dispatched
  `skipped_after_hangs` placeholders as observations.

## Answer

**Both materiality falsifiers fired. Little is affected, and the report says so with numbers.**

| | |
|---|---|
| 53 fields overlap their own `match` | 31 **proven** to have exceeded the old limit (harness bypassed `assemble()`) |
| 617 emitter-grade fields on distinct-`bytes` | 435 FULL-RANGE, **8 UNDER-COVERED**, 174 UNKNOWN — and only **1** (`falu2_ext.opsel`) is attributable to DEF-0166-1 |
| Round-trip suite under the **defective** assembler | test (A) 173 cases **0 failures**; test (B) 37 cases **0 failures** — demonstrated blind |
| 266 withheld fields re-scored | **253 AGREES, 11 wrong-reason, 2 WRONGLY-WITHDRAWN** |
| Net exposure vs the *40/166, 614 fields* headline | **13 rows**, all M4; **4 already in flight on G17P**; **0** blocked by a moved span |

Full findings: **`RESULTS.md`**. Scope 2: **`analysis/roundtrip_blindness.md`**.

## Layout

```
PRE_REGISTRATION.md   frozen before any verdict; AMENDMENT D dated and frozen
                      before any Arm D number was computed
PROGRESS.md           append-only milestone log (M0 - M8)
RESULTS.md            findings, per arm, with the falsifier outcomes
manifest.json         sha256 of every artifact + every pinned input + the raw read
analysis/
  static_overlap.py|.json          Arm A: the 53, and 2^(w-popcount(match & span))
  coverage_index.py                Arm B: re-index every raw JSONL, add the two counters
  classify.py                      Arm B: FULL-RANGE / UNDER-COVERED / UNKNOWN
  coverage.json                    *** DELIVERABLE: per field, claimed vs distinct bytes
  reclassify.json                  the ONE row I would put to the orchestrator
  reclassify_frozen_rule.json      what the mechanical frozen rule emits for all 8
  roundtrip_idiom.py|.json         Arm C: AST census over 1,419 python files
  roundtrip_blindspot.py|.json     Arm C: re-run the repo's suite against the OLD assembler
  roundtrip_blindness.md           *** DELIVERABLE: Scope 2 write-up
  run_eligibility.py|.json         Arm D: E1/E2/E3, with a quote+file:line per disownment
  rescore_D.py|rescore_D.json      Arm D: S1/S2/S2f/S3/S3b side by side, all 266 fields
  emit_wrongly_withdrawn.py        Arm D: the orchestrator's list
  wrongly_withdrawn.json           *** DELIVERABLE: both scorings, run ids, start/width
work/
  db.snapshot.json                 pinned db.json (all numbers are against this)
  validation.snapshot.json         pinned validation.json
  collect_raw_D.py                 EXP-0164 collect_raw.py + AMENDMENT D.2 ONLY (47 lines)
  raw_index_D.json.gz              placeholder-filtered raw index
  coverage_index.json.gz           Arm B index
  assemble_callsites.json          who calls assemble(), for Arm C triage
  fields_scored_against_ineligible.json
  make_manifest.py
raw/                  EMPTY BY DESIGN -- this experiment dispatched nothing
```

## Reproduction

Deterministic, offline, ~2 minutes total. From the repo root:

```sh
cd experiments/EXP-0170-assemble-coverage-audit
python3 analysis/static_overlap.py            # Arm A
python3 analysis/coverage_index.py            # Arm B index   (~4.7M raw lines)
python3 analysis/classify.py                  # Arm B -> coverage.json
python3 analysis/roundtrip_idiom.py           # Arm C census
python3 analysis/roundtrip_blindspot.py       # Arm C demonstration
python3 work/collect_raw_D.py                 # Arm D re-index (D.2)
python3 analysis/run_eligibility.py           # Arm D (D.3)
python3 analysis/rescore_D.py                 # Arm D re-score
python3 analysis/emit_wrongly_withdrawn.py    # Arm D deliverable
python3 work/make_manifest.py
```

`work/collect_raw_D.py` is `EXP-0164/analysis/collect_raw.py` with **one behavioural
change** (the D.2 placeholder predicate); `diff` the two to audit it — 47 changed lines,
all of them the predicate, its bookkeeping counter, and the output path.
`analysis/rescore_D.py` **imports** `cross_run`, `stable_live` and `classify` from
EXP-0164's `audit.py` and asserts its thresholds are `(2, 99.0, 2.0)`, so the gate is
provably unchanged and cannot have been retuned after seeing the answer.

## Clean-room statement

```
Clean-room provenance: OWN-SHADER + HW-PROBE (offline re-analysis of committed evidence)
Inputs inspected: this repository's own committed raw sweep records (JSONL written by
  harnesses we authored, from MSL we authored), tools/agx-isa/{db,validation}.json,
  and our own harness/analysis source.
Apple binary introspection: NONE
Device work: NONE
```

## What this experiment may not conclude

It says nothing about hardware. `UNDER-COVERED` means *this evidence does not support the
merged range* — never "the field is dead", never "the hardware rejects those values". It
promotes nothing, changes no `target`, and does not settle EXP-0158's provenance claim
(**EXP-0167** owns that ledger check: 204,044 `assemble()` calls, 0 differences).
