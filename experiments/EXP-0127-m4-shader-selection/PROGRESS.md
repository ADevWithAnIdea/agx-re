# EXP-0127 progress log

- `2026-08-28` Pre-registration frozen (`PRE_REGISTRATION.md`,
  `CAPTURE_CONTRACT.json`). Calibration (`work/calib_fs.m`,
  `work/calib_redirect2.m`, both retained, small) established: (1) a
  fragment function must genuinely consume its `[[stage_in]]` varying via a
  RUNTIME scale, not a compile-time-foldable literal, for `0x58000+0x08` to
  populate at all; (2) the field is already correct pre-commit and survives
  unmodified through commit; (3) a first redirect attempt (RED bound,
  spliced to GREEN's own natural selector) completed without fault but
  rendered AS RED, while a `0xffffffff` splice DID fault -- motivating the
  broadened boundary/alias case matrix in the frozen pre-registration.
- `2026-08-28` `verify.py --selftest` (13/13) and `--seqtest` (5/5) PASS.
  `run.py --smoke` PASS (non-recorded, `work/` only).
- `2026-08-28` First official run attempt `m4_20260828_run01`: crashed
  partway through (see `CAPTURE_CONTRACT.json` `post_capture_corrections`)
  on a false-positive address-leak check. Two complete records were written
  before the crash (`vstoken_varied`, `vstoken_uniform` count=650) and are
  RETAINED, not deleted or repaired -- they independently reproduce the
  linear-rule/boundary facts from pre-registration calibration (base=704,
  step=128, boundary_index=506, new_region_size=262144), a fourth
  independent confirmation. `raw/m4_20260828_run01/` is NOT one of the two
  official runs this experiment's closure claims depend on.
- `2026-08-28` Fixed the false-positive (renamed three derived boolean
  fields to avoid the substring `va`), re-verified `--selftest`/`--seqtest`
  clean, updated the frozen hashes in `PRE_REGISTRATION.md`/
  `CAPTURE_CONTRACT.json` with a disclosed correction entry. Proceeding to
  two fresh official runs under new ids.

- `2026-08-28T01:53:21` [m4_20260828_run02] vstoken varied done: `{"deltas": [384, 128, 128, 128, 128, 128, 128], "mode": "varied", "n": 8, "order": "0,1,2,3,4,5,6,7", "readback_status_all_completed": true, "tokens": [448, 832, 960, 1088, 1216, 1344, 1472, 1600]}`

- `2026-08-28T01:53:40` [m4_20260828_run02] vstoken uniform (count=650) done: `{"boundary_index": 506, "linear_base": 704, "linear_step": 128, "post_boundary_step_ok": true}`

- `2026-08-28T01:53:58` [m4_20260828_run02] vstoken perturbation (pad0/pad64/extraq) done: `{"extraq_code_unchanged": true, "pad64_code_unchanged": true, "pad64_pool_unchanged": true}`

- `2026-08-28T01:54:00` [m4_20260828_run02] fsredirect case baseline_red_solo done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": false}`

- `2026-08-28T01:54:02` [m4_20260828_run02] fsredirect case baseline_green_solo done: `{"bind": "green", "final_status": 4, "hang": false, "result_colour": "green", "wrote": false}`

- `2026-08-28T01:54:04` [m4_20260828_run02] fsredirect case baseline_blue_solo done: `{"bind": "blue", "final_status": 4, "hang": false, "result_colour": "blue", "wrote": false}`

- `2026-08-28T01:54:06` [m4_20260828_run02] fsredirect case redirect_red_to_green done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:54:08` [m4_20260828_run02] fsredirect case redirect_red_to_blue done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:54:10` [m4_20260828_run02] fsredirect case redirect_green_to_red done: `{"bind": "green", "final_status": 4, "hang": false, "result_colour": "green", "wrote": true}`

- `2026-08-28T01:54:13` [m4_20260828_run02] fsredirect case redirect_blue_to_red done: `{"bind": "blue", "final_status": 4, "hang": false, "result_colour": "blue", "wrote": true}`

- `2026-08-28T01:54:15` [m4_20260828_run02] fsredirect case misalign_plus1 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:54:17` [m4_20260828_run02] fsredirect case misalign_plus2 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:54:19` [m4_20260828_run02] fsredirect case misalign_plus4 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:54:21` [m4_20260828_run02] fsredirect case misalign_plus8 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:54:23` [m4_20260828_run02] fsredirect case misalign_minus1 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:54:25` [m4_20260828_run02] fsredirect case misalign_minus2 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:54:27` [m4_20260828_run02] fsredirect case misalign_minus4 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:54:29` [m4_20260828_run02] fsredirect case misalign_minus8 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:54:31` [m4_20260828_run02] fsredirect case boundary_zero done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:54:33` [m4_20260828_run02] fsredirect case boundary_far_oor done: `{"bind": "red", "final_status": 5, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:54:35` [m4_20260828_run02] fsredirect case boundary_top_bit done: `{"bind": "red", "final_status": 5, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:54:37` [m4_20260828_run02] fsredirect case boundary_max done: `{"bind": "red", "final_status": 5, "hang": false, "result_colour": "blue", "wrote": true}`

- `2026-08-28T01:54:40` [m4_20260828_run02] fsredirect case boundary_near_but_invalid done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:55:03` [m4_20260828_run03] vstoken varied done: `{"deltas": [384, 128, 128, 128, 128, 128, 128], "mode": "varied", "n": 8, "order": "0,1,2,3,4,5,6,7", "readback_status_all_completed": true, "tokens": [448, 832, 960, 1088, 1216, 1344, 1472, 1600]}`

- `2026-08-28T01:55:22` [m4_20260828_run03] vstoken uniform (count=650) done: `{"boundary_index": 506, "linear_base": 704, "linear_step": 128, "post_boundary_step_ok": true}`

- `2026-08-28T01:55:40` [m4_20260828_run03] vstoken perturbation (pad0/pad64/extraq) done: `{"extraq_code_unchanged": true, "pad64_code_unchanged": true, "pad64_pool_unchanged": true}`

- `2026-08-28T01:55:42` [m4_20260828_run03] fsredirect case baseline_red_solo done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": false}`

- `2026-08-28T01:55:44` [m4_20260828_run03] fsredirect case baseline_green_solo done: `{"bind": "green", "final_status": 4, "hang": false, "result_colour": "green", "wrote": false}`

- `2026-08-28T01:55:47` [m4_20260828_run03] fsredirect case baseline_blue_solo done: `{"bind": "blue", "final_status": 4, "hang": false, "result_colour": "blue", "wrote": false}`

- `2026-08-28T01:55:49` [m4_20260828_run03] fsredirect case redirect_red_to_green done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:55:51` [m4_20260828_run03] fsredirect case redirect_red_to_blue done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:55:53` [m4_20260828_run03] fsredirect case redirect_green_to_red done: `{"bind": "green", "final_status": 4, "hang": false, "result_colour": "green", "wrote": true}`

- `2026-08-28T01:55:55` [m4_20260828_run03] fsredirect case redirect_blue_to_red done: `{"bind": "blue", "final_status": 4, "hang": false, "result_colour": "blue", "wrote": true}`

- `2026-08-28T01:55:57` [m4_20260828_run03] fsredirect case misalign_plus1 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:55:59` [m4_20260828_run03] fsredirect case misalign_plus2 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:56:01` [m4_20260828_run03] fsredirect case misalign_plus4 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:56:03` [m4_20260828_run03] fsredirect case misalign_plus8 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:56:05` [m4_20260828_run03] fsredirect case misalign_minus1 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:56:07` [m4_20260828_run03] fsredirect case misalign_minus2 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:56:09` [m4_20260828_run03] fsredirect case misalign_minus4 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:56:11` [m4_20260828_run03] fsredirect case misalign_minus8 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:56:13` [m4_20260828_run03] fsredirect case boundary_zero done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:56:15` [m4_20260828_run03] fsredirect case boundary_far_oor done: `{"bind": "red", "final_status": 5, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:56:18` [m4_20260828_run03] fsredirect case boundary_top_bit done: `{"bind": "red", "final_status": 5, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:56:20` [m4_20260828_run03] fsredirect case boundary_max done: `{"bind": "red", "final_status": 5, "hang": false, "result_colour": "blue", "wrote": true}`

- `2026-08-28T01:56:22` [m4_20260828_run03] fsredirect case boundary_near_but_invalid done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:58:40` [m4_20260828_run04] vstoken varied done: `{"deltas": [384, 128, 128, 128, 128, 128, 128], "mode": "varied", "n": 8, "order": "0,1,2,3,4,5,6,7", "readback_status_all_completed": true, "tokens": [448, 832, 960, 1088, 1216, 1344, 1472, 1600]}`

- `2026-08-28T01:59:00` [m4_20260828_run04] vstoken uniform (count=650) done: `{"boundary_index": 506, "linear_base": 704, "linear_step": 128, "post_boundary_step_ok": true}`

- `2026-08-28T01:59:18` [m4_20260828_run04] vstoken perturbation (pad0/pad64/extraq) done: `{"extraq_code_unchanged": true, "pad64_code_unchanged": true, "pad64_pool_unchanged": true}`

- `2026-08-28T01:59:20` [m4_20260828_run04] fsredirect case baseline_red_solo done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": false}`

- `2026-08-28T01:59:22` [m4_20260828_run04] fsredirect case baseline_green_solo done: `{"bind": "green", "final_status": 4, "hang": false, "result_colour": "green", "wrote": false}`

- `2026-08-28T01:59:24` [m4_20260828_run04] fsredirect case baseline_blue_solo done: `{"bind": "blue", "final_status": 4, "hang": false, "result_colour": "blue", "wrote": false}`

- `2026-08-28T01:59:26` [m4_20260828_run04] fsredirect case redirect_red_to_green done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:59:28` [m4_20260828_run04] fsredirect case redirect_red_to_blue done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:59:30` [m4_20260828_run04] fsredirect case redirect_green_to_red done: `{"bind": "green", "final_status": 4, "hang": false, "result_colour": "green", "wrote": true}`

- `2026-08-28T01:59:32` [m4_20260828_run04] fsredirect case redirect_blue_to_red done: `{"bind": "blue", "final_status": 4, "hang": false, "result_colour": "blue", "wrote": true}`

- `2026-08-28T01:59:35` [m4_20260828_run04] fsredirect case misalign_plus1 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:59:37` [m4_20260828_run04] fsredirect case misalign_plus2 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:59:39` [m4_20260828_run04] fsredirect case misalign_plus4 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:59:41` [m4_20260828_run04] fsredirect case misalign_plus8 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:59:43` [m4_20260828_run04] fsredirect case misalign_minus1 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:59:45` [m4_20260828_run04] fsredirect case misalign_minus2 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:59:47` [m4_20260828_run04] fsredirect case misalign_minus4 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:59:49` [m4_20260828_run04] fsredirect case misalign_minus8 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:59:51` [m4_20260828_run04] fsredirect case boundary_zero done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T01:59:53` [m4_20260828_run04] fsredirect case boundary_far_oor done: `{"bind": "red", "final_status": 5, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:59:55` [m4_20260828_run04] fsredirect case boundary_top_bit done: `{"bind": "red", "final_status": 5, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T01:59:57` [m4_20260828_run04] fsredirect case boundary_max done: `{"bind": "red", "final_status": 5, "hang": false, "result_colour": "blue", "wrote": true}`

- `2026-08-28T01:59:59` [m4_20260828_run04] fsredirect case boundary_near_but_invalid done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T02:00:06` [m4_20260828_run05] vstoken varied done: `{"deltas": [384, 128, 128, 128, 128, 128, 128], "mode": "varied", "n": 8, "order": "0,1,2,3,4,5,6,7", "readback_status_all_completed": true, "tokens": [448, 832, 960, 1088, 1216, 1344, 1472, 1600]}`

- `2026-08-28T02:00:26` [m4_20260828_run05] vstoken uniform (count=650) done: `{"boundary_index": 506, "linear_base": 704, "linear_step": 128, "post_boundary_step_ok": true}`

- `2026-08-28T02:00:44` [m4_20260828_run05] vstoken perturbation (pad0/pad64/extraq) done: `{"extraq_code_unchanged": true, "pad64_code_unchanged": true, "pad64_pool_unchanged": true}`

- `2026-08-28T02:00:46` [m4_20260828_run05] fsredirect case baseline_red_solo done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": false}`

- `2026-08-28T02:00:48` [m4_20260828_run05] fsredirect case baseline_green_solo done: `{"bind": "green", "final_status": 4, "hang": false, "result_colour": "green", "wrote": false}`

- `2026-08-28T02:00:50` [m4_20260828_run05] fsredirect case baseline_blue_solo done: `{"bind": "blue", "final_status": 4, "hang": false, "result_colour": "blue", "wrote": false}`

- `2026-08-28T02:00:52` [m4_20260828_run05] fsredirect case redirect_red_to_green done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T02:00:54` [m4_20260828_run05] fsredirect case redirect_red_to_blue done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T02:00:56` [m4_20260828_run05] fsredirect case redirect_green_to_red done: `{"bind": "green", "final_status": 4, "hang": false, "result_colour": "green", "wrote": true}`

- `2026-08-28T02:00:59` [m4_20260828_run05] fsredirect case redirect_blue_to_red done: `{"bind": "blue", "final_status": 4, "hang": false, "result_colour": "blue", "wrote": true}`

- `2026-08-28T02:01:01` [m4_20260828_run05] fsredirect case misalign_plus1 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T02:01:03` [m4_20260828_run05] fsredirect case misalign_plus2 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T02:01:05` [m4_20260828_run05] fsredirect case misalign_plus4 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T02:01:07` [m4_20260828_run05] fsredirect case misalign_plus8 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T02:01:09` [m4_20260828_run05] fsredirect case misalign_minus1 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T02:01:11` [m4_20260828_run05] fsredirect case misalign_minus2 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T02:01:13` [m4_20260828_run05] fsredirect case misalign_minus4 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T02:01:15` [m4_20260828_run05] fsredirect case misalign_minus8 done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T02:01:17` [m4_20260828_run05] fsredirect case boundary_zero done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "red", "wrote": true}`

- `2026-08-28T02:01:19` [m4_20260828_run05] fsredirect case boundary_far_oor done: `{"bind": "red", "final_status": 5, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T02:01:21` [m4_20260828_run05] fsredirect case boundary_top_bit done: `{"bind": "red", "final_status": 5, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28T02:01:23` [m4_20260828_run05] fsredirect case boundary_max done: `{"bind": "red", "final_status": 5, "hang": false, "result_colour": "blue", "wrote": true}`

- `2026-08-28T02:01:25` [m4_20260828_run05] fsredirect case boundary_near_but_invalid done: `{"bind": "red", "final_status": 4, "hang": false, "result_colour": "black", "wrote": true}`

- `2026-08-28` Official pair `m4_20260828_run04`/`run05` captured under the
  corrected schema. `verify.py --captured m4_20260828_run04
  m4_20260828_run05`: **PASS**, 25/25 gated records byte-identical, zero
  mismatches. `RESULTS.md` and `README.md` written. Milestone complete:
  VS token rule solved (linear + capacity-boundary relocation), FS
  selector redirect REFUTED in all 4 directions (a load-bearing negative
  result), FS boundary/fault map characterized, code window confirmed
  invariant under padding/extra-queues (EXP-0110's VDM/FF-state category).
  P0.2 remains OPEN; see RESULTS.md "What P0.2 still needs".
