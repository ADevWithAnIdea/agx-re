# EXP-0192 — Does fault-vs-ok "movement" meet the emitter bar?

**Status:** COMPLETE. **Pure offline analysis — no device contacted, no shader compiled.**
**Target of the underlying evidence:** G17P (EXP-0156, EXP-0179, EXP-0140 partly M4) and
M4/G16G (EXP-0147). No verdict is promoted across targets.

## The question

`EXP-0190/analysis/collect_raw.py::sig_of` builds a per-case signature as
`"<hardclass>|<sha1(observed)[:10]>"`, where `hardclass` is the outcome when it is in
`HARD` (`fault`, `hang`, …) and the literal `"run"` otherwise. An `ok` case and a `fault`
case therefore **always** differ, and `audit.py`'s `moved` — the count of cases whose
signature differs from their group's modal signature — **counts a FAULT as movement**.

A field whose values merely *fault*, never producing two distinct **valid** outputs, can
thus be scored `STABLE-LIVE` and reach emitter grade.

`EXP-0191` measured the exposure (7 of 337 `STABLE-LIVE` arms have <2 distinct valid
payloads; four emitter-grade rows rest entirely on such an arm) but found it **post-hoc**
and correctly refused to act on it, filing it under `post_hoc_candidates`. This experiment
is the pre-registered successor: **the criterion was fixed and committed before any count
was computed.**

## Hypothesis and criterion (frozen — `PRE_REGISTRATION.md` §4)

`docs/evidence-classification.md` defines `hardware-run` with two conjuncts: arbitrary
values ran and what happened was recorded (**faults count as observations** — explicit in
the text), **and** the output matched prediction. A fault satisfies the first and not the
second. The frozen criterion resolves the two readings by splitting on **how many values
were legal**:

| case | condition | verdict |
|---|---|---|
| **A** | some attributing arm shows **≥2 distinct VALID payloads** | **STANDS** |
| **B** | no arm shows ≥2 valid payloads **and** ≤1 value is observed legal | **STANDS**, `legality-only` — nothing for an emitter to choose |
| **C** | no arm shows ≥2 valid payloads **and** ≥2 values are observed legal | **WITHHOLD** — an *inertness* observation that `moved` re-scored as movement |

Case C is the real defect: absent the fault inflation the row would have been
`INERT-SINGLE`/`INERT-MULTI`, and `INERT-SINGLE` is already in `audit.py`'s `WITHHOLD` set.

## Method — no third implementation

- `EXP-0190/work/raw_index.json.gz` supplies the attribution of raw records to db fields
  and the per-cell **modal signature** map `keys`. This experiment **splits** that
  signature into `(hardclass, observation-hash)`; it does not recompute it. That split is
  exactly the distinction `moved` cannot make.
- `EXP-0190/analysis/audit.json` supplies bucket, arm structure, and `cross_run`.
- `EXP-0191/analysis/detection_gate.py::payload_of` is **imported unmodified** for the
  record-level validity rules (error payloads, empty observations, bookkeeping-only dicts)
  and drives an independent second pass over the append-only `raw/**.jsonl`.

## Reproduction

```
python3 analysis/valid_payload_audit.py
```

Outputs `analysis/valid_payload_audit.json` and — because the criterion fired —
`analysis/reclassify.json`.

## Clean-room statement

```
Clean-room provenance: derived analysis of already-committed evidence (OWN-SHADER/HW-PROBE lineage)
Inputs inspected: experiments/*/raw/**/*.jsonl (our own append-only capture records),
                  tools/agx-isa/{db,validation}.json, EXP-0190/analysis+work, EXP-0191/analysis
Apple binary introspection: NONE. No shader compiled, no device contacted.
Reproduction: python3 analysis/valid_payload_audit.py
Evidence: analysis/valid_payload_audit.json, analysis/reclassify.json
```
