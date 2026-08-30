# EXP-0198 — completing the note-integrity audit of `tools/agx-isa/validation.json`

**Question.** `EXP-0196` audited whether the *observations* a `note` states exist in
committed evidence. It tested **391 of 855** notes and separated **167** that carry a
falsifiable claim but for which it built no instrument (`EXP-0196/work/not_checked.json`,
113 of them on emitter-grade fields). **Do those 167 hold?**

Plus one question EXP-0196 raised and declined to answer: the **12 `b_alu10_*` rows whose
`note` says "0 values dispatched" beside a `range` saying "256 of 256 sub-values, DENSE"**
(`EXP-0196/RESULTS.md` §3.5 — "a descriptor-identity question this audit is not equipped to
settle").

**Scope and constraints.**
* Desk analysis only — the target hardware is offline. Nothing was dispatched.
* Read-only outside this directory. **No label, no file under `tools/agx-isa/`, no
  `PROVENANCE.md`, no `docs/` file was modified. Nothing was committed by this experiment.**
* Clean room: only our own committed artifacts (JSON / JSONL / text / our own scripts /
  our own `tools/agx-isa` disassembler on our own byte strings) were read. No Apple binary
  was opened, disassembled, or introspected.
* The 391 EXP-0196 already tested were **not** re-audited. The 30 rows whose notes claim
  *"has no per-value records"* are another agent's task and were **skipped** — as it
  happens none of them is in the 167, so there is no overlap to resolve.
* **No label change is proposed here.** This experiment reports; the orchestrator rules.

## Layout

```
analysis/
  check_0139.py  -> check_0139.json    38 EXP-0139 notes: silent-zero / fault-range /
                                       not-reproducible / TESTED-BUT-UNEXPLAINED counts
  check_0157.py  -> check_0157.json    25 EXP-0157 notes: 59 `outcomes ...| carrier ...`
                                       segments + their `accepted set:` masks
  check_0162.py  -> check_0162.json    12 EXP-0162 notes: outcome histograms + the
                                       "detection power" arm figures
  check_0155.py  -> check_0155.json    19 EXP-0155 notes: the re-pointing clauses and the
                                       swept/disagree clauses          <-- THE FINDINGS
  check_e0189_nonzero.py -> ...json    25 "EXP-0189 withheld ... N values dispatched"
                                       notes with N > 0 (EXP-0196 covered only N == 0)
  check_0140.py  -> check_0140.json     8 EXP-0140 notes (control-flow, psel, mov_imm, usrc)
  check_0138.py  -> check_0138.json     4 "N/16 pre-registered predictions REFUTED" notes
  check_0141.py  -> check_0141.json    10 EXP-0141 atomic notes
  check_0147.py  -> check_0147.json     6 EXP-0147 notes (pixel_order, vtx_coord_xform, n3)
  check_fspecial.py -> ...json          4 EXP-0161/0165 `fspecial` notes
  check_withheld.py -> ...json          the 4 EXP-0191/0192/0193 "Case C" clauses
  check_misc.py  -> check_misc.json    16 remaining notes incl. the ten EXP-0181
                                       `_instruction` refresh notes
  check_b_alu10.py -> ...json          PART 2: the 12 b_alu10_* rows
  negative_control.py -> ...json       FALSIFIABILITY CONTROL (11/11 instruments)
  classify.py    -> classification.{json,tsv}
  run_all.sh                           regenerate every output, in dependency order
work/
  nc_entries.json, nc_notes.txt        the 167 rows and their note text
  validation.perturbed.json            written only by negative_control.py
```

## Reproduction

```
bash analysis/run_all.sh          # every check, then the classification
python3 analysis/negative_control.py   # then re-run run_all.sh: the control
                                       # deliberately leaves perturbed outputs behind
```

Findings, with quoted note text and quoted contradicting file+line: `RESULTS.md`.
