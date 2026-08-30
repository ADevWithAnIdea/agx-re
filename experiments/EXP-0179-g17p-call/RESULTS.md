# EXP-0179 — RESULTS

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal and kernels/census/*.metal (authored by us) and the AGX
  machine code the public newLibraryWithSource: / MTLBinaryArchive API compiled FROM THEM.
Apple binary introspection: NONE
Reproduction: README.md section "Reproduction"
Evidence: raw/g17p_20260830_run03, raw/g17p_20260830_run04 (gated pair);
  raw/g17p_20260830_run01 (retained, superseded carrier); raw/prefreeze/** (never a verdict)
```

---

## THE ANSWER, AT THE TOP

> **Can this ISA make a non-inlined call? YES.**
> **Can we EMIT one? YES — measured, not argued.**

**192 distinct calls, every byte generated from `db.json`'s declared field geometry with
ZERO bytes copied from any compiled shader, executed on the A18 Pro: 384 observations across
two gated runs, 0 failures.** In each one a generated `call` transferred control to a
generated callee placed past the program's `stop`, the callee wrote its register and its
memory breadcrumb, a generated `ret` returned, and control resumed at the instruction after
the call — verified against a 16-register dump predicted entirely on the host.

And separately, **the compiler emits one too**: 17 of 27 authored MSL constructs produce an
out-of-line call on the current G17P toolchain.

**Status: COMPLETE.** All fourteen arms have run. Arms `G, T, M, B3, B5, B6, TL, R, L` are gated, arm `S`
(the independent second method — the same four bytes mutated in a **real compiler-emitted**
call) has run as its own two-run pair. Arms `O` (the `ret.scoreboard` ordering observable),
`F` (falsifiers F3/F4/F6) and `N` (the depth-2 no-link-save probe) are **PENDING an exclusive
window** — have now run in a coordinated window; see sections 9, 10 and 11.

### Three results this experiment wants read plainly

**1. `call.b6` refuted itself.** It was measured inert across all 256 values on **both**
generated carriers, reported as a don't-care, and merged on that basis — and then **our own
independent second method overturned it**: on a real compiler-emitted call, bit 1 must be SET
(128 of 256 legal, `encodable_range` 128, not 256). Two generated carriers that share a leaf
callee do not differ in the dimension `b6` controls, however dense the sweep. **This is the
finding that would otherwise have shipped as a wrong emitter constraint.** §3, §8.

**2. `ret.scoreboard` is declined ON A FIRED CONTROL, not on an absent one.** Three earlier
experiments declined this family because they *could not build the ordering observable* — an
inconclusive in the shape of a decline. We built it, **proved it fires**, and the field still
did not move it: one distinct filler-length threshold per arm across all sixteen `scoreboard`
values, byte-identical in both runs. That is the difference between *unknown* and *known not
to*. §11.

**3. A nested call without a properly established scratch frame destroys the outer return and
runs forever.** That is the defensible claim. "The return address is a single link register"
is `INFERRED` and explicitly **not** demonstrated — the confound is ours. §9.

---

## 0. A correction to the record, before anything else

**EXP-0156 recorded `call` as NOT ATTEMPTED for lack of a carrier. That premise was false
when it was written.** Its §5.3 says its frozen CF skeleton contained no call and the only
same-length splice sites would have branched to an address computed from uninitialised
state. But `EXP-0035/kernels/{direct_call,chain,abi}.metal` and
`EXP-0038/kernels/frame.metal` were already in this repository, already compile
`__attribute__((noinline))` helpers into real out-of-line calls, and EXP-0035 already
HW-validated dispatch through them **on G17P**.

So the blocker was never carrier availability. **It was that nobody looked.** That matters
beyond this experiment: P0.8's cell has been reading "queued" for the same reason — the
evidence existed and was unfindable. The census was run anyway, on the current toolchain,
because it costs one compile and inlining behaviour can change under a compiler update.

---

## 1. OBSERVED — the census (arm Z, compile-only, no GPU)

`analysis/call_census.json`, from `raw/prefreeze/census_20260830a` (the 24 frozen constructs)
and `raw/prefreeze/census_20260830b_ext` (3 extension constructs, labelled as such).
Detection was done **two independent ways** — a position-independent raw scan for the
descriptor's own byte-aligned `match` pins, and the pinned tokenizer — and **they agree on
every compiled construct**.

**27 constructs: 15 DIRECT_CALL, 2 INDIRECT_CALL, 9 NO_CALL, 1 REJECTED.**

| construct | outcome |
|---|---|
| C01 plain static helper, tiny body | NO_CALL (control) |
| C02 `always_inline` | NO_CALL (control) |
| C03 `__attribute__((noinline))` | **DIRECT_CALL** |
| C04 `[[gnu::noinline]]` | **DIRECT_CALL** |
| C05 two call sites, same helper | **DIRECT_CALL ×2** |
| C06 noinline `void` helper writing through a device pointer | **DIRECT_CALL** |
| C07 noinline returning `float4` | **DIRECT_CALL** |
| C08 noinline returning a struct | **DIRECT_CALL** |
| C09 noinline, 12 arguments | **DIRECT_CALL** |
| C10 large body (1592 B main), **no attribute** | NO_CALL |
| C11 twelve call sites (1936 B main), **no attribute** | NO_CALL |
| C12 tail self-recursion | **DIRECT_CALL** |
| C13 non-tail self-recursion | **DIRECT_CALL** (2 in `__text`, 1 non-leaf frame) |
| C14 **mutual recursion** | **DIRECT_CALL** (3 in `__text`, 2 non-leaf frames) |
| C15 non-leaf chain | **DIRECT_CALL** (3 calls, 5 rets, 1 non-leaf frame) |
| C16 leaf only | **DIRECT_CALL** |
| C17 three levels deep | **DIRECT_CALL** (3 calls, 5 rets, 2 non-leaf frames) |
| C18 spilling non-leaf | **DIRECT_CALL** |
| C19 `[[visible]]` called directly, plain compute pipeline | **REJECTED** |
| C20 `visible_function_table`, runtime index | **INDIRECT_CALL** |
| C21 `visible_function_table`, constant index | NO_CALL (devirtualized) |
| C22 **address of a plain local function taken** | **INDIRECT_CALL** |
| C23 fragment stage, small noinline helper | NO_CALL |
| C24 vertex stage, small noinline helper | NO_CALL |
| C25 fragment stage, 48-round dependent chain | NO_CALL |
| C26 **vertex stage, 48-round dependent chain** | **DIRECT_CALL** |
| C27 `[[visible]]` through the linked-functions path | NO_CALL (inlined once linked) |

Five of these are **new**, not re-confirmations of EXP-0035:

1. **C14 mutual recursion compiles**, producing three calls and two non-leaf frames.
   EXP-0035 tried only tail self-recursion. **C13 non-tail self-recursion also compiles.**
2. **C22: taking the address of a plain local (non-`[[visible]]`) function compiles and
   lowers to `call_indirect`.** The pre-registration expected a rejection; it was wrong.
3. **C19: a `[[visible]]` function called directly is REJECTED at pipeline creation** —
   `unresolved visible function reference: vadd / Reason: visible function not loaded`. It
   is not an ordinary local call; it needs the linked-functions path. (`api-accept-reject`.)
4. **C10 and C11 — no attribute, 1592 B and 1936 B of code — both inlined.** Nothing tried
   without an explicit attribute produced an out-of-line call.
5. **The fragment stage produced no call in either attempt** (C23, C25): zero `call` bytes
   anywhere in that stage's whole `__text`. The **vertex** stage did, once the helper was
   large enough (C26).

### The declared clean-room boundary

P0.8 lists **Apple's inlining heuristic** as a declared clean-room BOUNDARY. This table is
**per-construct outcomes only**. We authored our own MSL until the instruction we wanted
appeared — CLAUDE.md allowed technique 3, CODEX.md `OWN-SHADER` — and we report what the
bytes compiled *from our own source* contain. **We do not model, threshold, or interpolate
the heuristic, and no Apple binary was inspected.** When a construct inlined, the census
recorded `NO_CALL` and moved on; it never asked why. Item 4 above is therefore a statement
about six specific authored programs, not about a cost model.

---

## 2. OBSERVED — a GENERATED call works, and the target formula is exact on G17P

**Arm G (the acceptance-gate arm).** 48 distinct forward displacements × 4 (register plan ×
mask nesting) combinations = **192 distinct generated calls**, in each of two gated runs.
**384/384 `ok`. Zero faults, zero hangs, zero disagreements.** Every byte of the `call`, the
callee and the `ret` was produced by `isa_helpers.call_bytes()`/`ret_bytes()` from the
pinned descriptor's declared bit positions.

**Arm T (the target formula, measured rather than assumed).** `db.json` records
`target = call_addr + 4 + offset` from EXP-0035, at four **backward** call distances on
**A18**. Every call in this repository's corpus is backward, because in every compiled
program the callee precedes the caller. All of this experiment's calls are **forward**, and
the displacement is computed from the layout rather than copied.

| generated displacement | observed |
|---|---|
| predicted − 8 | landed on ladder rung **0** (host-predicted 0) |
| predicted − 6 | rung **1** |
| predicted − 4 | rung **2** |
| predicted − 2 | rung **3** ← falsifier **F1**, fired in both runs |
| **predicted + 0** | landed exactly on the callee entry; callee ran; returned |
| predicted + 2, + 4 | control transferred *into* the callee body; partial writes; still returned |
| predicted + 6, + 8 | `CMDBUF_ERROR` fault |
| aimed at the callee's bare `ret` | **`ok`**, callee body skipped, **control returned** ← falsifier **F5** |
| aimed at ladder rung 0 | `ok`, rung 0 fired |

So `target = call_addr + 4 + offset` is **exact on G17P, in the forward direction, at 2-byte
granularity across a ±8 window, plus 48 further displacements in arm G.** The extrapolation
the orchestrator asked to have on the record either way: **a positive (forward) displacement
works.**

And: **a call to a body-less callee — a bare `ret` — returns correctly.** The return
machinery is independent of the callee body.

**Arm M (is the compiler's bracket required?).** The compiled form of a call is
`frame_marker (43 00 00 01)` → `call` → `pop_reconverge (0f 06 …)`; we re-confirmed that
shape offline against EXP-0035's own committed `_agc.main` bytes before running anything.
Both carriers, both runs, unanimous:

| | reconverge absent | reconverge present |
|---|---|---|
| **marker absent** | **fault** | **ok** |
| **marker present** | **fault** | **ok** |

> **The `0f 06` reconverge after the call is REQUIRED. The `43 00 00 01` frame marker is
> OPTIONAL.** An emitter must close a call with a `pop_reconverge`; it need not precede it
> with the marker.

That is the direct consequence of `call` reusing the `0f 05` execution-mask **push**: the
push must be popped, and the marker is scaffolding.

---

## 3. OBSERVED — the four `call` bytes and `ret.scoreboard`

Two gated runs (`run03` forward, `run04` reverse), two carriers, **dense 0..255**, 256
distinct encodings per field per carrier, **100.0000% cross-run agreement on every field,
zero disagreements, zero hangs, zero invalid runs**. `analysis/gate.json`,
`analysis/field_verdicts.json`.

### `call.b3` — a BRANCH-TAKEN selector, and only four of its bits are live

The live field is **bits 5:2**, a 4-bit code. **Bits 1:0 and bits 7:6 are inert** — the
outcome is constant within every `bits5:2` code, with **0 violations** over 256 values × 2
carriers × 2 runs.

| `b3[5:2]` | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| call taken | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓** | ✗ | **✓** | **✓** | **✓** | **✓** | **✓** | **✓** | ✗ | **✓** |

The compiler's `0x1a` is code **6**. When a code does not take the call the failure is a
clean **fall-through** — the callee never ran, its breadcrumb was still `0xDEADBEEF`, control
continued at the next instruction and returned normally — **never a fault**. That is the
signature of a branch predicate, and it is exactly the shape `if_push`'s own descriptor calls
`scope_kind` on the instruction that shares its `0f 05` leader. H4 is **supported for `b3`**.

### `call.b5` — two live bits, six inert, and a 64-value legal range

* **bit 1 (`0x02`) set → `CMDBUF_ERROR` fault**, 128 of 128 such values.
* **bit 2 (`0x04`) set with bit 1 clear → the call is not taken.**
* **bits 0, 3, 4, 5, 6, 7 are inert** (perfect 16/16 and 32/32 splits throughout).

> **`call.b5` is legal iff `(b5 & 0x06) == 0` — 64 of 256 encodable values.** The rule holds
> for all 256 values on both carriers in both runs.

### `call.b6` — inert on BOTH generated carriers, and the second method says that was CARRIER BLINDNESS

On both generated carriers the complete observation — all 16 registers, the POST sentinel and
the callee breadcrumb — is **byte-identical for every one of the 256 values in both runs**
(exactly one distinct full observation per carrier). Read alone, that says `b6` is a
don't-care.

**Arm S says otherwise, and arm S is right.** Mutating the same byte in the **real
compiler-emitted call** inside our own compiled `c_frame.metal` (`k_chain`, a **backward**
displacement, a **non-leaf** callee, the compiler's own bracket):

> **`call.b6` bit 1 (`0x02`) MUST BE SET.** 128 of 256 values legal; bits 0 and 2..7 are
> don't-care. 254/256 cross-run agreement; the two disagreements (`0x00`, `0x01`) are
> *nondeterministic across runs* — `0.0` in one, `3.0` in the other — which is what reading an
> unestablished return context looks like. The corpus value `0x56` has bit 1 set.

The generated carriers' callee is a **leaf, entered and left immediately**, so it never
exercises whatever `b6` bit 1 controls. That is the *same* failure shape as `ret.scoreboard`
below — a carrier that cannot ask the question returning a confident "no movement" — except
that here it was caught, by a second method rather than by argument. **The safe emitter rule
is the intersection: set bit 1.**

This is recorded as a narrowed promotion, not as a clean one: `hardware-run` is claimed for
the rule *"bit 1 must be set"*, evidenced on the compiled carrier over two runs, and the
generated carriers' inertness is reported as carrier blindness rather than as a finding.
**H4 is refuted for `b6`**: it is not a mask-bank selector.

### `call.tail` — INERT across the full range, on all three carriers

The complete observation is byte-identical for all 256 values on both generated carriers in
both runs, **and** all 256 values are legal on the real compiler-emitted call (256/256
cross-run agreement). A don't-care in a generated leaf call *and* in a compiled non-leaf call.
The corpus `0x00` is not load-bearing.

### `ret.scoreboard` — DECLINED, exactly as pre-registered

Inert across all 256 values, one distinct full observation per carrier per run. **The
mechanical gate says `promotable`. We decline it anyway**, and this is the reason:

> FIELD-SWEEP-PROTOCOL's own clause says a never-moving field is promotable only if the
> carriers differ **in the dimension the field controls**. `ret.scoreboard` is an
> execution/scoreboard **wait** mask; the dimension it controls is memory/execution
> **ordering** — and neither carrier differs in that dimension. Both return from a leaf
> callee with **no outstanding asynchronous operation to wait on**. Zero movement here means
> *"this carrier cannot ask the question"*, not *"the field is inert"*.

Three prior experiments declined this family and EXP-0172 declined it in advance for the
adjacent reason (its carrier read back after command-buffer completion, which flushes, so
movement proved general sensitivity rather than ordering power). **Arm `O` is the one
construction that could settle it** — the callee issues an asynchronous `device_load`
(DEF-0169-1), then *F* filler instructions, then `ret`; promotion requires the filler-length
threshold to **shift** with the `scoreboard` value in both runs. **Arm O has not run yet.**
`ret.scoreboard` stays `corpus-correlation`.

### `ret.linkmode` — consistency control only

Four values, as a cross-experiment control; **this experiment does not re-label the field**
(EXP-0156's dense G17P sweep stands). `0x02` (leaf) and `0x12` (non-leaf) both return
correctly from a generated leaf callee; `0x04` and `0x05` (CF merge) **do not return** — the
callee ran and control never came back. Consistent with EXP-0035 and EXP-0156.

---

## 4. OBSERVED — the reconvergence machinery, from the amendment probe

`raw/prefreeze/calib_20260830c_amend/`. Pre-freeze, so these are **observations that bound
the machinery**, not gated verdicts — but they are unambiguous and each was a single
controlled change:

* **An unconditional `if_push` with `scope_kind == 0x01` masks off the only lane of a
  one-thread dispatch** — nothing after it executes — **in both mask banks (`0x54`, `0x56`).
  `scope_kind == 0x1a` does not**, in either bank. (`0x1a` is the same value `call` carries
  at byte+3, i.e. `b3` code 6.)
* **`pop_reconverge` with `scope_kind == 0x01` does not close a call**: the callee ran but
  control did not return. `scope_kind == 0x02` returns correctly.
* **The pop's mask BANK is a don't-care** for closing a call: `scope` `0x04`, `0x24` and
  `0x54` all return correctly with `scope_kind == 0x02`.
* An 8-lane dispatch (`grid=8, tg=8`) of the same program returns correctly.

---

## 5. WHAT WENT WRONG, AND WHAT WAS DONE ABOUT IT

**The carrier frozen as `C2 nested` was DEAD, and run01 measured it.** All 1395 of its cases
came back the same way: status `OK`, PRE sentinel written, tail poison intact, and **all 16
registers, the POST sentinel and the callee breadcrumb still `0xDEADBEEF`**. The program ran
to the PRE sentinel and stopped. The cause is the first bullet in §4 — the frozen carrier used
`if_push(scope=0x54, scope_kind=0x01)`, which masks off the only lane.

This is EXP-0129's failure exactly: **a carrier that cannot express what is being asked of
it.** The response, recorded as `PRE_REGISTRATION.md` §13 / `CAPTURE_CONTRACT.json`
`amendment_01`:

* `raw/g17p_20260830_run01` is **retained in full and never reused**. Its `C2` half is
  excluded from every verdict; its `C1` half is a third, earlier observation that agrees with
  the gated pair.
* `C2` became `if_push(scope=0x56, scope_kind=0x1a)` — one mask level deeper, alternate bank,
  and alive.
* The amended pair took **new run ids** (`run03`, `run04`). **`run02` was never dispatched;
  the id is burned.**
* `harness/isa_helpers.py` and `harness/cases.py` changed, so their contract hashes are the
  amended ones; each capture is valid against the hashes in its own `00_env.json`.

**A calibration ordering defect, self-inflicted and caught.** `calib_20260830a` probed
`extmode_or` with `reconverge=False` — which we then discovered *faults* — so both arms came
back `fault` and the choice fell through to a default. `calib_20260830b` re-ran it with the
working bracket; **both `0x00` and `0xC0` produce a correct dump**, and `0x00` was frozen.
`calib_20260830a` is retained, not reused.

---

## 6. WHAT IS NOT ESTABLISHED

* **Whether the return address is a hardware stack or a single link register is `INFERRED`,
  not established** — arm N's confound is ours (no `frame_prologue`, scratch size not under our
  control). See §9 for the named successor experiment.
* **`ret.scoreboard` remains `corpus-correlation`** — declined with the positive control
  FIRING, which is a stronger decline than the three before it. See §3 and §11.
* **`ret.scoreboard` is bounded only for a LEAF return with one outstanding asynchronous
  load.** A non-leaf return, an outstanding store, or a multi-slot wait is untested.
* **No fragment-stage call was produced**, 2 of 2 constructs tried. This is `PARTIAL`, not
  "fragment shaders cannot call": the render-stage extraction may not expose every region.
* **Only forward displacements were generated.** A generated **backward** call needs a
  jump-over carrier, which did not calibrate and was dropped rather than fudged
  (`jumpover_ok: false`). Backward calls remain covered only by EXP-0035's compiled evidence.
* **`b3` codes were mapped for *whether the call is taken*, not for what each code *means*.**
  Eight codes take the branch and eight do not; nothing here distinguishes the eight taking
  codes from one another.
* **The `b5` fault bit was not characterised beyond "it faults."** No fault-class breakdown
  was attempted per value.
* **`call.b6`'s meaning is bounded, not explained.** We know bit 1 must be set and that the
  other seven bits are don't-care; we do not know *what* bit 1 selects, and the generated
  carrier cannot be used to find out.
* Everything here is **G17P**. Nothing is promoted to any other target.

---

## 7. WHAT AN IMPLEMENTER CAN NOW DO THAT THEY COULD NOT BEFORE

```
CALL  = 0f 05 54 <b3> 8f <b5> <b6> <off48 LE, signed> <tail>
        b3   : bits 5:2 must be one of {6,8,9,10,11,12,13,15}; bits 1:0 and 7:6 don't care.
               The compiler uses 0x1a (code 6).
        b5   : (b5 & 0x06) == 0. bit1 faults, bit2 suppresses the branch, rest don't care.
        b6   : bit 1 (0x02) MUST BE SET; bits 0 and 2..7 don't care. 128 of 256 legal.
        off48: target = call_addr + 4 + offset. Forward displacements work.
        tail : DON'T CARE (any of 256).
  MUST be followed by  pop_reconverge  0f 06 <bank> 02 00 00   (bank 0x04/0x24/0x54 all work)
  The 43 00 00 01 frame marker before the call is OPTIONAL.

RET   = 8f <linkmode> 54 <scoreboard>
        linkmode  : 0x02 leaf / 0x12 non-leaf both return; 0x04 / 0x05 do NOT return.
        scoreboard: no observable in a leaf return -- treat as unresolved, use the corpus 0x00.
```

> ⚠ **`call.b6`'s `encodable_range` is 128, not 256.** The first version of this result said
> 256 and was wrong. It is corrected here only because an independent second method
> contradicted it — a dense sweep on two carriers agreeing perfectly was not enough.

`call.b3`, `call.b5`, `call.b6` (narrowed, see §3) and `call.tail` move from
**`tokenization-only`** to **`hardware-run`** (`analysis/field_verdicts.json`). Combined with `call.offset`, which was
already emitter-grade, **every field of `call` is now characterised, and a call can be
emitted.** P0.8 ranked blocker #2 is addressed for `call`; `ret.scoreboard` is not, and is
declined rather than rounded up.

---

## 7a. FIELD-SWEEP-PROTOCOL §3(d) — this experiment is structurally immune, and that is checked, not assumed

Rule §3(d) was added on 2026-08-30: on the shared `persistrun.py`, **the first watchdog timeout
can silently manufacture every "hang" after it**, because an abandoned reader thread wakes on
the replacement child's stdout and races the foreground reader. EXP-0178's pilot recorded three
consecutive false `hang`s with `restarts=99` from one benign case.

**The precondition never occurred here.** Across **every** capture in this experiment — run01,
run03, run04, splice01, splice02, both calibrations and all baselines, 10,484 recorded
dispatch results:

| | |
|---|---|
| status histogram | `OK` **9273**, `CMDBUF_ERROR` **1211** |
| `HANG` observations | **0** |
| `invalid_victim` | **0** |
| malformed / `unpack` errors | **0** |
| per-run `carrier_hangs`, `stopped_arms` | **0**, **none** |

With zero watchdog timeouts there is no abandoned reader thread and no cascade to inherit, so
no result above can be a §3(d) artefact. The 1211 `CMDBUF_ERROR`s are contained per-command-buffer
faults with the OS fault-class string recorded on each — the great majority are `call.b5` bit 1,
which faults by design.

This also means the §3(c) contiguous-hazard machinery, which was pre-registered and built
(`run.py --hang-tolerant`, `analyze.py`'s longest-contiguous-hang-run detector), **never had to
fire**: the longest contiguous hang run is 0 on every field. It is left in place for the pending
`O/F/N` arms, which are where hangs are actually expected.

---

## 8. ARM S — the independent second method, and the one result it overturned

`raw/g17p_20260830_splice01` (forward) and `splice02` (reverse), `analysis/splice_verdicts.json`.

The four `call` bytes were mutated **in the real, compiler-emitted call** inside our own
compiled `kernels/census/c_frame.metal` (`k_chain` → `nl_mid` → two leaves): a different
program, a different register allocation, a **backward** displacement, a **non-leaf** callee,
the compiler's own bracket. One call site at `_agc.main + 36`. The oracle is host-computed and
never touches the GPU — `k_chain(3.0, 5.0) = (3+5) + (3×5) = 23.0f`, exactly representable —
over a buffer poisoned with `0xDEADBEEF`, so *wrote 23* / *wrote something else* / *never ran*
are three distinguishable outcomes. 1024 cases per run, dense 0..255 on each byte.

| field | legal | cross-run agreement | verdict vs the generated arms |
|---|---|---|---|
| `call.b3` | 128/256 | **1.0000** | **identical 16-code table** — reproduced exactly |
| `call.b5` | 64/256 | **1.0000** | `(b5 & 0x06) == 0` holds exactly |
| `call.b6` | 128/256 | 0.9922 | **CONTRADICTS** — bit 1 must be set (see §3) |
| `call.tail` | 256/256 | **1.0000** | inert here too |

Arm S cannot count toward the "≥ 2 carriers" bar for a *generated* result, because its call
bytes come from a compiled shader. What it can do is **contradict** a generated result, which
is worth more than agreeing with one — and it did. Two of the four fields were confirmed on a
third, structurally unrelated carrier; one was corrected.

---

## 9. ARM N — a nested call without a frame destroys the outer return. Bounded, not the clean answer.

`raw/MAPPING_g17p_20260830_run09N_hangtolerant` (forward) and `run10N` (reverse), 8 cases
each. A **declared, named, non-gated mapping pass** (`--hang-tolerant N`, run id containing
`MAPPING_`) per FIELD-SWEEP-PROTOCOL §3(c): an arm whose expected result *is* the hang cannot
be characterised under a budget of 2.

The construction: a generated `call` into a generated callee which itself makes a second
generated `call` to a third region — depth 2 — with **no `frame_prologue` (0x6f)** and,
in one variant, with the compiler's `link_save_restore` idiom around the inner call.

| configuration | forward | reverse |
|---|---|---|
| `link=0 marker=0 pop=1` | **HANG** | **HANG** |
| `link=0 marker=1 pop=1` | **HANG** | **HANG** |
| `link=1 marker=0 pop=1` | **HANG** | **HANG** |
| `link=0 marker=0 pop=0` (retained control) | fault | fault |

**All six correctly-formed depth-2 configurations hang. Adding `link_save_restore` does not
help. Adding the frame marker does not help.**

### What this does and does not establish

**Established (`HW-VALIDATED`):** on G17P, a generated call made from inside a callee, with no
established scratch frame, **destroys the outer return and runs forever**. An implementer must
not emit a bare nested call.

**NOT established — and the confound is ours, so it is stated rather than buried.** Our
synthesized program emits **no `frame_prologue`**, and `link_save_restore` writes to per-thread
**scratch** whose size comes from the carrier kernel's *compiled metadata* — which our
overwritten `_agc.main` does not control and which may be zero. So even the `link=1` arm may
have been saving into unallocated scratch. **Whether a correctly-framed nested call works is
untested here.**

**`INFERRED`, explicitly awaiting falsification: the return address is a single link
register, not a hardware stack.** The measurement above is *consistent with* an inner call
overwriting the outer return; and the compiler emits a `frame_prologue` **plus**
`link_save_restore` around every nested call in every non-leaf callee (EXP-0038; and the
census's C15/C17/C18 show 1–2 non-leaf frames per program), which a hardware stack would make
unnecessary. That is **consistent with**, not **demonstrating**. **Successor experiment:**
establish a real scratch frame — a carrier whose compiled kernel declares scratch, plus a
generated `frame_prologue` with a correct `frame_size` — and re-run these six configurations.

### Was arm N's hang real, or a DEF-0178-1 cascade?

**Measured, not assumed** — `analysis/cascade_N.json`, `analysis/cascade_check.py`:

* **`agreement_by_value` = 1.0000 vs `agreement_by_position` = 0.5000.** The same eight case
  keys give the same outcome class in both dispatch directions; position agreement is chance.
* **The contiguous-suffix cascade signature returns True here and MUST NOT BE CITED.** With
  8 of 8 cases non-OK it is *degenerate* — it cannot come out the other way, which makes it
  worthless exactly like a liveness ladder that cannot fail or a round trip blind to swapped
  operands. It is reported so that nobody quotes it.
* **The discriminator that does carry the weight is positive rather than an absence of
  evidence: the two `pop=0` controls FAULT rather than hang, in both directions, at different
  dispatch positions — index 3 forward, index 0 reverse.** A cascade cannot produce a clean
  `CMDBUF_ERROR` at dispatch index 0, *before any watchdog has fired*; and it cannot produce
  hangs at later indices in one order and earlier indices in the other for the same keys.
* Runner counters: `malformed = 0`, `discarded_lines = 0`, `invalid_victim = 0`; `restarts`
  increments by exactly 3 per hang, which is majority-of-3 working, not a leak.

### Amendment-02 — the first arm N pass was OUR BUG, not a hardware fact

`raw/MAPPING_g17p_20260830_run05N/run06N` (retained, never reused) faulted on all 6 cases in
both runs. The cause was that the depth-2 layout **omitted the `pop_reconverge` after the
inner call** — when **arm M had already measured that a call without a following pop faults**.
Our own earlier result predicted the failure and we had not applied it. Reported as
"depth-2 calls fault", it would have been a wrong hardware claim that looked clean.

The fix is deliberately more than a fix: `depth2_pop` is now a **variable**, and `pop=False`
is **retained as a control that reproduces the fault on purpose**, so arm N's result can never
again be confused with arm M's. `raw/MAPPING_g17p_20260830_run07N` is also retained and marked
defective — a `sync.sh push` returned non-zero inside an `&&` chain, so that pass ran against
the stale pre-amendment harness (6 cases instead of 8). Remote blob hashes are now verified
after every push (`harness/verify_remote.py`, 22/22 matched) instead of trusting `&&`.

---

## 10. ARM F — every falsifier fired, in both directions

`raw/MAPPING_g17p_20260830_run11F_hangtolerant` / `run12F`.

| falsifier | pre-registered expectation | observed |
|---|---|---|
| **F2** call replaced by 2-byte no-ops | callee's effect must vanish | callee never ran, breadcrumb still `0xDEADBEEF`, control returned — **fired** |
| **F3** byte+4 `0x8f` (a `match` byte) → `0x00`/`0xFF` | must not behave like baseline | never baseline: no transfer of control, or fault — **fired** |
| **F4** callee's `ret` replaced by no-ops | must not return | callee **ran** and did **not** return — **fired** |
| **F6** nested carrier, `pop_reconverge` removed | recorded, not predicted | **fault**, both runs — independently confirms arm M |

`analysis/cascade_F.json`: `agreement_by_value` 0.6667, `agreement_by_position` 0.6667 —
**INDISTINGUISHABLE at the 0.20 margin, and reported as such.** With 7 of 9 cases non-OK both
agreements are trivially close, so the clustering test cannot separate them here and claims
nothing. The three cross-run differences are between two *failure modes* (`fault` vs
`wrong_value`) in deliberately-broken programs — never between pass and fail — and every
falsifier was non-baseline in **both** runs, which is what arm F existed to show.

---

## 11. ARM O — the ordering observable WORKED, and `ret.scoreboard` is still declined

`raw/g17p_20260830_run13O` / `run14O`, 384 cases each, `analysis/order_arm.json`.

The callee issues an asynchronous `device_load` into `R_LOAD`, then *F* filler instructions,
then `ret`; the caller reads `R_LOAD` immediately after the call. Grid: 16 `scoreboard` values
× 12 filler lengths × 2 carriers.

**The positive control fired.** DEF-0169-1's asynchrony reproduces as a clean monotone step:

| carrier | not landed | landed from |
|---|---|---|
| `C1_flat` | fillers 0…8 | **10** |
| `C2_nested` | fillers 0…4 | **6** |

Byte-identical in both runs. `C2`'s threshold is *lower* because its extra `if_push` +
`pop_reconverge` already add latency, so fewer explicit fillers are needed — an internal check
that the instrument measures elapsed issue rather than something spurious.

**And across all 16 `scoreboard` values there is exactly ONE distinct threshold per arm. The
threshold does not shift.** `agreement_by_value` 1.0000 vs `agreement_by_position` 0.0000 —
the sharpest value-clustering in the experiment.

> **`ret.scoreboard` is DECLINED. `corpus-correlation`, unchanged.**
>
> This is the strongest form the decline could take. It is not "we could not build the
> observable": we built it, **proved it fires**, and the field did not move it. The
> pre-registered promotion condition — the threshold must *shift* with the `scoreboard`
> value in both runs — was not met, and a working instrument does not get to talk past that.
> Three prior experiments declined this family; this one declines it on much better evidence.

**What remains unknown:** `ret.scoreboard` may be load-bearing in a context this carrier does
not create — a non-leaf return, a return with an outstanding *store* rather than a load, or a
multi-slot wait. The measurement bounds it to "no observable ordering power on a leaf return
with one outstanding asynchronous load", nothing wider.

---

## 12. Final status

| arm | result |
|---|---|
| `Z` census | 27 constructs; 17 emit a call |
| `G` generated | **192 distinct generated calls, 384 observations, 0 failures** |
| `T` target | `call_addr + 4 + offset` exact, forward, ±8 at 2-byte granularity |
| `M` bracket | **pop_reconverge REQUIRED, frame marker OPTIONAL** |
| `B3/B5/B6/TL` | four fields `tokenization-only` → `hardware-run` |
| `R` scoreboard | **declined**, control fired |
| `L` linkmode | control only; EXP-0156's label untouched |
| `S` splice | second method; confirmed 3 fields, **corrected `b6`** |
| `F` falsifiers | all fired, both directions |
| `N` depth-2 | bounded negative; "single link register" `INFERRED` |
| `O` ordering | instrument works; field inert; decline upheld |

**Grand totals across every capture:** 11,660 dispatch results, **0 malformed responses,
0 innocent victims, 0 invalid runs**, and every non-OK outcome value-clustered wherever the
clustering test was able to separate value from position.

---

## 13. Concurrency: unlocked cost nothing measurable

Arms `N`, `F` and `O` ran while **EXP-0178 was mid-pair on `get_sr` and EXP-0180 was cleared
to dispatch**. Across that entire tail:

* **`invalid_victim` = 0** — not one `kIOGPUCommandBufferCallbackErrorInnocentVictim`, nothing
  to segregate, nothing to re-run;
* `malformed` = 0, `discarded_lines` = 0, `n_malformed_validity` = 0;
* every non-OK outcome value-clustered wherever the clustering test could separate value from
  position.

This is the FIELD-SWEEP-PROTOCOL §7 standing policy — sweep unlocked, instrument instead of
serializing — vindicated on the experiment most exposed to it, since arm N deliberately hangs
the device six times per pass. **Six genuine hangs, two neighbours running, zero contamination
observed in either direction.** The exclusive window was requested and granted for arm N and
was, in the event, not needed; that is worth recording so the next agent asks for less.

The one thing that *did* need care was not concurrency but the runner: DEF-0178-1 means the
first watchdog timeout can manufacture every hang after it, and arm N is the one arm whose
expected result is a hang. That was addressed structurally before dispatch (§7a,
`harness/saferunner.py`, `harness/selftest.py` gate G2) rather than by hoping.
