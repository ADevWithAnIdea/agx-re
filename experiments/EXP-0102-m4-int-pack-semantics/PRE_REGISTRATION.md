# PRE_REGISTRATION — EXP-0102 M4 INT-*/PACK-* semantics (compiler-contract questionnaire)

**Pinned repository revision (per SUBAGENT_BRIEF.md — record and compare
against THIS value, never live `HEAD`):** `0f1af7fa1d3e21a9996c3b49d7d91f6377427225`
(tree dirty at pin time with unrelated sibling-experiment untracked artifacts
— expected per SUBAGENT_BRIEF.md, not a contamination signal. `HEAD` may move
further during capture as the orchestrator commits sibling experiments; this
experiment's validity depends on the AUTHORED BLOB HASHES below, not on
`HEAD` staying still.)

Target: **local Apple M4 / G16G only** (10 GPU cores, macOS 26.6.2 build
25G82, Metal 4). A18 Pro is hands-off (standing directive); no M5 evidence
used anywhere. All claims below are M4-only unless explicitly marked
`INFERRED`-by-family.

## 0. Origin and status of this document

This contract is written **after** a disclosed pilot phase (`PROGRESS.md`),
matching the precedent set by EXP-0086/0089/0090/0099. The pilot phase:

1. Built the full 51-kernel/51-case harness (`kernels/gen_kernels.py`,
   `analysis/casematrix.py`, `harness/case_exec.py`) and confirmed every
   kernel/function compiles on this M4 (`kernels/*.metal`, one process per
   compile probe, logged in `PROGRESS.md`).
2. Ran every case once, informally, against a **first-draft** oracle. Two
   genuine oracle bugs were found and fixed BEFORE any gated capture: (a) a
   tuple-vs-list and NaN-vs-NaN equality bug in the comparator
   (`harness/case_exec.py::_eq`), and (b) an `--out` word-count unit bug for
   multi-word element kinds (`f32x2`/`f32x4`/`u64`) that produced truncated
   readbacks (`harness/case_exec.py::WORDS_PER_ELEM`). Both are host-side
   harness bugs, not hardware findings; fixed before freezing.
3. That same first pilot run surfaced a real, reproducible, then-unmodeled
   **hardware** boundary behavior for `extract_bits`/`insert_bits` at
   `cnt==32` (offset is bypassed entirely — see INT-01/02/03/11 below). A
   **second** pilot dry run, with `cnt` values `{33, 40}` added specifically
   to disambiguate "cnt==32 exactly" from "cnt>=32 generally", showed the
   bypass is exact-`cnt==32` only; `cnt>32` reverts to ordinary
   clamped-width, literal-offset shifting. This refined "MODEL D" is the
   model frozen into `analysis/oracle.py` below and is what the gated
   capture tests — it is a hypothesis to be **reconfirmed** by the frozen
   two-run capture, not treated as already proven by the pilot.
4. A third pilot finding: a directed "exact tie" fraction constructed as
   `(N+0.5)/65535` in float64 does **not** reliably survive float64→float32
   truncation as an exact half-integer once multiplied back by 65535 — the
   TRUE (exact-rational) product is off by ~1e-9, which had produced 2
   spurious "mismatches" against a naive float64 oracle for
   `pack_float_to_unorm2x16`. Fixed by computing the pack oracle over the
   **exact `Fraction`** value of the float32-snapped input
   (`oracle.py::f32_exact_fraction`, `_pack_norm_exact`), which resolved
   all 10/10 rows including the one genuine exact tie (`N=32767`, which
   IS exactly representable) rounding to its even neighbor. This is now a
   real, disclosed methodology point, not a hidden fix: **any tie/boundary
   claim in this family must be checked against the exact float32 value,
   not a float64 approximation of it.**
5. No case's kernel source, buffer bytes, or oracle formula was adjusted
   after seeing a specific case's individual GPU result to make that SAME
   case pass — the two oracle refinements above (MODEL D, exact-fraction
   packing) are general models applied uniformly across every row of their
   respective cases, derived from the FULL first-pilot dataset, then
   verified to fit every row before being frozen here. This mirrors
   EXP-0099 §0's disclosed-pilot precedent.

## 1. Item-by-item coverage (exact wording from `APPLE9_RE_IMPLEMENTATION_GAPS.md`)

All 14 `INT-*` and all 11 `PACK-*` items are addressed below. Every item is
either **COVERED** (a case in `analysis/casematrix.py` answers it, on this
gated capture) or **PARTIAL/DEFERRED** (explicitly marked, with the reason
and a recommended follow-up). None are silently dropped.

### INT-01 — "Does native unsigned bitfield extract return zero when the requested width is zero?"
**COVERED.** Case `int0102_extract_unsigned` (`k_int_extract.metal::extru`),
the `cnt==0` rows (24 of 122). Runtime-supplied `off`/`cnt` (buffer-fed, not
compile-time constants) so the hardware/codegen path is genuinely exercised.
Oracle: `oracle.ubfe_model_d_width32_bypasses_offset` returns 0 for `cnt==0`.

### INT-02 — "Does native unsigned bitfield extract match NIR for offsets and widths at and beyond the 32-bit boundary after applying NIR's required masking/clamping?"
**COVERED, with a hardware-model correction.** Same case, the off/cnt
boundary rows (off ∈ {0,1,16,28,31,32,33,40,63,64,1000,2^32-1}, cnt ∈
{1,8,31,32,33,40}, plus a cnt-only sweep at off=0 over {0..2^32-1}
boundaries). Pilot finding (frozen as MODEL D, to be reconfirmed): the
hardware does **not** implement NIR's presumed "mask offset mod 32, clamp
width to 32" contract. Instead: `cnt==0`→0; `cnt==32` **exactly**→result is
the input verbatim, offset ignored entirely (even off=2^32-1); otherwise
offset is applied as a **literal, unmasked** shift (`off>=32`→0), width
clamped to 32. This is three-way disjoint from both competing models
originally recorded (`model_a_masked_shift`, `model_b_unmasked_offset`),
both kept in the record as refuted alternatives.

### INT-03 — "Is signed bitfield extract always native unsigned extract followed by an explicit sign extension, with no hidden signed mode?"
**COVERED.** Case `int03_extract_signed` (`extrs`), same (a,off,cnt) rows
reinterpreted `int`. Oracle = MODEL D's unsigned result, sign-extended over
`min(cnt,32)` bits. A hidden signed mode would show as a MODEL-D-oracle
mismatch that a plain sign-extend cannot explain; a match across all 122
boundary rows (pilot: 122/122) is the falsifier-passing outcome.

### INT-04 — "Does immediate rotate implement every amount modulo 32, including 0, 31, 32, and values greater than 32?"
**COVERED.** Seven single-immediate kernels (`k_int_rotate_imm{0,1,31,32,33,63,64}.metal`),
each a **compile-time-constant** rotate amount (this item is specifically
about the immediate-operand path, unlike INT-05). Oracle: `rotl32(a,K)`
(mod-32 funnel). Structural cross-check (no extra hardware contact —
reuses the `--dump-main` bytes already captured for these cases):
`imm0`/`imm32`/`imm64` (all ≡0 mod 32) are predicted, and pilot-confirmed,
to compile to **byte-identical**, rotate-free code (the compiler folds the
identity rotate away at AIR compile time); `imm31`/`imm63` (both ≡31 mod 32)
are predicted/pilot-confirmed byte-identical to each other with a real
funnel op present; `imm33` (≡1 mod 32) is predicted to encode the same
shift-immediate field value as a would-be `imm1` — `imm1` was added
specifically to make this a same-value comparison rather than an inference.

### INT-05 — "Does the dynamic rotate expansion implement the same modulo-32 semantics for all runtime amounts?"
**COVERED.** Case `int0506_rotate_var` (`k_int_rotate_var.metal`), runtime
`n` (buffer-fed) swept over `{0,1,16,31,32,33,63,64,65,127,128,255,256,1000,
2^32-1,2^31}` × 4 base values = 64 rows. Explicitly a representative
boundary/multi-point sweep of the 32-bit amount domain, not exhaustive
(named per CODEX §3/§7 as the tested range).

### INT-06 — "Is there no one-instruction dynamic rotate form?"
**COVERED, structurally.** Answered from the SAME `--dump-main` bytes
captured for INT-04/INT-05 (`analysis/structural.py`, no extra hardware
contact): the runtime-amount kernel's `_agc.main` length vs. the
immediate-amount kernels'. Pilot: immediate rotate (non-degenerate case) is
a single 12-byte funnel op embedded in a 48-byte `_agc.main`; the
runtime-amount kernel is 98 bytes — consistent with EXP-0033's A18 finding
of a multi-instruction (shift-prep + two funnel/extract ops + subtract + OR)
expansion, now independently re-confirmed on M4.

### INT-07 — "Does native 32-bit IMAD wrap modulo 2^32 exactly like NIR integer multiply-add?"
**COVERED.** Cases `int0708_imad_wrap_u`/`_s` (`k_int_imad.metal`), boundary
triples chosen to force wraparound in both unsigned and signed
interpretations (e.g. `0xFFFFFFFF*2+1`, `INT32_MIN*-1+0`).

### INT-08 — "Can all three IMAD sources be arbitrary GPRs over the complete usable 96-register range?"
**PARTIAL/BEST-EFFORT, explicitly scoped down.** Case
`int08_imad_register_pressure` (`k_int_imad_pressure.metal`) forces 40 live
temporaries ahead of the final `a*b+c` to push the register allocator past
the low registers the other kernels naturally use, and reports (via
`--dump-main`) what register field values the compiled IMAD actually uses —
this is evidence about what the *compiler* reaches under pressure, not an
independently-assembled proof that IMAD's encoding *itself* can address the
full 0–95 range. A genuine independent-assembly proof requires solving the
still-open register ≥64 addressing blocker documented in
`docs/isa/register-move-and-liveness.md` §2.7/EXP-0099 ("Registers 64–95 are
UNKNOWN again... no validated addressing path for them") for the specific
`imad`/`0x9f` 12-byte family (a **different** family than the `falu2` one
that blocker was characterized on) — solving that blocker is out of this
experiment's time budget and is a named follow-up, not silently dropped.

### INT-09 — "Does the native find-MSB primitive return the highest set-bit index, with 0x80000000 -> 31, 1 -> 0, and zero handled as required by NIR ufind_msb?"
**COVERED by derivation + structural re-confirmation, not direct primitive
isolation.** Case `int0910_clz` (`k_int_clz.metal::clzu`), a boundary sweep
of `clz`. find-MSB itself is **derived** as `31 - clz(x)` for `x != 0` under
the byte-level decomposition EXP-0033 established on A18 (find-MSB op →
subtract-from-31 → zero-clamp) — this experiment re-examines that
decomposition's byte signature on the FRESH M4-compiled `clz` kernel
(`analysis/structural.py`) rather than re-asserting the A18 result
unchecked. Direct hardware isolation of the find-MSB primitive alone (via
splice, truncating the subtract/clamp trailer) was scoped OUT of this
experiment for time; see §3 Deferred below. Evidence tier:
`OWN-SHADER-DIFF`/`INFERRED` for the primitive's own semantics, layered on
top of an `HW-VALIDATED`-tier fresh M4 `clz` boundary sweep.

### INT-10 — "Is CLZ necessarily a compound sequence rather than a separate single instruction?"
**COVERED, structurally.** Same `clz` case, byte-length/opcode-family
compared against `int0910_popcount_baseline` (`popc`, EXP-0033's confirmed
single 8-byte op in the same `0x27`/`0xa7` family) via
`analysis/structural.py`. A materially longer `_agc.main` with more than one
non-trivial op in that family, for every tested `clz` input, structurally
answers "compound, not single-instruction" without needing a splice.

### INT-11 — "Is bitfield insert necessarily a mask/shift/combine sequence rather than a separate single instruction?"
**COVERED.** Case `int11_insert_bits` (`k_int_insert.metal::ins`), a 256-row
boundary sweep (base/val ∈ 4 patterns × off ∈ {0,4,16,28,31,32,33,63} × cnt
∈ {0,1,4,8,16,31,32,33}), functional correctness against the SAME MODEL-D
pattern discovered for extract (`cnt==0`→no-op, `cnt==32`→`val` verbatim
offset-ignored, else literal-offset mask/shift/clear/combine — pilot:
256/256 fit) plus a structural instruction-count check (no single-op
alternative observed in any tested row).

### INT-12 — "Can the full integer logic-LUT encoding realize all 16 two-input Boolean functions for arbitrary GPR operands?"
**COVERED.** 16 cases (`int12_logic00`..`int12_logic15`,
`k_int_logic16.metal::k0`..`k15`), one per canonical 2-input Boolean
function (AND, NAND, OR, NOR, XOR, XNOR, both projections and their
complements, both "or-not" combinations, and the two degenerate constants
0/all-ones), each with runtime `a`/`b` operands. Functional correctness
against `oracle.logic_lut`, plus a structural cross-diff
(`analysis/structural.py`) of all 16 compiled bodies to determine whether
they share one opcode family with a single varying LUT-select field, or
fall into disjoint op families (e.g. the two degenerate constants folding
away entirely, or projections compiling to plain register moves rather than
a logic op).

### INT-13 — "Does the carry-generate operation require a particular immediately preceding add or implicit machine state?"
**COVERED, structurally, on the compiler-emitted evidence.** Cases
`int1314_u64add` and `int13_u64add_expr` (`k_int_u64carry.metal`), two
different expression shapes (a plain `a+b` and an `(a+b)+c` sum embedded in
a larger expression). `analysis/structural.py` re-confirms, on M4,
EXP-0038's A18 finding that the `0x32` carry-generate op's position is
locked to immediately follow the specific low-word add whose overflow it
tests, in both shapes. This is compiler-emitted-instance evidence
(`OWN-SHADER-DIFF`), not an independent-construction proof that the
hardware *itself* mandates the adjacency (that would require splicing the
carry-gen op away from any add and observing a fault/incorrect-result vs. a
correct one from unrelated sources — scoped to INT-14, see below).

### INT-14 — "Can carry-generate be emitted as a self-contained operation with explicit source operands?"
**PARTIAL/DEFERRED.** Independently re-sourcing the `0x32` carry-generate
op's operands via splice (pointing it at two registers seeded by unrelated,
independent computations rather than a real preceding add) was scoped out
of this experiment's time budget given the standing project-wide warning
(`docs/isa/register-move-and-liveness.md`) that a wrong operand-field value
on this hardware silently zeroes rather than faults, and that this specific
op's register-field layout has not been independently characterized (only
its position and byte length are established, per EXP-0038). Attempting a
guessed splice here risks producing a false "it works standalone" or false
"it requires the preceding add" result from a misread operand field rather
than a genuine hardware fact. Recommended follow-up: a dedicated successor
experiment that first characterizes `0x32`'s operand-register field bit
layout (structural byte-diff across several u64-add contexts with different
GPR allocations) before attempting an independent-source splice.

### PACK-01 — "Is pack_half_2x16 implementable by a fully decoded Apple9 native conversion/pack sequence without generic integer bitfield lowering?"
**COVERED.** Case `pack0102_pack_half2x16` (`k_pack_half2x16.metal::packh`,
`float2→half2→as_type<uint>`, MSL's exact native equivalent of GLSL
`packHalf2x16`), 7 boundary pairs including the fp16 max/min-normal and an
overflow-to-±inf pair. Functional correctness against
`oracle.pack_half_2x16` (exact via `f16_encode_exact`, Fraction-based).
Structural: `analysis/structural.py` byte-diffs the compiled body against
EXP-0033/0038's confirmed `insert_bits` mask/shift/combine signature
(`0x0b`/`0x2b`/`0x9f`) and the confirmed native half-convert/pack signature
(`0x11` narrow-convert → `0x18` pack) to determine which family this
compiles to.

### PACK-02 — "Is unpack_half_2x16 implementable by a fully decoded Apple9 native unpack/conversion sequence?"
**COVERED.** Case `pack0102_unpack_half2x16` (`unpackh`), 10 rows including
NaN(0x7E00)/Inf(0x7C00) lane patterns (pilot: 10/10 exact, including NaN
lanes via NaN-aware comparison). Structural byte-diff as PACK-01.

### PACK-03 — "Is pack_snorm_2x16 a member of the native 0x97 pack-convert family?"
**COVERED.** Case `pack0304_pack_snorm2x16` (`packsn`), functional
correctness (pilot: 7/7 exact against the exact-fraction oracle) +
structural byte-diff against `packun`'s confirmed single-`0x97`-op EXP-0033
signature.

### PACK-04 — "Is unpack_snorm_2x16 a member of the native 0x17 unpack-convert family for all input bit patterns?"
**COVERED, EXHAUSTIVELY.** Case `pack0304_unpack_snorm2x16_exhaustive`
(`k_pack_unpack_exhaustive.metal::unpacksn_exh`), grid=65536, one dispatch —
every one of the 65536 possible 16-bit lane bit patterns exercised exactly
once (`gid | (gid<<16)`, low lane read back). Pilot: 65536/65536 bit-exact
against `oracle.unpack_snorm16`. Structural byte-diff against `unpackun`'s
confirmed single-`0x17`-op signature.

### PACK-05 — "Does native pack_unorm_2x16 match NIR rounding, clamping, NaN, and infinity semantics for all boundary cases?"
**COVERED.** Case `pack0506_pack_unorm2x16_edge` (`packun`), 10 directed
rows: negative, >1, both-NaN-lane combinations, ±Inf, subnormal-magnitude,
and three genuine exact-tie fractions in the ×65535 domain (constructed and
verified via EXACT `Fraction` arithmetic on the float32-snapped input, per
§0.4 — a naive float64 "tie" construction does not reliably survive
round-trip and was caught and fixed during the pilot). Pilot: 10/10,
including round-to-nearest-**even** at the one true tie (N=32767).

### PACK-06 — "Does native unpack_unorm_2x16 exactly match NIR for every 16-bit lane value?"
**COVERED, EXHAUSTIVELY.** Case `pack0506_unpack_unorm2x16_exhaustive`,
identical exhaustive-grid method to PACK-04. Pilot: 65536/65536 bit-exact.

### PACK-07 — "Does Apple9 have a native pack_32_4x8 or equivalent four-lane format-conversion operation?"
**COVERED.** Three cases: `pack0708_pack_unorm4x8`/`_snorm4x8`
(`k_pack_4x8_{unorm,snorm}.metal`, MSL's `pack_float_to_unorm4x8`/
`pack_float_to_snorm4x8` — both confirmed to COMPILE during the harness
smoke check, itself a small positive finding since these names were not
previously exercised in this repo's prior experiments) for the
NORMALIZED-format question, plus `pack07_pack4x8_manual_generic`
(`k_pack_4x8_manual.metal`, a hand-written non-normalized 4×8-bit integer
gather idiom) to separately probe whether a GENERIC (non-float-normalized)
4×8 pack has native support, via structural byte-diff against both the
builtin pack and the generic `insert_bits` signature.

### PACK-08 — "Does Apple9 have native UNORM and SNORM 4x8 unpack operations?"
**COVERED.** Cases `pack0708_unpack_unorm4x8`/`_snorm4x8`
(`unpack_unorm4x8_to_float`/`unpack_snorm4x8_to_float`, both confirmed to
compile), 8 rows each incl. round-tripped pack outputs and raw boundary
words, functional + structural single-op-length check.

### PACK-09 — "Does one FP16 vec2 add, multiply, or FMA instruction execute both packed lanes with independent lane-correct exceptional-value behavior?"
**COVERED.** Cases `pack0910_half2_{add,mul,fma}` (`k_pack_half2_alu.metal`),
8 rows each, per-lane EXCEPTIONAL pairs (NaN, ±0, ±Inf, subnormal, crossed
against ordinary values in the OTHER lane so cross-lane independence is
directly testable). Oracle: `oracle.f16_op`, a from-scratch correctly-
rounded binary16 reference built on exact `Fraction` arithmetic (genuinely
FUSED for the `fma3` case — a single rounding over the exact product+addend,
not a double-rounded `struct`-based approximation), cross-validated against
Python's own `struct` 'e' codec over 62000 values with 0 mismatches
(`PROGRESS.md`).

### PACK-10 — "Are packed FP16 lane results independent when one lane contains NaN, infinity, subnormal, or a signed zero?"
**COVERED** by the same three cases as PACK-09 (the matrix is designed
specifically to answer both items from one dataset — the "other lane"
column in each row is always an ordinary value, so an incorrect
cross-lane-corruption hardware bug would show as that lane's own mismatch).

### PACK-11 — "Is packed integer short2 ALU absent for every tested integer add/multiply/logic form?"
**COVERED.** Three cases `pack11_short2_{add,mul,and}`
(`k_pack_short2.metal`), extending EXP-0033's A18 finding (which tested only
`add`) to `mul` and a bitwise `and`, re-confirmed fresh on M4. Functional
correctness (scalar 16-bit wraparound model) + structural byte-diff to
confirm decomposition into two independent 32-bit ops for all three forms
(vs. the packed-2-lane `0x10` signature confirmed for `half2`).

## 2. Independent / controlled variables

- **Independent, per case:** the specific boundary/exceptional operand
  values enumerated in `analysis/casematrix.py` (offsets, widths, rotate
  amounts, IMAD triples, LUT function index, pack/unpack bit patterns,
  half2/short2 lane pairs).
- **Controlled/held fixed:** dispatch shape (`grid`×`tg` per case, all 1-D),
  `--no-fast-math` on every case, one kernel FUNCTION per case (no case
  mixes two operations), fresh subprocess per case (`case_exec.py` invoked
  once per case index, never reused).

## 3. Confounders (known, and how they are controlled)

- **Compile-time constant folding.** Any operand whose value could let the
  compiler statically resolve the interesting boundary is fed at
  **runtime** via a buffer, except INT-04 which is specifically ABOUT the
  compile-time-immediate path (and even there, the fold-away of `imm0`/
  `imm32`/`imm64` is treated as a *finding*, not a confound, since it
  directly answers "does immediate rotate implement modulo 32" at the
  value level).
- **float64-vs-float32 double rounding in the Python oracle.** Caught and
  fixed in the pilot (§0.4); every pack-to-integer oracle path now uses
  `oracle.f32_exact_fraction`/`Fraction` exact arithmetic on the actual
  float32-snapped input, not a float64 approximation.
- **NaN non-reflexivity (`nan != nan`).** Caught and fixed in the pilot
  (§0.1); `harness/case_exec.py::_eq` treats NaN==NaN as a match, since the
  question under test is "is this bit pattern a NaN", not numeric equality.
- **`--out` unit mismatch for multi-word element kinds.** Caught and fixed
  in the pilot (§0.1); `WORDS_PER_ELEM` scales the requested output buffer
  size correctly for `f32x2`/`f32x4`/`u64` kinds.
- **Register-file leftover state.** Not directly relevant to this
  experiment's cases (no case reads an intentionally-unwritten register),
  but every case's inputs are always explicitly buffer-supplied, never
  relying on an assumed-zero uninitialized register.
- **Kernel register pressure affecting splice reliability** (the dominant
  confounder in the EXP-0099/EXP-0090 family) does NOT apply here — this
  experiment does not splice hand-assembled bytes into a shared carrier;
  every case is a freshly, independently compiled kernel from its own MSL
  source, so this experiment carries none of that family's splice-fragility
  risk. (INT-14's deferral is precisely BECAUSE closing it properly would
  require entering that fragile splice regime without first doing the
  necessary field-characterization prep work — see INT-14 above.)

## 4. Standing gates (implemented in `verify.py` + `run.py`)

1. **`--selftest`** (`verify.py --selftest`): one authoritative, hand-worked
   vector list (`SELFTEST_VECTORS`), pure Python, zero GPU/tool dependency,
   runnable in any tree state (including before `harness/build.sh` has ever
   run). Also validates `analysis/casematrix.py` builds with no duplicate
   case ids and every oracle filled.
2. **`--seqtest`** (`verify.py --seqtest`): inspects `raw/` to classify the
   experiment directory's phase as `PRE_GPU`/`RUN01_PRESENT`/`RUN02_PRESENT`
   and checks phase-appropriate invariants (harness files present in
   `PRE_GPU`; record count and absence of `STOP.json` in the later phases).
3. **NON-RECORDED smoke gate** (`verify.py --preflight`/`--between-runs`):
   a throwaway `a+b` dispatch through the exact same `tools/agxtest/
   agxtest.py` path every case uses, run in a `tempfile.TemporaryDirectory`
   — never written under `raw/`. Run once before `run01` (`--preflight`)
   and once again before `run02` (`--between-runs`) to catch a
   toolchain/environment regression between the two gated captures.
4. **No nondeterministic field in byte-compared records.** `01_results.jsonl`
   (GATED) excludes wall-clock timestamps, durations, and raw subprocess
   argv/stdout/stderr — those go in the sibling, explicitly NON-gated
   `01_timing.jsonl`. `verify.py::GATED_FIELDS` enumerates exactly what is
   compared across runs.
5. **Fixtures from RECORDED REALITY.** No hand-typed "known good" byte
   fixture is embedded in the harness; the smoke-gate kernel's expected
   result (`11,22,33,44` for `{1,2,3,4}+{10,20,30,40}`) is elementary
   arithmetic, not a captured hardware artifact standing in for one.

Additional standing requirements this run honors: append+`fflush` each
case's record to `01_results.jsonl` as it completes (`run.py`, one line per
case, flushed immediately); a timestamped `PROGRESS.md` entry per milestone;
partial `RESULTS.md` sections written as their data exists; a hard
per-case timeout (40s dispatch timeout, 55s subprocess wall-clock kill);
one variable changed per case (see `analysis/casematrix.py` — every case
isolates one operation/boundary family); each case its own fresh process
(`case_exec.py` invoked once per case index via `subprocess.run` inside
`case_exec.py`'s own call to `agxtest.py`, itself invoked as a **separate**
subprocess by `run.py` per case — so a case is two nested fresh processes,
never in-process reuse); faults recorded as results (`status`/`timed_out`/
`exception` fields, never discarded); run ids `m4-<UTC-timestamp>-run01`/
`run02`, never reused; no post-capture repair (a defective capture is
retained and quarantined, a fix gets a new run id); revision pinned above,
never gated on live `HEAD`.

## 5. Expected observation / falsifiers, condensed

For every boundary-sweep case, the falsifier is: **the observed value
matches none of the recorded candidate models.** Where that happens (none
did, in the pilot — see `PROGRESS.md`), the finding would be reported as
`UNKNOWN` per CODEX §7, not forced into the closest-looking model. For the
structural (`INT-06`/`INT-09`/`INT-10`/`INT-12`/`INT-13`/PACK family-
membership) claims, the falsifier is: the compared kernels' `_agc.main`
byte lengths/opcode families do NOT show the predicted single-op vs.
multi-op / shared-family vs. disjoint-family split.

## 6. Two-run gated capture plan

`run.py --run-id m4-<UTC-timestamp>-run01` then, after a fresh
`--between-runs` smoke pass, `run.py --run-id m4-<UTC-timestamp>-run02`.
Both produce `raw/<run-id>/{00_env.json,01_results.jsonl,01_timing.jsonl,
02_dispatch.json,full/*.json}`. Post-capture: `verify.py --captured --run
<run01>` and `--run <run02>` (schema), then `verify.py --captured --compare
<run01> <run02>` (byte-identity on `GATED_FIELDS`). All four must PASS
before promoting any result into `RESULTS.md` as `HW-VALIDATED`-tier.
