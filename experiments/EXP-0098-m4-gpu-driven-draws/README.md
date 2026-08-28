# EXP-0098 — M4 GPU-driven draws and compute-emulated transform feedback

Closes addendum items **GLPRE-A01**, **GLPRE-A02**, **GLXFB-A01** (`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md`),
per `work/ADDENDUM-TRIAGE-20260828.md` Bundles H and I. Full question, hypotheses, falsifiers,
mechanism design, and clean-room boundary: `PRE_REGISTRATION.md`. Full results: `RESULTS.md`.

Target: local Apple M4 (G16G) only. A18 Pro hands-off, untouched. Public Metal API surface only —
no assembler, no native VDM/CDM grammar, `tools/*` unused.

## What this experiment does

- **Bundle H (GLPRE-A01/A02).** A compute kernel — never the CPU, never a prior encoder's
  `-[MTLBuffer contents]` write — writes vertex data, index data, and
  `MTLDraw[Indexed]PrimitivesIndirectArguments` records that a following render draw consumes.
  Tests the exact synchronization contract required (six named strategies, including
  deliberately-unsynchronized and asymmetric-fence controls), which indirect-argument fields are
  honored and with what values, and the finite-resource boundaries of
  `MTLIndirectCommandBufferExecutionRange`-driven device-generated draw counts and
  `maxCommandCount`.
- **Bundle I (GLXFB-A01).** A compute kernel captures synthetic primitives into up to four
  independent streams/buffers via atomic-counter-gated global-memory writes (modelling OpenGL
  transform feedback), enforcing whole-primitive-only capacity, then a second compute kernel
  writes an indirect draw record from the captured count that a replay draw consumes. Reuses
  Bundle H's synchronization matrix for the streamout→draw handoff.

## Build

```sh
clang -fobjc-arc -framework Metal -framework Foundation -Wall -Wno-deprecated-declarations \
  -o work/bin/gddraws harness/gddraws.m
clang -fobjc-arc -framework Metal -framework Foundation -Wall -Wno-deprecated-declarations \
  -o work/bin/xfbdraws harness/xfbdraws.m
```

## Run

```sh
python3 harness/run.py --list                                   # inspect the frozen 111-case matrix
python3 harness/run.py --run m4_20260828_run01 --out raw/m4_20260828_run01
python3 harness/run.py --run m4_20260828_run02 --out raw/m4_20260828_run02
```

## Verify (standing gate set)

```sh
python3 harness/verify.py --selftest                              # offline, no device
python3 harness/verify.py --seqtest                                # offline, no device
python3 harness/verify.py --preflight                              # before run01
python3 harness/verify.py --between-runs                           # after run01, before run02
python3 harness/verify.py --captured m4_20260828_run01 m4_20260828_run02   # after run02
```

## Layout

```
PRE_REGISTRATION.md       question, hypotheses/falsifiers, mechanism design, build-time
                           calibration findings, frozen matrix description, clean-room boundary
CAPTURE_CONTRACT.json     pinned revision, authored-file hashes, schema, matrix, timeouts, gates
RESULTS.md                observed vs interpreted, response blocks, finite-resource tables
PROGRESS.md               timestamped milestones
kernels/*.metal           authored MSL (OWN-SHADER) -- the only machine code this experiment
                           produces or inspects
harness/gddraws.m          Bundle H binary (h_sync, h_fields, h_icbrange, h_icbmax families)
harness/xfbdraws.m         Bundle I binary (xfb_capacity, xfb_multistream, xfb_discard, xfb_sync)
harness/schema.py          shared gated/nongated record schema (standing gate (a))
harness/casematrix.py      frozen 111-case matrix + order-sensitive-key declarations
harness/run.py             executor: smoke gate, hard timeouts, one case per process
harness/verify.py          --selftest / --seqtest / --preflight / --between-runs / --captured
harness/fixtures/          recorded_reality.json -- real M4 captures backing --selftest
raw/                       append-only capture output (two run directories)
work/                      build products, non-recorded smoke receipts (never raw/)
```
