# EXP-0210 — AMENDMENT 01, frozen 2026-08-30 before its first dispatch

**Trigger.** The first confirmation pair (`EXP-0203` → `raw/e0203_q41`, `raw/e0203_q42`,
retained, never reused) ran while nothing else was on the machine, and `q42` measured
`n_foreign == 0` in all 36 samples — but `q41` measured `n_foreign == 2` in some samples.
The two counted processes are:

```
pid 24509  agxtest/agxrun_persist --source .../EXP-0203/kernels/carrier_a.metal   ours=True
pid 24510  .../MTLCompilerService.xpc/Contents/MacOS/MTLCompilerService            ours=False
pid 24514  agxtest/agxrun_persist --source .../EXP-0203/kernels/carrier_b.metal   ours=True
pid 24515  .../MTLCompilerService.xpc/Contents/MacOS/MTLCompilerService            ours=False
```

They are **our own capture's shader-compiler XPC helpers**: `MTLCompilerService` is an XPC
service, so launchd — not our runner — is its parent, and a `ppid` walk cannot see it as
ours. The PIDs are adjacent to our two runners and appeared when our runners compiled our own
MSL. `PATTERNS` inherited `MTLCompilerService` from EXP-0201's `gpuwatch.py`, which had no way
to tell its own compiler from a sibling's and therefore counted both.

**This is a defect in the instrument, not an observation about the machine.** The independent
hardware-side signals in the same samples say so: `fLastSubmissionPID` over the whole of `q41`
is `{328, 24509, 24514}` — the idle login-window `SecurityAgent` plus **our own two runners
and nothing else** — `fBusyCount` is 0 in every sample, and `recoveryCount` is 12977 at the
first and last sample.

## What changes

`harness/quietsample.py` splits the single counter into three, and Q1 is re-stated on the
first of them:

| key | contents |
|---|---|
| `n_foreign_runner` | processes matching a **dispatch-runner** pattern (`agxrun`, `agxrun_persist`, `agxrender`, `renderpersist`, `rendersweep`, `gfrun`, `shdump`, `persistrun`, `agxtest`) that are not in our own subtree |
| `n_compiler_svc` | `MTLCompilerService` instances, with PIDs, recorded but **not** a criterion |
| `n_foreign` | unchanged, kept so the numbers stay comparable with the fan-out's own busy measurements |

**Q1 (amended): `n_foreign_runner == 0` in every sample.** A dispatch runner is the process
class that actually contends for the GPU, faults, hangs, and manufactures the
`InnocentVictim` and cascade evidence Gate E is about. A compiler service does not dispatch.

**Q1b (new, reported not gated):** every `MTLCompilerService` observed must be attributable to
this capture. The sampler now snapshots the full PID set at start, so any GPU-pattern process
seen during the window is flagged `new_since_start`. With `n_foreign_runner == 0` throughout
and Q3 showing no foreign submitter, a compiler service that appeared inside the window has no
other possible client. Both facts are reported per capture; neither is assumed.

**Q2, Q3, Q4 are unchanged.**

## What this amendment may NOT do

It may not be applied to data already seen. `raw/e0203_q41` and `raw/e0203_q42` are retained
**exactly as captured**, are **not** re-scored under the amended criterion, and **do not**
support a Gate E verdict. The EXP-0203 confirmation pair is re-dispatched under the amended
instrument as `g17p_q43` / `g17p_q44` (new run ids; `q41`/`q42` are never topped up or reused).
Their agreement with `q43`/`q44` is reported as supporting evidence, not as the gate.

This amendment is frozen before the first dispatch that uses it.
