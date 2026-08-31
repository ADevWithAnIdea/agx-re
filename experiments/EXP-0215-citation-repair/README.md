# EXP-0215 — citation repair: additions only, each anchored to bits

**Type:** desk analysis of this repository's own committed artifacts. **The device was
NOT touched** — EXP-0213 held the A18 Pro for quiet Gate E confirmations throughout. No
Apple binary was read, disassembled, or introspected. No shader was compiled.

**Nothing outside this directory was written.** `tools/agx-isa/validation.json`,
`db.json`, `docs/`, `PROVENANCE.md`, every `raw/` tree, and EXP-0209's and EXP-0211's
committed caches are untouched. Nothing was committed. No label, range, note, span or
target was changed anywhere.

## The one rule

> **This repair may only ADD a citation. It may never remove or replace one, and every
> addition must be justified by a located record.**

EXP-0189 removed nothing either, and still did a day of damage — in *prose*, by writing
"the original citation has no per-value records for it" onto 30 rows, of which EXP-0197
showed 27 were false. So this experiment writes no prose onto any row. It writes a
proposal file the orchestrator re-derives, and every proposal names a file and a line.

Additivity is asserted mechanically: `scripts/score.py` refuses to build the scratch
sidecar unless each row's original `evidence` list is still a prefix of the proposed one
(0 rows fail; 0 non-`evidence` fields differ anywhere in the file).

## What was built

| script | what it does |
|---|---|
| `scripts/build_index.py` | rebuilds `evidence_index.py`'s per-experiment cache **against today's `db.json`**, into this directory. EXP-0212 moved 5 field spans and added 13 fields this morning; the cache key is a fingerprint of the *experiment's* files, so it does not notice. Scoring today's spans against yesterday's cache is the "record swept the OLD span" hazard. |
| `scripts/locate.py` | subclasses `evidence_index.Indexer` — same K1/K2/K3 keying, same Gate A decode — and records the extra columns a proposal needs: the first **observation** record's file and line, whether the record's own `fstart`/`fwidth` equals the current span, how many distinct values the field's own bits took, and how many committed encodings still satisfy the descriptor's `match`. |
| `scripts/legacy_parse.py` | re-runs `tools/agx-isa/legacy_index.py` (EXP-0211) against the frozen `db.json`, into this directory. |
| `scripts/build_proposals.py` | the admission rules, and `--selftest` (20 assertions: 3 must-admit, 12 must-refuse, 5 helper checks). |
| `scripts/score.py` | the four dashboard runs that separate this experiment's contribution from the legacy indexer's. |
| `scripts/suspect_citations.py` | existing citations that look wrong. **Lists them. Removes none.** |
| `scripts/sibling_check.py` | what the match-destroying candidates actually dispatched. |
| `scripts/annotate.py` | writes each row's measured dashboard effect back into the proposal, including the five rows an addition pulls DOWN. |

## Admission rules

A candidate is any (experiment, row) pair where the experiment's committed `raw/` holds
records for that row's key. It becomes a proposal only if all of:

* **H1** the experiment resolves to a directory, is not quarantined, has a `raw/` tree,
  and commits an authored probe — `promotion_check.rule_R1`'s own three tests. An
  addition failing H1 would push the row from `auditable` to `incomplete` on dashboard 6:
  an addition that makes the row *worse*.
* **H2** the records are in `raw/`, not `analysis/` or `work/`. EXP-0209 found a prior
  audit's own scan output indexable as dispatches.
* **H3** at least 2 records carry an execution outcome. `00_manifest.json` in this corpus
  carries `instr`+`field`+`arm`+`n_cases` and no value, bytes or outcome — it is the plan,
  not the run, and it sorts first in the directory.
* **H4** the attribution is anchored to **bits**, not to a **name**:
  * **T1** ≥2 distinct values of the field's own bits, decoded at the *current* span out
    of committed actual bytes, **and** ≥2 distinct requested values, **and** ≥2 of those
    encodings still satisfy the descriptor's `match`;
  * **T2** the record declares `fstart`/`fwidth` equal to the current span, sweeps ≥2
    values, and the experiment commits no bytes at all;
  * **T3** a legacy byte sweep at a byte index proven inside the field's current span,
    whose **match-preserving** requested values move the field's own bits over ≥2 values.

Refused, each with its reason recorded in `work/refusals.json`:
records declaring a different span (the `carry_gen` `subop`→`srcA`→`srcB` hazard);
committed bytes present while the field's own bits take ≤1 value (EXP-0214's
`half_pack.dst`); every committed encoding failing the descriptor's `match` (EXP-0197
§4.4); a byte index outside the field's current span; K3 group-string substring matches
(EXP-0197 §6.2); and P4 dispatched-program corpora, which credit every field of every
instruction in a program that ran.

## Reproducing

```bash
E=experiments/EXP-0215-citation-repair
cp tools/agx-isa/validation.json $E/work/validation_frozen.json     # another agent writes it
cp tools/agx-isa/db.json         $E/work/db_frozen.json
python3 $E/scripts/build_index.py            # -> work/index          (~3 min)
python3 $E/scripts/locate.py                 # -> work/locators.json   (~3 min)
python3 $E/scripts/legacy_parse.py           # -> work/legacy_index/
python3 $E/scripts/build_proposals.py --selftest      # 20 assertions
python3 $E/scripts/build_proposals.py        # -> analysis/citation_additions.json
python3 $E/scripts/score.py                  # -> analysis/dashboard_delta.json
python3 $E/scripts/annotate.py
python3 $E/scripts/suspect_citations.py
python3 $E/scripts/sibling_check.py
```

`work/index`, `work/index_legacy` and `work/legacy_index/*.jsonl` are derived caches
(72 MB) and are removed after scoring; the commands above rebuild them. Every proposal's
locator points into a committed `raw/` file, not into a cache.

## Layout

```
EXP-0215-citation-repair/
  README.md                          this file
  RESULTS.md                         the numbers, the refusals, and how this could have lied
  selftest_output.txt                20 assertions, both directions
  analysis/
    citation_additions.json          THE DELIVERABLE: 496 additions over 372 rows,
                                     keyed <mnemonic>.<field>, each with a locator
    dashboard_delta.json             the four scored runs
    dashboard_summary.json           the seven ladders, four runs, one table
    downgrades_from_additions.json   the 5 rows an addition pulls DOWN
    suspect_citations.json           existing citations that look wrong. NONE REMOVED.
    sibling_mnemonics.json           records whose bytes decode to another descriptor
  work/
    validation_frozen.json           the sidecar every run was scored against
    db_frozen.json, span_repair.json the descriptor state, and today's 13+5 changes
    locators.json                    every (experiment, row) cell with its locator columns
    refusals.json                    741 refused candidates, each with its reason
    secondary.json                   2 program-corpus credits, reported, not proposed
    reports_{base,prop,base_leg,prop_leg}/   the four scored dashboard runs
```
