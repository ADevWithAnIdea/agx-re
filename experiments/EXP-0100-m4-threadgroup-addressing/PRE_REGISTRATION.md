# EXP-0100 pre-registration — M4 threadgroup addressing (GLCS-A01/GLCS-A02, Bundle F)

**Successor of `../EXP-0096-m4-threadgroup-addressing`** (see its `QUARANTINE.md`).
EXP-0096's `run01` (2900 splice cases, 145 budget cases) completed cleanly and completely
-- `STATUS OK` for all 2900 splice cases; 109 `OK` / 36 `PIPELINE_FAIL` for the 145 budget
cases, exactly matching the `BUDGET-STATIC-CAP` cases expected to fail pipeline creation
above the calibrated 32768-byte ceiling -- but a real, narrowly-scoped bug was found in
`verify.py::_build_tree`'s synthetic-fixture generator (NOT in the runner, matrix, kernels,
or captured data) that only activates once `raw/` exists in the real tree, permanently
blocking `verify.py --selftest` (an unconditional pre-run gate) for that experiment's own
run02. Per the standing rule against post-capture repair of a hash-frozen authored file,
EXP-0096 was quarantined rather than patched in place; this experiment applies the one-line
fix BEFORE any capture (see `verify.py`'s inline comment citing this history) and starts a
completely fresh two-run promotion under its own new pre-registration. The kernels, the
2900+145-case matrix (byte-identical to EXP-0096's, not re-tuned from its unpromoted run01
data), `baseline.py`'s probe locators, and `run.py` are otherwise UNCHANGED. EXP-0096's
run01 is cited below only as authoring-stage/process-history corroboration that the harness
executes cleanly end-to-end on this M4 host, never as promoted GLCS-A02 evidence.


## Scope note on GLCS-A01

Bundle F's own text (`work/ADDENDUM-TRIAGE-20260828.md` "Bundle F") closes **GLCS-A02
only** ("threadgroup addressing and compute launch capacity" is the bundle's title, but
its "Closes:" line and "Probe shape" both name GLCS-A02 exclusively — the `tg_addr_compute`
splice matrix and the threadgroup-memory public-Metal boundary sweep). GLCS-A01 (the
complete compute system-value/launch ABI — local/global invocation ID, workgroup
size/count, subgroup ID, variable-group-size dispatch) is a **separate, larger item** this
experiment does not attempt; where a GLCS-A01 fact is needed as a controlled variable here
(e.g. `thread_position_in_threadgroup`, dispatch geometry) it is used as a known-good
input, not re-derived. This experiment's own verdict is GLCS-A02 only.

## Question

`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md` GLCS-A02, in full:

> What is the complete Apple9 compiler and command ABI for OpenGL `shared` memory? Decode
> the threadgroup load/store address calculation, including the inferred `0x1c`
> address/base operation, all source and destination fields, byte versus element units,
> immediate and dynamic offset ranges, legal access widths and vector lengths, alignment
> requirements, and interaction with threadgroup atomics and barriers. Execute
> independently assembled 8-, 16-, 32-, 64-, and 128-bit accesses where legal, including
> unaligned and boundary-crossing cases. Determine the safe behavior of zero-size,
> one-past-end, partially out-of-range, and malformed accesses rather than extrapolating
> device-memory behavior. Decode the CDM/USC fields allocating static and dynamic
> threadgroup memory. Establish the exact maximum bytes per workgroup on G16G and G17P,
> allocation granularity, base alignment, combination of static and dynamic allocation,
> relationship to local size/GPR/scratch occupancy, zero-allocation encoding, largest legal
> value, first illegal value, and exhaustion result. Distinguish pipeline or dispatch
> rejection, reduced occupancy, firmware rejection, fault/device loss, and aliasing. Record
> the conservative OpenGL limit and validation rule a later driver must use.

Per `CLAUDE.md`/`CODEX.md` target discipline: **local M4 only** for every executed probe;
G17P is `INFERRED`-by-family (M4 is Apple9-equal for every driver-emittable subsystem,
`EXP-M4-*`), never independently validated here (A18 hands-off).

## Method (copied from `../EXP-0082-m4-mem-offset-semantics`)

A large frozen splice matrix, one field FAMILY changed per case, each case its own
process, an exact host-computed expected observation per case decided BEFORE any GPU
dispatch, two full capture runs, byte-exact cross-run comparison on the deterministic
payload only. Extended with a second, non-splicing case family (BUDGET) for the public-Metal
boundary sweep half of GLCS-A02, sharing the same contract/gates/runs.

### Two splice mechanisms (first-class tooling-gap finding, not a shortcut)

`tools/agx-isa/db.json`'s `tg_addr_compute` entry models `b3`/`b4`/`b5` (byte+3/4/5) as
real fields (type `"mod"`); byte0 (whole byte, `match` value `0x1c`) and byte+1 (`match`
value `0x02`) are pinned by the `match` clause even though the entry's own prose calls
byte0's high nibble and byte+1 "LIVE dst-register/operand selector" fields (prior A18
evidence, EXP-M4-14). **`tools/agx-isa`'s assembler cannot express a byte0-hi or byte+1
variant through its field mechanism.** Per the dispatch's own instruction ("if the
assembler cannot express an encoding you need, that is a first-class finding: record it
precisely and continue"), this experiment splices those two positions by **direct raw
byte patch** (`raw_byte0_hi` / `raw_byte1` / `raw_byte2` in `casematrix.py`), and
`b3`/`b4`/`b5` through the normal `isadb.decode_one`/`assemble` round trip. `run.py::splice_case`
asserts the two mechanisms are never mixed in one case. `kernels/tg_ld.metal` /
`kernels/tg_st.metal` probe the ordinary `device_load`/`device_store` family with the
threadgroup space bit set — `idx_off`/`elem_size`/`index_reg`/`space` ARE real `isadb`
fields there, so those cases use `isadb.assemble` exclusively, exactly as EXP-0082.

### Downstream-consumer-read discipline (never the spliced instruction's "own" result)

Every splice case's OBSERVATION is a downstream consumer, never the spliced instruction's
own immediate output: `tga` cases read the full 256-value per-thread output array (the
result of two later threadgroup reads that consume whatever the spliced-affected
populate write left behind); `tg_ld`/`tg_st` cases read the value the *later* load
returned, or scan the *entire* 8 KiB readback buffer for the store's effect. This is the
same discipline `docs/isa/register-move-and-liveness.md` established was necessary (a
splice that only re-checks its own instruction's result cannot detect a liveness/retention
failure, whose effect is defined to appear only at a LATER consumer).

## IMPORTANT new input incorporated before freezing (coordinator steering, mid-authoring)

`apple9_isa_explainer.md` (repo root) and `work/COMPILER-EXPLAINER-INTERACTION-20260828.md`:
an external compiler engineer's cross-checked bit tables found a **confirmed decoding bug**
in `tools/agx-isa/db.json`'s `falu2` (6-byte compact float) field layout — the nominal top
bit of the 7-bit `srcA_reg`/`srcB_reg` fields (bit 15 / bit 31) is a per-source **retention**
flag, not part of the register index; two instructions differing ONLY in retention state
decoded to "register numbers" 64 apart under the old layout. That is a *different*
instruction family from `tg_addr_compute` (no direct bit-position transfer), but the
methodological lesson is directly relevant to this experiment: **do not assume a
`db.json`-described "register/operand selector" field is a clean linear index without a
downstream-consumer-read check.** `EXP-0099` is settling the general register-field/
retention-flag question on hardware in parallel; this experiment cross-references it and
does not duplicate or import its unverified specifics. Concretely for EXP-0100:

- `casematrix.py`'s `TGA-DSTREG` family (byte0 high nibble, 16-value sweep) carries an
  explicit caution and a `tga_dstreg_bit3_pairs()` helper; `analysis.py`'s
  `tga_retention_pairs()` tests, for each `(hi, hi|0x8)` pair, whether the two values
  produce IDENTICAL downstream output (bit3 inert for this observable) or DIFFERENT
  output — without asserting a width claim the 256-value downstream array cannot support
  on its own. No new GPU cases were added for this; the already-planned full 16-value
  sweep already carries the needed data.
- The same caution applies qualitatively to `TGA-SRCSEL` (byte+1, full 256-value sweep)
  and to `TGLS-LD-IDXREG`/`index_reg`: `index_reg` is an already-`HW-VALIDATED` field
  (EXP-0082, device space, differentiated-GPR-content readback) whose *threadgroup-space*
  behavior this experiment re-checks rather than assumes; any surprising pattern in either
  family's dense sweep is reported descriptively, not forced into an index-only reading.

## Authoring-stage findings (compile-only / compile+dispatch-of-unmodified-or-single-scratch-splice
only; nothing below is promoted evidence — see "Authorized pre-capture plumbing validation")

1. **`tg_addr_compute` is emitted only for a compile-time-constant-offset masked-index
   shape.** Three independent authored kernel variants that computed the threadgroup
   offset from device/`idxbuf` memory at runtime (instead of a compile-time constant
   `+1`/`+2`) did NOT emit `tg_addr_compute` at all — confirmed by direct disassembly with
   `tools/agx-isa/isadb.py` of all three. `kernels/tga.metal` therefore reproduces the
   proven-emitting shape (own-MSL, mirrors prior A18 evidence's `k_thr.metal` /
   EXP-M4-14) verbatim in structure; the splice matrix supplies ALL the address variation
   instead of an `idxbuf`-controlled runtime index. Negative result, recorded as a
   first-class finding per `CLAUDE.md`'s methodology section.
2. **`kernels/tga.metal` compiled on this M4 host reproduces prior A18 evidence exactly,
   both baseline and under a scratch splice.** Baseline (unspliced) dispatch: `o[i]` for
   `i=0..253` is `2i+3`, wrapping to `255, 1` at `i=254,255` — byte-identical to the A18
   record in `tools/agx-isa/db.json`'s `tg_addr_compute` provenance. One scratch splice
   (`byte0` `0x1c`→`0x2c`) reproduced the documented A18 corruption pattern
   `o[i]=(i+2)&255` exactly.
3. **`kernels/tg_ld.metal`/`tg_st.metal` each contain EXACTLY ONE threadgroup-space
   `device_load`/`device_store`**, located by a structural rule (`baseline.py::locate_probe`):
   the unique `device_load` with the threadgroup space bit set (`tg_ld`), or the unique
   threadgroup-space `device_store` occurring AFTER the first `threadgroup_barrier`
   (`tg_st`, which disambiguates it from four compiler-unrolled zero-fill stores that
   precede the barrier). Both probes round-trip through `isadb.assemble(decode(...))`.
   One scratch splice (`tg_ld`, `idx_off`→`1`) moved the read from element 64 to element
   65 exactly, confirming H-ELEM (offset in ELEMENT units, added before the element-size
   scale) carries over from device space (EXP-0082) to threadgroup space, at least at this
   one point.
4. **Threadgroup-space `elem_size`/`ld_format` do NOT match the device-space code table.**
   `tg_ld.metal`'s baseline probe decodes `elem_size=0x08`, `ld_format=0x04` — neither
   value appears in EXP-0082's device-space `ELEM_BYTE` table (`{0x40,0x42,0x44,0x46,0x48}`).
   This experiment therefore does NOT assume a code table for threadgroup space and
   sweeps `elem_size` exhaustively (`TGLS-LD-01`, full byte 0x00–0xFF) instead of spot-
   checking five hypothesized codes.
5. **`tgbudget.m` v1→v2 correction (compiler-optimization artifact, not a hardware
   finding).** A first draft's canary kernel touched only compile-time-constant indices
   (`tile[0]`, `tile[N-1]`); LLVM's SROA proved those were the array's only live elements
   and discarded the rest of the allocation — `staticThreadgroupMemoryLength` read back a
   constant 16 bytes for every requested size including 65536, and a linear per-byte fill
   pattern (`(k*7+3)&0xFF`, period 256) was independently BLIND to any aliasing with a
   period dividing 65536 (the exact period this experiment went on to find — see below).
   v2 indexes every touched byte by `thread_position_in_threadgroup` strided across a
   RUNTIME loop bound, and verifies with a bit-mixing (multiplicative, non-periodic-in-
   any-small-range) hash (`(k*2654435761u)>>24`), which the compiler cannot fold away and
   which does not alias with any power-of-two period in the tested range.
6. **Authoring-stage calibration (v2 tool, compile+dispatch, scratch, unpromoted) located
   two real hardware boundaries**, used to choose this experiment's frozen ranges:
   - STATIC (`threadgroup T tile[N]`, compile-time size): `MTLComputePipelineState`
     creation FAILS once the requested size (rounded to a 4-byte granularity in the
     observed error text, e.g. a 32769 B request is reported as requiring 32772 B) exceeds
     32768 B; the QUERIED `staticThreadgroupMemoryLength` property itself rounds up to a
     16-byte granularity (e.g. 100→112, 1000→1008, 4097→4112). A hard, clean
     pipeline-creation-time rejection — never a dispatch fault.
   - DYNAMIC (`setThreadgroupMemoryLength:`) and COMBINED (static + dynamic declared in
     the SAME kernel): **NOT validated by pipeline creation at all.** A kernel dispatches
     "successfully" (`STATUS OK`, no command-buffer error) for any requested size tested
     (up to 1 MiB), but data SILENTLY CORRUPTS once the TOTAL declared+requested
     footprint (static bytes + dynamic bytes, regardless of the split — confirmed
     identical boundary at static∈{0,4096,8192,16384,32768}) exceeds **65536 bytes (64
     KiB)**. Beyond that boundary the corrupted-byte count grows in a pattern consistent
     with (not yet proven to be exactly) a 64 KiB physical aliasing window shared by
     static and dynamic threadgroup memory. This is the calibration basis for the frozen
     `BUDGET-DYNAMIC-CAP`/`BUDGET-COMBINED` ranges below; the capture proper re-derives it
     as promoted evidence (not the calibration numbers themselves).

## Hypotheses (falsifiable, frozen)

- **H-TGA-LIVE**: `tg_addr_compute`'s byte0 high nibble and byte+1 are load-bearing
  (perturbing either changes the downstream 256-value array from the baseline `2i+3`
  pattern), consistent with prior A18 evidence. Refuted by any value leaving the array
  byte-identical to baseline across the FULL 16-value / 256-value sweep (would mean the
  prior finding does not reproduce on M4).
- **H-TGA-RESERVED**: `b3`/`b4`/`b5` (the DB's true fields) are inert on M4 across the
  representative sweep and the simultaneous ff/ee/dd perturbation, matching prior A18
  evidence. Refuted by any single value or the simultaneous case changing the array.
- **H-ELEM-TG**: threadgroup-space `device_load`/`device_store` `idx_off` is an ELEMENT-unit
  additive immediate applied before the element-size scale (mirrors EXP-0082's device-space
  H-ELEM), for the scalar 4-byte access this matrix exercises. Refuted by any dense-sweep
  case landing at a byte offset inconsistent with `element = idx_off` (idx=0 anchor, so
  predicted byte offset = `idx_off * 4` exactly for every field value 0..2047).
- **H-TG-BOUNDARY-STATIC**: the public-Metal STATIC threadgroup-memory ceiling on M4 is
  32768 bytes, enforced by pipeline-creation-time rejection (not a dispatch fault),
  matching `EXP-0024`'s A18-side finding and this experiment's own authoring-stage
  calibration. Refuted by any dense-bracket case at ≤32768 B failing pipeline creation, or
  any case >32768 B succeeding.
- **H-TG-BOUNDARY-COMBINED**: the DYNAMIC and COMBINED (static+dynamic) threadgroup-memory
  ceiling is a SHARED 65536-byte total, NOT independently validated by the public Metal
  API, with exceeding it producing silent data corruption rather than a clean rejection.
  Refuted by (a) any total >65536 B remaining clean (`bad_byte_count==0`), (b) any total
  ≤65536 B corrupting, or (c) the boundary value differing by static/dynamic split.

- Independent variables: the spliced field family (splice cases, one per case) or the
  static/dynamic byte counts (budget cases, one per case).
- Controlled variables: kernel sources (hash-frozen), compile options (`--no-fast-math`),
  dispatch geometry per kernel (frozen in `casematrix.py`/`agxtest_argv`), the splice path
  (agxtest + binary archive + `FailOnBinaryArchiveMiss` for splice cases; a fresh
  `newLibraryWithSource:` compile + pipeline + dispatch for budget cases), buffer fill
  patterns, and the baseline anchors (re-derived at capture; drift = STOP).
- Refuters (cross-cutting): (1) any self-test/seqtest/preflight failure before capture;
  (2) non-byte-exact repeat between run01/run02 of either semantic payload
  (`04_results.jsonl`, `06_budget_results.jsonl` — the two `*_timing.jsonl` files are
  never refuters, by design); (3) the six-entry hand-validation set diverging; (4) any
  fault/timeout pattern differing in KIND between runs (status counts must match exactly).
- Known confounders: the Metal compiler's register allocation is not observed and not
  assumed — baseline (unspliced) instructions are correct by construction and every
  splice preserves all bytes outside the ONE changed field family (asserted byte-wise by
  `run.py::splice_case`); an out-of-allocation threadgroup access may return 0, garbage,
  fault the command buffer, alias, or (for stores) corrupt memory outside the intended
  region — each outcome is a recorded failure-mode datum, never retried in place; the
  budget sweep's fresh-compile-per-case path means compiler code generation (not address
  splicing) is the independent variable there, so a budget-case "failure" could in
  principle reflect a compiler decision rather than a hardware limit — the STATIC ceiling's
  clean pipeline-creation-time rejection (not a dispatch fault) is consistent with a
  genuine hardware/driver-enforced limit rather than an emergent compiler artifact, and
  RESULTS.md states this distinction explicitly rather than asserting hardware causation
  the data cannot fully exclude.

## Authorized pre-capture plumbing validation (no observation recorded as evidence)

Performed and cited above only as authoring-stage motivation (never promoted, never a
`raw/` artifact — identical in kind to the in-run smoke gate, the lesson of the quarantined
EXP-0072): (1) unmodified `tga`/`tg_ld`/`tg_st` archives run once each to confirm the
dispatch/readback path and the exact baseline values; (2) one scratch splice per kernel
(`tga` byte0, `tg_ld` `idx_off`) to confirm the splice mechanism and observe the predicted
shift; (3) `tgbudget` v1 (flawed) and v2 (corrected) run interactively across a wide,
unfrozen range of static/dynamic byte counts to locate the two boundaries the frozen
`BUDGET-*` ranges below bracket.

## Exact frozen method

1. `run.py --execute --run-id m4-20260828-run01|run02` refuses to run without `--execute`,
   requires `verify.py --selftest` AND `verify.py --seqtest` to pass first (runnable in
   every tree state), then the state gate (`--preflight` for run01, `--between-runs` for
   run02).
2. Provenance (git revision + dirty flags, sw_vers, xcrun, python, machine, SHA-256 of every
   authored blob) is recorded; run02 additionally must match run01's revision and authored
   hashes exactly. **Revision is pinned at THIS registration; the gate compares against the
   recorded run01 value, never against live `HEAD`** — a sibling experiment's commit
   landing between run01 and run02 is not contamination (this is the documented lesson of
   EXP-0082's own near-miss).
3. Build phase: `harness/build.sh` compiles the read-only tool sources
   (`tools/shdump/shdump.m`, `tools/agxtest/agxrun.m`) plus this experiment's own
   `harness/tgbudget.m` into `work/<run>/`; `baseline.py --bin-dir` re-compiles all three
   probe kernels, re-derives the anchors, and STOPs on any drift from the frozen anchors
   below.
4. TWO non-recorded smoke gates run in `work/` before any `raw/` artifact: one spliced
   scratch SPLICE case (`tg_ld`, `idx_off=1`, idx=64) and one scratch BUDGET case
   (`static`, 256 bytes). Either failing is a `STOP.json` at phase `smoke_gate_splice` or
   `smoke_gate_budget`; no capture is burned on a harness defect.
5. The SPLICE sweep: for each of the **2900** frozen splice cases, ONE field-family splice
   (raw byte patch or `isadb.assemble`, per kernel/field), executed via
   `tools/agxtest/agxtest.py` → `agxrun` in a fresh process, hard timeout 60 s. The
   semantic observation is appended to `raw/<run>/04_results.jsonl` (flushed per case);
   nondeterministic fields go to the sibling `raw/<run>/04_timing.jsonl`.
6. The BUDGET sweep: for each of the **145** frozen budget cases, one fresh
   `harness/tgbudget` invocation (own-argv-parametrized MSL, no splicing), hard timeout
   30 s, appended to `raw/<run>/06_budget_results.jsonl` / `06_budget_timing.jsonl` with
   the same flush-per-case and fresh-process-per-case discipline.
7. A fault (`CMDBUF_ERROR`), hang (`HANG`/timeout), or `EXCEPTION` is a recorded RESULT;
   the sweep continues in a fresh process.
8. Two runs are required, each in a fresh process; final verification requires BOTH
   `04_results.jsonl` and `06_budget_results.jsonl` to be byte-identical and both status-count
   maps identical. The two `*_timing.jsonl` files are schema-checked each run but NEVER
   required to match across runs (by design).

## Frozen matrix summary (full detail: `casematrix.py`)

SPLICE: **2900** cases — `tga` (CTRL 1, TGA-DSTREG 16, TGA-SRCSEL 256, TGA-LENDISC 38,
TGA-RESERVED 94 = 405); `tg_ld` (CTRL 3, TGLS-LD-03 2176, TGLS-LD-01 256, TGLS-LD-IDXREG 10,
TGLS-LD-05 5, TGLS-LD-EXTRA 4 = 2454); `tg_st` (CTRL 2, TGLS-ST-03 21, TGLS-ST-01 16,
TGLS-ST-05 2 = 41).

BUDGET: **145** cases — BUDGET-STATIC-CAP 72 (coarse capacity sweep 0..131072 + dense
bracket 32765..32799), BUDGET-DYNAMIC-CAP 42 (coarse sweep + dense bracket 65530..65544 +
periodicity characterization to 1 MiB), BUDGET-COMBINED 31 (four static/dynamic splits ×
boundary-bracket dynamic sweep, plus a non-power-of-two-static granularity cross-check).

## Frozen hand-validation set (6 entries)

`casematrix.py::hand_validation()`: `tga_ctrl` → matches the analytic baseline array
(`2i+3` wrap `255,1`); `tga_dstreg_2` → matches the known `(i+2)&255` A18 corruption
pattern; `ld_ctrl_idx64` → decoded element 64; `ld_range_f0000` → decoded element 0;
`ld_range_f2047` → decoded element 2047; `st_ctrl_idx64` → store byte offset 256. Any
divergence is an analysis-gate failure (STOP-equivalent for interpretation).

## Environment, timeouts, raw schema (frozen)

- Target: the local Apple M4 (G16G, 10 cores, macOS 26.6.2 build 25G82, Metal 4) through
  public Metal only. A18 hands-off; `macvdmtool` never.
- Hard timeouts (seconds): environment commands 10; harness build 60; baseline derivation
  180; every splice-case process 60; every budget-case process 30; every smoke case 60.
- Raw schema per run (append-only, regular files only): `00_inputs.json`,
  `01_cases.json` (splice matrix echo), `01b_budget_cases.json` (budget matrix echo),
  `02_build.json`, `03_dispatch.json`, `04_results.jsonl`/`04_timing.jsonl` (splice
  semantic/timing), `06_budget_results.jsonl`/`06_budget_timing.jsonl` (budget
  semantic/timing), `05_run_manifest.json`. `STOP.json` ends a run; never an automatic
  retry.

## Promotion rule and scope

Before any capture, in this exact order and all passing: `verify.py --selftest`,
`verify.py --seqtest`, `make_manifest.py --check`, `verify.py --preflight`. Before run02:
the same four with `--between-runs`. After run02: `analysis.py --write`,
`make_manifest.py --write && --check`, `verify.py --captured` — all must exit zero (the
six-entry hand set reproduced, both semantic payloads byte-identical across runs). Until
then GLCS-A02 remains **Open** for the M4.

Scope: local M4 public-Metal splice + boundary-sweep evidence on the three frozen splice
kernels and the `tgbudget` budget-sweep tool, for the exact 2900+145-case matrix, in the
exact compiled/generated forms frozen above. No A18 (G17P) inference beyond the standing
`INFERRED`-by-family label (hands-off), no Linux/UAPI claim, no M5 evidence.

Clean-room provenance: HW-PROBE / OWN-SHADER (authoring stage compile-only and
compile+dispatch calibration; capture planned)
Inputs inspected: authored MSL, harness, runner/verifier/analysis/matrix/baseline modules,
our own compiled shader bytes (splice targets and budget-sweep compiled forms); PUBLIC
reference material `apple9_isa_explainer.md` and its own internal cross-check document
`work/COMPILER-EXPLAINER-INTERACTION-20260828.md` (read for methodological caution only;
no unverified specific claim from either is imported as an established fact here)
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --selftest && python3 -B verify.py --seqtest &&
python3 -B make_manifest.py --check && python3 -B verify.py --preflight`; capture requires
explicit `run.py --execute`
Evidence: no raw observations exist at freeze; `CAPTURE_CONTRACT.json` is the frozen grammar
