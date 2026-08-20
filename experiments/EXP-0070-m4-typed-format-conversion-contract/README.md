# EXP-0070 M4 typed-format conversion contract

Captured P1.2 public-Metal M4 experiment bundle. It uses an authored MSL matrix,
owned-buffer in-bounds harness, deterministic analyzer, complete capture manifest,
and fail-closed verifier. Its results are limited to six exact public-Metal cases
on the recorded M4 environment; they make no native, descriptor, Linux, or A18
claim.

Audit the retained capture without rerunning it:

```sh
python3 -B verify.py --captured
python3 -B analysis.py --run-a m4-TODO-run01 --run-b m4-TODO-run02
python3 -B make_manifest.py --check
```

`analysis.json` is the retained derived, byte-exact analysis. `manifest.json`
hashes every authored, raw, and derived artifact (except itself). The runner is
retained for reproduction but must not be invoked as part of audit.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored text sources, public status objects, and full owned readbacks
Apple binary introspection: NONE
Reproduction: commands above
Evidence: `raw/m4-TODO-run01`, `raw/m4-TODO-run02`, `analysis.json`, and `manifest.json`
