# EXP-0075 pre-registration — M4 public typed-format conversion, batch 2

**Frozen state: PRE-GPU.** EXP-0075 is the named successor to quarantined
EXP-0072 (`experiments/EXP-0072-m4-typed-format-conversion-batch2/QUARANTINE.md`).
EXP-0072's run-01 capture is **NON-EVIDENCE** (every case payload was truncated
by a harness print race) and has not been read as data, compared against, or
used to derive anything here. This registration starts fresh: the design is
adopted from EXP-0072's frozen registration, and the only changes are the two
fixes its QUARANTINE.md pins, plus one added per-case environment field. No GPU
compilation, dispatch, or capture has occurred for EXP-0075 at registration
time. The authoritative frozen case matrix, expected words, and blob hashes
live in `CAPTURE_CONTRACT.json`; this file describes and justifies them.

Third bounded increment of task-list item **DRV-FMT-01** (per-format capability
and conversion table) in `APPLE9_RE_IMPLEMENTATION_GAPS.md` (P1.2), succeeding
EXP-0070 (batch 1, six formats, fragment-store path) and the quarantined
EXP-0072 registration (batch 2, fourteen formats, compute-store path).

## The two fixes this experiment exists to make

1. **Process-exit discipline in `harness/probe.m`.** EXP-0072's worker signalled
   its dispatch-phase semaphore before printing while `main()` treated that
   signal as done, so the process ended mid-`printf` and all 34 records were
   truncated at nondeterministic points. Here there is exactly **one** process
   exit call, inside `finish()`, which holds `g_exit_lock` while it prints the
   whole record, then calls `fflush(stdout)` and `fflush(NULL)`, and only then
   `exit(code)`. No thread signals completion before its record is durably
   written — the dispatch-phase semaphore is never signalled at all, and the
   only semaphore signal in the file marks the compile/dispatch phase boundary.
   After both phase waits, `main()` blocks forever (`for (;;) pause();`); it
   never returns and never ends the process. A watchdog breach in `main()` is
   the only other exit path and goes through the same locked `finish()`, so two
   threads can never interleave partial records. `verify.py --preflight`
   enforces the structural form of all of this (single exit call, single
   semaphore signal, lock → print → flush → flush → exit ordering, forever
   block after both waits, no successful return).
2. **A contract-named pre-capture NON-RECORDED smoke invocation.** After the
   host build and BEFORE the append-only `raw/` tree is created, `run.py`
   executes exactly one scratch case (`r32float_exact`) into
   `work/<run-id>/smoke/` (outside `raw/`), and requires its stdout to parse as
   exactly one JSON object with the complete contracted key set, self-consistent
   guard/texel/word data, status `ok`, device `Apple M4`, and a clean command
   buffer. Any payload-shape or truncation defect — including the exact
   EXP-0072 failure class, and even a hypothetical `exit()` hang after printing
   (which would show up as a receipt timeout with a complete record) — becomes
   a **pre-capture STOP**: `raw/` is never created, `work/<run-id>/STOP.json`
   is retained as the failure record, and an authorized pre-capture repair
   remains possible because nothing was captured. The gate is named in
   `CAPTURE_CONTRACT.json` under `capture.pre_capture_smoke` and is exercised
   by `verify.py --selftest` against synthetic payloads, including five
   truncation cut points, before any GPU work.

## Question and bounded hypotheses

For each of the fourteen named public pixel formats, what complete owned backing
bytes follow one authored **compute** store (`access::write`) of authored
constants to the sole texel of a 1x1 texture, and what does one authored,
in-bounds typed compute `read(uint2(0,0))` of the same texture observe in the
same public command buffer? The formats are R8Unorm, R8Snorm, RG8Unorm, RG8Snorm,
RGBA8Snorm, R16Float, RG16Float, R16Sint, R16Uint, R32Float, R32Sint,
RG11B10Float, RGB9E5Float, RGBA16Uint.

Scope note inherited from the EXP-0072 registration: that dispatch enumerated
fourteen format names; the enumerated list is authoritative and frozen at
fourteen.

Per-case testable hypotheses (full table in the contract, rules a/b/c):

- **a** — value exactly representable in the format; word derived from the
  documented channel bit layout only.
- **b** — documented Metal conversion rule (round-to-nearest-even for float
  narrowing; x(2^b-1) scaling for normalized encode) applied to an
  exactly-authored input.
- **c** — explicitly-flagged uncertain: tie rounding (127.5, 63.5), competing
  public snorm encode scales, or shared-exponent renormalization not pinned by
  public specs.

Highlights: unorm8 `0.5` tie `0.5*255 = 127.5` expected `80` (RNE/half-up; `7f`
under truncation); snorm8 `-1.0` expected `80` ([-1,1]→[-128,127] mapping) but
`81` under the x127-round mapping — the physical byte is the discriminator
because the typed read decodes -1.0 either way; fp16 mid literal
`0.5 - 2^-25` rounds to `0x3800`; R32Float passes `0x3EFFFFFF` through exactly;
RGB9E5 shared-exponent overflow-renormalization flagged uncertain.

A public-API rejection at library, pipeline, texture-creation, or command-buffer
level for any case is an expected **classification outcome**, not a failure: the
exact NSError text and the failing stage are recorded data. A changed guard
byte, absent status record, wrong-sized backing, repeat mismatch between runs,
or an unexpected status falsifies the affected hypothesis.

## Independent re-derivation check of the adopted expected words

As the registering author of EXP-0075 I re-derived all 34 expected texel words
and read-word vectors by hand before freezing them. **33 of 34 reproduce the
EXP-0072 registration exactly** (unorm/snorm scales and ties, 64/127 = `3f010204`,
128/255 = `3f008081` as hardware-observed for RGBA8Unorm in EXP-0070, fp16
0.5/`1/3` = `0x3800`/`0x3555` → `0038`/`5535` and `3f000000`/`3eaaa000`,
R32Float passthrough of `0x3EFFFFFF` and `0x3EAAAAAB`, RGB9E5 M=256/E=15 →
`0001027c`, and all ten integer passthrough cases including the RGBA16Uint
halfword order).

**One adopted value is flagged as a suspected derivation slip and kept
nevertheless, because it is a hypothesis to be tested, not a fact:** the
RG11B10Float exact/mid texel word. Under the standard no-sign e5m6/e5m5
layout (R in bits[10:0], G in bits[21:11], B in bits[31:22]), fp11(0.5) =
`0x380` and fp10(0.5) = `0x1c0`, giving word `0x701C0380`, i.e. little-endian
texel hex **`80031c70`** — not the adopted `0038c071` (word `0x71C03800`),
which does not decode to (0.5, 0.5, 0.5) under that layout. The dispatch that
created this successor froze EXP-0072's expected words verbatim, so
`0038c071` is registered as the hypothesis of record for both
`rg11b10float_exact` and `rg11b10float_mid`, and this paragraph is the
pre-registered prediction that the observation will be `80031c70` (or a
rejection). Whichever way the hardware answers, the deviation record is the
deliverable. The read words for those two cases (`3f000000` ×3 + `3f800000`)
are unaffected by the slip.

## Authored input values (frozen)

- unorm/snorm families: +1.0, 0.0, 0.5, and -1.0 (snorm only), authored as MSL
  decimal literals.
- Float families: `0.5` (exactly representable in fp16/fp11), the mid literal
  `0.4999999701976776123046875` (= `0.5 - 2^-25` = exact fp32 `0x3EFFFFFF`,
  not representable in fp16 or fp11, inside the round-to-0.5 zone of both), and
  `1.0 / 3.0` (compiler constant fold). The mid literal deliberately differs
  from `0.499999988079071044921875`, which rounds to fp32 `0x3F000000` and
  cannot exercise any mantissa boundary.
- Integer formats: 1, 2, 3855 (0x0F0F), stored as-typed via
  `texture2d<int/uint, access::write>` through the same compute-store path as
  the float formats (frozen choice).

## Exact method and controls

Each case is one fresh process with its own device, command queue, library
(runtime `newLibraryWithSource:` with `MTLCompileOptions.fastMathEnabled = NO`,
language version left at the host default), compute pipelines, command buffer,
and exactly two *owned* shared buffers: the texture backing (64 `0x5a` guard
bytes, a 256-byte payload row, then 64 `0xa5` guard bytes; the 1x1 texture
occupies the payload start at offset 64 with `bytesPerRow=256`) and the
typed-read result (64 `0x5a`, sixteen result bytes, 64 `0xa5`). Kernel 1
(`s_<case>`) stores the authored constant to `uint2(0,0)` only; kernel 2
(`k_read_float` / `k_read_int` / `k_read_uint`) reads `uint2(0,0)` only and
emits four little-endian uint32 words. There is no out-of-bounds path and no
blit. After command-buffer completion the harness prints public status/error
information plus complete owned buffer hex. It never retains or inspects
compiled shader bytes, archives, command streams, BOs, pointers, private
interfaces, or Apple helpers.

**Environment capture (frozen):** `00_inputs.json` records `git rev-parse HEAD`,
a `git_dirty` flag plus the porcelain status of the experiment directory,
`sw_vers`, `xcrun --version`, `sysctl -n hw.model`, machine, and the SHA-256 of
every capture-bound authored blob. Per case, the record carries
`fast_math_enabled: false` (explicitly set) and `msl_language_version`, the raw
public `MTLCompileOptions.languageVersion` value read from a freshly allocated
options object before anything is set on it — the public-API MSL language
datum for this host. Nothing else about the compiler is recorded or inspected.

Hard timeouts: environment commands 5 s each, host clang build 120 s, per-case
process 300 s, with in-harness phase watchdogs of 120 s (compile phase: library
+ pipelines + buffers + texture) and 300 s (dispatch phase: encode + commit +
waitUntilCompleted). A watchdog breach, nonzero exit, or OS error during the
capture writes a `STOP.json`, ends the run, and receives no automatic retry.
Before the capture begins, an environment-command or host-build failure stops
the run pre-capture (retained `work/<run-id>/STOP.json`, no `raw/` tree), so
such a failure never consumes the append-only capture. Failure or timeout of
any pre-build environment command is a hard stop before the host build begins.

Two fresh append-only runs (`m4-20260827-run01`, `m4-20260827-run02`, the
actual capture date) are required. Run 01 begins only from the raw-free
pre-GPU tree after `python3 -B verify.py --preflight` and
`python3 -B verify.py --selftest` pass and after the non-recorded smoke
invocation passes. Run 02 begins only after `python3 -B verify.py
--between-runs` accepts exactly the complete, closed run-01 tree with `work/`
absent or empty and `python3 -B verify.py --selftest` passes again; before
creating run 02 the runner also requires its current Git revision and authored
hash map to equal the closed run-01 record. Final verification additionally
requires identical `sw_vers`, `xcrun --version`, and `sysctl -n hw.model`
output and byte-exact equal case payloads across the two runs.

## Deviation from EXP-0070 provenance binding (deliberate, frozen here)

EXP-0070 bound its captured source hashes to Git blobs via an intermediate
orchestrator commit between phases. EXP-0075 runs under a single-session
no-commit dispatch, so no intermediate commit exists. Instead,
`00_inputs.json` records the revision/dirty state and the SHA-256 of every
capture-bound authored blob (the contract, this file, kernels, harness, and all
four Python tools). `verify.py --captured` fails closed unless the *current
on-disk* hashes still equal the captured ones, which detects any post-capture
mutation; the final `manifest.json` then freezes the complete captured tree
for the orchestrator's commit. `README.md`, `RESULTS.md`, and the incremental
`PROGRESS.md` operational log are documentation, written or extended after
capture begins, and are hashed by the final manifest rather than
capture-bound. Editing them between runs is therefore safe; editing any
capture-bound blob between runs aborts run 02 by design.

## Promotion rule and scope

Before any build, `python3 -B verify.py --preflight` AND
`python3 -B verify.py --selftest` must pass, and the non-recorded smoke
invocation must pass before `raw/` is created. The self-test feeds a synthetic
two-run capture — including every rejection status — through every schema gate
and the run-to-run comparison, proves tampered variants fail closed (including
a truncated case stdout, the EXP-0072 class), live-cross-checks run.py's record
builders and the harness's printed payload keys against the frozen key sets,
and live-exercises run.py's smoke validator against the truncation class and
eight other payload defects. Before any interpretation, `python3 -B verify.py
--captured`, `python3 -B analysis.py --run-a m4-20260827-run01 --run-b
m4-20260827-run02 --write`, and `python3 -B make_manifest.py --check` must all
pass for exactly the two contracted runs. Deviations between preregistered
expected words and observed words are RESULTS, recorded verbatim by the
analyzer; they do not fail verification. Until all gates pass, this increment
of DRV-FMT-01 remains **OPEN**. These observations cannot establish native
PBE/epilog behavior, descriptors, Linux mappings, A18/G17P behavior,
filtering, blending, atomics, MSAA, NaN/infinity/subnormal handling,
out-of-range inputs, or general conversion semantics beyond the exact authored
values. Everything here is **M4-target only**.

Clean-room provenance: HW-PROBE / OWN-SHADER source / PUBLIC API (planned only)
Inputs inspected: committed authored MSL, harness, contract, and future owned readbacks
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --preflight`; future capture requires explicit `run.py --execute`
Evidence: no raw observations exist; `CAPTURE_CONTRACT.json` is the frozen capture grammar and expected-word matrix
