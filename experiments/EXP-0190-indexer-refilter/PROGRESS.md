# EXP-0190 progress

- **T0** — read CLAUDE.md / CODEX.md / SUBAGENT_BRIEF.md / FIELD-SWEEP-PROTOCOL §3,§5,§7,
  EXP-0189 RESULTS + recount.py + collect_raw.py, EXP-0164 audit.py. Snapshotted
  `tools/agx-isa/{db,validation}.json` into `work/` (db sha256 2412eac1…, validation sha256
  21d006d0…). Repo revision b98b237b.
- **T1** — `PRE_REGISTRATION.md` written and frozen BEFORE any verdict: classification rule,
  frozen thresholds, restoration policy, controls C1–C6.
- **T2** — `analysis/census_underscore.py`: **96 distinct `_`-prefixed field names, 28,736
  records** across `experiments/*/raw/**/*.jsonl`.
- **T3** — `analysis/classify_underscore.py`: hand-classified all 96 with emitter citations.
  **14 FIELD-SWEEP, 1 CONTROL-SHAPED (`_detect`), 81 SCAFFOLDING.** Only 18 of the 96 have any
  group that varies its bytes, i.e. for 78 names the classification cannot change any number.
  → `analysis/underscore_fields.json`.
- **T4** — corrected indexer built as a 1-test patch of EXP-0189's `collect_raw.py`
  (`analysis/collect_raw.diff`), with `--legacy-underscore` to reproduce the old behaviour.
  **Legacy run reproduces EXP-0189's "6,592 groups → 5,910 cells" exactly.** Corrected:
  6,674 groups → 5,937 cells.
- **T5** — `analysis/verify_inheritance.py`: PASS — every verdict-producing function body and
  frozen constant in audit.py / collect_raw.py / recount.py is AST-identical to the original.
- **T6** — audits run on both indexes. Emitter-grade cohort (554): UNVERIFIABLE **14 → 12**,
  STABLE-LIVE **499 → 501**. Exactly two bucket changes, both UNVERIFIABLE → STABLE-LIVE:
  **`half_alu.dst`** (EXP-0138 `_byte0_hi`, NEW — EXP-0189 never found this one) and
  **`half_alu_ext8.dst`** (EXP-0180 `__dst_nibble`, the instance EXP-0189 found by hand).
  Withdrawn cohort (154 rows): identical under both indexes — **the refilter restores nothing.**
- **T7** — recount + restore + the cannot-fail hunt.  (in progress)
- **T7** — recount on both indexes. **C1 PASS: published rule, no withholding = 37 exactly**
  on both. Strict re-derivation: **legacy 35** (withdraws `half_alu`, `half_alu_ext8`, both on
  `field:dst`), **corrected 37** — today's headline is a fixed point once the filter is right.
- **T8** — `analysis/restore.py`: of 154 withdrawn rows, **1 restored** (`falu2i.imm_flag`,
  512 common keys / 100.00 % agreement / moved 7+7 / 0 disagreements, via the committed
  citation repair, NOT the filter), 1 blocked by EXP-0189's label ruling (`get_sr.form`),
  1 never-moved (`call.tail`), **151 stay withheld**. → 555/1040, 37/166.
- **T9** — C3 PASS (0 cells lost, 23 grew, 27 new). Unresolved groups identical (8,877) —
  no second-order discard in the label-level fallback.
- **T10** — tenth cannot-fail check found: **DEF-0190-1**, the inert buckets have no
  detection-power conjunct; **128 arms recorded exactly one distinct observation** over
  80,138 field records, so they could not return anything but "inert"; **21 INERT-* fields
  rest entirely on such arms, 5 of them emitter-grade** (`atomic_mem.{amode,base_slot,rsv3}`,
  `pop_reconverge.reserved`, `stop.reserved`) across three of the published 37 instructions.
  Its remedy (`_detect`, `__ladder_L_*`, `_live_control`) is discarded by the same filter.
  Also **DEF-0190-2** (latent): `gather()` silently disables its own gated-run filter.
- **T11** — RESULTS.md / README.md / manifest.json written. DONE. No commit made; nothing
  outside this directory written; `db.json`, `validation.json`, `docs/`, `PROVENANCE.md`,
  EXP-0164 and EXP-0189 untouched.
