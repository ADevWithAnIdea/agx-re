# EXP-0208 — axis reclassification of the withdrawn field rows

**Question.** `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` §10.2 says: *"Do not discard or rerun
everything. Reclassify existing raw on the independent axes first."* 496 field rows in
`tools/agx-isa/validation.json` carry a label that licenses an implementer to emit nothing
(`untested`, `corpus-correlation`, `tokenization-only`, `single-template-inference`). Many of
them are not untested at all — they were **withdrawn** after real sweeps that established real
facts. **What does the committed raw actually support for each of them, on each of the six
independent axes of §2?**

**Hypothesis (falsifiable).** For a substantial fraction of these rows the committed raw
supports a strictly stronger status on at least one axis than `label` implies — specifically
`live` liveness and reproducible fault/hang maps — and the single legacy label is what erased
it. **Refuter:** if the raw for these rows really is absent or really shows nothing moving,
the axes come back `unverified` / `not-dispatched` / `unknown` across the board and §10.2 has
nothing to recover.

**Method.** Pure desk analysis of this repository's own committed artefacts.

* **No device was contacted.** Nine hardware experiments were running on the A18 Pro for the
  duration; this experiment never touched it.
* **No Apple binary was read, disassembled, or introspected.** Inputs are our own append-only
  capture records, our own `db.json`/`validation.json`, and `git log`.
* **No label was changed.** The output is an `axes` object per row, proposed in
  `analysis/axes.json`, for the orchestrator to merge after re-deriving. `label` remains the
  PROMOTION status; `axes` is the EVIDENCE status.

## The instrument, and why it is built the way it is

The dispatch's warning was the design driver: *finding "no raw" is the most likely way to be
wrong.* Two confirmed defects in this corpus manufactured false absences, and building this
experiment found **seven more keyings** on top of them. An exact `(instr, field)` index over
`raw/**/*.jsonl` — the shape of `EXP-0189/analysis/collect_raw.py` — sees **8,223 of the
28,870** record groups this experiment indexes. The other 20,647 are keyed in ways it cannot
see:

| # | Keying | Where it appears |
|---|---|---|
| K1 | exact `instr` + `field` | the EXP-0138+ sweep era |
| K2 | `field: null`, byte index in the record | EXP-0171: 71,262 byte-level sweeps |
| K3 | **dotted** `"n3_mov.dst"` in `field` | EXP-0174 — a bare-name lookup misses every one |
| K4 | leading `_`/`__` (`_detect`, `__ladder_L_*`, `_live_control`) | 11,278 groups, dropped by 0189's `not startswith("_")` |
| K5 | `mnem` only, no field | EXP-0148 token resync: 2.9 M framing records |
| K6 | composite names `op_lsb\|op\|per_lane\|op_msb`, `lut_a+lut_b+op_base`, `size+reg_sel`, `src_class+match[8:12]=4`, `cache@bytemate` | EXP-0141/0144/0156 |
| K7 | byte-position names `byte+12`, `byte3`, `b11hi`, and record-carried `byte`/`byte_index` | EXP-0144/0162/0171 |
| K8 | record-carried `start`/`width` bit span — recovers **legacy names db.json has since split**: `fmt_word` (21,892 records), `dst_pair` (24,578) | EXP-0141/0144 |
| K9 | name containment `dst_desc` → `dst_desc_lo` | EXP-0147 |
| K10 | non-`jsonl` root-evidence JSON with a per-field prose `evidence` string | `EXP-M4-14/splice_results.json` |
| K11 | pre-EXP-0138 `.log`/`.txt` splice transcripts | `RT-5`, `RT-10`, `EXP-0013`, `EXP-O2C/D` |
| K12 | sibling descriptor: raw says `ilogic`, the row is `b_alu10_loe` at the same `(start,width)` | EXP-0171 → 248 rows. **Reported separately and never counted as direct evidence.** |

`analysis/index_jsonl.py` indexes K1–K9 across **860 files / 5,251,950 lines**, yielding
28,870 groups over 4,203,397 keyed records;
`analysis/index_nonjsonl.py` covers 17,087 `.json`/`.txt`/`.log`/`.md` files;
`analysis/curated_prose.json` is hand-verified K11 with the file and the verbatim quote.
Only **git-tracked** files count as committed evidence (`work/tracked_files.txt`).

## Two measurement rules that changed the answer

1. **Union, never sum.** EXP-0194's scanner summed per-group distinct-payload counts, so a
   field that is inert in *both* of two runs reports "2 distinct observed payloads". Every
   set here is UNIONed across groups and the liveness verdict is taken from the **maximum
   within a single carrier**.
2. **EXP-0191's validity rule, not "outcome == ok".** `silent_zero`, `wrong_value` and
   `no_draw` **are observations**; faults, hangs, undecodables and contaminated cases are not.
   Scoring only `ok` cases would move 131 rows from `live` to `inert` — `isel_reg8.cmp_mode` has
   **17 distinct valid payloads across 256 values** and zero `ok` cases.

## Reproduce

```sh
python3 analysis/index_jsonl.py        # K1-K9 index over experiments/**/raw/**/*.jsonl
python3 analysis/index_nonjsonl.py     # .json/.txt/.log/.md mention + structural index
python3 analysis/label_history.py      # per-row label history from the 52 commits to validation.json
python3 analysis/match_rows.py         # L1-L6 per-row evidence bundle
python3 analysis/extra_lookups.py      # L7-L12
python3 analysis/classify_axes.py      # -> analysis/axes.json
python3 analysis/reports.py            # hazard inventory, contradictions, no-raw audit
python3 analysis/make_table.py         # analysis/axes_table.tsv
python3 analysis/wall_check.py         # instrument test against the four documented walls
```

`work/` holds the large regenerable indices (git-ignored, hashed in
`work/derived_index_hashes.txt`).
