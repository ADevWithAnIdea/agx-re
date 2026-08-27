# EXP-0075 quarantine record

Status: **QUARANTINED / NON-EVIDENCE** on 2026-08-27 (terminal disposition
recorded by the orchestrator; the agent's RESULTS.md STOP banner is the
primary account).

## What happened

Both dispatched fixes worked: the non-recorded smoke gate caught a real
pre-capture defect on its first invocation (regenerated kernel header had
dropped `#include <metal_stdlib>` — exit 3, `library_failed`, no `raw/`
created), and after an authorized pre-capture repair, run 01 captured
**clean and fully verified**: 37 files, 34/34 cases exit 0, zero truncation
(records 1801–1857 bytes — the EXP-0072 defect class is gone), all guards
intact, `--between-runs` PASS, `make_manifest.py --check` PASS.

The contracted second run is then **structurally unreachable**: the frozen
`pre_second_run_gate` sequence (`verify.py --between-runs` →
`verify.py --selftest`) is self-contradictory — `--between-runs` requires
`raw/` to exist, while `--selftest` is implemented and contracted as a
PRE_GPU-only check that fails on the closed-root check once `raw/` exists.
No possible execution satisfies the contract. The landmine was inherited
from EXP-0072 (which never reached run 02) and is invisible to per-gate
self-tests; only a **gate-sequence state-machine self-test** catches it.

Repairing `verify.py`/`run.py` post-capture would break the capture-time
hash binding in `raw/m4-20260827-run01/00_inputs.json` (the
EXP-0064/0073/0072 quarantine class), so no repair was made.

## Disposition

- `raw/m4-20260827-run01/` is retained append-only as process history. It
  is **single-run, repeat-unverified**: no DRV-FMT-01/P1.2 claim may be
  promoted from this experiment. Its observations (25/34 expected-word
  matches; candidate findings: snorm encode = round(c×127) symmetric scale;
  reduced-float store narrowing (fp16/fp11/fp10/RGB9E5) truncates toward
  zero) are hypotheses for the successor to re-register and falsify, not
  facts.
- Successor: **EXP-0079-m4-typed-format-conversion-batch2** (not EXP-0077
  as guessed in RESULTS.md — EXP-0077 = MEM-01..05 offset-semantics
  splices and EXP-0078 = base-slot census are already committed to the
  user-directed load/store/SSBO priority cluster; the format re-run queues
  behind them). Successor requirements: (1) make `--selftest` runnable in
  the run01-present state; (2) add the mandatory gate-sequence
  state-machine self-test; (3) re-register the same 34-case matrix with
  corrected expected words and the truncation findings as
  hypotheses-to-falsify; (4) add half-even vs half-up separator values
  (1.5/255, 2.5/255) and a positive-direction fp16 truncation probe.

```text
Clean-room status: quarantined process history; no DRV-FMT-01 claim
Apple binary/code/archive/BO/compiled-shader-byte inspection: NONE
Raw retention: append-only, non-evidence (single verified run)
Successor: EXP-0079-m4-typed-format-conversion-batch2
```
