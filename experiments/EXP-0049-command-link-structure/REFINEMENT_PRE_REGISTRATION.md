# EXP-0049 refinement pre-registration: approach first rollover from below

Date: 2026-08-17

This file is frozen after the two unchanged main searches and before any
refinement run. It does not alter or overwrite the main results.

## Motivation from the preserved main result

In both main searches, `cdm-indirect` at count 2048 and `vdm-stable` and
`vdm-pass1` at count 4096 completed with correct readback and captured their
preclassified second-segment BO. The strict analyzer stopped because the
EXP-0043 source-link pair was absent from the preclassified first segment. At
those high counts, several rollovers may exist, so presence of the known second
segment does not establish that it is the first source segment's destination.

No additional source bytes were scanned to locate another target and no command
memory was changed. The main failures and all raw captures remain append-only.

## Refinement question and algorithm

Can the exact EXP-0043 link pair and known second segment be observed at the
first rollover by approaching it from a one-segment workload rather than
starting at the multi-segment fixed maximum?

For each of `cdm-indirect`, `vdm-stable`, and `vdm-pass1`, in a fresh process per
trial:

1. run counts 1, 2, 4, 8, ... up to the unchanged main upper bound;
2. stop at the first trial that captures the independently allowlisted target;
3. require that trial to contain the exact EXP-0043 link pair in the exact
   preclassified source BO;
4. if it does, binary-search between the prior no-target count and that count;
5. repeat the resulting `threshold-1` and `threshold` pair in fresh processes;
6. execute the entire refinement twice in independent append-only run trees.

## Hypothesis and falsifiers

Hypothesis: the exact known pair is retained at the first rollover and the main
stop was caused by using a high count with multiple segments.

- Support: exact pair plus known target at a repeatable first boundary.
- Falsifier: the first known target appears without the exact pair, no known
  target appears by the upper bound, a readback fails, or repetitions disagree.

On a falsifier, report the bounded negative result. Do not search for another
address encoding, broaden the BO allowlist, inspect any new target, or infer a
link by scanning pointer-like values.

## Unchanged clean-room and safety boundary

The exact four-VA allowlist, caps, public-API authored harness, prohibitions,
hard per-process timeout, evidence retention, M4-only scope, and structural-only
interpretation from `PRE_REGISTRATION.md` remain in force. In particular:

```text
Apple binary introspection: NONE
Apple auxiliary/helper/shader code inspection: NONE
Unknown BO contents inspected: NONE
Pointer following: NONE
Executing command-memory mutation or replay: NONE
```
