# Part-II questionnaire coverage — every item, and what answers it

Source of truth for item ids: `grep -n '^- \*\*[A-Z0-9]*-[0-9]*' APPLE9_RE_IMPLEMENTATION_GAPS.md`.

**The questionnaire is 181 items, not 169.** Section sizes:
OPT 11 · PACK 11 · FP 14 · INT 14 · I64 6 · MEM 22 · TEX 28 · ATOM 11 · FS 12 · TRIG 10 ·
SFU 7 · ENC 16 · CF 6 · SIMD 7 · P2 6.

## Headline count (honest)

| bucket | count | share |
|---|---:|---:|
| **Answered by a committed experiment** (a verdict is on record — including verdicts that are explicitly `PARTIAL` / `UNKNOWN` / `NO`, which per `CODEX.md` are first-class answers) | **145** | 80.1% |
| Covered only by **desk audit** of prior work — no new evidence in the owning cluster (all 9 are `ENC-*`) | 9 | 5.0% |
| **UNANSWERED** — no committed `RESULTS.md` squarely addresses them | **27** | 14.9% |
| total | 181 | |

Of the 145 answered, roughly **114 are firm Yes/No** and **31 carry an explicit
`PARTIAL`/`UNKNOWN` disposition** recorded by the owning experiment. That split is my
classification of the source verdicts; the per-item rows below are authoritative.

Every answer is **M4/G16G only; A18 deferred**. No item anywhere in Part II has independent
A18/G17P validation.

Column key — **Block**: `IN-FILE` = an answer block is already present in
`APPLE9_RE_IMPLEMENTATION_GAPS.md`; `NEW` = a block is drafted in `work/GAPS-ANSWER-BLOCKS.md`
awaiting splice; `—` = no block (unanswered).

---

## OPT — NIR contract (11 items; 11 answered, 0 unanswered)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| OPT-01 | EXP-0121 | `1143ec55` | YES — two structurally distinct div sequences (66 vs 300 B) | NEW |
| OPT-02 | EXP-0074 | `ae63b41f` | NO — bit-exact except DAZ+FTZ (4171 cases) | IN-FILE |
| OPT-03 | EXP-0121 | `1143ec55` | YES — `pow` needs a fixup (22/53 naive-composition NaNs) | NEW |
| OPT-04 | EXP-0121 | `1143ec55` | PARTIAL / NO for "single instruction"; YES numerically | NEW |
| OPT-05 | EXP-0121 | `1143ec55` | YES — one fused `isel8`, arbitrary register operands | NEW |
| OPT-06 | EXP-0121 | `1143ec55` | YES — FP32/I32/U32 x 6 conditions, 825/825 | NEW |
| OPT-07 | EXP-0121 | `1143ec55` | NO (bounded structural negative); ALU-select is correct | NEW |
| OPT-08 | EXP-0121 | `1143ec55` | UNKNOWN/PARTIAL mechanism; positive-leaning structurally | NEW |
| OPT-09 | EXP-0091 | `4c2df727` | YES — demote semantics (`fwidth` reads exactly 999.0) | IN-FILE |
| OPT-10 | EXP-0121 | `1143ec55` | NO — plain fenced load does not see cross-thread writes | NEW |
| OPT-11 | EXP-0121 | `1143ec55` | YES — plain store + atomic load + fence is clean | NEW |

Joint: `has_atomic_load_store` must stay FALSE (needs both OPT-10 and OPT-11 `Yes`).

## PACK — packed conversion (11 items; 11 answered, 0 unanswered)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| PACK-01 | EXP-0102 | `958f8307` | YES — two native `cvt_f2h_dst`, no bitfield lowering | NEW |
| PACK-02 | EXP-0102 | `958f8307` | YES — two `falu2` convert-mode instances | NEW |
| PACK-03 | EXP-0102 | `958f8307` | YES — single `pack_convert`, same family as unorm | NEW |
| PACK-04 | EXP-0102 | `958f8307` | YES — 65536/65536 exhaustive bit-exact | NEW |
| PACK-05 | EXP-0102 | `958f8307` | YES — RTE ties, clamp-first, NaN→0 | NEW |
| PACK-06 | EXP-0102 | `958f8307` | YES — 65536/65536 exhaustive bit-exact | NEW |
| PACK-07 | EXP-0102 | `958f8307` | YES (normalized) / NO (generic integer 4x8) | NEW |
| PACK-08 | EXP-0102 | `958f8307` | YES — two `unpack_convert` instances | NEW |
| PACK-09 | EXP-0102 | `958f8307` | YES — 24/24 lane-correct exceptional values | NEW |
| PACK-10 | EXP-0102 | `958f8307` | YES — no cross-lane corruption, 24/24 | NEW |
| PACK-11 | EXP-0102 | `958f8307` | YES — no packed short2 integer ALU exists | NEW |

## FP — floating-point ALU (14 items; 14 answered, 0 unanswered)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| FP-01 | EXP-0103 | `bbb1e9fc` | YES (fused, 508/509); one uncharacterized subnormal edge | NEW |
| FP-02 | EXP-0103 | `bbb1e9fc` | YES — 2012/2012 exact (scalar) | NEW |
| FP-03 | EXP-0103 | `bbb1e9fc` | PARTIAL — 818/820; negate-vs-separate-op not disassembled | NEW |
| FP-04 | EXP-0103 | `bbb1e9fc` | CHARACTERIZED — both min and max return operand B on a tie | NEW |
| FP-05 | EXP-0103 | `bbb1e9fc` | YES — NaN-avoiding min/max | NEW |
| FP-06 | EXP-0103 | `bbb1e9fc` | NO — extensive DAZ+FTZ, incl. saturate and compare | NEW |
| FP-07 | EXP-0103 | `bbb1e9fc` | YES — per-instruction, not the global math flag | NEW |
| FP-08 | EXP-0103 | `bbb1e9fc` | YES — FP16 subnormals preserved, scalar and packed | NEW |
| FP-09 | EXP-0103 | `bbb1e9fc` | PARTIAL — NaN contract matches; subnormals DAZ | NEW |
| FP-10 | EXP-0103 | `bbb1e9fc` | YES — 1886/1886 RTE, no flush | NEW |
| FP-11 | EXP-0103 | `bbb1e9fc` | YES in range; out-of-range saturates; NaN→0 | NEW |
| FP-12 | EXP-0103 | `bbb1e9fc` | YES (upgraded) — FP32→int8 saturates natively | NEW |
| FP-13 | EXP-0103 | `bbb1e9fc` | YES — 1886/1886 exact | NEW |
| FP-14 | EXP-0103 | `bbb1e9fc` | YES (419/420); dedicated unordered-compare op unknown | NEW |

## INT — integer/bitfield/select (14 items; 14 answered, 0 unanswered)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| INT-01 | EXP-0102 | `958f8307` | YES — width 0 returns 0 | NEW |
| INT-02 | EXP-0102 | `958f8307` | **NO — three-way contract, not NIR's** (`cnt==32` bypass) | NEW |
| INT-03 | EXP-0102 | `958f8307` | YES — unsigned + explicit sign-extend, no hidden mode | NEW |
| INT-04 | EXP-0102 | `958f8307` | YES — mod-32, folded at compile time | NEW |
| INT-05 | EXP-0102 | `958f8307` | YES — mod-32 for all 64 runtime rows | NEW |
| INT-06 | EXP-0102 | `958f8307` | YES — no one-instruction dynamic rotate | NEW |
| INT-07 | EXP-0102 | `958f8307` | YES — exact mod 2^32, signed and unsigned | NEW |
| INT-08 | EXP-0102 | `958f8307` | **PARTIAL/UNKNOWN — probe could not force high registers** | NEW |
| INT-09 | EXP-0102 | `958f8307` | YES (DERIVED) — `ufind_msb`, not `_rev` | NEW |
| INT-10 | EXP-0102 | `958f8307` | YES — CLZ is compound (3 ops vs popcount's 1) | NEW |
| INT-11 | EXP-0102 | `958f8307` | YES — 3 `ibfins` + 2 helper ALU ops | NEW |
| INT-12 | EXP-0102 | `958f8307` | **PARTIAL/UNKNOWN — `ilogic` covers only 10 of 16** | NEW |
| INT-13 | EXP-0102 | `958f8307` | YES for every compiler-emitted instance | NEW |
| INT-14 | EXP-0102 | `958f8307` | **PARTIAL/UNKNOWN — deferred by design** | NEW |

## I64 — 64-bit integer (6 items; **0 answered, 6 UNANSWERED**)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| I64-01 | UNANSWERED | — | — | — |
| I64-02 | UNANSWERED | — | — | — |
| I64-03 | UNANSWERED | — | — | — |
| I64-04 | UNANSWERED | — | — | — |
| I64-05 | UNANSWERED | — | — | — |
| I64-06 | UNANSWERED | — | — | — |

**Related but NOT an answer:** EXP-0102 (`958f8307`) observed, under INT-13/INT-14, that a
source-level `u64` add compiles to `iadd2` → `carry_gen` → `psel` → high-word add in two
independent expression shapes. That bears on I64-01 but EXP-0102 never framed or scoped it as an
I64 answer, so no block is proposed. **This is the largest fully-untouched section and the
cheapest closure win available** — a single EXP would likely close all six.

## MEM — memory addressing and robustness (22 items; 20 answered, 2 UNANSWERED)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| MEM-01 | EXP-0082 | `311d3f3e` | PARTIAL YES — element scaling for codes 0/3/4 only | IN-FILE |
| MEM-02 | EXP-0082 | `311d3f3e` | NO — fixed 4 B (load) / 16 B (store) units | IN-FILE |
| MEM-03 | EXP-0082 | `311d3f3e` | UNSIGNED 11-bit, 0..2047, dense | IN-FILE |
| MEM-04 | EXP-0082 | `311d3f3e` | NO — no non-power-of-two stride form | IN-FILE |
| MEM-05 | EXP-0082 | `311d3f3e` | NO — mod-2^32 wrap refuted | IN-FILE |
| MEM-05 (refinement) | EXP-0122 | `f2b8ef66` | wrap period is **exactly 2^43** | NEW (under MEM-12) |
| MEM-06 | EXP-0076 | `446a5f28` | NO — unaligned loads do not return the requested bytes | IN-FILE |
| MEM-07 | EXP-0076 | `446a5f28` | YES | IN-FILE |
| MEM-08 | EXP-0076 | `446a5f28` | YES (near-boundary) | IN-FILE |
| MEM-08 (refinement) | EXP-0122 | `f2b8ef66` | **"OOB reads zero" is NOT page-wide** — live data at 16384 B | NEW (under MEM-12) |
| MEM-09 | EXP-0076 | `446a5f28` | NO — mix model refuted | IN-FILE |
| MEM-10 | EXP-0076 | `446a5f28` | YES — silent discard | IN-FILE |
| MEM-11 | EXP-0076 | `446a5f28` | PARTIAL — mechanism not identifiable through public Metal | IN-FILE |
| MEM-12 | EXP-0076 + EXP-0122 | `446a5f28`, `f2b8ef66` | constraint recorded; must bounds-check, cannot lean on OOB-zero | IN-FILE + NEW |
| MEM-13 | EXP-0085 | `2e693a58` | YES — HW-VALIDATED interlock (48-deep chains, N=65536) | NEW |
| MEM-14 | EXP-0085 | `2e693a58` | YES — interlock is bidirectional | NEW |
| MEM-15 | EXP-0083 | `8d47a271` | PARTIAL — 31 usable slots, a binding-population edge not a ceiling | IN-FILE |
| MEM-16 | EXP-0083 | `8d47a271` | YES for 1..30; selector is effectively 7-bit | IN-FILE |
| MEM-17 | EXP-0083 | `8d47a271` | zero / mirror, never a fault | IN-FILE |
| MEM-18 | UNANSWERED | — | flagged open by EXP-0083 and EXP-0084 | — |
| MEM-19 | UNANSWERED | — | flagged open by EXP-0083 | — |
| MEM-20 | EXP-0084 | `783fe693` | YES — dynamic 64-bit addressing works, 4 constructions | IN-FILE |
| MEM-21 | EXP-0084 | `783fe693` | YES — per-lane divergent selection is real | IN-FILE |
| MEM-22 | EXP-0084 | `783fe693` | ceiling 31, dynamic path validated to N=256 | IN-FILE |

## TEX — texture ops, selectors, limits (28 items; 21 answered, 7 UNANSWERED/DEFERRED)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| TEX-01 | UNANSWERED (DEFERRED) | — | needs `op+2` opcode-space fuzzing; no MSL entry point | — |
| TEX-02 | EXP-0106 | `2858c20f` | NO compiler-reachable 4-offset gather; keep `lower_tg4_offsets` | NEW |
| TEX-03 | EXP-0106 | `2858c20f` | YES at 12 boundary/corner points, injective; NOT all 256 | NEW |
| TEX-04 | EXP-0106 | `2858c20f` | YES — dynamic, per-lane-divergent offset is native | NEW |
| TEX-05 | EXP-0106 | `2858c20f` | **NEGATIVE — 3 of 4 forms crash the compiler service** | NEW |
| TEX-06 | EXP-0106 | `2858c20f` | YES — per-lane bindless queries resolve correctly | NEW |
| TEX-07 | EXP-0106 | `2858c20f` | NO — no `samples_identical` primitive in MSL | NEW |
| TEX-08 | EXP-0106 | `2858c20f` | NO — no prefetch primitive in MSL | NEW |
| TEX-09 | EXP-0106 (cite EXP-0095) | `2858c20f` | YES — no R32G32B32 format at all | NEW |
| TEX-10 | EXP-0106 | `2858c20f` | NO for general YCbCr; packed 4:2:2 is native | NEW |
| TEX-11 | EXP-0106 (cite EXP-0015/M4-08) | `2858c20f` | YES — 3 presets only; emulation argued analytically | NEW |
| TEX-12 | UNANSWERED (DEFERRED) | — | needs `MTLHeap` sparse + `updateTextureMapping:` lifecycle | — |
| TEX-13 | EXP-0106 | `2858c20f` | PARTIAL — 3D depth axis new; MSAA sample-index OOB not exercised | NEW |
| TEX-14 | EXP-0106 | `2858c20f` | YES — 65 slots, every named boundary pair distinguishable | NEW |
| TEX-15 | EXP-0114 | `72c2dde8` | **premise falsified** — `op+4` is a 4-bit reused slot ref, not a selector | NEW |
| TEX-16 | EXP-0106 + EXP-0114 | `2858c20f`, `72c2dde8` | YES — compile-time rejection; raw injection = silent zero x14 | NEW |
| TEX-17 | EXP-0106 | `2858c20f` | YES — all 16 samplers live, zero cross-talk | NEW |
| TEX-18 | EXP-0106 | `2858c20f` | YES — named compile-time rejection at n=17 | NEW |
| TEX-19 | UNANSWERED (DEFERRED) | — | shape known at CAP=256 (EXP-0095); ceiling sweep not run | — |
| TEX-20 | UNANSWERED (DEFERRED) | — | same family as TEX-19 | — |
| TEX-21 | UNANSWERED (DEFERRED) | — | prior evidence is **A18** (EXP-O2B), not M4-validated | — |
| TEX-22 | UNANSWERED (DEFERRED) | — | EXP-O2B named the gap; never executed | — |
| TEX-23 | EXP-0106 | `2858c20f` | YES — per-axis limits exact, hard assertion at +1 | NEW |
| TEX-24 | EXP-0106 | `2858c20f` | YES — 15 levels; `level(NaN)` clamps LOW (new 3rd data point) | NEW |
| TEX-25 | EXP-0106 | `2858c20f` | creatable MSAA set is **{2,4}**, not {1,2,4}; query/creation mismatch | NEW |
| TEX-26 | EXP-0106 (cite EXP-M4-08) | `2858c20f` | PARTIAL — API half closed (32x clamps to **1x**); raw field untested | NEW |
| TEX-27 | EXP-0106 (cite EXP-M4-08) | `2858c20f` | PARTIAL — saturates at 112 (14.0); raw >112 untested | NEW |
| TEX-28 | UNANSWERED (DEFERRED) | — | codes 4/6/7 + border 3 untested; new MSL-4.0 sampler `bias` target | — |

## ATOM — atomics and synchronization (11 items; 11 answered, 0 unanswered)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| ATOM-01 | EXP-0085 | `2e693a58` | YES — own selector `0x1b`, distinct from add's `0x10` | NEW |
| ATOM-02 | EXP-0085 | `2e693a58` | YES — `atomic_tg` form, same selector encoding | NEW |
| ATOM-03 | EXP-0085 | `2e693a58` | YES — pre-op value, two independent invariant forms | NEW |
| ATOM-04 | EXP-0085 | `2e693a58` | YES — single native transaction, no retry loop | NEW |
| ATOM-05 | EXP-0085 | `2e693a58` | YES, boundary sharpened: only compile-time-provable uniformity | NEW |
| ATOM-06 | EXP-0085 | `2e693a58` | YES — disabled for exchange/cmpxchg | NEW |
| ATOM-07 | EXP-0093 | `d3e7d1ba` | YES — up to 100% corruption at PAIRS>=4; no implicit fence | NEW |
| ATOM-08 | EXP-0093 | `d3e7d1ba` | YES **only symmetric**; asymmetric fencing is unsafe | NEW |
| ATOM-09 | EXP-0093 | `d3e7d1ba` | YES — convergence is unconditional, not gated by memory class | NEW |
| ATOM-10 | EXP-0093 | `d3e7d1ba` | YES — `byte+3` bit0, bidirectional splice | NEW |
| ATOM-11 | EXP-0093 | `d3e7d1ba` | **NO** — distinct image/texture barrier path required | NEW |

## FS — fragment execution (12 items; 12 answered, 0 unanswered)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| FS-01 | EXP-0111 | `9739d612` | YES — HW splice, mutual `0xa0`/`0xa1` swap | NEW |
| FS-02 | EXP-0111 | `9739d612` | YES — stable across samples and original helpers | NEW |
| FS-03 | EXP-0111 | `9739d612` | PARTIAL — centre/origin closed; sample positions UNKNOWN | NEW |
| FS-04 | EXP-0111 | `9739d612` | YES — quad-local, blind to inter-quad steps | NEW |
| FS-05 | EXP-0111 | `9739d612` | NO at API surface; ISA-level coarse mode UNKNOWN | NEW |
| FS-06 | EXP-0111 | `9739d612` | YES for demoted and original helpers | NEW |
| FS-07 | EXP-0111 | `9739d612` | YES (`scalarize_ddx`); **`0x90`/`0x92` axis-byte anomaly unresolved** | NEW |
| FS-08 | EXP-0111 | `9739d612` | PARTIAL — **`interpolate_at_offset` violates its contract** | NEW |
| FS-09 | EXP-0111 | `9739d612` | YES — convergent is not foldable to flat (3 of 5 configs diverge) | NEW |
| FS-10 | EXP-0111 | `9739d612` | YES — materialize-all-then-select, 4/4 exact | NEW |
| FS-11 | EXP-0111 | `9739d612` | YES both sub-claims; single-store ISA mechanism UNKNOWN | NEW |
| FS-12 | EXP-0111 | `9739d612` | YES for 5 channels; **stencil INFERRED, not validated** | NEW |

## TRIG — transcendental (10 items; 8 answered, 2 UNANSWERED)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| TRIG-01 | UNANSWERED (DEFERRED) | — | needs field-level splice; `db.json` internals stay INFERRED | — |
| TRIG-02 | UNANSWERED (DEFERRED) | — | same | — |
| TRIG-03 | EXP-0103 | `bbb1e9fc` | PARTIAL — structural (198 vs 238 B), not field-level | NEW |
| TRIG-04 | EXP-0103 | `bbb1e9fc` | PARTIAL — same evidence | NEW |
| TRIG-05 | EXP-0103 | `bbb1e9fc` | precise <=2 ULP to FLT_MAX; fast cliff at (6587824, 6588825] | NEW |
| TRIG-06 | EXP-0103 | `bbb1e9fc` | YES for `fast::` only — total failure above the cliff | NEW |
| TRIG-07 | EXP-0103 | `bbb1e9fc` | PARTIAL — accuracy yes; coefficients deliberately NOT extracted | NEW |
| TRIG-08 | EXP-0103 | `bbb1e9fc` | YES — `fast::sin(NaN)=+0`, `precise::` propagates qNaN | NEW |
| TRIG-09 | EXP-0103 | `bbb1e9fc` | PARTIAL — max_ulp 0 for finite FP16; mechanism unverified | NEW |
| TRIG-10 | EXP-0103 | `bbb1e9fc` | **NO — updates EXP-0026's A18 "byte-identical" claim** | NEW |

## SFU — special functions (7 items; 6 answered, 1 UNANSWERED)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| SFU-01 | EXP-0103 | `bbb1e9fc` | YES — all nine independently selectable | NEW |
| SFU-02 | EXP-0103 | `bbb1e9fc` | YES — special block itemized per function | NEW |
| SFU-03 | EXP-0103 | `bbb1e9fc` | PARTIAL — output determinism proven; seed register not read back | NEW |
| SFU-04 | UNANSWERED (DEFERRED) | — | EXP-0026's A18 answer is an inferred argument, not a count | — |
| SFU-05 | EXP-0103 | `bbb1e9fc` | YES (upgraded) — 228/1884 differ from `x*rsqrt(x)` | NEW |
| SFU-06 | EXP-0103 | `bbb1e9fc` | YES (upgraded) — 170/820 differ by exactly 1 ULP | NEW |
| SFU-07 | EXP-0103 | `bbb1e9fc` | **NO** — exp2 <=1 ULP, log2 <=2 ULP, never correctly rounded | NEW |

Cross-cutting SFU findings carried in the block: `rcp`/`rsqrt`/`sqrt` share division's DAZ+FTZ
model exactly (184/184 divergences predicted, zero residual); `exp2`/`log2` have **no refined
path at all** (fast and precise are byte-identical output AND byte-identical 46-byte code);
FP16 SFU neither DAZs nor FTZs across all 65536 patterns.

## ENC — registers, immediates, encoding (16 items; 4 with new evidence, 9 desk-audit, 3 UNANSWERED)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| ENC-01 | EXP-0105 (DESK-AUDIT) | `79ab3da9` | PARTIAL — several families still `db.json`-inferred | NEW |
| ENC-02 | EXP-0105, **superseded by EXP-0112** | `79ab3da9`, `d5d8fbee` | **REFUTED for r64-95**; EXP-0112: aliases to `r(R mod 64)` in [64,112], faults at {126,127} | NEW |
| ENC-03 | UNANSWERED | — | not probed | — |
| ENC-04 | EXP-0105 (DESK-AUDIT) | `79ab3da9` | PARTIAL — float covered; integer ALU still inferred | NEW |
| ENC-05 | EXP-0105 (DESK-AUDIT) | `79ab3da9` | PARTIAL — **NaN-literal handling is an undocumented gap** | NEW |
| ENC-06 | EXP-0105 | `79ab3da9` | PARTIAL, extended — 5 of 7 new bits corrupt, 2 inert | NEW |
| ENC-07 | EXP-0105 | `79ab3da9` | PARTIAL — general answer **NO**, reserved bits not safely known | NEW |
| ENC-08 | EXP-0105 (DESK-AUDIT) | `79ab3da9` | PARTIAL — ~87-91% tokenization | NEW |
| ENC-09 | EXP-0105 (DESK-AUDIT) | `79ab3da9` | PARTIAL — own 16 cases round-trip | NEW |
| ENC-10 | EXP-0105, offset by EXP-0112 | `79ab3da9`, `d5d8fbee` | OPEN — `iminmax` abandoned; EXP-0112 ran 140/140 generated programs | NEW |
| ENC-11 | EXP-0105 (DESK-AUDIT) | `79ab3da9` | PARTIAL — compute closed, other stages not | NEW |
| ENC-12 | EXP-0105 (DESK-AUDIT) | `79ab3da9` | PARTIAL | NEW |
| ENC-13 | EXP-0105 (DESK-AUDIT) | `79ab3da9` | PARTIAL — substantially closed for tested depth | NEW |
| ENC-14 | EXP-0105 (DESK-AUDIT) | `79ab3da9` | PARTIAL — compute doubly closed | NEW |
| ENC-15 | UNANSWERED | — | `docs/isa/README.md`'s own disclosed gap | — |
| ENC-16 | UNANSWERED | — | disclosed gap; sibling workstream EXP-0107 | — |

Retractions carried in the ENC block: **EXP-0101 (`2cf96b56`) refutes EXP-M4-13's `dst` formula**
(the rule is `extmode = 2 * target_register`, and `dst_lo`/`dst_ext9` must be copied verbatim);
**EXP-0099 (`de4e4a81`) refutes BOTH bit-15/31 lifetime models** (the top bit is inert for both
addressing and retention), retracted from `docs/isa` in `88fa4953`.

## CF — control flow (6 items; 6 answered, 0 unanswered)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| CF-01 | EXP-0104 | `574ee96f` | YES + correction: two lowerings keyed to early-exit presence | NEW |
| CF-02 | EXP-0104 | `574ee96f` | YES — no hidden loop-exit helper | NEW |
| CF-03 | EXP-0104 + EXP-0115 | `574ee96f`, `fec9315a` | PARTIAL — 254/255/255 is the **Clang** wall, not silicon | NEW |
| CF-04 | EXP-0104 | `574ee96f` | YES — mask push/pop, never the `0x8f` call opcode | NEW |
| CF-05 | EXP-0104 + EXP-0115 | `574ee96f`, `fec9315a` | **NO** — and `if_push_pred.pred` is completely inert | NEW |
| CF-06 | EXP-0104 + EXP-0115 | `574ee96f`, `fec9315a` | YES — "there is nothing to allocate" | NEW |

Also carried (not a numbered item): the branch-reach map — zero forward slack, one backward alias
hole at −2, a fault/hang/silent-zero **checkerboard** past the code extent, and **13/162 points
genuinely non-deterministic run to run**.

## SIMD — subgroups and quads (7 items; 7 answered, 0 unanswered)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| SIMD-01 | EXP-0104 + EXP-0115 | `574ee96f`, `fec9315a` | YES — 32 constant; fragment sweep closed (12 sizes, 10784 pixels) | NEW |
| SIMD-02 | EXP-0104 | `574ee96f` | YES — bit i = lane i, stable and group-visible | NEW |
| SIMD-03 | EXP-0104 + EXP-0115 | `574ee96f`, `fec9315a` | defined but **3 different OOB modes**; static ≠ dynamic for `simd_shuffle` | NEW |
| SIMD-04 | EXP-0104 | `574ee96f` | YES — scans/reductions correct under divergence | NEW |
| SIMD-05 | EXP-0104 | `574ee96f` | YES — xor 1/2/3 = horizontal/vertical/diagonal, row-major quads | NEW |
| SIMD-06 | EXP-0104, **narrowed by EXP-0115** | `574ee96f`, `fec9315a` | **NOT universally a no-op** — breaks under divergent call patterns | NEW |
| SIMD-07 | EXP-0104 + EXP-0115 | `574ee96f`, `fec9315a` | PARTIAL — helper lanes are INCLUDED (refutation); popcount +8 UNKNOWN | NEW |

## P2 — deferred tail (6 items; **0 answered, 6 UNANSWERED**)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| P2-01 | UNANSWERED | — | — | — |
| P2-02 | UNANSWERED | — | — | — |
| P2-03 | UNANSWERED | — | — | — |
| P2-04 | UNANSWERED | — | — | — |
| P2-05 | UNANSWERED | — | — | — |
| P2-06 | UNANSWERED | — | — | — |

**Related but NOT answers:** EXP-0022 (simdgroup matrix), EXP-0023 (ray tracing), EXP-0030 and
EXP-0135 (mesh/object shading) all touch this territory, but none frames a result against a
`P2-*` id, so none is claimed here. A desk pass mapping those RESULTS onto P2-01..06 is a cheap
follow-up that may close several without new hardware work.

---

## The 27 genuinely unanswered items, grouped by what would close them

| group | items | what is actually needed |
|---|---|---|
| **64-bit integer** | I64-01..06 (6) | one experiment; EXP-0102 already has adjacent observations to build on |
| **P2 tail** | P2-01..06 (6) | likely a desk pass over EXP-0022/0023/0030/0135 first, then targeted probes |
| **Bindless capacity ceilings** | TEX-19, TEX-20, TEX-21, TEX-22 (4) | large allocation-and-sweep campaigns reusing EXP-0095 GLIMG-A02 / EXP-O2B methodology, on M4 (the sampler-side prior evidence is A18) |
| **Raw sampler/texture descriptor injection** | TEX-26/27 raw halves, TEX-28 (1 fully; 2 partial) | write-capable descriptor injection via the direct `[[sampler(n)]]` per-stage table; successor spec already written in EXP-0106 §2 |
| **ISA opcode-space fuzzing** | TEX-01, TRIG-01, TRIG-02 (3) | field-level splice on `op+2` / the trig primitive / the `0x2b` op |
| **Encoding gaps** | ENC-03, ENC-15, ENC-16 (3) | ENC-16's sibling workstream is EXP-0107; ENC-15 is a disclosed `docs/isa` gap |
| **Base-slot population path** | MEM-18, MEM-19 (2) | the USC constant/uniform-program path EXP-0083 explicitly deferred |
| **Sparse residency** | TEX-12 (1) | `MTLHeap` + `updateTextureMapping:` lifecycle harness |
| **SFU iteration count** | SFU-04 (1) | blocked by clean-room rule 5 as posed; needs reframing, not just effort |

## Health notes a reader should not miss

- **Every Part-II answer is M4/G16G.** Not one item has independent A18/G17P validation. Two
  items lean on A18-era prior work explicitly flagged as such: TEX-21/22 (EXP-O2B) and the
  TEX-26/27 API halves (EXP-M4-08, which was M4+A18 cross-confirmed).
- **Three retractions must survive any edit to the task list:** EXP-0112 over EXP-0105 on r64-95
  (aliasing, not silent zero); EXP-0101 over EXP-M4-13's `dst` formula; EXP-0099 over both
  bit-15/31 lifetime models (retracted from `docs/isa` in `88fa4953`).
- **Two answers contradict their own documentation and are the most driver-relevant findings
  here:** `interpolate_at_offset` (FS-08) does not implement its documented center-relative
  contract, and `extract_bits` (INT-02) has a three-way contract that is not NIR's.
- **One answer is a live software-stack hazard:** `min_lod_clamp()` (TEX-05) crashes the
  `AGXMetalG16G` compiler service for 3 of its 4 compute-stage forms on this macOS/Metal build.
