# EXP-0170 — PROGRESS

Append-only. Timestamps are local (M4 repo host).

- **2026-08-30 M0** — dispatch received. Read `CLAUDE.md`, `CODEX.md`,
  `experiments/SUBAGENT_BRIEF.md`, `experiments/FIELD-SWEEP-PROTOCOL.md`,
  `docs/evidence-classification.md`, `tools/agx-isa/isadb.py::assemble()`,
  `work/merge_verdicts.py`, `experiments/EXP-0164-inert-audit/analysis/collect_raw.py`,
  `experiments/EXP-0166-exp0146-recovery/RESULTS.md`. Repo rev `4b16d0b4`,
  `db.json` sha256 `07ad894d…`, `validation.json` sha256 `1fd62e55…`.
  Schema survey of `experiments/*/raw/**/*.jsonl` done (610 files; record shape
  varies per experiment — `bytes`/`value`/`field`/`instr`/`carrier`/`arm` are the
  common columns). **NO device work in this experiment; nothing was dispatched.**
- next: freeze `PRE_REGISTRATION.md` before any verdict is computed.
- **2026-08-30 M0b** — coordinator amendment received *before* any verdict was computed:
  extend scope with **Arm C**, a general audit of the *disassemble → re-assemble → compare*
  self-check idiom (symmetric-defect blind spot), reported separately from the coverage
  numbers. EXP-0167 owns the EXP-0158-specific ledger check; this experiment takes the
  general "who else shares the blind spot" question only. Folded into the pre-registration
  below before freezing.
- **2026-08-30 M1** — `PRE_REGISTRATION.md` frozen (three arms A/B/C, thresholds fixed).
  `db.json` and `validation.json` snapshotted into `work/`. No verdict computed yet.
- **2026-08-30 M2** — Arm A complete (`analysis/static_overlap.py` → `static_overlap.json`).
  **H1 CONFIRMED, F1 did not fire: 53 fields over 42 instructions overlap their own
  descriptor's `match`.** H2 CONFIRMED, F2 did not fire: the closed form
  `2^(w−popcount(match∩span))` reproduces all six of EXP-0166's tabulated numbers exactly.
  Reachable-fraction histogram 1/2:21, 1/4:18, 1/8:7, 1/16:3, 1/32:4. One field
  (`falu2_uni.uni_mode`) is fully pinned — 1 of its 2 encodings reachable. Zero field↔field
  span overlaps. **28 of the 53 are currently emitter-grade.**
- **2026-08-30 M3** — Arm B indexer complete (`analysis/coverage_index.py`): 4,677,940 raw
  lines parsed, 771,793 per-value field records, 0 unparseable; 4,354 sweep groups, 3,618
  informative, 5 degenerate, **37 collapsed groups in 4 experiments** (EXP-0138, EXP-0139,
  EXP-0146, EXP-0147). First classification pass: 617 emitter-grade fields → 435 FULL-RANGE,
  8 UNDER-COVERED, 174 UNKNOWN. **F3 FIRED (<25 UNDER-COVERED).**
- next: add per-field span unions + a dedicated audit of all 53 overlapping fields against
  observed span coverage, then Arm C.
- **2026-08-30 M4** — Arm C complete (`analysis/roundtrip_idiom.py` → `roundtrip_idiom.json`,
  160 hits over 1,419 python files; `analysis/roundtrip_blindspot.py` →
  `roundtrip_blindspot.json`). **H6 CONFIRMED, F6 did not fire.** Decisive: the PRE-fix
  OR-only `assemble()` was re-implemented locally and `tools/agx-isa/roundtrip_test.py`
  re-run against it — **test (A) `asm(disasm(b))==b`: 173 cases, 0 failures. Test (B)
  `disasm(asm(fields))==fields`: 37 cases, 0 failures, 9 of them touching one of the 53
  overlapping fields, 0 that would have caught it.** The suite is not merely
  theoretically blind; it demonstrably passes with the broken assembler.
- **2026-08-30 M5** — session-limit restart. Re-oriented from committed files (not memory).
  Coordinator adds **Scope 3 / Arm D**: EXP-0164's run-selection and placeholder handling.
  Arm D is NOT in the frozen §3, so it goes in as a dated **AMENDMENT with its own
  pre-registered thresholds, written before any Arm D number is computed.**
- **2026-08-30 M6** — Arm D complete. `work/collect_raw_D.py` (EXP-0164 `collect_raw.py`
  + D.2 only, 47 changed lines), `analysis/run_eligibility.py`, `analysis/rescore_D.py`
  (imports EXP-0164's `cross_run`/`stable_live`/`classify` **verbatim**, asserts
  MIN_COMMON/MIN_AGREE_PCT/MOVED_OVER_DISAGREE unchanged). Re-indexed 4,719,822 raw lines.
  **Placeholder signature found and it is corpus-wide: `validity:"skipped_after_hangs"`
  with `outcome:"hang"`, `attempts:[]`, `observed:null`, `status:"SKIPPED"` — 24,100 of the
  corpus's 24,201 `hang` records are never-dispatched placeholders.**
  266 withheld fields re-scored: **AGREES 253, STILL-WITHHELD-OTHER-REASON 11,
  WRONGLY-WITHDRAWN 2.** **F7 FIRED (<10) — the defect is NARROW.**
  **F9 FIRED** — not confined to EXP-0144: EXP-0138 `run02` and EXP-0140 `run01` are also
  implicated. **F10 FIRED** — 0 withheld cells used the `gating_fallback` path.
  **F8 PARTIALLY FIRED** — 2 of the dispatch's 4 re-scores reproduce exactly, 2 do not;
  my numbers stand per the pre-registered rule. 0 of the 266 have a span that moved since
  EXP-0164's db snapshot, so `merge_verdicts.py`'s DEF-0166-2 guard blocks none of them.
  Own-instrument bug found and fixed mid-arm (`INERT_SINGLE` vs `INERT-SINGLE` never
  compared equal, inflating STILL-WITHHELD from 11 to 92); recorded rather than hidden.
- next: `analysis/wrongly_withdrawn.json`, `analysis/roundtrip_blindness.md`, RESULTS.md,
  manifest.json, README.md.
- **2026-08-30 M7** — `analysis/wrongly_withdrawn.json` (13 rows, `mergeable:false`) and
  `analysis/roundtrip_blindness.md` written. Arm C's census resolved by hand: **28 files
  carry `def assert_round_trip`, 7 textually distinct bodies, all semantically identical
  and all symmetric** — `assemble(mnemonic, disassemble(buf).fields) == buf`, with no
  parameter through which a caller's intended value could enter. Confirmed 0 of the 13
  fields has a span that moved in the CURRENT `db.json` either (sha `322847…`; db.json,
  validation.json and isadb.py have ALL moved since my 01:25 freeze — noted as drift).
- next: RESULTS.md, manifest.json, README.md.
- **2026-08-30 M8** — `RESULTS.md`, `manifest.json`, `README.md` complete. §6 rewritten
  after checking the in-flight G17P experiments' OWN pre-registered device scope rather
  than guessing: **`EXP-0168-g17p-dst-resweep` already owns 4 of the 13 rows**
  (`cvt_f2h.op`, `cvt_f2i.dst`, `pack_convert.b7`, `unpack_convert.dst` — its
  `PRE_REGISTRATION.md:52-54`, and its :363 already cites EXP-0144's `pack_convert.b7`
  placeholders), and `EXP-0169` owns the UNVERIFIABLE 144 plus `falu2_uni.uni_mode` and
  `reg_move_cb.form`. **`falu2.srcA_class`/`srcB_class` are in NEITHER scope**, so they are
  the only rows where an M4 ruling is both available and not about to be superseded.
  Recommendation set to DEFER on the 4, RESTORE-CANDIDATE on the 2, policy-call on the 7.
  **EXPERIMENT COMPLETE.** No commit made (per dispatch). Nothing merged.
- **2026-08-30 M9** — full reproduction chain re-run end-to-end; every headline stable.
  Two harmless live-corpus drifts noted: `run_eligibility.py` now sees **469 runs / 51
  ineligible** (was 467/49) because a concurrent agent added `EXP-0169/raw/pilot02`,
  `pilot03`, which E3's `NONGATED` regex correctly excludes; and
  `roundtrip_blindspot.py` re-run against the CURRENT `isadb.py` (`9cda47a1…`, moved since
  my pin) returns the **same** Q1/Q2/Q3 verdicts, so Arm C's conclusion is not
  snapshot-dependent. Arm D verdicts unchanged: **253 / 11 / 2**.
