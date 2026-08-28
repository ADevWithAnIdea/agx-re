# PROGRESS — EXP-0141

Append-only milestone log. Timestamps UTC.

- **M1 2026-08-28** — read `CLAUDE.md`, `CODEX.md`, `SUBAGENT_BRIEF.md`,
  `FIELD-SWEEP-PROTOCOL.md`, `docs/evidence-classification.md`,
  `work/DOC-02-LABELLING-REPORT.md`, `db.json` + `validation.json` for the ten
  target instructions. Confirmed the blocking count: **58 of 81 fields** are
  below emitter grade (device_load 6, device_store 5, atomic_mem 14,
  atomic_rmw 14, atomic_tg 11, threadgroup_barrier 2, mem_fence 3, mem_fence8 2,
  dev_scoreboard_fence 1, tg_addr_compute 0-modelled-but-VETOED).
- **M2 2026-08-28** — authored six carriers (`kernels/*.metal`), rebuilt the
  EXP-0101 synthesis path on the CURRENT `db.json` schema (`mov_imm` is now
  `imm7`+`imm_top` with a 4-bit `dst`; `falu2`/`falu2i` split `srcA_reg` into
  6 bits + `srcA_reg_top`; `stop` is 4 bytes). PILOT: EXP-0101's construction
  reproduces exactly (`-7.0`), `(0,0)` silently zeroes to `1.5`, and a NEW
  result appeared immediately — a direct load->store forward needs
  `device_store.addr_mode = 0x56`; `0x54` stores 0.
- **M3 2026-08-28** — TWO HARNESS DEFECTS found and fixed before freezing:
  (a) reusing one splice-archive filename across persistent-runner requests
  gives **28/360 spurious `CMDBUF_ERROR`** on byte-identical known-good
  archives; a unique path per request (unlinked afterwards) gives **0/360**.
  (b) a real GPU fault poisons following command buffers, which return
  `kIOGPUCommandBufferCallbackErrorInnocentVictim / Discarded (victim of GPU
  error/recovery)`; a bounded retry keyed on that exact error text made the
  13-case control set **fully deterministic over 4 repeats** (was 3 different
  outcome vectors in 3 repeats). Both are recorded in `PRE_REGISTRATION.md` 6.
- **M4 2026-08-28** — all six carriers' HOST-COMPUTED oracles verified against
  the UNSPLICED compiled kernels (6/6 match). Case matrix frozen: 93 arms,
  20 529 cases, 6 pre-registered falsifiers, 61 pre-registered baselines.
  `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` frozen (15 authored blobs).
- **M5 2026-08-28 (resume after session-limit kill; `raw/` still empty)** —
  `FIELD-SWEEP-PROTOCOL.md` section 7 (concurrent sweeps contaminate each other)
  landed after the first freeze. Implemented all four requirements, plus a THIRD
  contamination mode found while doing so: under sibling GPU load a command
  buffer returns **STATUS OK having executed nothing**, and the zero readback is
  indistinguishable from this ISA's "silent zero" — it corrupted the
  pre-registered baseline itself during smoke. Added an integrity sentinel to
  all six carriers, majority-of-3 confirmation for every non-`ok` verdict,
  bounded innocent-victim retries with the OS fault class recorded, baseline
  health checks every 100 cases with runner restart + cascade abort, and a `ps`
  concurrency snapshot. ALSO replaced the barrier litmus: the first two shapes
  could not detect a spliced-out barrier at all; the lane-0-writer shape gives a
  deterministic 224/256 stale lanes. `PRE_REGISTRATION.md` AMENDMENT 1 written,
  `CAPTURE_CONTRACT.json` re-frozen. Controls: 3 consecutive identical outcome
  vectors, 6/6 falsifiers fail, 0/36 health failures.
- **M6 2026-08-28** — gated run `m4-20260828-run01` STOPPED at 3240/20529 on a
  harness defect from AMENDMENT 1 (a reproducible fault has no output, so its
  integrity sentinel is trivially missing; the canary loop retried every real
  fault 12+ times and mislabelled it `invalid_run`). Partial capture RETAINED
  with `PARTIAL.md`, id not reused. Fixed, AMENDMENT 2 written, contract
  re-frozen, gated runs renamed `run11`/`run12`.
  The 3240 partial records already answered the headline question and it
  reproduced identically at four target registers — see M7.
- **M7 2026-08-28** — gated run `m4-20260828-run11` COMPLETE: 20 615 records
  (20 529 cases + 86 interleaved health checks), 214/214 health checks passed,
  0 cascades, 0 control violations, 6/6 falsifiers failed as pre-registered,
  2 reproduced hangs (both in `attg_atomic_tg_b5`, arm correctly aborted at
  129/257 per the 2-hang budget; host survived). Outcomes: 10 315 ok,
  6 194 silent_zero, 3 763 wrong_value, 253 fault, 84 nondeterministic,
  4 invalid_run, 2 hang. Concurrency snapshot: 0 sibling GPU runners at start
  and end of this run.
  HEADLINE ANSWERED: `device_load.dst_lo` must be exactly 1 and only bit 0 of
  `dst_ext9` is live (must be 1) — identical at target registers 3, 7, 20 and
  33, and confirmed by the full 512-value 2-D product (exactly 64 accepted =
  {dst_lo == 1} x {dst_ext9 odd}). `extmode >> 1` is the destination register
  with bit 0 a don't-care, reaching r0..r63 only.
  SECOND HEADLINE: the atomic RMW operand register IS encoded — byte+5 bit 7
  and byte+6 bits 0..5 — which `db.json` calls "implicit" and DOC-02 ranks a
  MISSING field.
- **M8 2026-08-28** — added the `atomic_rmw` ADDENDUM matrix (13 arms, 3 074
  cases, byte+1 pinned to 0x11) because the frozen main matrix only ever swept
  the `atomic_mem` form; transferring those labels to `atomic_rmw` would be the
  exact strength mismatch `docs/evidence-classification.md` exists to prevent.
- **M9 2026-08-28** — gated run `m4-20260828-run12` launched (independent
  repeat). Running markedly slower than run11 (~7 s/case in the mostly-faulting
  `attg` arms vs ~2 s) under sibling GPU load; the majority-of-3 confirmation
  requirement is what makes non-`ok` cases expensive, and that is the intended
  trade.
- **M10 2026-08-28** — `m4-20260828-run12` COMPLETE (20 744 records; 215/215
  health, 0 cascades, 0 hangs, 0 control violations). Cross-run gate on the main
  matrix: **0 ACCEPTANCE disagreements**, 285 exact-outcome disagreements (all
  `fault` vs `nondeterministic`, i.e. how a failing value failed, never whether
  it worked). 133 cases exist in one run only — run11 aborted
  `attg_atomic_tg_b5` on its 2-hang budget while run12 completed it without
  hanging (it faulted reproducibly instead), so `atomic_tg.op_desc` stays
  PARTIAL. Promotion gate refined to compare ACCEPTANCE rather than exact
  outcome, with both numbers published.
- **M11 2026-08-28** — addendum `run21` + `run22` COMPLETE (15 005 records each,
  0 cases in one run only, 152/152 health each, 0 hangs, 0 cascades, 2 acceptance
  disagreements out of 15 005). **H7 CONFIRMED**: `atomic_rmw`'s bytes +2..+13
  yield accepted sets IDENTICAL to `atomic_mem`'s, all twelve. **H9 PROVEN**:
  operand index 3 (byte+5=0x80 AND byte+6=0x01) selects `a[3]`=3007 and consumes
  it — the two-byte model is no longer interpolated. **H10 CONFIRMED**:
  `device_store.extmode` accepted set moves with the source register
  (r4 -> {8,200}, r8 -> {16,208}, r12 -> {24,216}). **H8 PARTIALLY REFUTED**:
  the `dst_lo`/`dst_ext9` rule is `ld_format`-dependent in its DON'T-CARE bits
  (64/512 for 16 codes, 32/512 for ld_format 3/7/9/13, 16/512 for 39), though
  `dst_lo=1, dst_ext9=1` is valid under all 21 — reported, not smoothed over.
- **M12 2026-08-28** — FINAL LEDGER: **51 of the 58 blocking fields moved to
  emitter grade**; 7 remain and each has a stated reason (1 PARTIAL after hangs,
  4 with no ordering observable, 2 with no dispatchable carrier). `RESULTS.md`,
  `README.md`, `analysis/{summary,field_verdicts,bitrules,ledger,memfence8_locate}.json`
  and `manifest.json` written. NOT committed — the orchestrator commits.
