# EXP-0164 has no raw capture of its own — by design

This experiment ran no probe. Its inputs are the append-only `raw/` trees of the
experiments it audits, which stay where they are and were opened **read-only**.

The immutable inputs are pinned by hash instead:

| pinned input | sha256 |
|---|---|
| `work/validation.snapshot.json` | `c40195cd9f65d9176c5bc518ede1c171cf3904c26ba81f7b93dc2414b1ad7091` |
| `work/db.snapshot.json` | `83b83a350ece33b8fd9e98b773f02be2da89a5f942824896574ff22827042341` |

repo revision at snapshot: `b7dedbf0ce37c0a95823923bc70f3cab0f733b3c`

`work/raw_index.json.gz` is a **derived** index of 728 387 records from those trees,
regenerable with `python3 analysis/collect_raw.py`. It is not evidence and must not be
cited as such; the evidence is the source `raw/` trees, named per field in
`analysis/audit.json` -> `raw_files`.

`analysis/experiment_coverage.json` records, for every one of the 53 cited experiments,
whether its raw parsed and which runs were treated as gated.
