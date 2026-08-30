# EXP-0183 — PROGRESS (append-only; timestamps are local)

## 2026-08-30 — M0: orientation + baseline frozen
- Read CLAUDE.md, CODEX.md, experiments/SUBAGENT_BRIEF.md, FIELD-SWEEP-PROTOCOL.md §3.
- Read EXP-0180 RESULTS.md + analysis/db_defects.json; EXP-0181 analysis/orphaned_validation_rows.json.
- **PURE ANALYSIS. No device, no SSH, no GPU.** Every observation below is re-read from
  committed `raw/` trees; no new hardware run.
- File ownership honoured: I edit `tools/agx-isa/db.json` ONLY. `tools/agx-isa/isadb.py`
  belongs to EXP-0182 and is untouched (it is currently dirty in the working tree — that is
  EXP-0182 mid-flight).
- git HEAD at start: `20613a44194dc48fa95cb0563b88efabf757d09c`; `tools/agx-isa/isadb.py`
  DIRTY (EXP-0182).
- sha256 at start: db.json `1ada4e7b…be04`, isadb.py `500db91a…aa9f`,
  validation.json `230623ac…3eac`.
- **Baseline gate measured, and the dispatch's numbers are STALE by one uncommitted tree:**
  - `work/base_head` (git HEAD isadb.py): **833/1080 clean, 388,604 leftover, 25,419 tokens**
    — exactly the dispatch's figures. Confirms the provenance of the quoted baseline.
  - `work/base_live` (live working tree, = HEAD + EXP-0182's uncommitted isadb.py):
    **840/1080 clean, 387,496 leftover, 25,587 tokens.**
  - Both ALL PASS, 302 `[OK]`, 0 FAIL, 0 crash.
  - **I gate against `base_live`**, the tree my edit actually lands on; `base_head` is
    recorded so the dispatch's number is reconciled rather than contradicted.
