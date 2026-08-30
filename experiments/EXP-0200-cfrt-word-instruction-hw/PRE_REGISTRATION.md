# EXP-0200 — PRE-REGISTRATION

**Frozen before any build or gated capture.** Target: Apple A18 Pro / **G17P**
(`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6, Metal family
Apple9), `users-MacBook-Neo.local` / `192.168.170.254`. **Nothing runs on the M4.**
Clean-room category: **OWN-SHADER + HW-PROBE**. Every byte spliced, decoded or
inspected is the compiled form of our own MSL in `kernels/` and in
`t1/kernels/`. No Apple binary is disassembled or introspected.

---

## 1. The two questions

**Target 1 — the gated pair EXP-0187 could not finish.** EXP-0187 froze a
25-arm contract for `n4_rt_word.dst`, completed **one** run of it, and stopped:
its `RESULTS.md` §5 says the field is *"one clean gated pair away from a
verdict"*. That contract is carried into `t1/` **byte-for-byte** — every one of
its 27 blobs re-hashed against EXP-0187's own `CAPTURE_CONTRACT.json` by
`harness/verify_remote200.py`, which **refuses to proceed on any difference** —
and run twice. Nothing about it is redesigned here. Its own frozen gate
(`t1/analysis/verdicts.py`) computes the verdict, and this experiment may not
touch it.

**Target 2 — the `_instruction` question, which is the one that is actually
blocked.** `n1_word`, `n2_compact2`, `n3_word`, `rtq_pred`, `n4_cf_word` and
`n4_rt_word` are all `_instruction: tokenization-only`. That label means we can
**decode** the encoding and have never shown the hardware does what the
descriptor claims. Decoding the compiler's own bytes again cannot clear it, and
neither can a round trip: `assert_round_trip()` is symmetric across encode and
decode, and EXP-0170 showed the repo's own suite passes **173 cases, 0
failures** against an assembler that could not clear a bit.

Read the descriptors and the claim they make about the hardware is a **LENGTH**:
*"length 2 / 4; +N lands on the next op leader in every corpus occurrence"*.
Corpus framing is a statement about our tokenizer agreeing with itself. **No
experiment has ever asked the silicon what length it consumes at these
encodings.** Target 2 asks it, by generating the encoding ourselves at program
points the compiler never chose.

## 2. The instrument: a stop-ruler calibrated on hardware-run words

Three instructions already carry `_instruction: hardware-run` in
`validation.json`, with known lengths:

| word | bytes | length | label / evidence |
|---|---|---|---|
| `stop` | `0e 00 00 00` | 4 | `hardware-run`, A18 — *"corrupting the whole word is a no-op; the program still terminates correctly"* (EXP-0003/0010), so its 24-bit body is free filler |
| `mov_imm` | `0c 20` | 2 | `hardware-run`, G16G+G17P — 196,114 generated instances (EXP-0031/0140/0153/0167/0168) |
| `icmp_pred` | `0a ..` | 6 | `hardware-run`, M4+A18 (EXP-0104/0115/0112) |

Take an **8-byte hole**: a run of consecutive walked instructions summing to
exactly 8 bytes, on the executed path, **after** the store of the integrity
sentinel `out[1] = 7.5` and **before** the store of the result `out[0]`.
Overwrite the whole hole with

```
<candidate word W>  ++  stop  ++  zero padding
```

and read back the **poisoned** output buffer.

* Hardware consumes exactly `len(W)` at W's encoding → the planted `stop` is the
  next instruction decoded → the program halts → `out[0]` still holds its own
  poison `0xDEADBEEF` while `out[1]` holds `7.5`. Outcome **`not_written`**:
  *the program ran, and our word did not eat the terminator*.
* Hardware consumes **more** than `len(W)` → the `stop` is swallowed → execution
  reaches the original store → `out[0]` is **written**.

This is why the buffer must be poisoned rather than zeroed: the entire
observable is "the result slot was never written", which against a zeroed buffer
is indistinguishable from "wrote 0" — the silent-zero failure mode this ISA
produces by default.

**Two anchors calibrate the ruler at the same stop offset**, so every reading is
a contrast rather than an absolute:

| fill | bytes | stop at | prediction |
|---|---|---|---|
| `A_mov2` | `0c 20` ++ stop ++ `00 00` | +2 | `not_written` (known 2-byte word) |
| `A_icmp6` | `0a 00` ++ stop ++ `00 00` | +2 | **`written`** (known 6-byte word swallows the terminator) |
| `A_ifpush4` | `0f 05 00 54` ++ stop | +4 | `not_written` (known 4-byte word) |
| `C_reach` | stop ++ `00`×4 | +0 | `not_written` (reachability) |

`A_icmp6` is the conjunct that stops this from being a test that cannot fail: if
a six-byte word does **not** hide the terminator, the ruler is blind and no
length claim may be made from that hole.

## 3. Falsifiable hypotheses

* **H1 (length).** For each of the six words, the hardware consumes exactly the
  number of bytes `db.json` records: 2 for `n1_word` / `n2_compact2` /
  `n3_word`, 4 for `rtq_pred` / `n4_cf_word` / `n4_rt_word`.
  **Expected:** at every admitted hole, the word's ruler fill reads
  `not_written`, exactly as `A_mov2` (2-byte candidates) or `A_ifpush4`
  (4-byte candidates) does at the same offset.
  **Refuter A:** an admitted hole where the word reads `written` while its
  anchor reads `not_written` — its consumption is longer than claimed, and
  `db.json`'s length is wrong. *One clean refutation outranks any number of
  confirmations and is reported as the result.*
  **Refuter B:** `A_icmp6` reads `not_written` — the ruler cannot see over-read,
  the hole is barred, and if that happens everywhere the experiment returns
  nothing.
  **Refuter C:** `C_reach` reads `written` — the hole is not executed before the
  result store; bar it.
* **H2 (transparency).** Substituting a generated candidate word for a
  *different* word of the same length, at a natural occurrence, leaves the
  carrier's non-zero host oracle intact.
  **Refuter:** the oracle changes or the command buffer faults where the
  same-length anchor (`mov_imm` at a 2-byte hole, `if_push` at a 4-byte hole)
  does not — the word is not architecturally benign there, which is a
  first-class negative.
* **H3 (hazard transfer).** EXP-0187 mapped, on G17P over 512 dense dispatches
  on two carriers with zero exceptions, `n4_rt_word.dst`:
  `fault ⟺ (dst & 0b110) == 0b100`. `DST_VALUES` contains four values that
  satisfy the predicate and twelve that do not, dispatched at **synthesized**
  program points.
  **Expected if the wall is a property of the encoding:** the same four fault.
  **Refuter:** the partition differs at a synthesized site → the wall is a
  property of the *occurrence*, not of the encoding, and EXP-0187's rule does
  not generalise.
* **H4 (a flagged db defect, measured).** `op04_len8` is flagged `emit_unsafe`
  in `db.json` for over-consuming the following leader; our pinned tokenizer
  lengths `04 42 21 80` at **8** bytes. `D_op04_len8` is pre-registered to read
  **`written`** if that is right and **`not_written`** if the hardware consumes
  4. Either answer is publishable; the fill exists so that this gate has a case
  it expects to come out the *other* way.

## 4. Independent / dependent variables

* Independent (target 2): the byte string written into one 8-byte ruler hole, or
  into one natural 2/4-byte hole. One fill per dispatch; nothing else in the
  program changes.
* Dependent: `out[0]` (written / not written / value), the integrity sentinel
  `out[1]`, the poison tail `out[2..3]`, command-buffer status, the OS
  fault-classification string, and the pinned tokenizer's reading of the bytes
  we wrote.
* Independent (target 1): unchanged from EXP-0187 §3.

## 5. Confounders, and how each is handled

1. **The observable co-varying with the mutation** (protocol 3a, EXP-0140).
   Excluded by construction: the read-back is the store the compiler already
   emitted; no register, index or value in it derives from the bytes we write.
   EXP-0140 built its read-back out of the swept field and a *correct* result
   was therefore a constant vector by construction; nothing here can do that.
2. **A control that cannot fail.** Every ruler hole carries `C_reach` (must read
   `not_written`) **and** `A_icmp6` (must read `written`). They fail in opposite
   directions, so a hole that passes both has demonstrated detection power in
   both directions before any candidate is read.
3. **An INERT verdict with no detection-power conjunct** (protocol 5a,
   DEF-0190-1). Not applicable in form — no verdict here is "the bit does
   nothing" — and the admission rule is the conjunct anyway: a hole whose
   controls did not fire supports **no** verdict, confirming or refuting.
4. **False hangs from a watchdog timeout** (protocol 3d). The runner is
   EXP-0187's `saferunner187.py` over the pinned upstreamed
   `tools/agxtest/saferunner.py`, one reader thread per child; a malformed
   response is a **measurement failure with the raw lines kept**, never a hang,
   and is removed from agreement and from the dispatched count.
5. **A hang budget hiding a contiguous hazard** (protocol 3c). **There is no
   abort path.** Every fill of every arm is dispatched, including the four
   `DST_VALUES` that EXP-0187's predicate says will fault.
6. **Silent zeros and dispatches that wrote nothing** (protocol 7). Poisoned
   read-back, an independent integrity sentinel, `InnocentVictim` retried first,
   majority-of-3 on every non-OK case, and a sentinel-missing dispatch scored
   `invalid_run` and re-run — never `silent_zero`, never `not_written`.
7. **Movement that is really a different instruction.** The pinned tokenizer's
   reading of the mutated bytes is recorded on every case. (For target 2 this is
   *expected* to change — we are deliberately writing a different instruction —
   so it is recorded as documentation, and the verdict never rests on it.)
8. **Aliased fills** — nominally different cases that assemble to identical
   bytes, so the oracle describes a program that never ran.
   `analysis/contract200.py encodings` re-derives every fixed encoding from the
   pinned descriptor's own `match` constraints and asserts that **every fill
   within an arm is a distinct byte string**; it runs before the freeze and
   again before each gated run.
9. **A constant oracle.** The host prediction (`not_written` / `written` / `ok`)
   **varies across the fill space** and is derived from the descriptors before
   any dispatch. A fill list that predicted the same thing everywhere would
   describe the carrier, not the encoding.
10. **Sibling contamination.** Concurrent GPU processes are **sampled into
    `raw/<run>/env.json`**, so "the machine was quiet" is a measurement rather
    than a claim. Per protocol §7 this is a *sweep*, for which unlocked
    concurrent running is correct; where a reading rests on a single hard
    outcome it is adjudicated offline from the poisoned buffer and the sentinel
    (EXP-0160's filter), and `RESULTS.md` says which.

## 6. Detection power — the honest statement

The six target words have **no fields at all** except `n4_cf_word.b3` and
`n4_rt_word.dst`, so no same-instruction field control exists for four of them.
Detection power here is **structural, not field-based**, and it comes from three
places, each recorded per hole:

* `C_reach` — a `stop` at +0 must halt the program before the result store.
  This proves the hole is executed *and* that the poisoned observable can see it.
* `A_icmp6` — a known 6-byte word at +0 must hide a terminator at +2. This
  proves over-read is visible at this hole.
* `A_mov2` / `A_ifpush4` — a known 2- and 4-byte word must leave the terminator
  intact. These are the same-offset yardsticks the candidates are read against.

A hole that fails any of these is **barred from supporting any verdict**, and
the count of barred holes is reported. This is EXP-0172's gate rule 3 applied to
an instruction rather than a field.

## 7. Method

**7.1 Carriers.** Six compute carriers authored here (`kernels/k_w200.metal`:
transcendental, select, divergent loop, native half, mixed loads,
threadgroup-barrier) and four `intersection_query` carriers used through
EXP-0187's **verbatim** `t1/kernels/k_rq187.metal`. All ten bind a poisoned
output, write `out[1] = 7.5` first, and have a **non-zero host-computed oracle**
(12.5 / 122 / 111 / 22 / 18 / 30 / 1 / 4 / 11 / 6).

**7.2 Runner.** `agxrun_persist_as` under EXP-0187's pinned safe runner; grid 1 /
tg 1; request timeout 8 s compute, 10 s RT; `CONFIRM_ATTEMPTS = 3`,
`INNOCENT_RETRIES = 3`, `CANARY_RETRIES = 3`.

**7.3 Pre-freeze calibration** (`raw/prefreeze/`, **NO verdict may cite it**).
`analysis/census200.py` compiles every carrier and reports the walk, the
walk-confirmed occurrences of the six target words, and the 8-byte ruler-hole
candidates. `run200.py --probe-holes` then dispatches **only** `C_reach` at each
candidate. This exists because EXP-0184's own pilot changed its arm plan — only
2 of 14 `rt_query_traverse` occurrences turned out to be reachable, and freezing
blind would have produced "a confident, meaningless INERT".

**7.4 Arm-selection rule** (frozen; the docstring of `analysis/gen_arms200.py`
is normative). Ruler holes: admitted iff the probe's baseline was `ok` **and**
`C_reach` read `not_written` with the sentinel intact; at most **2** per
carrier, earliest first, non-overlapping. Transparency holes: walked tokens of
exactly 2 or 4 bytes whose mnemonic is one of the six targets (or
`pad_operand`, admitted as an extra slot, never as a target); at most **2** per
(carrier, mnemonic), earliest first. Every admitted hole gets the **entire**
frozen fill list — no per-arm cap, no hang budget, no outcome-dependent pruning.

**7.5 Frozen fill values.**
`DST_VALUES = {00,01,02,03,04,05,06,07,22,42,44,45,46,7f,80,ff}` — four satisfy
EXP-0187's hazard predicate, twelve do not, and `0x22`/`0x42` are the two the
compiler itself emits.
`B3_VALUES = {00,01,02,04,08,10,20,40,7f,80,ff}` — **sampled, and explicitly not
a `n4_cf_word.b3` field claim.** That field carries a standing decline
(EXP-0172 dispatched 256 values and reported STILL-UNDERPOWERED; EXP-0184
declined re-litigating it), and EXP-0187 separately swept byte+3 of the same
0x04-group word at 16 values with zero movement. These values ride along with
the `_instruction` fills at no extra design cost and are reported as
corroboration only. **No `b3` verdict will be proposed.**

## 8. The gate (implemented by `analysis/verdicts200.py` and nothing else)

1. **Two gated runs**, the same frozen `harness/arms200.json`.
2. **≥ 99 % per-value cross-run agreement** on the outcome partition (outcome +
   the exact observed 32-bit vector), and, on ruler arms,
   `moved >= 2 * disagree AND moved >= 1` — written that way, **not**
   `moved >= 2 * max(disagree, 1)`, the form that cannot promote a width-1 field
   by arithmetic (protocol 5b).
3. **Hole admission** per §6, in **both** runs. Barred holes are counted and
   reported.
4. **Anchor match per stop offset**: a 2-byte candidate is read only where
   `A_mov2` read `not_written`; a 4-byte candidate only where `A_ifpush4` did.
5. **Verdict per word.** `LENGTH-CONFIRMED` needs ≥ 2 admitted holes in ≥ 2
   distinct carriers, all reading `not_written`, none reading otherwise.
   Any admitted hole reading `written` against a `not_written` anchor →
   `LENGTH-REFUTED`. Hard outcomes are counted **separately** and never as
   movement. Otherwise `UNDERPOWERED`.
6. **Labels.** `LENGTH-CONFIRMED` → propose `hardware-run` for
   `<mnemonic>._instruction`, with a `range` that states exactly what was
   measured (total bytes consumed, at how many holes, in how many carriers,
   against which anchors) and a `note` recording whether transparency was
   *also* shown. `LENGTH-REFUTED`, `UNDERPOWERED` → the label **stays**
   `tokenization-only`. **No rounding up.**
7. **What this can and cannot see, recorded in the verdict itself.**
   `not_written` for a 2-byte candidate bounds consumption at ≤ 2, and the
   parcel is 2 bytes, so that is exactly 2. For a 4-byte candidate it bounds
   consumption at ≤ 4 and **cannot separate one 4-byte op from two 2-byte
   tokens**, because every 4-byte candidate's trailing half (`00 00`,
   `00 <b3>`, `20 80`) is itself a legal 2-byte encoding. The honest claim is
   **total bytes consumed**, which is the number an emitter needs.
8. Target 1's verdict is computed by `t1/analysis/verdicts.py`, EXP-0187's own
   frozen gate, unmodified.

## 9. Raw record schema

One JSON object per case appended to `raw/<run_id>/sweep.jsonl` (target 2) or
`t1/raw/<run_id>/sweep.jsonl` (target 1), flush+fsync'd immediately, never
buffered. Target-2 keys: `carrier, arm, instr, field, value, fill_id, bytes,
hole_off, hole_len, token, observed{vals, vals_u32, sent_u32, sentinel_ok,
tail_ok, tail_u32, unwritten, gputime_ns, status}, oracle{predict,
carrier_oracle}, predict, match, outcome, status, statuses, fault_classes,
innocent_retries, role, note, ts`. Target-1 keys are EXP-0187's, unchanged.

`instr` carries the **mnemonic the fill is evidence about** and `field` is
`_instruction`, so `tools/agx-isa/wave_audit.py` finds the records under the key
it will be given. `value` is a **globally unique integer per (arm, fill)**,
because that audit indexes cross-run agreement by `value` alone and a per-arm
counter would silently pair records from different arms.

`outcome ∈ ok | not_written | silent_zero | wrong_value | fault | hang |
invalid_run | nondeterministic | measurement_failure | carrier_ready |
carrier_start_failed`. Faults, hangs and no-ops are **kept**.

## 10. Environment, timeouts, revision

Recorded in `CAPTURE_CONTRACT.json`: the repo revision **at pre-registration**
(carried forward verbatim by every re-freeze — captures are compared against
that recorded value, never against live `HEAD`), every authored and pinned blob
hash including the whole verbatim `t1/` tree, the target description, and all
timeouts. `harness/verify_remote200.py` re-verifies the hashes **on the device**
as a **separate, unchained step** after every push, and additionally re-checks
`t1/` against EXP-0187's own contract.

## 11. Safety

No abort path (§5.5). If a contiguous hazard appears it is a first-class result
and is reported as a wall, not clipped by a budget — EXP-0187's `dst` wall is
already known and is deliberately re-entered here at synthesized sites.
`macvdmtool` is **forbidden**; if the neo stops answering the experiment STOPS
and reports BLOCKED with where it was.
