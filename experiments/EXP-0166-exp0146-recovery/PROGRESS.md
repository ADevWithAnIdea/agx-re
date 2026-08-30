# EXP-0166 progress log (append-only)

- **2026-08-30 M0** — Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
  `experiments/FIELD-SWEEP-PROTOCOL.md`, `docs/evidence-classification.md`. Read EXP-0146's
  `README.md`, `PROGRESS.md`, `RESULTS.md`, `harness/arms.py` and the raw JSONL schema of
  run01/run03/run04/run05. Read `work/merge_verdicts.py` and confirmed the key-convention
  rejection path (`"%s: %s is not a field of %s in db.json"`). Dumped the current
  `db.json` field lists and `validation.json` labels for the 13 mnemonics in scope.
  **Key structural finding recorded before any statistic was computed:** EXP-0146's oracle is the
  *unmutated baseline output*, so its `match:true` / "ok at {N values}" sets are **inert-sets**,
  not "the field works here" sets.
- **2026-08-30 M1** — `PRE_REGISTRATION.md` frozen with all thresholds, gates G1-G5, falsifiers
  F1-F5, and input SHA-256s. Repo rev at freeze `b7dedbf0` (validation.json dirty in tree).
- **2026-08-30 M2** — `tools/agx-isa/db.json` changed under me mid-analysis (frozen
  `83b83a35…` -> `30ae6a41…`) because **EXP-0165 owns and is repairing that file this session**.
  Handled per confounder §5.5: the drift is *reported, not patched*; a snapshot is pinned at
  `work/db_snapshot.json` so the adjudication is reproducible, and the field **geometry**
  (`start`/`width`) of all 11 in-scope mnemonics was re-dumped and confirmed **unchanged** between
  the two hashes — the drift is in `semantics`/`note` prose and/or other instructions.
- **2026-08-30 M2b** — Coordinator hold received: **no device work on the neo** (EXP-0167 needs a
  quiet machine; the GPU lease is a no-op shim, and EXP-0160 showed an unlocked 5-rep re-run can
  *manufacture* faults). The §6 device arm is therefore NOT run. This reinforces §4.1: `run04`'s
  5-rep adjudication never rescues a field's agreement rate.
- **2026-08-30 M3** — Stage 1/2/3 built and run (`analysis/adjudicate.py`, `verdicts.py`,
  `emit_deliverables.py`). Amendments A1-A7 frozen in `PRE_REGISTRATION.md` (five of the seven can
  only weaken a row; A3 is the only two-directional one and both versions are reported).
  `db.json` moved a second time mid-analysis (EXP-0165 landed the `sfu_marker` C7b split), so the
  snapshot was re-taken (`addf5eda…`) and everything re-derived against it — which surfaced
  **`sfu_marker.b0_hi`/`b1_hi`, two brand-new fields with NO `validation.json` entry** (a state
  `validate_labels.py` hard-fails on), one of which EXP-0146's committed data can fill.
  **13 merge-ready rows; 52 keys withheld.** `work/merge_verdicts.py --dry-run` applies all 13 with
  0 skipped and 0 problems; nothing was written.
- **2026-08-30 M4** — H3/F3 settled from EXP-0146's own raw: `iadd2.srcB_ext`'s 128 values group
  into 32 sets of four by `v>>2`, and **32/32 groups collapse to exactly one cross-run-agreeing
  observable** — the `reg<<2` register packing, reproducing EXP-0154's G17P DEF-0154-4 on M4 from
  data captured a day earlier. F3 did not fire.
- **2026-08-30 M5** — Deliverables written and verified. **12 merge-ready rows** (from 94 original
  verdicts), **53 withheld** (23 G3 veto / 11 G2 redundant / 12 unstable / 7 inert-single-carrier),
  **6 proposed db.json defects**. `work/merge_verdicts.py --dry-run` applies all 12 with 0 skipped,
  0 problems: emitter-grade 605 -> 617 fields, emittable instructions 44 -> 44 (no instruction
  flips). `db.json`/`validation.json` moved a THIRD time (`sfu_marker.b0_hi`/`b1_hi` were merged by
  the orchestrator citing EXP-0146 while I worked), so the snapshots were re-taken and my now-
  redundant `sfu_marker.b1_hi` row was correctly dropped by the G2 gate — the gate works.
  `README.md`, `RESULTS.md`, `manifest.json`, `raw/README.md` written. Verified with `git status`
  that nothing outside `experiments/EXP-0166-exp0146-recovery/` was modified and **nothing was
  committed**; `work/merge_verdicts.py` was only ever executed with `--dry-run`, which does not
  write. No device was dispatched to at any point.
