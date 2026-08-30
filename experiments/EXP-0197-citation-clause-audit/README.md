# EXP-0197 — do the thirty "has no per-value records" clauses tell the truth?

**Question.** Thirty `note` fields in `tools/agx-isa/validation.json` carry the clause
*"the original citation `<EXP-…>` has no per-value records for it"*. Each clause was the
stated justification for `EXP-0189` re-pointing that row's `evidence`. `EXP-0196` verified
six of the thirty and found all six FALSE. **Are the other twenty-four true?**

Twenty-nine of the thirty sit on emitter-grade fields (17 `hardware-run`, 12
`isolated-byte-diff`), which are the fields the published "544 of 1040 emitter-grade" count
is made of. A false clause does not by itself move a label, but it mis-states where a row's
evidence lives, which is the audit trail the closure gate is checked against.

**Scope and constraints.**
* Desk analysis only. The target hardware is offline; nothing was dispatched.
* Clean room: only our own committed artifacts (JSON / JSONL / text logs / hex dumps of our
  own compiled shaders / our own scripts) and our own disassembler `tools/agx-isa/isadb.py`
  were read. **No Apple binary was opened, disassembled, or introspected.**
* **Nothing outside this directory was modified.** No label, no file under `tools/agx-isa/`,
  no `PROVENANCE.md`, no `docs/` file was touched. Nothing was committed.

## The criterion, stated so it can return "no"

> **CLAUSE-FALSE** — the originally-cited experiment commits, for this field, **≥ 2 per-case
> records in which the field's own bits take different values**, each record carrying its own
> committed observation (a dispatch outcome, a readback, a fault, a pixel dump).
> **CLAUSE-TRUE** — no such pair exists under **any** keying tried.
> **UNRESOLVED** — the search was blocked.

It returned "no" three times, so it is not a cannot-fail check. Two further falsifiers are
applied inside the FALSE bucket and both fired (`RESULTS.md` §4).

## Why a field-name index is not admissible evidence here

`EXP-0189/analysis/collect_raw.py` admits a raw record only if **(1)** the file is under
`<exp>/raw/**` and ends in `.jsonl`, **(2)** `rec["instr"]` is a `str`, **(3)** `rec["field"]`
is a `str`, and **(4)** that string does not begin with `_`. Everything else is `continue`d
*before* any byte-level attribution runs. `rescue.py` later lifts (4) for names not matching
`baseline|ladder|falsifier|control|…`, but keeps (1)–(3).

`analysis/collector_blindspot.py` re-runs that admission filter over all 27 originally-cited
directories. **24 of them yield zero admissible records — for any field, not just the one in
question.** So for those rows the clause restates the collector's input filter, not a property
of the experiment.

This audit therefore searches under four independent keyings and reports each separately:

| | keying | what it catches |
|---|---|---|
| **K1** | `instr == <mnem>` and `field == <field>` | modern named sweeps |
| **K2** | `instr == <mnem>`, `field` null or `_`-prefixed, `byte_index` inside the field's `db.json` byte span | `EXP-0171`-style byte sweeps, `__dst_nibble`, `__falsifier_byte0` |
| **K3** | any `group`/`carrier`/`arm`/`name`/`item`/`case`/`kernel`/`label` string naming the field or mnemonic | case-name sweeps |
| **K4** | encodings recovered from **every** file format — `.jsonl`, per-case `.json`, `.txt`, `.log`, `.hex` — tokenized with `tools/agx-isa` (ANCHORED) or fitted to the descriptor's own `match` constraints (MATCHFIT, weak) | the pre-2026-08 text-log corpus, which K1–K3 cannot see at all |

K4 harvests **space-separated** hex (`0f 80 86 02 …`, `a9171415 02000000 …`) as well as
contiguous runs. The first pass did not, and returned a false zero for `call_indirect` — the
same class of blind spot this audit is investigating, so it is fixed here rather than reported
as an absence (`RESULTS.md` §6.1).

## Layout

```
analysis/
  rows.py                  -> work/rows.json               the 30 rows, originals resolved, db spans
  scan.py                  -> work/scan_*.json             K1..K4 over every original citation
  census.py                                                per-value census of one field in one experiment
  dump.py                                                  pretty-print one row's scan evidence
  descriptor_scan.py       -> work/descriptor_scan.json    the two whole-descriptor (`_instruction`) rows
  distinct_bytes.py        -> work/distinct_bytes.json     the distinct-encodings falsifier
  collector_blindspot.py   -> work/collector_blindspot.txt EXP-0189's own admission filter, re-run
  positive_half.py         -> work/positive_half.json      do the REPAIRED citations carry the records?
  classify.py              -> verdicts.json / .tsv         the three buckets, with evidence
  worse_source.py          -> worse_source.json            did the repair point at a worse source?
```

## Reproduction

```
python3 analysis/rows.py
python3 analysis/scan.py                 # ~4 min, ~250 MB of committed raw
python3 analysis/descriptor_scan.py
python3 analysis/distinct_bytes.py
python3 analysis/collector_blindspot.py
python3 analysis/positive_half.py
python3 analysis/classify.py
python3 analysis/worse_source.py
# spot-check any single row:
python3 analysis/census.py EXP-0034-texture-variants tex_sample variant --under raw
```

Citations resolve exactly as `tools/agx-isa/validate_labels.py` resolves them
(`glob(experiments/<slug>*)`).

Findings, with file + line + counts for every one: `RESULTS.md`.
