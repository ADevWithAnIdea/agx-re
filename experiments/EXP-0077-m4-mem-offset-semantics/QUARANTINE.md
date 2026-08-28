# EXP-0077 quarantine record

Status: **NON-EVIDENCE / TERMINAL PROCESS HISTORY** (2026-08-27).

MEM-01..MEM-05 splice experiment. All pre-capture gates passed (`--selftest`
19/19, the then-new `--seqtest` gate-sequence state machine 14/14,
`make_manifest --check`, `--preflight`) and three authorized non-recorded
plumbing validations proved the M4 splice mechanism works (unspliced load →
`a[64]=0x3CA50040`; spliced `idx_off=+1` → `a[65]=0x3CA50041`). The run then
crashed at the in-run smoke gate before any recorded observation existed.

No raw observation was produced; nothing may be cited. Retained append-only as
the record of the crash class and of the working splice plumbing.

Successor: **EXP-0080-m4-mem-offset-semantics** (smoke-case key set completed;
smoke gate moved BEFORE any `raw/` artifact so a smoke defect burns no run id —
EXP-0075's lesson made structural; unexpected sweep exceptions write STOP.json).

```text
Clean-room status: no recorded observation; process history only
Apple binary introspection: NONE
Successor: EXP-0080-m4-mem-offset-semantics
```
