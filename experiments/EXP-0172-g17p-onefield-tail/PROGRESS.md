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
