# EXP-0172 — PROGRESS

Append-only. Newest entry last. Times UTC.

## 2026-08-30 — M0: dispatch read, governing law read
- Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
  `experiments/FIELD-SWEEP-PROTOCOL.md`.
- Repo revision at dispatch: `4b16d0b4` (`exp(0166): the assembler could not clear a bit`).
- **No device work started.** Device queue is held by four experiments ahead of this one;
  the dispatch requires analysis + pre-registration first, then an explicit go.

## 2026-08-30 — M1: worklist regenerated and ownership reconciled
- `python3 tools/agx-isa/emit_worklist.py` regenerated. Headline **44 emittable / 122 blocked
  / 166 emitter-relevant**; **30** instructions are ONE field away (dispatch said 29 — it has
  moved).
- Ownership reconciliation against the dispatch (EXP-0168 owns 12 instructions + the field
  name `dst` anywhere; EXP-0171 owns `ilogic` + the field names `srcA`/`tail`):
  - **NOT mine (field name `dst`)**: `frag_color_pack.dst`, `n4_rt_word.dst`,
    `rt_query_traverse.dst`, `uniform_mov.dst`.
  - **NOT mine (field name `tail`)**: `bf_fma_dst.tail`, `ibitcount.tail`.
  - **NOT mine (EXP-0168 instruction)**: `atomic_mem`, `copysign`, `cvt_f2h`, `falu_acc`,
    `if_push`, `iter_at`, `pack_convert`, `shift_amt_move`.
  - **MINE (16)**: `cubearray_coord_const.b3`, `dev_scoreboard_fence.scope_flag`,
    `falu2i.imm_flag`, `frame_marker_compact.b1`, `get_sr.form`, `half_alu_fma12.ext`,
    `imageblock_store.src`, `irotate.b2`, `mesh_out_src.sel`, `n4_cf_word.b3`,
    `ret.scoreboard`, `simd_ballot.cache`, `simd_shuffle.cache`, `tex_deriv.dstsrc`,
    `tex_sample.coord`, `vary_slot.slot`.
  - `irotate.b2` was NOT in the dispatch's list but is unowned and is `irotate`'s last
    blocking field; adopted.

## 2026-08-30 — M2: prior-evidence read, per-field triage
- Read `EXP-0163/RESULTS.md` (inert-liveness; the 7-of-20 result, the `iter_at.loc`
  controlled test, the `frag_color_store` `0x86` db defect, and the `simd_shuffle` byte+2
  caveat), `EXP-0166/RESULTS.md` (DEF-0166-1: 53 fields overlap their own `match`;
  `irotate.b2` reached **32 of 256** encodings through `isadb.assemble()`), and the
  `db.json` + `validation.json` rows for all 16 fields.
- Confirmed by static check that of my 16, **only `irotate.b2`** has bits pinned by its own
  descriptor's `match` (bits 16,18..23 pinned; only bit **17** free). Every other field of
  mine is match-disjoint, so a dense sweep really is dense — but the harness will count
  DISTINCT `bytes` regardless.
- Forked EXP-0163's harness (`run.py`, `harness/runner.py`, `harness/gfrun.m`,
  `analysis/census.py`, `analysis/gen_arms.py`, `analysis/manifest.py`) and the 11 of its
  authored kernels this experiment reuses.

## 2026-08-30 — M3: contract FROZEN; Tier-1 carriers rewritten device-load-free
- `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` written and frozen **before any build**.
  31 authored artifacts hashed. Repo revision at pre-registration `2792d7ca` (dirty: yes —
  sibling experiments in flight; per SUBAGENT_BRIEF captures are gated on the AUTHORED BLOB
  HASHES, not on live `HEAD`).
- **Pinned ISA DB** (orchestrator warning: the neo's shared `tools/agx-isa/db.json` is STALE —
  1036 fields vs the repo's, `falu2.srcA_class`/`srcB_class` replaced by `mod_lo`, reached by a
  `_find_isadb()` fall-through). `work/frozen/{db.json,isadb.py}` are this experiment's snapshot
  (**172 instructions, 1062 fields**), sha256 in the contract, resolved EXPLICITLY on the device
  via `AGXRE_REPO=$HOME/agxre/EXP-0172`. The neo's shared `tools/` is NOT touched.
- **`device_load` async hazard (EXP-0169) designed out of Tier 1.** A diff-based movement oracle
  over a load-seeded operand can FABRICATE movement — the one contamination mode that invents a
  positive instead of destroying one. Rewrote `k_fimm`, `k_srwide`, `k_srnarrow` to seed from
  special registers through ALU only, and `k_texread`/`k_texmix` to derive coordinates from the
  interpolated `[[position]]` with **no buffer at all**. Authored `k_deriv.metal` (new carrier for
  `tex_deriv.dstsrc`), also buffer-free. `fimm2` keeps the load-sourced `mods==0xC0` form
  deliberately and is flagged.
- **Priority frozen** (13 instructions swept, 4 fields declined without device time).
  TIER 1 = `falu2i.imm_flag`, `get_sr.form`, `tex_sample.coord`, `vary_slot.slot`,
  `tex_deriv.dstsrc`. TIER 3 = `ret.scoreboard`, `dev_scoreboard_fence.scope_flag`, promotion
  **declined in advance** (no ordering observable). Declined outright:
  `cubearray_coord_const.b3` (descriptor fires 0/1080 — EXP-0148 — nothing to splice into),
  `half_alu_fma12.ext` (`emit_unsafe` length defect owns those bytes), `mesh_out_src.sel` (no mesh
  pipeline in the harness).
- **HANG COURTESY (§7):** this experiment will sweep `ret.scoreboard` (an execution/scoreboard-wait
  mask) and `n4_cf_word.b3` (sits immediately before reconvergence points). Both are plausible
  hang regions. If the device resets during this window, EXP-0172 is a candidate cause.

## 2026-08-30 — M4: staged, built, PRE-FREEZE CENSUS done, arms FROZEN
- `~/agxre/EXP-0172/` staged on the neo with its **own pinned tool tree**
  (`tools/agx-isa/{db.json,isadb.py}` = `work/frozen/*`, sha256
  `322847609de79055b651b79fbd630948bb97120bcefd037a3c7ae5a301ba64a5`, 172 instructions /
  1062 fields), resolved explicitly via `AGXRE_REPO=$HOME/agxre/EXP-0172`. The neo's shared
  `tools/` was not read or written.
- Built `work/{gfrun2,shdump,agxrun_persist}` with the frozen clang line. All three OK.
- **Pre-freeze census (calibration, `raw/prefreeze/census.json`): all 24 carriers compiled,
  0 build failures.** Highlights: the new `deriv` carrier emits **9 `tex_deriv` occurrences with 9
  DISTINCT `dstsrc` values** across both axis codes (0x92/0x90) — the richest carrier this field has
  ever had; `srwide` emits 15 `get_sr` (form=1 on the position-in-grid family), `srnarrow` 7
  (form=0 on scalar SRs), so the *width* dimension rule 2 demands is actually spanned; `fimm`/`fimm2`
  give 15 `falu2i` occurrences and **`imm_flag` = 1 in every single one**, as predicted.
- **MEASURED DECLINE: `dev_scoreboard_fence` has ZERO occurrences in any of the 24 carriers, in any
  stage.** It cannot be swept here; recorded as a measured decline rather than swept on a carrier
  that does not emit it.
- `harness/arms.py` generated by the frozen selection rule and **FROZEN**: **57 arms, ~7848 dense
  sweep cases per run.** `imageblock_store` is carried by `ibsamp` (1 sample) and `ibms4`
  (4 samples) only — `ibhalf`/`ibmrt` emit `frag_color_store` instead, recorded in `MISSING`.

## 2026-08-30 — M5: smoke02 calibration; arm selection corrected; GATED RUNS LAUNCHED
- `smoke02` (calibration, `work/`, no verdict cites it): 780 cases, **0 hangs, 0 cascades, 0 runner
  restarts**, 195 s. **51 of 57 arms showed strict detection power** (a status-OK, same-mnemonic
  control that moved the observation).
- Fixed a real harness bug first (`smoke01` died on it and is retained, not reused): run.py
  re-decoded a patched instruction from its **own bytes alone**, but several isadb length rules look
  ahead past the instruction (`_r9_succ_safe`), so a 4-byte buffer walked off the end. Re-decode now
  splices into the real stage buffer and decodes at the instruction's own offset — the lookahead
  sees the bytes the hardware will — and cannot raise.
- **The calibration caught a rule-2 mistake in my own arm selection.** All six chosen `get_sr` arms
  happened to have `form == 0` natively, so every control flipped 0→1 and the **1→0 direction was
  never tested**: two arms that agree on the field's own baseline value cannot bound its effect in
  both directions. `gen_arms.py` now buckets occurrences by their baseline value of the target field
  and takes them round-robin, so an arm list spans the field's own values as well as the carriers'
  dimension. `get_sr.form` now has 4 arms at `form=0` and 4 at `form=1`.
- Arms regenerated and re-frozen: **66 arms, ~7904 dense sweep cases per run.**
- Early calibration reads (NOT verdicts — one run, complement+zero controls only):
  `tex_deriv.dstsrc` moved on 3/3 arms; `frame_marker_compact.b1` moved on 5/5;
  `tex_sample.coord` moved on the derivative-free `texread` arm and not on `texmix`;
  `falu2i.imm_flag` **inert on 6/6** (refuting my own size-bit H1);
  `get_sr.form` inert on 6/6 (but see the rule-2 fix above — those were all one direction);
  `simd_ballot.cache` and `simd_shuffle.cache` inert including on the NEW last-use carrier;
  **`n4_cf_word` has NO detection power at all on any of its 3 carriers** — nothing anywhere in the
  4-byte word `04 01 00 XX` moves the observation.
- **GATED RUNS LAUNCHED 09:33 UTC**, `run01` then `run02`, sequentially, same frozen `arms.py`.

## 2026-08-30 09:40 UTC — HANG NOTICE (§7 courtesy) — EXP-0172 caused device resets
`run01` produced **genuine, reproduced `ErrorHang`s** (majority-of-3 confirmed, not single
observations). If a sibling experiment saw `InnocentVictim` or unexplained streaks in this window,
**EXP-0172 is a likely cause.** The regions, exactly:

| field | hang values | swept before FIELD STOPPED |
|---|---|---|
| `frame_marker_compact.b1` | `b1 = 3` and `b1 = 7` | **8 of 256** — on all 5 carriers |
| `tex_deriv.dstsrc` | `0x3FFFF`, `0x7FFFF` (all-ones patterns) | 39 of 65 sampled — on all 4 arms |
| `imageblock_store.src` | `src = 246, 247` | 248 of 256 — on both arms |

`MAX_HANGS_PER_FIELD = 2` stopped each field as §8 requires, so no arm ran away — but the *area*
`frame_marker_compact.b1` hung twice on the FIRST carrier and I let it repeat on four more, which is
against the spirit of §8 even though the per-arm limit held. **Correction applied to `run02`:
`frame_marker_compact` is EXCLUDED**, and `frame_marker_compact.b1` is reported as a
**single-run PARTIAL (8/256), NOT promoted**, with the hang region documented as the result. It
could not have been promoted at 8/256 coverage, so re-running it would have cost the device ~10 more
resets for no evidential gain. `ret` is also excluded from `run02`: promotion was declined in
advance and its arm was drowning in `InnocentVictim` retries.
