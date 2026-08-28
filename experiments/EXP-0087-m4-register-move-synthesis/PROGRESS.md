# PROGRESS -- EXP-0087 (M4 register-move synthesis)

- 2026-08-27T18:00:00-07:00 -- Read CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md.
  Read tools/agx-isa/db.json's five reg_move_* descriptors + uniform_mov/
  mov_imm/mov_zext16 siblings, and docs/isa/README.md's register-file /
  device_load / device_store sections (96-GPR file, compact-move dst is a
  4-bit r0-r15 field, device_store carries no explicit source-register
  field). Built tools/shdump + tools/agxtest locally (this host is the M4
  target) into a scratch dir and ran informal (non-recorded) pilot probes:
  confirmed a 16-value constant-index carrier kernel compiles to 16 compact
  moves feeding 4 vector stores; confirmed splicing one move's `usrc` field
  (independently assembled with tools/agx-isa) changes the corresponding
  output slot to the new source's value with no other slot affected;
  confirmed the four non-`0x01`-family byte+2 values piloted all read back
  zero; confirmed dst-field retargeting on the last move redirects the
  write across all four register quads exactly as predicted from
  instruction-ordering reasoning. This pilot data (not evidence itself)
  shaped the frozen matrix.
- 2026-08-27T18:20:00-07:00 -- Created experiments/EXP-0087-m4-register-
  move-synthesis/. Wrote kernels/synth_move.metal (16-value carrier,
  frozen anchor confirmed: 124-byte _agc.main, 16 compact moves + 4 vector
  stores) and kernels/census.metal (4 compiler-emitted-move census
  kernels). Wrote harness/build.sh, baseline.py (derives + freezes the two
  probe anchors and the census), casematrix.py (49-case frozen matrix +
  predictions), run.py, verify.py, analysis.py, make_manifest.py.
- 2026-08-27T18:35:00-07:00 -- Wrote PRE_REGISTRATION.md, README.md,
  RESULTS.md (placeholder), computed and wrote CAPTURE_CONTRACT.json.
  Next: pass verify.py --selftest/--seqtest, make_manifest --write/--check,
  verify.py --preflight, then the two gated captures.
- 2026-08-27T18:45:00-07:00 -- Host was rebooted (unrelated) and this
  session was interrupted after run01 completed. Resumed: re-orient from
  disk confirmed raw/m4-20260827-run01/ is complete and closed (49 result
  lines, 47 OK / 2 CMDBUF_ERROR, matching the frozen MOVE-05 fault
  predictions). Removed the leftover empty work/ dir. Re-ran the contracted
  pre-second-run sequence (verify.py --selftest [20/20 PASS], --seqtest
  [14/14 PASS], make_manifest.py --check [OK], verify.py --between-runs
  [PASS]) -- run01 is a valid closed run, run02 authorized. Did NOT touch
  or repeat run01. Proceeding to run02 under its own id.
- 2026-08-27T18:45:30-07:00 -- (session interrupted here by a terminal-
  emulator issue on the user's side, twice; both times resumed cleanly from
  disk per this log, per the coordinator's instructions -- see the two
  entries above and below for what was re-verified before continuing each
  time. No run id was ever reused or repeated.)
- 2026-08-27T18:55:00-07:00 -- Ran the RUN02_PRESENT sequence:
  `analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02 --write`
  CRASHED (TypeError in `classify()` on case `move02_bit2_od0c`, whose
  frozen `pred={"out0":"corrupt_out8"}` is a string the function did not
  handle). `analysis.py` is hash-frozen (AUTH_CODE, already burned into
  both closed runs' `00_inputs.json` and into `CAPTURE_CONTRACT.json`) --
  per standing rule, NOT repaired post-capture. Wrote `QUARANTINE.md`
  scoping the defect precisely (the raw captures are NOT affected) and
  naming EXP-0088 as successor for a corrected `analysis.py` (no GPU
  recapture needed -- it can run directly against this experiment's already-
  closed raw/ data). Independently confirmed, by direct diff of the two
  closed runs' `04_results.jsonl`, that 47/49 cases are byte-for-byte
  identical across both runs and exactly 2 (`move01_b2_26`,
  `move05_byte2_0f`) differ (CMDBUF_ERROR in run01, STATUS OK reading an
  all-zero output in run02) -- a genuine hardware nondeterminism finding on
  those two specific undocumented/boundary byte+2 encodings, also recorded
  in QUARANTINE.md, not a file defect.
- 2026-08-27T19:05:00-07:00 -- Produced the full 49-case classification via
  an uncommitted scratch script (not part of this experiment's hash-frozen
  tree) reading `raw/m4-20260827-run01/04_results.jsonl` directly with a
  corrected version of `classify()`'s logic. Cross-checked against the raw
  JSONL and against `raw/m4-20260827-run01/06_baseline.json`'s census.
  Wrote the full RESULTS.md: compiler census (item 1), per-category
  synthesis verdicts WORKS / silent-zero / CORRUPTS / FAULT / nondeterministic
  / ambiguous (item 2), THE RULE plus five precisely-scoped open unknowns
  U1-U5 (item 3, cross-referencing sibling EXP-0086 for the liveness-bit
  question rather than duplicating it), the corrected five-into-one
  descriptor proposal (item 4), and an explicit DRV-ISA-01 generate-vs-
  decode verdict (yes, under a narrow stated constraint).
- 2026-08-27T19:10:00-07:00 -- Regenerated manifest.json (`make_manifest.py
  --write`), confirmed `--check` passes. Ran `verify.py --captured` to
  record its exact failure for the log (expected to fail per QUARANTINE.md:
  no analysis.json + 2-row cross-run mismatch) -- did not edit any gate or
  hash-frozen file to force it to pass. Reporting to the user now.
- 2026-08-27T19:15:00-07:00 -- Appended the exact `verify.py --captured`
  failure transcript to QUARANTINE.md for the record, then did a final
  `make_manifest.py --write` (manifest.json is a pure hash-tracking file,
  not gate-frozen itself, so keeping it current is always safe). Final
  state: raw/ both runs closed and valid; QUARANTINE.md scopes the one
  blocked gate precisely; RESULTS.md carries the full findings. Reporting
  to coordinator.
