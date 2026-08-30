# EXP-0179 — PROGRESS (append-only; newest last)

Rule: one timestamped entry per milestone. On resume, re-orient from THIS file,
`CAPTURE_CONTRACT.json` and what is actually in `raw/` — never from memory.

## 2026-08-30 — M0 START: analysis + carrier design (no device contact yet)
- Read `CLAUDE.md`, `CODEX.md`, `SUBAGENT_BRIEF.md`, `FIELD-SWEEP-PROTOCOL.md` (§3 five
  rules, §7 concurrency + confirmation exception).
- Read the gap: `docs/P0-P1-CLOSURE.md` P0.8, `EXP-0177/analysis/p08_gaps.md` G2.
- Located the PRIOR ART that EXP-0156 did not have: **call carriers already exist in this
  repo.** `EXP-0035/kernels/{direct_call,chain,abi,fptr_table,fptr2,dylib_*}.metal` and
  `EXP-0038/kernels/frame.metal` all compile `__attribute__((noinline))` helpers into real
  out-of-line calls, and EXP-0035 HW-validated dispatch through them on G17P.
  **So milestone 1 of the dispatch ("get the compiler to emit a call at all") is very
  likely already solved; the census still has to be run and reported on the CURRENT G17P
  toolchain.**
- Picked the harness lineage: `EXP-0174-g17p-n3mov/harness/{isa_helpers,sweeprun,run}.py`
  (SYNTH carrier = the whole `_agc.main` replaced by a program we assemble; poisoned
  read-back; PRE/POST sentinels; tail poison; blind/pad-masked slot bookkeeping).
- Repo revision at design time: `12e059e5aab38258c55ce490a01e146e6fae30d9`, clean.
- Pinned `work/frozen/db.json` sha256 `a77f8cfa163fcf720c0c1093e4ddc5815ceb43c218bb64a87c86d3dcf975dc22`
  (172 instructions / 1036 fields) and `isadb.py` `9cda47a1…`. NOTE this is NOT the same
  db.json EXP-0174 pinned (1062 fields) — EXP-0175's defect corrections landed in between.
  Fail-closed resolution, no path search.
- NO DEVICE CONTACT YET. Waiting for the orchestrator's go (EXP-0169 hang-prone sweep +
  EXP-0178 queued ahead of us).
