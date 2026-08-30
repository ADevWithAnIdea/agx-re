# run01 — PARTIAL, RETAINED, NOT REUSED

Stopped by hand at 1,746 / ~29,600 cases, ~11 minutes in.

**Why.** `iter.dst` values >= 192 (destination GPR >= 96) produce *genuine, reproducible* GPU
hangs — `kIOGPUCommandBufferCallbackErrorHang`, confirmed 3/3 by the majority-of-3 guard at
values 192, 193, 194, then a full watchdog timeout (3/3) at 195. This is a real hardware
result and it is retained below and in `sweep.jsonl`. It was also actively degrading the
shared GPU: a concurrently running sibling experiment (EXP-0138 `m4_20260828_run05`) stopped
making progress during the same window.

**The defect this exposed in the harness.** FIELD-SWEEP-PROTOCOL sec.8 says "after two genuine
hangs in one area, STOP that arm". The `MAX_HANGS_PER_ARM` counter only counted watchdog
timeouts (`status == "HANG"`), so the three `ErrorHang` command-buffer faults at 192/193/194
did **not** count against the budget and the sweep kept driving the hang. Corrected in the
successor: a case counts against the hang budget when the OS classification is `ErrorHang`
**or** the watchdog fired, and the budget stops the **field** (not just the arm), so the rest
of the arm's fields still get swept.

**Disposition.** Retained unmodified as append-only evidence. The id is never reused and this
directory is never topped up. The successor capture is `m4_20260828_run02`.

Observed before the stop (carried into the successor's analysis as corroboration, not as a
substitute for its own sweep):

- `vary_slot@vert0` and `vary_slot@v16`: both fields swept 0..255 dense, no faults.
- `iter@frag1`: `grp`, `lead`, `coeff_sel` complete; `dst` swept 0..195 before the stop.
- 164 `fault` outcomes and 8 `silent_zero` recorded, all with their OS classification string.
