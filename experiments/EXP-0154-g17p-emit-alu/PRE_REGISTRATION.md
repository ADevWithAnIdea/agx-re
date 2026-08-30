# EXP-0154 — PRE-REGISTRATION (frozen before any gated run)

**Frozen:** 2026-08-29. **Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`,
`applegpu_g17p`, 5 GPU cores, macOS 26.6, Metal family Apple9), reached at
`192.168.10.243`. **Every claim this experiment produces is a G17P claim.**
No M4 GPU work. No M5. The A18 here is the sanctioned test target under the
2026-08-28 directive, not the hands-off machine of the older directive.

## 1. Question

`tools/agx-isa/validation.json` reports 38 of 171 instructions **emittable** and
443 of 1036 fields at emitter grade. 133 fields across 32 float/integer ALU
instructions are below that bar, and an instruction is emittable only if *every*
field is `hardware-run` or `isolated-byte-diff`
(`docs/evidence-classification.md` section 2). Which of those 32 can be raised to
emittable **on G17P**, and what are the exact per-field rules an emitter must
apply?

## 2. Hypotheses (falsifiable)

* **H1 (scaffold).** A contiguous ALU block lifted byte-for-byte out of the
  compiled form of our own MSL still computes correctly when transplanted into a
  synthesized program whose registers we seeded with distinct values, so the
  *operands it names are ours* and its value->register map is decodable.
  *Refuter:* the transplanted block returns the poison, or returns a value that
  is not a function of our seeds.
  *(Pilot S3 already satisfies the positive arm: `k_u32add`'s lifted `iadd2`
  returned r0 = 10 + 34 = 44 over our seeds. Recorded in `work/smoke/smoke.json`.)*

* **H2 (sentinel).** Integrity sentinels that (a) are stored to memory *before*
  the instruction under test runs and (b) live in a register written *after* it
  runs are immune to the release-on-read effect that destroyed EXP-0138's
  sentinel, so no case is lost to "the field worked and killed the witness".
  *Refuter:* `sentinel_bad` fires on cases whose block executed correctly.

* **H3 (release-on-read as an oracle).** Reading a GPR as a 32-bit source zeroes
  it. Dumping all 16 registers therefore identifies *which register* a swept
  operand descriptor named, independently of the arithmetic result.
  *Refuter:* no register zeroes, or the zeroed register does not track the swept
  descriptor value.
  *(Pilot S3 positive arm: `srcB_imm = 0x08` -> N=2, and r2 came back 0.)*

* **H4 (per-instruction).** For each arm, every db.json field is either inert
  across its whole encodable range, or its ok/not-ok partition over a dense
  sweep is completely described by an exact `(value & MASK) == V` predicate, or
  by a semantic map (register index / shift amount / boolean function).
  *Refuter:* a field whose partition has no such description; it is then
  reported `untested` with the full enumeration, never rounded up.

* **H5 (G16G -> G17P reproduction).** The M4 results this experiment
  deliberately re-tests — EXP-0139's `iadd2.lenbit` fault, `iadd2.dst >= 192`
  fault bound, `ibfe.offset` literal vs `ibfe.width` mod-32 asymmetry;
  EXP-0146's `ilogic` 16-function LUT map and byte0 `0x0a` fault — reproduce on
  G17P. *Refuter:* any of them behaves differently. **A divergence is a
  first-class finding, not a failure.**

## 3. Independent / controlled variables

Independent: exactly ONE db.json field of ONE instruction per case (or one
constituent byte, for raw fields wider than 8 bits). Controlled and identical
across every case of an arm: the seed table, the lifted block's other bytes, the
program layout, the carrier, the dispatch shape (grid 1, tg 1), the poison, and
both sentinels.

## 4. Coverage rule (FIELD-SWEEP-PROTOCOL section 3)

* width <= 8 -> **all 2^w values, dense**.
* width > 8 -> **byte-wise**: every constituent byte swept 0..255. The full
  16/32/40/48-bit space is NOT claimed and every verdict says so.
* Register fields are 7-8 bits and are therefore swept densely over 0..127/255,
  which subsumes the boundary set.

## 5. Oracle

The observation is the **full 16-register architectural state after the block**,
plus both sentinels, read out of a buffer poisoned with `0xDEADBEEF` before
every dispatch. A case is `ok` iff all 16 registers equal the *unmutated
anchor's* register state, measured on the same device in the same process. This
is strictly stronger than a single output word: a value that computes the right
answer but disturbs another register is not interchangeable for an emitter and
is not scored `ok`.

`outcome` in {`ok`, `silent_zero`, `wrong_value`, `fault`, `hang`,
`undecodable`}. `silent_zero` = differs and every differing register is 0 (the
canonical Apple9 wrong-operand failure mode).

Independent host-side oracles applied in analysis, not by the runner:
`iadd2` sum/difference of seeds; `ilogic` truth table recovered bitwise from
distinct seeds covering all four (bit_a, bit_b) combinations; `ishift` shift
amount; `iminmax` min/max of seeds; register-identity via which seed the result
equals and which register was zeroed.

## 6. Pre-registered falsifiers

* **F0, one per arm:** byte0 of the instruction under test forced to `0x00`
  MUST NOT score `ok`. If it does, that arm's sweep cannot see a difference and
  the arm is reported as proving nothing.
* **F1:** `iadd2.lenbit = 0` selects the 12-byte form and must NOT be `ok`.
* **F2:** `iadd2.dst >= 192` (register index >= 96) must fault.
* **F3:** `ilogic` byte0 `0x0a` must not be `ok`.
* **F4:** `ibfe.width = 32` must behave exactly like `width = 0`.
* **F5:** `ibfe.offset` in 32..63 must shift the field out entirely.

## 7. Promotion rule (frozen; applied by `analysis/verdicts.py`)

Two gated runs, `run01` and `run02`, over the identical frozen matrix. A field
is promoted only if **its per-value outcome map is identical in both runs**
(victim-class cases excluded from the comparison, per section 8).

| label | requires |
|---|---|
| `hardware-run` | dense sweep of the whole encodable range AND (inert everywhere, OR an exact `(v & MASK) == V` rule with **zero** exceptions, OR a semantic map matched over its full domain) AND the arm's falsifier fired |
| `isolated-byte-diff` | the partition is explained but with 1-2 exceptions, or the field was swept byte-wise rather than over its full multi-byte space |
| `untested` | anything else, with the complete outcome enumeration recorded in `note` |

This is more permissive than EXP-0139's "<=1-bit rule" bar and matches EXP-0146;
the difference is stated here deliberately so a reviewer can re-score it.

## 8. Confounders and their mitigation

* **Sibling GPU experiments.** A hang triggers a device reset that kills other
  contexts' work, reported as `kIOGPUCommandBufferCallbackErrorInnocentVictim`.
  Mitigation: majority-of-3 before any `fault`/`hang`; the OS classification
  string recorded verbatim on every non-OK case; victim-class cases flagged and
  excluded from the cross-run gate.
* **GPU error cascade.** The unmutated baseline is re-validated every 250 cases;
  on drift the child runner is restarted and the event logged to
  `baseline.jsonl`.
* **Our disassembler is not the authority.** A mutated instruction our own DB
  cannot tokenize is recorded (`rt_ok: false`) and still executed; the hardware
  decides.
* **Release-on-read.** Addressed by H2/H3 above.
* **Carrier specificity.** Every verdict is scoped to the named lifted block; a
  field inert in this operand configuration may not be inert in another.

## 9. Deliberately NOT run

| instruction | why |
|---|---|
| `fspecial` | EXP-0138 recorded **three reproducible GPU hangs** on byte+3 bit7 and stopped that arm under FIELD-SWEEP-PROTOCOL section 8. Not re-opened. |
| `falu_srcmod12b`, `half_alu_fma12` | `emit_unsafe` in db.json regardless of field labels |
| `int_alu_ehi`, `ibfe_mesh_attr` | no own-MSL anchor from a compute harness |
| `icmpsel`, `isel10_c`, `isel_reg8`, `falu2_uni` | no own-MSL anchor among the 27 authored probes / needs a uniform-bound carrier not built here |

## 10. Environment, timeouts, revision

* Repo revision at freeze: `3a885d58c4d286eda61a8808029c8a7aecb1dfec`, tree clean.
  Per SUBAGENT_BRIEF, captures are gated on the **authored blob hashes** in
  `CAPTURE_CONTRACT.json`, not on live `HEAD`.
* Per-request watchdog 8 s; `shdump` 300 s; every remote call wrapped in a hard
  `alarm`.
* Concurrency: bulk sweeps run **unlocked** (orchestrator directive
  2026-08-29); `gpulease.sh` is reserved for hang-prone work, of which this
  experiment deliberately runs none.
