# EXP-0081 progress log

- **2026-08-28T00:5xZ — M1: successor created.** EXP-0081 succeeds the
  terminal EXP-0080 (single complete run, repeat-unverified: its
  --between-runs gate re-derived splice args instruction-relative while the
  runner records main-relative; post-capture repair forbidden by the hash
  binding). Root fix: `run.splice_case` takes the probe main offset and
  returns MAIN-relative splice args as the single definition shared by
  runner + verifier + synthetic-tree builder; new selftest mutation
  `splice_instruction_relative` proves the per-line check rejects the
  instruction-relative form. Matrix/predictions/kernels byte-identical to
  EXP-0080's (not tuned from its unverified run). Run ids dated 2026-08-28.
