# QUARANTINE — m4-20260828e-run01 / m4-20260828e-run02

Both runs' 49 cases executed successfully (`exit=0`, `status=ok` for every case; no faults, no
timeouts, no GPU wedges; `analysis/analyze.py --write` reported `repeat_exact: true` for this
pair before this quarantine). The underlying scientific case data is not suspected of any defect
— every splice/dispatch result matched `m4-20260828d-run0{1,2}`'s (quarantined for an unrelated
reason) and the pre-registration exploration exactly.

**Reason for quarantine:** `gen_contract.py`'s authored-blob discovery swept up `README.md`,
`RESULTS.md`, and `PROGRESS.md` into the SAME hash-pinned `blob_sha256`/`authored_sha256`
registry as the genuine capture-time inputs (kernels, harness, `run.py`, `verify.py`,
`CAPTURE_CONTRACT.json`). `RESULTS.md` is, by design, written and substantially edited AFTER
capture (it reports the capture's own outcome) — pinning its hash into capture-time provenance
was a design mistake discovered only when `RESULTS.md` was written and `verify.py`'s
post-capture `check_inputs()` would have (correctly) rejected the now-mismatched hash. This
mirrors EXP-0106's own precedent for a `verify.py`-side design defect discovered after a
technically-correct capture. Fixed: `gen_contract.py` now excludes `README.md`/`RESULTS.md`/
`PROGRESS.md` from the blob registry (verify.py's `static()` still requires all three to exist
as regular files; it no longer hash-binds them). `PRE_REGISTRATION.md` remains pinned, since it
genuinely is frozen before capture. Retained unmodified per the standing "never repair a raw
capture in place" rule; recaptured fresh under `m4-20260828f-run01`/`m4-20260828f-run02`.
