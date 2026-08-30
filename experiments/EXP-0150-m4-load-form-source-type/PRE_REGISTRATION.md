# PRE-REGISTRATION — EXP-0150: load "form" bits and consumer "source-type" bits

**Frozen before any code was written and before any hardware run.** Predictions in
§4 are the record that matters: they were committed to disk before the first case
was assembled. Any later change appears as a numbered AMENDMENT appended to §8,
never as an edit to §1–§7.

Target: **local Apple M4 / G16G only** (`Mac16,10`, macOS 26.6.2 / 25G82, 10 GPU
cores). No A18 Pro (hands-off, user directive 2026-08-27). No M5 evidence.
Closure is measured against **G16G only**.

---

## 1. The question

An external compiler engineer, writing the backend for this hardware, proposes a
model nobody in this repository has tested directly:

> Loads have a **"form"** selected by a **2-bit field** that Metal only ever sets
> to `00` or `11` (so there may be up to 4 forms), and consuming instructions
> carry **"source type" bits** that must **correspond** to the load form of their
> source.

Four committed results converge on it from different directions:

1. **EXP-0101 §1.4** — a `falu2i` consuming a `device_load` result requires
   `mods = 0xC0`: **bits 6+7 together; neither alone works**, and `0x00` fails
   identically to each single bit. That is exactly a "`00` or `11`, never `01`/`10`"
   two-bit pattern.
2. **EXP-0141 §4.2** — `device_store.extmode` accepts exactly **two** values per
   source register R: `2*R` **and** `2*R | 0xC0`. Same bit pair, same `0xC0`.
   (Note the correct attribution: this two-form result is on the **store**'s
   `extmode`, not the load's. `device_load.extmode` was found to require bit 7
   **clear** — `v & 0x80 == 0` — over a dense 256-value sweep. §3 explains why
   that sweep cannot by itself decide the question, and how this experiment does.)
3. **EXP-0141 H2** — `device_store` byte+2 bit 1 is a **data-source selector**:
   clear = ALU-computed, set = direct live load-result. Inert (256/256) when the
   data is ALU-computed, **required** when the source is a forwarded load. A
   consumer-side source-type bit already confirmed.
4. **EXP-0129 / EXP-0126** — the long-standing A18↔M4 "contradiction" resolved as
   **operand PROVENANCE**: an ALU-seeded operand behaves differently from a
   `device_load`-seeded one, independent of dispatch shape.

Plus **DOC-02 D5**: the literal bit-17 / `0x54`↔`0x56` position has at least four
distinct behaviours across instruction families.

**Nobody has ever run `01` or `10` on any of these two-bit pairs.** EXP-0101 tested
`mods ∈ {0, 0x01, 0x02, 0x04, 0x08, 0x40, 0x80, 0xC0}` — eight points, one
provenance, one instruction. That is the gap this experiment closes.

**Why it matters to a driver.** If correspondence holds, a compiler must know, for
*every* operand of *every* load-consuming instruction, which family produced it,
and set two bits accordingly. Getting it wrong yields a **silent zero, not a
fault** (`docs/evidence-classification.md` §5) — a bug that fails quietly and far
from its cause. This affects every instruction a backend emits downstream of a
load.

## 2. Which form axis this experiment tests

`device_load` has at least three candidate "form" axes. This experiment tests
**exactly one** and does not touch the others:

| axis | field | status | tested here? |
|---|---|---|---|
| **the 2-bit pair at `extmode` bits 7:6** | `device_load.extmode[7:6]` (byte+3) | the axis under test | **YES** |
| data-format code | `ld_format` (6 bits, 21 working codes, EXP-0141) | established, separate | **NO — pinned at `0x11`** |
| format tail | `ldform_hi11` (6 bits, 8/64 accepted, EXP-0141) | established, separate | **NO — pinned at `0x10`** |

Consumer-side, the 2-bit pair under test is:

| instruction | field | literal position |
|---|---|---|
| `falu2i` | `mods` bits 7:6 | instruction bits **47:46**, byte+5 bits 7:6 |
| `falu2` | `mod_hi` bits 3:2 | instruction bits **47:46**, byte+5 bits 7:6 — *the same literal bits* |
| `device_store` | `extmode` bits 7:6 | byte+3 bits 7:6 |

Whether the `falu2`/`falu2i` pair and the `device_store` pair are "the same bits"
in any meaningful sense is **H3**, not an assumption.

## 3. The confound this design exists to break

`device_load.extmode` carries **both** the destination register and (per the
hypothesis) possibly the form: EXP-0141 established `extmode = 2*R`, bit 0
don't-care, R reachable 0..63 only.

EXP-0141's dense `L_extmode` sweep **paired** every value `v` with a consumer
reading `r(v>>1)`. That pairing is exactly what makes it unable to answer this
question: under the *register* model `extmode = 0x4E` lands the value in r39 and
the paired consumer reads r39 (pass); under the *form* model it lands in r7 with
form `01` and the paired consumer reads r39 (fail). EXP-0141 recorded a pass, but
its design cannot separate "bit 6 is register bit 5" from "bit 6 is form bit 0
and the paired consumer was pointed at the wrong register".

**This experiment fixes the consumer register and varies the producer's bits 7:6
independently** — and, as the discriminator, runs the same producer values against
*both* candidate consumer registers (the form-model target and the register-model
target). Two competing models, one experiment, disjoint predictions.

## 4. Hypotheses, variables, and PREDICTIONS

All oracles are host-computed in Python from the MSL/ISA semantics we authored,
never read off a GPU run. Every program is fully hand-assembled through
`tools/agx-isa` `isadb.assemble()` — no captured Apple byte string anywhere.

Fixed memory image: `mem[1] = -8.5`, `mem[2] = 7.25`. ALU seeds: `+8.0`, `+2.0`.
Consumer immediate: `+1.5`. All exactly representable in f32; every oracle below
is distinct from every other and from `0.0`.

### H1 — does the producer's `extmode[7:6]` select a form?

**Independent variable:** `device_load.extmode`, dense 0..255, and the four
targeted values `2*R0 | (pf<<6)` for `pf ∈ {00,01,10,11}`.
**Controlled:** consumer register **fixed**; `ld_format`, `ldform_hi11`,
`dst_lo=1`, `dst_ext9=1`, `addr_mode=0x44`, `space=0x10`, `access_desc=0x20` pinned;
consumer `mods = 0xC0`.

- **H1-form:** bits 7:6 are a form field, register = `(extmode>>1) & 0x1F`.
  Predicts: with the consumer fixed at `r7` and `extmode = 0x0E|pf<<6`, the value
  arrives for the *legal* forms (`00`, and `11` if the engineer is right) and the
  consumer at `r39` never sees it.
- **H1-reg:** bits 7:6 are register bit 5 and a must-be-zero bit; there is no form
  field. Predicts: consumer at `r7` works only for `pf=00`; consumer at `r39` works
  only for `pf=01`; `pf=10` and `pf=11` never deliver anywhere.

> **PREDICTION (H1): H1-reg. I predict the 4-form claim is REFUTED on the
> producer side.** Specifically, over the dense 0..255 sweep with the consumer
> pinned at r7, I predict the accepted set is **exactly `{0x0E, 0x0F}`** (2 of
> 256) — `extmode>>1 == 7`, bit 0 don't-care — and every other value is
> `silent_zero` (observed `1.5`), not a fault.
>
> **PREDICTION for the never-tested `01` and `10`:**
> - `pf = 01` (`extmode = 0x4E`): **the load succeeds but delivers to r39**, not
>   r7. Consumer@r7 → `silent_zero (1.5)`; consumer@r39 → `ok (-7.0)`.
> - `pf = 10` (`extmode = 0x8E`): **delivers nowhere.** Both consumer@r7 and
>   consumer@r39 → `silent_zero (1.5)`. (Consistent with EXP-0141's `v & 0x80 == 0`
>   rule; `0x8E>>1 = 71` and `falu2i`'s 6-bit `srcA_reg` reads r7, so this case is
>   *unambiguous* — the two models agree it should land in r7 if it lands at all,
>   and I predict it does not.)
> - `pf = 11` (`extmode = 0xCE`): **delivers nowhere.** Both → `silent_zero`.
>
> If instead `pf=11` delivers to r7 while `pf=01` and `pf=10` do not, the
> engineer's producer-side claim is **CONFIRMED** and my prediction is wrong. I
> record that as the headline if it happens.

### H2 — must the consumer's source-type bits MATCH the producer's form?

**Independent variables:** producer form `pf ∈ {00,01,10,11}` × consumer bits
`cf ∈ {00,01,10,11}` (`mods ∈ {0x00,0x40,0x80,0xC0}`). 4×4, twice (consumer at the
form-model register and at the register-model register).

> **PREDICTION (H2):** the 4×4 matrix **collapses to a single working cell**,
> `(pf=00, cf=11)`, in the consumer@r7 matrix, and to `(pf=01, cf=11)` in the
> consumer@r39 matrix. There is **no diagonal**, because (per H1) there is only one
> legal producer form. Correspondence in the engineer's sense — a 4×4 with a
> working diagonal — is predicted **REFUTED**; what survives is a *provenance*
> correspondence (H4), which is a different and weaker claim.

### H3 — one shared mechanism, or several? Are the bits the same bits?

**Consumers tested:** `falu2i` (bits 47:46 via `mods`), `falu2` (bits 47:46 via
`mod_hi[3:2]` — *the same literal instruction bits*), `device_store` (byte+3 bits
7:6 via `extmode`). Each swept **densely over all 256 values of the carrying
byte**, under each operand provenance.

> **PREDICTION (H3):** `falu2` and `falu2i` behave **identically** at bits 47:46
> (same literal bits, same rule) — for a load-sourced operand the accepted set is
> `{v : v & 0xC0 == 0xC0}` (bits 6+7 set, low bits free except where an already
> known corruptor — `mod_hi` bit 44 = `0x10`, EXP-0105 — removes them), and for an
> ALU-sourced operand it is `{v : v & 0xC0 == 0x00}`.
> `device_store.extmode` is predicted **NOT** the same mechanism: EXP-0141 already
> shows both `2R` and `2R|0xC0` accepted for an *ALU*-sourced store, i.e. the store
> is indifferent where `falu2i` is not.

### H3b — the two-operand question (the sharpest test of `01`/`10`)

`falu2` has two register operands but only one 2-bit pair. Three models:

- **per-operand:** bit 46 = srcA class, bit 47 = srcB class. Then a **mixed**
  `falu2` (srcA load-sourced, srcB ALU-sourced) should require `0x40` or `0x80` —
  *a value that has never worked anywhere in this repository*.
- **instruction-wide:** one class for the whole instruction; any load-sourced
  operand forces `11`.
- **srcA-only:** the pair describes srcA; srcB's class lives in a different field.

> **PREDICTION (H3b): instruction-wide.** For srcA-load/srcB-ALU and for
> srcA-ALU/srcB-load I predict the accepted set is `{v : v & 0xC0 == 0xC0}` in
> both, i.e. the presence of *any* load-sourced operand forces `11`, and neither
> `0x40` nor `0x80` alone ever works. The per-operand model is already disfavoured
> by EXP-0101 (`falu2i` has a single register operand and an immediate, yet still
> needs *both* bits), but it has never been tested with two register operands of
> different provenance, which is what this arm does.
> **If `0x40`/`0x80` works in exactly one of the two mixed arms, the per-operand
> model is CONFIRMED and that is the headline result of this experiment.**
> Refuter for "srcA-only": if the srcA-ALU/srcB-load arm has **no** accepted value
> in all 256, the pair cannot be describing srcB, and srcB's class control lives in
> a field we have not identified — recorded as an open gap, plus the two
> pre-registered secondary sweeps (`opflags` 0..31, `ctrl` 0..127) to look for it.

### H4 — REQUIRED REFUTER: is an ALU-sourced operand indifferent to these bits?

If the bits mean "source type", an operand whose source is *not* a load should
either be indifferent to them, or require the complementary code. If an
ALU-sourced operand is neither — if it behaves exactly like a load-sourced one —
the source-form reading is wrong and these bits mean something else.

> **PREDICTION (H4): NOT indifferent — the complementary code is REQUIRED.**
> `falu2i` with an ALU(`falu2i`)-sourced operand accepts `{v : v & 0xC0 == 0x00}`
> and **fails at `0xC0`**. Basis: EXP-0141's `sweepdefs.py` carries an informal
> pilot note — *"`mods` must be 0 here, not EXP-0101's `0xC0`: `0xC0` is required
> only when the `falu2i` operand is `device_load`-sourced, and it BREAKS this
> `mov_imm`-sourced seed"* — never gated, never swept. This experiment gates and
> densely sweeps it.
> **This is the arm that decides the whole model.** If ALU-sourced turns out
> indifferent (all 256 accepted), then the bits are a load-side interlock hint and
> "source type" is the wrong name. If ALU-sourced *requires* `0x00` while
> load-sourced *requires* `0xC0`, correspondence-to-provenance is CONFIRMED even
> though the 4-form claim (H1/H2) is refuted.

## 5. Outcomes, oracles, and the silent-zero rule

Per case, one JSON record with the `FIELD-SWEEP-PROTOCOL.md` §4 keys.
`outcome ∈ ok | silent_zero | wrong_value | fault | hang | undecodable`, extended
with `nondeterministic` and `invalid_run` (§6) exactly as EXP-0141 used them.

Every case carries a host-computed `oracle` **and** a host-computed
`silent_signature` — the value that results if the operand under test reads as
`0.0`. A wrong field value on this hardware usually yields a **silent zero, not a
fault**; zeros are results and are recorded as `silent_zero`, never skipped.

For the dense `falu2` byte+5 sweeps the oracle **models `srcB_neg` (bit 43)**:
oracle = `A + B` when bit 43 is clear, `A - B` when set (HW-VALIDATED, EXP-0006).
`ok` therefore means "the operand arrived *and* the documented modifier applied";
each record also carries `oracle_variant ∈ {nominal, negated}` so a reader can
apply the stricter rule.

## 6. Robustness — `FIELD-SWEEP-PROTOCOL.md` §7 (binding)

Implemented in `harness/sweeprun.py`, carried over from EXP-0141's hardened
executor:

1. **Majority-of-3 before any `fault`.** No non-`ok` verdict from one observation:
   a case is re-measured until two observations agree or three exist; `fault`/`hang`
   additionally require ≥2 of 3 non-innocent failures. A single failure among
   successes is `nondeterministic`, never `fault`.
2. **OS fault-classification string recorded** on every non-OK
   (`kIOGPUCommandBufferCallbackError*`). `InnocentVictim`-class failures are
   evidence about the *machine*, not the encoding: bounded-retried (6) and
   segregated; they never by themselves make a case a `fault`.
3. **Periodic baseline re-validation.** The unmutated program is re-measured at
   every carrier start/end and every 100 cases. Two consecutive failures =
   declared cascade, stop, record where.
4. **Integrity sentinel through an independent path.** Every synthesised program
   first writes `out[4] = 8.0` via `mov_imm → falu2i(mods=0) → device_store`, a path
   that does not involve the instruction under test. A `STATUS OK` run whose
   sentinel did not land is `invalid_run` and is repeated, never recorded — this
   hardware can return success having executed nothing under sibling GPU load, and
   an all-zero readback is otherwise indistinguishable from a genuine silent zero.
5. **Unique splice-archive path per request**, unlinked after use (reusing one
   path produced ~8 % phantom `CMDBUF_ERROR` in EXP-0141's pilot).
6. **Poisoned read-back buffer.** Every output buffer is pre-filled with
   `0xDEADBEEF` before each dispatch, so "the GPU wrote nothing" is distinguishable
   from "the GPU wrote zero".
7. **Concurrency disclosed.** Sibling GPU-runner processes counted at run start and
   end and reported in `RESULTS.md`.

**Safety.** One hypothesis per dispatch; hard 8 s per-request watchdog; append +
`fflush` + `fsync` every case; `PROGRESS.md` after every milestone. **After two
reproduced hangs in one arm the arm is ABORTED and reported PARTIAL**; after six on
one carrier the carrier is abandoned. Never `macvdmtool`. Never touch the A18.
Never write outside this experiment directory.

## 7. Confounders identified in advance

1. **Destination-register collision.** A swept `extmode` can target the register
   the program uses as the store's index (`rIDX`). Mitigation: every synthesised
   program re-zeroes `rIDX` with a `mov_imm` immediately before the final store, so
   the collision cannot corrupt the observation. Retained as a note regardless.
2. **6-bit consumer register field.** `falu2`/`falu2i` `srcA_reg` is 6 bits with an
   HW-tested-inert top bit (EXP-0099/0119), so a consumer "at r71" really reads r7
   and "at r103" really reads r39. Every record carries the *effective* register.
3. **Register aliasing.** EXP-0112: an ALU register field R in [64,112] aliases
   `r(R mod 64)`; 126/127 fault. All fixed registers stay in 0..63.
4. **`mod_hi` bit 44 is a known silent corruptor** (EXP-0105) and `ctrl` bits 0/1
   are the instruction-length selector (EXP-0119). Both fall inside swept bytes;
   expected to remove values from the accepted set for reasons unrelated to the
   hypothesis, and the mask-rule derivation reports them as such rather than
   folding them into the claim.
5. **Retokenization.** A swept byte may make the program disassemble differently.
   Round-trip is *recorded per case* (`rt`), and asserted (build-time stop) on
   controls only.
6. **`device_store` needs `addr_mode = 0x56` for load-forwarded data** (EXP-0141
   H2); `0x54` silently stores 0. Pinned correctly per arm, and swept in its own
   arm as a positive control.
7. **One carrier shape.** Terminal scalar-32-bit indexed load, compute stage, one
   thread. Fragment stage, vector loads, and the base-sharing load form are **not**
   reached; no claim generalises past that.

## 8. Gate

Two independent gated runs. A field's accepted set is promotable only if both runs
agree **case for case on acceptance** (`ok` vs not-`ok`) and produce the identical
accepted-value set. Disagreements are published next to the claim
(`cross_run_agreement_pct` raw and `cross_run_accept_agreement_pct` gate), never
silently resolved. Labels come from `docs/evidence-classification.md` §2 and
nothing else.

### AMENDMENTS

*(none at freeze time; any change lands here, numbered and dated)*
