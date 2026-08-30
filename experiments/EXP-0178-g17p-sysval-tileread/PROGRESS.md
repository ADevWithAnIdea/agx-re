# EXP-0178 — PROGRESS

Append-only. One entry per milestone. Assume the session can be killed at any moment;
on resume, re-orient from this file, `CAPTURE_CONTRACT.json`, and what is actually in `raw/`.

## 2026-08-30 — M0: reading and analysis (no device, no SSH)

- Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
  `experiments/FIELD-SWEEP-PROTOCOL.md` (incl. the five rules added 2026-08-30: §3a
  co-variation, §3b round-trip-is-not-a-gate, §3c contiguous-hazard mapping pass, §7
  unlocked-sweeps/quiet-confirmation, §8 safety).
- Read the two source experiments the dispatch names:
  - **EXP-0092** (`get_sr` `srsweep`, M4, exhaustive 0x00–0xFF × 2 gated runs) — carrier
    `kernels/srprobe.metal`, grid=64/tg=64, later-read discipline via a separate `iadd2`
    and a third separate `device_store`.
  - **EXP-0147** (`tile_read`/`tile_read_mrt`, M4, 25,064 cases × 2 gated runs) — carriers
    `kernels/pipe_render.metal::f_tile`/`f_mrt`, harness `rendersweep.m` + `rsdrv.py` +
    `shdump2.m`, litmus-power probe, integrity sentinel, collateral-vs-fault classification.
- Read the blocking status in `tools/agx-isa/validation.json` (as of `generated: 2026-08-28`,
  `db_sha256 a77f8cfa…`) and `experiments/EXP-0177-p08-abi-assembly/analysis/p08_gaps.md`
  (gaps **G1** and **G6**).
- **Ran `python3 tools/agx-isa/match_overlap_report.py`** on the targets, as the dispatch
  requires. RESULT: **none** of `get_sr.*`, `tile_read.*`, `tile_read_mrt.*` appears in the
  34-field overlap list. Every field under test has its full nominal encodable range;
  none is a one-legal-value pseudo-field. Recorded in `PRE_REGISTRATION.md` §3.
- Root-caused **why EXP-0169's G17P `get_sr` arm produced `untested`**: its `k_sr` probe was
  *lifted* into a synthesized program run at **grid=1 / tg=1**
  (`harness/casematrix.py:78` states the relaxation explicitly), where essentially every
  reachable SR reads 0. `L_sr_sel` therefore could not move and the ladder failed. The fix is
  a dispatch geometry and a carrier in which distinct SRs produce distinct host-computable
  patterns — which is exactly what EXP-0092 used and what this experiment restores on G17P.

## 2026-08-30 — M1: pre-registration drafted (no device, no SSH)

- `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` written and frozen (see M2).
- `kernels/`, `harness/`, `analysis/` authored. `pinned/` populated with this experiment's
  OWN copy of `isadb.py` + `db.json`, sha256 recorded in the contract; the harness resolves
  that pair by absolute path and **exits non-zero if it is absent** (no path-search fallback).
- **Courtesy notice (FIELD-SWEEP-PROTOCOL §7):** the `tile_read.dst` / `tile_read_mrt.dst`
  arms sweep byte+3 over 0..255. EXP-0147 recorded `fault` at 0xf6–0xff on M4; on G17P the
  analogous register-ceiling crossings **hang** (EXP-0155, seven fields). Hangs are possible
  in that region. `get_sr.dst_hi` is deliberately **NOT swept** for the same reason (values
  6–7 select registers ≥96).

## Status

- **BLOCKED ON GO.** EXP-0169 is running a hang-prone `device_store.base_slot` sweep and
  must not have neighbours. No SSH, no build, no dispatch has been performed by this
  experiment. Nothing has been written outside `experiments/EXP-0178-g17p-sysval-tileread/`.
