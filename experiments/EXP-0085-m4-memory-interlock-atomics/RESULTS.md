# EXP-0085 results — M4 memory interlock + atomic operation set

**Target: local Apple M4 (G16G) only**, macOS 26.6.2 build 25G82, Metal 4,
10 GPU cores. No A18 Pro claim (A18 hands-off). Two capture runs
(`raw/m4-20260827-run01`, `raw/m4-20260827-run02`), 56 cases each, from
byte-identical authored source. **Cross-run gate: PASS (0 issues).
Provenance gate: PASS. Per-case invariant verdicts: 56/56 PASS.**
`verify.py --selftest`/`--seqtest`/`--captured` all PASS. Zero GPU faults,
hangs, watchdog fires, or host issues across both runs (112 dispatches
total, plus the two smoke-gate dispatches).

## Headline verdicts

| item | verdict | evidence class |
|---|---|---|
| **MEM-13** (load/texture/atomic → ALU, no explicit wait) | **YES — HW-VALIDATED** | contention (N≤65536) + adversarial stress (N=65536×48 in-flight) + structural (0-wait tokenization) |
| **MEM-14** (ALU-computed source → store/atomic, no explicit wait) | **YES — HW-VALIDATED** | contention + structural |
| **ATOM-01** (device atomic subtract = direct op selector) | **YES — HW-VALIDATED** | functional (exact `mod 2^32` arithmetic) + structural (op selector `0x1b`, distinct from add's `0x10`) |
| **ATOM-02** (threadgroup atomic subtract = direct op selector) | **YES — HW-VALIDATED** | functional (one-threadgroup contention) + structural (same `0x1b`/`0x10` selectors under the `atomic_tg` instruction form) |
| **ATOM-03** (device atomic return = pre-op value) | **YES — HW-VALIDATED** | functional, two independent invariant forms (exact per-slot + contended permutation) |
| **ATOM-04** (compare-exchange = one native transaction, exact semantics) | **YES — HW-VALIDATED** | functional single-winner invariant under real N=65536/256 contention + structural (single instruction, no retry loop) |
| **ATOM-05** (uniform-address SIMD pre-combine valid for every op emitted) | **YES, with a sharpened boundary — HW-VALIDATED** | structural + functional, see below |
| **ATOM-06** (pre-combine disabled for distinct-return-value ops) | **YES, with a sharpened boundary — HW-VALIDATED** | structural + functional, see below |
| ATOM-07 (relaxed ordering, no implicit device fence) | **DEFERRED** (language-exposure-only negative result recorded) | — |
| ATOM-08 (device fence Vulkan/GL acquire/release visibility) | **DEFERRED** | — |
| ATOM-09 (barrier convergence+fence coupling) | **DEFERRED** | — |
| ATOM-10 (device-scope barrier vs standalone fence encoding) | **DEFERRED** | — |
| ATOM-11 (texture/image fence coverage) | **DEFERRED** | — |

## MEM-13 — OBSERVED / INTERPRETED

**OBSERVED.** Six cases, all PASS on both runs: `il_load_alu` (device load →
immediate `fma`), `il_gather` (dependent/gather load → immediate `fma`),
`il_atomic_alu` (atomic RMW result → immediate ALU, N=8192, permutation
invariant), `il_chain48_n4096`/`il_chain48_n65536` (48 independent loads per
thread, zero waits, summed and consumed with no intervening statement — the
adversarial register-pressure/occupancy stress case, run at both N=4096 and
N=65536 threads), and `il_tex_alu_64x64` (`texture2d::read` → immediate
`fma`, 4096 texels). Every case's output matched its independently
recomputed exact expected value (float ops used only exact-representable
small integers, so no summation-order tolerance was needed — see
`PRE_REGISTRATION.md` "Contention invariants"). Structural tokenization
(`analysis/tokenize_evidence.txt`) of the M4-compiled bytes for
`il_load_alu`/`il_gather`/`il_atomic_alu`: the consuming ALU instruction is
byte-adjacent to the producer (`device_load`→`falu3` with 0 intervening
bytes; the atomic case's ALU consumer follows the compiler's SIMD-reduce
broadcast/rebuild tail — `simd_shuffle`→`iadd2`/`cvt_i2f`→`falu3` — with no
wait/scoreboard opcode anywhere in that chain).

**INTERPRETED.** M4 exhibits the same hardware register interlock EXP-0025
documented on A18/G17P for compute memory ops: a load, gather, atomic
result, or texture read feeds a consuming ALU instruction with zero
authored slack and no software wait, and the hardware guarantees the
consumed value is the operation's own result — including through the
compiler's multi-instruction SIMD-reduce/broadcast machinery for the atomic
case, and under adversarial register pressure (48 independent per-thread
loads) at up to 65536 concurrently-scheduled threads. **This extends the
A18 finding to two new operation classes it did not test compute-side:
texture `read()` and the specific "atomic RESULT consumed by ALU"
sub-case** (EXP-0025's `atomicuse` kernel tested atomic-then-ALU too, but
not under real multi-threadgroup contention).

**Alternative explanations not excluded.** As in EXP-0025: this is
observational (a construction attempt that produced correct results at
every scale tried), not a proof that no register-pressure regime beyond
N=65536/48-deep chains could ever expose a hazard. The DB field names in
`analysis/tokenize_evidence.txt` (`ret_flag`, `addr_desc`, `data_desc`,
etc.) are unvalidated placeholders (EXP-0018 already flagged the atomic
reg-pack tail as *inferred*); only the **presence/absence of an opcode**
between producer and consumer is treated as evidence here, not per-bit
field semantics.

## MEM-14 — OBSERVED / INTERPRETED

**OBSERVED.** `il_store_src` (ALU-computed value `a[i]*b[i]-a[i]` stored
with zero gap, N=8192, fully deterministic, PASS both runs byte-identical)
and `il_atomic_src` (ALU-computed addend `a[i]+b[i]` fed directly as the
atomic's operand, N=8192, commutative-sum invariant `atom_final ==
sum(a[i]+b[i]) mod 2^32`, PASS both runs byte-identical). Structural
tokenization: `il_store_src` compiles to `device_load, device_load,
falu3[fma], device_store, stop` — the `fma` computing the store source sits
directly between the two loads and the store, 0 intervening bytes.
`il_atomic_src`'s tokenization (21 instructions) shows the `falu2[fadd]`
computing the addend immediately followed by a `cvt_f2i`, then the
compiler's SIMD-reduce/elect/atomic sequence — again no wait instruction
anywhere between the ALU computation and the atomic.

**INTERPRETED.** The register interlock is bidirectional: it also covers
the case where a memory/atomic operation's *source* register was written by
an ALU instruction immediately before, with no explicit wait needed before
the store/atomic reads it. Combined with MEM-13, a driver author does not
need to reason about scoreboard/wait insertion on M4 for ordinary compute
memory or atomic instructions in either direction — the omission that would
be a silent-corruption bug on G13-style hardware (EXP-0025's framing)
cannot occur here for these operation classes.

## ATOM-01 / ATOM-02 — operation set (device + threadgroup)

**OBSERVED — exact op-selector bytes** (structural, `analysis/tokenize_evidence.txt`,
cross-checked against every EXP-0018 A18/G17P value):

| op | device selector (structural, this exp) | threadgroup selector (structural, this exp) | EXP-0018 A18 byte+12 (÷2 = this field) | functional (both scopes, this exp) |
|---|---|---|---|---|
| add | `0x10` | `0x10` | `0x20` | PASS (exact `mod 2^32`) |
| **sub** | **`0x1b`** | **`0x1b`** | `0x36` | PASS (exact `mod 2^32`) |
| and | `0x11` | — (not separately re-tokenized; functional PASS) | `0x22` | PASS |
| or | `0x16` | — | `0x2c` | PASS |
| xor | `0x1f` (from `da_xor_static0`) | — | `0x3e` | PASS |
| umin | `0x1d` | `0x1d` | `0x3a` | PASS |
| umax | `0x1c` | `0x1c` | `0x38` | PASS |
| smin | (functional only) | — | `0x2a` | PASS |
| smax | (functional only) | — | `0x28` | PASS |
| exchange/store | `0x1e` | `0x1e` | `0x3c` | PASS (permutation) |
| compare-exchange | `0x12` | `0x12` | `0x24` | PASS (single-winner) |

Every M4-observed device selector equals **exactly half** the corresponding
EXP-0018 A18/G17P byte+12 value (the two DBs place the same bit field at a
different bit offset; the underlying hardware encoding is the same field).
**ATOM-01 is a direct YES**: subtract has its own selector (`0x1b`),
distinct from add (`0x10`) and from every other op — not an ALU
negate-then-add sequence, confirmed both structurally (single `atomic_mem`/
`atomic_rmw` instruction, no extra ALU op before it feeding a negated
operand) and functionally (`da_sub_indexed`'s per-slot final values match
`(init - delta) mod 2^32` exactly, which would not hold if the hardware
were doing unsigned-add-of-two's-complement homebrew inside the RMW rather
than a native subtract). **ATOM-02 is a direct YES**: `atomic_tg` is a
distinct instruction FORM from `atomic_mem` (own mnemonic, `byte+1` mode
bits `0x03` vs `0x01`/`0x11`, EXP-0018's threadgroup-scope bit), but reuses
the identical op-selector encoding, and the functional one-threadgroup
contention test (N=256, own-slot AND shared-slot addressing) matches the
combine-order-independent invariant exactly for add/sub/min/max.

**Width and return-form findings** (folds in the ATOM item's "operand
widths / return-value vs no-return forms / memory scopes" requirement):

- **32-bit**: full op set (add/sub/and/or/xor/umin/umax/smin/smax/
  exchange/compare-exchange) available with a return-value form, both
  device and threadgroup scope. All PASS.
- **32-bit float**: only `fetch_add` (`da_fadd`) is exposed by MSL, matching
  EXP-0018; PASS (exact sum, both addressing modes, N=65536).
- **64-bit**: MSL exposes **only** `atomic_min_explicit`/`atomic_max_explicit`
  — the **void, no-return** form. `atomic_fetch_add_explicit`,
  `atomic_fetch_min/max_explicit` (the fetch/return forms), and even
  `atomic_load_explicit` on `atomic_ulong` are all **rejected by the
  compiler** (re-confirmed interactively this run, see
  `PRE_REGISTRATION.md` "Build-time findings" #1). This sharpens EXP-0018's
  "only the void 64-bit min/max form exists" into: **there is no
  return-value-producing 64-bit atomic RMW anywhere in this MSL surface.**
  Functional: `da_umin64`/`da_umax64` PASS (exact `min`/`max` over 8192
  lanes, both addressing modes, checked via non-atomic CPU-side readback
  after GPU completion since no in-kernel fetch exists).
- **Return-value vs no-return, 32-bit exchange**: `da_exch` (return used,
  10-instruction compiled form including the register-forwarding
  `mov_imm`+`falu2` tail) vs `da_exch_noret`/`da_store` (return discarded,
  7-instruction compiled form — the forwarding tail is elided and an extra
  `device_load` appears instead, reloading `deltas[tid]` for the unrelated
  output write). **`atomic_store_explicit` and a return-discarded
  `atomic_exchange_explicit` compile to byte-identical `atomic_mem[xchg]`
  instructions** — MSL's "no-return store" is not a separate hardware
  operation, it is the same exchange with the return path unused. Both
  PASS the "final ∈ tags; old_out == deltas untouched" invariant.
- **Memory scopes**: device and threadgroup, both fully exercised; no
  third scope observed or expected (matches EXP-0018).
- **Orderings**: only `memory_order_relaxed` is accepted on an atomic RMW
  **call** in this MSL build; `memory_order_seq_cst` is rejected with
  "`order` argument must be `metal::memory_order_relaxed`" and
  `memory_order_acq_rel` is an undeclared identifier (case
  `da_add_seqcst_compile_probe`, PASS as an expected negative result —
  see ATOM-07 below for why this is exposure-only, not a closure).

## ATOM-03 — device atomic return = pre-op value

**OBSERVED.** Two independent invariant forms, both exercised for every RMW
and exchange op: (a) **own-slot** (`addr=indexed`, no contention): every
`old_out[i]` equals the init value exactly — a direct, uncontended
per-lane check that the returned value is the *pre-write* content, not the
post-write content or garbage. (b) **shared-slot** (`addr=uniform`, real
contention up to N=65536): the multiset `{old_out} ∪ {final}` equals
exactly the multiset `{deltas/tags} ∪ {init}` for every RMW/exchange case —
a bijective linearizable-history proof (no duplicate "old" observed by two
lanes, no delta/tag lost). All PASS, both runs, byte-identical on every
non-order-sensitive field.

**INTERPRETED.** Device (and threadgroup) atomic RMW/exchange returns are
consistently the pre-operation value, matching NIR's requirement, under
both no-contention and real multi-threadgroup contention.

## ATOM-04 — compare-exchange is one native transaction

**OBSERVED.** `da_cmpxchg`/`ta_cmpxchg` uniform-address cases (N=65536 and
N=256 respectively): **exactly one** lane's CAS succeeds among all
concurrent attempts on every run, the final value equals that winner's
desired tag, and every losing lane's observed `old` equals that same final
value (never a torn/unrelated value) — PASS on both runs, byte-identical
per-run winner count and final-vs-loser relationship (the *identity* of the
winning lane is order-sensitive and excluded from the cross-run gate per
`casematrix.py::case_order_sensitive_keys`, exactly as pre-registered).
Indexed (own-slot, no contention) cases: every lane succeeds, PASS.
Structural: `da_cmpxchg`/`da_cmpxchg_static0`/`ta_cmpxchg` each compile to a
**single** `atomic_mem[cmpxchg]`/`atomic_tg[cmpxchg]` instruction (op
selector `0x12`) with no backward branch/jump anywhere in the tokenized
stream — no retry loop.

**INTERPRETED.** Compare-exchange executes as one native hardware
transaction with exactly the success/return semantics NIR requires: a
single winner under contention, atomic visibility of the comparison and
write, and no software CAS/retry loop (consistent with, and now
contention-validated beyond, EXP-0018's single-instruction finding).

## ATOM-05 / ATOM-06 — SIMD pre-combine: sharpened boundary condition

**OBSERVED.** Three address forms were compared structurally and
functionally for the same ops:

1. **Static-literal uniform address** (`da_add_static0`/`da_xor_static0`/
   `da_umin_static0`, address `&target[0]`, a compile-time constant):
   compiles to the full `simd_reduce → icmp_pred/if_push (elect) →
   atomic_rmw → pop_reconverge → simd_reduce/simd_shuffle (broadcast) →
   iadd2 (rebuild)` sequence — Apple's SIMD pre-combine optimization IS
   applied. Functional PASS (contention sum invariant, N=8192).
2. **Runtime-uniform address** (`da_add`/`da_xor`/`da_umin`/... `addr=uniform`,
   address `target[idx[tid]]` where `idx[]` is a buffer whose contents
   happen to be all zero): compiles to a **plain** `atomic_mem[op]`
   instruction with **no** `simd_reduce`/election machinery at all, even
   for `add` — the exact same shape as the genuinely non-uniform
   `addr=indexed` case. Functional PASS (same contention sum invariant,
   N=65536).
3. **Non-reducible ops at a static-literal uniform address**
   (`da_exch_static0`, `da_cmpxchg_static0`): compiles to a **plain**
   `atomic_mem[xchg]`/`atomic_mem[cmpxchg]` instruction — **no**
   `simd_reduce`/election machinery, even though the address is the same
   kind of compile-time-constant literal that DOES trigger the
   optimization for `add`/`xor`/`umin`. Functional PASS (permutation /
   single-winner invariants, N=8192).

**INTERPRETED.**
- **ATOM-05 — YES, bounded precisely.** The uniform-address SIMD
  pre-combine is applied, and functionally exact, for every *reducible*
  (commutative/associative, single-result) op the compiler emits it for in
  this corpus: add, xor, min (and, by EXP-0018's original A18 evidence
  reproduced unchanged here, or/max) — but **only when the compiler can
  prove the address uniform at compile time.** A data-dependent address
  that happens to be runtime-uniform (loaded from a buffer of all-zero
  indices) is **not** optimized — the compiler takes the same
  per-lane-address code path it would for a genuinely varying index. This
  is a sharper boundary than EXP-0018 established (which tested only a
  literal-uniform vs per-lane-indexed pair, not the "uniform buffer
  content, non-uniform provenance" case this experiment discovered during
  build-time probing).
- **ATOM-06 — YES.** The pre-combine is unconditionally **disabled** for
  exchange and compare-exchange — ops whose defining semantics require each
  lane's own distinct desired-value/return-value — even at a
  compile-time-provable uniform address where the optimization is
  otherwise available. This is exactly the "distinct return values" case
  ATOM-06 asks about, now structurally confirmed rather than inferred: the
  compiler's own code generation, not merely absence of a counterexample,
  demonstrates the optimization is scoped to reducible ops.
- The optimization is **semantically invisible either way**: every
  functional invariant (final value, permutation, single-winner) held
  identically whether or not the reduce path was taken, confirming Apple's
  optimization does not change observable atomic semantics — only the
  instruction count/path.

## Deferred: ATOM-07 through ATOM-11

Not answered by this increment; see `PRE_REGISTRATION.md` "Scope" for the
full accounting and rationale (a distinct instruction family — the `0x07`
fence/barrier group — requiring its own splice campaign). The only new
input recorded here: `da_add_seqcst_compile_probe` re-confirms, at the
**atomic RMW call site** (not just a standalone fence, which is what
EXP-0051 tested), that this MSL build accepts only `memory_order_relaxed`
and rejects `memory_order_seq_cst`/`memory_order_acq_rel` — a language-
exposure fact, not a native ordering/fence semantics answer. Also newly
observed and explicitly NOT interpreted: a `scoreboard_fence kind=0x22`
instruction (`0x07` byte0 family, distinct `kind` value from EXP-0025's
`threadgroup_barrier` `mem_scope` values `0x61`/`0x85`) appears around the
compiler's SIMD-reduce lane-election machinery in every reduce-path atomic
kernel (see `analysis/tokenize_evidence.txt`, `il_atomic_alu`/
`da_add_static0`/etc.) — raw evidence for a successor experiment on the
fence/barrier family (ATOM-09/10), not an ATOM-07/08/09/10/11 finding.
**Recommended successor: the next available EXP-NNNN number (fence/barrier
instruction family). Note: EXP-0086 was already claimed by a concurrent
session for an unrelated topic (register-liveness-bits) at the time this was
written -- pick whatever is next free at dispatch time.**

## Contention invariants — matrix summary

| invariant class | cases | both runs |
|---|---|---|
| commutative/associative combine (`final == combine(init, deltas)`, any order) | 34 (device+threadgroup RMW, both addressing modes, 32/64-bit) | PASS, byte-identical |
| permutation/bijection (`{old_out} ∪ {final} == {new} ∪ {init}`) | 4 (`da_exch`/`da_exch_static0` uniform, `il_atomic_alu`) | PASS (multiset match; per-lane order excluded from gate as pre-registered) |
| single-winner (`exactly 1 success; final == winner tag; losers see final`) | 4 (`da_cmpxchg`/`da_cmpxchg_static0`/`ta_cmpxchg` uniform) | PASS |
| own-slot exact (`old_out[i] == init`, `final[i] == expected(init, deltas[i])`) | 16 (every `addr=indexed` case) | PASS, byte-identical |
| deterministic scalar (no contention) | 6 (interlock MEM-13/14 cases) + 1 (tex) | PASS, byte-identical |
| negative/exposure (`compile_fail` with expected diagnostic) | 1 (ordering probe) | PASS, byte-identical |

56/56 cases, both runs. Zero faults, zero watchdog fires (`work/*/smoke_receipt.json`
plus every `05_receipts.jsonl` entry shows `timed_out: false`, `exit: 0`).

## A18-era claims: RE-VALIDATED on M4 vs INHERITED

Per dispatch instruction, explicit accounting:

- **EXP-0025 "no explicit scoreboard wait; hardware register interlock for
  device load/atomic/texture results"** — **RE-VALIDATED on M4 silicon** in
  this experiment (own M4 compile, own M4 dispatch, own M4 tokenization;
  see MEM-13/MEM-14 above). Not merely cited — independently reproduced,
  and extended to texture-read and atomic-source (MEM-14) cases EXP-0025
  did not cover.
- **EXP-0025 "the only explicit sync op is the `0x07` threadgroup/device
  barrier"** — **INHERITED, not re-tested.** This experiment did not probe
  barrier presence/absence; it only observed (unexplained) `0x07`-family
  `scoreboard_fence` instructions appear around unrelated compiler
  scaffolding (see "Deferred" above) as a side effect of tokenizing atomic
  kernels, which is new raw evidence, not a re-validation of EXP-0025's
  barrier claim.
- **EXP-0018 atomic op-selector table (byte+12), device scope** —
  **RE-VALIDATED on M4 silicon**, exactly (every M4 op-selector value here
  equals the EXP-0018 A18 value ÷ 2, the two DBs' bit-window choice being
  the only difference — see ATOM-01/02 table above).
- **EXP-0018 "atomics are native single RMW ops, not CAS/retry loops"** —
  **RE-VALIDATED on M4 silicon**, and strengthened from a no-backward-jump
  structural observation to a functional single-winner proof under real
  contention (EXP-0018 did not run multi-lane CAS contention).
  Threadgroup-scope op-selector position — **EXP-0018 marked this
  *inferred*; this experiment RE-VALIDATES it as structural fact on M4**
  (the `atomic_tg` instruction form and its op-selector byte, table above).
- **EXP-0018 "uniform-address atomic gets a compiler SIMD-reduce
  optimization"** — **RE-VALIDATED on M4 silicon, and its boundary
  condition sharpened** (static-literal vs runtime-uniform address; see
  ATOM-05/06 above). EXP-0018 tested only the literal case.
- **EXP-0018 "64-bit atomics: only the void min/max form exists"** —
  **RE-VALIDATED on M4** (re-tested interactively, same rejections) **and
  sharpened**: `atomic_load_explicit` on `atomic_ulong` is also rejected,
  which EXP-0018 did not test.
- **EXP-0051 "this Metal build rejects acquire/release identifiers, accepts
  relaxed + seq-cst at the fence level"** — the **RMW-call-site** rejection
  pattern (not tested by EXP-0051, which tested standalone fences/loads)
  is **new M4 evidence from this experiment**, not a re-validation of
  EXP-0051 itself (different call site).

## Limitations and confounders (see `PRE_REGISTRATION.md` for the full list)

- Structural (tokenization) findings are scoped to the exact toolchain
  (`sw_vers`/`xcrun --version` recorded in every `00_inputs.json`); they are
  not guaranteed stable across macOS/Metal versions.
- `tools/agx-isa` field-NAME splits for the newly observed `atomic_tg`/
  `atomic_mem`/`scoreboard_fence`/`tg_atomic_prep` forms are the
  disassembler's placeholder guesses; this experiment treats only
  instruction-family/opcode presence and the op-selector byte (which
  exactly reproduces EXP-0018's independently-derived A18 value) as
  validated, not the other named sub-fields.
- No A18 Pro claim anywhere in this document; every finding is M4-only
  unless explicitly marked "RE-VALIDATED"/"INHERITED" above with its exact
  provenance.
- ATOM-07 through ATOM-11 are open; see "Deferred" above.
- `il_chain48` at N=65536 is a strong but finite adversarial stress bound,
  not an exhaustive proof that no register-pressure regime could ever
  expose an interlock hazard.

## Post-capture bug-fix and recapture (full account: `PROGRESS.md`)

The first capture pair surfaced a genuine `--init` byte-order bug in
`harness/atomics_probe.m` (fixed: `parse_le_hex()`), a `case_order_sensitive_keys`
field-name bug (`target_final_hex` vs `tg_result_hex` for threadgroup
exchange/CAS), an ordering-probe diagnostic-substring bug, and a
no-return-form invariant bug — all four mechanical, zero discretion over
the correct fix, and none discovered by looking at what answer was
"wanted." Nothing had been promoted at that point, so the flawed run pair
was discarded (not laundered) and the full 56-case matrix was **recaptured
from scratch** under the same run-ids from byte-identical post-fix source.
`CAPTURE_CONTRACT.json`'s `amendment_2026-08-27` key documents this
verbatim. The results and verdicts in this document are exclusively from
the clean recapture.

## Verification

```sh
python3 -B verify.py --selftest      # PASS (10 checks)
python3 -B verify.py --seqtest       # PASS (11 state/gate combinations)
python3 -B verify.py --captured      # PASS
python3 -B analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02 --write
  # cross_run_gate.pass=true, provenance_gate.pass=true, verdict_counts={"PASS":56,"FAIL":0}
sh analysis/tokenize_structural.sh   # regenerates analysis/tokenize_evidence.txt
```

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / OWN-SHADER
Inputs inspected: authored MSL (kernels/atomics.metal, kernels/atomics_ordering.metal,
  kernels/interlock.metal, kernels/interlock_tex.metal), authored ObjC harnesses
  (harness/atomics_probe.m, harness/interlock_probe.m, harness/interlock_tex_probe.m),
  authored Python (casematrix.py, run.py, analysis.py, verify.py), read-only
  use of tools/shdump and tools/agx-isa (unmodified) on our own compiled kernel bytes
Apple binary introspection: NONE
Apple auxiliary/helper code inspection: NONE
Command/BO scan or pointer following beyond our own allocated buffers: NONE
Target qualification: local M4/G16G only; no A18 Pro claim; A18-era claims this
  document re-validates or inherits are labeled individually above
Reproduction: README.md command sequence
Evidence: raw/m4-20260827-run01/, raw/m4-20260827-run02/, analysis.json,
  analysis/tokenize_evidence.txt, manifest.json
```
