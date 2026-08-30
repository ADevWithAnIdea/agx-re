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
