# EXP-0199 — progress log (append-only)

Target: A18 Pro / G17P, 192.168.170.254. Remote workdir `~/agxre/EXP-0199`.

- **2026-08-30 ~11:50Z** — dispatched. Read SUBAGENT_BRIEF, NEO-TARGET-BRIEF,
  FIELD-SWEEP-PROTOCOL, CODEX, evidence-classification. Device verified alive.
- **~11:55Z** — carriers authored (`k_line*.metal`, `k_sin.metal`, `c_depth.metal`,
  `c_vary4.metal`); `gfrun5.m` forked verbatim from our own EXP-0172 `gfrun2.m`;
  `crun199.m` written (compute splice runner WITH the 0xDEADBEEF read-back poison,
  which the shared `agxrun_persist.m` does not have) ; `runner199.py` written with
  ONE pump thread per child (DEF-0178-1).
- **~12:00Z** — carriers compiled on device, tokenized with `tools/agx-isa/isadb.py`;
  `c_depth` fragment tokenizes to 32 instructions with **0 leftover bytes** and puts
  `frag_depth_store` at offset 168 inside the documented `87/07` depth bracket.
- **~12:03Z** — PREFREEZE pilot 01/02/03 (retained in `raw/prefreeze/`).
  Findings that shaped the frozen matrix:
  * **HAZARD, reported as a courtesy per FIELD-SWEEP-PROTOCOL §7:** inserting the
    2-byte word `01 00` at a `k_line` instruction boundary **hung the GPU 5 times
    out of 5** (`kIOGPUCommandBufferCallbackErrorHang`). The device recovered each
    time and no `macvdmtool` was needed. **Excluded from the frozen matrix.**
  * `06 02` inserted at a boundary the compiler did not choose runs the carrier
    **exactly correctly**, while `00 00`, `ff ff`, `60 01` and a 2-byte deletion at
    the same boundaries all break it.
  * `k_line3` gives 6 bytes of alignment slack, enough for a 4-byte insertion.
- **~12:08Z** — PRE_REGISTRATION.md + CAPTURE_CONTRACT.json frozen (repo revision
  `ff747ca3`, 14 dirty sibling files recorded; the contract gates on the authored
  blob hashes, not on live HEAD).
- **~12:14Z** — `smoke01` (arm C, 202 cases) run and **retained, not reused**;
  killed once the record schema was verified.
- **~12:17Z** — **run01** = `g17p_run01a` (arms A,E), `g17p_run01b` (arm B),
  `g17p_run01c` (arms C,D). 2328 + 1059 + 2367 cases. **0 hangs.**
- **~12:22Z** — **run02** = `g17p_run02a/b/c`, same frozen matrix, same frozen
  archives. run02b and run02c complete, 0 hangs; run02a slow through the n2_op6
  byte0 sweep (that sweep contains ~50 GPU faults, each costing a queue rebuild).
- **~12:30Z** — run01 raw pulled back into the repo.
- **~12:20Z** — COORDINATOR STOP: `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` added by the user
  and normative. Read it. Assessment: the original contract lacked Gate A (actual-byte
  ledger), Gate C (independent semantic predictor with pre-registered competing models) and
  Gate E (shuffled/reversed confirmation). Gate B (positive control per arm) was already
  present. Per its §4 the original contract and the four captured runs were **RETAINED
  UNCHANGED and reclassified as DISCOVERY**; nothing was discarded or re-run.
- **~12:25Z** — `AMENDMENT-01.md` + `CAPTURE_CONTRACT-AMENDMENT-01.json` frozen (repo
  revision `2616a3c2`). Harness changes: `--ledger <off>:<len>` in `crun199.m` and
  `gfrun5.m`, printing `ACTUAL <off> <hex>` from the spliced file **re-read off disk**;
  `analysis/predictor.py` holding the case matrix, the ledger assertion and the
  per-model per-case predictions; `kernels/c_depth2.metal`, the **adversarial second depth
  carrier** (decreasing depth function, different varying, third varying in colour).
- **~12:30Z** — `g17p_confsmoke` (664 cases, retained) verified the ledger end to end:
  657 checks, 0 failures, with an independent `isadb` decode per case. It also verified the
  c_depth2 host oracle exactly (0.6125/0.6875/0.5375 = `0.9 − (PIX0.g − 0.125)`).
- **~12:33Z** — schema amended before the amendment's first GATED dispatch: render cases
  now record the **exact number of differing pixels** per surface plus a value histogram,
  so a semantic claim quotes numerators instead of a hash inequality.
- **~12:36Z** — `g17p_conf01` (shuffled, 6507 cases, 113 s, 0 hangs).
- **~12:38Z** — `g17p_conf02` (reverse) **crashed** on an unguarded baseline comparison
  after 13 records. RETAINED, not repaired. `g17p_conf03` aborted correctly after 2 records
  once the guard was added but before the baseline was scored against itself. RETAINED.
  Replacement captured under a NEW id.
- **~12:41Z** — `g17p_conf04` (reversed, 6507 cases, 320 s, 0 hangs). **Both gated
  confirmation captures complete: 0 hangs, 0 measurement failures, 0 invalid ledgers,
  12 932 ledger checks with 0 failures, cross-run agreement 6475/6511 = 99.45 %.**
  Concurrency MEASURED: median 9, peak 17 other agents' GPU processes.
- **~12:45Z** — all raw pulled back into the repo. Analysis (`analysis/gates.py`,
  `analysis/make_verdicts.py`), `RESULTS.md`, `README.md`, `manifest.json` written.

## Progress accounting (RE_EXPERIMENT_PROCESS_CORRECTIONS §9)

- **New raw observations:** 25 471 case records across 12 capture directories.
- **New geometry facts:** exact accepted sets for 12 bytes across 5 instructions;
  `frag_depth_store` byte+1 and byte+2 and `vary_slot` byte0 and byte+2 shown to be
  over-constrained or unenforced relative to their declared `match`; `sfu_marker` length 2
  and `frame_marker_compact` length 4 confirmed by insertion.
- **New liveness facts:** `frag_depth_store.b5` bit 1; `vary_slot.slot` bit 2 (reproduced
  on a new carrier); `vary_slot.sel`/`byte0`; `n2_op6` byte0/opsel/imm_sel on a fourth
  carrier.
- **New semantic facts:** `frag_depth_store` writes the shader depth output to the depth
  attachment (M_A1 selected over three competing models, on two carriers);
  `vary_slot.slot` is NOT a slot selector (M_B1 refuted against a working positive
  control); the two markers' framing models selected.
- **New generated recipes:** `generated-point` for `sfu_marker` (2-byte) and for the
  4-byte `0x60` form. No canonical recipe.
- **Claims downgraded:** none of ours. Two db.json claims are contradicted by direct
  observation and are recorded as db defect candidates, NOT applied
  (`vary_slot` byte+3 semantics; `frame_marker_compact` length).
- **Bounded unknowns remaining:** the micro-operation of both markers; `n2_op6`'s
  semantics (declared unknown in advance); `frag_depth_store` b3/b4 operand meaning;
  whether `frame_marker_compact`'s 2-byte reading survives in its corpus contexts
  (threadgroup atomics / divergent control flow), which were not tested.
- **~12:52Z** — COORDINATOR RULING: **Gate E is currently unmeetable for the whole
  fan-out** (EXP-0204's dedicated quiet-window helper never saw a quiet machine in 86
  samples; EXP-0201/0203/0205 are held on E alone). Applied:
  * every verdict downgraded to **`reproducibility: INCOMPLETE — Gate E not met`** and
    explicitly **held** for a serialized quiet confirmation run. Gates A/B/C/D are
    complete;
  * **checked the EXP-0204 hang window (20:00–20:25 UTC) against my own captures:
    `g17p_conf01` ran 19:29–19:31 and `g17p_conf04` ran 19:36–19:42 UTC, entirely
    BEFORE it.** None of my 36 disagreements can be attributed to EXP-0204;
  * applied EXP-0201's lens: of 36 cross-run disagreements, **26 have a `fault`/`hang` on
    exactly one side** (11 carrying `InnocentVictim`) and 3 more are the baseline records
    themselves. **Adjudicated agreement 6501/6511 = 99.846 %**, lowest per-group
    254/256. No model selection turns on a single value.
