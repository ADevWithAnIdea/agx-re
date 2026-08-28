# EXP-0116 progress log

- 2026-08-28T (calibration, informal, not evidence): built `work/calib0.m`
  (deleted before freeze) to prove iotrace's BODUMP `cpu=` field is literally
  `MTLBuffer.contents` for that BO -- confirmed byte-for-byte
  (`contents_ptr=0x106c14000` == `cpu=0x106c14...` in the dump filename),
  meaning it is a directly writable pointer in this process's own address
  space.
- 2026-08-28T (calibration): built `harness/linksplice.m` with an initial
  two-command-buffer design (`cbR`/`cbM`). Two failure modes discovered and
  worked through, both recorded here rather than silently fixed:
  1. First attempt committed+waited `cbR` before encoding `cbM`; the
     resulting dump showed R0/R1 completely absent and `cbM`'s own chain
     landing at what looked suspiciously like recycled addresses. Root
     cause confirmed (not assumed) by rerunning cleanly: waiting for a
     command buffer's completion lets Metal reuse (WITHOUT zeroing) its
     0x8000-byte segment storage for the next command buffer's own
     allocations -- observed directly as a "chain" whose two segments
     mutually link to each other (a genuine A0/A1 <-> R0/R1 alias), and as
     a spurious 732-record run built from 1 fresh record + 731 stale
     leftover records from the previous occupant, all still matching our
     authored signature. This is a genuine process/method finding (BOs are
     not cleared on reuse) but NOT reusable as a clean redirect target, so
     `committed_wait` is not used for the frozen case matrix; only its
     genuinely uncommitted sibling and the same_cb design are.
  2. A pure "never commit cbR" design instead FAULTED
     (`kIOGPUCommandBufferCallbackErrorPageFault`) when `cbM`'s spliced link
     was redirected into it -- both A0's own 732 dispatches AND the redirect
     target failed to produce any output (readback stuck at sentinel),
     while the command buffer reported a genuine, CONTAINED hardware page
     fault (no hang, no host issue, next process ran normally). Leading
     interpretation: GPU-side residency for a command buffer's referenced
     memory is established around commit/schedule time; an uncommitted
     command buffer's own segments were simply never told to the GPU, so a
     hand-built link reaching into them reaches memory the GPU does not
     have mapped for this submission, distinct from the memory being
     invalid or the byte content being wrong. Retained as the ONE
     documented `cross_cb_uncommitted` negative in the frozen matrix
     (mechanism=`cross_cb`), not discarded.
- 2026-08-28T (calibration, method fix): also found and fixed a content-
  based-classification bug: because seg0 (`cbM`'s own head) and R0 (`cbR`'s
  head) are byte-identical at the level the scanner reads (same authored
  grid/tg signature), a greedy "first 732-count linked segment found"
  classifier picked whichever `readdir()` happened to return first --
  WRONG in at least one run (confirmed by cross-checking record counts:
  the mislabelled "A1" showed 5 records, R1's true shape, not 1). Fixed by
  finding the unique chain HEAD structurally (a link source that is nobody
  else's link target) and following links forward from there, never by
  address order or file-listing order. This fix is now the same
  disambiguation logic used throughout `linksplice.m` and `codeswap.m`.
- 2026-08-28T (redesign): replaced the two-command-buffer approach for the
  MAIN case matrix with the single-command-buffer `same_cb` mechanism
  (seg0/seg1/seg2, 732/732/36 records, reproducing EXP-0110's own validated
  natural chain shape exactly, writing to two separate buffers so an
  intermediate segment's non-execution is directly observable). This avoids
  BOTH problems above: nothing is ever completed-and-reused mid-experiment,
  and every candidate splice target is part of the SAME not-yet-committed
  command buffer, so residency is never independently in question.
  Validated over 3+ repeated `baseline_check` runs: natural chain
  (732/732/36) and correct final readback every time.
- 2026-08-28T (finding, not a bug): `same_cb`'s own leaf segment (`seg2`)
  reads its OWN tail word as `0x00000000` in a PRE-COMMIT dump and only as
  the real terminator `0x40000000` in a POST-COMMIT dump of the identical
  BO. Confirmed by direct hex inspection of both the live process's
  in-memory read and the saved `.hex` file at the exact same offset (both
  agree: 0 pre-commit, 0x40000000 post-commit). Interpretation: Metal
  defers finalizing the LAST segment's terminator sentinel to commit/
  schedule time, unlike an intermediate segment's forward LINK word (which
  this experiment confirmed reliable pre-commit across 5+ repeated runs).
  `natural_chain_ok`'s definition in `linksplice.m`/`codeswap.m`
  deliberately does not require `seg2`'s own tail to already read as a
  terminator pre-commit, since the splice itself never touches that word.
- 2026-08-28T (task 1, HW-VALIDATED positive): `skip_seg1` case run twice
  in calibration -- both times `final_status=4` (Completed, no fault),
  `readback_MID_word0` stayed at sentinel `0x5eed1000` (seg1's 732 real
  dispatches never ran), and `readback_A_word0` = `0xc0000023`, EXACTLY
  seg2's own last authored tag -- proving the hardware followed our
  hand-computed link directly from seg0 to seg2, skipping seg1 entirely,
  and correctly executed seg2's real, unmodified records to completion.
- 2026-08-28T (task 2, boundary sweep, calibration): ran the case matrix
  (see `casematrix.py`) once each. Results (informal, re-derived officially
  below): `skip_seg1`/`mid_segment_offset`/`misaligned_byte1`/
  `misaligned_word2`/`at_capacity_boundary`/`out_of_range_bit44`/
  `out_of_range_far` -> clean completion, seg1 skipped, seg2 reached.
  `misaligned_word4`/`misaligned_word8`/`one_past_capacity`/
  `out_of_range_beyond_bo`/`out_of_range_null`/`out_of_range_bit40`/
  `tag_zero`/`tag_vdm` -> clean, CONTAINED page fault
  (`kIOGPUCommandBufferCallbackErrorPageFault`), `readback_A_word0` stuck
  at pure sentinel (even seg0's own legitimate 732 dispatches produced no
  visible output -- the whole command buffer's effect was rejected, not
  just the tail). `encoding_max` (tag `0xff`, target
  `0x00ffffffffffffff`) -> a DIFFERENT, more severe failure class:
  `kIOGPUCommandBufferCallbackErrorHang` (a genuine GPU hang, contained --
  no host wedge, no process hang; `readback_A_word0` showed seg0's OWN
  last tag, i.e. seg0 itself completed before the hang). System health
  re-checked immediately after (`calib0` sanity dispatch) and confirmed
  normal. `out_of_range_bit40` vs `out_of_range_bit44`/`out_of_range_far`
  (bit44/bit46 offsets alias back to a valid mapping and succeed; bit40
  does not and faults) is read as: the target field's real, hardware-
  translated address width is narrower than its 56-bit encoding, with the
  transition somewhere between bit40 and bit44 -- not pinned down further
  here. `misaligned_byte1`/`misaligned_word2` succeeding while
  `misaligned_word4`/`misaligned_word8` fault is read as: sub-4-byte
  offsets are masked/rounded away by the fetch path, while 4-byte-and-up
  misalignment lands on genuinely different (and here, invalid) content --
  an alternative, not fully excluded, explanation is that each misaligned
  offset simply decodes different garbage bytes as a "record", and the
  ones that happen to succeed/fault are shape-dependent rather than a
  clean alignment rule; RESULTS.md reports both readings.
- 2026-08-28T (task 3, bounded attempt): built `harness/codeswap.m`.
  Compiled two genuinely different kernels (`kernel_x`: fixed constant
  `0x11111111`; `kernel_y`: fixed constant `0x22222222`), appended their
  real dispatches after `seg2` (so they land as `seg2`'s own records
  36/37, never disturbing the validated 732/732/36 boundary), captured
  BOTH real records verbatim (44 bytes each), confirmed they are
  byte-identical except the `+0x08` "code/uniform-window pointer" field
  (`0x00007970` vs `0x00007973` -- a difference of only 3, suspicious for
  a raw shifted absolute VA and more consistent with a small per-dispatch
  preamble-slot index), built a hybrid record (kernel_x's record with only
  that one field replaced by kernel_y's own value), wrote it plus a
  terminator into a fresh buffer we fully own, and redirected seg0's
  (HW-validated) link into it. Result: clean, CONTAINED page fault; neither
  `buf_X` nor `buf_Y` changed from sentinel. Read as a precise negative:
  the `+0x08` field is not a portable, location-independent absolute code
  selector that can be verbatim-copied between two originally-adjacent
  records and relocated; its true encoding (relative to segment base?
  dispatch ordinal? something else?) remains UNKNOWN. This experiment did
  not attempt to derive that encoding (out of scope for the remaining
  budget) -- flagged as the concrete P0.7 follow-up.
- 2026-08-28T (freeze): wrote `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`,
  `schema.py` (GATED/NON-GATED key split + redaction + no-address-leak
  assertion), `casematrix.py` (frozen 18-case linksplice matrix +
  1-pseudo-case codeswap), `run.py`, `verify.py`. `verify.py --selftest`
  (12/12) and `--seqtest` (7/7) both PASS on the first run after freeze.
  All informal calibration artifacts under `work/calib0.m`,
  `work/dumps_*`, `work/c*_result.json`, `work/sw_*` deleted before the
  official runs began (per SUBAGENT_BRIEF: scratch stays inside the repo
  under `work/`, and is not promoted as evidence -- every claimed number
  above is re-derived from the two official `raw/` captures, not copied
  from these deleted files).
- 2026-08-28T (official run01/run02): `verify.py --preflight` PASS ->
  `run.py --run-id m4_20260828_run01 --execute` -> smoke gate PASS, 19/19
  cases completed (18 linksplice + codeswap), zero process timeouts ->
  `verify.py --selftest --seqtest --between-runs` PASS -> `run.py --run-id
  m4_20260828_run02 --execute` -> 19/19 cases again, zero timeouts ->
  `verify.py --captured` **FAIL, 3/19 mismatches**
  (`misaligned_word8`,`out_of_range_bit40`,`codeswap_task3`). Diagnosed
  immediately by diffing the two gated records field-by-field: in every
  case the ONLY differing field was the readback content on a FAULTED
  command buffer (`final_status=5` both times) -- e.g. `misaligned_word8`
  read back pure sentinel in run01 but partial progress into `seg2`
  (`0xc0000002`) in run02. This is a genuine hardware finding (fault-time
  memory-visibility race), not a capture defect; both runs retained as
  evidence. `schema.py` corrected (readback content excluded from the gate
  whenever `final_status!=4`) -- see the module's own
  "POST-CAPTURE SCHEMA CORRECTION" docstring and `CAPTURE_CONTRACT.json`.
  `verify.py --selftest` re-run after the fix: 16/16 PASS (new
  racy-on-fault fixtures literally reproducing the discovered case).
- 2026-08-28T (official run03/run04, corrected schema round 1):
  `run.py --run-id m4_20260828_run03 --execute` -> 19/19, zero timeouts ->
  between-runs PASS -> `run.py --run-id m4_20260828_run04 --execute` ->
  19/19, zero timeouts -> `verify.py --captured` **FAIL, 1/19 mismatch**
  (`encoding_max`). Diagnosed: `final_status` was identical (5) both runs,
  but the verbatim `final_error` string differed --
  `"...ErrorHang"` in run03 vs `"Discarded (victim of GPU error/recovery)
  ...ErrorInnocentVictim"` in run04. A second genuine hardware finding
  (GPU-level hang/TDR recovery labeling race), not a capture defect; both
  runs retained. `schema.py` corrected again (gate a normalized
  `final_error_category` -- `PageFault`/`GPU_RECOVERY_EVENT`/`Other`/`None`
  -- never the verbatim string). `verify.py --selftest` re-run: 20/20 PASS
  (new racy-final_error fixtures literally reproducing this case).
- 2026-08-28T (official run05/run06, corrected schema round 2, FINAL):
  `run.py --run-id m4_20260828_run05 --execute` -> 19/19, zero timeouts ->
  `verify.py --selftest --seqtest --between-runs` PASS -> `run.py --run-id
  m4_20260828_run06 --execute` -> 19/19, zero timeouts -> `verify.py
  --selftest --seqtest --captured` -> **20/20, 7/7, 19/19 ALL PASS, zero
  mismatches** (`analysis/cross_run_report.json`). This is the pair
  `RESULTS.md`'s closure-relevant table is drawn from. Total across all six
  official runs: 114 fresh GPU command-buffer submissions, zero
  process-level timeouts, zero host wedges; one case (`encoding_max`)
  produced a genuine, CONTAINED GPU hang each time (confirmed recovered by
  the immediately-following run's own smoke-gate dispatch succeeding).
- 2026-08-28T (wrap-up): `analysis/report.py` written and run against
  `raw/m4_20260828_run05`; `RESULTS.md` written (verdict, per-task
  observed/interpreted sections, the link-target boundary table, the
  finite-resource-mandate table, the nondeterminism-discovered-by-the-gate
  section, GENERATED-vs-COPIED per field, remaining P0.5/P0.7 gaps, gate
  results, clean-room attestation); `README.md` written; large
  `work/*/dumps/` BO-snapshot directories (~1.1 GiB total) and
  `*.iotrace.log` files deleted across all six run work-directories (not
  evidence -- the promoted facts are in `raw/`, reproducible by rerunning
  `run.py`; `work/` dropped from 1.1 GiB to under 1 MiB). `manifest.json`
  finalized. Experiment complete for this dispatch's scope.
