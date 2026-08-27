# EXP-0072 pre-registration — M4 public typed-format conversion, batch 2

**Frozen state: PRE-GPU.** This is the second bounded increment of task-list item
DRV-FMT-01 (per-format capability and conversion table) in
`APPLE9_RE_IMPLEMENTATION_GAPS.md`, succeeding EXP-0070 (batch 1, fragment-store
path, six formats). No GPU compilation, dispatch, or capture has occurred for
EXP-0072. One host-side, syntax-only compile check of our own harness source
(`xcrun clang -fsyntax-only -fobjc-arc harness/probe.m ...`, writes no files)
was run after the self-test passed, to rule out a trivial host-build death
inside the append-only first run; it produced no artifacts, and its only
diagnostic is a deprecation warning for the still-functional public
`fastMathEnabled` property (explicitly set to NO and recorded per case). The
authoritative frozen case matrix, expected words, and blob hashes live in
`CAPTURE_CONTRACT.json`; this file describes and justifies them.

## Question and bounded hypotheses

For each of the fourteen named public pixel formats, what complete owned backing
bytes follow one authored **compute** store (`access::write`) of authored
constants to the sole texel of a 1x1 texture, and what does one authored,
in-bounds typed compute `read(uint2(0,0))` of the same texture observe in the
same public command buffer? The formats are R8Unorm, R8Snorm, RG8Unorm, RG8Snorm,
RGBA8Snorm, R16Float, RG16Float, R16Sint, R16Uint, R32Float, R32Sint,
RG11B10Float, RGB9E5Float, RGBA16Uint.

Scope note: the dispatch enumerated fourteen format names while stating
"13 formats"; the enumerated list is authoritative and frozen at fourteen.

Per-case testable hypotheses (full table in the contract):

- unorm8: +1.0 -> `ff`, 0.0 -> `00`, and the 0.5 tie (0.5*255 = 127.5) -> `80`
  under round-half-even/half-up, `7f` under truncation;
- snorm8: +1.0 -> `7f` (both candidate public encode scales agree), 0.0 -> `00`,
  the 0.5 tie (63.5 under the x127 scale) -> `40`, and -1.0 -> `80` under the
  [-1,1]->[-128,127] mapping but `81` under the x127-round mapping — the
  physical byte is the discriminator because the typed read decodes -1.0 either
  way;
- fp16 (R16Float/RG16Float): exactly-representable 0.5 -> `0038`; the mid
  literal (not representable in fp16) rounds to `0038` under RNE; 1.0/3.0 ->
  `5535`;
- R32Float: exact passthrough of all three values including the mid literal
  (`ffffff3e`);
- RG11B10Float: exact 0.5 -> `0038c071` (fp11/fp10 fields), and the mid literal
  collapses to the same word (11-bit mantissa boundary);
- RGB9E5Float: exact 0.5 -> `0001027c` (shared exponent M=256, E=15), and the
  mid literal collapses to the same word via mantissa-overflow renormalization
  (flagged uncertain);
- integer formats (R16Sint, R16Uint, R32Sint, RGBA16Uint), stored **as-typed**
  (int4/uint4 through the same compute-store path): exact passthrough of 1, 2,
  and 3855 (0x0F0F).

A public-API rejection at library, pipeline, texture-creation, or command-buffer
level for any case is an expected **classification outcome**, not a failure: the
exact NSError text and the failing stage are recorded data. A changed guard
byte, absent status record, wrong-sized backing, repeat mismatch between runs,
or an unexpected status falsifies the affected hypothesis.

## Authored input values (frozen)

- unorm/snorm families: +1.0, 0.0, 0.5, and -1.0 (snorm only), authored as MSL
  decimal literals.
- Float families: `0.5` (exactly representable in fp16/fp11), the mid literal
  `0.4999999701976776123046875`, and `1.0 / 3.0` (compiler constant fold).
  The dispatch suggested `0.499999988079071044921875`; arithmetic host check
  shows that decimal rounds to fp32 `0x3F000000` (exactly 0.5), which cannot
  exercise any mantissa boundary. The frozen mid literal is
  `0.5 - 2^-25 = 0.4999999701976776123046875` = exact fp32 `0x3EFFFFFF`: not
  representable in fp16 or fp11, and inside the round-to-0.5 zone of both
  (fp16/fp11 halfway point 0.4998779296875).
- Integer formats: 1, 2, 3855 (0x0F0F), stored as-typed via `texture2d<int/uint,
  access::write>`; the same compute-store path as the float formats (frozen
  choice, recorded here and in the contract).

## Exact method and controls

Each case is one fresh process with its own device, command queue, library
(runtime `newLibraryWithSource:` with `MTLCompileOptions.fastMathEnabled = NO`),
compute pipelines, command buffer, and exactly two *owned* shared buffers: the
texture backing (64 `0x5a` guard bytes, a 256-byte payload row, then 64 `0xa5`
guard bytes; the 1x1 texture occupies the payload start at offset 64 with
`bytesPerRow=256`) and the typed-read result (64 `0x5a`, sixteen result bytes,
64 `0xa5`). Kernel 1 (`s_<case>`) stores the authored constant to `uint2(0,0)`
only; kernel 2 (`k_read_float` / `k_read_int` / `k_read_uint`) reads
`uint2(0,0)` only and emits four little-endian uint32 words. There is no
out-of-bounds path and no blit. After command-buffer completion the harness
prints public status/error information plus complete owned buffer hex. It never
retains or inspects compiled shader bytes, archives, command streams, BOs,
pointers, private interfaces, or Apple helpers. The frozen readback path is the
typed compute read; the owned backing bytes are read directly from our own
buffer as physical-texel evidence.

Hard timeouts: environment commands 5 s each, host clang build 120 s, per-case
process 300 s, with in-harness phase watchdogs of 120 s (compile phase:
library + pipelines + buffers + texture) and 300 s (dispatch phase: encode +
commit + waitUntilCompleted). A watchdog breach, nonzero exit, or OS error
writes a `STOP.json`, ends the run, and receives no automatic retry. Failure or
timeout of any pre-build environment command is a hard stop before the host
build begins.

Two fresh append-only runs (`m4-20260827-run01`, `m4-20260827-run02`) are
required. Run 01 begins only from the raw-free pre-GPU tree after
`python3 -B verify.py --preflight` passes. Run 02 begins only after
`python3 -B verify.py --between-runs` accepts exactly the complete, closed
run-01 tree and an absent or empty `work/` directory; before creating run 02 the
runner also requires its current Git revision and authored hash map to equal the
closed run-01 record. Final verification additionally requires identical
`sw_vers`, `xcrun --version`, and `sysctl -n hw.model` output and byte-exact
equal case payloads across the two runs.

## Deviation from EXP-0070 provenance binding (deliberate, frozen here)

EXP-0070 bound its captured source hashes to Git blobs via an intermediate
orchestrator commit between phases. EXP-0072 runs under a single-session
no-commit dispatch, so no intermediate commit exists. Instead, `00_inputs.json`
records `git rev-parse HEAD`, a `git_dirty` flag plus the porcelain status of
the experiment directory, `sw_vers`, `xcrun --version`, `sysctl -n hw.model`,
machine, and the SHA-256 of every capture-bound authored blob (the contract,
this file, kernels, harness, and all four Python tools). `verify.py --captured`
fails closed unless the *current on-disk* hashes still equal the captured ones,
which detects any post-capture mutation; the final `manifest.json` then freezes
the complete captured tree for the orchestrator's commit. `README.md`,
`RESULTS.md`, and the incremental `PROGRESS.md` operational log are
documentation, written or extended after capture begins, and are hashed by the
final manifest rather than capture-bound.

## Promotion rule and scope

Before any build, `python3 -B verify.py --preflight` AND
`python3 -B verify.py --selftest` must pass. The self-test (added after
quarantined EXP-0073 died of an unsatisfiable frozen-verifier schema) feeds a
synthetic two-run capture — including every rejection status — through every
schema gate and the run-to-run comparison, proves ten tampered variants fail
closed, and live-cross-checks run.py's record builders and the harness's
printed payload keys against the frozen key sets; it is a contracted
pre-capture gate for BOTH runs. Before any interpretation, `python3 -B
verify.py --captured`, `python3 -B analysis.py --run-a m4-20260827-run01
--run-b m4-20260827-run02 --write`, and `python3 -B make_manifest.py --check`
must all pass for exactly the two contracted runs. Deviations between
preregistered expected words and observed words are RESULTS, recorded verbatim
by the analyzer; they do not fail verification. Until all gates pass, this
increment of DRV-FMT-01 remains **OPEN**. These observations cannot establish
native PBE/epilog behavior, descriptors, Linux mappings, A18/G17P behavior,
filtering, blending, atomics, MSAA, NaN/infinity/subnormal handling,
out-of-range inputs, or general conversion semantics beyond the exact authored
values. Everything here is **M4-target only**.

Clean-room provenance: HW-PROBE / OWN-SHADER source / PUBLIC API (planned only)
Inputs inspected: committed authored MSL, harness, contract, and future owned readbacks
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --preflight`; future capture requires explicit `run.py --execute`
Evidence: no raw observations exist; `CAPTURE_CONTRACT.json` is the frozen capture grammar and expected-word matrix
