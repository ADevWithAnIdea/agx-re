# EXP-0188 — PROGRESS

Append-only. One entry per milestone, so a kill costs at most one milestone.

## 2026-08-30 — M1: pre-registration frozen (before any build or device time)
- Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`, `experiments/FIELD-SWEEP-PROTOCOL.md`
  (all of it, §3/§5/§7 included).
- Selected **4 of the 9** offered fields, by whether the dimension can actually be BUILT:
  `if_push.scope` (region kind), `iadd2.b2_fmt` (operand format/width),
  `simd_ballot.cache` + `simd_shuffle.cache` (execution-mask bank / divergence depth).
  Declined `iter.b9`, `imageblock_store.b4`, `frag_color_store.store_mode`, `vtx_out_pos.slot`
  (all need a render/vertex harness for a PIPELINE-STATE dimension) and `cvt_f2i.b9`
  (EXP-0184 spanned its dimension today). Reasons in `PRE_REGISTRATION.md` §2.
- Authored 18 carriers across 3 MSL files; host oracles simulate our own MSL and assert every
  expected value is NON-ZERO and never collides with the poison.
- `CAPTURE_CONTRACT.json` frozen, 21 blobs. Repo revision pinned `45d97d62`.
- Nothing has run on the device yet.
