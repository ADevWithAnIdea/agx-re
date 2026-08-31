# EXP-0221 — progress (per CLAUDE.md's incremental-progress rule)

| milestone | state |
|---|---|
| harness forked from EXP-0220, offline gates T0..T5 | PASS, 7,160 cases, 0 failures |
| threadgroup carrier + no-threadgroup control carrier authored | done |
| DISCLOSED PRE-FREEZE PILOT (tgpilot stages 1, 4..9) | done, `work/pilot/` |
| PRE_REGISTRATION.md + CAPTURE_CONTRACT.json frozen | done, before the first gated dispatch |
| gated run01 (canonical, tile carrier) | 7,160 cases, 0 hangs |
| gated run02 (shuffled seed 221, tile carrier) | 7,160 cases, 0 hangs, 0 disagreements vs run01 |
| gated notg (control carrier, arms D2/T0..T4/CTL) | 1,178 cases, 0 hangs |
| census (rebuild + sha256 vs raw) | 14,320 programs, 0 mismatches, COPIED 0, CARRIER 0 |
| gates A/B/D/E | PASS; C fails on 415 pre-registered model errors, left failing |
| post-freeze exploratory stage 10 | 1,596 cases, 0 deliveries (disclosed, not evidence) |
| RESULTS.md / README.md / field_verdicts / generated_recipe | done |

**Nothing committed. No label, `tools/agx-isa/`, `docs/` or `PROVENANCE.md` touched.**
