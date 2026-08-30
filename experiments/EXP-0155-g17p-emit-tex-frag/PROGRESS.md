# EXP-0155 — PROGRESS (append-only, one entry per milestone)

- **2026-08-29 ~22:05Z — orientation.** Read `CLAUDE.md`, `CODEX.md`,
  `SUBAGENT_BRIEF.md`, `NEO-TARGET-BRIEF.md`, `FIELD-SWEEP-PROTOCOL.md`,
  `docs/evidence-classification.md`. Confirmed the blocking-field census against
  `tools/agx-isa/validation.json`: **110 fields** over the 18 dispatched
  instructions. Credentials + address confirmed with the orchestrator; neo alive
  (`applegpu_g17p`, macOS 26.6, up 29 min).

- **~22:10Z — harness.** Authored `harness/gfrun.m` from OUR OWN prior code
  (EXP-0143 `frun.m` + EXP-0142 `renderpersist/texpersist`): persistent render
  loop with the FIELD-SWEEP-PROTOCOL §7 sentinel/poison/unique-scratch
  mitigations, **plus** a sampled R32Float texture (`texel = x+100y`), a
  writable RGBA32Float texture reset+read-back per request, 3D/cube/2D-array and
  depth textures, and the OS fault-classification print (`ERRDOM`). Built on the
  neo with full Xcode.

- **~22:18Z — pre-freeze census (calibration, not evidence).** Compiled all 16
  carriers and tokenized both stages with `tools/agx-isa`. Findings that changed
  the design, all retained in `raw/prefreeze/`:
  * a float2 2D sample emits **no `tex_coord_setup`** at all — nor does a
    3D/cube/array sample; only the const-offset-gather / bias / gradient /
    depth-compare carrier (`t_lodoff`) emits it. `tex_coord_setup` arms moved there.
  * the RGBA32Float colour output of the implicit-LOD sample carrier is an
    **`imageblock_store`**, not a `frag_color_store` — so `imageblock_store` got
    a carrier for free.
  * **`imageblock_load` has no carrier**: programmable blending compiles to
    `tile_read` (EXP-0147's instruction), and the explicit-layout imageblock
    still does not compile. Pre-registered as NOT ATTEMPTED.
  * the branch in the first `t_write` stopped the program tokenizing at all;
    rewritten branch-free (all fragments write the same three texels).

- **~22:23Z — the EXP-0129 trap, caught pre-freeze.** The first smoke read
  **every texture arm as NOT LIVE**. A byte-by-byte diagnostic showed the splice
  was landing and the pixel did move — the single named control `coord = 0x00`
  was inert because our compiled `tex_sample` bytes **already hold `coord = 0`**.
  Replaced by a frozen **liveness ladder** (named control, then each swept
  field's complement and zero, skipping values the field already holds, ≤14
  steps, every step emitted). Re-smoke: **40 / 40 arms LIVE**, 0 dead.

- **~22:30Z — PRE_REGISTRATION.md + CAPTURE_CONTRACT.json FROZEN** at repo rev
  `7dc67d76`, **52,090 pre-registered sweep cases** over 40 arms / 16 carriers,
  plus the 0x57 collision probe and the `vary_store` field sweep.

- **~22:35Z — run01 launched** (gated, unlocked per the orchestrator's
  concurrency correction; `InnocentVictim` retried, never recorded as `fault`).

- **~05:56Z — run01 STOPPED BY HAND at 33,185 / 52,090 cases (24 of 41 arms) and
  RETAINED as PARTIAL.** Twice the device entered a transient window in which
  nearly every command buffer came back `InnocentVictim`; because the harness
  retried a foreign fault 8× *and then* applied majority-of-3 on top, one
  contaminated case cost ~45 s and 24 renders and throughput fell from ~105
  cases/s to under 1 case per 100 s. The first window followed a **genuine,
  reproducible hang of our own** — `tex_sample.tex_type = 32` on the `t_texops`
  gather occurrence, 3/3 `kIOGPUCommandBufferCallbackErrorHang`. Unmutated
  renders of `c_iter` and `t_sample` returned `STATUS OK` immediately after the
  stop, so the device was **not** wedged. Recorded in
  `raw/g17p_20260829_run01/PARTIAL.md`; the id is never reused and the capture
  is never used to promote a field.

- **~06:00Z — harness fix (amendment A1, no classification change) + run02.**
  A case already classified `FOREIGN_FAULT` is no longer re-confirmed (it is
  `foreign` either way), the foreign backoff is shortened, and a cascade guard
  settles and re-validates the baseline after 8 consecutive foreign outcomes.
  The two gated runs are captured under NEW ids `run02` / `run03`.

- **~06:08Z — run02 stopped and retained as PARTIAL (amendment A2).** EXP-0153's
  `persistrun.py` EOF-spin defect was relayed mid-run; `harness/runner.py` here
  carried the identical bug (an exited child returns `""`, not `None`, so the
  caller spins at 100 % CPU with no timeout). Fixed, and the gated pair
  re-captured under NEW ids so both runs share identical runner code.

- **~06:28Z — GATED RUN 03 complete.** 49,847 cases, 1,449 s, 41 hangs, no
  cascade. Pulled into the repo.

- **~06:38Z — GATED RUN 04 complete.** 49,679 cases, 213 s, 47 hangs, no cascade.
  Pulled into the repo. **99,526 gated cases total.**

- **~06:45Z — analysis.** `analysis/verdicts.py` → `field_verdicts.json`:
  **105 of 110 blocking fields promoted (86 `hardware-run`, 19
  `isolated-byte-diff`); 17 of 18 instructions EMITTABLE; `tex_sample` CLEARED
  (9/9).** `analysis/summarize.py` → `bit_rules.json`: **232 exact,
  machine-checked set identities** over 244 comparable (arm, field) triples.
  Headline hardware findings: a single destination-register rule shared by seven
  instructions (GPR >= 96 faults; +bit1 hangs — reproduces EXP-0143's M4 boundary
  on G17P); the **0x57 collision RESOLVED** (byte+2 is a don't-care in all four
  programs; byte+1's low three bits are the form/length selector).

- **~07:05Z — lease-isolated fault confirmation (A3), PARTIAL.** 114 genuine
  cross-run fault/hang values re-run 5x: **112 reproduce, 2 do not** — including
  one true §7A false fault (`tex_write.coord_pack = 5`, `fault` in both gated
  runs, `wrong_value` 5/5 isolated). Stopped by hand at ~1 record/85 s; ~900
  values remain unconfirmed and are labelled as such. Two defects in the pass
  recorded in its `NOTE.md` (control records wrongly selected; the shared lease
  races on a stale break).

- **~07:10Z — deliverables written**: `RESULTS.md`, `README.md`, `manifest.json`,
  `analysis/{field_verdicts,bit_rules}.json`, all raw pulled back into the repo.
