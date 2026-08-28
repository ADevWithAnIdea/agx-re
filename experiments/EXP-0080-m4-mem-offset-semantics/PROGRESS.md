# EXP-0080 progress log

- **2026-08-28T00:0xZ — M1: successor created; design adopted; three process
  fixes applied.** EXP-0080 is the successor of the terminal
  `../EXP-0077-m4-mem-offset-semantics` (crashed at its in-run smoke gate on a
  `KeyError: 'item'` after creating `raw/m4-20260827-run01/` as a stub; ZERO
  matrix cases executed; see its RESULTS.md/PROGRESS.md). Design adopted
  unchanged: kernels/ (byte-identical), baseline anchors, casematrix (2164
  cases), analysis, make_manifest, verify gates. Fixes: (1) SMOKE_CASE carries
  the full case-record keys; (2) build + baseline + the NON-RECORDED smoke
  gate run BEFORE any raw/ artifact is created (a defect there exits 3 with
  the receipt printed and no burned run id — the EXP-0077 crash class made
  structurally impossible); (3) an unexpected sweep exception writes STOP.json
  (phase dispatch_loop) with the completed-case count. The EXP-0077
  pre-capture plumbing validations are re-run as this experiment's own
  authorized checks below (same three: unspliced ld, one spliced scratch
  case, unspliced st).

- **2026-08-28T00:2xZ — M2: smoke gate caught two real runner defects at the
  FIRST invocation; clean pre-capture stop (no raw burned — the new ordering
  proving itself).** run01 attempt #1 exited 3 at phase `smoke_gate`:
  `out0=0x3CA50000` (a[0]) with `decoded=null`. Root causes, both mine, both
  fixed in an authorized pre-capture repair (no raw path existed, so the
  hash binding could be refreshed legally): (1) `splice_case` emitted
  instruction-relative byte offsets (`_agc.main@9=81`) instead of
  main-relative (the probe load sits at main+0x26, so the byte wanted
  `@0x2f`) — the misdirected splice landed in the preceding iadd2's immediate
  and shifted the idxbuf read to zero words, hence a[0]; (2) the readback hex
  is a LITTLE-ENDIAN byte dump and was parsed as a big-endian integer
  (`0000a53c` must decode to 0x3CA50000, not 0x0000a53c). Fixed in run.py
  (offsets + parsing), analysis.py (hand-check decode), verify.py (synthetic
  out0 now the same LE form). All gates re-pass after the refresh
  (selftest 19/19, seqtest 14/14, manifest OK, preflight PASS). The one smoke
  dispatch that ran is a testbed invocation of the same kind as the authorized
  plumbing checks; its observation is not evidence.

- **2026-08-28T00:4xZ — M4: TERMINAL. run01 complete but unverifiable
  (single-run, repeat-unverified); successor EXP-0081.** After the M2 repair,
  run01 captured fully: 2164/2164 cases, six raw artifacts, no STOP.json,
  controls exact (~0.05 s/case). `verify.py --between-runs` then failed on
  `case splice consistency`: verify re-derives splice args from
  `run.splice_case` (instruction-relative offsets) while the runner records
  main-relative offsets (probe at main+0x26). The synthetic self-test could
  not catch it — its fabricated lines were built with the same wrong helper
  (generator/checker agreement). Repairing verify.py post-capture breaks the
  00_inputs.json hash binding (the EXP-0072/0075 quarantine class), so
  EXP-0080 is terminal process history; run01's observations seed no promoted
  claim. Successor EXP-0081: `splice_case` takes the probe main offset as a
  parameter (single definition shared by runner/verifier/synthetic builder)
  plus a selftest mutation proving the per-line check pins the main-relative
  splice form.
