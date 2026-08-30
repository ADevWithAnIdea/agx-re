# EXP-0143 — PROGRESS (append-only, one entry per milestone)

- **2026-08-28 ~16:50Z — re-orientation.** Dispatch said to start fresh, but the experiment
  directory already existed and is **committed at `4fe49a1c`** ("all 10 agents died on the
  session limit"): carriers, `frun.m`, `runner.py`, `casematrix.py`, `run.py` and a smoke
  (`work/smoke_smoke01/`) were already authored by the earlier dispatch of this same
  experiment. `raw/` was **empty** — no capture had been taken. Decision: keep the authored
  code (it is our own; re-authoring buys nothing on a tight timeline), freeze a **new**
  pre-registration, capture under **new** run ids, and retain `work/smoke_smoke01/` untouched.
  Confirmed the 64 blocking fields against `validation.json` — count matches the dispatch exactly.

- **~17:00Z — harness hardened to FIELD-SWEEP-PROTOCOL sec.7.** Added to `frun.m` an
  **integrity sentinel on an independent path**: after writing the patched archive it re-reads
  the file off disk through a separate `NSData` read and byte-compares every spliced window
  (`SENTINEL_FAIL` otherwise). Added to `run.py`: majority-of-3 fault confirmation, the OS
  fault-classification string (`InnocentVictim` vs `ErrorHang` etc.) recorded per trial,
  periodic (250-case) + end-of-arm baseline re-validation with 4 retries, `0xDEADBEEF`
  read-back poison detection, and a **unique splice-archive path per request** on the compute
  side (the render side already had one). `runner.py`: foreign retries 6 -> 8 with longer backoff.

- **~17:02Z — smoke02 (44 cases, 1.8 s, new run id).** All 22 arm baselines OK, sentinel OK on
  every case. **The new guards immediately caught a false positive**: `iter@frag0W` had read
  "live" in the earlier smoke01 only because a sibling experiment's `InnocentVictim` fault was
  scored as "the observation changed". With foreign-fault retry it correctly reads NOT live.
  `vary_slot@vert0` / `vary_slot@v16`, which smoke01 recorded as "baseline failed", are both
  live — those failures were sibling contamination, not the carrier.

- **~17:12Z — run01 STOPPED BY HAND at 1,746 / ~29,600 cases. RETAINED as PARTIAL.**
  `iter.dst >= 192` (destination GPR >= 96) produces **genuine, reproducible GPU hangs**
  (`kIOGPUCommandBufferCallbackErrorHang`, 3/3 at values 192/193/194, then a full 3/3 watchdog
  timeout at 195). Real hardware result — and it was degrading the shared GPU: the concurrent
  sibling EXP-0138 stopped progressing in the same window. **Harness defect this exposed:**
  `MAX_HANGS_PER_ARM` counted only watchdog timeouts, so `ErrorHang` command-buffer faults did
  not count against the sec.8 budget and the sweep kept driving the hang. Corrected: a genuine
  hang is now a *confirmed* watchdog timeout **or** an OS `ErrorHang`; the budget stops the
  **field** (2 hangs) rather than the whole arm (6), so breadth across the other fields
  survives; a 2 s settle follows each hang. `raw/m4_20260828_run01/PARTIAL.md` records this.

- **~17:20Z — host GPU degraded.** After stopping run01, a single one-shot render of the
  unmutated carrier did not return within 120 s, and the sibling experiment remained stalled.
  Investigating before relaunching; not relaunching a sweep into a degraded GPU.
