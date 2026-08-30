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
