# EXP-0154 — PROGRESS (append-only)

Target: **Apple A18 Pro / G17P**, `192.168.10.243`, remote work dir `~/agxre/EXP-0154/`.
Repo revision pinned at pre-registration: see `CAPTURE_CONTRACT.json`.

## M0 — 2026-08-29 — environment verified
- neo reachable; macOS 26.6, arm64, `Apple A18 Pro`; python3 **3.9.6** (harness must be 3.9-clean).
- `~/agxre/tools/{agx-isa,agxtest,shdump}` present and prebuilt.
- `tools/agx-isa/db.json` sha256 **identical** on repo host and neo:
  `f5db942f03c9ad3870a102e0e34f705217ffa7ea5883dd960d0ffec93e76e36e`;
  `isadb.py` `1d60d36d2da7b681028c201013a510603d8fb7909bb59186e7534296e3b6e0d1`.
- Repo `HEAD` at dispatch: `3a885d58c4d286eda61a8808029c8a7aecb1dfec`, working tree clean.

## M0.1 — target set computed from db.json x validation.json (not from the dispatch text)
133 blocking fields over 32 instructions. The dispatch's FALU counts were total-field
counts; the authoritative blocked counts are in `analysis/target_set.json`.

Key discovery while scoping: **`EXP-0146`'s verdicts were never merged into
`tools/agx-isa/validation.json`.** EXP-0146 (M4) already closes every field of
`carry_gen`, `iadd2`, `ilogic`, `irotate`, `mov_zext16`, `shift_amt_move`. Those six are
therefore "solved on G16G, unmerged, and never tested on G17P" — re-running them here
converts them to DIRECT G17P evidence, which is exactly the point of the pivot.

## M1 — 2026-08-29 — anchor extraction (first pass) — PARTIAL
`harness/anchors.py` on the neo compiled 26 of 27 authored probe kernels and tokenized
every one with **0 leftover bytes**, reproducing NEO-TARGET-BRIEF's claim that the
M4-built Apple9 DB tokenizes G17P code cleanly. Anchors found (own-MSL, G17P):

| probe | instruction under test | offset in `_agc.main` |
|---|---|---|
| `k_u64add` | `iadd2` + `carry_gen` + `psel` | 32 / 42 / 48 |
| `k_and`/`k_or`/`k_xor` | `ilogic` | 32 |
| `k_rot_imm` | `irotate` | 18 |
| `k_rot_var` | `shift_amt_move` | 76 |
| `k_zext16` | `mov_zext16` | 18 |
| `k_bfe` | `ibfe` | 18 |
| `k_ashr` | `ishift` | 18 |
| `k_imin`/`k_umax` | `iminmax` | 32 |
| `k_isel` | `isel10` | 52 |
| `k_imad` | `imad` | 32 |
| `k_loopcmp` | `icmp_pred` | 18 |
| `k_sat_add` | `falu2_ext` | 32 |
| `k_abs_add` | `falu2_srcmod10` | 32 |
| `k_fma` | `falu3` | 56 |
| `k_sat_fma` | `falu3_ext` | 56 |
| `k_fma_abs` | `falu3_srcmod12` | 56 |
| `k_sum` | `falu_acc` | 252/256/260/270 |
| `k_uni` | `falu2_uni` | 24 |

Negative/structural results already worth recording:
- `k_bfi` (`insert_bits`) does **not** emit `ibfins`; it emits `b_alu10_lof`. `ibfins`
  appears instead inside `k_rot_var` (variable rotate) at offset 42.
- `k_isel_small` (`a<b ? a : b`) is compiled to `iminmax`, not to a select.
- `icmpsel` did not appear in any of the 27 probes.

Crash: `harness/anchors.py` aborted on `k_half2` because `isadb.disassemble` returned a
record with `length is None`. Fixed in the next pass (recorded, not hidden).

## M2 — 2026-08-29 — scaffold validated on live G17P (`work/smoke/smoke.json`)
`harness/smoke.py`, 5 cases, device `Apple A18 Pro`, `_agc.main` region 2412 B:
- **S1** seeds/dump/sentinels all exact — except r13, which came back 90 because the PRE
  sentinel used r13 as scratch and never restored it. **Real bug, caught by the pilot,
  fixed** (`pre_sentinel_instrs(kind)` now restores the seed). Re-verified in run02/run03
  baselines: r13 = 127.
- **S2** every word that is not a register slot or a sentinel stayed `0xDEADBEEF`.
- **S3** `iadd2` lifted verbatim out of our own compiled `k_u32add` computed
  **r0 = 10 + 34 = 44 over OUR seeds** — H1 confirmed. And **r2 came back 0**: the srcB
  operand (`srcB_imm = 0x08` -> N = 2) was released-on-read. **H3 confirmed on G17P**;
  the trap that cost EXP-0138 six sweeps is now the operand oracle.
- **S4** sensitivity witness: byte0 -> 0x00 changed the observation.
- **S5** float scaffold: all 14 float seeds exact.

## M3 — 2026-08-29 — pre-registration + capture contract FROZEN
`PRE_REGISTRATION.md` sha256 `2d3dc826...`; `CAPTURE_CONTRACT.json` pins all 10 authored
blobs, the read-only tool hashes, the raw schema, timeouts and the promotion rule.

## M4 — 2026-08-29 — run01 launched, then STOPPED for throughput; matrix amended
Measured throughput on G17P is ~3.3 dispatches/s, dominated by per-request
`newLibraryWithURL:` + pipeline creation (profiled: our own Python is 0.2 ms/case for
program construction, 22 ms for a full-program round-trip). The v1 matrix (38,089 cases)
needed ~3.4 h per gated run. `run01` was stopped at **2,306 cases** and is **RETAINED
EXACTLY AS IT STOPPED** — not topped up, not reused, not deleted.
`CAPTURE_CONTRACT.json :: amendment_01` records the reduction to **23,267 cases**: dense
over every field that is BELOW emitter grade (the ones that decide emittability), sampled
(~30 boundary/power-of-two/interior values) over fields already at emitter grade, which
are only being confirmed on G17P and are never promoted from a sampled sweep.

## M5 — 2026-08-29 — gated pair launched CONCURRENTLY
`g17p_20260829_run02` (`--order forward`) and `g17p_20260829_run03` (`--order reverse`)
over the identical frozen v2 matrix, run at the same time in opposite arm order so they
are not hitting the same illegal encodings simultaneously. Sibling GPU experiments were
active throughout (EXP-0156 held `gpulease.sh`, plus one further `run.py`); this is
recorded per FIELD-SWEEP-PROTOCOL section 7.4 and every non-OK case carries the OS
fault-classification string.
