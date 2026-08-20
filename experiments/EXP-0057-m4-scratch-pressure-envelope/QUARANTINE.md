# EXP-0057 quarantine record

Status: **QUARANTINED / NON-EVIDENCE** on 2026-08-20.

This applies to every live-produced EXP-0057 artifact, including both raw run
directories, derived analysis JSON, the generated manifest, and the historical
text in `README.md` and `RESULTS.md`. They are retained append-only for an
auditable account of the failed process. They must not be staged as experiment
evidence, cited in `PROVENANCE.md`, used to update `AGX_RE_INFORMATION_GAPS.md`,
or used to support any implementation or hardware conclusion.

## Audit finding

The frozen registration permitted only a strictly bounded own-pipeline metadata
observation. `harness/metadata.py` instead called `archive.read_bytes()` and
used generic `iter_gpu_images`/`MachO` traversal to find a metadata region. Even
though it did not intentionally extract shader code, this touches a compiled
pipeline container beyond the registered metadata-only boundary and therefore
fails the clean-room process contract.

Separately, the live records retained only success booleans for output/guard
checks, rather than the full authored output and guard readbacks required for
independent verification. They also lack a complete target OS/tool/repository
revision record at capture time. These are independent provenance defects.

## Consequence

P0.1 remains **OPEN**. EXP-0041 remains the applicable valid M4 negative
boundary evidence; EXP-0057 contributes nothing. Do not repair this experiment
in place or rerun it. Any future scratch-pressure work must start with a new
experiment number and a fresh preregistration that avoids the archive traversal,
captures full bounded authored readback/guards, records the complete environment
and revision before execution, and passes independent audit before promotion.
