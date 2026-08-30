## 4. EXP-0202 — `irotate.operands`, `ibitcount.cache`, `ibitcount.dst`, `cvt_f2i._instruction`

**Three captures, and only the last two are the pair.**

| capture | run id | order | result |
|---|---|---|---|
| `e0202_q01` | `g17p_quiet01` | forward | 10596 records, 807.7 s. Q1 = 0 foreign runners, Q3 = no foreign submitter — but **`recoveryCount` 12977 → 15096, +2119**. Frozen refuter **R1 fires**. Retained, never reused, **supports no verdict**; it is what forced AMENDMENT-03. |
| `e0202_q03` | `g17p_quiet03` | forward | 10596 records, 803.4 s, 397 samples. **QUIET** under A03 (Q1 0, Q2a pass, Q3 no foreign submitter, Q4 ok). Q2b **+2118**, all ours. |
| `e0202_q04` | `g17p_quiet04` | reverse | *(see table below)* |

### 4.1 The device-reset finding, which is the most useful thing this capture produced

> **A single EXP-0202 capture resets the G17P about 2100 times in roughly 13 minutes**, on an
> otherwise idle machine, deterministically: `g17p_quiet01` +2119 and `g17p_quiet03` +2118.

Those resets come from EXP-0202's own pre-registered fault regions — `ibitcount.dst` 192..255
and `irotate` byte+3 192..255, the two mapped hazard walls, plus the `(v & 7) == 7` class. The
fault counts are byte-for-byte reproducible: comparing the quiet forward capture against the
**committed busy** `run03`, the hard-outcome tallies are **exactly equal** — 706 `fault`,
2 `invalid_run`, 196 `not_written` in each — with **10590/10590 actual bytes identical** and
**9686/9686 = 100.00 %** payload agreement.

Two consequences, both worth carrying forward:

1. **EXP-0202's faults are hardware, not contamination.** They reproduce identically with no
   other GPU client on the machine.
2. **This family of sweeps is, by itself, a large reset source for everyone else.** Every
   device reset discards in-flight command buffers in other contexts — the documented
   mechanism behind `kIOGPUCommandBufferCallbackErrorInnocentVictim`. `recoveryCount` was not
   sampled during the 2026-08-30 fan-out, so this cannot be attributed retrospectively; but
   ~2100 resets per capture is a concrete reason the concurrent wave saw victim streaks, and
   a concrete reason to keep this experiment off a shared machine.
