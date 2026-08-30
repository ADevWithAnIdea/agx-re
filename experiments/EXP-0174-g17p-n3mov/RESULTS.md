# EXP-0174 — RESULTS

> **The one sentence.** **YES — this ISA can move one GPR to a different GPR, and we
> generated the encoding from the descriptor's own bit geometry with ZERO bytes copied from
> any compiled shader:** `n3_mov` is a 16-bit half-register move, a full 32-bit `r[i] = r[j]`
> is two of them, and 840 generated 32-bit copies over all 240 ordered `(dst != src)` pairs
> plus 1680 generated half-moves passed a host-computed 16-register prediction on the A18 Pro,
> **with 0 failures, in two gated runs and two independent register plans.**

**Target: Apple A18 Pro / G17P** — `applegpu_g17p`, `AGXAcceleratorG17P`, macOS 26.6.
Device identity is read from the live device into `raw/<run>/00_env.json` on every run and is
never taken from a literal.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (authored by us) and the AGX machine code the public
  newLibraryWithSource: / MTLBinaryArchive API compiled FROM THEM.
Apple binary introspection: NONE
Reproduction: harness/sync.sh push && build
              python3 harness/run.py  --run g17p_20260830_run01 --order forward
              python3 harness/run.py  --run g17p_20260830_run02 --order reverse
              python3 harness/grid.py --run g17p_20260830_run01 --plan idx15 --order forward
              python3 harness/grid.py --run g17p_20260830_run02 --plan idx7  --order reverse
              python3 harness/grid.py --run g17p_20260830_run03 --plan idx15 --order reverse
              python3 analysis/analyze.py --runs g17p_20260830_run01,g17p_20260830_run02
              python3 analysis/verdicts.py
Evidence: raw/g17p_20260830_run01/  gated, forward     (5822 cases + 65536 grid)
          raw/g17p_20260830_run02/  gated, reverse     (5822 cases + 65536 grid)
          raw/g17p_20260830_run03/  grid replication   (65536, same plan as run01)
          raw/prefreeze/**          CALIBRATION and one post-freeze adversarial probe.
                                    NEVER evidence for a gated verdict.
```

**The instruction under test was GENERATED, never spliced.** Every one of its four bytes is
computed by `harness/isa_helpers.n3_bytes()` from the bit positions `db.json` declares, and
cross-checked against `isadb.assemble()` at import time by `assert_geometry()`.
`kernels/probes.metal` exists only as a source of compiled positive controls and is on the
path of no verdict here.

---

## 1. What was asked and why

EXP-0173's closure audit named one blocker above all others:

> No emittable descriptor moves one GPR to a DIFFERENT GPR. That blocks `nir_op_mov`, phi
> lowering, parallel copy, register-allocator coalescing and spill reload — which is to say
> it blocks the register allocator, which is to say it blocks the back end.

`mov_zext16` is an in-place narrow on one register used as both source and destination.
`n2_op6` calls itself a catch-all bucket and is not HW-dispatch validated. `n3_mov` was the
candidate, and its three operand fields — `dst`, `srcA_reg`, `srcA_uni` — were all
`corpus-correlation`, sourced from EXP-M4-13, which is compile-only.

## 2. VERDICTS — two gated runs, `analysis/field_verdicts.json`

| field | verdict | vals | distinct bytes | enc range | start | width | moved | disagree | agree % | carriers |
|---|---|---|---|---|---|---|---|---|---|---|
| `n3_mov.dst` | **hardware-run** | 16 | 16 | 16 | 4 | 4 | 26 | 0 | 100.000 | 2 |
| `n3_mov.srcA_reg` | **hardware-run** | 256 | 256 | 256 | 8 | 8 | 508 | 0 | 100.000 | 2 |
| `n3_mov.srcA_uni` | **hardware-run** | 2 | 8 | 2 | 15 | 1 | 12 | 0 | 100.000 | 2 |
| `n3_mov.subform` | **hardware-run** | 256 | 536 | 256 | 16 | 8 | 528 | 0 | 100.000 | 4 |
| `n3_mov.companion` | **hardware-run** | 256 | 512 | 256 | 24 | 8 | 256 | 0 | 100.000 | 2 |
| `n3_mov._instruction` | **hardware-run** (generated) | — | 1504 | — | — | — | 2128 | 0 | 100.000 | 2 |

`srcA_reg` is swept as the WHOLE of byte+1 (256 values) because the measurement below shows
`db.json` splits that byte in the wrong place; the two "fields" it declares there are covered
exhaustively and jointly by that one sweep.

**Every field clears the gate on both clauses**: ≥ 99 % cross-run agreement (all are
100.000 %) and movement ≥ 2× disagreements (all have **zero** disagreements against non-zero
movement). No case with `validity != "valid"` is counted anywhere. There are no skip
placeholders: 0 hangs, 0 stopped arms, 11 644 dispatched cases across the two gated runs plus
196 608 grid dispatches, `carrier_hangs = 0`.

## 3. THE HEADLINE — the register move, stated so it can be emitted

`n3_mov` is a **16-bit half-register move** with independent source-half and
destination-half selection:

```
byte0 = (dst << 4) | 0x3          dst  = destination GPR, r0..r15
byte+1 = (S << 1) | hs            S    = source GPR, 7 bits, ALIASING PERIOD 64
                                  hs   = 0 -> read the source's LOW 16 bits
                                       = 1 -> read the source's HIGH 16 bits
byte+2                            & 0x03 == 1  and  & 0xC0 == 0   -> MOVE
                                  bit 3 (0x08) -> RELEASE the source half read
                                  bits 2, 4, 5 -> don't care
byte+3                            & 0x1E == 0                     -> the write happens
                                  bit 0 = 0 -> write the destination's LOW  16 bits
                                        = 1 -> write the destination's HIGH 16 bits
                                  bits 5..7 -> don't care

    r[dst] halfword hd  :=  r[S] halfword hs        THE OTHER HALF OF r[dst] IS PRESERVED
```

**A full 32-bit `r[i] = r[j]` is two instructions, in either order:**

```
    i3  (2j+1)  01  01        ; r[i].hi := r[j].hi        (r[i].lo preserved)
    i3  (2j+0)  01  00        ; r[i].lo := r[j].lo        (r[i].hi preserved)
```

Worked example from the raw: `23 13 01 01 | 23 12 01 00` puts r9's full `0x40200000` into r2.

**The evidence that this is GENERATION and not decoding.** Arm `F/gen32` builds that pair
from the rules above for **all 240 ordered `(dst, src)` pairs with `dst != src`**, in **both**
instruction orders, in **both** register plans, and scores each against a full host-computed
16-register prediction:

| | run01 (forward) | run02 (reverse) |
|---|---|---|
| generated 32-bit copies dispatched | 960 | 960 |
| matched the host prediction exactly | **840** | **840** |
| undecidable (destination is the carrier's blind or pad-masked slot; covered by the other plan) | 120 | 120 |
| **FAILED** | **0** | **0** |
| generated half-moves (`G/genhalf`) matched | **1680** of 2048 (368 undecidable) | **1680** |
| **FAILED** | **0** | **0** |

All 16 destinations are covered: 12 of them decidably in both plans (60 passing cases each)
and 4 (r6, r7, r13, r15) in exactly one plan each (30 passing cases), because each plan is
blind at its read-back index register and masked at its padding register, and the two plans
were chosen disjoint in both. `dst = 5` is undecidable in arm `A/dstmap` (that arm's source
*is* r5, so a correct self-move and a no-op are the same observation) and is covered by
`F/gen32`, where it passes 60/60.

**The source survives unless you ask for it not to.** `byte+2` bit 3 releases the source, and
a post-freeze adversarial probe shows the release is **half-granular**: with r3 set to
`0x4020002F`, reading its low half with release leaves `0x40200000` and reading its high half
with release leaves `0x0000002F`. Emitters that want a non-destructive copy must clear bit 3;
`byte+2 = 0x01` is the safe canonical move.

## 4. Two things `db.json` gets wrong, and what an emitter following it would do

### DEF-0174-1 — the byte+1 operand field is modelled one bit off

`db.json` declares `srcA_reg` = byte+1 bits 0..6 and `srcA_uni` = byte+1 bit 7, enum
`{0: gpr, 1: uniform/hi}`. **Measured over a dense 0..255 sweep of byte+1, in two register
plans, in two runs, with 100.000 % agreement and zero model mismatches:**

- the source register is byte+1 bits **1..7**;
- byte+1 bit **0** is the SOURCE-HALF select. `byte+1 = 0x12` yields `0x0000` and
  `byte+1 = 0x13` yields `0x4020` — the low and high halves of r9 = `0x40200000`;
- byte+1 bit 7 is source-register **bit 6**. All 128 `(v, v+128)` pairs produced
  byte-identical 16-register dumps in both plans and both runs, because the register file
  **aliases with period 64** (this is the same period EXP-0112 measured on the ALU, and it is
  measured here rather than assumed). **No uniform-file value was ever reached through it.**

An emitter following `db.json` writes the source register number into bits 0..6; the hardware
reads that as register `S >> 1` with half-select `S & 1` — the wrong register *and* the wrong
half, silently, with no fault.

### DEF-0174-2 — `subform`/`companion` are an op selector and a destination-half select

`db.json` calls byte+2 a "source-class / size sub-form selector" and byte+3 a
"companion / second-operand descriptor" whose `0x01` is "the ZERO-EXTEND high-half-zero
companion ... emitted after the low-half move to zero the upper 16 bits". Measured over the
**complete 256 × 256 cross-product (65 536 encodings, run three times)**:

- byte+2 is an **operation** selector: `& 0x07 == 0` is the in-place narrow
  (`r[dst] &= 0xFFFF`, byte+1 inert — this is the `mov_zext16` member, and EXP-0161's result
  is reproduced exactly); `& 0x03 == 1` is the move; `& 0x07 == 3` behaves as XOR and `== 4`
  as OR of the byte+1 and byte+3 operands (`93 0a 04 08` gives `0x41 | 0x3a = 0x7b`);
  bit 3 is the source release; bits 6..7 must be 0;
- byte+3 bit 0 **selects the destination half and PRESERVES the other one**. It does not zero
  anything: `23 13 01 01` alone gives `0x40200022`, keeping r2's own low half `0x0022`.

## 5. A correction to EXP-0168, measured not argued

EXP-0168 (hours old) reported as a hardware fact:

> **Measured: a write whose 4-bit destination nibble is 15 is discarded, and the slot reads 0.**
> Driver consequence: an emitter must not allocate register index 15 as the destination of a
> 4-bit-dst instruction — it is a bit bucket, not a GPR.

**That is a by-construction artifact of its own read-back path.** In
`EXP-0168/harness/isa_helpers.py`, `R_IDX = 15` and `store_word()` emits `mov_imm(R_IDX, 0)`
immediately before **every** `device_store` — including the store whose `data_reg` is 15. r15
is therefore zeroed one instruction before it is read, in every case of every arm, and could
not have read anything else. It is the same class of blindness EXP-0168 itself exposed in
EXP-0140 — the oracle destroying the thing it observes — occurring in its own harness, and
EXP-0168's committed `raw/g17p_20260830_run02/baseline.jsonl` shows the signature plainly:
`regs[15] = 0` against `SEED_I[15] = 121`.

**Measured here:** in register plan `idx7`, whose read-back index register is r7, r15 holds
its `mov_imm` seed 121 in every baseline of both gated runs, and `dst = 15` writes r15
correctly — `f3 0a 01 00` puts 65 into r15, and all 15 generated 32-bit copies into r15 pass.
**r15 is an ordinary, writable GPR.** EXP-0168's alternative reading, "physical r15 is a
hardwired zero register", is also refuted: it holds and returns 121.

**What this does NOT establish.** This is a fact about r15 as reached through `n3_mov`'s
4-bit `dst` nibble and `mov_imm`'s. EXP-0168's other conclusion — that `falu2i(r15, r14, +2.5)`
also read back 0 — was measured through the same defective path and should be re-run rather
than assumed either way. The same applies to that experiment's `regs[0] = 0` anomaly, which
this harness does **not** reproduce (r0 reads its seed 10 with both of the `extmode`
encodings `db.json` allows, 3 repetitions each, in both plans) and which therefore remains an
**unexplained open question about EXP-0168**, not a finding of this experiment.

## 6. Where this experiment's own frozen model was WRONG

Recorded rather than smoothed. Both were caught by pre-registered falsifiers.

| frozen in `PRE_REGISTRATION.md` | measured | caught by |
|---|---|---|
| H3: the move mask is `(b2 & 0x03) == 1 and (b2 & 0xE0) == 0` — 8 values | bit 5 is FREE; the mask is `(b2 & 0xC0) == 0`, **16** values | `X/b2hi`: `byte+2 = 0x21` was pre-registered as a value that must not move, and it moves. Independently confirmed by the 65536-case cross-product |
| H4: `byte+3 >= 2` must not write | `0x20 / 0x40 / 0x80` write exactly like `0x00`; `0x08 / 0x10` write **zero**; only `0x02 / 0x04` do not write. The rule is `byte+3 & 0x1E == 0` | `X/b3hi`, 6 of 14 cases per run |

Neither correction touches the generation result: arms `F/gen32` and `G/genhalf` use
`byte+2 = 0x01` and `byte+3 ∈ {0x00, 0x01}`, which are inside both the frozen and the
corrected masks.

## 7. Falsifiers and controls — what proves the method could have failed

A falsifier **fires** when the observation differs from the n3 MOVE prediction for the same
`(dst, src)` — which is what the pre-registration claims ("only nibble 3 may produce the
predicted move"). Identical counts in both gated runs and both plans:

| falsifier | n | fired | interpretation |
|---|---|---|---|
| `X/lownib` — byte0's low nibble set to each value except 3 | 30 | **28** | The 2 non-fires are byte0 low nibble **0xb** in each plan, which produces the same value. That is `reg_move_c1`, a different documented instruction that turns out to be a register move too (§8) — not a failure of the n3 model. Nibble 7 **faults** reproducibly; nibble 0xe over-consumes and poisons the dump (`invalid_sentinel`, correctly excluded) |
| `X/narrow` — byte+2 := 0x00 | 4 | **4** | performs `r[dst] &= 0xFFFF` and does **not** copy the source, reproducing EXP-0161 |
| `X/b3hi` | 14 | 8 | 6 non-fires are the H4 refutation above |
| `X/b2hi` | 12 | 10 | 2 non-fires are the H3 refutation above |
| `X/selfmove` — `dst == src` | 6 | — | **pre-registered UNDECIDABLE** and scored `undecidable`, never `ok`: a correct self-move and a no-op are the same observation here |

**Stale-pipeline control (`X/alternate`).** This experiment dispatches at ~1120 cases/second,
roughly 55× EXP-0168's rate, which makes "the child cached a pipeline and re-ran an earlier
program" a live alternative explanation for everything above. Two distinct blocks were
therefore dispatched alternately 20 times each, in both plans, in both runs: r2 held **65 in
all 40 of one block's dispatches and 10 in all 40 of the other's**, with no convergence
anywhere. Independently, `gputime_ns` is present and non-zero on 5820 of 5822 cases in run01
(range 1374–6583 ns), so each dispatch demonstrably reached the GPU; the high rate is host-side
overhead around a 1-thread dispatch of a ~3.4 KB program, not absent work.

**One reproducible fault, and one defect in this experiment's own metric.**
`27 0a 01 00` — byte0 low nibble 7 — **faults reproducibly**: in both gated runs, in both
register plans, after majority-of-3 retries, with no `InnocentVictim`-class string. That is a
recorded hardware fact, not an obstacle. It also exposed a defect in `analysis/analyze.py`'s
first cross-run agreement metric, which compared only the register dump: a case with no dump
in *either* run was scored a DISAGREEMENT, so a reproducible fault was the one observation the
gate could never pass. The metric now compares the `(OS fault class, faulted?, dump hash)`
triple, which scores two identical faults as the agreement they are; that took the falsifier
row from 96.875 % to 100.000 % and changed no other row. The pre-fix numbers are recoverable
by re-running the analysis against the same raw — no raw was touched.

**Grid replication.** The 65536-case cross-product was run three times. `run01` and `run03`
use the **same** register plan and opposite orders: **65536 of 65536 records byte-identical,
100.0000 % agreement, zero disagreements.** `run02` uses the other plan and agrees on
98.68 % — the 864 differences are exactly the cases that read or write the two plans'
different registers, which is the expected and desired behaviour of a genuine second carrier,
not a defect.

## 8. Two further observations, deliberately labelled OBSERVATION and not promoted

Both come from a post-freeze adversarial probe (`raw/prefreeze/adv01`), reproduced in both
register plans. Neither was swept, so neither gets a label.

1. **`reg_move_c1` (byte0 low nibble 0xb) is also a GPR-to-GPR move, with the same `2*S`
   operand encoding.** `2b (2S) 01 00` writes r[S] into r2 for S ∈ {0,1,3,5,8,10,14}, where
   r[S] was written by `mov_imm`. The cross-check that this is really a register read: byte+1
   `0x0e` selects r7, and it returns **83 in plan `idx15` and 0 in plan `idx7`** — exactly
   those two plans' r7 states. `db.json`'s `reg_move_c0` semantics block says "AS OF
   2026-08-28 NO VALIDATED GPR-TO-GPR MOVE EXISTS ON APPLE9" and that this form is
   "UNIFORM-REGISTER-SOURCED ONLY — it FAILS to read a GPR written by falu2/falu2i or by
   device_load" (EXP-0090). EXP-0090's negative used `falu2`/`falu2i`- and `device_load`-
   written sources; `device_load` on G17P is now known to be **asynchronous** (DEF-0169-1),
   which is a candidate explanation for at least half of that negative. **Recommended
   follow-up experiment**, not a claim.

2. **`pad_operand` (byte0 low nibble 0) has an architectural effect.** `db.json` says it is
   "NOT A STANDALONE HARDWARE OPCODE ... a 2-byte low-nibble-0 slot carrying a trailing
   operand ... of the PRECEDING instruction". Measured: the 4-byte sequence `X0 (2S) 00 01`,
   placed where the preceding instruction is a completed 2-byte `mov_imm`, **writes r[S]'s
   value into r[X]** — verified for S ∈ {0,1,3,5,8,10,14}, X = 2, both plans. This experiment
   did not sweep that group and **cannot** say whether those four bytes are one instruction or
   a 2-byte op plus an operand word. What is established is only that they have an effect,
   which "not a standalone opcode" does not predict. It was found by accident: it was this
   experiment's first falsifier.

## 9. Observed vs interpreted, and what remains unknown

**Directly observed.** Every number in §2–§7 is a count over the committed `sweep.jsonl` /
`grid.jsonl`, recomputed by `analysis/analyze.py` from raw with no carry-over from
`PROGRESS.md` or from calibration. The observable is the full 16-GPR dump plus two sentinels
plus a 28-word tail poison region out of a buffer pre-filled with `0xDEADBEEF`.

**Interpretation.** That byte+1 bit 0 is a *source-half select* rather than, say, a byte or
sub-word index that happens to look like a half select at 32-bit granularity, is the reading
best supported by the data; it is not separately proven against a sub-16-bit operand model.
Likewise "the register file aliases with period 64" is inferred from `r[S]` and `r[S+64]`
being indistinguishable, which is also consistent with "bit 6 of the field is ignored"; the
two are not separated here, and EXP-0112's independent mod-64 ALU result is the reason to
prefer aliasing.

**Exact tested range.** `dst` 0..15 dense. byte+1 0..255 dense (source registers 0..127, both
halves, both alias bands). byte+2 0..255 dense. byte+3 0..255 dense. The full byte+2 × byte+3
cross-product, 65536 encodings, three times. Sources whose value is host-known: r0..r15 only.
Two register plans. Grid 1, threadgroup 1, compute stage only.

**Not established.**
- **Source registers 16..63 read as 0** (192 of 192 cases, both plans, both runs). That is a
  property of a carrier that allocates 16 GPRs, **not** a property of the field. A carrier with
  a larger register allocation is needed to exercise `S > 15`, and until then the source map is
  `hardware-run` over S ∈ 0..15 ∪ 64..79 and `untested` above that.
- **The fragment stage.** Everything here is the compute stage. EXP-0172 measured a period-16
  register aliasing for `tex_sample.coord` on the fragment stage; whether `n3_mov`'s source
  aliasing is also stage-dependent is untested.
- **Whether the move is 16-bit-only or whether some other byte+2 value performs a single
  32-bit copy.** The complete cross-product found no `(byte+2, byte+3)` that copies both
  halves at once at this `(dst, src)`, but that is one source register and one destination.
- **byte+2's two-source logic ops** (XOR at `& 7 == 3`, OR at `== 4`) are located and their
  operand slots identified, but their per-value maps were not swept. They are reported as
  observations inside `n3_mov.subform`'s note, not as separate verdicts.
- **The two OBSERVATION-status findings in §8.**

**Safe driver fallback.** Emit the canonical non-destructive form: `byte+2 = 0x01`,
`byte+3 ∈ {0x00, 0x01}`, `byte+1 = 2*S + hs` with `S ≤ 15`, and use the two-instruction
sequence for a 32-bit copy. That is the exact configuration with 2520 passing generated cases
and zero failures across two runs and two carriers.

## 10. What this changes for the acceptance gate

`docs/compiler-readiness.md`'s headline — "You cannot write a register move ... which is to
say it blocks the register allocator, which is to say it blocks the back end" — **no longer
holds on G17P.** A back end can now lower `nir_op_mov`, phi nodes, parallel copies,
register-allocator coalescing and spill reloads with an instruction sequence it constructs
itself, from a specification that contains no captured Apple template, and every field that
sequence must fill is `hardware-run` on the actual documentation target.

Three caveats the orchestrator should carry forward rather than round off: the move is 16-bit
granular so every 32-bit copy costs two instructions; `db.json`'s operand model for this
instruction is wrong in a way that fails silently (DEF-0174-1), so it must be corrected before
anyone emits from it; and the source-register range is established only over r0..r15 in a
16-GPR carrier.
