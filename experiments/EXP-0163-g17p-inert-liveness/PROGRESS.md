# EXP-0163 — PROGRESS (append-only)

Target: **A18 Pro / G17P**, `users-MacBook-Neo.local` @ 192.168.10.243.
Device work under `~/agxre/EXP-0163/` on the neo; every artifact pulled back here.

## 2026-08-30 — M0: brief read, target list re-derived independently

- Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
  `experiments/FIELD-SWEEP-PROTOCOL.md`, and EXP-0155's
  `README.md` / `PRE_REGISTRATION.md` / `harness/casematrix.py` /
  `harness/runner.py` / `run.py` / `harness/gfrun.m`.
- Re-derived the never-moved field list MYSELF from EXP-0155's two gated runs
  (`analysis/audit_0155.py`, output `work/audit_0155_move_counts.json`).
  Method: over `raw/g17p_20260829_run03/sweep.jsonl` and `..._run04/sweep.jsonl`,
  drop the `_`-prefixed pseudo-fields, count per `(instr, field, carrier)` how
  many swept values had `match == false`.  `match` takes only `true`/`false` in
  those files (49098 / 56840), so "match is not True" and "match is False" are
  the same count.
- **Result: 22 fields, not 20.**  All 20 dispatched fields reproduce exactly,
  with the same carrier counts.  Two MORE fields also never moved anything and
  were not on the dispatch list:
  `op57_fragment.byte2` [2 carriers] and `op57_vertex.byte2` [2 carriers] —
  the H3 / 0x57-collision probe arms of EXP-0155, which are byte probes rather
  than db.json fields.  Reported to the orchestrator; they are carried as
  secondary targets here.
- Connectivity to the neo confirmed (`hostname`, `sw_vers` = 26.6).
  `~/agxre/gpulease.sh` is the neutralised no-op shim; concurrency unrestricted.

Next: M1 — author carriers + census them on the neo (pre-freeze calibration).

## 2026-08-30 — M1: carriers authored, census run, contract FROZEN

- Authored **27 MSL carrier programs** (29 carrier configurations; `k_cent.metal` and `k_ibsamp.metal` are each built under two different pipeline descriptors) (`kernels/k_*.metal`), each targeting a specific
  structural gap in EXP-0155's carrier set; forked EXP-0155's `gfrun.m` into
  `harness/gfrun2.m` adding a layered (`texture2d_array`) colour attachment,
  array / 3D / half / uint writable textures, and OUTBUF reporting for render
  passes (needed as the primary observation for multisampled arms).
- **Pre-freeze census** (`analysis/census.py`, three passes, all in
  `raw/prefreeze/`).  `census_run1` recorded five carriers that did not build:
  the free-function `interpolate_at_*` spelling does not exist (the pull model is
  the `interpolant<>` member API), a `[[clip_distance]]` array cannot sit in a
  `stage_in` struct, `quad_ballot` returns `quad_vote` not `simd_vote`, and a
  layered target needs `inputPrimitiveTopology`.  All fixed; `census_run3` builds
  all 26.
- Census findings that already refute the "inert" reading structurally:
  `vary_store.hint2` takes **0x54 / 0x55 / 0x56** across the new carriers (one
  value in EXP-0155's single carrier); `hint6` takes 0x48..0x4d;
  `tex_write.amode` takes **0x55** on the last write of each program, not only
  0x54; `tex_coord_setup` appears in **three** distinct `form` values (0x00, 0x10,
  0x42) with `idx` up to 0x94 and `b5`/`b8` non-zero, versus one form with
  everything zero; `simd_shuffle.rsv9` is **0xa1 / 0x91** in the mode-0x06
  rotate/fill form; `frag_tile_setup.sel` takes eight distinct values.
- **Detection-profile smoke** (`work/smoke_smoke01`, 992 cases, 99 s): 63 of 64
  arms have strict detection power.  It also caught `run.py` and `census.py`
  disagreeing on occurrence indices for three `cent4` arms — `run.py` now
  mirrors the census's tokenize-prefix-then-scan rule AND asserts the frozen
  census bytes, so a shifted occurrence is a recorded error, never a silently
  wrong arm.  Two more carriers added afterwards (`ibms4`, `sball`).
- **`PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` frozen.** 72 arms, 28
  carrier configurations (`twrt` was added later, under Addendum A), 20 db.json fields + 2 byte probes, repo revision 33f0aa825a76.
  ~39,900 dense sweep cases per gated run.

Next: M2 — the two gated runs.

## 2026-08-30 — M2: gated run01 complete; PAUSED for a coordinated quiet window

- `raw/g17p_20260830_run01/` — 39,233 cases, 50.3 s, **0 confirmed hangs, 0
  cascades, 0 runner restarts**, 88 of 39,233 cases non-OK.  Pulled back to the
  repo immediately.
- Outcomes: 32,452 `ok` (unchanged), **5,744 `wrong_value` (moved the
  observation)**, 687 detection-profile `moved`, 278 detection-profile `inert`,
  71 arms `has_power`, 1 arm `no_power` (`iter@vmany/fragment#0`).
- COURTESY / SAFETY NOTE: one detection-profile step,
  `iter_at@cent1/fragment#0` with `grp=0x50` (re-decodes as no known mnemonic),
  produced a real `kIOGPUCommandBufferCallbackErrorHang` at ~00:42.  Contained;
  the runner continued.  Recorded here because a device reset is visible to
  every other agent on the machine.
- **Orchestrator requested a coordinated quiet window for EXP-0167.  Went quiet
  immediately after run01 landed; nothing was killed mid-capture.**  run02 (the
  confirmation run, ~5-10 min of device time) is deferred until the window
  closes — which is also the right ordering under the new FIELD-SWEEP-PROTOCOL
  §7 amendment that confirmation runs need a quiet machine.

Next: M3 — analysis of run01 (offline), then run02 when the window closes.

## 2026-08-30 — M3: run01 analysis (offline, device quiet)

Integrity checks on `raw/g17p_20260830_run01`:
- **156 (arm, field) sweeps, all complete**: 148 dense 256-value + 8 two-value
  (`simd_shuffle.cache` is 1 bit wide).  37,904 sweep cases + 1,329 baseline /
  detection-profile records = 39,233.
- **Zero baseline failures** — no `_baseline_recheck` or `_baseline_final`
  mismatch on any of the 72 arms.
- 71 of 72 arms pass the STRICT detection gate (status OK + observation changed
  + still decodes as the arm's mnemonic).  The one that does not is
  `iter@vmany/fragment#0`; it is excluded from every verdict.
- **Reproducibility measured directly**: comparing the pre-freeze smoke against
  run01 over the 962 detection-profile cases they share gives **exactly one
  disagreement** — `tex_write@twdim/fragment#1 amode=0xab`, and the raw shows
  the smoke scored it `moved` only because that command buffer returned
  `kIOGPUCommandBufferCallbackErrorHang`.  Both runs' OK-status observations
  agree.  **This exposed a classification defect in run.py's in-run detection
  predicate** (`not same_obs`, where `same_obs` requires both statuses OK, so a
  FAULT scores as "moved").  `analysis/verdicts.py` now recomputes the gate from
  the raw records instead of trusting the in-run summary; the raw is untouched.
  Recomputed strictly, the gate is unchanged at 71/72.
- **88 of 39,233 cases were non-OK, all inside the detection profile, none in a
  target-field sweep**: 84 `ErrorHang` + 4 `ErrorPageFault`, no `InnocentVictim`
  at all.  They come from complementing register/operand fields (`grp`, `dst`,
  `src`, `b5_tag`, `hint1`, `form_sig`) into out-of-range registers.  **No value
  of any of the 20 target fields faulted, on any arm.**

Exact per-bit rules derived (`analysis/rules.py`, provisional pending run02):
- `iter_at.loc` — **bit1 alone**; two equivalence classes of exactly 128 values;
  bit0 and bits 2..7 are don't-cares (0x81 behaves as 0x01, 0x83 as 0x03).
  0/256 on the 1-sample control `cent1`, 128/256 on `cent4`, `ms4cent`,
  `ms4out`, `atoff4`.
- `vary_store.hint6` — **bit4 alone** moves, on all seven live arms.
- `tex_coord_setup.idx` — **bit7 alone**, on the byte+4==0x42 form.
- `tex_coord_setup.b8` — **bit3** (plus bit4 on two arms).
- `tex_coord_setup.b5` — bits 0,1,2,4 (+3 on the 0x42 form); `b6` — bits 2,3,4,5.
- `simd_shuffle.rsv9` — bits 1,2,6,7 on the mode-0x06 rotate/fill form,
  8-10 equivalence classes.

`ADDENDUM A` pre-registered and carrier `twrt` authored: `tex_write.amode` /
`rsv11` were inert on all six arms but those come from only TWO source programs,
one short of the ≥3-carrier bar, and both share the property that every write
uses a constant compile-time coordinate.  `twrt` writes with runtime coordinates,
texture-provenance data, inside a loop, and to a 3D destination with runtime
depth.  Its own paired runs (run03/run04) are queued behind the quiet window.

Device work still PAUSED.  Queued: run02 (frozen contract, ~1 min device time,
expected to produce ~88 contained GPU hangs in its detection profile), then the
addendum pair.

## 2026-08-30 — M4: write-up complete for run01 (device still quiet)

- `analysis/verdicts.py` (buckets + strict detection gate recomputed from raw),
  `analysis/rules.py` (exact per-bit liveness + equivalence classes),
  `analysis/emit_verdicts.py` (the FIELD-SWEEP-PROTOCOL §5 flat schema),
  `analysis/report.py` (the machine-generated verdict tables),
  `analysis/manifest.py` (artifact hashes) — all committed and runnable.
- `analysis/field_verdicts_flat.json` is the deliverable: flat dict keyed
  `<mnemonic>.<field>` with `label` / `target` / `evidence` / `range` / `note`
  plus `bucket`, `semantics`, `emitter_guidance`, `live_bits`, `exact_rules`
  (per arm: rule, live bits, equivalence-class sizes, per-run counts,
  cross-run identity), `inert_arms` (per arm: values swept, and the NAMED
  controls that proved that arm could see a change), and `db_defects`.
- `RESULTS.md` written, marked **[1-RUN] PROVISIONAL** throughout.
- `db_defects` recorded: (a) `frag_color_store` with byte+1 == 0x86 is decoded
  by db.json as a 14-byte compute `device_store` — carrier `texcube` emits it and
  that fragment has no writable device buffer, so every frag_color_store census
  silently omits this variant; (b) `simd_shuffle` byte+2 is modelled as ONE bit,
  so the `simd_shuffle.cache` negative covers one bit, not the byte; (c) the
  suspected 12-byte rotate-form length is NOT a defect — checked, db decodes
  10 bytes plus a 2-byte `n2_compact2` and the stream stays consistent; the open
  question (is that trailing `0200` part of the op?) is recorded instead.

Device work still PAUSED, awaiting the orchestrator's all-clear.  Queued, in
order: run02 (frozen contract, ~1 min, ~88 contained GPU hangs expected), then
the Addendum A pair (run03/run04, `--mnem tex_write`, ~1 min).

## 2026-08-30 — M4b: secondary byte probes resolved; still quiet

- `op57_vertex.byte2` is bit range [16:24] of the 8-byte vertex form ==
  `vary_store.hint2`, so it IS one of the 20 fields and is covered:
  INERT-ROBUST over 9 arms on 5 carriers.
- `op57_fragment.byte2` is **NOT covered by EXP-0163** and RESULTS.md says so
  plainly: no carrier here emits the 6-byte fragment kill/target-mask op (none
  of the 26 uses `discard_fragment()` or `[[sample_mask]]`), and a byte scan of
  every fragment program finds no 0x57 opcode byte at all.  A successor needs a
  kill/mask carrier.
- Re-derived from EXP-0155's own raw while checking: its 0x57 arms DID have
  detection power on both stages — `byte1` moved 448/512 (vertex) and 384/512
  (fragment) across its two runs while `byte2` was 512/512 inert on all four —
  so its H3 is refuted for byte+2 on both stages by its own evidence.
- Full analysis chain re-run clean from the repo:
  `verdicts.py` → `rules.py` → `emit_verdicts.py` → `report.py` → `manifest.py`.
  `work/` cleaned of transfer archives.

Still PAUSED on the device.  Nothing of mine is running on the neo.
