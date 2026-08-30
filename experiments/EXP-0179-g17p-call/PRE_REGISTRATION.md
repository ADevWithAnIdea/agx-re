# EXP-0179 — PRE-REGISTRATION

**Frozen:** 2026-08-30, before any case in `raw/g17p_*_run*` is dispatched.
**Target:** Apple A18 Pro / G17P, `users-MacBook-Neo.local`. Device identity is read from
the live device into `00_env.json` on every run and is never taken from a literal here.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (authored by us) and the AGX machine code the public
  newLibraryWithSource: / MTLBinaryArchive API compiled FROM THEM; plus this repository's
  own committed evidence (EXP-0035, EXP-0038, EXP-0117, EXP-0128, EXP-0137, EXP-0140,
  EXP-0153, EXP-0155, EXP-0156, EXP-0160, EXP-0163, EXP-0168, EXP-0169, EXP-0170,
  EXP-0172, EXP-0173, EXP-0174, EXP-0175, EXP-0177, EXP-M4-13, EXP-M4-14).
Apple binary introspection: NONE
```

> **The instruction under test is GENERATED, not spliced.** Every byte of the `call`, of
> the `ret`, of the callee it targets, and of the whole program around them is computed by
> `harness/isa_helpers.py` from the bit geometry `work/frozen/db.json` declares, and
> cross-checked against `isadb.assemble()` by `assert_geometry()`. **No byte of any of them
> is copied out of a compiled shader.** One arm (`S/splice`) additionally mutates a REAL
> compiler-emitted call inside our own compiled `frame.metal`, as an independent second
> method; it is labelled as such everywhere and never substitutes for the generated arms.

---

## 0. The declared clean-room boundary (restated, because this experiment sits next to it)

`docs/P0-P1-CLOSURE.md` P0.8 lists **Apple's inlining heuristic** as a declared clean-room
BOUNDARY, not a gap. This experiment does **not** approach it. We are not characterising,
modelling, or documenting *how Apple's compiler decides to inline*. We author **our own
MSL** and observe, at the level of the machine code produced **from our own source**,
whether an out-of-line call instruction appears. That is CODEX.md's `OWN-SHADER` category
and CLAUDE.md allowed technique 3, verbatim.

The distinction is operational, not cosmetic:

* **Allowed and done here:** "MSL construct X, compiled by the public runtime API, produced
  a program containing a 14-byte `0f 05 …` call" — a fact about *our* program's bytes.
* **Not done here:** any statement of the form "Apple's compiler inlines when <cost model>",
  any attempt to find the threshold, and any inspection of the compiler binary. The census
  reports **per-construct outcomes only**, with no interpolation between them and no claim
  about why a construct inlined.

If a construct inlines, the census records `call: absent` and moves on. It never asks why.

---

## 1. The question

`APPLE9_RE_IMPLEMENTATION_GAPS.md` → `docs/P0-P1-CLOSURE.md` P0.8, ranked blocker #2, as
assembled by EXP-0177 (`analysis/p08_gaps.md` G2):

> `call.{b3,b5,b6,tail}` are `tokenization-only` — "framing only (round-trips; no value
> semantics established)" — and `ret.scoreboard` was declined in advance by EXP-0172.
> **NO CALL CAN BE EMITTED.**

That blocks every out-of-line helper, the entire split prolog/epilog contract EXP-0137
specified, non-leaf frames, and any variant-reduction scheme. EXP-0156 recorded `call` as
**NOT ATTEMPTED** for a *carrier* reason, not a measurement reason (`EXP-0156/RESULTS.md`
§5.3): its frozen 152-byte CF skeleton contained no call, and the only same-length splice
sites would have branched to an address computed from uninitialised state.

**So the question this experiment asks, in the order it asks it:**

1. **Can this ISA make a non-inlined call at all, and which of our own MSL constructs make
   the compiler emit one?** (census — a deliverable on its own)
2. **Can we EMIT one — generate a `call`, a callee and a `ret` from the rules, with zero
   bytes copied from any compiled shader, and have the hardware execute the call, run the
   callee, and return to the right instruction?**
3. **What do `call.b3`, `.b5`, `.b6`, `.tail` and `ret.scoreboard` actually do**, over the
   dense 0..255 range, on ≥2 carriers, in two gated runs?

---

## 2. What is already established, and what this experiment may NOT re-use as its own result

| fact | source | status here |
|---|---|---|
| `call` = 14 B `0f 05 54 1a 8f 00 56 <off> 00`; target = `call_addr + 4 + offset` | EXP-0035, A18, four **backward** call distances | **re-measured by generation on G17P.** Not assumed. |
| `ret` = `8f <linkmode> 54 <sb>`, no encoded target | EXP-0035 + RT-ISA-FIX | assumed only as the STARTING encoding; the return is proven per case by an observable |
| `ret.linkmode` dense 0..255, `hardware-run`, G17P | EXP-0156 | reused as a control; not re-swept |
| args from r10, return in r10 | EXP-0035 | **not used.** This experiment's callee communicates through a register the ABI does not name and through a memory breadcrumb, so no verdict depends on the ABI being right. |
| `43 00 00 01` frame marker before, `0f 06 …` reconverge after | EXP-0035 byte-observation | **treated as HYPOTHESES to test (arm `M/bracket`), not as required scaffolding** |
| `device_load` is ASYNCHRONOUS on G17P (DEF-0169-1) | EXP-0169 | binding: **no `device_load` on any verdict path.** It appears in exactly one arm (`O/order`) where its asynchrony IS the instrument, and that arm's promotion is pre-declined unless a positive control fires. |
| `link_save_restore.{b1,marker,scope}` are match-pinned pseudo-fields; only `dir_offset` is real | EXP-0173 → EXP-0175 (DEF-0170-1) | not swept here; recorded as context for why the non-leaf arm is bounded |
| a round trip is not an emitter gate | EXP-0170 (FIELD-SWEEP-PROTOCOL 3b) | `rt_ok` is recorded per case and **used for nothing** |

---

## 3. Hypotheses (falsifiable)

**H1 — the compiler emits a real out-of-line `call` from our own MSL on the current G17P
toolchain.** At least one authored construct in `kernels/census/` compiles to a program
containing a 14-byte `0f 05 … 8f … ` call and a separate callee region ending in `8f`.
*Refuter:* every construct in the census inlines or is rejected, i.e. no `call` byte
sequence appears in any of our own compiled programs. **That refutation is a first-class
result and is reported as the headline.**

**H2 — a `call` + callee + `ret` can be GENERATED.** A program in which every byte of the
call, of the callee, and of the return is computed from `db.json`'s declared geometry (no
byte copied from any compiled shader) executes: the callee's register write and memory
breadcrumb appear, and control resumes at the instruction after the call.
*Refuter:* the generated call faults, hangs, does not transfer control (callee breadcrumb
still poisoned), or does not return (post-call marker absent while the callee breadcrumb is
present).

**H3 — the target formula is `target = call_addr + 4 + offset`, and holds for a FORWARD
(positive) displacement.** Every call in this repository's corpus is backward, because in
every compiled program the callee precedes the caller. Forward calls are an extrapolation
that Metal never had to emit.
*Refuter:* the offset ladder (§6, arm `T/target`) lands control at `call_addr + C + offset`
for some `C != 4`, or the forward direction does not work at all while the backward one
does.

**H4 — `call.b3` (observed 0x1a) is the SCOPE-KIND of the execution-mask push the call
performs, and `call.b6` (observed 0x56) is its mask-BANK selector.** `call` shares the
`0f 05` leader with `if_push`, whose own descriptor declares byte+2 = `scope` (bank,
`0x54`/`0x56` ping-pong by nesting parity) and byte+3 = `scope_kind` (`0x01` conditional
skip / **`0x1a` loop-iteration scope**). `call` carries `0x54` at byte+2 (pinned in its
`match`) and **`0x1a` at byte+3** — the same value `if_push` calls a scope kind.
*Refuter:* `b3` and `b6` are inert across their dense range in BOTH carriers, or their
effect does not differ between the flat and the mask-nested carrier.

**H5 — `call.b5` and `call.tail` are RESERVED (inert).** Observed constant `0x00`.
*Refuter:* any value of either that changes the dump, the breadcrumb, or the return, in a
run whose validity gate passes.

**H6 — `ret.scoreboard` has NO observable in a carrier that only reads memory after
command-buffer completion.** EXP-0172 measured that the byte *moves* the observation and
correctly declined promotion, because completion flushes and movement therefore proves
general sensitivity, not ordering-specific power. Three experiments have declined this
family for the same reason.
*Refuter (the ONLY thing that would overturn the decline):* in arm `O/order`, the
**filler-length threshold** at which an in-shader-consumed `device_load` has landed
(DEF-0169-1's own instrument: with no wait, 0,0,0,0,2,5,8,8 of 8 registers landed as a
function of filler length alone) **shifts as a function of the `scoreboard` value**, and
shifts the same way in both gated runs. A value that merely breaks the program at every
filler length is general sensitivity and is NOT a refutation.

**H7 (extrapolate-and-test, bounded) — the return address is a hardware STACK, not a single
link register.** If it is a stack, a generated call from inside a callee (depth 2) with NO
`link_save_restore` and no `frame_prologue` still returns correctly. If it is a single
register, the outer return is destroyed.
*Refuter:* either outcome is a result. Both are reportable; this arm is run LAST and under
its own hang budget because a destroyed return address is precisely the "runs forever"
failure FIELD-SWEEP-PROTOCOL §3(c) warns about.

---

## 4. The carriers

**Two carriers, differing in the dimension the fields under test control.** H4 says these
bytes are execution-mask scope/bank selectors. The dimension a scope selector controls is
**mask-stack depth / nesting parity** — so two carriers that differ in the register plan
alone would be one carrier (the EXP-0163 lesson, cited by EXP-0177 G1).

| | `C1 flat` | `C2 nested` |
|---|---|---|
| mask-stack depth at the call | top level, no enclosing push | one `if_push` deep, popped after the call |
| callee | leaf, writes `R_CALLEE`, stores its breadcrumb, `ret` | leaf, writes `R_CALLEE` **and two ladder-independent registers**, stores its breadcrumb, `ret` |
| call displacement | forward, short | forward, long (callee placed further past `stop`) |
| register plan | `idx15` (blind slot r15, pad-masked r13) | `idx7` (blind slot r7, pad-masked r6) |

The two register plans are disjoint in both the blind and the pad-masked slot, so every one
of the 16 slots is genuinely observed in at least one carrier (EXP-0174's construction,
reused). Every case records `blind` and `pad_masked`; the analysis excludes them explicitly
and never draws a verdict from a slot the carrier cannot see.

A third carrier, **`C3 splice`**, mutates the real compiler-emitted call inside our own
compiled `kernels/frame.metal` (`k_chain` → `mid`, the same program EXP-M4-14 spliced on
A18). It is an INDEPENDENT SECOND METHOD for the same fields, run at a reduced value set,
and is reported separately. It is never counted toward the "≥2 carriers" bar for a
generated result, because its call bytes come from a compiled shader.

### Program layout (both generated carriers)

```
  seeds:        mov_imm r0..r15 = SEED_I            (host-known state; no device_load)
  PRE sentinel: store SENT_PRE to W_PRE, restore the scratch register's seed
 [C2 only]      if_push                              (mask-stack depth +1)
  CALL_AT:      call  offset = CALLEE_AT-(CALL_AT+4) <-- THE INSTRUCTION UNDER TEST
 [C2 only]      pop_reconverge
  RET_AT:       mov_imm R_POST = POSTCALL            <-- proves control resumed HERE
                <16-register dump>  <POST sentinel>  <stop>
  LADDER:       mov_imm R_L0=L0; R_L1=L1; R_L2=L2; R_L3=L3   (4 x 2 bytes)
  CALLEE_AT:    mov_imm R_CALLEE = CALLEE_CONST
                store_word(W_CALLEE, R_CALLEE)       <-- MEMORY BREADCRUMB
                ret  (linkmode=0x02 leaf, scoreboard=<swept in arm R>)
                <self-restoring padding to the end of the region>
```

Everything after `stop` is unreachable by fall-through and is entered ONLY by the call.

### Why the observable cannot co-vary with the field under test (FIELD-SWEEP-PROTOCOL 3a)

This is the defect that cost EXP-0140 its result and EXP-0168 had to find. Here it is
excluded **structurally, not by care**:

* **`call` and `ret` have no register operands at all.** Neither descriptor contains a
  `reg`-typed field. There is therefore no value of `b3`, `b5`, `b6`, `tail` or
  `scoreboard` that can name the read-back index register, the data register of any store,
  the sentinel register, or the callee register.
* The read-back is a **fixed list of 16 stores**, `store_word(W_REG0 + 4r, r)` for
  r = 0..15, byte-identical in every case of every arm, plus two sentinel stores and the
  callee breadcrumb store. No store's `data_reg`, `index_reg` or `idx_off` is a function of
  any swept value.
* The three derived observables — `callee_ran`, `returned`, `landing_rung` — are computed
  on the HOST from that fixed dump plus the host-known seed table. No GPU-measured baseline
  enters any oracle (DEF-0169-1's fabricated-movement trap: **there is no
  periodically-refreshed baseline diff anywhere in this experiment**; the baseline is
  recorded for run-integrity only and every oracle is host-computed from `SEED_I`).

### The landing ladder — why a mis-targeted call is *readable* instead of merely fatal

Four 2-byte `mov_imm` rungs immediately precede `CALLEE_AT`, each writing a distinct
non-seed value to a distinct register. Control entering at rung *j* executes rungs *j..3*
and not rungs *< j*, so **the lowest-numbered rung whose register changed identifies the
landing point at 2-byte granularity over an 8-byte window before the callee.** This makes
the `T/target` offset ladder an *instrument* rather than a hazard, and it is what lets a
wrong `b3`/`b5`/`b6` value be classified as "branched somewhere else" instead of just
"program broke".

---

## 5. Independent / controlled variables, and the observable

| | |
|---|---|
| independent | exactly ONE of `call.b3`, `call.b5`, `call.b6`, `call.tail`, `ret.scoreboard`, or (arm `T`) the call `offset`, per case |
| controlled | carrier, register plan, `_agc.main` region length, seed table, ladder values, callee body, the store list, grid/threadgroup, `extmode`, the pinned `db.json`/`isadb.py` snapshot, the poison pattern |
| observable | 16-GPR dump + PRE sentinel + POST sentinel + **callee memory breadcrumb** + 28-word tail poison region, out of a buffer pre-filled with `0xDEADBEEF` before every dispatch |

Derived, all host-computed:

* `callee_ran` — `W_CALLEE != POISON` **and** `regs[R_CALLEE] == CALLEE_CONST`. The memory
  breadcrumb is written *inside* the callee, so it survives a call that never returns.
* `returned` — `regs[R_POST] == POSTCALL`.
* `landing_rung` — lowest *j* with `regs[R_Lj] == Lj`; `None` if no rung fired.
* `collateral` — the set of slots that differ from `SEED_I` and are not explained.

**Outcome mapping** (on top of FIELD-SWEEP-PROTOCOL §4's enum, which is what is written to
`sweep.jsonl`):

| observation | `outcome` | `note` |
|---|---|---|
| `callee_ran && returned && landing_rung == 0 && no collateral` | `ok` | the call worked |
| `!callee_ran && returned && breadcrumb poisoned` | `wrong_value` | `no_call` — fell through |
| `callee_ran && !returned` | `wrong_value` | `no_return` |
| `callee_ran && landing_rung != 0` | `wrong_value` | `mis_target(rung)` |
| `R_CALLEE == 0` where a write was predicted | `silent_zero` | |
| command-buffer error | `fault` | with the OS fault-class string |
| watchdog | `hang` | majority-of-3 first |

`validity` is kept strictly separate from `outcome` (EXP-0168's point): all-poison, a failed
PRE/POST sentinel, a clobbered tail region, or an `InnocentVictim`-class error is
`invalid_*` and is RE-RUN, never scored.

---

## 6. Arms (frozen)

| id | arm | what varies | cases | gated |
|---|---|---|---|---|
| `Z` | `census` | 18 authored MSL constructs, **compile only, no GPU** | 18 | no (deliverable in its own right) |
| `K` | `calib` | pre-freeze carrier calibration (§8) | ~60 | **PRE-FREEZE, never evidence** |
| `T` | `target` | call `offset` = predicted + k, k ∈ {−8,−6,−4,−2,0,+2,+4,+6,+8}, plus `target="ret"` and `target="ladder"` | 2 × 11 | yes |
| `G` | `gen` | **the acceptance-gate arm.** 48 distinct fully generated call displacements × 4 (register plan × mask nesting) combinations = **192 distinct generated calls**, every byte computed from the descriptor geometry | 4 × 48 | yes |
| `M` | `bracket` | presence/absence of the `43 00 00 01` frame marker × presence/absence of the `0f 06 04 02 00 00` reconverge (4 combinations) | 2 × 4 | yes |
| `B3` | `call.b3` | dense 0..255 | 2 × 256 | yes |
| `B5` | `call.b5` | dense 0..255 | 2 × 256 | yes |
| `B6` | `call.b6` | dense 0..255 | 2 × 256 | yes |
| `TL` | `call.tail` | dense 0..255 | 2 × 256 | yes |
| `R` | `ret.scoreboard` | dense 0..255 | 2 × 256 | yes |
| `L` | `ret.linkmode` | control only: {0x02, 0x04, 0x05, 0x12} | 2 × 4 | yes |
| `O` | `order` | `ret.scoreboard` (16 values) × in-callee `device_load` filler length (12 values), 2-D, §9 | 2 × 192 | **promotion pre-declined**, see H6 |
| `S` | `splice` | the same five fields mutated in the REAL compiled call inside our own compiled `kernels/census/c_frame.metal` (`k_chain`) | reduced value set | second method, reported separately, **never counted toward the ≥2-carrier bar for a generated result** |
| `N` | `nested` | depth-2 generated call, no link save/restore (H7) | 2 × 6 | own hang budget, run LAST |
| `F` | `falsifiers` | §7 (F2/F3/F4/F6; F1 and F5 live inside arm `T`) | 2 × 4–5 | must fire every run |

**`harness/cases.py build_cases()` is the authoritative matrix**, and its sha256 is recorded
in `CAPTURE_CONTRACT.json`; the counts above are descriptive. As frozen it emits **3189 cases
per run** (`python3 harness/cases.py` prints the per-arm breakdown). Dense 0..255 is
FIELD-SWEEP-PROTOCOL §3 coverage for an 8-bit field (`w <= 8` → sweep all 2^w values). Arms
are dispatched in the order `G, T, M, B3, B5, B6, TL, R, L, O, F, N` so the **hang-prone arms
run last** and a stopped arm costs the least evidence.

**Every row emitted for every case carries** `values_dispatched`, `distinct_bytes`,
`encodable_range`, `start`, `width`, per the dispatch standard, plus `bytes`, `carrier`,
`plan`, `validity`, `os_class`, `blind`, `pad_masked`, `attempts`, and `rt_ok`
(recorded, used for nothing).

---

## 7. Falsifiers — pre-registered to FAIL

If none of these fires, the sweep proves nothing about the method's ability to see a
difference, and the whole run is void.

| id | construction | pre-registered expectation |
|---|---|---|
| `F1` | `T/target` with k = **−2** (the call aimed 2 bytes EARLY, into the landing ladder) | `landing_rung` must be **3** where the baseline is `None` — the ladder must resolve a 2-byte target shift, and the callee must still run |
| `F2` | the 14 call bytes replaced by 7 × 2-byte `mov_imm(R_PAD, SEED[R_PAD])` no-ops | `callee_ran == false`, breadcrumb still `0xDEADBEEF`, `returned == true` — proves the callee's effect is attributable to the call and to nothing else |
| `F3` | `call` byte+4 forced from `0x8f` to `0x00` (a `match` byte, deliberately outside the swept fields) | must NOT behave like the baseline: fault, hang, or no transfer of control |
| `F4` | `ret` replaced by two `mov_imm` no-ops inside the callee | must NOT return: `callee_ran == true`, `returned == false` (or hang) |
| `F5` | offset set to target the callee's **bare `ret`**, skipping its body entirely (`target="ret"`) | `callee_ran == false`, breadcrumb still `0xDEADBEEF`, `returned == true` — a call to a body-less callee must still return, which tests the return machinery independently of the callee body |
| `F6` | `C2 nested` run with the `if_push` present but the `pop_reconverge` removed | recorded, not predicted — bounds whether an unbalanced mask stack is fatal |

---

## 8. Pre-freeze calibration (`raw/prefreeze/`, NEVER evidence)

Exactly four parameters are permitted to be decided by calibration. They are enumerated
here with their candidate sets, so this is a closed list and not "fill gaps as you go"
(SUBAGENT_BRIEF: an underspecified frozen contract is an automatic STOP). Once measured,
they are written into a **FROZEN ADDENDUM appended to this file and to
`CAPTURE_CONTRACT.json`**, and nothing else in the contract changes.

| # | parameter | candidate set |
|---|---|---|
| 1 | `extmode_or` for `device_store` — the ALU-forwarded data source | `{0x00, 0xC0}` (db.json declares both; EXP-0174 calibrated it) |
| 2 | whether the generated baseline call requires the `43 00 00 01` marker and/or the `0f 06` reconverge to work at all | the 4 combinations of arm `M`; the combination used for the OTHER arms' baseline is whichever is the minimal working one, and arm `M` still sweeps all 4 under the gate |
| 3 | carrier region length — `_agc.main` must be long enough for seeds + call + dump + ladder + callee + padding | fixed by lengthening `kernels/carrier_call.metal`'s FMA chain until `region_len >= required`; the required length is computed, not guessed |
| 4 | whether `C4 jumpover` (a generated forward `jump` over a callee placed BEFORE the call site, giving a BACKWARD displacement) works | if the forward `jump` does not calibrate, the backward-displacement half of arm `T` is **dropped and reported as untested**, not fudged |

Calibration also runs the F1/F2 falsifiers once, so a carrier that cannot see a difference
is caught before the gate rather than after it.

---

## 9. Arm `O` — the ordering observable, and the condition for declining it

`ret.scoreboard` has been declined three times. EXP-0172 stated the reason precisely: its
harness reads memory back **after command-buffer completion**, and completion flushes, so a
byte that changes the observation has demonstrated general sensitivity, not ordering power.

This arm is the only construction that could distinguish the two, and it exists because
DEF-0169-1 handed us an in-shader ordering instrument: on G17P `device_load` is
**asynchronous**, and with no wait the number of registers that had landed was a function
of **filler length alone** (EXP-0169 observed 0,0,0,0,2,5,8,8 of 8).

Construction: the callee issues a `device_load` into `R_LOAD` from a known input buffer,
then *F* filler instructions, then `ret`. The caller stores `R_LOAD` immediately after the
call. The 2-D grid is (`scoreboard` value × *F*).

* **Positive control (must fire, or the arm is void):** at the baseline `scoreboard` value
  there exists a filler length *F\** at which the loaded value has NOT landed and a larger
  *F* at which it has, reproducibly in both runs. If no such threshold exists — the load
  always lands, or never does — **the arm is VOID and `ret.scoreboard` is DECLINED**, in
  the same terms EXP-0172 used, and this is stated plainly in `RESULTS.md`.
* **Promotion condition (pre-registered, narrow):** the threshold *F\** must **shift** as a
  function of the `scoreboard` value, consistently across both gated runs. Only a shift is
  ordering-specific power.
* **NOT a promotion:** a `scoreboard` value that breaks the program at every filler length,
  or that changes the dump in the completion-flushed sense EXP-0172 already measured.

If the arm is void or the threshold does not shift, `ret.scoreboard` is reported
`corpus-correlation` (unchanged) with the decline restated. **We say so plainly rather than
converting a live observation into a promotion after the fact — which is exactly what
pre-registering the decline is for.**

---

## 10. Known confounders and how each is handled

| confounder | handling |
|---|---|
| **(3a) observable co-varying with the field** | structurally impossible: neither `call` nor `ret` has a register-typed field (§4) |
| **(3b) round trip mistaken for an emitter gate** | `rt_ok` recorded, cited nowhere; no verdict reads it |
| **(3c) a contiguous hazard hidden by a per-field hang budget** | **expected here — control flow is where hangs live.** If ≥2 hangs occur at ADJACENT values of one field, the gated arm stops (budget 2) and a NAMED, NON-GATED mapping pass `MAPPING_EXP0179_<field>_hangtolerant` is dispatched over the whole 0..255 range with the budget deliberately overridden, announced in `PROGRESS.md` before it runs, and reported as a mapping result — never merged into the gated verdict |
| **DEF-0169-1 `device_load` asynchrony fabricating movement** | no `device_load` on any verdict path; seeds are `mov_imm`/`falu2i` immediates only; **no oracle is a diff against a refreshed GPU baseline** |
| **stale shared `db.json` on the neo** | `work/frozen/` pin, sha256 in the contract, fail-closed resolver with NO path-search fallback (`isa_helpers._find_isadb`) |
| **a never-moving field promoted on carriers that cannot express it** | the two carriers differ in mask-stack depth, which is the dimension H4 says these fields control; if a field never moves in EITHER, the verdict says so and names the dimension tested |
| **`InnocentVictim` / busy-machine contamination** | poisoned read-back, independent sentinels, OS fault-class string on every non-`ok` case, majority-of-3 before any `fault`/`hang`; sweeps run unlocked per §7, and any CONFIRMATION pass is either run on a coordinated quiet window or adjudicated offline from the poison + sentinel per EXP-0160's filter — and `RESULTS.md` states which |
| **a call that returns into the middle of the dump** | the dump's first instruction is at a known offset; a return to the wrong place shows as a missing `POSTCALL` marker and/or a corrupted store sequence, both visible |
| **compiler-scheduled scratch** | the SYNTH carrier's whole `_agc.main` is replaced, so nothing the compiler scheduled inside it survives; the kernel's declared scratch size is recorded in `00_env.json` and the non-leaf/`N` arm is bounded because we cannot enlarge it |
| **an unbalanced execution-mask stack at `stop`** | arm `M` and `F6` bound it explicitly rather than assuming it |

---

## 11. Promotion gate (binding)

A field is promoted to `hardware-run` only if ALL hold:

1. dense 0..255 dispatched on **≥2 carriers that differ in the dimension the field
   controls**, in **two gated runs** (`run01` forward order, `run02` reverse order);
2. **≥99% per-value cross-run agreement**, counting `validity == "valid"` cases only;
3. **movement ≥ 2 × the disagreement count**;
4. every falsifier in §7 fired in **both** runs;
5. the semantics stated are host-computed from the fixed observable, not from a GPU
   baseline diff;
6. no verdict rests on a blind or pad-masked slot.

A field that is inert across its whole range is promotable only under rule 1's
carrier-dimension clause, and its verdict must name the dimension that was varied.
Anything short of the gate is written as `corpus-correlation`, `single-template-inference`,
`tokenization-only`, or `untested` — the eight labels of `docs/evidence-classification.md`
and nothing else. **`rt_ok` is never cited.**

---

## 12. Safety

* per-request watchdog 8 s; `shdump` 300 s; every SSH command under an `alarm`;
* majority-of-3 before any `fault`/`hang` is recorded; 2 s cooldown after a hang;
* per-arm hang budget 2 → arm STOPS and is reported PARTIAL, except in a declared,
  named mapping pass (§10, FIELD-SWEEP-PROTOCOL 3c);
* arms `N` (depth-2, no link save) and the `T` backward half are **known hang candidates**
  and are announced in `PROGRESS.md` before they run, as §7's courtesy rule asks;
* every case appended and `fsync`ed as it completes — never buffered;
* `PROGRESS.md` entry per milestone; artifacts pulled back from the neo promptly;
* **if the neo stops answering: STOP, report BLOCKED. No scanning. No `macvdmtool`.**

---

## 13. AMENDMENT-01 — the frozen `C2 nested` carrier was MEASURED DEAD (2026-08-30, post-run01)

**Appended, never edited in place.** §4 above stands as frozen; this records what the
hardware said about it and what replaced it.

`run01` (`raw/g17p_20260830_run01/`, retained in full) dispatched 2790 gated cases. Every
one of the **1395 cases on `C2 nested`** came back the same way: status `OK`, the PRE
sentinel written (`0x5A`), the tail poison intact — and **all 16 registers, the POST sentinel
and the callee breadcrumb still `0xDEADBEEF`**. The program ran to the PRE sentinel and
nothing after it executed. The 1395 `C1 flat` cases in the same run are unaffected and are
retained as evidence.

`raw/prefreeze/calib_20260830c_amend/` isolates the cause, and it is a **hardware fact worth
having on its own**:

| construction | result |
|---|---|
| `if_push(scope=0x54, kind=0x01)` (the frozen C2) | **dead** — nothing after it executes |
| `if_push(scope=0x56, kind=0x01)` | **dead** — so it is the KIND, not the bank |
| `if_push(scope=0x54, kind=0x1a)` | **works** — callee ran, returned |
| `if_push(scope=0x56, kind=0x1a)` | **works** — callee ran, returned |

**An unconditional `if_push` with `scope_kind == 0x01` masks off the only lane of a
one-thread dispatch, in both mask banks; `scope_kind == 0x1a` — the same value `call` itself
carries at byte+3 — does not.** That is EXP-0129's failure mode exactly: a carrier that
cannot express what is being asked of it. The right response is to report it and replace the
carrier, not to reinterpret 1395 dead cases as a finding about `call`.

**`C2 nested` becomes `if_push(scope=0x56, scope_kind=0x1a)`** — one mask level deeper, in
the **alternate** bank to the `0x54` the call pins in its own `match`, and alive. That is a
genuine difference in the dimension H4 names, which two carriers differing only in the
register plan would not be.

**Consequences, all recorded rather than absorbed:**
- `run01` is **retained and never reused**; its `C2` half is excluded from every verdict and
  its `C1` half is reported as a third, earlier observation.
- The amended gated pair takes **new run ids** — `g17p_20260830_run03` (forward) and
  `g17p_20260830_run04` (reverse). **`run02` was never dispatched**; the id is burned.
- `harness/isa_helpers.py` and `harness/cases.py` change, so their hashes in
  `CAPTURE_CONTRACT.json` change. The contract is regenerated and the amendment named in it.
  A capture is valid against the hashes recorded for **its own** run.

Two further facts from the same probe, kept because they bound the reconvergence machinery
an emitter has to get right:

- **`pop_reconverge` with `scope_kind == 0x01` does not close a call**: the callee ran but
  control did not return (both banks). `scope_kind == 0x02` returns correctly.
- **The pop's mask BANK is a don't-care** for closing a call: `scope` `0x04`, `0x24` and
  `0x54` all return correctly with `scope_kind == 0x02`.
