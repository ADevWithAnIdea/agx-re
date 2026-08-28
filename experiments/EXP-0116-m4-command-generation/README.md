# EXP-0116: M4 command-stream link/code GENERATION and hardware-consumer proof

## Question

`docs/P0-P1-CLOSURE.md` P0.5 and P0.7 both require independent GENERATION,
not merely decoding. EXP-0110's own DECODED-vs-GENERATABLE table states
neither row closes because "no link record was hand-constructed and
executed, no code block was built outside the archive path." This
experiment attempts exactly that for the CDM (compute) segment link field:

1. Can a link record we compute ourselves (never copied from a capture) be
   spliced into a live, not-yet-submitted command buffer and be followed by
   real hardware, with an unambiguous observable side effect?
2. Across the target field's representable range, where is the boundary
   between "hardware follows it," "hardware faults," and "hardware hangs"?
3. Can a CDM record referencing real captured machine code be relocated and
   executed outside `MTLComputePipelineState` creation for that record?

## Hypothesis

See `PRE_REGISTRATION.md` for the full falsifiable hypothesis set (H1-H6),
independent/controlled variables, per-case predicted outcome table, and
confounders, frozen before the official captures.

## Method

New technique vs prior EXP-0043/0049/0110 (which only READ command-stream
bytes): this experiment also WRITES a hand-computed value into that same
CPU-mapped memory, strictly before the owning command buffer is committed.
Calibration proved the CPU pointer `tools/iotrace`'s BODUMP reports for a BO
is literally `MTLBuffer.contents` for that BO -- an ordinary, directly
writable pointer in this process's own address space. This is HW-PROBE
("write a known pattern into hardware-visible state, observe what the
hardware does with it") per `CLAUDE.md`, not Apple-binary introspection.

Primary mechanism (`same_cb`): one command buffer, one compute encoder,
rolled over into the exact 732/732/36-record three-segment CDM chain
EXP-0110 validated occurs naturally, with the middle segment (`seg1`)
writing a SEPARATE buffer from the outer two so its non-execution is
directly, unambiguously observable. `seg0`'s own tail link is overwritten
in place (before commit) with a value this program computes per test case.
See `RESULTS.md` for the full case matrix and outcomes, and
`PRE_REGISTRATION.md`/`PROGRESS.md` for the two discarded/superseded
calibration mechanisms and why.

## Commands (reproduction)

```sh
# gates (no device needed)
python3 verify.py --selftest
python3 verify.py --seqtest

# one official run (rebuilds harness/tools first)
python3 verify.py --preflight --run-id <run-id>
python3 run.py --run-id <run-id> --execute
python3 verify.py --selftest --seqtest --between-runs --run01-id <run-id>

# cross-run gate over two runs
python3 verify.py --captured --run01-id <run01> --run02-id <run02>

# derive the summary table from a gated capture
python3 analysis/report.py raw/m4_20260828_run05
```

Six official runs exist (`m4_20260828_run01`..`run06`) because the
cross-run gate itself caught two genuine pieces of hardware nondeterminism
mid-experiment and `schema.py` was corrected twice in response (fully
disclosed in `CAPTURE_CONTRACT.json`'s `post_capture_corrections` and
`RESULTS.md`); `run05`/`run06` is the pair the closure-relevant table is
drawn from. `run01`-`run04` remain valid raw evidence for the two
discoveries, not discarded.

## Clean-room category

`HW-PROBE / DATA-TRACE / OWN-SHADER`. See `RESULTS.md`'s attestation block
and `PRE_REGISTRATION.md`'s "Method summary" for the specific justification
of the one new technique (direct CPU-pointer writes into this process's own
registered command-stream memory, pre-commit).

## Layout

- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` -- frozen hypothesis/method/
  case matrix and file-hash pins (with disclosed post-capture corrections).
- `PROGRESS.md` -- milestone log, including calibration dead-ends kept for
  audit.
- `harness/linksplice.m` -- the link-splice program (tasks 1/2).
- `harness/codeswap.m` -- the code-record hybrid/relocate program (task 3).
- `schema.py`, `casematrix.py`, `run.py`, `verify.py` -- gate/capture
  infrastructure.
- `analysis/report.py` -- derives the summary table from a gated capture.
- `raw/m4_20260828_run01`..`run06/` -- immutable captures (see above).
- `RESULTS.md` -- observations vs interpretation, the full case-boundary
  table, the finite-resource-mandate table, GENERATED-vs-COPIED per field,
  remaining P0.5/P0.7 gaps, gate results, clean-room attestation.
