# EXP-0207 — PROGRESS

Append-only. One entry per milestone, so a kill costs at most one milestone.

## 2026-08-30 — M0: reading, before any design
- Read `experiments/SUBAGENT_BRIEF.md`, `experiments/NEO-TARGET-BRIEF.md`,
  `experiments/FIELD-SWEEP-PROTOCOL.md` (all of it: §3a–d, §5a, §5b, §7, §9), `CODEX.md`,
  `docs/evidence-classification.md`.
- Read the prior record for every one of the seven target fields:
  `tools/agx-isa/validation.json` rows, `EXP-0147` (vtx_coord_xform), `EXP-0155`/`EXP-0163`
  (frag_color_store.store_mode, iter.b9 — the eight/six inert arms), `EXP-0168`/`EXP-0172`/
  `EXP-0178`/`EXP-0189` (get_sr.form, get_sr.dst_hi), `EXP-0187` (mesh_out_src: the first
  carrier ever found), `EXP-0188` (the four fields it DECLINED before device time, with
  reasons), `EXP-0141` (dev_scoreboard_fence.scope_flag).
- Read `tools/agx-isa/wave_audit.py` — the gate these verdicts are judged by on arrival.
- Device reachable: `192.168.170.254`, macOS 26.6, python 3.9.6, clang present.

## 2026-08-30 — M1: pre-registration frozen (before any build or device time)
- `PRE_REGISTRATION.md` written first: seven fields, the dimension each one plausibly
  controls, the dimensions ALREADY spanned (so none is repeated), the per-field oracle and
  its kind, refuters, confounders, the raw schema, and the gate R1–R8.
- Selected all seven offered fields. Nothing was declined before device time; the two with
  the weakest prior odds (`dev_scoreboard_fence.scope_flag`, `vtx_coord_xform.operand`)
  carry an explicitly stated gate that can return "no", and for `scope_flag` the arm's own
  detection-power control decides whether any verdict may be filed at all.
- Authored 5 MSL files / 25 carriers, a render runner extended with the pipeline-state
  dimensions the fields need (format, blend incl. DUAL-SOURCE, depth, per-sample device
  read-back), and **a mesh render runner — the reason `mesh_out_src.sel` has never been
  dispatched by anyone: no runner in this repo could execute a spliced MESH pipeline.**
- `analysis/verdicts.py` self-test PASSES its three refusal assertions (a fault-only field
  is refused; a width-1 field with 1 move / 0 disagreements is accepted; an inert claim
  from an arm with no firing control is refused).
- `analysis/covary.py` (R8): 30 arm-fields, each with a recorded argument that the
  observable is not selected by the field under test.
- `CAPTURE_CONTRACT.json` frozen, **25 blobs**; repo revision pinned `f59821fe`.
- Nothing has run on the device yet.

## 2026-08-30 — M2: census x3, pilots x4 (all PRE-FREEZE, retained in raw/prefreeze/)
- `census01`: `interpolant<>` is FRAGMENT-ONLY (one compile error failed the whole library and
  with it all eight fragment arms); MSL declares only `memory_order_relaxed`; `mesh_wide2/3`
  emit no `mesh_out_src`. → Amendment 1.
- `census02`: neither fence carrier emits `dev_scoreboard_fence` at all (reproducing EXP-0141
  on a far stronger carrier); `mesh_wideP2` emits it with non-degenerate geometry; `f_dual`
  fuses dual-source blending into ONE store; `f_mask` emits no `frag_color_store` and does not
  tokenize. → Amendment 2 (`fen_syn`, the pre-spliced fence arm).
- `census03`: `fen_syn` resolves; `sr_dump` resolves with a dst_hi baseline of 0 against
  `sr_c`'s 1. All 30 archives built.
- `pilot01/02/03/04`: found and fixed, before any gated run — a NaN/inf in the `pixels` array
  making the response unparseable (recorded `measurement_failed`, never a hardware outcome);
  `v_sv` indexing its corner array with an unfolded `vertex_id` under `baseVertex 9`;
  a baseline-retry policy that spent four 40 s health cycles on a carrier that simply draws
  nothing. → Amendment 3 (the whole `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` adoption).

## 2026-08-30 — M3: the two gated runs
- `raw/g17p_20260830_run01` (forward) 6193 records, `run02` (reverse) 6192. **0 hangs, 0
  watchdog timeouts, 0 malformed responses, 0 ledger failures.** 11 `InnocentVictim` retried
  in place, never scored.

## 2026-08-30 — M4: the interaction capture (Amendment 4, frozen before its own dispatch)
- `raw/g17p_20260830_int01/int02`, forward and reverse. **H8 confirmed 22 of 24 predicted
  cells:** `get_sr.form` is inert at `dp_width` 0x10 on 6 of 6 arms and live at 0x14 on 5 of 5
  non-vertex arms — **and the effect follows the FIELD into carriers whose compiler chose
  0x10**, which refutes the "it is something else about sr_hi" alternative by name.

## 2026-08-30 — M5: analysis, and the cross-experiment checks
- Verdicts, answers, census, covary and `tools/agx-isa/wave_audit.py` all run and agree.
- **EXP-0204's 20:00–20:25 UTC hang window does not touch this experiment**: all four captures
  ran 19:37–19:47 UTC, **0 records inside the window** (arithmetic, in RESULTS §10.2).
- **Gate E recorded INCOMPLETE on every row** (reversed order + identical ledgers met; a quiet
  machine never available). Serialized quiet confirmation is the named next step for all seven.
- **Shadowing checked, per EXP-0204's `cubearray_coord_const` lesson**: `mesh_out_src` IS
  shadowed by the 8-byte `op04_len8` residue, keyed on **byte+2**, which is why four mesh
  carriers read "absent" — but all 256 swept values keep length 2, so the sweep is unaffected.
- **`dp_width` behaves like a bitfield, not the 4-value enum `db.json` documents** (§10.3),
  and a tempting `(dp & 0x14) == 0x14` rule is recorded as REFUTED, not adopted.
