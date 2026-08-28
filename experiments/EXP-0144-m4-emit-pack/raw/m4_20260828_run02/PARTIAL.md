# m4_20260828_run02 — PARTIAL, RETAINED, NOT USED

Stopped by hand at **5,219 of 22,237** cases. At case 11855 (`cvt_f2h_dst` byte+2
`opsel` sweep) the periodic carrier baseline re-validation failed. Inspection of
the surrounding window shows five `kIOGPUCommandBufferCallbackErrorHang` results
from **this sweep's own** deliberately-illegal `opsel` encodings in the preceding
300 cases: the baseline was sampled inside the GPU's own error-recovery window,
not during a sibling-experiment cascade.

`FIELD-SWEEP-PROTOCOL.md` §7.3 says a failing baseline means "stop, note where, and
resume in a fresh process rather than recording the cascade as data", so the run was
stopped rather than continued. It is retained unmodified and **not used for any
verdict**.

Fix: `baseline_check` now retries up to four times with an increasing settle delay
and only counts as a cascade if it fails *every* attempt; a genuine cascade now stops
the run outright instead of merely logging. A 0.1 s settle was also added before the
fault-confirmation re-run so a confirmation is never measured inside recovery.

The gate pair was re-captured as `m4_20260828_run03` and `m4_20260828_run04`.
