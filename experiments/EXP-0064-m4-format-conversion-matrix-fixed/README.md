# EXP-0064: M4 public typed format conversion matrix

> **QUARANTINED / NON-EVIDENCE.** See `QUARANTINE.md`. Do not run, cite, stage,
> or promote the retained live outputs; audit found irreparable capture-time
> harness-hash and raw-schema provenance gaps.

Two fresh public-Metal runs exercised six fixed 1x1 render-store followed by
typed compute-read cases. The only retained payloads are complete owned shared
render backings (384 bytes) and compute backings (144 bytes), including guards.
No IOKit, archive, compiled-code, command, state, or BO data is captured.

Run `analysis.py`, then `make_manifest.py` and `verify.py` from this directory.
The latter fails closed on the exact two-run path/type matrix, full hex lengths,
source/environment binding, guards, hashes, and semantic repeatability.

```text
Clean-room provenance: HW-PROBE / OWN-SHADER source / PUBLIC API
Apple binary/helper/auxiliary/command/state/code/unknown-BO inspection: NONE
Compiled code bytes or archives inspected: NONE
```
