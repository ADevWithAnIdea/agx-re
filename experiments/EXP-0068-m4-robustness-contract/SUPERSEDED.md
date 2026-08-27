# EXP-0068 supersession record

Status: **SUPERSEDED without capture** on 2026-08-27.

EXP-0068 was a pre-GPU gate scaffold only: a `PRE_REGISTRATION.md` and
`CAPTURE_CONTRACT.json` defining the required blobs, environment capture, closed raw-tree
schema, and stop-before-build discipline for a P1.5 / DRV-ROBUST-01 public-Metal M4
owned-buffer OOB boundary probe. No `kernels/`, `harness/`, `run.py`, `analysis.py`,
`make_manifest.py`, or `verify.py` was ever authored, nothing was built, and no capture
exists.

Its intended scope (out-of-allocation behavior, guard/zero mappings) is now part of the
user-directed load/store/SSBO priority cluster and is folded, broadened to the full
unaligned + boundary-crossing matrix, into **EXP-0076-m4-buffer-robustness-matrix**
(answering Part-II `MEM-06…MEM-12` of `APPLE9_RE_IMPLEMENTATION_GAPS.md`). EXP-0076 takes
a fresh, complete frozen pre-registration; this scaffold is retained as process history of
the gate idea and binds nothing.

```text
Clean-room status: no capture; process history only
Apple binary introspection: NONE
Successor: EXP-0076-m4-buffer-robustness-matrix
```
