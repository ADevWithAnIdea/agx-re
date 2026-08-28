# PRE_REGISTRATION — EXP-0121 M4 NIR-contract closure (OPT-01,03,04,05,06,07,08,10,11)

Frozen before any capture run. OPT-02 and OPT-09 are already answered (EXP-0074, EXP-0091) and
are out of scope here.

## Pinned environment (frozen at pre-registration; do NOT re-check against live HEAD)

- Repo revision: `87d02c34f56357734f448695cf62d37ab555fcb0` (dirty tree — many sibling
  experiments' untracked directories from parallel agents; this experiment's own tracked
  input files are what gate validity, per `SUBAGENT_BRIEF.md`'s "authored blob hashes match"
  rule, not `git status` cleanliness of the whole tree).
- Host: local Apple M4 / G16G, macOS 26.6.2 (25G82), 10 GPU cores, Metal 4.
- Toolchain: `xcrun clang` (Command Line Tools), Python 3.14.6. `tools/shdump/shdump.m`,
  `tools/agxtest/agxrun.m`, `tools/agxtest/agxtest.py`, `tools/shdump/agxparse.py`,
  `tools/agx-isa/isadb.py` used READ-ONLY (built into this experiment's own `work/bin/`,
  never modified). A render harness `harness/fsrun.m` is copied+adapted from
  `experiments/EXP-0111-m4-fragment-semantics/harness/fsrun.m` (our own prior committed code,
  reuse explicitly sanctioned by `SUBAGENT_BRIEF.md`) with no functional changes beyond what
  is noted in `harness/fsrun.m`'s own header.
- Source hashes of the frozen kernel/harness files are recorded in `CAPTURE_CONTRACT.json`
  (`sha256` per file) at freeze time, before run01.

## Global method note

Per `SUBAGENT_BRIEF.md`'s documented ISA hazards (`docs/isa/register-move-and-liveness.md`:
GPR-sourced register moves are `UNKNOWN`/broken outside a narrow validated scope, and
`device_load`→ALU bridging has repeatedly failed under hand construction), this experiment
does **not** hand-assemble novel instruction encodings from scratch. Evidence is built from:

1. **OWN-SHADER functional testing** — MSL kernels we author, compiled by the public runtime
   compiler, with runtime (non-compile-time-foldable, buffer-sourced) operands spanning
   directed boundary/hole values plus randomized fill, dispatched on real M4 hardware, and
   compared against an independently written host oracle (`harness/oracle.py`). This is the
   primary evidence source for OPT-01/03/04/05/06/10/11.
2. **STRUCTURAL decoding** — `shdump` → `agxparse` → `tools/agx-isa` `isadb.disassemble` on
   the exact bytes the compiler emitted for (1), read-only, to determine instruction identity,
   count, and field values (e.g., is there one fused compare-select instruction or two; is the
   `ldexp` op a single dedicated opcode; is a varying/output slot field typed `imm` or `reg` in
   `tools/agx-isa/db.json`). This is the primary evidence source for OPT-07/08's "hardware
   question" (separate from the already-answered MSL-surface question).
3. **Bounded, narrow splice validation** where (1)+(2) leave a specific field's causal role
   unconfirmed and the splice target is a single, previously-characterized bit/byte in an
   otherwise-untouched compiled program (the same technique EXP-0093 used for the `0x07`-family
   convergence bit) — used sparingly, one change at a time, never to construct a whole novel
   instruction body from database field tables alone.

## Per-item hypotheses, variables, falsifiers

### OPT-01 — fdiv: distinct relaxed/precise hardware sequences?
- H: relaxed (`fast::divide`, or plain `/` under `fastMathEnabled=YES`) and precise (plain `/`
  under `fastMathEnabled=NO`, and `precise::divide` where it exists) compile to **structurally
  different instruction sequences** (different instruction count/mnemonics — specifically:
  precise division uses the `fspecial_est` seed + Newton-Raphson refinement chain per
  `tools/agx-isa/db.json`'s existing provenance note ("`fspecial_est` appears ONLY in the
  precise... lowerings; fast-math uses the single-op SFU `fspecial` instead"), while relaxed
  division uses a single `fspecial` reciprocal estimate) AND/OR produce **numerically
  divergent results** on a shared corpus.
- IV: math-mode (relaxed vs precise) × namespace (plain `/` vs explicit `fast::divide`).
  CV: identical `(a,b)` corpus, identical dispatch shape.
- Expected if TRUE: byte length / instruction mnemonic list differs between relaxed and precise
  compiles of the same division expression, AND/OR ULP-level numeric divergence on a
  subnormal/boundary-heavy corpus (reusing EXP-0074's DAZ+FTZ characterization of the precise
  path as the reference model to compare the relaxed path against).
- Falsifier: byte-identical compiled instruction sequences for relaxed vs precise AND
  bit-identical numeric output across the whole corpus — would mean Apple9 exposes only one
  observable division sequence regardless of precision mode, contradicting `.lower_fdiv=false`.

### OPT-03 — pow: fixup beyond exp2(y*log2(x))?
- H: `pow(x,y)` compiles to **more instructions** than the manual `exp2(y*log2(x))` composition
  (extra compares/selects for the IEEE special cases: negative base, `0^0`, `x^0=1` for any x
  incl. NaN/Inf, `(-0)^odd`, `(-0)^even`, negative base with non-integer exponent → NaN), and/or
  produces **different results** on those edge cases than the naive composition (which is
  undefined/NaN-producing for negative `x` because `log2(negative)` is NaN).
- IV: builtin `pow` vs manual `exp2(y*log2(x))`. CV: identical `(x,y)` edge-case corpus.
- Expected if TRUE (fixup needed): `pow` compiled body is structurally larger (extra
  `icmp_pred`/`sel`/`isel*` instructions) and numerically diverges from the naive composition on
  the special-case corpus, while agreeing with a from-scratch IEEE-754/C99 `pow` host oracle.
- Falsifier: `pow` and the manual composition are byte-identical or numerically identical
  everywhere including the special cases (would mean the special cases are simply not handled
  correctly by either, or somehow both already agree, which the corpus is designed to detect).

### OPT-04 — ldexp: single decoded instruction across the exponent envelope?
- H: `ldexp(x,n)` with a **runtime** (non-foldable) `n` compiles to the single dedicated
  `fldexp` opcode already in `tools/agx-isa/db.json` (byte0 low-nibble 0xf, 6 bytes,
  `NOT HW-dispatch-validated` per its provenance), and this op produces the C99/IEEE-correct
  result across exponent boundaries (0, ±1, subnormal-producing negative exponents down to and
  past -149, overflow-producing positive exponents past 128, `INT32_MIN/MAX` exponents),
  signed zero, subnormal `x`, ±Inf, and NaN.
- IV: `x` class (normal/subnormal/zero/inf/nan) × `n` (boundary sweep). CV: identical dispatch
  shape; `n` supplied via a runtime buffer, never a compile-time literal (a constant `n` folds
  to `fmul`, per the DB note, and would not exercise `fldexp` at all).
- Expected if TRUE: (a) structural: tokenized `_agc.main` contains exactly one `fldexp` per
  `ldexp` call site, with the same match bytes documented in `db.json`; (b) functional: HW
  output bit-exact against `math.ldexp` (Python's C99 `ldexp`, used only as a portable,
  independently-implemented host oracle — not an Apple source) at every tested point, OR a
  clean, fully characterized deviation (e.g., a DAZ/FTZ carve-out matching the rest of this
  hardware's FP32 behavior).
- Falsifier: no `fldexp` instruction appears (compiler instead synthesizes ldexp via bit
  manipulation / `exp2` multiply even for runtime `n`) — refutes "directly executable
  instruction"; or functional output is wrong/undefined outside a clean explainable model —
  downgrades "fully decoded operands and result semantics" to `PARTIAL`.

### OPT-05 / OPT-06 — general compare-and-select: one instruction, arbitrary operands, full type/condition coverage?
- H: `tools/agx-isa/db.json` already documents a **fused** compare-select family
  (`isel8`/`isel10`/`isel10_c`/`isel_reg`/`isel_reg8`, semantics `d = (cmpA CC cmpB) ? selTrue :
  selFalse`) distinct from the **two-instruction** `icmp_pred`(sets a predicate)+`sel`(branchless
  select on that predicate) pattern EXP-0111's FS-10 observed for an array-select idiom. H: a
  plain two-value ternary/`select()` over **runtime, non-Boolean, non-adjacent-by-construction**
  operand values compiles to ONE fused `isel*` instruction (not `icmp_pred`+`sel`), for FP32,
  signed I32, and unsigned I32, across every comparison NIR needs (eq, ne, lt, le, gt, ge — the
  `cc`/`cond` enums in `db.json` list only `eq_form`/`{f,u,s}cmp_{gt,lt}`, so le/ge/ne coverage is
  an open question this experiment must resolve: are they separate enum values, or synthesized
  via operand-swap / negation bits on the same 4 base conditions?).
- IV: operand type (f32/i32/u32) × condition (eq/ne/lt/le/gt/ge) × operand pair (including
  signed/unsigned-distinguishing pairs, e.g. bit pattern `0xFFFFFFFF` as `-1` (signed less than
  0) vs `UINT32_MAX` (unsigned greater than 0)). CV: identical dispatch shape, `select(B,A,pred)`
  idiom with runtime `A`,`B`,`pred`-inputs (`A`,`B` far from 0/1, e.g. large distinct sentinels)
  so the result is unambiguously "which operand" not "which boolean".
- Expected if TRUE: (a) structural — one `isel*`-family instruction per case, `cc`/`cond` field
  value maps onto the requested condition (possibly via a documented swap/negate transform for
  le/ge/ne); (b) functional — HW output equals `pred ? A : B` (host-computed) for every case,
  including the signed/unsigned-distinguishing pairs (confirms the `u`/`s` distinct `cc` values
  are not aliases).
- Falsifier (OPT-05): the compiled body is `icmp_pred`+`sel` (or any 2-instruction split) for
  the plain-ternary idiom, or the selected instruction's `selTrue`/`selFalse` values are not
  independently controllable (i.e., functionally always material to only a Boolean-shaped
  output) — would mean the fused form is not what a compiler backend can rely on for arbitrary
  values. Falsifier (OPT-06): any of f32/i32(signed)/u32 or any of eq/ne/lt/le/gt/ge produces a
  wrong result, or signed/unsigned-distinguishing pairs are not actually distinguished (i.e., the
  hardware silently treats `scmp`/`ucmp` identically) — narrows the claim to the subset that
  passed.

### OPT-07 — dynamically indexed varying/input: hardware capability vs. compiler strategy
- Builds on EXP-0111 FS-10 (`HW`-confirmed: dynamic fragment-input indexing lowers to
  "read every candidate via ordinary fixed-slot `iter`/`iter_flat`, select via `icmp_pred`+
  `sel`/ALU" — functionally correct, but that is a *compiler strategy*, not proof the hardware
  categorically cannot address a varying slot with a register operand).
- H: `tools/agx-isa/db.json`'s `iter` instruction types its `src_slot` field (byte+5) as `imm`
  (a per-instruction compile-time immediate, `slot<<1`) — i.e., under the SIMT execution model,
  every lane executing one `iter` instruction reads the SAME slot; there is no field in the
  currently-decoded encoding through which a *register* (per-lane-varying) value could select
  the slot. This experiment (a) re-confirms that field-type fact by fresh structural decode of a
  wider (8-varying) dynamic-index kernel than FS-10's 4-varying one, checking whether a larger
  candidate set changes the strategy (e.g., triggers a genuinely different, register-sourced
  `iter` variant once linear ALU-select cost grows), and (b) treats the immediate-field finding
  as a **bounded structural negative**, explicitly distinguished from an exhaustive proof that no
  register-sourced `iter` variant exists anywhere in the unobserved encoding space.
- IV: number of candidate varyings (4 vs 8) forcing a wider select tree. CV: same dispatch shape,
  same runtime-index derivation (`pos.x`-derived, non-foldable).
- Expected if TRUE (compiler strategy is stable, no hardware indirect-slot instruction is
  exposed by the compiler at any candidate count): every candidate slot is still read by an
  ordinary fixed-`src_slot` `iter`/`iter_flat`, selection is still ALU (`icmp_pred`+`sel` or a
  reduction tree), and `src_slot` values are still small compile-time constants (not runtime
  register values) even at 8 candidates.
- Falsifier: at 8 candidates the compiler switches to fewer `iter` instructions than declared
  varyings with an register-operand slot field — would be **positive** evidence of an indirect
  hardware path and would flip OPT-07 toward `PARTIAL`/`YES` for the ISA question.

### OPT-08 — dynamically indexed varying/output: hardware capability vs. compiler strategy
- Builds on EXP-0111 FS-11 (`No` MSL syntax for a dynamically-indexed fragment-output array;
  the only expressible lowering is branch-unrolled fixed `[[color(n)]]` outputs; functionally
  correct for a genuinely per-fragment-divergent 2-way selector; but FS-11's own structural scan
  found a *single* `frag_color_store` instruction servicing what should be two logically distinct
  per-RT writes, flagged `UNKNOWN`/"candidate follow-up" — never bit-decoded).
- H1 (field-type, symmetric to OPT-07): `frag_color_store`'s `rt_index` field (byte+5) is typed
  `imm` in `db.json` (`rt<<1`, a per-instruction constant) — no register-sourced RT-index field
  is present in the currently-decoded encoding.
- H2 (the FS-11 mystery, addressed head-on): re-compile a fresh, WIDER (3-way, not 2-way)
  per-fragment-divergent branch-unrolled kernel and fully dump/tabulate every `frag_color_store`
  and `frag_tile_setup` instance's raw bytes and every decoded field (not just the store count)
  to determine whether the single-store shape from FS-11 (a) generalizes to 3 targets, (b) is
  explained by `frag_tile_setup`'s `sel` field carrying a genuinely dynamic (register-sourced)
  RT/tile selector distinct from `frag_color_store`'s own static `rt_index`, or (c) is an
  artifact of this specific 2-target case (e.g., the compiler happening to route both branch
  arms' `src` register through one shared store while `frag_tile_setup`'s bracket alone gates
  which physical tile memory the write lands in) that does not scale to 3 targets.
- IV: number of render targets / branch arms (2, matching FS-11, vs 3, new). CV: same
  `[[position]]`-derived genuinely-divergent selector, same readback method (per-fragment,
  per-RT pixel colors).
- Expected if TRUE (H1, negative): `rt_index` stays a small compile-time constant in every
  observed instance, at both 2 and 3 targets.
- Expected if H2 resolves to "yes, genuine hardware dynamic selector": the 3-target case shows
  a `frag_tile_setup`/`frag_color_store` combination whose selector byte value structurally
  depends on which RT can be written (not just a fixed enumeration), AND functionally routes a
  divergent selector to 3 different targets with fewer store instructions than targets.
- Falsifier of H2's positive reading: the 3-target kernel needs 3 (or more) distinct
  `frag_color_store`/`frag_tile_setup` combinations (one genuinely per target, scaling linearly)
  — confirms the FS-11 2-target single-store shape was a narrow compiler coincidence (e.g. two
  RTs sharing one packed store), not a dynamic-selector capability, and the negative (H1) stands.

### OPT-10 / OPT-11 — does an ordinary aligned load/store satisfy atomic-load/store semantics under fences?
- H: replacing the ready/ack signaling words in a cross-threadgroup message-passing litmus
  (EXP-0093's proven-sensitive design: `PAIRS>=4` producer/consumer threadgroup pairs, a
  bounded spin-wait, a payload+flag mailbox) with **ordinary (non-atomic-typed, but
  `volatile`-qualified to prevent register caching) 32-bit-aligned loads/stores**, surrounded by
  the same `atomic_thread_fence(mem_device, seq_cst, thread_scope_device)` calls EXP-0093 proved
  sufficient for the fully-atomic case, reproduces the **fully-atomic-fenced** zero-mismatch
  invariant — separately for the store side (OPT-11: plain store, trusted atomic load) and the
  load side (OPT-10: trusted atomic store, plain load), plus the combined (both plain) case.
- IV: access method per {producer-write, consumer-read} ∈ {atomic, plain} (4 combinations:
  AA baseline, PA=plain-store/atomic-load [OPT-11], AP=atomic-store/plain-load [OPT-10],
  PP=both-plain) × fence presence (fenced / unfenced-weak-control) × `PAIRS` ∈ {1,4,8}.
  CV: identical payload/salt generator, identical bounded spin (never unbounded), identical
  iteration count, same underlying 4-byte-aligned storage (`atomic_uint` struct fields,
  accessed either via `atomic_*_explicit` or via a raw `(volatile device uint*)` reinterpret —
  same bits, different access method, avoiding any storage-layout confound).
- Expected if TRUE (both OPT-10 and OPT-11 YES): PA, AP, and PP fenced configurations all show
  **zero mismatches** at every tested `PAIRS`, matching AA-fenced exactly; every UNFENCED
  configuration (including AA-unfenced, reproducing EXP-0093's ATOM-07 result as a within-this-
  experiment sanity check) shows **nonzero, `PAIRS`-scaling mismatches** — the weak control must
  actually break, per the dispatch's explicit falsifier requirement.
- Falsifier: any FENCED plain-access configuration (PA, AP, or PP) shows nonzero mismatches at
  `PAIRS>=4` while AA-fenced (the trusted atomic baseline, same run) shows zero — proves ordinary
  load/store does NOT get the same ordering/visibility treatment as an atomic op even under
  identical fencing, and the corresponding OPT-10/OPT-11 answer is `No`.
- Per dispatch's finite-resource / concurrency mandate: exact per-lane mismatch counts and
  message completion counts are **not** gated (order-sensitive scheduling detail, expected to
  vary run-to-run) — only the coarse invariant (`exact`/`broken`/`incomplete`) is a gated field;
  raw per-configuration mismatch/timeout counts are written to a sibling non-gated file
  (`raw/<run>/concurrency_detail.jsonl`), proving the split explicitly in `verify.py --selftest`.

## Evidence labels anticipated

OPT-01/03/04/05/06/10/11: `OWN-SHADER-DIFF` + `HW-PROBE` (functional, own-MSL, host-oracle
compared) — not `HW-VALIDATED` in the strict "independently assembled/spliced" sense unless a
splice sub-test is added and passes (see `RESULTS.md` for which items got one).
OPT-07/08: `STRUCTURAL` (own-compile field-type decode) primarily, `OWN-SHADER-DIFF`+`HW-PROBE`
for the functional-correctness side already partly established by EXP-0111 (cited, not redone
from zero) and extended here (8-candidate input, 3-target output).

## Confounders considered

- Compiler version/flags drift between runs: pinned by capturing the exact `xcrun`/Metal
  toolchain version in `00_env.json` each run; not expected to change within this session.
- Fast-math global flag vs. explicit `fast::`/`precise::` namespace: tested both ways for
  OPT-01 (see FP-07 precedent in EXP-0103) to avoid conflating a global compile flag with a
  per-call namespace choice.
- GPU thermal/scheduling variance affecting concurrency litmus outcomes: addressed by the
  gated/non-gated split above (qualitative invariant gated, raw counts not).
- `volatile` in MSL preventing compiler caching but not itself a claim about hardware ordering
  guarantees: the claim under test is exactly "hardware ordering/visibility given a `volatile`
  (i.e., genuinely-emitted) plain load/store", so this is by design, not a confound — but it is
  called out explicitly so a reader does not mistake `volatile` itself for the mechanism being
  validated.
- `isel*` field is register-typed for `selTrue`/`selFalse`, but the compiler could still choose
  to fold a *specific* observed pair of values (e.g., always adjacent registers) in a way that
  looks arbitrary but isn't independently controllable; addressed by using very different,
  far-apart sentinel values per case and multiple unrelated register-pressure contexts.

## What this experiment does NOT attempt

- Does not hand-construct a novel `isel*`/`fldexp`/`iter` instruction body from `db.json` field
  tables in isolation (the register-move/liveness hazards make blind construction unreliable);
  any splice sub-test starts from a real compiled instruction and flips a single already-typed
  field.
- Does not resolve the exact bit-for-bit bracketing of `fldexp`'s `operand`/`b4`/`b5` raw fields
  beyond what a fresh structural decode can localize; full operand decode is explicitly allowed
  to close as `PARTIAL`.
- Does not probe vertex-stage output slot indexing (a different, untested "varying write"
  surface from the fragment-color-output framing this experiment shares with EXP-0111); flagged
  as an explicit gap in `RESULTS.md`.
