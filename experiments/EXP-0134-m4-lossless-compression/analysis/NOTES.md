The repeatable analysis code for this experiment lives in `harness/auxdecode.py`
(descriptor + aux-byte decoder) and `harness/run.py` (per-case verdict derivation), since
both are exercised on every official run through `harness/run.py`, not as a separate
post-hoc reporting pass — matching CODEX §6's "equivalent layouts... acceptable" allowance.
The derived report is `RESULTS.md`; the queries used to build its tables from
`raw/*/02_gated.jsonl` are the ad hoc one-off `python3 -c` snippets recorded in this
experiment's session transcript (grouping/printing fields already present verbatim in the
committed gated JSONL — no additional derivation logic beyond what `auxdecode.py`/`run.py`
already perform).
