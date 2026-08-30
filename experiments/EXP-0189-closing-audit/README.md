# EXP-0189 — closing audit of the published 55/166 and 638/1040

## Question

`tools/agx-isa/validation.json` publishes **55 of 166 emitter-relevant instructions
emittable** and **638 of 1040 fields emitter-grade**. EXP-0164 cut the same headline
from 79/166 to 41/166 by re-deriving every emitter-grade field from `raw/`.
Everything merged since commit `459bb8bd` was merged by the orchestrator under its
own policy and had not been audited by anyone else. **Does 55 survive an independent
re-derivation from raw, under EXP-0164's frozen thresholds?**

## Hypotheses (full statement, with refuters, in `PRE_REGISTRATION.md` §2)

H1 the merges hold at 55 · H2 the post-`459bb8bd` cohort is no weaker than the rest ·
H3 the width-1 gate bug (`moved >= K * max(disagree,1)`) is not in merged code ·
H4 no row's `range`/`note` asserts inertness while its raw records movement ·
H5 EXP-0181's `_instruction` refresh is backed by hardware dispatch records.

## Method

Reuse, do not rebuild. `analysis/collect_raw.py` and `analysis/audit.py` are
**verbatim copies** of `experiments/EXP-0164-inert-audit/analysis/`'s (only `_meta`
strings differ) — that indexer already handles the per-experiment raw-schema
differences and does bit-exact attribution by fitting each descriptor's own
`db.json` `match` constraints. Three new scripts add outputs only:

- `analysis/recount.py` — reimplements `tools/agx-isa/validate_labels.py`'s **current**
  emittable rule (audit.py predates the DEF-0173-1 `_instruction` gate), audits the
  172 `_instruction` pseudo-entries, splits the post-`459bb8bd` cohort, and runs the
  text-vs-evidence contradiction sweep.
- `analysis/rescue.py` — re-runs the **frozen** rule over a corrected input for the
  94 `UNVERIFIABLE` rows: underscore-named raw groups the indexer discards (R1) and
  attributable records in experiments the `evidence` list fails to cite (R2).
- `analysis/finalize.py` — emits the deliverable `reclassify.json`.

## Reproduction

```sh
cd experiments/EXP-0189-closing-audit
python3 analysis/collect_raw.py      # -> work/raw_index.json.gz
python3 analysis/audit.py            # -> analysis/{audit,controls,experiment_coverage}.json
python3 analysis/recount.py          # -> analysis/emittability.json
python3 analysis/rescue.py           # -> analysis/rescue.json
python3 analysis/finalize.py         # -> analysis/reclassify.json
```

## Result (detail in `RESULTS.md`)

**55 does not survive. 38 of 166 is the defensible number; 33 as the evidence lists
literally stand. Fields: 556 of 1040, not 638.** The post-`459bb8bd` merges are *not*
the cause — they withhold at 18.3 % against 16.9 % for the corpus they joined. The
shortfall is inherited A18-phase debt, dominated by `EXP-M4-14-a18-splice`, which has
**no `raw/` directory at all** and is still load-bearing for 7 instructions and 29
fields. An eighth cannot-fail check was found and proved constructively
(`EXP-0179/analysis/analyze.py:140-142`).

## Clean-room provenance

```
Clean-room provenance: derived analysis of already-committed evidence (no new capture)
Inputs inspected: tools/agx-isa/{db,validation}.json; experiments/*/raw/** (our own
  append-only records of AGX machine code compiled by the PUBLIC runtime API from MSL
  authored in this project, and byte splices of that same code); our own analysis and
  harness sources.
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled,
  symbol-dumped, strings-scanned or debugged. No shader was compiled. No device was
  contacted -- the A18 Pro was down for the whole run and no device work was attempted.
Reproduction: the five commands above.
Evidence: work/raw_index.json.gz, work/{db,validation}.snapshot.json,
  analysis/{audit,reclassify,emittability,rescue,controls,experiment_coverage}.json,
  work/{coverage_overclaims,range_contradictions,lost_after_rescue,controls_extra}.json,
  work/cannotfail-0179/ (the constructive proof of the section 7 finding).
```

## Constraints honoured

No `git commit`. No edit to `tools/agx-isa/db.json`, `tools/agx-isa/validation.json`,
`docs/`, or `PROVENANCE.md`. `raw/` is empty by design: this experiment captured
nothing, and every file it reads is another experiment's committed evidence.
