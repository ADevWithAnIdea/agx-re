# EXP-0193 — PROGRESS

- **2026-08-30 — M0 frozen.** `PRE_REGISTRATION.md` committed to disk at repo revision
  `7286bf04c500f726fbe3bf096a166e90b6a34e0f` (tree clean). Criterion is EXP-0192 §4.2,
  **inherited unchanged**, consumed by import. Population sized: 337 STABLE-LIVE arms
  (matches EXP-0191's committed 337), 503 distinct fields, 23 experiments. Control R1
  expectation (`call.b5` → Case A, V = 3, 4, 2) recorded BEFORE running, with an explicit
  STOP condition. Baseline: 546/1040 emitter-grade, 33/166 emittable, validate_labels rc=0.
- **2026-08-30 — M1 run01 complete, rc=0, 7.6 s.** `analysis/population_audit.py` (thin driver,
  imports EXP-0192's `classify_row` unmodified) scored all **503** fields of the **337**-arm
  STABLE-LIVE population. **R1 control PASSED: `call.b5` = Case A with V = 3, 4, 2** on the three
  expected arms, all five per-arm counters matching EXP-0192's committed table. **R2 PASSED**: all
  four EXP-0192 rows re-derived to their committed cases. R4: 0 unverifiable.
  **Result: 497 Case A, 0 Case B, 6 Case C** — the 3 already withheld plus **3 NEW**:
  `frag_color_pack.fmt_class`, `ray_move_copy6.optype`, `vtx_coord_xform.operand`.
  `analysis/population_audit.json` + `analysis/reclassify.json` written.
- **2026-08-30 — M2 evidence read-back.** Pulled the raw records behind the three new Case-C rows
  (read-only; `raw/` untouched). `frag_color_pack.fmt_class`: **all 512 records share one
  `observed` payload**; the 2 moved cells are `undecodable` at value 86, note *"re-decodes as
  pack_convert"*, with `status: OK` and the sentinel written — a **tokenizer** disagreement, not a
  hardware event. `ray_move_copy6.optype`: 382 `ok` sharing one payload, 128 `fault`.
  `vtx_coord_xform.operand`: 1642 `ok` sharing one pixel matrix, 987 `no_draw` SENTINEL_MISS,
  39 `fault`. Instruction-level impact confirmed: only `vtx_coord_xform` loses emittability.
- **2026-08-30 — M3 run02 = run01 byte-identical.** `sys.dont_write_bytecode` added to the driver
  after run01 left a `__pycache__` in EXP-0191/0192's analysis dirs; those were removed and the
  re-run created none. Verified after the run: every frozen input hash unchanged, `git status`
  shows only `experiments/EXP-0193-stable-live-sweep/`.
- **2026-08-30 — M4 COMPLETE.** `README.md`, `RESULTS.md`, `manifest.json` written.
  **497 Case A · 0 Case B · 6 Case C · 0 unverifiable.** Honest number:
  **32 of 166 emittable, 543 of 1040 emitter-grade fields** (from 33 / 546). No label edited,
  nothing committed.
