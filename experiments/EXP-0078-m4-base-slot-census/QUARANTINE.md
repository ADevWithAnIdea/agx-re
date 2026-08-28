# EXP-0078 quarantine record

Status: **QUARANTINED / NON-EVIDENCE** (2026-08-27).

MEM-15..MEM-17 base-slot census. `raw/m4-20260827-run01` captured complete and
internally consistent (351/351 cases `ok`, zero faults/timeouts/watchdogs, smoke
gate passed, probe identification recorded pre-capture). The frozen post-capture
verifier then cannot close it: `verify.py --between-runs` fails permanently with
`FAIL ident probe opcode m4-20260827-run01 storeprobe` — a defect in the frozen
verifier's identification check, not an observation.

Post-capture repair is forbidden (the frozen `CAPTURE_CONTRACT.json` binds the
verifier hash, recorded in `raw/m4-20260827-run01/00_inputs.json`; repairing it
is the EXP-0064/0072/0073/0075 quarantine class). Run 01 is therefore retained
append-only as single-run, repeat-unverified process history: **no MEM-15/16/17
claim may be promoted from it.** Its observations are hypotheses for the
successor to re-register and falsify.

Successor: **EXP-0083-m4-base-slot-census** — same frozen design, with the
identification check fixed (opcode taken from the recorded probe rather than
re-derived), a selftest fixture that exercises the ident path in the
run01-present state, and the standing gate set.

```text
Clean-room status: quarantined process history; no MEM-15..17 claim
Apple binary introspection: NONE
Raw retention: append-only, non-evidence (single run)
Successor: EXP-0083-m4-base-slot-census
```
