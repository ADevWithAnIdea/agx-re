# PROGRESS — EXP-0162

| when (UTC-ish) | milestone | state |
|---|---|---|
| 2026-08-29 | neo reachable, toolchain built (`shdump`, `shdump2`, `rendersweep`, `agxrun_persist`) under `~/agxre/EXP-0162/work/bin` | DONE |
| 2026-08-29 | desk corpus scan (`analysis/corpus_scan.py`, `analysis/scan57.py`) over the committed own-MSL corpus | DONE |
| 2026-08-29 | locate-only pilot on G17P — all 12 carriers compile, every anchor reproduces its M4 bytes | DONE (`work/pilot_locate.json`) |
| 2026-08-29 | `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` frozen | DONE |
| 2026-08-29 | run01 (compute): `cvt_bf16` 1816 cases / `cvt_f2h_dst` 1304 / `packed_half2_hi` 1304, **0 hangs**, all baselines OK | DONE, pulled back |
| 2026-08-29 | **bf16 numeric result measured on G17P**: RNE fits 30/31 vectors; TIES_DOWN, TRUNC, RNA each refuted by named tie vectors; f32 input denormals FLUSH TO ZERO | DONE |
| 2026-08-29 | `packed_half2_hi` synthesis executes: HIGH lane = correct packed-half2 product, LOW lane written as ZERO — EXP-0144's withdrawn finding re-established | DONE |
| 2026-08-29 | run02 (render) aborted at baseline — six sibling agents' GPU experiments; retained unused, never reused | RETAINED |
| 2026-08-29 | `NEO-TARGET-BRIEF.md` updated on disk mid-run: **the GPU lease has been removed**; run03 (queued behind it) killed and never captured | NOTED |
| 2026-08-29 | run04 (render) `rog`: 2048 cases, 0 hangs, 22/22 baselines OK — full G17P `pixel_order` legal sets + 24 cross-form probes | DONE, pulled back |
| 2026-08-29 | run04 `kill`/`vary` stopped early at 2 hangs (protocol §8); runner given a per-(target,byte) hang cap and re-launched as run05 | DONE |
| 2026-08-29 | A/B of both proposed `db.json` changes against COPIES: roundtrip 302 OK / 0 FAIL, corpus 832→833 clean, 388872→388604 leftover | DONE |
| 2026-08-30 | run05 (render) `kill` 1128 cases / `vary` 298 cases with the per-(target,byte) hang cap; both detection-power controls passed | DONE, pulled back |
| 2026-08-30 | `analysis/field_verdicts.json` (37 entries: 33 `hardware-run`, 2 `isolated-byte-diff`, 2 `untested`) | DONE |
| 2026-08-30 | `analysis/proposed_db_changes.json` — P1 `pixel_order` (settled), P2 `vary_store` (settled), P3 `cvt_bf16` match (still blocked on db defect 28) | DONE |
| 2026-08-30 | `RESULTS.md`, `README.md`, `manifest.json` written; nothing committed (orchestrator owns commits) | DONE |
