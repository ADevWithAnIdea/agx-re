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

**Status: PARTIAL.** Arms `G, T, M, B3, B5, B6, TL, R, L` are complete and gated. Arms
`O` (the `ret.scoreboard` ordering observable), `F` (falsifiers F3/F4/F6) and `N` (the
depth-2 no-link-save probe) are **PENDING an exclusive window** — they are the declared
hang-prone tail and the orchestrator holds that window.

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

### `call.b6` and `call.tail` — INERT across the full range

For each of these, the **complete observation** — all 16 registers, the POST sentinel and the
callee breadcrumb — is **byte-identical for every one of the 256 values, on both carriers, in
both runs** (exactly **one** distinct full observation per carrier). The corpus values
`0x56` and `0x00` are not load-bearing. An emitter may write any value.

These are promoted under FIELD-SWEEP-PROTOCOL's never-moving clause because the two carriers
differ **in the dimension H4 names for these bytes** — execution-mask stack depth and bank
(`C2` sits one `if_push(scope=0x56, kind=0x1a)` deeper, in the alternate bank to the `0x54`
the call pins in its own `match`). H4 is **refuted for `b6`**: it is not a mask-bank selector,
or if it is, the bank is a don't-care for a call.

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

* **Arms `O`, `F` (F3/F4/F6) and `N` have not run.** They are the declared hang-prone tail
  and await an exclusive window. Until `N` runs, **whether the return address is a hardware
  stack or a single link register is UNKNOWN** — the depth-2, no-`link_save_restore` probe is
  the test.
* **`ret.scoreboard` remains `corpus-correlation`.** See §3.
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
* Arm `S` (mutating the real compiler-emitted call in our own compiled `c_frame.metal`) is
  **not yet run**; the second-method cross-check is outstanding.
* Everything here is **G17P**. Nothing is promoted to any other target.

---

## 7. WHAT AN IMPLEMENTER CAN NOW DO THAT THEY COULD NOT BEFORE

```
CALL  = 0f 05 54 <b3> 8f <b5> <b6> <off48 LE, signed> <tail>
        b3   : bits 5:2 must be one of {6,8,9,10,11,12,13,15}; bits 1:0 and 7:6 don't care.
               The compiler uses 0x1a (code 6).
        b5   : (b5 & 0x06) == 0. bit1 faults, bit2 suppresses the branch, rest don't care.
        b6   : DON'T CARE (any of 256).
        off48: target = call_addr + 4 + offset. Forward displacements work.
        tail : DON'T CARE (any of 256).
  MUST be followed by  pop_reconverge  0f 06 <bank> 02 00 00   (bank 0x04/0x24/0x54 all work)
  The 43 00 00 01 frame marker before the call is OPTIONAL.

RET   = 8f <linkmode> 54 <scoreboard>
        linkmode  : 0x02 leaf / 0x12 non-leaf both return; 0x04 / 0x05 do NOT return.
        scoreboard: no observable in a leaf return -- treat as unresolved, use the corpus 0x00.
```

`call.b3`, `call.b5`, `call.b6` and `call.tail` move from **`tokenization-only`** to
**`hardware-run`** (`analysis/field_verdicts.json`). Combined with `call.offset`, which was
already emitter-grade, **every field of `call` is now characterised, and a call can be
emitted.** P0.8 ranked blocker #2 is addressed for `call`; `ret.scoreboard` is not, and is
declined rather than rounded up.
