# EXP-0064 quarantine record

Status: **QUARANTINED / NON-EVIDENCE** on 2026-08-20.

All live-produced EXP-0064 material—both `raw/` runs, `analysis.json`,
`manifest.json`, and `RESULTS.md`—is retained append-only for process
traceability only. None may be staged as evidence, cited, promoted, or used to
update shared P1.2 documentation or any implementation decision.

Independent audit found that capture-time provenance did not retain a hash of
the exact harness source, and that the raw-record schemas were not fully frozen
and closed at capture time. Later source comparisons and verifier hardening
cannot reconstruct that missing capture-time proof. The retained public outputs
therefore cannot satisfy this repository's clean-room promotion standard.

No rerun or in-place repair is authorized. A future successor must receive a
new experiment number and fresh preregistration, capture hashes of every
authored source/harness/runner before execution, enforce complete closed raw
schemas before payload use, retain full owned outputs and environment identity,
and pass independent audit before any promotion.

```text
Clean-room status: quarantined process history; no hardware claim
Apple binary/code/archive/BO inspection: NONE
Raw retention: append-only, non-evidence
```
