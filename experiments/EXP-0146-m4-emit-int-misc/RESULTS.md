# EXP-0146 — RESULTS

**Target:** local **Apple M4 / G16G**, 10 GPU cores, macOS 26.6.x, Metal 4. **A18 deferred**
(never touched). M5 never touched. `macvdmtool` never invoked.

**Clean-room provenance**
```text
Clean-room provenance: OWN-SHADER + HW-PROBE (host oracles from PUBLIC C/MSL/IEEE definitions)
Inputs inspected: kernels/*.metal (authored by us) and their compiled _agc.main bytes only
Apple binary introspection: NONE
Reproduction: README.md "Commands"
Evidence: raw/{pilot,trial00,run01,run02,run03,run04,run05,run06}/ — 58 764 append-only records
```

---

## 0. Headline

1. **A native, single-instruction 64-bit integer ADD exists on Apple9 and the Apple compiler
   never emits it.** Pre-registered falsifier F3 resolved positive. This is the finding with the
   most direct value to the implementation team.
2. **`ilogic` reaches all 16 two-input boolean functions**, with a collision-free selector and
   one hardware-validated encoding per function. This refines EXP-0102's `INT-12` "10 of 16".
3. **`carry_gen` is a two-operand compare, not a marker plus a source** — closing the operand
   half of `INT-14`, which EXP-0102 deferred by design.
4. **47 of the 60 `db.json` fields across the twelve dispatched instructions are now
   `hardware-run`** (plus a bonus 14 for the 64-bit `iadd2` form). The other 13 belong to the two
   instructions for which no *executable* own-MSL carrier exists; they stay `untested`.
5. **All six `I64` questionnaire items are answered** (four YES, one YES-with-a-correction, one
   PARTIAL) — `analysis/I64_answers.md`.

---

## 1. How much of this was measured, and how hard the gate was

| capture | records | what it is |
|---|---:|---|
| `raw/pilot/` | — | compile+disassemble carrier location; testbed flake-rate log |
| `raw/trial00/` | 515 | harness self-test (one arm). **Not** a gated run. |
| `raw/run01/` | 18 787 | **gated run 1** |
| `raw/run02/` | 18 787 | full repeat, **CONTAMINATED** (see §2) — retained, not used as a gate |
| `raw/run03/` | 18 787 | **gated run 2** |
| `raw/run04/` | 1 834 | adjudication: 1 735 cases x 5 serial repetitions + 97 baseline checks |
| `raw/run05/` | 53 | second-method probes P1-P4 |
| `raw/run06/` | 1 | `sr_read_wide` carrier execution attempt |

Promotion gate: `run01` and `run03` must agree **case-for-case on both the outcome class and the
exact 8 output words**. They agreed on 17 924 of 18 773 comparable cases (95.48%). Every one of
the 849 disagreements, plus every case either run scored `fault` or `hang` (1 735 cases in total),
was re-tested 5x serially in `run04`, whose majority-of-informative-repetitions result overrides
the gated pair. **After adjudication, 0 unresolved cases remain.**

## 2. Concurrency contamination — disclosed, measured, and worked around

`FIELD-SWEEP-PROTOCOL.md` §7 was amended (2026-08-28) because sibling experiments found that
concurrent GPU sweeps contaminate each other. That applies to this experiment, and this section
is the honest accounting.

- **`run01` and `run02` were captured while up to nine other agents were running GPU experiments
  on this host.** This experiment cannot observe or control that, so a background rate of
  spurious zeros and faults cannot be excluded from any capture here, `run03` included.
- **Measured directly** (`raw/pilot/testbed_flake_rate.txt`, four passes of 1 200 *identical,
  unmutated* dispatches): with the device otherwise idle, 0-6 of 1 200 identical dispatches
  returned the wrong answer. With one of my own sweeps running concurrently, that rose to as
  much as **22 in 100**. `run02` overlapped ~2 400 of my own extra dispatches and is therefore
  retained as a contaminated intermediate and **excluded from the gate**; `run03` was captured
  with nothing else issued from this experiment and replaced it.
- **Fault classification is now recorded per case** (`observed.fault_class`, from the Metal
  command-buffer error string). In `run03`: 689 `innocent_victim`
  (`kIOGPUCommandBufferCallbackErrorInnocentVictim` — "Discarded (victim of GPU error/recovery)",
  i.e. killed for *someone else's* error and carrying **no information about our bytes**),
  369 genuine `hang`, 194 genuine `fault` (`kIOGPUCommandBufferCallbackErrorPageFault`), 2 other.
  **`run04` segregates them**: a case's verdict is taken from its non-`innocent_victim`
  repetitions only. 1 006 of the 1 735 adjudicated cases had at least one victim repetition;
  1 529 of 1 735 were fully stable across their informative repetitions.
- **Baseline re-validation** ran before each adjudicated arm and every 25 cases: 97 checks, of
  which **17 failed** — each failure tore down the runner process and restarted it in a fresh
  process rather than being recorded as case data.

**Consequence for the reader:** no field verdict here rests on a single observation. Where a
value's behaviour could not be made stable it is reported, not averaged.

## 3. Observations — what was directly measured

### 3.1 The native 64-bit add (falsifier F3)

*Observed.* `k_u64sub.metal` (`out[gid] = a[gid] - b[gid]` on `ulong`) compiles to
`get_sr, device_load, device_load, iadd2, device_store, stop` — **one** arithmetic instruction,
`1f 01 56 00 02 08 00 50 17 05`, with both `device_load`s and the `device_store` using element
code 4 (8 bytes) rather than the 4-byte code 3 of the 32-bit kernels. Changing **only byte0 bit 7**
(`0x1f` → `0x9f`, the add/subtract selector HW-validated by `RT-1a-FIX`) produced output equal to
`(a + b) mod 2^64` **exactly, on every row, in both gated runs**, and again on a second,
independently chosen boundary input set in 5/5 repetitions (`run05` P1):

| a | b | observed | note |
|---|---|---|---|
| `0xFFFFFFFFFFFFFFFF` | `0x1` | `0x0` | full 64-bit wrap |
| `0x8000000000000000` | `0x8000000000000000` | `0x0` | carry out of bit 63 |
| `0xFFFFFFFF00000000` | `0x00000000FFFFFFFF` | `0xFFFFFFFFFFFFFFFF` | no lo→hi carry |
| `0x0123456789ABCDEF` | `0x00000000FEDCBA98` | `0x0123456888888887` | **lo→hi carry propagated** |
| `0xAAAAAAAAAAAAAAAA` | `0x5555555555555556` | `0x0` | wrap |

*Interpretation.* The kernel contains exactly one arithmetic instruction, so the carry across the
32-bit word boundary is produced **inside that instruction**. A native 64-bit register-pair add
exists.

*Alternatives not excluded.* This was validated in one carrier shape — the compiler's own 64-bit
subtract with one bit flipped — not synthesized from scratch. The byte that makes the operands
64-bit wide was **located** (byte+7 is `0x50` here vs `0xA8` in the byte-identical-otherwise
32-bit form) but **not isolated**, because changing it also changes which register is read.

### 3.2 `carry_gen` — the operand model, closing the open half of `INT-14`

All five `db.json` fields swept densely, both gated runs agreeing on every case:

| field | rule | outcomes (of 256 unless noted) |
|---|---|---|
| `dst` (4b) | only `0x3` | 1 ok / 15 wrong |
| `subop` (byte+1) | `(v & 0x7F) == 0x01`, **bit 7 inert** | 2 ok / 254 wrong |
| `srcA` (byte+3) | `(v & 0x7F) == 0x03`, **bit 7 inert** | 2 ok / 254 wrong |
| `cmpmode` (byte+4) | `(v & 0xA7) == 0x22`; bits 3,4,6 don't-care | 8 ok / 136 silent zero / 112 wrong |
| `b5` (byte+5) | only `{0x01,0x05,0x09,0x81}` — **no clean mask rule** (`0x0d` fails) | 4 ok / 252 wrong |
| byte+2 (a *match* byte) | `(v & 0xCD) == 0x05`; bits 1,4,5 don't-care | 8 ok / 248 wrong / 1 fault |

*Interpretation.* `db.json` types byte+1 as an opaque `subop` and calls byte+2 the
carry-generate marker. The sweep shows byte+1 and byte+3 have the **same shape** — the
project-standard `(reg<<1)|is32` operand descriptor with an inert bit 7 — so `carry_gen` is
`p[dst] = (r[byte+1] <u r[byte+3])`, a two-operand unsigned compare. `0x01` = r0/32-bit and
`0x03` = r1/32-bit, exactly the low-word add's operands. EXP-0102 left `INT-14` open precisely
because "`carry_gen`'s operand-register field layout has never been characterized"; it now is.

*Falsifier F1 fired:* byte+2 = `0x00` raised a contained command-buffer fault, reproducing
EXP-0038's A18 neutralization on M4 by a second method.

*What is still open.* Whether `dst` names a *predicate register* the consumer can be re-pointed
to. `run05` P2 crossed `dst` 0..15 against a 32-point sweep of each `psel` body byte (1 536
combinations) and found **no** working pair other than the compiler's own `dst=3`. Emit producer
and consumer together, as `INT-13` already recommends.

### 3.3 `ilogic` — all 16 boolean functions

Full table with one hardware-validated encoding per function:
**`analysis/ilogic_lut_table.md`**. Minimal selector `(op_base, lut_a & 3, lut_b & 0x0f)`,
**zero collisions** over the agreed 2-D map. Field rules: `lut_a` bits 2-4 don't-care, bits 5-7
must be clear; `outmod` has exactly one load-bearing bit (bit 7 = publish; every value with it
clear silently zeroes); `srcA`/`srcB` are operand descriptors whose bit 7 is inert and whose 248
wrong values **silently zero**; and `z6`, `z8`, `z9` are **HW-tested inert over all 256 values
each**, in a carrier where the instruction's other fields demonstrably change the output.

*Falsifier F2 fired:* byte0 `0x0b` → `0x0a` faults.

### 3.4 The 64-bit `iadd2` form — bit-exact emitter rules, and a register-file boundary

| field | rule | notable |
|---|---|---|
| `addsub` | 0 = subtract, 1 = **native 64-bit add** | §3.1 |
| `dst` (byte+3) | `{0x00,0x01}` ok (size bit free) | **`0xBE..0xFF` (reg ≥ 95) FAULT** |
| `srcA` (byte+7) | `{0x50,0x54}` (bit 2 free) | **every `v & 3 == 3` FAULTS** (64 values) |
| `opmode` (byte+4) | `(v & 0x02) == 0x02` — **one** live bit | 128 ok / 128 silent zero |
| `opc_tail` | `(v & 0x11) == 0x11` | 64 ok |
| `opc_tail2` | `(v & 0x05) == 0x05` | 64 ok |
| `srcB_reg_hi` | only the LSB is live (must be 0) | 64 ok |
| `srcB_imm` | `(v & 0xFC) == 0x08` | 4 ok |
| `srcB_ext` | `(v & 0x7C) == 0x00` | 4 ok |
| `lenbit` | 1 = 10-byte form; 0 **faults** | length selector |
| `store_en` | 1 = publish; 0 silently zeroes | |
| `b2_bit0`, `b2_fmt` | **HW-tested inert** (2/2 and 64/64) | |

The `dst ≥ 95 → fault` boundary independently corroborates EXP-0020's ~96-entry addressable GPR
file from a different instruction family and a different method.

### 3.5 `sfu_marker` is not a byte-invariant token

`db.json` describes it as a "byte-INVARIANT 2-byte token (06 02) … fixed control token with no
operand bits". Refuted: byte+0 requires `(v & 0xF7) == 0x06` (2 of 256 work; 62 return a **wrong**
value) and byte+1 requires `(v & 0x13) == 0x02` (32 of 256). Setting byte+0 to `0x00` **flips the
sign** of `fast::sin` on exactly the rows whose argument needs range reduction, leaving the
small-argument rows correct — i.e. the token carries live quadrant/sign control.

### 3.6 The rest of the cluster

`irotate` (both named bytes plus all 9 bytes of the two raw `operands`/`tail` fields),
`mov_zext16`, `shift_amt_move`, `n3_mov`, `n2_op6` (on **two** independent carriers),
`n2_op8` and `n2_op10` were all swept densely with per-field rules recorded in
`analysis/field_verdicts.json` and `analysis/bit_rules.json`. Two findings worth naming:

- **`mov_zext16`'s byte+1 is inert here** — all 128 register values and both flag values
  reproduce the exact zero-extend, while the same instruction's `subform` faults on 26 values.
  `db.json` types byte+1 as the source register (corpus correlation, EXP-M4-13). The direct
  contrast is `shift_amt_move`'s byte+1, modelled identically, where **exactly one of 128 values
  works**. So the model is right for one instruction and contradicted for the other.
  `n3_mov` shows the same inertness. Recorded in `db_defects`; **not resolved** (see §5).
- **`irotate`'s rotate amount is not independently emittable from this carrier**: byte+6 admits
  only `{0x6c,0x6e}`, so rotating by a different constant needs a differently-compiled carrier.

### 3.7 The two instructions with no executable carrier — reported, not invented

- **`int_alu_ehi` (0/7 fields).** An independently authored own-MSL `std140`-shaped
  uniform→storage matrix copy (`kernels/k_std140_matcopy.metal`) compiled to `imad`/`device_store`
  and emitted **no** `0xef` at all. This **reproduces** EXP-M4-13's negative result by a second,
  independent attempt. All 7 fields stay `untested`.
- **`sr_read_wide` (0/6 fields).** Our own `intersection_query` kernel
  (`kernels/k_rayquery.metal`) **does** emit three `sr_read_wide` instances (offsets 856, 864,
  1494). It executes (`STATUS OK`) but returns all zeros, because `agxrun_persist` binds
  `MTLBuffer`s only and cannot bind an `MTLAccelerationStructure`: `q.next()` never enters the
  loop, so the getters never reach the output. Per FIELD-SWEEP-PROTOCOL §3.2 a field whose value
  cannot reach the output proves nothing, so **no sweep was run** and all 6 fields stay
  `untested`. This is a **testbed** gap, not a hardware or DB one; the fix is a
  `setAccelerationStructure:` path in `tools/agxtest/agxrun_persist.m`.

## 4. `I64-01..06`

Full block, ready to splice: **`analysis/I64_answers.md`**. Summary:
**I64-01 YES** (native add exists; compiler emits a 5-op chain instead) ·
**I64-02 YES** (one instruction, borrow included) ·
**I64-03 PARTIAL** (fault boundaries established; alternative pair placements **not** tested) ·
**I64-04 YES** (single `imad`, one byte apart signed vs unsigned) ·
**I64-05 YES** (no native 64x64→low64: three `imad`) ·
**I64-06 YES** (compare / shift / min-max / bit-scan / select all compound, with measured
sequences). All nineteen 64-bit kernels were **functionally exact** against host oracles.

## 5. Limitations — what a reader must not over-read

1. **Every verdict is carrier-scoped.** A field's ok-set is "what reproduces *this carrier's*
   result". An "ok" value can mean the field is inert **or** that this carrier cannot observe the
   difference; verdicts say which, but the second reading is never fully excludable.
2. **`mov_zext16.src_reg` / `n3_mov.srcA_reg` inertness is unexplained.** The ALU-forward
   explanation is plausible and untested: `run05` P3's second carrier compiled to `iadd2`/`funary`
   and emitted no `mov_zext16`, so the arm was void. Do **not** conclude these are not register
   fields; conclude that they are inert *in these instances*.
3. **I64-03 is genuinely open.** Only fault boundaries were established.
4. **Register fields are validated at the values that work, not across the file.** `carry_gen`'s
   operands were shown to be `(reg<<1)|is32` descriptors, but only the two register numbers the
   carrier happens to hold were exercised.
5. **A18 is deferred everywhere.** Every number here is M4/G16G.
6. **Concurrency.** See §2. Up to nine other GPU experiments ran alongside `run01`/`run02`.
7. **`iadd2` is EXP-0139's dispatched mnemonic.** The 14 `iadd2` verdicts here are for the
   **64-bit form in the `k_u64sub` carrier** and are keyed `iadd2.<field>@u64sub`. The
   orchestrator must merge them against EXP-0139's 32-bit-form results rather than overwrite.
8. **Clean-room rule 5 respected.** For `n2_op8`/`n2_op10` only each byte's accept/reject
   envelope is documented; the SFU range-reduction and marshalling coefficient **sequences** are
   deliberately not reconstructed.

## 6. Verdict

**PASS, PARTIAL on two instructions.** 47 of the 60 `db.json` fields across the twelve dispatched
instructions are `hardware-run` under a two-run gate with full adjudication of every disagreement
and every fault; the remaining 13 belong to the two instructions with no executable own-MSL
carrier and are honestly left `untested` with a named cause and a concrete next step. All six
`I64` items are answered. Ten `db.json` defects/refinements are recorded in
`analysis/field_verdicts.json → db_defects` **without editing `db.json`**.

## 7. Recommended next work

1. **Synthesize the native 64-bit add from scratch** (not by flipping one bit of a compiled
   subtract) and isolate the operand-width bit in byte+7. Highest value in this report.
2. **Answer I64-03 properly** by co-mutating `device_load` destinations with the `iadd2` operand
   fields, so operands can be relocated to arbitrary aligned and unaligned pairs.
3. **Probe for unemitted native 64-bit compare/shift/min-max.** Given I64-01, "the compiler does
   not emit it" is now known to be weak evidence that the hardware lacks it.
4. **Add `setAccelerationStructure:` to `agxrun_persist.m`** — that single change unblocks all 6
   `sr_read_wide` fields and the whole ray-query getter family.
5. **Resolve the `mov_zext16`/`n3_mov` byte+1 inertness** with a carrier that observes the move at
   register granularity.
