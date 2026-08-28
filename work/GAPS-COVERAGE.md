# Part-II questionnaire coverage — every item, and what answers it

Source of truth for item ids: `grep -n '^- \*\*[A-Z0-9]*-[0-9]*' APPLE9_RE_IMPLEMENTATION_GAPS.md`.

**The questionnaire is 181 items, not 169.** Section sizes:
OPT 11 · PACK 11 · FP 14 · INT 14 · I64 6 · MEM 22 · TEX 28 · ATOM 11 · FS 12 · TRIG 10 ·
SFU 7 · ENC 16 · CF 6 · SIMD 7 · P2 6.

## Headline count (honest)

**Updated 2026-08-28 (wave-2 desk pass, `work/GAPS-ANSWER-BLOCKS-2.md`).** The numbers below
supersede the first version of this table. Two changes drive them: `I64-01..06` was closed by
EXP-0146 after this table was first written, and a desk pass over the committed corpus produced
verdicts for 14 more of the previously-UNANSWERED items.

| bucket | count | share |
|---|---:|---:|
| **Answered by a committed experiment** (a verdict is on record — including verdicts that are explicitly `PARTIAL` / `UNKNOWN` / `NO`, which per `CODEX.md` are first-class answers) | **157** | 86.7% |
| Covered only by **desk audit** of prior work — the question asks "is X fully validated / completely known?" and the answer is a checkable statement about the evidence record, not a new hardware fact | 17 | 9.4% |
| **Confirmed blocked by a clean-room rule as posed** — needs a scope decision, not evidence (SFU-04 only) | 1 | 0.6% |
| **UNANSWERED** — no committed `RESULTS.md` squarely addresses them, and none can be answered from the record | **6** | 3.3% |
| total | 181 | |

Previous version of this table: 145 answered / 9 desk-audit / 27 unanswered.

Of the 157 answered, roughly **121 are firm Yes/No** and **36 carry an explicit
`PARTIAL`/`UNKNOWN` disposition** recorded by the owning experiment or by the wave-2 pass. That
split is my classification of the source verdicts; the per-item rows below are authoritative.

Per-section reconciliation of the four buckets (sums to 181): answered = OPT 11 + PACK 11 + FP 14
+ INT 14 + I64 6 + MEM 20 + TEX 24 + ATOM 11 + FS 12 + TRIG 8 + SFU 6 + ENC 4 + CF 6 + SIMD 7 +
P2 3 = **157**; desk-audit = MEM 1 + TRIG 2 + ENC 12 + P2 2 = **17**; blocked-by-rule = SFU 1 =
**1**; unanswered = MEM 1 + TEX 4 + P2 1 = **6**.

**Five of the wave-2 verdicts (across both the answered and desk-audit buckets) are `PARTIAL`
with a named open half that still needs hardware**
(P2-01 bf16 emittability, TEX-12 residency code + filtered/gathered forms, TEX-20 the >=1,000,000
and nonresident cases, TEX-28 the filter sub-field, MEM-18 the exact table-to-preload mapping).
Counting them as "answered" follows `CODEX.md` §7 — a recorded PARTIAL with a stated tested range
IS the answer — but a reader planning work should treat them as half-open.

Every answer is **M4/G16G only; A18 deferred**, except where a row says otherwise. Several
wave-2 answers rest partly on A18-era evidence and say so inline: P2-01 (the one executed bf16
splice, EXP-O2D), P2-03 (the matrix operand selectors, EXP-0022/EXP-O2C), P2-05 (both executed
RT results), ENC-16 (the `frame_prologue`/`link_save_restore` sweeps, EXP-M4-14), TEX-21/22
(EXP-O2B). No item anywhere in Part II has independent A18/G17P validation of a *wave-2* claim.

Column key — **Block**: `IN-FILE` = an answer block is already present in
`APPLE9_RE_IMPLEMENTATION_GAPS.md`; `NEW` = a block is drafted in `work/GAPS-ANSWER-BLOCKS.md`
awaiting splice; **`NEW-2` = a block is drafted in `work/GAPS-ANSWER-BLOCKS-2.md` awaiting
splice** (wave 2, 2026-08-28); `—` = no block (unanswered).

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

## I64 — 64-bit integer (6 items; **6 answered, 0 unanswered — CLOSED**)

**CLOSED by EXP-0146 (`f36b2ac4`), which postdates the first version of this table.** A
splice-ready answer block already exists at
`experiments/EXP-0146-m4-emit-int-misc/analysis/I64_answers.md` (anchor verified unique). Two
gated capture runs (18 786 records each) plus a 5x-serial adjudication pass and a targeted
second-method pass; **0 unresolved cases**.

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| I64-01 | EXP-0146 | `f36b2ac4` | **YES — a NATIVE single-instruction 64-bit ADD exists and Apple's compiler never emits it** (splice `iadd2` byte0 `0x1f`->`0x9f`); supersedes the EXP-0102/EXP-0038 reading that 64-bit add is necessarily a carry chain | EXP-0146 `analysis/I64_answers.md` |
| I64-02 | EXP-0146 | `f36b2ac4` | YES — one register-pair instruction does the complete 64-bit subtract incl. borrow | same |
| I64-03 | EXP-0146 | `f36b2ac4` | **PARTIAL / mostly UNKNOWN** — fault boundaries established; alternative pair placements NOT tested. "Do not assume unaligned pairs work." | same |
| I64-04 | EXP-0146 | `f36b2ac4` | YES — 32x32->64 is a single `imad`; signed/unsigned differ in exactly one byte (`imad` byte+10 `0x0a`/`0x1e`) | same |
| I64-05 | EXP-0146 | `f36b2ac4` | YES (no native 64x64->low64 multiply) — three `imad` instances, 86 B | same |
| I64-06 | EXP-0146 | `f36b2ac4` | YES — every 64-bit compare/shift/minmax/bitscan/select is compound; only sub (and optionally add) are not | same |

Joint: `lower_int64_options` must keep every compare/shift/minmax/bitscan/select bit set, and
may clear the add and sub bits.

## MEM — memory addressing and robustness (22 items; 20 answered + 1 desk-audit, 1 UNANSWERED)

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
| MEM-18 | **desk audit** (EXP-0010/0020/0083/0141/EXP-G1a) | `8d47a271`, — | **PARTIAL — leaning "intermediate base-register/preload file"**: base_slot is a preloaded uniform-file slot, its content is program-dependent (constant-program hoisting), selector effectively 7-bit with 128..255 mirroring 0..127. The exact table-to-preload mapping the item demands does NOT exist. | NEW-2 |
| MEM-19 | UNANSWERED | — | flagged open by EXP-0083; never probed. Needs a USC uniform-program probe driving the declared preload count past capacity | — |
| MEM-20 | EXP-0084 | `783fe693` | YES — dynamic 64-bit addressing works, 4 constructions | IN-FILE |
| MEM-21 | EXP-0084 | `783fe693` | YES — per-lane divergent selection is real | IN-FILE |
| MEM-22 | EXP-0084 | `783fe693` | ceiling 31, dynamic path validated to N=256 | IN-FILE |

## TEX — texture ops, selectors, limits (28 items; 24 answered, 4 UNANSWERED/DEFERRED)

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
| TEX-12 | EXP-0122 | `f2b8ef66` | **PARTIAL** — unmapped+fetched CLOSED (fault-free, reads zero, 4 configs x 3-5 coords, `every_case_all_zero`); mapped is a confirmed NEGATIVE (a write into a demonstrably-mapped tile does not persist on the `MTLHeapTypeSparse` path); residency code + filtered/gathered forms UNTESTED | NEW-2 |
| TEX-13 | EXP-0106 | `2858c20f` | PARTIAL — 3D depth axis new; MSAA sample-index OOB not exercised | NEW |
| TEX-14 | EXP-0106 | `2858c20f` | YES — 65 slots, every named boundary pair distinguishable | NEW |
| TEX-15 | EXP-0114 | `72c2dde8` | **premise falsified** — `op+4` is a 4-bit reused slot ref, not a selector | NEW |
| TEX-16 | EXP-0106 + EXP-0114 | `2858c20f`, `72c2dde8` | YES — compile-time rejection; raw injection = silent zero x14 | NEW |
| TEX-17 | EXP-0106 | `2858c20f` | YES — all 16 samplers live, zero cross-talk | NEW |
| TEX-18 | EXP-0106 | `2858c20f` | YES — named compile-time rejection at n=17 | NEW |
| TEX-19 | UNANSWERED (DEFERRED) | — | shape known at CAP=256/K=8 (EXP-0095, feasibility to N=4096); per-lane non-uniform half supported at 4 entries by EXP-0106 TEX-06; ceiling sweep not run | — |
| TEX-20 | EXP-0095 (unpopulated half); EXP-0106 defers the rest | `2858c20f` | **PARTIAL** — unpopulated/OOB entry: silent zero on load, silently dropped with NO aliasing on store/atomic, at `CAP=256`/`K=8`. `>=1,000,000` and nonresident remain DEFERRED | NEW-2 |
| TEX-21 | UNANSWERED (DEFERRED) | — | prior evidence is **A18** (EXP-O2B), not M4-validated | — |
| TEX-22 | UNANSWERED (DEFERRED) | — | EXP-O2B named the gap; never executed | — |
| TEX-23 | EXP-0106 | `2858c20f` | YES — per-axis limits exact, hard assertion at +1 | NEW |
| TEX-24 | EXP-0106 | `2858c20f` | YES — 15 levels; `level(NaN)` clamps LOW (new 3rd data point) | NEW |
| TEX-25 | EXP-0106 | `2858c20f` | creatable MSAA set is **{2,4}**, not {1,2,4}; query/creation mismatch | NEW |
| TEX-26 | EXP-0106 + **EXP-0136** | `2858c20f`, `2e2bc21a` | **UPGRADED to full: NO, aniso is not limited to 16x** — patched codes 5/6/7 (32/64/128x) resolve with a measured, threshold-exact quality effect; Metal's 16x cap has zero hardware backing. API half unchanged (32x clamps to **1x**) | NEW + NEW-2 |
| TEX-27 | EXP-0106 (cite EXP-M4-08) | `2858c20f` | PARTIAL — saturates at 112 (14.0); raw >112 untested | NEW |
| TEX-28 | EXP-0136 | `2e2bc21a` | **PARTIAL** — address codes 4/6/7 = exact aliases (4->0, 6/7->3); border code 3 = exact alias to preset 0 (3 creation contexts); swizzle 6/7 = deterministic invalid, **hard CMDBUF_ERROR fault**. **Filter sub-field UNTESTED** (mipFilter code 3, descriptor bits 24/26, MSL-4.0 sampler `bias` state field) | NEW-2 |

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

## TRIG — transcendental (10 items; 8 answered + 2 desk-audit, 0 UNANSWERED)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| TRIG-01 | **desk audit** (`validation.json` + EXP-0103) | `bbb1e9fc` | **NO** — not one operand/modifier field of the `0x2b` family is `hardware-run`: `tex_coord_setup` 7 of 10 fields `untested`, rest `corpus-correlation`; `sfu_marker` `tokenization-only` ("exact micro-op NOT characterized") | NEW-2 (joint block) |
| TRIG-02 | **desk audit** (`validation.json` + EXP-0103) | `bbb1e9fc` | **NO** — same evidence; EXP-0103's own Limitations says TRIG-01/02 "were not attempted" and nothing since has attempted them | NEW-2 (joint block, anchored on TRIG-01) |
| TRIG-03 | EXP-0103 | `bbb1e9fc` | PARTIAL — structural (198 vs 238 B), not field-level | NEW |
| TRIG-04 | EXP-0103 | `bbb1e9fc` | PARTIAL — same evidence | NEW |
| TRIG-05 | EXP-0103 | `bbb1e9fc` | precise <=2 ULP to FLT_MAX; fast cliff at (6587824, 6588825] | NEW |
| TRIG-06 | EXP-0103 | `bbb1e9fc` | YES for `fast::` only — total failure above the cliff | NEW |
| TRIG-07 | EXP-0103 | `bbb1e9fc` | PARTIAL — accuracy yes; coefficients deliberately NOT extracted | NEW |
| TRIG-08 | EXP-0103 | `bbb1e9fc` | YES — `fast::sin(NaN)=+0`, `precise::` propagates qNaN | NEW |
| TRIG-09 | EXP-0103 | `bbb1e9fc` | PARTIAL — max_ulp 0 for finite FP16; mechanism unverified | NEW |
| TRIG-10 | EXP-0103 | `bbb1e9fc` | **NO — updates EXP-0026's A18 "byte-identical" claim** | NEW |

## SFU — special functions (7 items; 6 answered, 1 BLOCKED by clean-room rule 5, 0 UNANSWERED)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| SFU-01 | EXP-0103 | `bbb1e9fc` | YES — all nine independently selectable | NEW |
| SFU-02 | EXP-0103 | `bbb1e9fc` | YES — special block itemized per function | NEW |
| SFU-03 | EXP-0103 | `bbb1e9fc` | PARTIAL — output determinism proven; seed register not read back | NEW |
| SFU-04 | **BLOCKED BY CLEAN-ROOM RULE 5** (confirmed) | `bbb1e9fc` | Counting iterations in Apple's compiler-generated sequence is forbidden by `CLAUDE.md` rule 5; EXP-0103 pre-registered it `DEFERRED` for exactly this reason. **Needs a scope decision, not evidence.** Substitute hardware facts recorded: seed ~7.5-8 mantissa bits (EXP-0026, A18) + `precise::rcp` 0 ULP, 1856/1886 exact (EXP-0103, M4) | NEW-2 |
| SFU-05 | EXP-0103 | `bbb1e9fc` | YES (upgraded) — 228/1884 differ from `x*rsqrt(x)` | NEW |
| SFU-06 | EXP-0103 | `bbb1e9fc` | YES (upgraded) — 170/820 differ by exactly 1 ULP | NEW |
| SFU-07 | EXP-0103 | `bbb1e9fc` | **NO** — exp2 <=1 ULP, log2 <=2 ULP, never correctly rounded | NEW |

Cross-cutting SFU findings carried in the block: `rcp`/`rsqrt`/`sqrt` share division's DAZ+FTZ
model exactly (184/184 divergences predicted, zero residual); `exp2`/`log2` have **no refined
path at all** (fast and precise are byte-identical output AND byte-identical 46-byte code);
FP16 SFU neither DAZs nor FTZs across all 65536 patterns.

## ENC — registers, immediates, encoding (16 items; 4 with new evidence, 12 desk-audit, 0 UNANSWERED)

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| ENC-01 | EXP-0105 (DESK-AUDIT) | `79ab3da9` | PARTIAL — several families still `db.json`-inferred | NEW |
| ENC-02 | EXP-0105, **superseded by EXP-0112** | `79ab3da9`, `d5d8fbee` | **REFUTED for r64-95**; EXP-0112: aliases to `r(R mod 64)` in [64,112], faults at {126,127} | NEW |
| ENC-03 | **desk audit** (EXP-0020/0141/0146/0113) | `f36b2ac4`, — | **NO** — known for FP16 (halves 2/GPR; `0x09` size bit reaches only the low half) and for FP32 GPR indexing *per instruction form* (falu2 dst 4-bit r0-r15, falu3 7-bit, device_load dst R in 0..63, index_reg r96..r127 FAULT); **NOT known for I64 pair placement** ("Do not assume unaligned pairs work" — EXP-0146); **untouched for vectors** | NEW-2 |
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
| ENC-15 | **desk audit** (EXP-0020/0024, corrected EXP-M4-09/CMD-8) | — | **NO** — only the compute CDM config bit23 is decoded, as a 2-tier boolean whose "<=11/>=12 GPR" threshold is recorded **FALSE** (f0=8 appears on both sides; lowest SET at f0=5); it tracks a compiler-computed occupancy property (`__GPU_METADATA` field-32) 1:1. No vertex/fragment mapping exists; Dynamic Caching + the halfregs->max-threads curve are NOT-YET-CHARACTERIZED | NEW-2 |
| ENC-16 | **desk audit** (EXP-0107/0125/M4-14/0041) | — | **NO** — `frame_prologue.frame_size` is 16-byte granular, over-allocation tolerated, **not cleanly monotonic (`0x40` faults while `0x30` runs) so the sub-field layout is unresolved**; `spill_frame_marker`'s role UNRESOLVED and absent from all nine M4 mains; scratch addressing not located at any lifecycle point. **New and exact:** stage-uniform ceiling, last success K=65,431 (261,740 B) / first failure K=65,432 (261,744 B) | NEW-2 |

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

## P2 — deferred tail (6 items; **3 answered + 2 desk-audit, 1 UNANSWERED**)

**Numbering warning.** Part-II `P2-01..06` are **not** the Part-I `DRV-P2-01..05` rows.
Part-II `P2-*` is BF16 / cooperative-matrix / mesh-stage-ISA / ray-query / FP64. EXP-0134,
EXP-0135 and EXP-0136 name themselves after the `DRV-P2-*` rows and are cited below only where
they genuinely bear on the Part-II question.

| item | answered by | commit | verdict as recorded | block |
|---|---|---|---|---|
| P2-01 (BF16 arith) | EXP-O2D + EXP-M4-13 + EXP-M4-02 | — | **PARTIAL** — hardware YES (distinct `0x11` group, scalar `byte+1=0x02` and packed `bfloat2` `0x04`, opsel `0x1c/1d/1e`; the only executed field is the add/mul opsel splice, **A18**); emit NO — every bf16 operand field is `untested`/`tokenization-only`, so the family is "decodable, not yet emittable". `EXP-0145` (uncommitted at the time of this pass) is the successor | NEW-2 |
| P2-02 (BF16 numerics) | **desk audit** | — | **NO** — no committed experiment has measured a single bf16 numeric result; EXP-0103 is fp32/fp16 only, EXP-0102 covers unorm/snorm/half. Do not assume fp32's DAZ+FTZ transfers — FP16 already contradicts it | NEW-2 |
| P2-03 (coop matrix) | **EXP-0147** + EXP-0022/EXP-O2C | `487caaad`, — | **YES, upgraded** — `matrix_mac` is now **EMITTABLE**, 12/12 fields (`dst_desc` 256/256 rule bit6=1 & bit7=0; `b11hi` 128/128 rule `(v&3)==0`). Bonus capability: **`A*B - C` and a half-tile variant**, which Metal never emits. Constraints: 8x8 only, integer matrices REJECTED, mode `0x54` is semantic not a hint. Field targets are mixed M4/A18 | NEW-2 |
| P2-04 (mesh stage ISA) | EXP-0135 + EXP-0147 + EXP-M4-13 | `661f1258`, `487caaad` | **NO** — the mesh *pipeline* contract is well characterized on M4 (payload 16,384 B; UVB 256 vtx / 512 prim; amplification silently dies at 65,536 vs Metal's 1,048,576; firmware-managed allocation), but **no field of any mesh-stage instruction has ever been executed**: `mesh_out_src.sel` `untested` (EXP-0147 pre-registered it not attempted), `ibfe_mesh_attr` corpus-correlation | NEW-2 |
| P2-05 (ray query) | **desk audit** (EXP-0023/M4-14/O2C/M4-13) | — | **NO** — only `rt_intersect` and `rt_query_traverse` have any `hardware-run` field and **both are A18**; the rest of the ~13-op family is `corpus-correlation`/`tokenization-only`. BVH node format is firmware-authored and opaque to userspace (a kernel-coordination item) | NEW-2 |
| P2-06 (native FP64) | **UNANSWERED** | — | The only thing on record is a **premise** ("not exposed by MSL on Apple GPUs"), not a probe. EXP-0146's native 64-bit ADD is integer register-pair machinery — what the question excludes | — |

## What is still genuinely open (6 items), and what each needs

| item | what is actually needed |
|---|---|
| **P2-06** — native FP64 | An MSL `double` compile-rejection probe (cheap) **plus** an opcode-space search. Corpus byte0-census coverage proves nothing: the corpus is compiled from an MSL with no `double`. |
| **TEX-01** — projective divide | `op+2` bit-space fuzzing on a spliced valid `tex_sample` bundle, plus directed zero / signed-zero / inf / NaN / array-coordinate inputs, on M4. `tex_addr_setup.form = 0x01` is already identified as coordinate projection but only on **A18** and with no numeric edge cases. `lower_txp` stays enabled meanwhile. |
| **TEX-19** — bindless texture to 1,000,000 | Re-run EXP-0095's GLIMG-A02 methodology at boundary values near 1,000,000, on M4. |
| **TEX-21** — bindless sampler to 499,999 | M4 re-run of EXP-O2B §4's methodology at boundary values near 499,999 — the existing evidence is **A18** and predates the M4-only directive. |
| **TEX-22** — 500,001st sampler / destroyed ID | Same successor as TEX-21, extended to allocation failure, ID reuse after destruction, and dedup. EXP-O2B named this gap and never executed it. |
| **MEM-19** — USC preload capacity | A USC uniform-program probe that varies the declared preload count across and beyond the supported capacity, on M4 — the successor EXP-0083 named. |

### Plus: one item that needs a DECISION, not evidence

**SFU-04** — counting refinement iterations in Apple's compiler-generated reciprocal sequence is
forbidden by `CLAUDE.md` FORBIDDEN rule 5, and EXP-0103 pre-registered it `DEFERRED` for exactly
that reason. Recommendation: mark it **OUT-OF-SCOPE (clean-room rule 5)** with the two clean
hardware endpoints as the documented substitute (seed ~7.5-8 mantissa bits, EXP-0026 A18;
`precise::rcp` 0 ULP with 1856/1886 exact, EXP-0103 M4), rather than leaving it as an open
experimental gap that implies a future experiment could close it.

### Plus: five PARTIAL answers with a named open half

| item | the half that still needs hardware |
|---|---|
| P2-01 | every bf16 operand field is `untested` — the family is decodable, not emittable. `EXP-0145` is the live successor. |
| TEX-12 | the residency code (`sparse_color`/`.resident()`) and the filtered + gathered forms; mapped-texel colour is blocked behind the write-persistence negative. |
| TEX-20 | index `>= 1,000,000`, and the nonresident-resource case. |
| TEX-28 | the filter sub-field: `mipFilter` code 3, descriptor bits 24 and 26, and the MSL-4.0 per-sampler `bias(float)` state field's raw bit location. |
| MEM-18 | the exact table-to-preload mapping and its independent capacity — EXP-0083 explicitly declined to make a constant-program slot-table claim. |

## Health notes a reader should not miss

- **Not every Part-II answer is M4-executed.** No item has independent A18/G17P validation, but
  several answers rest wholly or partly on **A18-era** evidence and must say so wherever they are
  reused: TEX-21/22 (EXP-O2B), the TEX-26/27 API halves (EXP-M4-08, M4+A18 cross-confirmed),
  P2-01's single executed bf16 splice (EXP-O2D), P2-03's matrix operand selectors
  (EXP-0022/EXP-O2C), **both** of P2-05's executed ray-tracing results (EXP-0023, EXP-M4-14), and
  ENC-16's `frame_prologue`/`spill_frame_marker`/`link_save_restore` sweeps (EXP-M4-14).
- **`tools/agx-isa/validation.json` is behind `EXP-0147`.** Its `coverage` block still reports 21
  emittable mnemonics and still labels `matrix_mac` `target: A18` with `dst_desc`
  `tokenization-only`. EXP-0147 promoted `matrix_mac.dst_desc` and `matrix_mac.b11hi` to
  `hardware-run` on M4 and its `analysis/emittability.json` records `emittable_after: true`.
  Regenerating the sidecar is a prerequisite before P2-03's block is treated as normative.
- **Six retractions must survive any edit to the task list:** EXP-0112 over EXP-0105 on r64-95
  (aliasing, not silent zero); EXP-0101 over EXP-M4-13's `dst` formula; EXP-0099 over both
  bit-15/31 lifetime models (retracted from `docs/isa` in `88fa4953`); **EXP-0140 over EXP-0128's
  `mov_imm` "silent zero"** (the buffer was zero-initialised — the instruction does not write at
  all); **EXP-0139 over EXP-0112** (the `r(R mod 64)` aliasing does NOT transfer to `iadd2.dst`);
  **EXP-0148 deleting `falu2_ext8b`**, which was never an instruction. Two further supersessions
  the wave-2 blocks carry: EXP-0146 supersedes the EXP-0102/EXP-0038 reading that 64-bit add is
  necessarily a carry chain, and EXP-0135 supersedes EXP-0030's framing of the `0x43` marker as
  object/mesh-exclusive (it is a generic pre-call frame-setup marker).
- **Two answers contradict their own documentation and are the most driver-relevant findings
  here:** `interpolate_at_offset` (FS-08) does not implement its documented center-relative
  contract, and `extract_bits` (INT-02) has a three-way contract that is not NIR's.
- **One answer is a live software-stack hazard:** `min_lod_clamp()` (TEX-05) crashes the
  `AGXMetalG16G` compiler service for 3 of its 4 compute-stage forms on this macOS/Metal build.
