# EXP-0085 pre-registration — M4 memory interlock + atomic operation set

**Frozen state: PRE-GPU at freeze time for the contracted two capture runs.**
This registration was drafted alongside interactive build/compile probing of
the harnesses and kernels (recorded below, in "Build-time findings already
folded into this registration") — those probes are pre-registration
methodology (CODEX §3 "smallest authored probe" / discovering the exact
legal MSL surface before freezing the matrix), not the contracted evidence.
**No case in the frozen 56-case matrix below has been captured into `raw/`
at freeze time.** The two required runs (`run01`, `run02`) and all
interpretation happen after this file and `CAPTURE_CONTRACT.json` are
frozen and hashed.

## Scope: which gap-analysis items this increment answers

From `APPLE9_RE_IMPLEMENTATION_GAPS.md`, section "P0 — Memory addressing and
robustness" (MEM-13, MEM-14) and section "P0 — Atomics and synchronization"
(ATOM-01 through ATOM-11, the complete cluster — every item is enumerated
here so none is silently dropped):

| item | covered this increment? | how |
|---|---|---|
| MEM-13 (load/texture/atomic result → ALU, no explicit wait) | **YES** | own-shader zero-slack contention + structural tokenization + adversarial register-pressure stress |
| MEM-14 (ALU-computed source → store/atomic, no explicit wait) | **YES** | own-shader zero-slack + contention invariant + structural tokenization |
| ATOM-01 (device atomic subtract is a direct op selector) | **YES** | functional + structural (op field observed distinct from add) |
| ATOM-02 (threadgroup atomic subtract is a direct op selector) | **YES** | functional (threadgroup-scope contention invariant) |
| ATOM-03 (device atomic return = pre-op value) | **YES** | functional, permutation/prefix invariants under real contention |
| ATOM-04 (compare-exchange = one native transaction, exact success/return semantics) | **YES** | functional single-winner invariant under real contention + structural (single `atomic_mem[cmpxchg]`, no retry loop) |
| ATOM-05 (uniform-address SIMD pre-combine valid for every op Apple emits it for) | **YES, sharpened** | structural tokenization across add/xor/min (reduce path present) vs exchange/cmpxchg (reduce path absent even at a static-uniform address) |
| ATOM-06 (pre-combine disabled when lanes need distinct return values) | **YES, sharpened** | structural + functional: disabled for exchange/cmpxchg (distinct-value ops) unconditionally, AND disabled for RMW ops whenever the address is only *runtime*-uniform (loaded from a buffer) rather than *statically provable* uniform — a boundary condition beyond EXP-0018's original test |
| ATOM-07 (relaxed atomics ordered only by dependencies, no implicit device-wide fence) | **DEFERRED — language-exposure only** | see below |
| ATOM-08 (device fence gives Vulkan/GL-required acquire/release visibility) | **DEFERRED** | see below |
| ATOM-09 (threadgroup barrier = convergence + requested memory fence, coupled) | **DEFERRED** | see below |
| ATOM-10 (device-scope barrier vs standalone device fence: distinct encoding?) | **DEFERRED** | see below |
| ATOM-11 (texture/image ops share the device-buffer fence encoding?) | **DEFERRED** | see below |

**Why ATOM-07..11 are deferred, not silently dropped.** They are questions
about the **fence/barrier instruction family** (`0x07` byte0, EXP-0025's
`threadgroup_barrier`/`scoreboard_fence` group) — a distinct instruction
class from the atomic-RMW op-selector family (`0x67`) this increment
targets. Answering them rigorously requires a dedicated splice campaign
against the `0x07` family's `mem_scope`/`kind` fields (EXP-0025 decoded
`mem_scope` for the threadgroup barrier only; this run's tokenization
additionally observed an unexplained `scoreboard_fence kind=0x22` op emitted
around the compiler's SIMD-reduce lane-election machinery — see
RESULTS.md — that is new raw evidence for a successor, not an answer).
Folding that campaign into this increment would blow the "one variable per
run" / tight-timeline discipline. This experiment's own data (EXP-0051's
API-level relaxed/seq_cst exposure findings, reconfirmed and extended to
device atomic RMW **calls** — not just fences — in the ordering-probe case
below) is recorded as informative input for that successor, explicitly
labeled `STRUCTURAL`/exposure-only, not a closure of ATOM-07/08/09/10/11.
**Recommended successor: the next available EXP-NNNN number (fence/barrier
instruction family, `0x07` byte0), building on EXP-0025's `mem_scope` decode
and this run's `scoreboard_fence kind=0x22` observation. (EXP-0086 was
already claimed by a concurrent session for an unrelated topic at the time
this was written -- pick whatever is next free at dispatch time.)**

## Prior evidence this increment builds on (not redone)

- `EXP-0025-scoreboard/RESULTS.md` (A18 Pro/G17P): established that G17P has
  **no explicit per-op scoreboard wait instruction**; async load/atomic/
  texture results feed consumers directly via a hardware register interlock;
  the only explicit sync op is the `0x07` threadgroup/device-scope barrier.
  **This claim is RE-VALIDATED on M4 in this experiment** (own tokenization
  of M4-compiled bytes, own contention dispatches) — see RESULTS.md
  "A18 claims re-validated on M4 vs inherited".
- `EXP-0018-atomics-subgroup/RESULTS.md` (A18 Pro/G17P): atomic RMW ops are
  single native instructions (not CAS/retry loops); documented the op-field
  table for add/sub/and/or/xor/min/max/exchange/compare-exchange; found the
  uniform-address SIMD pre-combine for a **literal** uniform address; found
  64-bit atomics expose only a min/max form and 32-bit float only
  `fetch_add`. This increment re-validates the pre-combine claim on M4,
  extends it to more ops (min, xor structurally; exchange/cmpxchg as a
  negative control), and sharpens the "which address counts as uniform"
  boundary (see ATOM-05/06 row above).
- `EXP-0051-m4-synchronization-litmus/RESULTS.md` (M4): API-level finding
  that this Metal/OS build accepts relaxed atomics and a seq-cst
  `atomic_thread_fence`, but rejects acquire/release identifiers as
  undeclared. This increment's ordering-probe case (below) checks whether
  that same rejection pattern holds for the **RMW call's own** `memory_order`
  argument (a different language surface than a standalone fence call).

## Build-time findings already folded into this registration

Before freezing the matrix, the harnesses and kernels were compiled and
smoke-run interactively (per CODEX §3, "build the smallest authored probe")
to discover the actual legal MSL surface on this toolchain
(macOS 26.6.2 / Metal 4) rather than guessing from EXP-0018's build. Findings
folded in:

1. `atomic_fetch_add_explicit`/`atomic_fetch_min_explicit`/`atomic_fetch_max_explicit`/
   `atomic_load_explicit` on `atomic_ulong` are **all rejected** by this MSL
   ("`order` argument must be `metal::memory_order_relaxed`" / "requirement
   `_valid_fetch_*_type` was not satisfied"). Only the **void** (no return)
   `atomic_min_explicit`/`atomic_max_explicit` compile for 64-bit. This
   sharpens EXP-0018's "only the void 64-bit atomic_min/max form exists":
   there is **no** way to read the pre-op value of a 64-bit atomic RMW from
   MSL at all (kernels `da_umin64`/`da_umax64` below record 0 in `old_out`
   by construction; functional correctness is checked on the final value
   only, via non-atomic CPU-side readback after GPU completion).
2. `memory_order_seq_cst` on a **device atomic RMW call** (not a standalone
   fence) is rejected ("candidate disabled: `order` argument must be
   `metal::memory_order_relaxed`"); `memory_order_acq_rel` is an **undeclared
   identifier** in this MSL. Both match EXP-0051's fence-level findings,
   extended here to the RMW-call surface (ordering-probe case).
3. A **literal, compile-time-constant** uniform atomic address (`&x[0]`)
   triggers Apple's SIMD-reduce/lane-election optimization (EXP-0018), but
   an address that is merely **runtime**-uniform — computed as
   `x[idx[tid]]` where `idx[]` is loaded from a buffer whose contents happen
   to be all zero — does **not** trigger it, even though every active lane
   addresses the same location. This was not distinguished in EXP-0018 and
   is a genuine new structural finding this experiment carries forward (see
   the "uniform"/"indexed" vs "\*_static0" case split below).

## Falsifiable hypotheses

All targets: local Apple M4 (G16G), macOS 26.6.2 build 25G82, Metal 4, MSL
compiled at runtime (`newLibraryWithSource:`, `fastMathEnabled = NO`).
Independent variable: the frozen 56-case matrix in `CAPTURE_CONTRACT.json`
(`matrix.cases`, mirrored in `casematrix.py::MATRIX`). Every case's exact
expected value/invariant is a **pure function of the case parameters**,
recomputed independently by `analysis.py` from the same fill formulas the
harness uses (never read back from the harness's own claimed expectation).

### MEM-13 — H1

For every kernel where an ALU instruction immediately (zero authored
intervening statements) consumes the result of a `device_load`, a dependent
(gather) `device_load`, a `texture2d::read`, or an `atomic_fetch_add`
result, the consumed value is **exactly** the value the memory/atomic
operation produced — for every lane, under real multi-threadgroup
contention (N up to 65536) and under an artificially high per-thread
register-pressure chain (48 independent loads/thread, `il_chain48`, both at
N=4096 and N=65536 for occupancy stress).
**Refuter:** any lane's ALU-consumed value provably corresponds to a stale
(pre-write) or unrelated register content — observable as: a load/gather
mismatch against the exact expected value; a broken permutation invariant
for `il_atomic_alu` (the recovered `{old}` multiset must equal exactly
`{0..N-1}`, no duplicates/gaps); or any `il_chain48` sum mismatch at any N.
**Adversarial-construction attempt (explicit):** push `il_chain48` to
N=65536 (far beyond EXP-0025's manyload20) so many threadgroups are
concurrently resident and contending for the register file/load-store units
simultaneously; a single wrong sum anywhere in that dispatch is a
constructed violation. A second, independent method — tokenizing the
M4-compiled bytes of `il_load_alu`/`il_gather`/`il_atomic_alu` via
`tools/shdump`+`tools/agx-isa` (read-only) — checks structurally for any
scoreboard/wait-family instruction between producer and consumer.

### MEM-14 — H2

For every kernel where the memory/atomic operation's **source** operand is
computed by an ALU instruction immediately (zero intervening statements)
before the store/atomic (`il_store_src`: `a[i]*b[i]-a[i]` stored with zero
gap; `il_atomic_src`: `a[i]+b[i]` fed directly as the atomic's addend), the
stored/consumed source is exactly the freshly computed value, for every
lane, under the same contention/stress conditions as H1.
**Refuter:** `il_store_src` output mismatch at any lane; `il_atomic_src`
final counter mismatch against `sum(a[i]+b[i]) mod 2^32` (commutative,
order-independent, so this must be exact and byte-identical across both
capture runs). Structural: tokenize `il_store_src`/`il_atomic_src` and check
for a wait/scoreboard instruction between the ALU and the store/atomic.

### ATOM-01/02 — H3

`atomic_fetch_sub_explicit` compiles to a **distinct** operation selector
from `atomic_fetch_add_explicit` (not add-of-negation at the ALU level, not
a rejection), for both device (`da_sub`) and threadgroup (`ta_sub`) scope,
and executes with the exact arithmetic subtract semantics under contention
(final == `(init - sum(deltas)) mod 2^32`, exact and order-independent).
**Refuter:** compile rejection; wrong final value; or (structural,
informative only) a tokenized op-selector byte identical to add's.

### ATOM-03 — H4

Every RMW/exchange kernel's per-lane `old_out` is the value the target held
**immediately before** that lane's operation applied, established two ways:
(a) indexed/own-slot cases, where `old_out[i]` must equal the frozen init
value exactly for every lane (no contention, so this is a tight functional
check with no scheduling freedom); (b) uniform/shared-slot cases, where the
`{old_out} ∪ {final}` multiset must equal exactly `{deltas/tags} ∪ {init}}`
(a bijective linearizable-history proof that tolerates legitimate per-lane
scheduling-order variation — see the "Contention invariants" section).
**Refuter:** any indexed-case `old_out[i] != init`; any uniform-case
multiset mismatch.

### ATOM-04 — H5

`atomic_compare_exchange_weak_explicit` under real contention (N lanes racing
`CAS(expected=init, desired=distinct-tag)` on one location) produces **exactly
one** success among all N lanes, the final value equals that winner's
desired tag, every losing lane's observed `old` equals that same final
value (never a torn or unrelated value), and (structural) the compiled
instruction stream contains a **single** `atomic_mem[cmpxchg]` instruction
with no backward jump / retry loop.
**Refuter:** zero or >1 successes; final != winner's tag; any loser's `old`
!= final; a tokenized backward-branch/loop around the atomic.

### ATOM-05/06 — H6

The compiler emits the SIMD-reduce/lane-election sequence (`simd_reduce` →
`icmp_pred`/`if_push` elect → single `atomic_rmw` → `pop_reconverge` →
broadcast) for add/xor/min **only** when the atomic address is a
compile-time-provable-uniform literal (`*_static0` kernels), **never** for
exchange/compare-exchange at that same literal address, and **never** for
any op (including add) when the address is merely runtime-uniform (loaded
through an `idx[]` buffer, `*_uniform` kernels without `_static0`).
**Refuter:** a tokenized `*_static0` add/xor/min kernel with no
`simd_reduce`; a tokenized `*_static0` exchange/cmpxchg kernel WITH a
`simd_reduce`; a tokenized `*_uniform` (buffer-driven) kernel WITH a
`simd_reduce`. Functional cross-check: every reduce-path and non-reduce-path
kernel must still satisfy its H3/H4/H5 functional invariant regardless of
which path the compiler chose (the optimization must be semantically
invisible).

### ATOM-07 (exposure-only, explicitly not a closure) — H7

`atomic_fetch_add_explicit` with `memory_order_seq_cst` and with
`memory_order_acq_rel` are both rejected by this MSL build at the RMW-call
site (not just at a standalone fence), matching EXP-0051's fence-level
finding. **This is a language-surface observation, not a native
ordering/fence semantics answer** — see the deferral note above.
**Refuter:** either identifier compiles successfully.

## Contention invariants (per CODEX / dispatch requirement)

Every contended case's gate is one of these three run-invariant forms (never
raw per-lane order, which the dispatch instructions explicitly flag as
legitimately varying):

1. **Commutative/associative combine** (add/sub/and/or/xor/min/max, device
   and threadgroup, uniform address): `final == combine(init, deltas[0..N-1])`
   in any order — exact for integer ops (mod 2^32/2^64), and exact for the
   float `fadd` case because every delta and every partial sum stays a
   representable integer under 2^24 by construction (deltas are small
   positive integers, `N <= 65536`, so no summation order can introduce
   rounding — see `harness/atomics_probe.m` fill comment).
2. **Permutation/bijection** (exchange, and the `il_atomic_alu` atomic
   result → ALU probe): the multiset `{per-lane observed "old"} ∪ {final}`
   must equal exactly the multiset `{per-lane written "new"} ∪ {init}` — a
   duplicate or a missing value is a lost-update or a stale/duplicated read.
3. **Single-winner** (compare-exchange): exactly one success; the final value
   and every loser's observed `old` must equal the winner's desired value.

Per fenced class (d): the **raw per-lane arrays** (`old_out_hex`, contended
`target_final_hex`/`success_out`, `il_atomic_alu`'s `out_hex`) are recorded
in `04_results.jsonl` for every case, but the **cross-run byte-identity
gate** excludes exactly the keys `casematrix.py::case_order_sensitive_keys()`
declares for that case (documented per-case in that function's docstring) —
never a blanket exclusion, and never applied to any case's fully
deterministic keys (inputs, `status`, and every non-contended kernel's
entire record). `verify.py --selftest` proves both directions: the gate
PASSES when only a case's declared order-sensitive keys differ, and FAILS
when any other key differs, using a synthetic in-memory pair of "runs" (no
Metal, no real `raw/`).

## Independent/controlled variables and known confounders

- Independent variable: the case matrix (op × width × scope × addressing ×
  thread count). Controlled: kernel source per class, harness fill formulas
  (frozen, documented above), compile options (`fastMathEnabled = NO`),
  dispatch geometry rules (device: `dispatchThreads` with a 256-wide
  threadgroup, N total threads across possibly-many threadgroups;
  threadgroup-scope: exactly one threadgroup of N ≤ 256 threads).
- **GPU scheduling nondeterminism** is expected and pre-registered as
  legitimate for every contended case (see "Contention invariants"); it is
  never treated as a failure by itself.
- **Compiler freedom**: the exact instruction sequence Apple's compiler
  emits for a given MSL idiom may change with toolchain version; structural
  (tokenization) findings are scoped to this exact `sw_vers`/`xcrun
  --version` (recorded in `00_inputs.json` every run), not a permanent ISA
  guarantee.
- **`tools/agx-isa` field-name uncertainty**: several field names the
  disassembler prints for the newly observed `atomic_mem`/`scoreboard_fence`/
  `tg_atomic_prep` forms are the DB's placeholder guesses, not
  HW-splice-validated bit meanings (EXP-0018 already flagged the atomic
  reg-pack tail as *inferred*). This experiment treats the **byte sequence
  and instruction-family/count-level** structural facts (presence/absence
  of `simd_reduce`, presence/absence of a wait-family opcode between
  producer and consumer, total instruction count) as evidence; it does
  **not** promote unvalidated per-bit field splits to documented facts.
- No A18 Pro claim: the A18 is hands-off; every M4 finding here is M4-only
  unless explicitly cited as inherited from an A18-era experiment (EXP-0018/
  EXP-0025), which is itself flagged per-claim in RESULTS.md.

## Standing gate set (frozen; implemented in `verify.py`/`run.py`)

(a) `verify.py --selftest` — synthetic, offline, no Metal/device, runnable
before any GPU work and after every run; proves the matrix schema and the
cross-run gate's PASS/FAIL correctness (see above).
(b) `verify.py --seqtest` — walks PRE_GPU → RUN01_PRESENT → RUN02_PRESENT
against fabricated synthetic `raw/` trees (never the real one), proving
`--preflight`/`--between-runs`/`--captured` are each satisfiable exactly in
their contracted state and fail in every other state, including an
incomplete run01 (short results file) and a STOPped run01.
(c) NON-RECORDED smoke gate — `run.py` builds all three harnesses, then runs
ONE scratch case (`da_add`, uniform, N=8) into `work/<run-id>/smoke_receipt.json`
(never `raw/`); it must parse with `status: ok` and a non-null
`target_final_hex` before the append-only `raw/<run-id>/` tree is created.
(d) No nondeterministic field inside any byte-compared record —
`gputime_ns`/`duration_ms`/`started_utc`/`argv`/`cwd` live **only** in
`05_receipts.jsonl` (`casematrix.py::RECEIPT_KEYS`), structurally excluded
from `RESULT_KEYS_BY_FAMILY`; `verify.py --selftest` asserts this
structurally (no result-family key set intersects the nondeterministic-field
set) in addition to the cross-run gate proof above.

## Timeouts and environment (frozen)

- Per-case subprocess hard timeout: 45 s (in-process `SIGALRM` watchdog at
  `timeout-5` inside each harness as the inner belt, exit 98 on fire).
- Build timeout: 60 s per harness binary. Environment command timeout: 10 s.
- Recorded every run: `sw_vers`, `xcrun --version`, `python`, `machine`, git
  revision + dirty entries, SHA-256 of every authored file
  (`casematrix.py::authored_sha256()`), the frozen matrix itself
  (`01_matrix.json`), and per-case process receipts (`05_receipts.jsonl`).
- Raw schema per run: `00_inputs.json`, `01_matrix.json`, `02_build.json`,
  `04_results.jsonl`, `05_receipts.jsonl`, `06_run_manifest.json`
  (+ `STOP.json` only on a pre-capture or infrastructure abort). Append-only;
  never edited after a run closes.

## Promotion rule

Before any capture: `verify.py --selftest`, `verify.py --seqtest`, then
`verify.py --preflight`. Between runs: `verify.py --between-runs`. Before any
verdict: `analysis.py --run-a ... --run-b ... --write` must report the
cross-run gate and provenance gate both PASS and zero `FAIL` verdicts among
the per-case invariant checks (a `FAIL` is a promotion blocker requiring a
new pre-registered successor, not an in-place fix — CODEX quarantine
discipline), then `verify.py --captured`. Until then, every item in the
scope table above remains **Open** for this configuration.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC (planned)
Inputs inspected: authored MSL (`kernels/`), authored ObjC harnesses
(`harness/`), authored Python (`casematrix.py`/`run.py`/`analysis.py`/
`verify.py`), read-only use of `tools/shdump` and `tools/agx-isa` on our own
compiled bytes
Apple binary introspection: NONE
Reproduction: the command sequence in `README.md`
Evidence: no raw observations exist at freeze; `CAPTURE_CONTRACT.json` is
the frozen grammar; the two runs and `analysis.json` are produced after this
freeze
