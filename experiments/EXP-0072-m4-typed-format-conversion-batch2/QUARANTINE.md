# EXP-0072 quarantine record

Status: **QUARANTINED / NON-EVIDENCE** on 2026-08-27.

## What happened

Pre-registration, `verify.py --preflight`, and `verify.py --selftest` all passed
cleanly (the self-test — added for exactly this purpose after EXP-0073 — proved
every schema gate satisfiable and caught several real pre-capture bugs,
including a wrong `command_buffer_error` status set). Capture run 01
(`raw/m4-20260827-run01`) then executed: host build clean, all 34 case
processes exited 0, all four guard regions intact in every record, device
"Apple M4", command buffer status 4, no API rejection, compile rejection,
timeout, GPU fault, hang, device loss, or reboot.

The failure is a **harness defect that the schema self-test cannot express**:
in `harness/probe.m`, the worker thread signals the dispatch-phase semaphore
immediately after `waitUntilCompleted`, BEFORE printing its JSON record, while
`main()` treats that signal as "done" and returns 0. The process therefore
exits while the worker is still mid-`printf`, truncating stdout at a
nondeterministic point. All 34 case payloads are truncated (0 of 34 parse as
JSON; they end at varying points around the `"os"` field), and the physical
texel hex / read-word data — printed last — is lost entirely. The runner
recorded exit 0 for every case, so no `STOP.json` was written; the defect
surfaced only at payload parsing, i.e. after the append-only capture.

## Why this cannot be repaired in place

Repairing `harness/probe.m` after capture is not authorized: the frozen
`CAPTURE_CONTRACT.json` binds the SHA-256 of the harness, and
`raw/m4-20260827-run01/00_inputs.json` records that pre-capture hash.
`verify.py --captured` fails closed unless the current on-disk hash still
equals the captured one, so any fix breaks the no-drift binding — the same
capture-time-provenance failure class that quarantined EXP-0064 and EXP-0073.
The contracted between-runs gate (`verify.py --between-runs`) fails on the
retained run01 by design (unparseable case stdout = missing schema fields),
so EXP-0072 cannot meet its pre-registered promotion rule. No raw evidence was
edited and no automatic retry was attempted.

## Disposal of the retained material

- `raw/m4-20260827-run01/` is retained **append-only as process history
  only**. No hardware claim, format classification, expected-word confirmation,
  or deviation may be staged, cited, promoted, or used for any DRV-FMT-01
  decision from this tree. (For transparency only: the truncated records
  consistently show status "ok" with all pipelines and textures created and
  command buffer status 4 for all 34 cases — including RG11B10Float and
  RGB9E5Float — but this is unverified process history from a defective
  harness, not evidence. The successor must re-establish everything.)
- `CAPTURE_CONTRACT.json`, `PRE_REGISTRATION.md`, `manifest.json`,
  `PROGRESS.md`, and the authored sources stay as the frozen record of what
  was registered; nothing is edited. `README.md` and `RESULTS.md` carry the
  quarantine banner only.
- The successor is **EXP-0075-m4-typed-format-conversion-batch2** (EXP-0074 is
  EXP-0073's successor): same frozen design, with the harness race fixed and
  two added pre-capture gates.

## Required fixes for the successor (do not re-derive from scratch)

1. `harness/probe.m` process-exit race: after both semaphore waits succeed,
   `main()` must not return — it must block forever (`pause()` or
   `dispatch_main()`), letting only the worker's `finish()` → `exit()` terminate
   the process (exit flushes stdio completely from the printing thread).
   Alternative: signal `sem_dispatch` only after the payload has been fully
   printed and flushed, with `fflush(stdout)` before the signal.
2. Add a pre-capture harness smoke gate that this failure class cannot bypass:
   after the host build and BEFORE creating the append-only raw tree, the
   runner executes one non-recorded probe invocation (a scratch case whose
   stdout is parsed as JSON and then discarded, outside `raw/`) and refuses to
   begin capture unless the payload parses and every field is present. This
   turns any print-truncation or payload-shape defect into a pre-capture stop.
3. Keep the schema self-test; extend it if further invariants become
   expressible (it already catches receipt/payload/provenance contradictions
   and caught one post-EXP-0073-class bug here).

```text
Clean-room status: quarantined process history; no DRV-FMT-01 hardware claim
Apple binary/code/archive/BO/compiled-shader-byte inspection: NONE
Raw retention: append-only, non-evidence
Successor: EXP-0075-m4-typed-format-conversion-batch2
```
