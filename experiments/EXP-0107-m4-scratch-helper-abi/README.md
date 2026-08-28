# EXP-0107: M4 scratch/helper ABI at high pressure

Successor to `EXP-0041-scratch-helper-abi` (valid negative boundary evidence
at 208–576 B declared scratch). **Not** a successor to the quarantined
`EXP-0057-m4-scratch-pressure-envelope` — see `PRE_REGISTRATION.md`
"Predecessors" for why, and `CAPTURE_CONTRACT.json`.

See `PRE_REGISTRATION.md` for the frozen question, hypotheses, confounders,
case matrix design, and safety rules; `casematrix.py` for the exact case list
(single source of truth); `RESULTS.md` for observations vs interpretation.

## Reproduce

```sh
cd /Users/user/asahi_re/public/agx-re
python3 -B experiments/EXP-0107-m4-scratch-helper-abi/verify.py --selftest
python3 -B experiments/EXP-0107-m4-scratch-helper-abi/verify.py --seqtest
python3 -B experiments/EXP-0107-m4-scratch-helper-abi/run.py --run-id m4-20260827-run01 --execute
python3 -B experiments/EXP-0107-m4-scratch-helper-abi/run.py --run-id m4-20260827-run02 --execute
python3 -B experiments/EXP-0107-m4-scratch-helper-abi/verify.py --check
python3 -B experiments/EXP-0107-m4-scratch-helper-abi/analysis/analyze.py --run-dir experiments/EXP-0107-m4-scratch-helper-abi/raw/m4-20260827-run01 --output experiments/EXP-0107-m4-scratch-helper-abi/analysis/report_run01.txt
python3 -B experiments/EXP-0107-m4-scratch-helper-abi/make_manifest.py
```

Run ids are append-only and contracted in `CAPTURE_CONTRACT.json`/`casematrix`
via `run.py`'s `RUNS` tuple; an existing `raw/<run-id>` is never reused or
repaired. `run.py` refuses to run without `--execute`, refuses an
unrecognized `--run-id`, runs `verify.py --selftest`/`--seqtest` first, then a
NON-RECORDED smoke case before creating any `raw/` artifact.

## Clean-room attestation

```text
Clean-room provenance: OWN-SHADER / DATA-TRACE / PUBLIC API
Apple binary introspection: NONE
Apple helper-program bytes inspected: NONE
Reproduction: commands above
Evidence: raw/, analysis/, manifest.json
```
