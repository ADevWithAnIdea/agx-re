# EXP-0213 — AMENDMENT-01

**Frozen 2026-08-30, before stage 6A's first dispatch. No capture taken under the original
text is re-scored, and none is discarded.**

## What changed

Two files are ADDED — `harness/drive_cap.sh` and `harness/capture_cap.sh`. Nothing is
edited. Phases 1, 2 and 3 keep `drive_one.sh` / `capture.sh` exactly as frozen.

## Why — a defect in my own instrument, found before it mattered

`drive_one.sh` enforces the pre-registered wall-clock cap with

```sh
perl -e 'alarm shift; exec @ARGV' "$ALRM" sh -c "$*"
```

An `alarm(2)` timer **survives `execve`**, so SIGALRM does arrive — but it arrives at the
`sh -c` and at nothing else. The `python3 run.py` child underneath it is **orphaned and keeps
sweeping the GPU** while the driver records the capture as stopped. For phases 1–3 this is
inert: those captures finish in about **1 second** of device time against a 300 s alarm, so
the alarm can never fire. For EXP-0206's stages 6A/6B/6C the cap is the entire safety
mechanism — EXP-0206's `run.py` deliberately has **no abort path and no hang budget**, and
this experiment does not change that, so the only place a stopping rule can live is outside
it. A cap that silently leaves the capture running would have made
"the stage exceeded its cap and was stopped" a false statement in `RESULTS.md`.

`drive_cap.sh` runs the capture as a tracked background child, polls the deadline, and on a
hit sends TERM then KILL to the child **and** its process group, then reaps any dispatch
runner still alive. A cap hit is reported as `__DRIVE_CAP_HIT` in the capture log and
`__DRIVE_RC=142`; the partial capture is retained under its own run id and is never topped up
or reused.

## Scope of the by-name reap

On a cap hit only, `drive_cap.sh` also runs `pkill -KILL -f agxrun_persist` and
`pkill -KILL -f gfrun4`. Captures in this experiment are strictly sequential and this agent
owns the device for the session, so this cannot take a sibling's runner — but it is stated
here rather than left implicit, and the quiet sampler records every process in every sample,
so a foreign runner present at a cap hit would be visible in the raw.

## What this amendment does NOT do

It does not touch a hypothesis, the Gate E criterion, the declared budgets, the declared
exclusions, the agreement key, the volatile-field list, or any source experiment's harness or
contract. It does not loosen a failing conjunct: it makes an existing stopping rule actually
stop.
