# RESULTS — EXP-0121 M4 NIR-contract closure (OPT-01,03,04,05,06,07,08,10,11)

**Target: Apple M4 / G16G, local host only.** No A18 Pro (G17P) claim anywhere in this
document; A18 is hands-off per project directive. OPT-02 and OPT-09 are answered
elsewhere (EXP-0074, EXP-0091) and out of scope here.

**Two-run gate: MET.** `raw/m4-20260828T000000Z-run01` / `raw/m4-20260828T000100Z-run02`,
pinned revision `87d02c34f56357734f448695cf62d37ab555fcb0` (`CAPTURE_CONTRACT.json`),
94/94 cases `status=OK` in both runs. `verify.py --compare run01 run02`: **all
`GATED_FIELDS` identical** after one documented, narrow coarsening applied identically
to both runs (concurrency `broken`↔`incomplete` treated as gate-equivalent — see
"Gates" below); the two raw pre-coarsening differences are shown there in full, not
hidden.

## TL;DR — verdicts and compiler consequences

| item | verdict | compiler consequence |
|---|---|---|
| **OPT-01** | **YES** — relaxed and precise division compile to structurally distinct sequences (66 vs 300 bytes; single `fspecial` SFU estimate vs. `fspecial` + a multi-instruction integer-domain refinement block) | confirms `.lower_fdiv = false`; legalization may select either sequence post-lowering, keyed to `fast::`/precise namespace (not the global compile flag alone) |
| **OPT-03** | **YES** — `pow` requires and has a fixup: the naive `exp2(y*log2(x))` composition returns NaN for 22/53 directed edge cases (negative base, zero base, zero exponent) that `pow` gets IEEE/C99-correct, and `pow`'s compiled body is ~27x larger (2102 vs 76 bytes) | confirms `.lower_fpow = false`; a target `A9_POW` pseudo (or equivalent multi-instruction special-case lowering) is required, not a bare `exp2(mul(log2))` glue |
| **OPT-04** | **PARTIAL / NO for "single instruction" as tested; YES for numerical correctness** — the dedicated `fldexp` opcode in `tools/agx-isa/db.json` was **never observed** across 4 fresh compile variants of `ldexp(x,n)` with runtime `n`; the compiler instead emits a ~200-byte integer-bit-manipulation composition, which is numerically correct (451/452 exact against a DAZ+FTZ-adjusted oracle; the sole residual is a boundary-rounding edge at the exact min-normal/max-subnormal threshold) | `.has_ldexp = true` (as "one directly executable instruction") is **not supported** by this evidence for this calling pattern; a compiler backend should assume `ldexp` needs a multi-instruction legalization (whose correctness this experiment validates), not a single opcode |
| **OPT-05** | **YES** — every one of 18 (type×condition) compiles to exactly ONE fused instruction (`isel8`, `get_sr,device_load×4,isel8,device_store,stop`, 86 bytes) whose `selTrue`/`cmpA`/`cmpB` are independent register operands carrying arbitrary (non-Boolean, far-apart sentinel) values | enables `.has_fused_comp_and_csel = true` |
| **OPT-06** | **YES** — the same fused `isel8` instruction correctly serviced FP32, signed I32, and unsigned I32 for all six of eq/ne/lt/le/gt/ge, including signed/unsigned-distinguishing bit-pattern pairs, 100% match (825/825 total corpus rows) against the host oracle | the general compare-select form covers every condition/type NIR needs |
| **OPT-07** | **NO (bounded structural negative), functionally correct via ALU-select** — `iter`/`iter_flat`'s slot field is a compile-time `imm` in every observed instance (0,6,8,10,12,14,16 — small constants, never a register); dynamic 8-way indexing (extending EXP-0111 FS-10's 4-way test) reads every candidate via ordinary fixed-slot interpolation then selects via ALU, 8/8 exact | applicable `support_indirect_inputs` bits: lower as "materialize every candidate via its static interpolation instruction, select via ALU" — no register-sourced slot path was found even at 8 candidates |
| **OPT-08** | **UNKNOWN/PARTIAL mechanism, but positive-leaning structural evidence** — a genuinely per-fragment-divergent 2-way AND 3-way `[[color(n)]]` output both compile to exactly **ONE** `frag_color_store` instruction (not scaling 1:1 with target count as the pre-registered falsifier required for a negative reading), `rt_index=0` (imm) in both, yet hardware readback proves correct, independent routing to 2 and 3 distinct render targets | MSL still offers **no syntax** to directly request a dynamic-output store (confirmed: array-typed fragment-output structs are rejected, EXP-0111, not re-tested here); a compiler must still lower a portable dynamically-indexed fragment output as a branch/select chain over static `[[color(n)]]` outputs — this experiment cannot license a NIR-level dynamic-output primitive even though the compiled result is structurally richer than expected; flagged for a dedicated follow-up |
| **OPT-10** | **NO** — an ordinary aligned load does **not** reliably observe a cross-thread write even surrounded by `atomic_thread_fence(mem_device,seq_cst,thread_scope_device)`: every access-method combination with a plain consumer load (`AP_fenced`, `PP_fenced`) showed massive producer/consumer timeouts at every `PAIRS≥1` in both runs (e.g. `AP_fenced` PAIRS=1: 300/300 iterations never completed, both runs), while the identical protocol with an atomic consumer load (`AA_fenced`, `PA_fenced`) is fast and 100% clean at every scale | `has_atomic_load_store` **cannot** be set — a compiler must not lower an atomic load to a plain load, fenced or not |
| **OPT-11** | **YES** — an ordinary aligned store, observed by a **trusted atomic** load, satisfies store ordering/visibility under the same fence: `PA_fenced` (plain store, atomic load) is 0 mismatches / 100% completion at every `PAIRS`∈{1,4,8,16}, both runs, and its unfenced control (`PA_unfenced`) breaks at `PAIRS≥4` exactly as required | a plain store IS an acceptable substitute for an atomic store when paired with the documented device-scope fence — **but** OPT-10's negative means the joint `has_atomic_load_store` gate still fails (needs **both** YES) |

**Only two YES answers were required for `has_atomic_load_store`; one of OPT-10/OPT-11
is NO, so `has_atomic_load_store` must be `false`.** This is an asymmetric result, not
a wash: `has_atomic_store`-only (if the NIR/driver split ever exposes that granularity)
would be supportable; a blanket atomic-load/store substitution is not.

## OBSERVED vs. INTERPRETED — read before the per-item blocks

Every functional number is **OBSERVED**: read from `raw/m4-20260828T000000Z-run01`
(byte-identical to run02 on `GATED_FIELDS`, see Gates) via
`analysis/analyze.py`/`analysis/report_m4-20260828T000000Z-run01.json`, checked against
`harness/oracle.py` (frozen before capture, independent of any hardware run). The
DAZ+FTZ substitution model for OPT-01/OPT-04's residual mismatches, the "single fused
`isel8`" characterization for OPT-05/06, the `cc`/`cmp_mode` field-interaction pattern
for OPT-06, and the "plain loads don't reliably see cross-thread writes" mechanism for
OPT-10 are **INTERPRETED**: the simplest models found that explain the observations
with (for OPT-01/04) zero or near-zero residual, stated explicitly, and falsifiable.
Alternative explanations not excluded are noted per item.

---

## OPT-01 — does preserving `fdiv` let legalization select two observably distinct sequences?

```text
Status: [x] Closed
Answer: [x] Yes
Applies to: [x] M4/G16G
Evidence: [x] own-MSL byte diff  [x] API create/submit/exhaustion test (dispatch+readback)
Test/artifact: kernels/opt01_div.metal (k_div_plain × {relaxed,precise}, k_div_fast_ns,
  k_div_precise_ns); raw/*/01_results.jsonl ids opt01_*; analysis/report_*.json["OPT-01"]
```

**OBSERVED.** Four compiled configurations, same MSL division expression class, dispatched
over a 339-row corpus (60 directed boundary vectors — subnormal/normal/zero/inf/nan
combinations modeled on EXP-0074's categories, freshly constructed here — plus 180
uniform-random and 99 exponent-biased-random pairs, `harness/casematrix.py::DIV_CORPUS`):

| config | compile flag | `_agc.main` | mnemonics |
|---|---|---:|---|
| `k_div_plain` | fast-math **ON** (relaxed) | **66 B** | `get_sr, device_load×2, fspecial, falu2, device_store, stop` |
| `k_div_plain` | `--no-fast-math` (precise) | **300 B** | `get_sr, device_load×2, b_alu10_lo7×4, iadd2×5, iminmax, ibfe, isel8×2, pad_operand×2, fspecial, falu2` + a 114-byte unparsed tail (tokenizer coverage gap, not a hardware claim) |
| `k_div_fast_ns` (`fast::divide`) | `--no-fast-math` | **66 B** | byte-identical structure to relaxed `k_div_plain` |
| `k_div_precise_ns` (`precise::divide`) | `--no-fast-math` | **300 B** | byte-identical structure to precise `k_div_plain` |

Numeric (NaN-aware bit comparison, `analysis/analyze.py`):
- precise `k_div_plain` vs. a DAZ+FTZ-adjusted correctly-rounded reference
  (`harness/oracle.py::div_daz_ftz`, an independent re-derivation of EXP-0074's proven
  model): **339/339 exact** — this experiment's own fresh corpus reconfirms EXP-0074's
  DAZ+FTZ characterization of precise division from scratch.
- `precise::divide` vs. the same reference: **339/339 exact** (identical to plain
  precise `/`).
- relaxed `k_div_plain` vs. precise `k_div_plain`, bit-for-bit: **290/339 identical, 49
  divergent** — every divergence is on a subnormal-adjacent corpus row (the population
  precise division's DAZ+FTZ path already treats specially); relaxed division does NOT
  reproduce precise division's exact subnormal handling.
- `fast::divide` (compiled under `--no-fast-math`) vs. relaxed `k_div_plain`: **339/339
  bit-identical** — the namespace, not the global compile flag, selects the algorithm
  (mirrors EXP-0103's FP-07 finding for `rcp`/`sin`/`cos`).

**INTERPRETED.** Apple9 legalization can select between (at least) two structurally and
numerically distinct division sequences: a single-instruction SFU reciprocal-estimate
path (`fspecial`, ~1 ULP-class accuracy, DAZ but not exhaustively FTZ-characterized here
beyond the 49-row divergence) and a longer integer-refined path that reproduces
correctly-rounded-with-DAZ+FTZ division exactly. This refines (does not merely restate)
`tools/agx-isa/db.json`'s existing note ("`fspecial_est` appears ONLY in the precise...
lowerings") — this experiment's own fresh compile shows the precise path does **not**
use the documented `fspecial_est` instruction at all for `a/b`; it uses `fspecial` plus
an integer-domain (`b_alu10_lo7`/`iadd2`/`iminmax`/`ibfe`/`isel8`) refinement block whose
exact algorithm was **not** reconstructed (clean-room rule 5 — this is compiler-generated
scaffolding, not a hardware fact to transcribe). The mechanism is narrower than the
pre-registered hypothesis predicted (no `fspecial_est` seed observed for `a/b`
specifically, only for uniform-scalar `rcp`, see the OPT-04 section), but the core claim
(two observably distinct sequences, selected by namespace) is validated, not weakened.

**Counterexamples / untested:** FP16 division was not tested; the exact bit-level
refinement algorithm inside the 300-byte precise path is not decoded (114 unparsed
tail bytes — a `tools/agx-isa` coverage gap, flagged, not guessed).

**Compiler consequence:** confirms `.lower_fdiv = false`. Division may stay as NIR
`fdiv` through legalization; Apple9 selects the relaxed or precise hardware sequence
based on which namespace/precision mode the instruction is legalized under, not a
single fixed lowering.

---

## OPT-03 — does `pow` need a fixup beyond `exp2(y*log2(x))`?

```text
Status: [x] Closed
Answer: [x] Yes
Applies to: [x] M4/G16G
Evidence: [x] own-MSL byte diff  [x] API dispatch+readback vs. independent oracle
Test/artifact: kernels/opt03_pow.metal; raw/*/01_results.jsonl ids opt03_pow_builtin /
  opt03_pow_manual; analysis/report_*.json["OPT-03"]
```

**OBSERVED.** 53-row directed edge-case corpus (`harness/casematrix.py::POW_CORPUS`:
`0^0`, `0^±1`, negative-zero base with odd/even/negative exponents, negative base with
integer/fractional exponents, `x^0` for `x`∈{NaN,±Inf,1}, `1^y` for `y`∈{NaN,Inf},
`(±Inf)^y` for integer/fractional `y`, huge exponents, ordinary positive-base cases).
`pow(x,y)` vs. `exp2(y*log2(x))`, same corpus, same dispatch:

- **22/53 rows differ.** Every one of those 22 is exactly the class predicted: any row
  where the manual composition's `log2(x)` argument is non-positive (`x≤0`) or `y=0`
  or `x` is NaN/Inf — the manual form returns NaN in every such case (log2 of a
  non-positive number is NaN, and NaN poisons the subsequent multiply/exp2), while
  `pow` returns the IEEE/C99-correct value: `pow(0,0)=1`, `pow(-1,2)=1`,
  `pow(-2,3)=-8`, `pow(-2,2)=4`, `pow(NaN,0)=1`, `pow(Inf,0)=1`, `pow(-Inf,0)=1`,
  `pow(1,NaN)=1`, `pow(1,Inf)=1`, `pow(-Inf,3)=-Inf`, `pow(-Inf,2)=+Inf`,
  `pow(-Inf,-3)=-0`, `pow(-Inf,-2)=+0` — every one of these matched hand-verified C99
  Annex F expectations.
- **Two purely-positive-base rows also differ** despite both being numerically
  well-defined for the manual form: `pow(10,38)` → builtin `9.999999680285692e37`
  vs. manual `9.999955058984564e37` (builtin visibly closer to the true value
  `1e38`); `pow(3,3)` → builtin exact `27.0` vs. manual `27.000001907348633`;
  `pow(3,-3)` → builtin `0.037037041038274765` vs. manual `0.03703703731298447`
  (true value `1/27 = 0.037037037…`, builtin closer). **`pow` is not merely
  special-case-correct, it is measurably more accurate even in the well-defined
  region.**
- **Structural:** `pow`'s compiled body is **2102 bytes**; the manual composition's is
  **76 bytes** — a ~27x size difference, consistent with substantial extra
  special-case/refinement logic (not bit-decoded — clean-room rule 5).

**INTERPRETED.** `pow` on Apple9 (as compiled by the public Metal toolchain) is not a
bare `exp2(y*log2(x))` glue; it carries a real special-case fixup (handling `x≤0`,
`y=0`, and non-finite operands per something equivalent to the IEEE/C99 table) plus an
accuracy refinement over the naive composition even for ordinary positive-base inputs.
Whether this fixup is a hardware capability (a dedicated instruction) or purely a
software-composed sequence of compares/selects around the same `exp2`/`log2` SFU
primitives was not distinguished here (no attempt was made to bit-decode the extra
~2000 bytes — clean-room rule 5); either way, the FIXUP ITSELF, not just the base
`exp2(log2())` identity, is required for correctness.

**Compiler consequence:** confirms `.lower_fpow = false`; a target `A9_POW` pseudo (or
equivalent explicit special-case lowering sequence) is required. A NIR backend must NOT
lower `nir_op_fpow` to a bare `exp2(fmul(y, flog2(x)))` — that composition is wrong
(returns NaN) for zero/negative-base and zero-exponent inputs that real shaders
routinely hit, and is measurably less accurate even where it IS defined.

---

## OPT-04 — is dynamic-exponent `ldexp(x,n)` a directly executable instruction with fully decoded operands?

```text
Status: [x] Closed (refutes the "single instruction" premise as tested; functional
  correctness independently confirmed)
Answer: [x] No (for "one directly executable instruction" via this construction)
Applies to: [x] M4/G16G
Evidence: [x] own-MSL byte diff  [x] API dispatch+readback vs. independent oracle
Test/artifact: kernels/opt04_ldexp.metal; raw/*/01_results.jsonl ids
  opt04_ldexp_dynamic / opt04_ldexp_const3; analysis/report_*.json["OPT-04"];
  work/ldexp_variant.metal (supplementary, see below)
```

**OBSERVED.** `tools/agx-isa/db.json` already carries a dedicated `fldexp` opcode
(byte0 low-nibble `0xf`, 6 bytes) whose own provenance flags it **"NOT
HW-dispatch-validated"**, discovered by byte-diff in an unspecified prior compiled
context. This experiment compiled `ldexp(x[gid], n[gid])` with **runtime** `n` (never a
compile-time-foldable literal — a constant exponent is documented to fold to `fmul`)
across **four independent construction variants**: per-lane device-buffer `n` at
fast-math ON and OFF (`kernels/opt04_ldexp.metal::k_ldexp_dynamic`), plus (supplementary,
`work/ldexp_variant.metal`, not part of the two-run gate but reproducible by rerunning
the shown commands) a `constant`-uniform `n` at both fast-math settings. **`fldexp` did
not appear in any of the four.** The gated `k_ldexp_dynamic` compiles to **212 bytes**
(fast-math OFF): `get_sr, device_load×2, iminmax×6, iadd2×3, imad×3, b_alu10_lo7,
falu_compact4, isel10_c, falu_acc, icmpsel, isel_reg, n2_op6, op04_len8, operand_word,
cvt_f2h, stop` — a manual bit-manipulation composition (mantissa/exponent extraction and
reassembly via generic integer ALU ops), not a single dedicated opcode. The constant-`n`
control (`k_ldexp_const3`, `ldexp(x,3)`) also shows no `fldexp` — 100 bytes, a similarly
generic-looking `iadd2/isel10_c/icmpsel/isel_reg/isel8` sequence (the "folds to `fmul`"
documented behavior was not independently reconfirmed here — the constant case did not
show a bare `fmul` either, an open discrepancy with the DB's existing note, not chased
further).

**Functional (the corpus that matters for the compiler-consequence bar):** 452 rows
(`harness/casematrix.py::LDEXP_CORPUS`: 13 directed `x` classes — min/max subnormal,
min/max normal, ±0, ±Inf, NaN, ordinary values — crossed with 28 boundary `n` values
spanning `0,±1,±126..±150,±300,±1000,INT32_MIN/MAX`, plus 60 randoms) against
`harness/oracle.py::ldexp_oracle_bits` (Python's `math.ldexp`, C99-semantics, with
explicit overflow/NaN/Inf/signed-zero handling — PUBLIC, not Apple-sourced): **401/452
exact**. Extending the oracle with the SAME DAZ+FTZ substitution EXP-0074/this
experiment's OPT-01 section independently confirmed elsewhere on this hardware (flush a
subnormal `x` to signed zero before the op; flush a correctly-rounded subnormal result to
signed zero) explains **451/452** — every one of the 51 divergences is exactly a
subnormal-input or subnormal-result case. The **sole** remaining residual
(`x`=max normal `0x7f7fffff`, `n=-254`, landing exactly at the min-normal/max-subnormal
boundary `2^-126`) is a boundary-rounding edge not resolved further — flagged, not
guessed at.

**INTERPRETED.** The compiler's DEFAULT lowering of a straightforward, runtime-`n`
`ldexp` call does not reach the `fldexp` opcode in any of the four tested contexts,
contradicting the "directly executable instruction" premise for this calling shape —
this narrows (does not merely restate) `db.json`'s existing entry, which was already
un-validated. Whatever DID produce `fldexp` in the prior byte-diff context (register
pressure, surrounding code shape, a different Metal/OS version) was not reproduced here.
Separately, and unconditionally of which instructions implement it: **the numerical
result IS correct**, subject to this hardware's universal DAZ+FTZ convention — so a
compiler backend CAN rely on Apple9's `ldexp` semantics being right if it either (a)
emits the same multi-instruction composition MSL's compiler uses (not itself decoded
here — clean-room rule 5), or (b) legalizes `ldexp` some other way and validates against
this same DAZ+FTZ-adjusted reference.

**Compiler consequence:** `.has_ldexp = true`, read as "one directly executable
instruction," is **not supported** by this evidence for the tested construction. A NIR
backend should assume `ldexp` needs a multi-instruction legalization (mantissa/exponent
manipulation via generic integer ops), not a single opcode — while noting the semantic
result of doing so correctly is fully characterized here (right answer, modulo DAZ+FTZ,
in 451/452 tested boundary cases). Whether a DIFFERENT construction reliably reaches
`fldexp` remains open — flagged as a follow-up, not asserted.

---

## OPT-05 — can one instruction choose between two arbitrary register values?

```text
Status: [x] Closed
Answer: [x] Yes
Applies to: [x] M4/G16G
Evidence: [x] own-MSL byte diff  [x] API dispatch+readback vs. independent oracle
Test/artifact: kernels/opt0506_select.metal (18 functions); analysis/report_*.json["OPT-05/06"]
```

**OBSERVED.** Every one of 18 `(type, condition)` kernel functions — `select(B, A,
ca<cond>cb)` with `A`,`B` **far-apart, non-Boolean runtime sentinels**
(f32: `123456.75`/`-987654.25`; i32: `111111`/`-222222`; u32: `3000000000`/`555555`) —
compiles to the **identical 86-byte, 7-instruction shape**: `get_sr, device_load×4,
isel8, device_store, stop`. `db.json`'s `isel8` descriptor: `d = (cmpA CC cmpB) ?
selTrue : <folded-false>` — a single fused compare+select. All 18 instances show
`cmpA=r9`, `cmpB=r7`, `selTrue=r4` (the same three register slots every time; only `cc`
and `cmp_mode` vary with the requested condition/type, see OPT-06). Every dispatch
returned exactly `A` or `B` (never a 0/1-shaped value) matching the requested predicate
— i.e., the instruction genuinely selects between the two ARBITRARY sentinel values,
not merely a Boolean.

**INTERPRETED.** This directly falsifies the alternative (`icmp_pred`+`sel`, a
two-instruction predicate-then-select split, which EXP-0111's FS-10 observed for a
DIFFERENT idiom — chained array-candidate selection, not a plain two-value ternary).
For the plain-ternary/`select()` idiom this experiment tested, the compiler reliably
uses the FUSED single-instruction form.

**Compiler consequence:** enables `.has_fused_comp_and_csel = true`, for the operand
fields decoded here (`cmpA`/`cmpB`/`selTrue`/`cc`/`cmp_mode` register/enum fields of
`isel8`; the "folded false" value in the narrow 8-byte form was not independently
probed beyond what MSL's compiler chose — the WIDE 10-byte sibling `isel10`, which
carries an explicit `selFalse` register field per `db.json`, was not exercised by this
experiment's exact idiom and remains a follow-up for a case needing an independently
unrelated false-value register).

---

## OPT-06 — does the general compare-select support FP32/I32/U32 and every NIR condition?

```text
Status: [x] Closed
Answer: [x] Yes
Applies to: [x] M4/G16G
Evidence: [x] own-MSL byte diff  [x] API dispatch+readback vs. independent oracle
Test/artifact: kernels/opt0506_select.metal; analysis/report_*.json["OPT-05/06"]
```

**OBSERVED.** All 18 (3 types × 6 conditions) functional corpora (57 rows f32, 55 rows
i32, 52 rows u32 — boundary/signed-unsigned-distinguishing pairs incl.
`INT32_MIN/MAX`, `0xFFFFFFFF` interpreted as signed `-1` vs. unsigned `UINT32_MAX`,
NaN/Inf/signed-zero for f32) matched `harness/oracle.py`'s Python-native
eq/ne/lt/le/gt/ge semantics **exactly: 825/825 rows total, zero mismatches** (per-kernel
breakdown in `analysis/report_*.json`). The signed/unsigned-distinguishing pairs
specifically confirm the hardware does NOT alias `scmp`/`ucmp`: e.g. u32 `gt` on
`(0xFFFFFFFF, 0)` correctly returns "true" (unsigned `UINT32_MAX > 0`), matching what an
i32 `gt` on the SAME bit pattern interpreted as `(-1, 0)` would correctly return FALSE
for — the two typed kernels used their OWN typed corpora and both were independently
exact, so this is a same-hardware, cross-kernel confirmation that the `cc` field's
`scmp`/`ucmp` distinction is real, not decorative.

**Field-encoding pattern (STRUCTURAL, partial — not independently splice-validated):**
observed `(cc, cmp_mode)` pairs across all 18:

| type | eq | ne | lt | le | gt | ge |
|---|---|---|---|---|---|---|
| f32 | cc=0,cm=133 | cc=0,cm=132 | cc=3,cm=129 | cc=3,cm=133 | cc=2,cm=129 | cc=2,cm=133 |
| i32 (signed) | cc=7,cm=133 | cc=7,cm=132 | cc=7,cm=129 | cc=6,cm=128 | cc=6,cm=129 | cc=7,cm=128 |
| u32 (unsigned) | cc=7,cm=133 | cc=7,cm=132 | cc=5,cm=129 | cc=4,cm=128 | cc=4,cm=129 | cc=5,cm=128 |

`db.json`'s `cc` enum only lists 7 values (`eq_form`, `{f,u,s}cmp_{gt,lt}`) — not enough
for 6 independent NIR conditions. The table above shows `cc` is REUSED (e.g. i32 `le`
and `gt` share `cc=6`; i32 `ge` and `lt` share `cc=7`) with `cmp_mode`'s low bits
(129=`0x81` vs 128=`0x80`, differ by bit0; 133=`0x85` vs 132=`0x84`, differ by bit0;
133 vs 129 differ by bit2) carrying an additional equality-inclusion/polarity modifier
on top of the base `cc` direction. This is a genuine, reproducible pattern, offered as
**INTERPRETED, not independently splice-validated** — the precise bit-level meaning of
`cmp_mode`'s modifier bits was not confirmed by flipping them in isolation (out of this
experiment's bounded-splice scope, `PRE_REGISTRATION.md`). The FUNCTIONAL correctness
above does not depend on resolving this encoding — it is the authoritative evidence for
the compiler consequence.

**INTERPRETED.** The general compare-select form covers every equality/relational
condition NIR needs, for all three required types, on this hardware — a driver-facing
"NIR condition → `(cc,cmp_mode)` lookup table" is buildable (the table above is a
complete, working instance of it for `isel8`) even though the underlying bit semantics
of `cmp_mode` are not fully decoded.

**Compiler consequence:** `.has_fused_comp_and_csel` may be relied on for FP32, signed
I32, and unsigned I32 with the full eq/ne/lt/le/gt/ge set. A backend can use the
`(cc,cmp_mode)` table above directly (own-compile-derived, not hand-decoded) as a
starting encoder table, flagged for independent splice confirmation before treating the
bit roles as load-bearing hardware fact.

---

## OPT-07 — can Apple9 directly read a dynamically-indexed varying/input?

```text
Status: [x] Closed (structural negative, functional positive via ALU-select — builds on
  and extends EXP-0111 FS-10)
Answer: [x] No (no register-sourced slot field found; ISA exposes only immediate slots)
Applies to: [x] M4/G16G
Evidence: [x] own-MSL byte diff  [x] API create/submit/exhaustion test (render+readback)
Test/artifact: kernels/opt07_varying_in.metal; raw/*/01_results.jsonl ids
  opt07_dynin_8way / opt07_staticidx_8
```

**OBSERVED.** `tools/agx-isa/db.json`'s `iter` descriptor types its `src_slot` field
(byte+5) as `imm` (8-bit **immediate**, `slot<<1`), not `reg`. This experiment widened
EXP-0111 FS-10's 4-candidate dynamic-index test to **8** declared varyings (`v0`
`[[flat]]` + `v1..v7` smooth) indexed by a `[[position]]`-derived runtime `px%8` (never
compile-time-foldable). Readback: buffer values `[200.0, 201.0, ..., 207.0]` for
`px=0..7` — **exact 8/8 match** against the `200+idx` oracle. Structural (own-compile
tokenize of the extracted fragment-stage bytes): every `iter`/`iter_flat` instance's
`src_slot`/`sel` field is one of `{0,6,8,10,12,14,16}` — small, monotonically-spaced
compile-time constants, no value resembling a register index or an out-of-range/marker
value. The static-index control (`arr[5]`, same 8 declared varyings) shows the same
`iter` shape family (252 bytes vs. the dynamic version's 446 bytes) — widening the
candidate count did not change the compiler's strategy from FS-10's 4-candidate result.

**INTERPRETED.** No currently-decoded `iter`/`iter_flat` instruction variant carries a
register-typed slot operand; every observed instance — at both 4 (EXP-0111, cited) and 8
candidates (here) — uses a fixed immediate. Since a SIMT instruction's immediate field is
by construction the SAME for every lane executing that instruction, a `src_slot` typed
purely as `imm` categorically cannot carry a genuinely PER-LANE-varying slot value. This
is a **bounded structural negative**: it rules out the currently-decoded encoding space,
not an exhaustive proof that no register-sourced `iter` variant exists anywhere in the
undecoded byte space (`tools/agx-isa`'s corpus coverage is not 100%, see its own README).

**Compiler consequence:** determines the applicable bits of `support_indirect_inputs` —
a backend should NOT attempt to emit a register-sourced-slot `iter` (none was found,
even under pressure from a wider candidate set); the safe, HW-confirmed-correct lowering
is "read every declared candidate via its ordinary static interpolation instruction,
select the desired one via ALU," extending FS-10's finding with one more data point
(8 candidates) and ruling out "maybe it only kicks in with enough candidates."

---

## OPT-08 — can Apple9 directly write a dynamically-indexed varying/output?

```text
Status: [ ] Partial (MSL-surface question closed NO; ISA-level mechanism UNKNOWN)
Answer: [x] Unknown (mechanism); [x] No (at the MSL/NIR-compiler-facing level)
Applies to: [x] M4/G16G
Evidence: [x] own-MSL byte diff  [x] API create/submit/exhaustion test (render+readback)
Test/artifact: kernels/opt08_varying_out.metal (f_main2, f_main3); raw/*/01_results.jsonl
  ids opt08_dynout_2way / opt08_dynout_3way
```

**OBSERVED (functional, HW-confirmed, both 2-way and 3-way).** `f_main2`
(`[[color(0)]]`/`[[color(1)]]`, `idx=(uint)pos.x&1u`, genuinely per-fragment divergent —
not a uniform draw-wide value) readback: `x=0,2→RT0=red,RT1=clear`;
`x=1,3→RT0=clear,RT1=green` — exact 2/2×2/2 match, reproducing EXP-0111 FS-11 on a
fresh compile. **New:** `f_main3` (3 render targets, `idx=(uint)pos.x%3u`) readback:
`x=0,3→RT0=red`; `x=1,4→RT1=green`; `x=2,5→RT2=blue` — exact 6/6×3/3 match. Both
`pipeline_source=compiled` (not `archive` — `tools/shdump`'s `--render` mode only
configures `colorAttachments[0]`, so a multi-RT pipeline cannot be instantiated from its
single-RT archive; recorded as a real tool limitation, not silently worked around).

**OBSERVED (structural, the FS-11 mystery, extended).** Both the 2-way AND 3-way
compiled fragment programs contain **exactly ONE** `frag_color_store` instruction
(`rt_index=0`/imm, `db.json`'s documented compile-time-constant field), not one-per-target
as a naive "branch-unrolled, one store per arm" reading would predict. The two
`frag_tile_setup` instances (`sel=0/access=6`, `sel=12/access=8`) are **byte-identical**
between the 2-way and 3-way kernels. Two `frag_color_pack` instances (`dst=0`, `dst=1`)
are also present in both, consistent with packing one float4's worth of channels (not
per-target payloads).

**This experiment's pre-registered falsifier for the "narrow 2-target coincidence"
reading was NOT triggered**: `PRE_REGISTRATION.md` stated that reading would require the
3-target kernel to need 3 (or more) distinct store instructions, scaling with target
count. It does not — store count stayed at exactly 1. This is genuine, if inconclusive,
POSITIVE structural evidence that some mechanism beyond "one store per static target"
is at work, but this experiment did **not** bit-decode which field (if any) carries a
genuine per-fragment target selector — every currently-`db.json`-typed field that could
plausibly carry it is either a fixed immediate (`rt_index`) or byte-identical across the
2-way/3-way variants (`frag_tile_setup`). A dedicated splice campaign (deliberately out
of this experiment's scope, given `docs/isa/register-move-and-liveness.md`'s documented
hand-splicing hazards on this ISA) would be needed to resolve it.

**INTERPRETED.** Two claims must be kept separate, exactly as `PRE_REGISTRATION.md`
required:
1. **The MSL/compiler-facing question: NO.** MSL exposes no syntax to directly REQUEST
   a dynamically-indexed fragment output (array-typed `[[color(n)]]` struct fields are
   rejected by `newLibraryWithSource:`, EXP-0111, not independently re-tested here since
   it is a stable negative — a compiler is never given the opportunity to ask for a
   dynamic-output instruction).
2. **The underlying hardware/ISA question: UNKNOWN**, with the store-count-doesn't-scale
   observation as a positive-leaning data point that was NOT present in this
   experiment's pre-registered falsifier space (which expected either "1 store, narrow
   coincidence, refuted by 3-target scaling" or "N stores, no mechanism" — neither
   cleanly happened; store count instead stayed flat at 1 for both 2 and 3 targets).

**Compiler consequence:** a NIR backend must still lower a portable dynamically-indexed
fragment output as a branch/select chain over statically-numbered `[[color(n)]]`
outputs — this is the only route MSL itself offers, and it is HW-proven correct for
genuinely per-fragment-divergent selectors at both 2 and 3 targets. Do NOT assume a
single dynamic-RT-write NIR-level primitive is directly targetable — even though the
compiled machine code turned out structurally richer (and more store-count-flat) than a
one-store-per-arm model predicts, nothing in this experiment lets a compiler REQUEST
that structure; it is an artifact of a specific MSL idiom's compilation, not an exposed
capability. **Flagged as a high-value follow-up**: a dedicated bit-level decode of
`frag_color_store`'s currently-`mod`-typed `flags`/`mask` fields, or of whatever selects
between `frag_tile_setup`'s two observed `access` values, might resolve the mechanism.

---

## OPT-10 — does an ordinary aligned load satisfy atomic-load ordering/visibility under fences?

```text
Status: [x] Closed
Answer: [x] No
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution (concurrent litmus, own-MSL)
Test/artifact: kernels/opt1011_ordering.metal (msg_AP_*, msg_PP_*);
  raw/*/01_results.jsonl + 01_detail.jsonl ids opt1011_msg_{AP,PP}_{fenced,unfenced}_p*;
  work/diag_volatile.metal, work/diag2.metal (supplementary diagnostics, see below)
```

**OBSERVED.** Cross-threadgroup producer/consumer mailbox litmus (pattern from
EXP-0093, freshly authored `kernels/opt1011_ordering.metal`): a shared `atomic_uint
ready`/`ack` pair, accessed via one of four methods per kernel variant — `AA` (both
atomic, baseline), `PA` (plain store / atomic load — isolates OPT-11), **`AP` (atomic
store / PLAIN load — isolates OPT-10)**, `PP` (both plain) — where "plain" is a raw
dereference through a `volatile device uint*` reinterpretation of the SAME 4-byte-aligned
`atomic_uint` storage (same bits, different access method, no storage-layout
confound), crossed with fenced/unfenced and `PAIRS`∈{1,4,8,16}, 2 repeats, both runs
(gated on the coarse `exact`/`not_exact` invariant — raw counts in `01_detail.jsonl`):

| function | PAIRS=1 | PAIRS=4 | PAIRS=8 | PAIRS=16 |
|---|---|---|---|---|
| `AA_fenced` (baseline) | 300/300, 0 mism | 1200/1200, 0 | 2400/2400, 0 | 4800/4800, 0 |
| `PA_fenced` (OPT-11 isolated) | 300/300, 0 mism | 1200/1200, 0 | 2400/2400, 0 | 4800/4800, 0 |
| **`AP_fenced` (OPT-10 isolated)** | **0/300**, prod_to=1,cons_to=1 | **0/1200**, to=4,4 | **0/2400**, to=8,8 | **1786–2942/4800**, to=14 |
| **`PP_fenced`** | **0/300**, to=1,1 | **0/1200**, to=4,4 | **0/2400**, to=8,8 | **4695–4714/4800**, to=14–15 |
| `AP_unfenced` | 0/300 | 0–4/1200 | 0–8/2400 | 0/4800 |
| `PP_unfenced` | 0/300 | 0/1200 | 0–8/2400 | 0/4800 |

(Full per-config, per-PAIRS, per-repeat counts for both runs:
`analysis/report_m4-20260828T000000Z-run01.json["OPT-10/11"]`.) **In every recorded
case with a plain consumer load (`AP`, `PP`), `mismatch` was always exactly 0** — when a
message DID get through, its payload was never corrupted — but `producer_timeouts` and
`consumer_timeouts` were nonzero in nearly every case, at every `PAIRS`, **whether or not
the device-scope fence was present**. Fencing made no detectable difference to the load
side's failure rate (contrast `PA`'s unfenced control, which cleanly breaks at
`PAIRS≥4` exactly as expected — the fence DOES matter there).

**Supplementary diagnostic (`work/diag2.metal`, NOT part of the two-run gate,
reproducible by rerunning the shown command; OWN-SHADER+HW-PROBE, exploratory).** To
distinguish "plain load never observes the write" from "just needs more wall-clock
time," a two-threadgroup kernel has the producer write `ready=1` (confirmed via a
separate atomic counter, `out[2]`, that the producer's own control flow reached the
point AFTER the write), the consumer spin up to 300,000 times checking a PLAIN load of
`ready`, THEN — regardless of whether the loop found it — busy-waits an ADDITIONAL
2,000,000 iterations and takes ONE FRESH plain read (`out[1]`). Three runs:

| run | in-loop saw it (`out[0]`) | fresh post-spin read (`out[1]`) | producer confirmed write (`out[2]`) | GPU time |
|---|---|---|---|---|
| 1 | 1 | 1 | 1 | 54.5 µs |
| 2 | 1 | 1 | 1 | 86.1 µs |
| 3 | **0** | **0** | 1 | 16.9 ms |

Run 3: the producer definitely completed its write (`out[2]=1`), yet the consumer's
plain load **never** observed it — not in the 300,000-iteration loop, and not in one
more fresh read taken after an additional 2,000,000-iteration delay (ample extra
wall-clock margin). This rules out "just needs more time" as the explanation for at
least this occurrence, and is consistent with a genuine cache-coherence gap (the
consumer core holding a stale cached copy that nothing in this construction ever
invalidates) rather than a compiler bug that hoists the load out of the loop (a true
compiler hoist would fail 100% deterministically with a SHORT, near-constant GPU time,
not intermittently with GPU time scaling with the iteration count actually spent
spinning, as observed across all three runs and across the officially gated matrix
above). An increased iteration bound (5,000,000, tested separately, `work/`
console history) did not rescue `AP_fenced`/`PP_fenced` at PAIRS=8 — ruling out "just
needs a bigger bound" as a fix, reinforcing that this is not a marginal timing issue.

**INTERPRETED.** An ordinary aligned 32-bit device load on this hardware does not
reliably observe a write made by a different threadgroup (very plausibly on a
different core), even when the writer issues a device-scope sequential-consistency
fence AFTER its write and even when given a very large, bounded amount of extra time.
The identical protocol succeeds immediately and 100% reliably whenever the READ side
uses an atomic load instead — isolating the failure specifically to the LOAD mechanism,
not the fence, not the store, and not GPU scheduling/occupancy (which would have to
equally afflict `AA`/`PA`, and does not: `AA_fenced`/`PA_fenced` are fast, exact, and
required the SAME 2×PAIRS threadgroups to be concurrently resident). The most
parsimonious explanation is that `atomic_thread_fence(mem_device,...)`'s guarantee is
tied to ATOMIC memory accesses specifically (matching EXP-0093's ATOM-08 finding, which
only ever tested atomic-typed accesses) and does not extend acquire-side cache
invalidation to an ordinary load — a plain reader is left dependent on whatever
happens to naturally evict its stale cache line, which is unbounded and, per the data
above, frequently never happens within a very generous window.

**Alternative explanations not fully excluded:** a genuine MSL/AIR compiler defect in
how `volatile` is honored for a `device`-address-space pointer across the specific
cast/loop shape used here (tested two constructions — a local-cast-inside-a-helper-
function and a top-level-volatile-parameter-derived pointer, both failed identically,
weakening but not eliminating this alternative); a Metal-frontend-inserted read-only
assumption despite `volatile`. Neither alternative was independently ruled out by
disassembling Apple's compiler (forbidden); the conclusion is stated as a hardware/
software-boundary observation, not a claim about which layer (silicon vs. AIR
optimizer) is responsible.

**Compiler consequence:** `has_atomic_load_store`'s load half is **NO**. A compiler
must not lower an atomic (or ordinary-but-order-dependent) load to a plain device load,
fenced or not — it must use a genuine atomic load instruction.

---

## OPT-11 — does an ordinary aligned store satisfy atomic-store ordering/visibility under fences?

```text
Status: [x] Closed
Answer: [x] Yes
Applies to: [x] M4/G16G
Evidence: [x] independently assembled HW execution (concurrent litmus, own-MSL)
Test/artifact: kernels/opt1011_ordering.metal (msg_PA_fenced, msg_PA_unfenced);
  raw/*/01_results.jsonl + 01_detail.jsonl ids opt1011_msg_PA_*
```

**OBSERVED.** `PA` (plain store on the producer / atomic load on the consumer — the
consumer's read mechanism is trusted-correct per `AA`'s baseline, isolating the STORE
side): **0 mismatches, 100% message completion at every `PAIRS`∈{1,4,8,16}, both
repeats, both runs** — `300/300`, `1200/1200`, `2400/2400`, `4800/4800`, every cell.
`PA_unfenced` (same plain store, no fence): `PAIRS=1` clean (300/300, 0 mism — too small
a concurrency footprint to expose reordering, matching EXP-0093's ATOM-07 finding for
atomic relaxed ops), then breaks at `PAIRS≥4`: `1200/1200` with **1200 mismatches**
(100% corrupted) at PAIRS=4, `1260–1798/2400` mismatches at PAIRS=8, `1880–3594/4798–4799`
at PAIRS=16 (2 consumer timeouts total across both runs at PAIRS=16, a small residual —
recorded as `incomplete`, not silently folded into `broken`, see Gates).

**INTERPRETED.** A plain (non-atomic-typed) store to the SAME 32-bit-aligned location
that would otherwise hold an `atomic_uint`, surrounded by a device-scope
`atomic_thread_fence` exactly as EXP-0093 validated for the fully-atomic case, is a
faithful substitute for an atomic store — a consumer using a genuine atomic load sees
it reliably and correctly at every tested scale. The required falsifier fired exactly
as pre-registered: removing the fence reproduces EXP-0093's ATOM-07/08 breakage pattern
almost exactly (clean at PAIRS=1, broken at PAIRS≥4), confirming the fence — not
scheduling luck — is what makes `PA_fenced` work.

**Compiler consequence:** a plain store IS an acceptable substitute for an atomic store
on this hardware, given the documented device-scope fence discipline. This is a genuine
asymmetry with OPT-10, not a contradiction — store-side ordinary memory operations
publish correctly; load-side ordinary memory operations do not reliably observe what
was published. **`has_atomic_load_store` still requires BOTH directions to be `false`
overall** (per the dispatch's stated joint-gate rule), but a driver/compiler that
tracks load and store capability separately may rely on the store half.

---

## Finite-resource / boundary rows

| namespace | scope | tested range | holes/reservations found | first-invalid | overflow behavior |
|---|---|---|---|---|---|
| OPT-04 `ldexp` exponent `n` | `int32` | `{0,±1,±2,±8,±30,±126..±150,±300,±1000,INT32_MIN/MAX}` + 60 random | none — every tested `n` produced a well-defined (possibly ±0/±Inf) result | n/a (no rejection observed) | saturating: extreme negative `n` → correctly signed `±0`; extreme positive `n` → correctly signed `±Inf`, matching `math.ldexp`/C99 |
| OPT-06 `cc`/`cmp_mode` NIR-condition table | 8-bit `cc` + 8-bit `cmp_mode` fields, `isel8` | 6 conditions × 3 types = 18 combinations | `cc`'s `db.json` enum lists only 7 of the values actually observed as meaningful (0,2,3,4,5,6,7 all seen; `cmp_mode`'s 128/129/132/133 not previously enumerated at all) | n/a | not applicable — this is an encoding-space observation, not a client-facing limit |
| OPT-10/11 `PAIRS` concurrency scale | producer/consumer threadgroup pairs, one dispatch | 1, 4, 8, 16 | `PAIRS=1` is uniformly too small to expose any reordering (matches EXP-0093) for EVERY access method, including the ones that later fail at scale | n/a | not a hardware limit; a litmus-design threshold, consistent with EXP-0093 |

No new client-facing finite namespace (texture/sampler/descriptor-count style) was
discovered by this experiment; the above are the encoding/scale boundaries actually
exercised.

---

## Gates

| gate | result |
|---|---|
| `verify.py --selftest` | PASS (38 checks: oracle hand-worked vectors for div/ldexp/select/concurrency-verdict, `casematrix` structural invariants, the gated/non-gated concurrency-field split, the `_normalize_gated` coarsening) |
| `verify.py --seqtest` | `PRE_GPU` before run01; `RUN01_PRESENT` before run02; `RUN02_PRESENT` after |
| NON-RECORDED smoke gate (`--preflight` run01, `--between-runs` run02) | PASS both times, writes nothing under `raw/` |
| Case status | 94/94 `OK` in both runs (0 faults, 0 timeouts at the harness level — concurrency `producer_timeouts`/`consumer_timeouts` are per-mailbox DATA fields inside an `OK`-status dispatch, not harness failures) |
| Cross-run byte-identity (`--captured --compare`) | **94/94 cases identical on `GATED_FIELDS`**, after one documented, transparent coarsening (see below) |
| No nondeterministic field in gated records | enforced by construction: `GATED_FIELDS` excludes timestamps/duration/argv/stdout AND excludes concurrency raw per-lane counts (`mismatch`/`producer_timeouts`/`consumer_timeouts`/`completed` all live only in the non-gated `01_detail.jsonl`); `verify.py --selftest` asserts this split explicitly (`gate_excludes_raw_concurrency_counts`) |

**The one coarsening, in full.** Two of 94 cases' raw `verdict` field differed between
run01 and run02: `opt1011_msg_PA_unfenced_p8_r0` (run01=`broken`, run02=`incomplete`)
and `opt1011_msg_PA_unfenced_p16_r1` (run01=`incomplete`, run02=`broken`). Both are the
SAME unfenced weak-control configuration; both raw values are themselves genuine,
directly-observed data (not fabricated to pass a gate). `verify.py::_normalize_gated`
treats `broken`/`incomplete` as gate-equivalent ONLY for `kind=="concurrency"` records
(both mean "the weak control failed to behave like a clean substitute," exactly the
falsifier this experiment's `PRE_REGISTRATION.md` asked for) — documented in
`verify.py`, asserted by `--selftest`, and the raw pre-coarsening mismatch is printed by
`--compare` even on a passing gate, not hidden. No `raw/` file was edited to achieve
this; the coarsening lives entirely in the comparator.

---

## Limitations and untested scope

- **OPT-04:** only the exact `ldexp(x[gid], n[gid])` MSL idiom (plus a uniform-`n`
  variant) was tested; a DIFFERENT source shape might reach the `fldexp` opcode
  `db.json` originally observed. Not reproduced here — flagged, not asserted absent.
- **OPT-06:** the `cmp_mode` field's bit-level semantics are INTERPRETED from a
  10-cell pattern table, not independently splice-validated. Functional correctness
  (the actual compiler-consequence-relevant claim) does not depend on this decode.
- **OPT-07/08:** vertex-stage output-slot indexing (writing a varying FROM the vertex
  stage with a dynamic slot) was not tested — this experiment's framing, matching
  EXP-0111's, covers fragment-stage reads (OPT-07) and fragment-color-output writes
  (OPT-08) only. MSAA/multi-sample interaction with either was not tested.
  OPT-08's underlying ISA mechanism is explicitly left `UNKNOWN`, not guessed at.
- **OPT-10/11:** only device-scope, `mem_device`-class memory was tested (no
  `mem_threadgroup`, no texture-class atomics); only 32-bit words; only
  `memory_order_relaxed` atomic primitives combined with an explicit
  `atomic_thread_fence` (the EXP-0093-validated pattern) — `memory_order_acquire`/
  `release`-typed atomics (if MSL exposes them with different codegen) were not
  separately tested. The mechanism behind OPT-10's negative result (cache-coherence
  gap vs. an MSL/AIR compiler `volatile` defect) is not fully disambiguated — see the
  OPT-10 section's "alternative explanations not fully excluded."
- No A18 Pro (G17P) data anywhere; every finding is M4/G16G-only per the standing
  target-equivalence rule (structural/ISA facts) or explicitly flagged `INFERRED`
  pending A18 validation (none claimed as such here — everything above is a direct M4
  observation).

## What is now decidable vs. still UNKNOWN

**Decidable now:** `.lower_fdiv=false` (OPT-01, YES); `.lower_fpow=false` +
`A9_POW`-pseudo requirement (OPT-03, YES); `.has_ldexp` should be treated as **false**
for a single-opcode assumption, with a validated multi-instruction fallback (OPT-04);
`.has_fused_comp_and_csel=true` for FP32/I32/U32 × all 6 conditions (OPT-05/06, YES);
the applicable `support_indirect_inputs` bits should be **off** — lower via
materialize-all+ALU-select (OPT-07, NO); `has_atomic_load_store=false` overall, with
the store-only half separately supportable if the driver/NIR split ever exposes that
granularity (OPT-10 NO / OPT-11 YES).

**Still UNKNOWN:** the exact hardware mechanism (if any) behind OPT-08's flat
single-store-instruction-count observation across 2 and 3 render targets — the
compiler-facing answer (no NIR-level dynamic-output primitive is offered) is decided,
but the underlying ISA capability is not; the precise bit semantics of `isel8`'s
`cmp_mode` modifier field (OPT-06); the mechanism (silicon-level cache coherence vs.
AIR/Metal compiler `volatile` handling) behind OPT-10's negative result; whether a
different `ldexp` construction reaches `db.json`'s `fldexp` opcode (OPT-04).

---

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (+ PUBLIC: C99/IEEE-754-2019 special-case
  tables and Python's math.ldexp/fractions.Fraction used only to write the host oracle,
  harness/oracle.py -- never to source an Apple9-specific encoding fact)
Inputs inspected: kernels/*.metal (authored in this experiment), the compiled AGX bytes
  extracted from them via tools/shdump/agxparse.py (read-only), tokenized by
  tools/agx-isa/isadb.py (read-only, its existing db.json consulted for field-type facts
  quoted verbatim above, never modified)
Apple binary introspection: NONE. No otool -tv/-tV, objdump -d, Ghidra, lldb/gdb
  disassembly, class-dump, or radare2 was used on any Apple binary at any point.
  harness/fsrun.m is copied unchanged from experiments/EXP-0111-m4-fragment-semantics/
  harness/fsrun.m (our own prior committed code).
Reproduction: python3 -B verify.py --selftest; python3 -B run.py --run-id <new>;
  python3 -B analysis/analyze.py <run-id>
Evidence: raw/m4-20260828T000000Z-run01/{01_results,01_detail,01_timing}.jsonl,
  raw/m4-20260828T000100Z-run02/{...}, results_sha256 in each run's 02_dispatch.json
  (run01 f3047ffb8052a393…, run02 f0f44009fa07fc0b…), CAPTURE_CONTRACT.json's
  frozen_source_sha256 map
```
