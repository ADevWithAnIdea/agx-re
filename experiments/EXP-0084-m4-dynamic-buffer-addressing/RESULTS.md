# EXP-0084 results — M4 dynamic buffer addressing (MEM-20/21/22)

**Status: CAPTURED.** Both contracted runs (`raw/m4-20260827-run01`,
`raw/m4-20260827-run02`) closed clean; `verify.py --captured` passes;
`04_results.jsonl` is **byte-identical, in full, across both runs** (no
carve-out — see "Cross-run gate" in `PRE_REGISTRATION.md`). Target: local
**Apple M4 (G16G)**, macOS 26.6.2 (25G82), Metal 4, `fastMathEnabled=NO`,
`mathMode=Safe` unless noted.

## OBSERVED (directly, from `raw/m4-20260827-run01/04_results.jsonl` and
`raw/m4-20260827-run02/04_results.jsonl`, before interpretation)

- 14/14 cases recorded in both runs; both runs identical case-for-case.
  Status counts (identical both runs): `ok` 10, `compile_reject` 2,
  `identification_failed` 2, `cb_error` 0, `refuted`/`confirmed` 0,
  `watchdog`/`proc_fail`/`proc_timeout` 0. No fault, hang, or crash anywhere
  in the matrix.
- `analysis.py` (repeatable, run against each raw tree independently)
  reports `all_dispatch_match: true` for both runs: **every one of the 10
  successfully-dispatched cases' `out_hex`/`outb_hex`/`outsel_hex` matches
  its case-specific expected value EXACTLY, byte for byte** (see per-case
  detail below). `analysis/analysis_run01.json` and
  `analysis/analysis_run02.json` are the full derived reports; identical to
  each other apart from the `run_dir` field.
- Cases 8/9 (`mem22_direct_cap_31`, `mem22_direct_cap_32`): both
  `compile_reject`, both with the **identical** compiler diagnostic:
  `program_source:109:37: error: 'buffer' attribute parameter is out of
  bounds: must be between 0 and 30\n    const device uint* b31
  [[buffer(31)]]`. This diagnostic is a property of `cap32`'s declaration
  (buffer index 31) — see "Limitation" below for why case 8 (`cap31`, which
  declares only indices 0..30) is **confounded** and cannot independently
  confirm compiling cleanly on its own in this experiment.
- Cases 12/13 (`decode_dynamic_addressing_mechanism`,
  `splice_swap_indirect_pointer`): both `identification_failed`. The
  decode found exactly 2 `device_load` instructions in `splice_target`'s
  main region (`n_device_load_main=2`, `n_device_load_preamble=0`,
  `main_leftover_len=0` — a clean, complete tokenization), consistent with
  H7's structural prediction, but the pre-registered refuter fired:
  `l1.index_reg == l2.index_reg == 1` (both `1`), so
  `confirmation_ok=False` per the frozen identification algorithm. **Both
  loads instead differ in `base_slot`: `l1.base_slot=3`,
  `l2.base_slot=4`.** The splice case correctly stopped before attempting
  any splice (`target=null`, `splice_offset_abs=null`) — the pre-registered
  hedge for exactly this outcome.

## INTERPRETED

### MEM-20 — can Apple9 load/store through a dynamically obtained 64-bit
device address, without a statically encoded base slot?

**Answer: Yes**, established at HW-PROBE + OWN-SHADER strength by four
independent constructions, all executed and byte-exact on the real M4:

1. **`mem20_uniform_single`** — a plain `device ulong*` buffer holding one
   runtime-obtained `MTLBuffer.gpuAddress` value, cast to `device T*` and
   dereferenced (`kernels/probes.metal:mem21_uniform`). Every one of 32
   lanes read the correct tag word through the address (`out_hex` = 32×
   `TAG(0)=0x5A000000`).
2. **`mem20_implicit_ab`** — Metal's public implicit-argument-buffer
   feature (`struct ArgBuf { device uint *ptr; }`, populated via
   `MTLArgumentEncoder`, never via `setBuffer:offset:atIndex:` on the
   pointee). `out_hex[i] == TAG(0x300000+i)` for all 32 lanes.
3. **`mem20_chained_indirection`** — double indirection: a dynamic address
   pointing to a buffer whose own element 0 holds a SECOND dynamic address.
   `out_hex[i] == TAG(0x700000+i)` for all 32 lanes — the mechanism
   composes.
4. **`mem20_no_useresource`** — the same construction as (1) but the
   compute encoder never calls `useResource:` on the indirectly-referenced
   buffer (an adversarial/no-prediction probe, H4). Result: identical
   correct output to (1) — on this M4/macOS 26.6.2 configuration, for a
   plain compute dispatch against a buffer allocated for the lifetime of
   the dispatch, explicit residency declaration was **not** load-bearing
   for correctness. This is a narrow, single-configuration observation
   (one buffer, one dispatch, `MTLResourceStorageModeShared`), **not** a
   general robustness claim — Apple's public documentation still specifies
   `useResource:` as required for indirectly-referenced resources, and a
   Vulkan-compiler fallback should not rely on its absence.

**The complete executable sequence (compiler-emitted, this configuration):**
an ordinary `device ulong*` (or implicit-AB-pointer-member) buffer is bound
via a normal static base slot; its runtime CONTENTS — an 8-byte value
supplied by our own CPU-side harness from a public `MTLBuffer.gpuAddress`
call, never known at compile time — are loaded, cast to a `device T*`, and
dereferenced by an ordinary pointer-typed access in the SAME kernel. No
special MSL syntax, pragma, or capability flag is required; standard C-style
pointer casts within a kernel body compile and execute correctly.

**Mechanism (decode, H7, REFUTED AS ORIGINALLY STATED — see below) plus a
supplementary HW-VALIDATED finding (see "Supplementary exploratory
finding"):** the pre-registered hypothesis that the two per-lane
dereferences' `index_reg` fields would differ (carrying the dynamic address
identity) was **refuted**: both loads share `index_reg=1` (consistent with
both being indexed by the same per-lane `gid`, which is what `index_reg`
is documented to hold — `tools/agx-isa/db.json`, "the GPR holding the array
INDEX", not the address itself). Instead, **`base_slot` differs (3 vs 4)
between the two loads** — a compiler-generated form in which each
dynamically-loaded pointer is assigned its own `base_slot` table entry
(consistent with `MEM-18`'s open "intermediate base-register/preload file"
alternative), populated by preamble instructions this experiment's ISA DB
does not yet decode (`preamble_leftover_len=54` of 64 bytes — an DB
coverage gap, not a correctness question). A follow-up manual exploration
(outside this experiment's frozen two-run gate; see below) **confirmed at
HW-VALIDATED strength** that this `base_slot` field is what causally
selects which dynamically-loaded pointer a `device_load` dereferences: a
single hand-spliced byte flip (`base_slot` 3→4) redirected the exact same
compiled instruction from one dynamically-loaded buffer to the other, on
real hardware, exactly as predicted.

### MEM-21 — can a non-uniform, per-lane index select DIFFERENT buffer base
addresses for different lanes in one SIMD group, distinguished from a
uniform whole-dispatch selection?

**Answer: Yes**, with the divergent and uniform cases directly contrasted:

- **`mem21_uniform_ctrl`** (negative control: `sel_u` is a scalar `constant
  uint&` argument, identical for every lane by construction) — **all 32
  lanes read the SAME buffer** (`out_hex` = 32× `TAG(1)`). Zero divergence,
  as required of a true uniform-program selection.
- **`mem21_perlane_divergent_32`** (positive: `sel = gid % 32`, computed
  ONLY from `thread_position_in_grid`, never read back from a per-lane data
  buffer) — **every one of the 32 lanes in one SIMD group (M4 SIMD width
  32) read a genuinely DIFFERENT buffer**: `out_hex[gid] == TAG(gid)` for
  all 32 lanes — 32 distinct values, not one value broadcast. `outsel_hex`
  independently confirms each lane computed its own distinct `sel=gid`.
- **`mem21_outlier_lane17`** (fine-grained control: `sel = (gid==17) ? 1 :
  0`) — lane 17 alone read `TAG(1)`; every other lane read `TAG(0)`. This
  refutes a "coarse broadcast-group" alternative explanation for the
  perlane result (i.e. rules out a hardware/driver mechanism that only
  supports a small number of distinct address groups rather than genuine
  per-lane selection): a SINGLE lane's selection, surrounded by 31 lanes
  making the opposite choice, still resolved correctly.

**How per-lane divergence was proven, not merely asserted:** the selector
is computed exclusively from `thread_position_in_grid` inside the kernel
(never read from a data buffer, so it cannot be confused with ordinary
per-element addressing within one buffer); the DIVERGENT case's 32 output
words are 32 DISTINCT values (`TAG(0)..TAG(31)`), directly falsifiable
against a broadcast (which would show one repeated value, exactly what the
UNIFORM control case does show); and the OUTLIER case isolates a single
lane's divergence against a uniform background, ruling out coarse grouping.
All three cases compile from and dereference the SAME `device ulong*`
address-array construction validated for MEM-20 — per-lane base-address
divergence and the MEM-20 dynamic-dereference mechanism are the same
hardware capability exercised with a thread-varying vs. uniform selector,
not two different mechanisms.

**Architectural note (from the `device_load` ISA descriptor, already
HW-VALIDATED prior to this experiment, `tools/agx-isa/db.json`):** the
STATIC direct-slot mechanism's `base_slot` field is an 8-bit IMMEDIATE,
fixed at compile time and therefore identical for every lane by
construction — it is architecturally INCAPABLE of expressing per-lane
divergence on its own. `index_reg`, by contrast, is a per-lane GPR-select
field. This experiment's dispatch-level results (above) establish that
genuine per-lane base-address divergence IS achievable; the supplementary
finding below narrows the mechanism further (a per-lane-computed VALUE
selects among MULTIPLE dynamically-populated `base_slot` table entries,
rather than one `base_slot` table entry containing a per-lane-varying
address).

### MEM-22 — when given more live buffer resources than the direct-slot
path holds, does the toolchain reject, use a descriptor-table/dynamic-
address path, or split/preload?

**Answer: the toolchain does BOTH — it rejects at the DIRECT-binding
compiler boundary, and offers (and this experiment separately, independently
hardware-validates) a working dynamic-address fallback beyond that
boundary:**

- **Direct-slot boundary (`mem22_direct_cap_32`, compiler-output
  observation):** declaring a 32nd direct `[[buffer(31)]]` argument is
  **rejected at MSL compile time** with an explicit diagnostic: `'buffer'
  attribute parameter is out of bounds: must be between 0 and 30`. This is
  a hard, unambiguous, toolchain-enforced ceiling of **31 simultaneously
  DIRECT-bound buffer arguments** (indices 0..30) for a compute kernel on
  this device/OS/Metal-version combination — a compiler-level fact,
  reproduced identically across both runs.
- **Dynamic-address fallback, independently hardware-validated
  (`mem22_dynamic_64`, `mem22_dynamic_256`):** reusing the EXACT SAME
  MEM-20/21 dynamic-dereference mechanism (a `device ulong*` array of
  runtime-obtained addresses, `sel=gid`) with **64** and **256** distinct
  backing buffers — 2× and 8× past the 31-argument direct ceiling — both
  compiled, dispatched without a command-buffer error, and every one of 64
  (respectively 256) lanes read its own distinct buffer's tag word
  correctly (`out_hex[gid] == TAG(gid)` for every gid, both sizes). This is
  real, independent HW EXECUTION validation of the fallback, not merely a
  compiler-output observation: the toolchain does not merely "offer" a
  dynamic-address path syntactically, that path actually WORKS, correctly,
  at a resource count the direct path provably cannot reach.
- The evidence-level separation the task asked for: **"reject" is a
  compiler-output observation** (case 9's diagnostic); **"dynamic-address
  path works"** is **independent hardware execution evidence** (cases
  10/11's byte-exact dispatch results) — these are two different rows of
  evidence in `04_results.jsonl`/`analysis.json`, not one conflated claim.
  This experiment found **no evidence of a "split/preload" strategy**
  (e.g. the compiler silently batching resources across multiple dispatches
  or draws) — that alternative was not observed because it was never
  triggered: the direct path simply refuses to compile past 31, and the
  dynamic-address path was reached by AUTHORING it directly (not by asking
  the compiler to lower an over-large direct-binding request into
  something else). Whether Apple's OWN toolchain (e.g. a Metal argument
  buffer generated from a very large `[[buffer]]`-indexed resource array
  in real application code) picks the dynamic-address path automatically,
  as opposed to us authoring it explicitly, is **not established** by this
  experiment and remains open for a future probe if it becomes load-bearing
  for the Vulkan compiler's resource-array lowering strategy.

**Limitation on `mem22_direct_cap_31`:** `cap31` and `cap32` are two
functions in the SAME MSL translation unit (`kernels/cap_kernels.metal`,
compiled as one file by `newLibraryWithSource:`); a compile error anywhere
in the file (here, `cap32`'s out-of-range index) fails the WHOLE library,
so `cap31` is reported `compile_reject` too even though its OWN 31-argument
declaration (indices 0..30) is not implicated by the diagnostic (which
names `b31 [[buffer(31)]]`, a symbol that exists only in `cap32`). This
experiment therefore does **not** independently confirm that 31 direct
buffer arguments alone compile and dispatch cleanly on this M4/toolchain —
that specific sub-claim is a **design defect discovered mid-capture** (a
shared-translation-unit confound), not a hardware finding, and is flagged
here rather than silently corrected (per `CODEX.md` — the frozen source is
part of both captured runs' provenance and was not edited after run01).
The MEM-22 boundary VALUE itself (31) is still established unambiguously
by the compiler's own diagnostic text (which states the bound directly,
independent of `cap31`'s presence in the file); a future probe splitting
`cap31`/`cap32` into separate translation units would close this narrow
gap. It does not affect MEM-20/21's conclusions, nor MEM-22's fallback-path
conclusion (cases 10/11), which do not depend on `cap31`.

## Supplementary exploratory finding (NOT part of the frozen two-run
gated evidence — read this section's evidentiary weight carefully)

After both contracted runs closed and `verify.py --captured` passed, the
H7 refutation (`base_slot` differs, not `index_reg`) was investigated
further with a **manual, single-run, ungated exploration** (not run through
`run.py`/`verify.py`, no `raw/` append-only record, no cross-run
reproducibility check — commands and raw bytes preserved in
`analysis/supplementary/README.json` and
`analysis/supplementary/splice_target_main.hex` for audit, but this is
process history / a documented hypothesis for a successor, not promoted
evidence at the same standing as the frozen matrix above):

1. Rebuilt `tools/shdump/shdump.m` and `harness/splice_run.m` into a
   scratch directory (no edits to either file).
2. Compiled `splice_target` with `shdump --no-fast-math` (the identity-
   library recompile inside `splice_run.m` uses `fastMathEnabled=NO`;
   plain `shdump` — as `analysis/decode_lib.py`'s `build_archive()` also
   calls it — defaults to `fastMathEnabled=YES`, an AIR-hash mismatch that
   caused the FROZEN `splice_case.py` path to be unable to reach a baseline
   run even had `confirmation_ok` been true; this is a **second latent bug**
   in the frozen splice harness, found only by this manual exploration,
   flagged for a successor and NOT corrected in this already-captured
   experiment).
3. Confirmed byte-for-byte the SAME `_agc.main` bytes as the frozen decode
   case (`l1` at instruction offset 4, `base_slot=3`; `l2` at offset 18,
   `base_slot=4`) — reproducible given fixed source.
4. Ran the UNMODIFIED archive: `out_hex` = 32× `0x5a0000aa` (`TAG_A`,
   fed by `l1`), `outb_hex` = 32× `0x5a0000bb` (`TAG_B`, fed by `l2`).
5. Spliced EXACTLY ONE byte: `l1`'s `base_slot` field (absolute file offset
   7560, `device_load` bits [32:40]) from `0x03` to `0x04` (`l2`'s value).
6. Ran the SPLICED archive: `out_hex` flipped to 32× `0x5a0000bb`
   (`TAG_B`) — `l1` now dereferences the buffer `l2` was dereferencing —
   while `outb_hex` remained 32× `0x5a0000bb`, byte-identical to the
   baseline (the untouched load `l2` unaffected).

**This is the exact predicted outcome of the revised hypothesis** ("
`base_slot`, not `index_reg`, causally selects which dynamically-loaded
pointer a `device_load` dereferences") **and constitutes a real,
independently-synthesized-encoding, hardware-executed splice confirmation
— the strongest evidence tier (`HW-VALIDATED`) — for that revised
mechanism, on this one compiled binary, in this one manual observation.**
It is reported here in full, with commands and byte offsets, precisely
because CODEX requires negative/corrective results to be recorded
honestly rather than dropped, and because omitting a finding this directly
load-bearing for MEM-20's "complete executable sequence" would be less
useful than reporting it with an explicit, honest evidentiary caveat. It
is **not** promoted to the same standing as the frozen matrix (no second
run, no `verify.py` gate, no append-only raw capture) — a successor
experiment (new `EXP-NNNN`, fresh pre-registration) should formalize this
exact splice as its own H1/refuter pair, fix the two bugs identified above
(the `index_reg`→`base_slot` field correction and the `--no-fast-math`
archive/identity-compile mismatch), and re-run it under the full standing
gate set.

## Compiler-emitted vs. hardware-validated evidence — explicit separation

Per the dispatch instructions, these are kept as clearly distinct rows:

| Claim | Evidence level | Source |
|---|---|---|
| MEM-20 core capability exists (dynamic dereference works) | **HW-PROBE + OWN-SHADER** (real GPU dispatch, byte-exact readback, TWO independently reproduced runs) | cases 0-4 |
| MEM-20 mechanism = `index_reg` carries the address | **REFUTED** (decode, both runs identical) | cases 12/13 |
| MEM-20 mechanism = `base_slot` differs per dynamic pointer | **STRUCTURAL** (decode, both runs identical) escalated to **HW-VALIDATED** for one compiled binary by the supplementary splice (NOT part of the frozen two-run gate) | case 12 + supplementary |
| MEM-21 per-lane divergence exists and is distinguishable from uniform selection | **HW-PROBE + OWN-SHADER** (real GPU dispatch, three contrasted cases, TWO reproduced runs) | cases 5-7 |
| MEM-22 direct-slot compiler ceiling = 31 | **compiler-output observation** (TWO reproduced runs, identical diagnostic) | case 9 |
| MEM-22 dynamic-address fallback executes correctly past that ceiling | **HW-PROBE + OWN-SHADER** (real GPU dispatch at N=64,256, byte-exact readback, TWO reproduced runs) | cases 10-11 |

## Exact tested range

`n` (address-array size): 1, 2, 30, 31, 32, 64, 256. Grid/lane count: 1
(cap kernels), 32 (all others), 64, 256 — i.e. every dispatched case uses
exactly one thread per dereferenced address (`grid == n` for the
divergent/dynamic-count cases), except the fixed-32-lane control/outlier/
implicit-AB/chained cases. Selector patterns: constant `0`, constant `1`,
`gid % N` (N=32/64/256), `(gid==K)?1:0` (K=17). `useResource`: called (11
cases) or deliberately omitted (1 case, `mem20_no_useresource`). All on the
local **Apple M4 (G16G)**, compute stage, `fastMathEnabled=NO`,
`mathMode=Safe`, macOS 26.6.2 (25G82), git revision recorded in
`raw/*/00_inputs.json`.

## What remains UNKNOWN / explicit safe driver fallback

- The exact preamble instruction(s) that populate the dynamically-computed
  `base_slot` table entries are **not decoded** (54 of 64 preamble bytes
  are outside this repository's current `tools/agx-isa` DB coverage) — a
  DB-coverage gap, not a behavioral unknown; MEM-20/21/22's dispatch-level
  answers do not depend on it.
- Whether `base_slot`'s table supports MORE than the two entries exercised
  here, its total capacity, and its relationship to the direct-binding
  `base_slot` values (MEM-15/16/17/18/19) are **not established** — a
  DIFFERENT, adjacent, still-open questionnaire item.
- `mem22_direct_cap_31`'s standalone-compile claim is confounded (see
  above); the compiler-enforced 31-argument ceiling itself is still solid.
- No A18 Pro (G17P) claim; scope is the local M4 (G16G) only, per current
  target discipline. No claim about any other Metal/OS toolchain version.
- **Safe driver fallback if this result needs re-validation on another
  toolchain/target:** a Vulkan-grade compiler targeting Apple9 can assume
  (pending re-validation per target, per `CODEX.md` target discipline) that
  (1) bindless/bounded-array descriptor access compiles to an ordinary
  pointer dereference through a runtime-loaded 64-bit value — no special
  ISA support is required beyond what any `device T*` load already uses;
  (2) per-lane-divergent resource selection is free once (1) holds, because
  the selecting computation is ordinary per-lane arithmetic; (3) resource
  counts beyond the 31-argument direct-binding ceiling MUST use the
  dynamic-address (argument-buffer-style) path — there is no compiler-
  level "split into multiple direct-bound dispatches" alternative observed.

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: kernels/probes.metal, kernels/cap_kernels.metal (+ its
  generator), harness/probe.m, harness/splice_run.m, casematrix.py,
  procutil.py, run.py, verify.py, analysis/decode_lib.py,
  analysis/decode_case.py, analysis/splice_case.py, analysis.py (all
  authored by us); tools/shdump/shdump.m, tools/shdump/agxparse.py,
  tools/agx-isa/isadb.py + db.json, tools/agxtest/README.md (read-only,
  our own prior clean-room tooling, invoked/imported, never edited)
Apple binary introspection: NONE
Reproduction: see README.md's command sequence; both raw runs and
  analysis/analysis_run0{1,2}.json reproduce from `raw/*` alone
Evidence: raw/m4-20260827-run01, raw/m4-20260827-run02,
  analysis/analysis_run01.json, analysis/analysis_run02.json,
  analysis/supplementary/ (exploratory, see caveats above), manifest.json
```
