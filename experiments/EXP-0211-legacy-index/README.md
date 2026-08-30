# EXP-0211 — making the pre-EXP-0138 raw era machine-readable

**Type:** tooling and offline analysis only. **The device was not touched.** EXP-0210 was
holding the A18 Pro for quiet confirmation captures for the whole of this work; every
artifact here is derived from this repository's own committed files. No Apple binary was
read, disassembled, or introspected.

**Nothing was changed outside this directory and `tools/agx-isa/legacy_index.py`.** No
label, no `tools/agx-isa/validation.json`, no `db.json`, no `docs/` page, no
`PROVENANCE.md` entry. No raw file was edited, rewritten, normalised, or moved — raw is
append-only and this experiment only reads it. Nothing was committed.

## The problem

`tools/agx-isa/evidence_index.py` — and therefore `promotion_check.py` and `dashboards.py`
— reads `.jsonl` and `.json` records keyed by a string `instr` and a string `field`. The
early corpus predates that convention entirely: it is `.log`/`.txt` transcripts, `.hex`
program dumps, and per-case `.json` process captures. **185 of the 226 experiment
directories that have a `raw/` tree yield zero cells to that indexer.** The consequences
are already measured and committed:

* EXP-0197 — 29 cited experiments yield zero admissible records; 27 of 30 "the original
  citation has no per-value records" clauses are false because of it, and for 24 of 27 the
  clause could not have come out any other way.
* EXP-0194 — an audit built on that filter can only ever *lose* evidence, never find it.
* EXP-0209 — 420 of 1040 rows score `no-data` on the geometry and liveness dashboards, and
  its own §4 limitation 4 says an unknown number of those are `format-unreadable` rather
  than genuinely absent.
* `jump.offset` was nearly retracted as "promoted without raw"; its evidence is in
  `EXP-0010-control-flow/raw/run_experiments.log` in prose.

## What was built

`tools/agx-isa/legacy_index.py` — five parsers over the legacy formats, emitting records in
**exactly** the shape `evidence_index.Indexer.handle()` consumes, plus per-record
provenance (`parse_confidence`, `_parser`, `_src_file`, `_src_line`, `_exp`, `_run`).

| id | grammar | source |
|---|---|---|
| `P1` | byte-sweep table: `# … bytes=<hex>` + `# sweeping rel=0xN` header, then `0xVV  OK  <class>  [obs]  raw=<hex>` rows | EXP-0005/0006/0007 `.log` |
| `P2` | prose splice, anchored to committed instruction bytes or to a committed `main:` program | EXP-0010/0012/0013, RT-5 |
| `P3` | absolute-offset sweep, resolved only when exactly one committed program of the stated length carries the stated original byte | EXP-0005 |
| `P4` | dispatched program corpus: a raw record pairing program bytes with a committed execution outcome | EXP-0047/0050/0102/0205 |
| `P5` | key/value dispatch record (`MAIN_ORIG` / `SPLICE …` / `MAIN_SPLICED` / `STATUS`) — the only legacy shape that commits a real Gate A ledger | EXP-0003 |
| `C0` | program bytes with **no** committed outcome → compile-only, written to a separate stream, **never merged** | everywhere |

### The three rules that stop it manufacturing evidence

1. **Never synthesize instruction bytes.** A sweep transcript states a baseline encoding
   and a requested byte; what was actually dispatched is not committed. Reconstructing it
   would assume the splice landed — the exact assumption Gate A exists to test and the
   exact place DEF-0166 hid. Only hex literally present in the file is ever emitted as
   `bytes`. This is why the text parsers move the liveness and limits dashboards and move
   the geometry dashboard by **zero**.
2. **Never guess an attribution.** The mnemonic always comes from tokenizing committed
   bytes with our own disassembler (`tools/agx-isa/isadb.py`); the field comes from a
   literal `db.json` field name or from a byte index proven to lie inside that
   instruction. Everything else is counted as `unparsed` and reported.
3. **Dispatch is not compilation.** Program bytes with no committed execution outcome are
   compile-only corpus evidence and go to a separate stream, because the liveness ladder's
   rung 1 says "dispatched".

## Reproducing

```bash
# the parser must be able to say BOTH yes and no before it is allowed to run
python3 tools/agx-isa/legacy_index.py --selftest        # 35 assertions

# the format inventory
python3 tools/agx-isa/legacy_index.py --survey

# parse the corpus -> index/legacy_records.jsonl, index/compile_only_records.jsonl,
#                     index/parse_stats.json                          (~30 s)
python3 tools/agx-isa/legacy_index.py --parse

# a PARALLEL evidence-index cache. The committed EXP-0209 cache is never modified.
W=experiments/EXP-0211-legacy-index/work
cp -R experiments/EXP-0209-dashboards/work/index $W/base_index
cp -R $W/base_index $W/m1_index && cp -R $W/base_index $W/m2_index
python3 tools/agx-isa/legacy_index.py --parse --merge-cache $W/m1_index --parsers P1,P2,P3,P5
python3 tools/agx-isa/legacy_index.py --parse --merge-cache $W/m2_index

# the five scored runs (the sidecar is frozen first, because another agent writes it)
cp tools/agx-isa/validation.json $W/validation_frozen.json
python3 tools/agx-isa/dashboards.py --index-dir $W/base_index \
        --labels $W/validation_frozen.json --ledger $W/ledgers/base.jsonl \
        --reports $W/reports_base --run-id EXP-0211-base
#   ...and the same for m1 (m1_index), m2 (m2_index),
#   m3ctl (base_index + validation_counterfactual.json),
#   m3lite (m1_index + counterfactual), m3 (m2_index + counterfactual)
```

The five runs are the delta instrument:

| run | evidence index | citations | what it isolates |
|---|---|---|---|
| `base` | EXP-0209's committed cache | as committed | the before |
| `m1` | + legacy **text** parsers (P1/P2/P3/P5) | as committed | what the transcripts alone add |
| `m2` | + **all** legacy parsers | as committed | the after |
| `m3ctl` | EXP-0209's cache, unchanged | repaired | the effect of the citations alone |
| `m3lite` | + text parsers | repaired | text parsers, citation-unblocked |
| `m3` | + all parsers | repaired | the ceiling |

`m3ctl` exists so that `m3 − m3ctl` is the legacy index's own contribution and not the
effect of adding citations. **The repaired-citation runs are a measuring instrument, not a
proposal**: `work/validation_counterfactual.json` is a scratch copy in this directory, and
adding those citations also *lowers* the audit dashboard (see RESULTS §5).

## Layout

```
EXP-0211-legacy-index/
  README.md                     this file
  RESULTS.md                    inventory, records, unparsed fraction, seven deltas,
                                the residue, and how the parser could have lied
  index/
    legacy_records.jsonl        33 760 records in evidence_index's own shape
    compile_only_records.jsonl   9 807 records deliberately NOT merged
    parse_stats.json            candidates, refusals with reasons, refusal samples
  analysis/
    format_inventory.json       every extension under experiments/*/raw/, with counts
    records_by_format.json      records per parser / confidence / source format
    dashboard_delta.json        the seven dashboards across all five runs
    nodata_movement.json        which bottom-rung rows moved, and under which run
    nodata_residue.json         the rows that stay `no-data`, grouped by what they cite
  work/
    reports_{base,m1,m2,m3ctl,m3lite,m3}/   the six scored dashboard runs
    validation_frozen.json      the sidecar snapshot every run was scored against
    validation_counterfactual.json  the scratch citation repair (M3 only)
```

`work/{base,m1,m2}_index` and `work/ledgers` are derived copies and are removed after
scoring; the commands above rebuild them.
