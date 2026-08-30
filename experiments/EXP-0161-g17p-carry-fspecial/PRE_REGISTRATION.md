# EXP-0161 — PRE-REGISTRATION (frozen before any build or run)

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, Metal family Apple9, `Mac17,5`), `192.168.10.243`. Every verdict this
experiment produces is labelled `target: G17P`.

Written 2026-08-29, **before** `harness/anchors.py`, `harness/smoke.py` or
`harness/run.py` were executed on the device. The concrete case matrix that follows
from anchor extraction is frozen separately in `CAPTURE_CONTRACT.json` (with its
sha256) **before** the gated runs, per `CODEX.md` step 2.

---

## 1. Question

Two independent questions, both about instructions that are currently **not emittable**
because their descriptor fields are below emitter grade in
`tools/agx-isa/validation.json`.

### Q1 — Is `carry_gen` / `mov_zext16` / `ibfe(offset,width)` emittable on G17P once the
carrier stops being defective?

EXP-0154 swept `carry_gen` (5 blocking fields) and `mov_zext16` (4 blocking fields) on
G17P and **promoted nothing from either**, because both failed their pre-registered
falsifier: forcing byte0 of the instruction under test to `0x00` still reproduced the
entire 16-register baseline. EXP-0154 diagnosed the cause in its own `RESULTS.md` §5:

> "for `CARRY_GEN` the cause is diagnosable and is my own design error: the integer
> seeds (all <= 127) never produce a carry out of the low word, so the carry-generate
> is a no-op in this carrier whatever its encoding. A successor must seed operands that
> actually carry."

That is a **carrier defect, not a hardware fact**. The same defect disables
`mov_zext16` (for a seed `<= 127`, `x & 0xFFFF == x`, so the zero-extend is the
identity and cannot be distinguished from a no-op) and leaves `ibfe.offset` /
`ibfe.width` only weakly live (bits 4..11 of a `<= 127` seed are zero, so the
instruction's own result is 0 for most offsets), which is why EXP-0154 reported its
pre-registered `ibfe` reproduction tests **INCONCLUSIVE**.

### Q2 — What is inside `fspecial`, an instruction nobody has ever swept?

`fspecial` has **11 fields**, all `corpus-correlation` or `tokenization-only`, and it
is flagged `emit_unsafe` in `db.json`. EXP-0138 opened the arm, hit **three
reproducible GPU hangs** at byte+3 (`src`) values 192/193/194 under a 12 s watchdog,
and safety-stopped under FIELD-SWEEP-PROTOCOL §8. EXP-0154 deliberately did not
re-open it. The **safe region (byte+3 < 192) has never been swept at all**, and
neither have the other ten fields.

---

## 2. Hypotheses and falsifiers

Each hypothesis names the observation that refutes it. A refuted hypothesis is reported
as a refuted hypothesis; nothing from a refuted arm is promoted.

### H1 (carrier-fix, the load-bearing one)
With every seeded GPR holding a value with **bit31 set**, the lifted 64-bit low-word
add always carries, so `carry_gen`'s predicate is load-bearing on the observed output
path, and the pre-registered falsifier **fires**.

* **Expected if true:** the case `carry_gen byte0 := 0x00` is scored **not `ok`** —
  the 16-register dump differs from the unmutated anchor's, because the high-word
  add loses the +1.
* **Refuter (F1):** the falsifier is scored `ok` again. Then the carrier is *still*
  defective, this experiment has learned nothing new about `carry_gen`, and **no
  `carry_gen` field is promoted** — exactly as EXP-0154 declined.
* **Second refuter (F1b):** `carry_gen byte+2 := 0x00` scored `ok`. EXP-0038 (A18) and
  EXP-0146 (M4) both recorded that neutralising byte+2 drops the carry; if it does not
  here, the block is not the chain we think it is.

### H2 (`carry_gen` operand model reproduces on G17P)
`carry_gen` is a two-operand unsigned compare `p[dst] = r[srcA] <u r[srcB]`, both
operands packed `(reg<<1)|is32` with an **inert bit 7** (EXP-0146, M4, dense 0..255,
exactly `{0x01,0x81}` accepted for `srcA`).

* **Expected if true (G17P):** over a dense 0..255 sweep of `srcA` and of `srcB`, the
  set of values reproducing the baseline is closed under toggling bit 7, and the
  register a value names is recoverable as `reg = (v >> 1) & 0x3F` from the
  release-on-read zero in the 16-register dump.
* **Refuter:** bit 7 is *not* inert on G17P (the two halves of the value space
  disagree), or the accepted set is not consistent with any `(reg<<1)|is32` map.
  A G16G↔G17P disagreement is a first-class result and is reported as one.

### H3 (`mov_zext16.src_reg` is a real source-register selector)
EXP-0146 found byte+1 **INERT** in the `k_zext16` carrier — all 128 values of bits 0..6
and both values of bit 7 reproduced the zero-extend — and left the question OPEN with
two candidate explanations: (a) byte+1 is not a source-register selector, or (b) the
operand is ALU-forwarded from the immediately preceding `device_load`, making the field
a don't-care *in that instance*.

This experiment separates them: in a SYNTHESIZED program the source is **not** the
immediately preceding load (fifteen loads and a sentinel store intervene, and the
register the field names varies), and every seeded register holds a **distinct** value
with a **distinct low halfword**.

* **Expected if (b):** `src_reg` becomes live here — different values produce
  `r[dst] = seed[j] & 0xFFFF` for different `j`, and the map `v -> j` is recoverable.
* **Expected if (a):** `src_reg` is inert *again*, in a carrier where forwarding cannot
  explain it. That is a positive result about the descriptor, recorded as a `db_defect`.
* **Refuter for the whole arm (F2):** `mov_zext16 byte0 := 0x00` scored `ok`, i.e. the
  instruction is still not observable. Then nothing is promoted.

### H4 (`ibfe`'s opposite out-of-range rules reproduce under a strongly-live carrier)
On the same instruction, `offset` is **LITERAL** (32..63 shift the field out entirely,
result 0) while `width` is taken **MOD 32** (EXP-0139 DEF-0139-2 on M4, dense 0..63;
reproduced on G17P by EXP-0153). EXP-0154 could not test this because its seeds were
`<= 127`.

* **Expected if true:** with 32-bit seeds whose every bit is exercised, a host-computed
  oracle built from `offset` literal + `width` mod 32 fits **more** stable values than
  the alternative models (`offset` mod 32; `width` literal; `width` clamped at 32),
  over a dense 0..63 sweep of each.
* **Refuter:** an alternative model fits at least as many values.

### H5 (`fspecial` safe region)
For byte+3 (`src`) restricted to **0..191**, every `fspecial` field can be swept without
a GPU hang, and the fields divide into (i) operand descriptors whose value selects a
register, (ii) function/precision selectors with a small accepted set, and (iii)
genuinely inert bits.

* **Expected if true:** 0 watchdog hangs in the safe arm; a non-trivial accepted set for
  `dst`, `src`, `src_ext`; and the function map `(fn_hi, fnclass)` from `db.json`
  reproduced on G17P by observing the *computed value* (rsqrt / log2 / sqrt / exp2 /
  round) rather than by decoding bytes.
* **Refuter:** the safe arm hangs, or the unmutated `fspecial` anchor's own result does
  not match the host-computed oracle (then the carrier, not the field, is being
  measured).

### H6 (`fspecial` dangerous region — a BOUNDED NEGATIVE is the intended result)
byte+3 >= 192 (bit 7 set) faults or hangs the command buffer reproducibly, and an
emitter must never set it.

* **Expected if true:** under `~/agxre/gpulease.sh`, values 192.. reproduce EXP-0138's
  faults/hangs.
* **Stop rule (binding, FIELD-SWEEP-PROTOCOL §8 + CLAUDE.md):** **after two GENUINE
  hangs in this arm, the arm STOPS** and is reported PARTIAL with the exact values
  reached. "Genuine" means: watchdog hang or `...ErrorHang`, **confirmed under the
  lease** (§7A), not `...ErrorInnocentVictim`.
* **Refuter:** 192..255 run clean under the lease. Then EXP-0138's three hangs were
  sibling contamination, which would be a significant correction and is reported as one.

### H7 (the §7A discipline itself)
Majority-of-3 in an unlocked bulk sweep is **not** sufficient to call a `fault`
(EXP-0153: five `F_imm_top` cases passed majority-of-3 AND agreed across two
independent unlocked runs, and four of them were **not faults at all** under the
lease).

* **Binding rule for this experiment:** every `fault`/`hang` verdict that would enter
  `analysis/field_verdicts.json` is re-run **5x under `~/agxre/gpulease.sh`** before
  promotion, and the read-back buffer is **poisoned with `0xDEADBEEF`** so a suspect
  case can also be adjudicated offline from the committed digest.

---

## 3. Independent / controlled variables

* **Independent:** one `db.json` field (or one raw byte, where `db.json` models a
  multi-byte field as `raw`) of the instruction under test, one value at a time.
* **Controlled and held fixed:** the seed vector; the carrier MSL and its compilation
  flags; the lifted block's other instructions; dispatch shape (`grid=1, tg=1` for
  SYNTH, `grid=N, tg=N` for INPLACE); the read-back poison; the pinned
  `db.json`/`isadb.py` in `work/frozen/`.
* **Measured:** the full 16-register architectural dump plus PRE/POST sentinels (SYNTH),
  or the functional output vector against a host-computed oracle (INPLACE), plus the
  OS's own command-buffer fault-classification string, verbatim, on every non-OK case.

## 4. Method

Two carrier styles, deliberately different so each load-bearing claim has a second
method:

1. **SYNTH+LIFTED** — `_agc.main` is wholly replaced by a program assembled from
   `tools/agx-isa`'s own field rules: PRE sentinel -> **15 `device_load`s that seed
   r0..r14 from an authored SEED buffer at buffer(1)** -> the lifted block (one field
   mutated) -> a 16-register dump -> POST sentinel -> `stop`. `mov_imm`'s immediate is
   only seven bits, so a seed that carries **cannot** come from `mov_imm`; the load-based
   seed is the entire fix for EXP-0154's defect. No wait instruction is needed:
   db.json's `scoreboard_model` (EXP-0025, HW-validated) records a hardware register
   interlock with >= 20 loads outstanding.
2. **INPLACE** — the naturally compiled `_agc.main` of one of our own probe kernels with
   ONE instruction mutated in place, everything else exactly as the compiler produced
   it, judged against a HOST-COMPUTED functional oracle over an authored input vector.

### Seed vector (the fix, stated exactly)
15 distinct 32-bit seeds, each with **bit 31 set** (so any pair sums past 2^32 and the
lifted low-word add always carries, whichever register pair the anchor names), each with
a **distinct non-zero high halfword** (so `mov_zext16` is not the identity and its
result identifies the source register), a **distinct low halfword**, and a distinct
`extract_bits(v,4,8)` (so `ibfe` identifies its source too). Values are spread across
`[2^31, 2^32)` rather than clustered, so `carry_gen`'s unsigned compare is TRUE for some
register pairs and FALSE for others — without that spread the predicate would be
constant and the sweep could not tell operands apart. The float seed set is 15 distinct
**positive finite** floats, legal inputs to rsqrt/log2/sqrt/exp2.

### Coverage (FIELD-SWEEP-PROTOCOL §3.3)
Field width `w <= 8` -> **all 2^w values, dense**. Wider or `raw` fields -> **byte-wise,
all 256 values per constituent byte**. `fspecial.src` is the sole exception: 0..191
dense in the unlocked arm; 192..255 only under the lease, with the two-hang stop rule.

### Oracle
* SYNTH: the unmutated lifted block's own 16-register dump, captured as the arm's
  baseline before any mutation and re-validated every 250 cases; **plus** a host
  computation of what each register should hold, derived from the authored seed vector
  and the documented semantics — never from an observed GPU output.
* INPLACE: a host-computed function of the authored input vector
  (`(a+b) mod 2^64`, `x & 0xFFFF`, `extract_bits(a,4,8)`, `rsqrt(a)`, ...).

### Anti-contamination (FIELD-SWEEP-PROTOCOL §7 and §7A, binding)
1. Bulk sweeps run **concurrently and unlocked**; the number of sibling GPU experiments
   is recorded in `RESULTS.md`.
2. The OS fault-classification string is recorded verbatim on every non-OK case;
   `...ErrorInnocentVictim`-class failures are flagged `victim` and excluded from the
   cross-run gate.
3. Majority-of-3 before any `fault`/`hang` is written to a case record.
4. **§7A: no `fault`/`hang` verdict is promoted without a 5x re-run under
   `~/agxre/gpulease.sh`.** Cross-run agreement is explicitly NOT accepted as sufficient.
5. The read-back buffer is poisoned with `0xDEADBEEF` before every dispatch, so an
   unwritten word identifies itself and a suspect case can be adjudicated offline.
6. The baseline is re-validated every 250 cases; a baseline failure restarts the child
   runner rather than logging a cascade as data.
7. Two gated runs of the same frozen matrix, executed in **opposite arm order**; a field
   verdict requires agreement across both runs.

### Timeouts and stop rules
* Per-request watchdog: **8 s** (SYNTH/INPLACE bulk), **12 s** in the `fspecial`
  dangerous arm (EXP-0138's value, so a hang there is comparable with EXP-0138's).
* Every remote call wrapped in a host-side hard timeout.
* **Two genuine hangs in one arm stop that arm** and it is reported PARTIAL.
* If the neo stops answering: **STOP, report BLOCKED**. `macvdmtool` is forbidden.

## 5. Known confounders

* **Sibling GPU experiments** on the same device (this is the §7/§7A problem; mitigated
  as above, and the residue is reported, not hidden).
* **Release-on-read**: reading a GPR as a 32-bit source zeroes it. Used deliberately as
  the operand oracle; the sentinels are placed where no descriptor under test can reach
  them (PRE is stored before any seed exists; POST is written after the block ran).
* **r15 is the index register** and is re-zeroed before every store, so a write to r15
  by the instruction under test is NOT observable. Stated as a limitation, not papered over.
* **`db.json` drift**: sibling experiments edit the repo's `tools/agx-isa`. Analysis is
  pinned to `work/frozen/` (sha256 in `CAPTURE_CONTRACT.json`) and `db.json` /
  `validation.json` are NOT edited by this experiment.
* **Our disassembler is not the authority.** A mutated instruction may legitimately fail
  our round trip; `rt_ok` is recorded per case and never used to reject a case.
* **The lifted block is compiler-chosen code.** We document instruction encodings and
  behaviour, never a compiler algorithm.

## 6. What would make this experiment report NOTHING

Stated in advance so a null result is not renegotiated afterwards:
* F1 or F1b fires -> no `carry_gen` promotion.
* F2 fires -> no `mov_zext16` promotion.
* The `fspecial` unmutated anchor does not match its host oracle -> no `fspecial`
  promotion; the arm is reported as a carrier failure.
* An arm hangs twice -> that arm is PARTIAL, with the exact reached values.
* A `fault` that does not survive lease confirmation is recorded as **not** a fault, and
  the corrected reading is reported even though it lowers the headline.

## 7. Clean-room statement

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/probes.metal and kernels/carrier_seed.metal (authored by us
  for this experiment), and the AGX machine code the PUBLIC runtime API compiled from
  that source. tools/{shdump,agxtest,agx-isa} used READ-ONLY and unmodified.
Apple binary introspection: NONE
Reproduction: README.md "Reproduction"
Evidence: raw/<run_id>/sweep.jsonl (append-only), work/
```
