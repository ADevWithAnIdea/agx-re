# EXP-0189 PROGRESS

- **PRE_REGISTRATION.md frozen** at repo rev `0de24f4f`, before any verdict.
  Snapshots pinned: db `2412eac1…`, validation `867e4b05…`.
- `analysis/{collect_raw.py,audit.py}` copied VERBATIM from EXP-0164 (only the
  `_meta` strings differ; diff recorded in RESULTS Deviations).
- `collect_raw.py`: 6,592 groups → 5,910 cells, 0 unparseable lines,
  8,877 records in 152 unresolved kinds. `work/raw_index.json.gz` written.
- `audit.py` over the 638 emitter-grade fields (C4 PASSES: exactly 638):
  STABLE-LIVE 486, INERT-MULTI 27, SINGLE-RUN 14, UNSTABLE 15, INERT-SINGLE 2,
  **UNVERIFIABLE 94** (no-field-records 56, no-raw 29, named-but-unstructured 9).
  C1 (reproduce EXP-0155's 15 orchestrator withholds) PASS. C2 (`iter.dst`
  STABLE-LIVE) PASS.
- `analysis/recount.py` reimplements `validate_labels.py`'s CURRENT rule (incl. the
  DEF-0173-1 `_instruction` gate) and **reproduces the published 55 exactly**.
  - strict withholding (INERT-SINGLE ∪ UNSTABLE ∪ UNVERIFIABLE) → **33 of 166**
  - lenient → 37 of 166
  - `_instruction` gate alone (7 mnemonics whose emitter-grade `_instruction` has no
    per-value dispatch record anywhere) → 51 of 166
- **The `moved >= 2*max(disagree,1)` bug is NOT live.** It appears textually at
  `EXP-0180/analysis/verdicts.py:184` but sits inside `… if disagree else moved > 0`,
  so `max(disagree,1) == disagree` on every branch that evaluates it. Verified by
  enumeration. Every other merged gate uses the correct `2.0 * disagreements` form.
- **Two mechanical causes of FALSE `UNVERIFIABLE` found and rescued**
  (`analysis/rescue.py`):
  - R1 the indexer discards any record whose `field` starts with `_`; EXP-0180 logs
    the ONLY `half_alu_ext8.dst` sweep as `__dst_nibble`;
  - R2 `audit.py` only looks in the CITED experiments; `call.offset` cites EXP-0035
    while EXP-0179 holds fully attributable records for it.
  Widened evidence for 40 of the 94; 29 clear the frozen rule; **57 remain
  UNVERIFIABLE**. Emittable after rescue: **38 of 166**.
- **EXP-M4-14 has NO `raw/` directory at all** (only a narrative
  `splice_results.json`). Seven currently-emittable instructions rest on it.
- `analysis/recount.py` flags **35 emitter-grade rows whose own `range`/`note` text
  asserts inertness/absence while their attributed raw records movement.**
- Two subagents dispatched: (a) hunt an eighth cannot-fail check, (b) verify the
  EXP-0181 `_instruction` refresh and the four ungated orchestrator rulings.

NEXT: finish the text-contradiction list, write RESULTS.md + manifest.json.

## Completed
- `analysis/{recount,rescue,finalize}.py` written and run; `reclassify.json`,
  `emittability.json`, `rescue.json`, `manifest.json`, `README.md`, `RESULTS.md` landed.
- **Headline: 55/166 → 38/166 (generous) / 33/166 (as cited). Fields 638 → 556 / 527.**
- All six pre-registered controls PASS (C1..C6), including C6: 48 width-1 fields reach
  STABLE-LIVE, so the gate is demonstrably not refusing width-1 promotions.
- **Eighth cannot-fail check found and proved constructively**: EXP-0179
  `analysis/analyze.py:140-142` promotes on cross-run AGREEMENT alone — no `moved>=1`
  conjunct. `call.tail` carries a `hardware-run` label from that branch with 0 movement
  on all three arms. Independently confirmed from this audit's own index.
- Clean negatives recorded: the `max(disagree,1)` bug is NOT live; 0 normative `range`
  texts contradict their own raw; `call.b6` and `get_sr.form` both survive re-derivation.
- 8 of the published 55 still depend on a field with no attributable raw record.
- Hand-ruling audit integrated (§8a): `call.b6` SOUND; EXP-0181's 30/30 refresh SOUND
  and byte-verified; `iter_at._instruction` over-labelled (→ `isolated-byte-diff`,
  count unaffected); **`get_sr.form` does not survive** — promoted on 12 records with
  `oracle: null`/`foreign: true` that score the unmutated baseline `wrong_value`, by an
  experiment that filed no verdict for it, against EXP-0172 which HAD spanned the
  documented dimension in both directions and wrote "NOT emitter-grade".
- §8b: the number is also too LOW on one axis — six instructions are blocked only by a
  stale `_instruction` label and all six have per-value dispatch records.
- manifest.json regenerated with all 27 artefact hashes. EXP-0189 COMPLETE.
