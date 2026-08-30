# EXP-0192 — progress

- **T0** — read `CLAUDE.md`, `CODEX.md`, `SUBAGENT_BRIEF.md`, `FIELD-SWEEP-PROTOCOL.md`
  §3/§5, `docs/evidence-classification.md` §2, EXP-0191's pre-registration + its
  `post_hoc_candidates`, and `EXP-0190/analysis/{collect_raw,audit}.py`. Confirmed
  `sig_of` gives `ok` and `fault` different signatures and that `moved` therefore counts a
  fault as movement.
- **T1** — pinned revision `8d01daa35a53a478f72fe800dc94d27492c11d77` (tree clean) and the
  six input hashes; wrote and froze `PRE_REGISTRATION.md` **before computing any count**.
  Criterion: Case A (≥2 distinct valid payloads) STANDS, Case B (≤1 legal value) STANDS
  legality-only, Case C (≥2 legal values, <2 valid payloads) WITHHOLD. YES-direction
  stated explicitly; `call.b5` pre-registered as the R2 control that must NOT be withheld.
- **T2** — wrote `analysis/valid_payload_audit.py`: no third indexer; splits
  `collect_raw.py`'s own signature into (hardclass, observation-hash), imports
  `detection_gate.py::payload_of` unmodified for the record-level second pass.
- **T3** — first run returned `UNVERIFIABLE-HERE` for every row: two loader bugs (the
  index is nested under `["index"]`, and `validation.json` is keyed
  `instructions[mnemonic][field]`). Fixed; rerun.
- **T4** — RESULT: criterion fired. `ret.linkmode` Case A (STANDS, rescued by EXP-0179);
  `ret_luse.linkmode`, `jump_cond.offset`, `n3_sample_read.tail` Case C (WITHHOLD).
  Control `call.b5` Case A — not withheld, so the criterion discriminates.
- **T5** — headline impact computed against `validate_labels.py`: 34/166 → **33/166**
  emittable (family `ret_luse` lost), 549/1040 → **546/1040** fields.
- **T6** — wrote `README.md`, `RESULTS.md`, `analysis/reclassify.json`, `manifest.json`.
  No `git commit`; nothing outside this directory touched.
