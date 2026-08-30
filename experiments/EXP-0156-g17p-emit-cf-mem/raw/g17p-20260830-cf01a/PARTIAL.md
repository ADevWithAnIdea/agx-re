# RETAINED PARTIAL CAPTURE — `g17p-20260830-cf01a`

**Status: PARTIAL. Retained as append-only evidence. Its run id is never reused and it
is cited by no promoted verdict.** Successor: **`g17p-20260830-cf01d`**, a fresh run id
dispatching the identical arm set.

## What happened (recorded, not tidied away)

This chunk was launched from an interactive `ssh` session whose *local* wrapper timed out
after 120 s. The `ssh` client was killed; the remote `run.py` was **not** killed and kept
capturing (records grew 780 → 836 → 851 → 887 after the disconnect, which is how we know).
It then stopped advancing at **record 887** and stayed there for ~7 minutes.

The most probable cause is that the process blocked writing progress output to the pipe
whose reader (the dead `ssh`) was gone — the last record written is
`ret_luse.tail value=39`, `invalid_run`, fault class
`command buffer failed: Discarded (victim of GPU error/recovery)`, i.e. an
`...ErrorInnocentVictim` from a sibling agent's GPU error, which is exactly the point
where `run.py` prints. This is a **harness/transport** failure, not a hardware result.

The orphan was killed deliberately (`kill 3678`), which also released the GPU lease it was
holding and unblocked both this experiment's own batch and the other agents on the device.

## Why it is not repaired in place

`SUBAGENT_BRIEF.md`: *"A partial capture is retained, never reused. If a kill leaves a
half-finished run directory, leave it exactly as it is, note it, and capture under a NEW
id. Do not top it up, delete it, or reuse its id."*

## Lesson recorded for the successor

Every subsequent capture in this experiment runs under `nohup` on the neo with its output
redirected to a file on the neo, so no capture's liveness depends on an ssh channel
staying open.
