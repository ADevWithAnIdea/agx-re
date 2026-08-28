# PROGRESS — EXP-0093

All times approximate, local M4 host, single session, 2026-08-28.

- **T0** Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
  `work/ADDENDUM-TRIAGE-20260828.md`, `APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md`
  (GLFS-A08), `APPLE9_RE_IMPLEMENTATION_GAPS.md` (ATOM-07..11), and the four
  predecessor experiments (`EXP-0085`, `EXP-0091`, `EXP-0051`, `EXP-0025`) plus
  `docs/isa/register-move-and-liveness.md`'s methodological warning. No device
  work yet.
- **T1** Read `tools/agx-isa/db.json`'s current `0x07`-family entries
  (`threadgroup_barrier`, `mem_fence`, `scoreboard_fence`, `dev_scoreboard_fence`,
  `mem_fence8`, `compute_fence_scoped`) and `EXP-0029-fragment-isa/RESULTS.md`'s
  `pixel_order` finding to establish the known-bytes baseline before touching the
  device.
- **T2** Built `tools/shdump`/`tools/agxtest` binaries into `work/bin/`. Own-compile
  reproduced `EXP-0029`'s `rog.metal`/`rog_none.metal` byte-for-byte on this
  toolchain; located the ACQUIRE (`07 14 54 50 06 00`) / RELEASE (`07 04 54 d0 06
  00`) pair exactly as EXP-0029 described.
- **T3** Own-compile census: `raster_order_group` index sweep (compile-only, no GPU)
  found index ∈ {0,1,2} compile to distinct bytes, index ≥3 (through 65535) alias
  byte-identical to index 0. Compiled `mem_texture` `threadgroup_barrier` directly
  (compute stage) and found it is a genuine ACQUIRE(`sub=0x14`)/RELEASE(`sub=0x04`)
  PAIR — corrects the existing `db.json` provenance note, which recorded `sub=0x04`
  for both members of that pair.
- **T4** Wrote `harness/roglitmus.m` (fragment ROG litmus + splice runner), built it,
  smoke-tested the strong/weak texture and buffer RMW-count invariant interactively
  at N=16/4096/65536: strong always exact N; weak always collapses to ~1-2.
- **T5** Wrote `harness/splice.py`, produced spliced archives neutering the
  texture-ROG acquire/release scope bytes and the buffer-ROG fence/bracket bytes;
  interactively confirmed the causal splice results that seeded `PRE_REGISTRATION.md`
  H-ROGTEX/H-ROGBUF (including the buffer-case surprise: the bracket-open ops, not
  the `07 04 54 c4 08 00` fence, carry the mutual-exclusion effect).
- **T6** Wrote `harness/fencelitmus.m` (compute device-fence pairs), reproducing
  `EXP-0051`'s 0-violation result at `PAIRS=1,2` and finding a real, large-magnitude
  violation at `PAIRS≥4` for the fully-relaxed case, 0 violations for the
  fully-fenced case — interactively, before freezing the matrix.
- **T7** Ported `EXP-0025`'s `tgdiv2` convergence kernel to device memory
  (`kernels/tgdiv2_dev.metal`) and to `mem_none` (`kernels/tgdiv2_mem_none.metal`);
  via `tools/agxtest/agxtest.py` (read-only tool usage) confirmed bidirectional
  splice causality on `byte+3` bit0 (`0x85↔0x84`) for `ATOM-10`, and full convergence
  under `mem_none` for `ATOM-09`.
- **T8** Wrote `harness/schema.py`, `harness/casematrix.py` (128-case frozen matrix,
  every case's expected verdict frozen from the T3-T7 build-time probing), `run.py`,
  `verify.py` (5 standing gates). Captured `harness/fixtures/recorded_reality.json`
  from two real GPU dispatches (gate (e): selftest fixtures grounded in recorded
  reality, not hand-typed constants).
- **T9** `verify.py --selftest`: 11/11 PASS. `verify.py --seqtest`: 7/7 PASS.
- **T10** Wrote `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` (pinned revision
  `14017e25641402e10f98100d1a3696175fc0e982`, 0 tracked modifications).
- **T11** `verify.py --preflight`: PASS (empty raw/). Ran
  `python3 harness/run.py --run m4_20260828_run01 --out raw/m4_20260828_run01`:
  smoke gate PASS, 128/128 cases OK/PASS, zero faults, zero hangs, zero timeouts.
- **T12** `verify.py --between-runs`: PASS. Ran
  `python3 harness/run.py --run m4_20260828_run02 --out raw/m4_20260828_run02`:
  128/128 cases OK/PASS, zero faults/hangs/timeouts, byte-identical smoke gate.
- **T13** `verify.py --captured m4_20260828_run01 m4_20260828_run02`: cross-run gate
  PASS, 0 issues, both runs 128/128 PASS. Spot-checked that the declared
  order-sensitive keys (`devfence_pairs` race counts, `rogbuf_splice_brackets_only`/
  `_all` final counter values) genuinely DIFFER between the two runs (proving the
  exclusion mechanism is doing real work, not vacuously matching) while every
  gated field (verdict, status, exact-invariant cases) is byte-identical.
- **T14** Wrote `README.md`, `manifest.json`, `RESULTS.md` (this milestone),
  `PROGRESS.md`. No host wedge, no reboot, no BLOCKED state at any point in this
  session. 256 total real GPU dispatches across both runs, 0 faults.
