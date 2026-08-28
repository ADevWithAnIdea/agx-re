# EXP-0127 -- M4 graphics shader selection: VS token rule, FS selector
# redirect/boundary, and code-window relocation category

- Date: 2026-08-28
- Target actually tested: local Apple M4 / G16G, macOS 26.6.2 (25G82), Metal 4
- Gap scope: `docs/P0-P1-CLOSURE.md` P0.2 (`DRV-UAPI-02`), stale since EXP-0042
- Evidence: HW-PROBE + DATA-TRACE + OWN-SHADER

## Question and acceptance relevance

EXP-0042 found a separable VS creation-order token (VDM `+0x1c/+0x20`) and an
FS selector at `0x58000+0x08` that structurally correlates with FS code
layout, but left open: the token's general rule, the selector's true
meaning (structural correlation vs proven hardware consumer), and whether
either maps to the queue-wide `usc_exec_base` the unchanged Asahi UAPI
actually provides (no per-render code-BO field exists). This experiment
answers all three with generated, independently-verified probes -- not by
re-decoding a captured template.

## Method summary (full detail: `PRE_REGISTRATION.md`)

Four sub-tests, all on our own compiled MSL and our own harnesses:

1. `harness/vstoken.m --mode varied`: 8 vertex functions of deliberately
   different compiled sizes, created and drawn in a fixed interleaved
   tiny/huge order, to discriminate an ordinal-token hypothesis from a
   code-offset hypothesis for the VDM `+0x20` field.
2. `harness/vstoken.m --mode uniform --count 650`: many near-identical
   vertex functions, to find the token's step, width, and the point (if
   any) where its own numeric regime changes.
3. `harness/vstoken.m --pad-mb 64` / `--extra-queues 4`: EXP-0110's own
   64 MiB client-padding and extra-command-queue methods, applied to the
   code window specifically (EXP-0042 only tested 17 small BOs).
4. `harness/fsredirect.m`: for three real, distinctly-sized/coloured
   fragment pipelines (red/small, green/medium, blue/large), independently
   discovers each one's own natural `0x58000+0x08` selector value via solo
   draws, then -- mirroring EXP-0116's HW-PROBE splice method for the CDM
   segment link -- writes a computed value into that same live, CPU-mapped
   field strictly before the owning command buffer commits, and observes
   whether hardware executes the redirected-to program. A 20-case matrix
   covers the decisive redirect (both directions, two distinct targets),
   an eight-point misalignment sweep (+-1/2/4/8 bytes from a valid value),
   and a boundary/alias sweep (zero, a moderate and a very-far
   out-of-range offset, the top bit set, and the field's own `0xffffffff`
   representable ceiling).

Every mutation-bearing case (`fsredirect --case ...`) runs in its own
process (SUBAGENT_BRIEF.md's "one case per process"); the two safe,
non-mutating `vstoken` sweeps run to completion in a single process each,
matching EXP-0042's own precedent. All BODUMP DATA-TRACE dump directories
are written under `work/` (scratch) and deleted immediately after each
sub-test's derived, non-address facts are computed and appended to
`raw/<run-id>/gated.jsonl` -- keeping `raw/` small (740 KiB total across
five run attempts) while every harness's own raw stdout (every draw's
status, every case's full JSON line) is preserved verbatim as the
human-auditable evidence trail.

## Capture history (all disclosed; nothing repaired in place)

| run id | status | role |
|---|---|---|
| `m4_20260828_run01` | partial (2 records), crashed on a schema bug | retained; not official |
| `m4_20260828_run02` | complete, valid | retained; primary evidence for the racy-result_colour finding (superseded for the gate role) |
| `m4_20260828_run03` | complete, valid | retained; same finding (superseded for the gate role) |
| `m4_20260828_run04` | complete, valid | **official** (cross-run gate) |
| `m4_20260828_run05` | complete, valid | **official** (cross-run gate) |

Both schema corrections (a false-positive address-leak check, and a
genuine hardware-nondeterminism-on-clean-completion discovered by the
cross-run gate itself) are fully disclosed in `CAPTURE_CONTRACT.json`'s
`post_capture_corrections` and `PROGRESS.md`. Never reused a run id; never
repaired a raw capture in place.

## Reproduce and verify

```sh
cd experiments/EXP-0127-m4-shader-selection
python3 verify.py --selftest        # 16/16 PASS
python3 verify.py --seqtest         # 5/5 PASS
python3 run.py --smoke              # non-recorded, work/ only
python3 run.py --run-id <NEW_RUN01>
python3 run.py --run-id <NEW_RUN02>
python3 verify.py --captured <NEW_RUN01> <NEW_RUN02>
```

`analysis/gen_kernels.py --n-uniform 800` deterministically regenerates
`kernels/vs_uniform.metal` (frozen hash in `PRE_REGISTRATION.md`).

See `RESULTS.md` for the evidence-qualified verdict: the token rule, the
FS selector's actual (non-code-selecting) role, the boundary/alias map,
the code-window relocation category, and the explicit `usc_exec_base`
mapping statement. P0.2 remains **OPEN** after this experiment -- it
narrows the gap substantially and, notably, REFUTES the working hypothesis
that `0x58000+0x08` is itself the FS code selector, which materially
changes what the remaining work must target.

## Clean-room attestation

Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER

Inputs inspected: the MSL and Objective-C/Python source in this directory
(all authored here); IOKit boundary data and BO contents captured by the
repository's unmodified, read-only `tools/iotrace/iotrace.c` from this
process's own registered GPU buffer objects; direct CPU writes into this
process's own `MTLBuffer`-backed memory (the same mechanism Metal's own
userspace uses to build the command stream, per `CLAUDE.md`'s sanctioned
HW-PROBE method). No Apple binary was disassembled, decompiled, or
otherwise introspected.

Apple binary introspection: NONE

Reproduction: the commands above, all with hard timeouts (process-level in
`run.py`, per-commit watchdog + `alarm()` inside every harness).

Evidence: `raw/`, `raw_manifest.sha256`, `manifest.json`,
`PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`, `PROGRESS.md`.
