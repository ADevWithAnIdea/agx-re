# EXP-0080 quarantine record

Status: **QUARANTINED / NON-EVIDENCE** (2026-08-27; see dating note below).
**Dating note (orchestrator, 2026-08-27):** this record was originally dated 2026-08-28 because the capture run-id was stamped `m4-20260828-*` across the UTC midnight rollover. The authoritative capture timestamps inside `raw/*/00_inputs.json` and `02_build.json` read `2026-08-27T23:56:51`; local host time was 2026-08-27 PDT. The raw directory names are left unchanged — they are bound by the frozen contract hashes and are append-only evidence.


MEM-01..MEM-05 splice experiment; successor to EXP-0077. Its first launch
stopped cleanly at the smoke gate with **no burned run id**, catching two real
runner defects (splice offsets were instruction-relative instead of
main-relative; readback hex parsed big-endian) — both repaired under the
authorized pre-capture path. One complete capture run followed, but it is
**single-run and repeat-unverifiable** under its own frozen contract, so no
MEM-01..05 claim may be promoted from it.

Post-capture repair is forbidden by the `00_inputs.json` hash binding (the
EXP-0072/0075 quarantine class). Retained append-only as process history.

Successor: **EXP-0081-m4-mem-offset-semantics** — `run.splice_case` takes the
probe main offset as a parameter, giving runner, verifier and synthetic-tree
builder a single shared definition of the MAIN-relative splice form, plus a
selftest mutation (`splice_instruction_relative`) proving the per-line check
rejects the instruction-relative form.

```text
Clean-room status: quarantined process history; no MEM-01..05 claim
Apple binary introspection: NONE
Raw retention: append-only, non-evidence (single run)
Successor: EXP-0081-m4-mem-offset-semantics
```
