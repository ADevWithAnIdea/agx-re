# QUARANTINE — m4-20260828d-run01 / m4-20260828d-run02

Both runs' 49 cases executed successfully (`exit=0`, `status=ok` for every case; no faults, no
timeouts, no GPU wedges). The underlying scientific case data is not suspected of any defect.

**Reason for quarantine:** `run.py`'s `env_record()` computed `authored_sha256` from
`CAPTURE_CONTRACT.json`'s `blob_sha256` map, which (by `gen_contract.py`'s design) deliberately
excludes `CAPTURE_CONTRACT.json`'s own hash (it cannot hash itself while being written). This
left `00_inputs.json.authored_sha256` missing the `CAPTURE_CONTRACT.json` entry that
`verify.py`'s `check_inputs()` requires (`set(i["authored_sha256"]) == set(auth_files())`, where
`auth_files()` = `blob_sha256` keys + `"CAPTURE_CONTRACT.json"`). `analysis/analyze.py --write`
caught this immediately (`FAIL inputs schema m4-20260828d-run01`) before any promotion to
`RESULTS.md`.

Per `experiments/SUBAGENT_BRIEF.md`'s standing rule ("never repair or rerun ... in place... a
successor takes a NEW ... id") and the precedent in EXP-0094
(`quarantine-m4-20260828b-run01/QUARANTINE-run01b-attempt2.md`, an identical class of issue: all
cases correct, `verify.py`'s own design needed a fix), these two run directories are retained
**unmodified** and quarantined rather than patched in place. `run.py` was fixed (`env_record()`
now adds `CAPTURE_CONTRACT.json`'s own hash to the `authored_sha256` map) and the pair was
recaptured fresh under new run ids `m4-20260828e-run01`/`m4-20260828e-run02`.
