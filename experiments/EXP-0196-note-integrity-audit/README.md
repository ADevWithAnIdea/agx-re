# EXP-0196 — note-integrity audit of `tools/agx-isa/validation.json`

**Question.** Every field entry in `tools/agx-isa/validation.json` may carry a `note`.
Those notes make factual claims — "N values dispatched", "moved on M of N carriers",
"three executions", "reproduced across two runs", "the original citation has no
per-value records". **Which of those claims is NOT supported by committed raw evidence?**

This is the direction nobody had checked. `EXP-0164` and `EXP-0189` audited whether the
cited evidence supports a **label**. This audit asks whether a note's stated
**observations** exist on disk at all.

**Seed.** `EXP-0194/RESULTS.md` §6 flagged `rt_ray_mem.field_off`: `EXP-0157` carries an
unmerged `isolated-byte-diff` verdict whose byte-diff half is committed but whose claimed
*three executions* the auditor could not find. Resolve that, then generalise.

**Scope and constraints.**
* Desk analysis only — the target hardware is offline. Nothing was dispatched.
* Read-only outside this directory. **No label, no file under `tools/agx-isa/`, no
  `PROVENANCE.md`, no `docs/` file was modified. Nothing was committed by this experiment.**
* Clean room: only our own committed artifacts (JSON / JSONL / text / our own scripts)
  were read. No Apple binary was opened, disassembled, or introspected.

## Layout

```
analysis/
  extract_claims.py          -> claims.jsonl            every checkable claim in every note
  note_provenance.py         -> note_provenance.json    which committed artifact carries each note
  raw_field_index.py         -> work/raw_field_index.json.gz   what the 1.8 GB of raw jsonl names
  check_0169.py              -> check_0169.json         "moved on N of M ladder-passing carriers", from raw
  check_0168.py              -> check_0168.json         "X% agreement over K shared values", from raw
  check_outcomes.py          -> outcomes_check.json     `outcomes {...}` naive per-run count  (NEGATIVE CONTROL — do not read as findings)
  check_outcomes2.py         -> outcomes_check2.json    `outcomes {...}` under the producing experiment's own gate
  check_citation_repair.py   -> citation_repair_check.json    name-only pass  (superseded)
  check_citation_repair2.py  -> citation_repair_check2.json   (instr, field) + byte-span pass
  check_e0189_zero.py        -> e0189_zero_check.json   "0 values dispatched" claims, from raw
  check_coverage_keys.py     -> coverage_keys_check.json  machine-readable values_dispatched / distinct_bytes
  classify.py                -> classification.json/.tsv  the four buckets
work/
  all_notes.tsv, emit_notes.tsv, claim_segments.*, raw_field_index.json.gz, ...
```

## Reproduction

```
python3 analysis/extract_claims.py
python3 analysis/note_provenance.py
python3 analysis/raw_field_index.py
python3 analysis/check_0169.py
python3 analysis/check_0168.py
python3 analysis/check_outcomes.py        # negative control: 20 "mismatches" that are method artefacts
python3 analysis/check_outcomes2.py       # the real check
python3 analysis/check_citation_repair2.py
python3 analysis/check_e0189_zero.py
python3 analysis/check_coverage_keys.py
python3 analysis/classify.py
```

Evidence-path resolution reuses `tools/agx-isa/validate_labels.py`'s rule verbatim
(`glob(experiments/<slug>*)`), so a citation resolves here exactly as the project's own
validator resolves it.

Findings, with quoted note text and quoted contradicting file+line: `RESULTS.md`.
