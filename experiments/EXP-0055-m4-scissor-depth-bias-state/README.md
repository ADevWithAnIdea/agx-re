# EXP-0055 — M4 scissor/depth-bias state boundary

## Question and verdict

EXP-0054 established bounded public-Metal scissor and depth-bias behavior. This
experiment asks whether change-one-factor versions of those authored workloads
produce reproducible DATA-TRACE differentials inside two exact M4 state mappings
already preclassified by clean live evidence.

The answer is **PARTIAL**. A single byte at `0x58000 + 0x36` is reproducibly
correlated with nonzero constant or slope depth bias. The tested scissor fields,
multi-scissor slot changes, exact bias values, and clamp values are not located
in either permitted mapping. P0.3 remains OPEN.

This is a local Apple M4 / G16G-class result only. It does not establish hardware
consumption, native synthesis, private descriptor bases/strides, integer mode,
Linux UAPI mapping, kernel/firmware ownership, or any A18 Pro fact.

## Process and frozen plan

The process is part of the result. `PRE_REGISTRATION.md` was independently
reviewed, frozen at SHA-256
`b3c1df8b72da3c14cd93897451ad686c66b6b49f80478ba6841f796a175a0b04`,
and committed alone as
`cf1ea53c8cc8d95dd28b740e407ffd11b9a51144` before any EXP-0055 source build or
GPU execution.

The frozen matrix contains 19 cases under `plain` and `pad64k` client-allocation
schedules. Each of the two append-only top-level runs built the exact authored
sources once and launched all 38 combinations as fresh 45-second-bounded
processes. Both runs completed without a process error, timeout, guard error,
or preflight failure.

The pad schedule retains a fixed-pattern authored 65536-byte shared buffer before
pipeline/resource creation. Its bytes are checked only as authored control data;
the allocation is never captured as state evidence.

## Exact DATA-TRACE boundary

Only these exact allocation starts can be remembered or read by
`harness/allowtrace.c`:

| GPU VA | preclassified M4 role | expected allocation/read | cap |
| --- | --- | ---: | ---: |
| `0x58000` | `fixed-function-render-state` | `0x8000` | `0x10000` |
| `0x68000` | `tiling-state` | `0x88e0` | `0x10000` |

The provenance bridge is committed EXP-0048 artifact commit
`5b701aa587b15b13680a9d83854d563bcb46228a`, its parent/manifest revision
`22ab13a10e7e0a744c5f847d2c7286ba6b2c1cad`, and committed manifest SHA-256
`58d518daea1fca9a45fdab16bdc681425c64eaedc97eaf7a07f773604a59dcfb`.
The preregistration binds its two repeated exact metadata hashes and the prior
draw/no-blend fixed-state anchors.

Unknown allocations contribute boundary metadata only. Their CPU mappings are
not retained. The tracer never dumps compiled shader/code, command, auxiliary,
or unknown BOs. It never interprets or follows a pointer and never mutates or
replays command memory.

Before any allowed payload is opened or hashed, the runner and analyzer validate
the complete path matrix and each closed nine-key metadata record: exact VA,
role, size, handle, single occurrence, allowlist marker, no-pointer marker, and
no-mutation marker. They then require exact trace/metadata/file linkage. Any
mismatch is a bounded stop; there is no fallback scan or broader capture path.

A pre-commit independent audit found that the live runner accepted the required
trace records but did not reject an additional unknown line family. The retained
traces contain only the five intended closed families. The current runner,
analyzer, manifest generator, and verifier now reject every unknown trace line;
the verifier also asserts the exact retained aggregate record counts. The current
runner contains visibly delimited post-capture hardening blocks, and `verify.py`
removes only those blocks in memory to reconstruct and hash the exact live-runner
bytes recorded by both raw runs. No raw artifact was rewritten.

The same audit found that the first manifest generator could hash an unexpected
regular file outside the state matrix. The corrected generator first resolves
the complete global path/type allowlist—including the exact 152 permitted `.bin`
paths—and rejects any extra file, directory, symlink, or special entry before it
opens or hashes an artifact. Its manifest revision is a stable Git ancestor
anchor, so regeneration and verification remain valid in a relocated descendant
checkout. These audit failures and corrections are retained in
`analysis/failures.md` because process provenance is part of the result.

## Authored matrix

All targets are 16 x 16. Every readback retains a 32-byte prefix guard, the full
1024-byte image, and a 32-byte suffix guard as complete hex.

- Seven single-scissor cases isolate x, y, width, height, zero width, and zero
  height from `(2,3,7,5)`.
- Three two-scissor cases change only slot 0 x or slot 1 x while two authored
  primitives select viewport indices 0/1 and write distinct colors.
- Nine one-draw Depth32Float cases isolate constant/slope signs, magnitude
  100000, and sign-matched `0.001` clamps under an unchanged Always/depth-write
  state and sloped triangle.

See `PRE_REGISTRATION.md` and `harness/probe.m` for the exact tables and inputs.

## Reproduction

Use new append-only run IDs on the stated M4 target:

```sh
cd /Users/user/asahi_re/public/agx-re/experiments/EXP-0055-m4-scissor-depth-bias-state
python3 run.py --run-id m4_YYYYMMDD_runNN
python3 run.py --run-id m4_YYYYMMDD_runMM
python3 analysis/run_analysis.py
python3 make_manifest.py
python3 verify.py
```

The retained canonical runs are `raw/m4_20260817_run01` and
`raw/m4_20260817_run02`. The runner records exact source/header/tool/repository
identities, build argv/stdout/stderr, build-product sizes and hashes, every trial
argv/environment/status/output, trace metadata, state pairs, failures, and a
complete recursive SHA-256 inventory. Build products are temporary, not retained,
and are not semantically inspected. The raw source identity names the exact
live-runner byte stream; the reconstruction check described above keeps that
identity independently verifiable after the parser hardening.

`analysis/analyze.py` repeats the complete metadata-first preflight, validates a
closed six-line public output grammar and exact modeled guards/pixels, checks all
depth relations, requires exact stdout and payload repetition, and retains every
byte differential for every predeclared pair and allocation schedule.

## Evidence map

- `PRE_REGISTRATION.md`: frozen questions, matrix, falsifiers, and boundary.
- `harness/probe.m`: complete authored Objective-C/MSL public workload.
- `harness/allowtrace.c`: exact two-VA interposer.
- `raw/`: two complete append-only runs, including all public bytes and failures.
- `analysis/summary.json`: exact full differential records and derived facts.
- `analysis/report.txt`: compact human-readable derivation.
- `analysis/failures.md`: preserved verifier-tooling failures and corrections.
- `RESULTS.md`: observations, bounded interpretation, and remaining gaps.
- `manifest.json`: exact committable artifact allowlist, sizes, and hashes.
- `verify.py`: independent raw/source/history/derivation/manifest verifier.

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE + DATA-TRACE + OWN-SHADER source
Inputs inspected: authored Objective-C/MSL and readbacks; public Metal status;
  boundary metadata; exact preclassified M4 state BOs 0x58000 and 0x68000 only
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Compiled shader bytes inspected: NONE
Command BO contents inspected: NONE
Unknown BO contents inspected: NONE
Pointer following: NONE
Generic BO/memory scan: NONE
Mutation/splice/replay: NONE
Target: M4/G16G-class only; A18 Pro untested
Reproduction: commands above
Evidence: raw/, analysis/, manifest.json
```
