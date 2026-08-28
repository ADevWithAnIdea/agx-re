# EXP-0146 — pre-registration (frozen before any mutation run)

**Experiment:** `EXP-0146-m4-emit-int-misc` — make the integer-support instruction cluster
`carry_gen ilogic int_alu_ehi irotate mov_zext16 shift_amt_move n2_op6 n2_op8 n2_op10 n3_mov
sr_read_wide sfu_marker` **emittable** (per `experiments/FIELD-SWEEP-PROTOCOL.md`), and answer
questionnaire items **I64-01..06** of `APPLE9_RE_IMPLEMENTATION_GAPS.md`.

**Target:** local **Apple M4 / G16G**, 10 GPU cores, macOS 26.6.x, Metal 4. No SSH. The A18 Pro
is untouched; M5 is untouched. `macvdmtool` is never invoked.

**Repository revision pinned at pre-registration:** `3efd06c6ba3d0dad0b8eedc97a4a6af4e7f2e981`
(working tree contains other agents' untracked `experiments/EXP-013x/EXP-014x` directories; per
`SUBAGENT_BRIEF.md` a capture is valid if the *authored blob hashes* match, not if `HEAD` is
frozen).

**Clean-room provenance:** `OWN-SHADER` + `HW-PROBE`. Every byte inspected, mutated or executed is
the compiled form of MSL **we authored** in `kernels/` (compiled at runtime by
`tools/shdump/shdump.m` via `newLibraryWithSource:`). No Apple binary is disassembled,
decompiled, symbol-dumped, strings-scanned or debugged. Instruction encodings are read and
rebuilt exclusively through `tools/agx-isa/isadb.py` (read-only use).

---

## 0. Pilot phase already performed (disclosed, non-mutating)

Before this document was frozen, a **compile-and-disassemble-only** pilot ran
(`work/pilot/disasm.py`): each authored kernel in `kernels/` was compiled and its `_agc.main`
tokenized with `tools/agx-isa`. **No bytes were mutated and nothing was dispatched.** Its only
purpose was to establish *which carrier contains which target instruction, at which byte offset*
— the "carrier" requirement of FIELD-SWEEP-PROTOCOL §3.2. Its output is retained as
`raw/pilot/carrier_disasm.txt`. The carrier table in §3 below is frozen from it.

## 1. Falsifiable hypotheses

**H1 (carry_gen operand model).** `carry_gen`'s six bytes are
`[dst<<4|0x2][subop][0x35][srcA][cmpmode][b5]`, and `subop` (byte+1) and `srcA` (byte+3) are the
**two source-operand descriptors** in the project-standard `(reg<<1)|is32` encoding, `dst` (byte0
high nibble) is the predicate destination, and `cmpmode` (byte+4) selects the compare relation.
*Predicted observation:* in the `k_u64add` carrier, values of `subop`/`srcA` that keep the
compare reading the low-word add's true operand reproduce the correct 64-bit sum; other values
either drop the carry (high word one too small) or add a spurious carry.
*Refuter:* if the observed carry pattern is invariant under a full 0..255 sweep of `srcA`, then
`srcA` is not an operand selector and H1 is refuted.

**H2 (ilogic is a true 2-input LUT with an emittable selector).** `op_base` (byte+2 bit0),
`lut_a` (byte+4) and `lut_b` (byte+5) jointly select the boolean function; the realized function
is recoverable bit-exactly from one output word when the two sources carry
`(0xCCCCCCCC, 0xAAAAAAAA)`-style covering patterns.
*Predicted observation:* sweeping `lut_a` 0..255 x `lut_b` 0..255 (and both `op_base` values)
yields a *deterministic map* from encoded value to one of the 16 boolean functions.
*Refuter:* if all swept values produce the same function (or zero), the LUT selector is not in
these bytes.

**H3 (I64-02: a native 64-bit subtract exists).** `k_u64sub` compiles to **one** integer op
(`iadd2`, byte0 `0x1f`) between a 8-byte `device_load` pair and an 8-byte `device_store`;
therefore that single instruction performs the whole 64-bit subtract including the borrow.
*Predicted observation:* borrow-crossing inputs (e.g. `0x0000000100000000 - 1`) read back exactly.
*Refuter:* a wrong high word on any borrow-crossing row.

**H4 (I64-01: no native 64-bit add is reachable by flipping the add/sub bit).** `iadd2`'s byte0
bit7 is the HW-validated add/sub selector. Splicing the **64-bit** subtract's `0x1f -> 0x9f`
therefore predicts a **64-bit add**. If the hardware has a native 64-bit add, this splice
produces `a+b` exactly; if it does not, the result is wrong.
*This is a pre-registered case that may go either way and is recorded as a first-class result
in both directions.*

**H5 (I64-03: 64-bit operands are register PAIRS with a placement rule).** Sweeping the 64-bit
subtract's `dst` (byte+3) and `srcA` (byte+7) over 0..255 identifies which encodings are legal
placements, and whether odd/unaligned pair bases are accepted.
*Refuter:* every value produces the same output (field inert) or every value faults.

**H6 (the opaque group).** `n2_op6`, `n2_op8`, `n2_op10`, `n3_mov`, `sfu_marker`,
`shift_amt_move`, `mov_zext16`, `irotate`, `sr_read_wide` each have at least one byte whose
mutation changes the carrier's output. *Refuter (per field):* a full 0..255 sweep in which every
value reproduces the baseline output exactly = the byte is inert **in this carrier**, which is
reported as such (`untested`/`tokenization-only`, never rounded up).

## 2. Variables

- **Independent:** exactly one field (or one byte) per case, set to a chosen value.
- **Controlled:** carrier source (frozen hashes, §6), compile flags (`--no-fast-math`), input
  buffers (frozen vectors, §4), grid/threadgroup (`8/8`), splice offset, all other bytes of the
  carrier.
- **Dependent:** the 8 output words/pairs read back, plus the command-buffer status.

## 3. Carriers (frozen from the pilot; `mnemonic @ byte offset in _agc.main`)

| instruction | carrier kernel | offset | why the field is live on the output path |
|---|---|---|---|
| `carry_gen` | `k_u64add.metal` | `+0x2a` | its predicate feeds `psel` then the high-word add that is stored |
| `ilogic` | `k_logic_and.metal` | `+0x20` | the only ALU op; its result is stored |
| `irotate` | `k_rot_imm.metal` | `+0x12` | the only ALU op; its result is stored |
| `mov_zext16` | `k_zext16.metal` | `+0x12` | the only ALU op; its result is stored |
| `shift_amt_move` | `k_rot_var.metal` | `+0x4c` | stages the rotate amount consumed by the stored result |
| `n3_mov` | `k_u64eq.metal` | `+0x3c` | last op before the store |
| `n2_op6` | `k_u64eq.metal` | `+0x32` | in the compare chain that produces the stored result |
| `n2_op8` | `k_sfu_sin.metal` | `+0x18` | SFU range-reduction step feeding the stored `fast::sin` |
| `n2_op10` | `k_roundmodes.metal` | `+0x1c` | SFU marshal in the conversion chain that is summed and stored |
| `sfu_marker` | `k_sfu_sin.metal` | `+0x4a` | immediately before the `fspecial` that produces the stored value |
| `iadd2` (64-bit form) | `k_u64sub.metal` | `+0x20` | the only integer op; H3/H4/H5 |
| `sr_read_wide` | **carrier search** (§7) | — | no own-MSL carrier found in the pilot |
| `int_alu_ehi` | **carrier search** (§7) | — | own MSL emits `0x9f` (EXP-M4-13 negative result) |

## 4. Frozen input vectors (8 threads, one row per thread)

Written verbatim by `harness/oracles.py` (frozen with this document):

- `U64_A`/`U64_B` — eight 64-bit pairs chosen so the low-word carry/borrow pattern is
  `[0,1,1,0,1,1,0,0]` / mixed, and so the four words of every row are mutually distinct
  (needed to identify which register a swept operand descriptor selects).
- `LOGIC_A`/`LOGIC_B` — eight 32-bit pairs each covering all four `(bit_a,bit_b)` combinations,
  so the realized boolean function is recoverable from one output word.
- `U32_A`/`U32_B`, `F32_A` — boundary-heavy 32-bit / float vectors.

## 5. Coverage rule (FIELD-SWEEP-PROTOCOL §3.3)

- width <= 8 → **all 2^w values, dense**.
- width > 8 → `{0,1,2,max-1,max}` + all powers of two + >= 16 asymmetric interior samples.
- Multi-byte `raw` fields (`irotate.operands` 40b, `irotate.tail` 32b, `n2_op10.immword` 48b,
  `n2_op8.body` 40b) are additionally swept **byte-wise** (each constituent byte 0..255 with the
  others held at baseline). A byte-wise result that contradicts the modelled field boundary is
  recorded under `db_defects` in `analysis/field_verdicts.json` — `db.json` is **not** edited.

## 6. Pre-registered falsifiers (cases expected to FAIL)

| id | case | prediction |
|---|---|---|
| `F1` | `carry_gen` byte+2 `0x35 -> 0x00` | carry dropped: high word one too small on carry rows (reproduces EXP-0038's A18 neutralization on M4) |
| `F2` | `ilogic` byte0 `0x0b -> 0x0a` | descriptor no longer matches; wrong value or fault |
| `F3` | `k_u64sub` byte0 `0x1f -> 0x9f` | **either** an exact 64-bit add (H4 positive) **or** a wrong high word (H4 negative). Both are recorded. |
| `F4` | `mov_zext16` byte0 `0x13 -> 0x12` | wrong value or fault |

If **no** pre-registered falsifier fails, the sweep is declared unable to detect a difference and
its positive results are downgraded to `untested`.

## 7. Instructions with no own-MSL carrier

`sr_read_wide` and `int_alu_ehi` were **not** produced by any kernel we authored in the pilot
(EXP-M4-13 already recorded the `int_alu_ehi` negative: our own MSL emits `0x9f`/`iadd` for the
equivalent integer address math). One bounded carrier search is pre-registered for each
(ray-query getters for `sr_read_wide`; a `std140`-shaped uniform->storage matrix copy for
`int_alu_ehi`). **If the search fails, both are reported `untested` with the carrier-absence
reason recorded — no label is rounded up and no result is invented.**

## 8. Confounders

- **Silent zeros.** On Apple9 a wrong operand-field value usually yields a silent zero, not a
  fault. Every zero is recorded as `outcome:"silent_zero"`, never dropped.
- **Register aliasing.** `r(R mod 64)` for `R in [64,112]`, faults at 126/127 (EXP-0112).
- **`mov_imm` hazard.** `imm7` values 128..255 silently zero and, combined with `iadd2`'s N=0
  self-read, produced two real GPU hangs (EXP-0128). **This experiment does not synthesize any
  `mov_imm`**; it mutates fields inside compiler-emitted carriers only.
- **Carrier coupling.** A mutated field may change the output through a path other than the one
  hypothesized. Mitigated by (a) using carriers whose only ALU op is the target where possible,
  and (b) reporting per-row output vectors, not a single scalar.
- **Compiler scheduling.** Offsets are re-resolved by disassembly at run time and asserted equal
  to the frozen table; a mismatch aborts the run.

## 9. Environment, timeouts, safety

- One `agxrun_persist` process per carrier; **8 s per-request watchdog**; the driver kills and
  restarts the child on a wedge.
- `raw/<run_id>/sweep.jsonl` is opened append-only, line-buffered, `flush`+`fsync` after **every**
  case.
- `PROGRESS.md` gets a timestamped entry per milestone.
- **Stop rule:** after **two genuine hangs in one arm**, that arm is abandoned and reported
  PARTIAL. After a host anomaly, STOP and report BLOCKED.

## 10. Runs

Two gated runs, `run01` and `run02`, with identical inputs and identical case lists; `run02` is a
full independent repeat in a fresh process. A field is only labelled `hardware-run` if **both**
runs agree case-for-case. Disagreement is reported, not averaged.

## 11. Deliverables

`raw/<run_id>/sweep.jsonl`, `analysis/field_verdicts.json`, `analysis/I64_answers.md`,
`RESULTS.md`, `PROGRESS.md`, `manifest.json`. **No edits** to `tools/agx-isa/db.json`,
`tools/agx-isa/validation.json`, `docs/`, `PROVENANCE.md` or
`APPLE9_RE_IMPLEMENTATION_GAPS.md`. **No `git commit`.**
