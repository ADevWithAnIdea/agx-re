# EXP-M4-09 / CMD-2 — Stencil ops 0–7 on all three op fields

**Gap (CMD-2):** EXP-0019 swept all 8 stencil ops on the PASS field only; sfail/zfail
were tested with just 2 of 8 ops. The doc's shared stencil-op enum (0–7 =
keep/zero/replace/incrClamp/decrClamp/invert/incrWrap/decrWrap) across pass/zfail/sfail
was an assumption for sfail/zfail.

**Hypothesis:** all three op fields of the `0x58000+0x3c` (front) / `+0x44` (back)
stencil word share one 0–7 enum at bit positions pass[18:16], zfail[21:19],
sfail[24:22].

**Method:** DATA-TRACE (iotrace) + OWN-SHADER (svar.m draw). Sweep each op field
independently through all 8 ops, holding the other two at `keep`, with an active
`--scmp less` compare to keep the packet enabled; extract & decode the +0x3c/+0x44
words. Runs on the LOCAL Apple M4.

**Clean-room:** no Apple binary or shader-code BO inspected — only registered
state-pool bytes.

**Result:** CONFIRM for all three fields + back-face. See `RESULTS.md`.

Files: `svar.m` `iotrace.c` `bodiff.py` (copied harness), `run.sh` (driver),
`extract.py` (decoder), `caps/` (raw text hex dumps + stdout), `analysis/` (table +
isolation diffs). Text logs only — never committed by this subagent.
