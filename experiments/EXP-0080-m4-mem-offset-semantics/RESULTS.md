# EXP-0080 results — M4 device_load/store memory-offset semantics (MEM-01..MEM-05)

**Status: TERMINAL PROCESS HISTORY — one complete but UNVERIFIABLE run
(single-run, repeat-unverified). Successor: EXP-0081-m4-mem-offset-semantics.**

## What happened (2026-08-28, honest record)

EXP-0080 inherited EXP-0077's complete frozen design and fixed its crash
(smoke case keys; smoke gate moved BEFORE any raw artifact; sweep exception
guard). The first launch stopped cleanly at the smoke gate — catching two real
runner defects with NO burned run id (splice offsets were instruction-relative
instead of main-relative; the readback hex was parsed big-endian). Both were
fixed in an authorized pre-capture repair (no raw existed; hash binding
legally refreshed). All gates re-passed.

`run01` then captured **completely**: 2164/2164 cases, all six raw artifacts,
no `STOP.json`, every control decoding exactly as hand-predicted
(`ld_ctrl_idx64→a[64]`, `st_ctrl_idx64→tgt[64]=0x5A17C0DE`, etc.), ~0.05 s per
case on the local M4.

The contracted `--between-runs` gate then failed with
`FAIL case splice consistency 7 (ld_idxreg_r1)`: `verify.py`'s per-line check
re-derives the expected splice arguments from the shared helper
`run.splice_case`, which returns **instruction-relative** offsets, while the
runner (correctly — the smoke gate had proven instruction-relative splices hit
the wrong bytes) records **main-relative** offsets (probe load at main+0x26).
The synthetic self-test could not catch this: its fabricated case lines were
built with the SAME wrong helper, so generator and checker agreed.

## Why this is not repaired in place

`raw/m4-20260827-run01/00_inputs.json` binds the SHA-256 of every authored
blob at capture time, including `verify.py`. Repairing the verifier now breaks
the no-drift binding — the EXP-0064/0072/0073/0075 quarantine class. The run
is therefore **single-run, repeat-unverified**: per the EXP-0075 precedent its
observations are retained append-only as process history and may seed
hypotheses for the successor, but no MEM-01..05 claim may be promoted from
this tree. The pre-capture matrix of EXP-0081 is byte-identical to this one
(frozen before any capture; not tuned from run01).

## Disposition

- `raw/m4-20260827-run01/` stays append-only, non-evidence. For transparency
  only: the completed sweep's status column was all-`OK` in the viewed control
  sample; no interpretation is offered here.
- Successor **EXP-0081-m4-mem-offset-semantics** adopts the design with the
  root fix: `splice_case` itself takes the probe's main offset (ONE
  definition, used by runner, verifier and synthetic-tree builder), and the
  self-test gains a mutation proving the per-line check pins the
  main-relative splice form (the gap that let this class through).

## Target and scope label

M4 / G16G, local host, public Metal API only. No A18 (G17P) inference; A18
hands-off. No M5 evidence. `macvdmtool` never used.

```text
Clean-room provenance: HW-PROBE / OWN-SHADER (one complete unverified run; non-evidence)
Inputs inspected: authored MSL (kernels/), authored harness/runner/verifier/analysis/
  matrix/baseline, and the compiled bytes of our own kernels only
Apple binary introspection: NONE
Reproduction: gates still pass pre-capture; the closed run cannot pass --between-runs
  by design (the defect this record documents)
Evidence: raw/m4-20260827-run01/ (complete, single-run, repeat-unverified), PROGRESS.md
Successor: ../EXP-0081-m4-mem-offset-semantics/
```
