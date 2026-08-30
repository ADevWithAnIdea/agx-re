# EXP-0168 — RESULTS

**Target: Apple A18 Pro / G17P** — `applegpu_g17p`, `AGXAcceleratorG17P`, 5 GPU
cores, `Mac17,5`, macOS 26.6 (25G5043d), Metal family Apple9. Device identity is
read from the live device into `raw/<run>/00_env.json` on every run and is never
taken from a literal.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
  (+ PUBLIC for IEEE-754 / MSL conversion definitions, used ONLY to write host
   oracles, never to source an Apple9 encoding fact)
Inputs inspected: kernels/*.metal (authored by us) and the AGX machine code the
  public newLibraryWithSource: / MTLBinaryArchive API compiled FROM THEM; plus
  this repository's own committed raw from EXP-0138/0140/0141/0144/0147/0155/
  0162/0163/0164.
Apple binary introspection: NONE
Evidence: raw/prefreeze/** (calibration, NEVER evidence)
          raw/g17p_20260830_run02/  gated, forward order
          raw/g17p_20260830_run03/  gated, reverse order
```

> **Status of this document.** The compute arm's two gated runs are complete and
> analysed — verdicts in section 1a. The render arm is built, censused and
> frozen (19 arms, ≥ 2 distinct carrier dimensions per target); its gated runs
> are the remaining device work. Every claim below is labelled with the run(s)
> it rests on.

---

## 1. What was asked, and the one-sentence answer

EXP-0164 withdrew 122 fields to `untested` and named the cheapest way back: the
field NAME `dst` blocks 13 instructions, and twelve more instructions are one
field away. This experiment asked whether those fields can be re-established
with evidence that survives a re-audit.

**The answer is that the old evidence was not merely underpowered — for the most
load-bearing field in the set it was incapable of returning any other result.**
EXP-0140's `uniform_mov.dst` read-back was `device_store(data_reg=D)` where `D`
is the swept `dst`, so field and observable co-varied and a *correct* hardware
result was a constant observed vector **by construction**. Its "16 values
dispatched, 0 observations moved" was the **passing** outcome of a test that
could return nothing else. With a fixed 16-GPR dump and a host-known seed table,
the same field moves **214** times.

---

## 1a. VERDICTS — compute arm, two gated runs (run02 forward, run03 reverse)

**16 `hardware-run` · 6 `proven-dont-care` · 2 `still-underpowered`** across 24
swept names, against a gate deliberately stricter than the orchestrator's: **≥ 99.5%** cross-run
agreement (his bar 99%) and **movement ≥ 4× disagreements** (his 2×), plus ladder
passed in every run, falsifier failed in every run, dense coverage for w ≤ 8, no
case counted whose `validity != valid`, and the byte-mate control interpreted.

| field | verdict | vals | distinct_bytes | enc_range | start | width | moved | carriers | agree% | common |
|---|---|---|---|---|---|---|---|---|---|---|
| `atomic_mem.addr_desc_hi` | **hardware-run** | 4 | 36 | 4 | 54 | 2 | 15 | 3 | 100.0 | 36 |
| `cvt_f2h.op` | **hardware-run** | 256 | 256 | 256 | 16 | 8 | 221 | 2 | 99.609 | 256 |
| `cvt_f2i.dst` | **hardware-run** | 256 | 256 | 256 | 24 | 8 | 190 | 2 | 100.0 | 256 |
| `falu2.dst` | **hardware-run** | 16 | 16 | 16 | 4 | 4 | 15 | 1 | 100.0 | 16 |
| `falu2i.dst` | **hardware-run** | 16 | 16 | 16 | 4 | 4 | 15 | 1 | 100.0 | 16 |
| `falu_acc.cache` | **hardware-run** | 2 | 28 | 2 | 21 | 1 | 28 | 3 | 100.0 | 28 |
| `get_sr.dst` | **hardware-run** | 16 | 16 | 16 | 4 | 4 | 15 | 1 | 100.0 | 16 |
| `get_sr.dst_hi` | **hardware-run** | 8 | 8 | 8 | 29 | 3 | 8 | 1 | 100.0 | 8 |
| `mov_imm.byte1` | **hardware-run** | 256 | 768 | 256 | 8 | 8 | 767 | 2 | 100.0 | 768 |
| `mov_imm.imm_top` | **hardware-run** | 2 | 6 | 2 | 15 | 1 | 5 | 2 | 100.0 | 6 |
| `pack_convert.b7` | **hardware-run** | 256 | 256 | 256 | 56 | 8 | 190 | 3 | 100.0 | 256 |
| `shift_amt_move.src_flag` | **hardware-run** | 2 | 26 | 2 | 15 | 1 | 22 | 1 | 100.0 | 26 |
| `uniform_mov.dst` | **hardware-run** | 16 | 224 | 16 | 4 | 4 | 214 | 3 | 100.0 | 224 |
| `uniform_mov.form_b2` | **hardware-run** | 256 | 256 | 256 | 16 | 8 | 232 | 1 | 100.0 | 256 |
| `uniform_mov.opdesc_b3` | **hardware-run** | 256 | 256 | 256 | 24 | 8 | 208 | 1 | 100.0 | 256 |
| `unpack_convert.dst` | **hardware-run** | 256 | 256 | 256 | 24 | 8 | 188 | 3 | 100.0 | 256 |
| `cvt_f2i.b9` | **proven-dont-care** | 256 | 256 | 256 | 72 | 8 | 0 | 2 | 100.0 | 256 |
| `if_push.scope` | **proven-dont-care** | 256 | 256 | 256 | 16 | 8 | 0 | 4 | 100.0 | 256 |
| `stop.b1` | **proven-dont-care** | 256 | 256 | 256 | 8 | 8 | 0 | 2 | 100.0 | 256 |
| `stop.b2` | **proven-dont-care** | 256 | 256 | 256 | 16 | 8 | 0 | 2 | 100.0 | 256 |
| `stop.b3` | **proven-dont-care** | 256 | 256 | 256 | 24 | 8 | 0 | 2 | 100.0 | 256 |
| `stop.reserved` | **proven-dont-care** | 66 | 66 | 16777216 | 8 | 24 | 0 | 2 | 100.0 | 66 |
| `copysign.operands` | **still-underpowered** | 256 | 256 | 256 | 24 | 8 | 0 | 1 | 100.0 | 256 |
| `get_sr.form` | **still-underpowered** | 2 | 2 | 2 | 3 | 1 | 0 | 1 | 100.0 | 2 |

### What is actually MERGEABLE — 18 of the 24, and the split matters
Six of the 24 swept names are **not declared `db.json` fields**: `mov_imm.byte1`,
`stop.b1`, `stop.b2`, `stop.b3`, `uniform_mov.form_b2` and
`uniform_mov.opdesc_b3` are names **this experiment invented** for whole-BYTE
companion and attribution sweeps. They carry real measurements — `uniform_mov`'s
byte+2 form selector is the axis the entire headline result turns on — but
merging them as field rows would be a silent mis-attribution of exactly the kind
this experiment exists to prevent. Every row now carries
`is_declared_db_field` / `synthetic_byte_sweep` / `merge_note`, computed against
the pinned descriptor rather than asserted, so `merge_verdicts.py` refuses them
**by intent rather than by accident**.

| | declared db.json fields (mergeable) | synthetic byte sweeps |
|---|---|---|
| `hardware-run` | **13** | 3 |
| `proven-dont-care` | **3** | 3 |
| `still-underpowered` | **2** | 0 |
| total | **18** | 6 |

The 13 mergeable `hardware-run` rows: `uniform_mov.dst`, `falu2.dst`,
`falu2i.dst`, `get_sr.dst`, `get_sr.dst_hi`, `cvt_f2i.dst`,
`unpack_convert.dst`, `pack_convert.b7`, `cvt_f2h.op`, `falu_acc.cache`,
`mov_imm.imm_top`, `shift_amt_move.src_flag`, `atomic_mem.addr_desc_hi`.
The 3 mergeable `proven-dont-care`: `if_push.scope`, `cvt_f2i.b9`,
`stop.reserved`.

Cross-run agreement is **100.000%** on 23 of 24 fields and **99.609%** on
`cvt_f2h.op` (1 disagreement in 256, against 221 moved = 221×). No field is below
the bar on agreement or on movement. **There are no skip placeholders in either
run** — zero hangs, zero stopped fields — so no count here rests on a
never-dispatched case, which is the specific flaw `analysis/rescore_0144.py` had
to unpick in EXP-0144.

### The six `proven-dont-care` rows, and what label they should carry
`if_push.scope` (4 carriers), `cvt_f2i.b9` (2), and `stop.reserved` / `stop.b1` /
`stop.b2` / `stop.b3` (2 each) are **inert with detection power proven** — dense
coverage, every carrier passing its ladder, every falsifier firing, 0 movement,
100.000% agreement. A genuinely inert field **cannot satisfy the movement clause
by construction**, so it is reported as `proven-dont-care` with its ladder
numbers rather than self-promoted.

Per the orchestrator's ruling these become **`single-template-inference`, not
`hardware-run`**, unless the field's ROLE is independently known — emitter-grade
asserts the implementer may *choose* the value, and "emit what the compiler
emitted" is a captured-template dependency. My reading of the four `stop` rows is
that their role IS known (they are the reserved payload of a program-end token,
and no value of any of them prevented termination), but that is his call. Note
`stop.reserved` is a **24-bit** field: 66 of 16,777,216 values were dispatched,
so its row carries `under_covered: true` and its don't-care claim is bounded to
the sampled set, not the whole field.

### The two `still-underpowered` rows, and why more device time will not fix them
- **`copysign.operands`** — 256/256 dense, 100.000% agreement, 0 movement, but
  **ONE carrier**, because the compiler will not emit `copysign` in a
  high-register-pressure kernel at all (it lowers the sign transfer to
  `n2_op6` + `falu*`). One carrier cannot distinguish an inert field from a
  carrier blind to it — the EXP-0155 lesson — so this stays `untested` rather
  than being promoted on one carrier's word.
- **`get_sr.form`** — 2/2 dense (1-bit field), 100.000% agreement, 0 movement,
  one carrier. Same reasoning.

Both need a *structurally different* carrier, not more values and not more runs.

### Which withheld rows this closes
Of the 26 rows in scope, the compute arm settles 24 (the other two,
`frag_color_pack.dst` and `vtx_out_pos.dst`/`slot`, are the render arm's, plus
`pixel_order.kind` and `iter_at.grp`). **`dst` itself is now measured on
`uniform_mov`, `falu2`, `falu2i`, `get_sr`, `cvt_f2i`, `unpack_convert`, and — via
the byte+2 cross-product — the `reg_move_c0/c1/c2var/c9` forms**, all
`hardware-run`. `reg_move_cb` is measured and **differs** (1/15), which is a
result about that form, not a gap. `matrix_mac.dst` is NOT ATTEMPTED by design.

---

## 1b. VERDICTS — render/vertex arm, ONE gated run (PROVISIONAL)

`raw/g17p_20260830_rclean01`: **2,632 cases in 85.1 s, 4 hangs,
`stopped_early: false`, 0 refused arms**, run as a hang-free-families-first pass
so the clean families were banked before any `frag_color_pack` hazard was
dispatched.

> **Every row here is PROVISIONAL.** One gated run means cross-run agreement —
> the pre-registered promotion gate — has **not been evaluated**. The analyser
> stamps that on each row itself. The second gated run is **BLOCKED** (§9a).

| field | bucket | provisional label | arms | distinct carrier dims |
|---|---|---|---|---|
| `pixel_order.kind` | **LIVE** | `hardware-run` | 6 | 3 |
| `vtx_out_pos.dst` | **LIVE** | `hardware-run` | 3 | live on 1, inert on 2 |
| `vtx_out_pos.slot` | **INERT-ROBUST** | `single-template-inference` | 3 | **3** |
| `iter_at.grp` | **LADDER-FAILED** | `untested` | 0 eligible | — |

### `vtx_out_pos.slot` — EXP-0147's own open follow-up, answered
EXP-0147 called `slot` inert in a **single-varying** carrier, and its RESULTS.md
names "`vtx_out_pos.slot` in a multi-varying carrier" as the follow-up. Here it
is inert at 256/256 across **three distinct carrier dimensions**: the
single-varying control, 8 scalar FLAT varyings, and the **MIXED-WIDTH**
discriminator (`half/half2/float/float2/float4`). That third one exists because
with uniform-width varyings the two candidate readings of `slot` — an ordinal
into a slot table, and a byte offset into the output block — differ only by a
constant factor and are **indistinguishable at every value**; mixing widths makes
the map non-linear. Every arm passed its ladder and its falsifier. This is a real
negative, not a carrier that could not see.

### `vtx_out_pos.dst` moves ONLY in the degenerate carrier
1 of 16 moved on `r_v1` (single varying); **0 of 16** on `r_v8f` and `r_vmix`. A
field live in the degenerate carrier and inert in the rich ones is an odd shape,
and I will not explain it from one run. Reported as measured, flagged for the
second gated run.

### `pixel_order.kind`: the pre-registered model holds where it came from and
### BREAKS on the non-commutative carrier
The partition was derived **offline from EXP-0162's raw before this experiment
ran anything**, and reproduces all 256 of its recorded outcomes on both members.
Against this experiment's carriers:

| arm | carrier dimension | predicted 256, held |
|---|---|---|
| `r_rog8#0`, `r_rog8#1` | commutative additive RMW (EXP-0162's own shape) | **256/256 = 100%** |
| `r_rog2#1` | two ordered resources of different type | **256/256 = 100%** |
| `r_rog2#0` | two ordered resources of different type | 232/256 = 90.6% |
| `r_rogx#0` | **non-commutative affine** RMW | **32/256 = 12.5%** |
| `r_rogx#1` | **non-commutative affine** RMW | 64/256 = 25.0% |

A cross-experiment replication that **succeeds exactly where it should and fails
where the model was never tested.** EXP-0162's carrier could only ever exhibit
ordering *loss*; `r_rogx` is order-sensitive in a way loss alone cannot explain,
and the model does not survive there. Observed live bits 1, 2, 4 (plus 5, 6 on
`r_rog2#0`) against the model's 1, 2, 4. This also closes EXP-0162's
**auditability** gap: its per-value sweep was recorded under
`instr=acquire|release, field=byte1`, so no record under `raw/` was attributable
to `pixel_order.kind`. These are.

### `iter_at.grp` is NOT ESTABLISHED — both reasons recorded
1. **Its ladder FAILED on both arms.** `iter_at.loc` (byte+7) did not produce ≥ 2
   distinct hashes, *including on the 4-sample carrier* where EXP-0163 measured
   it moving 128/256. Under R3, an arm that cannot show its ladder is DISCARDED
   and its inertness is not evidence — so this is `untested`, **not "inert"**.
2. **Only 3 of 256 values were dispatched.** Under a plain ascending order the
   sweep hit `grp = 0`, hung, hit `grp = 1`, hung, and stopped on the
   two-hangs-per-field budget **without ever reaching either legal value**
   (0x2f, 0xaf). Identical in shape to `frag_color_pack.dst` 194..197: *the
   hazard sits in front of the thing you came to measure, so every run spends its
   budget before it learns anything.* `coverage_for()` now takes a `first` list
   and the runner feeds it the descriptor's `legal_values`, giving the order
   **0x2f, 0xaf, then the rest** — verified offline, **not yet run gated**.

### `frag_color_pack.dst` — not in this run
Deliberately deferred to a separate pass because its arms hang (§8.1) and a
sibling experiment was live on the machine. Its coverage-gap fix (defer the whole
192..197 band so 198..255 is banked first) is in place and verified offline but
has **not** produced a gated run.

---

## 2. THE HEADLINE: `dst` × form, the cross-product nobody ran

The compact-move family (`uniform_mov`, `reg_move_c0/c1/c2var/c9/cb`) is ONE
4-byte instruction (EXP-0087/EXP-0140): `byte0`-hi = `dst`, byte+1 = source,
byte+2 = form selector, byte+3 = op_desc. EXP-0140 swept `dst` at **one** byte+2
value and `analysis/verdicts.py:327` fanned that single verdict verbatim onto all
six descriptor names — although its own probe shows the forms behave differently.

**There is no `dst` × form cross-product anywhere in that matrix.** There is one
here: 16 `dst` × 14 byte+2 values = 224 distinct encodings, in a carrier whose
store list is identical in every case, scored against the host-known seed table.

| byte+2 | descriptor(s) whose `match` it satisfies | `dst` 0..14 → exactly slot `dst` | value written |
|---|---|---|---|
| 0x00 | `reg_move_c0` | **15/15** | 0x0 |
| 0x01 | `reg_move_c1`, `uniform_mov` | **15/15** | 0x0 |
| 0x02 | — | **15/15** | 0x30 |
| 0x05 | — | **15/15** | 0x0 |
| 0x09 | `reg_move_c9` | **15/15** | 0x0 |
| 0x11, 0x15, 0x31, 0x35 | — | **15/15** each | 0x0 |
| 0x21, 0x25 | `reg_move_c2var` (bits 20..23 = 2) | **15/15** each | 0x0 |
| 0x0b | `reg_move_cb` | **1/15** — `dst` deviates | 0x4b |
| 0x0f, 0x26 | — (EXP-0113's "nondeterministic" pair) | **0/15**, many slots move | — |

**`dst` selects the destination register and the changed slot tracks the field's
value at 11 of 14 form values — including every form EXP-0140 classified
`silent_zero` (c0, c2var) and `wrong_value` (c9).** Those forms still *write* the
destination; only the value written is uninteresting. So the observable has to be
*which slot changed*, and a single-word read-back cannot express that dimension
at all.

`reg_move_cb` genuinely differs (1/15) and byte+2 = 0x0f / 0x26 change the
instruction **length** — their signature is a partially-poisoned dump
(`r0..r8 = deadbeef`), i.e. the rest of the program was misparsed. Both are
reported as themselves.

**Deliberately not claimed:** a 1:1 form→descriptor map. 0x01 satisfies both
`reg_move_c1` and `uniform_mov`; `c2var` is pinned on bits 20..23, not the low
nibble; so several values are jointly satisfiable. Every case records its full
instruction `bytes`, so this is re-keyable without re-running — which EXP-0144's
raw is not, because its case labels were read from a `db.json` whose field names
later moved.

---

## 3. RETRACTED — the "r15 is not writable" claim was MY OWN SCAFFOLDING

**This section previously reported a hardware fact. It was wrong, it was wrong
by construction, and it is the same failure I convicted EXP-0140 of.** EXP-0174
found it; the mechanism is confirmed here in my own source.

**What I claimed:** that a write whose 4-bit destination nibble is 15 is
discarded and the slot reads 0 — presented as a driver-relevant register-file
fact, with the caveat that I could not distinguish "hardwired zero register"
from "nibble 15 means no destination".

**What is actually true:** `isa_helpers.R_IDX = 15`. That is the register my own
`device_store` scaffolding uses as its index register, and `store_word()` emits
`mov_imm(R_IDX, 0)` **before every single store** — including the store that
reads back r15:

```python
R_IDX = 15          # device_store index register; re-seeded to 0 before EVERY store
def store_word(word_idx, data_reg, base_slot=0):
    return (mov_imm(R_IDX, 0)
            + device_store(R_IDX, word_idx // STORE_STRIDE_WORDS, base_slot,
                           data_reg=data_reg))
```

So r15 is clobbered to 0 immediately before it is observed, in every case, in
every arm, on both seeding paths. **r15 could never have read anything but 0,
whatever the hardware did.** EXP-0174 confirms the positive result on a plan
indexed on r7: r15 holds its seed in all 64 baselines and is written normally.
**r15 is an ordinary writable GPR.**

**This is exactly rule R-A — the observable must not co-vary with the field
under test — violated in my own harness.** EXP-0140's read-back was
parameterised by the swept `dst`; mine was parameterised by the register being
read. In both cases the apparatus destroyed the thing it was measuring, and in
both cases the result was a confident, clean-looking, *impossible* observation.
I caught theirs by reading their code and missed mine by not reading my own. The
rule is worth more than the retracted fact.

**What survives:** `dst = 15` genuinely *is* undecidable **in this carrier** —
not because the hardware discards it, but because my scaffolding overwrites it.
The `undecidable_values` / `decidable_values` accounting on the verdict rows is
therefore still correct as a statement about coverage (`uniform_mov.dst`
dispatches 16, decides 15); only the stated *cause* changes, and
`undecidable_why` has been rewritten to say so. No verdict label moves.

**Left open, deliberately not claimed:** run02 also showed `regs[0] = 0` where
the seed is 10, at the baseline of several arms. EXP-0174 reports that anomaly
does **not** reproduce on its r7-indexed plan. I have no mechanism for it and it
is not worth a guess, so it is recorded as an open observation rather than
promoted to a finding.

---

## 4. The strongest negative: `if_push.scope` is inert with proven detection power

| arm | carrier dimension | ladder distinct | swept | moved | falsifier |
|---|---|---|---|---|---|
| `IFPUSH/flat` | ONE non-nested scope (the blind control) | 4/16 | 256 | **0** | fires |
| `IFPUSH/loop` | a real loop | 4/16 | 256 | **0** | fires |
| `IFPUSH/nest3.outer` | 3 genuine nesting levels, outer push | 4/16 | 256 | **0** | fires |
| `IFPUSH/nest3.inner` | 3 genuine nesting levels, inner push | 6/16 | 256 | **0** | fires |

Four structurally distinct carriers, every ladder passing, every falsifier
firing, dense 256/256, zero movement everywhere. The ladder is `scope_kind` — the
same instruction's neighbouring byte, which EXP-0140 measured moving 178 cases to
`wrong_value` — so the observable demonstrably resolves differences on this
instruction and still cannot see `scope` at any value.

This survives the three specific objections that made EXP-0140's flat verdict
unconvincing (M2c): its if/else lowered to `isel10`, a SELECT exercising no mask
stack (here **every divergent region contains a store**, which cannot be
if-converted); both its live pushes carried scope 0x54, so the nesting-parity
model was never instantiated (here **three genuine nesting levels**); and its
observable was one GPR over 8 lanes of a partially-filled SIMD (here a per-lane ×
per-region slot pattern out of a poisoned buffer over a full 32-lane dispatch).

Per the orchestrator's ruling, a proven-inert field whose ROLE is not
independently known is **`single-template-inference`, never `hardware-run`** —
emitter-grade asserts the implementer may *choose* the value, and "emit what the
compiler emitted" is a captured-template dependency.

---

## 5. Ten by-construction defects — nine found here, one found by EXP-0174

Every one was caught by the pre-freeze smoke or by cross-checking an analysis
against an independent measurement — none by inspection. They are the substance
of this experiment as much as the verdicts are.

| # | defect | why it would have produced a confident wrong answer |
|---|---|---|
| 1 | `SEED_I[15] = 0` collided with the value under test | reg_move forms 0x00/0x01/0x03 **write zero**, so `dst=15` could not be told from "did nothing". The "fix" (seed 121) never landed — see defect 10 |
| 2 | falsifier `byte0 = 0x00` confounded with the swept field | `uniform_mov`'s byte0 is `opcode nibble │ dst`, so 0x00 also sets `dst=0` — and the anchor's `dst` is 0. Measured **identical to the baseline** on 4 REGMOVE arms; also on `COPYSIGN/lowpress` and `ATOMIC/highreg` |
| 3 | `STOP/terminal` and `STOP/midprogram` were **one carrier** | `STOP/terminal` fell through to `synth_program()`, which puts the block in the BODY — the same program shape. Both gave whole-dump-poison on hardware |
| 4 | `NEEDED` was a hand-maintained lookup list | omitting `iter_at` made `--mode freeze` report *"no occurrence in this carrier — a STRUCTURAL RESULT about when the instruction is emitted"*. The instruction was at offset 8 all along |
| 5 | the terminating arm's **correct** result scored as corruption | `STOP/midprogram`'s absent POST sentinel IS the measurement; the run-integrity rule discarded **835 of 836** cases and silently cut `stop.*` to one carrier |
| 6 | the `iter_at` carrier could not make the compiler emit `iter_at` | plain smooth interpolation lowers to the location-implicit form; `iter_at` needs an EXPLICIT location (`[[centroid_perspective]]`) — which is why EXP-0155's carrier was `c_cent1` |
| 7 | `STOP/terminal`'s discriminating word was outside the classifier | the register dump has already run in every case on that carrier, so the 16 regs are identical by construction; the falsifier plainly fires (`probe 0x4d` vs `0xdeadbeef`) but scored `ok`, failing the arm's own ladder and blocking all four `stop` fields. The sweep could see **nothing**: 836 cases, all `ok`, all `moved=False` |
| 8 | I added an instruction family with no host ORACLE | `oracle()` branches `vtx`/`rog`/else-`fcp`; the new `itr` family fell through to `fcp` and died on `KeyError: 'fcp_values'` at the first baseline dispatch. **The offline mock test never calls `oracle()`**, so a family can pass the mock with no oracle at all |
| 10 | **r15 is my `device_store` index register**, and `store_word()` re-seeds it with `mov_imm(15,0)` before every store — including the store that reads r15 | produced a clean, reproducible, **impossible** observation that I wrote up as a hardware fact ("nibble 15 discards the write"). Rule R-A violated in my own harness; retracted in §3 |
| 9 | the hazard sat in front of the measurement, twice | `frag_color_pack.dst` (band 194..197) and `iter_at.grp` (254 of 256 values out-of-descriptor) both blow the hang budget *before* reaching the values worth measuring — so every run since EXP-0155 has spent its budget and learned nothing. Fixed by ordering: legal values first, hazardous band last |

### Four generalisable rules for `FIELD-SWEEP-PROTOCOL`

**R-A — the observable must not co-vary with the field under test.** A sweep
whose read-back path is parameterised by the swept value measures nothing about
the value. (With `iter_at.loc` the *carrier* could not express the field; with
`uniform_mov.dst` the *oracle* could not.)

**R-B — a falsifier that clobbers a byte carrying BOTH the opcode and a field
under test is confounded with that field's own values.** "Not this instruction"
must be expressed in bits the field does not own, and the substitute must be
**measured** to fire, not assumed to. On `uniform_mov`, low nibble 0x0 and 0x1
are *different instructions that write the same destination register from the
same dst bits*; 0x4/0x6/0x7/0xc/0xe/0xf change the instruction length; only 0x5
and 0xd are inert-with-the-program-completing at both forms.

**R-C — on a carrier where the ABSENCE of something is the measurement, the
generic outcome/validity classifier reads the wrong word and returns a confident
negative.** Both of this experiment's `stop` arms had this, in opposite
directions: the midprogram arm's correct result (no POST sentinel, whole window
poison) was scored as *corruption*, discarding 835 of 836 cases; the terminal
arm's discriminator (a post-stop witness word) was simply never read, so 836
cases scored `ok`/`moved=False`. A carrier built around an absence needs its
classifier told which word carries the signal.

**R-D — order the sweep so the hazard cannot cost you the measurement.** When a
field's dangerous values sit numerically *before* its interesting ones, an
ascending sweep spends the hang budget and stops without ever dispatching what it
came for — and the gap is **self-perpetuating**, because the next run does the
same thing. `frag_color_pack.dst` 194..197 has now defeated three experiments
this way, and `iter_at.grp` defeated this one until the order was fixed.
Legal/interesting values first, known-hazardous band last.

---

## 6. An offline result that costs no device time

`analysis/rescore_0144.py` re-derives EXP-0164's cross-run gate from EXP-0144's
committed raw, comparing only runs that **actually dispatched** the value.

| field | audit said | best measured pair | common | agree |
|---|---|---|---|---|
| `pack_convert.b7` | 2.73% | run05 vs rv01 | 256 | **100.00%** |
| `cvt_f2i.dst` | 82.42% | run02 vs rv01 | 225 | **99.56%** |
| `cvt_f2i.b9` | inert / 1 carrier | run03 vs rv01 | 256 | **100.00%** |
| `unpack_convert.dst` | 25.78% | run05 vs rv01 | 192 | 98.96% |
| `cvt_f2h.op` | 91.41% | run01 vs run04 | 256 | 98.44% |

EXP-0164 picks the two gated runs with the most distinct attributed values,
**ties broken alphabetically** (`audit.py:78-80`), which selects `run03` — a
capture EXP-0144 itself disowns. run03 holds **17 measured cases and 248
placeholders** for `pack_convert.b7`; run03/run04 hold **0 measured and 272
placeholders each** for `unpack_convert.dst`. Those placeholders carry
`outcome:"hang"`, and EXP-0164 treats only `{invalid_run, victim, skipped}` as
contamination, so they were scored as observations.

Per the orchestrator's ruling these rows are **not restored**: they are recorded
as *"withdrawn for the wrong reason, superseded by this experiment's own G17P
measurement"*. The underlying data is M4/G16G; only this experiment's own G17P
sweep carries a target-correct label.

---

## 7. Descriptor defects handed over (`db.json` NOT edited — EXP-0165 owns it)

`analysis/bitcheck.py` checks exhaustively, over every value, that the harness's
bit surgery equals `isadb.assemble`. **79 fields agree exactly, 0 mismatches.**
The other 4 are a first-class result: a field DECLARED over bits its own
descriptor's `match` constant PINS — the same self-contradiction EXP-0162 fixed
in `pixel_order.flags`.

| descriptor | field | declared bits | match pins | real encodable range |
|---|---|---|---|---|
| `iter_at` | `grp` | 0..7 | **0..6** | **2** (bit 7 only; 0x2f, 0xaf) |
| `pixel_order` | `scope` | 24..31 | 28..30 | 32 |
| `reg_move_cb` | `form` | 16..23 | 16..19 | 16 |
| `shift_amt_move` | `kind` | 16..23 | 16..19 | 16 |

`iter_at.grp` is also why that field has never been swept past ~25 of 256 values
on any run: 254 of its 256 values are out-of-descriptor bit patterns, i.e. a
decode desync, and both EXP-0155 and EXP-0163 tripped the two-hang stop rule on
them. It **cannot** satisfy this experiment's own dense-coverage clause, and its
row says so (`encodable_range: 2`, `coverage_is_bounded_by_descriptor: true`)
rather than quietly relaxing the gate.

---

## 8. New hardware facts beyond the field verdicts

1. **`frag_color_pack.dst` = 194 and 196 are GENUINE HANGS on G17P** (not
   contained faults). They are the first two values past the point where
   EXP-0155's per-field stop rule fired — i.e. the first two values of the
   `194..255` region that had never been dispatched on **any** target. This also
   explains why that gap is **self-perpetuating**: under a forward order a sweep
   reaches 194, hangs, spends its budget and stops. This experiment defers all
   four hazardous values (192, 193, 194, 196) to the END of the order so
   `197..255` is banked first.
2. **`uniform_mov` byte+2 = 0x02 writes `0x30` and 0x0b writes `0x4b`**, while
   ten other form values write 0 — the form selector chooses the *value* as well
   as the form.
3. **byte+2 = 0x08 is a 16-bit-lane merge**: it writes `0x00ab00XX` where `XX` is
   the destination's *previous* low byte (r8→`0x00ab005e` with seed 0x5e,
   r10→`0x00ab0071` with seed 0x71, r13→`0x00ab007f`, r14→`0x00ab0003`). It
   preserves the low half and writes the high half.
4. **`uniform_mov` byte0 low nibbles 0x4, 0x6, 0x7, 0xc, 0xe, 0xf change the
   instruction length** (partially-poisoned-dump signature); 0x5 and 0xd are
   inert with the program completing; 0x0 and 0x1 are distinct instructions that
   write the same destination from the same dst bits.
5. **`vtx_out_pos` is emitted only by vertex carriers that do NOT write a device
   buffer** — present in `r_v1`, `r_v8f`, `r_vmix`; absent from `r_v8`, `r_v4v`,
   `r_vsrc`, all three of which bind `--out-buf` to the vertex stage. So the
   "second, independent observation path" those carriers were built for is not
   available for this instruction.
6. **`frag_color_pack` is emitted only for the 8-bit unorm attachments** —
   present in `r_fcp1`, `r_fcp1s`, `r_fcp4`; absent from `r_fcpf` (RGBA32Float)
   and `r_fcph` (16-bit float).
7. **`k_rot_uni`'s `_agc.main` does not tokenize** (62 leftover bytes,
   `<unknown>@22`) and `k_f2h_consumed` leaves 6 (`<unknown>@60`) — db.json
   coverage gaps, recorded, not repaired here.
8. **The compiler does not emit `copysign` in a high-register-pressure kernel**
   (`k_copysign_rp`, 180 B, clean tokenization) — it lowers the sign transfer to
   `n2_op6` + `falu*` instead. So `copysign.operands` has exactly ONE reachable
   carrier and cannot clear a two-carrier bar from own-shader evidence.
9. **`reg_move_c0/c1/c2var/c9/cb` have ZERO occurrences in the whole probe
   corpus** — the Apple compiler never emits those forms from any MSL we can
   write. They are reachable only by setting byte+2 on the `uniform_mov` anchor,
   which is the structural justification for the `REGMOVE/form` arm.

---

## 9. Run integrity

| | run02 (forward) | run03 (reverse) |
|---|---|---|
| cases | 10,366 | 10,366 |
| **hangs** | **0** | **0** |
| fields stopped by budget | **0** | 0 |
| skip placeholders | **none** | none |
| `invalid` diverted to re-run | 849 | — |
| victims | 83 | 119 (see below) |

**Zero hangs and no stopped fields means there are no skip placeholders in either
run** — which is exactly what made EXP-0144's and EXP-0155's verdicts
unscoreable, and what `analysis/rescore_0144.py` had to unpick.

**Toolchain identity, asserted on the device rather than assumed.** `ISA_DIR`
resolves to the pinned `work/frozen/` snapshot,
`db.json 07ad894d…` / `isadb.py c97c2a22…`, **172 instructions / 1062 fields**,
with `falu2.srcA_class` / `srcB_class` present. The shared
`~/agxre/tools/agx-isa/db.json` is stale (`f5db942f…`, 171 instructions / 1036
fields, `mod_lo` replacing the two `_class` fields) and **was never read**.

> **The near-miss worth reading.** `work/frozen` did not initially exist on the
> device, so `_find_isadb()` fell past candidate #1. The candidate order hashed
> into `CAPTURE_CONTRACT.json` at freeze had `~/agxre/tools/agx-isa` — **the
> stale shared copy** — as the first existing entry. A post-freeze edit I
> recorded at M8 as *"benign — it changes WHERE the pinned db is looked up, not
> WHAT"* reordered that list to prefer the private per-experiment copy. **That
> one line is the only reason this experiment is not keyed to `mod_lo`.** The
> lesson is not that we got lucky: **a path-search fallback list is a silent
> correctness surface**, and a harness should FAIL when its pinned toolchain is
> absent rather than quietly resolve something else.

**The `device_load` false-movement mode does not reach this experiment**, for two
independent reasons. *By construction:* STYLE-S seeds r0..r15 with `mov_imm` /
`falu2i` immediates — there is no `device_load` in the seeding path — and the
`dst` oracle is a host-computed slot pattern, not digest-equality against a
baseline. *By measurement:* six identical dispatches of each of the five STYLE-P
probes gave **1 distinct digest** each, and run02's `baseline.jsonl` holds 70
baseline takes across 33 arms with **exactly 1 distinct baseline hash per arm** —
including `STOP/midprogram`, whose 7 takes span the 10 baseline-drift child
restarts and returned the same hash each time. **Arms with a drifting baseline:
none.**

**Concurrency cost, measured, for `FIELD-SWEEP-PROTOCOL` §7.** Running the render
smoke alongside gated run03 produced 3 hangs on the `frag_color_pack@r_fcp1` arms
and raised run03's victim count from run02's 83 to **119 (+43%)**. run03 stayed
clean, but the render smoke was killed and the render arm deferred: unlocked
sweeps are cheap when both arms are hang-free and are not free when one splices a
known-hazardous field.

### 9a. BLOCKED: the second gated render run
The neo also hosts EXP-0169, EXP-0171 and EXP-0172. `ps` showed **39, then 23,
`agxrun_persist` / `gfrun` processes**. Render throughput collapsed from
**31 cases/s** (rclean01: 2,632 cases in 85.1 s) to **~0.07 cases/s** — 3 cases in
45 s, a ~400× slowdown. A second gated run at that rate is ~10 hours, so it was
stopped rather than hold the machine. This is a **scheduling** fact, not a
hardware one, and it is exactly what `gpuwatch.jsonl` exists to record.

Also flagged: **my `frag_color_pack` arms generate genuine device hangs**
(192..197, and `src_present_mask = 0xff`), and a hang kills a sibling's in-flight
command buffers. The render arm was resequenced to run the hang-free families
first for that reason, so the window in which this experiment is dangerous to
EXP-0172 is bounded and known.

**Throughput, because M6's estimate was wrong by 8×.** ~2.4–5.6 cases/s, not the
44.9 EXP-0154 measured — this matrix pays for majority-of-3 confirmation, an
OS-fault-class lookup on every non-`ok` case, and a baseline revalidation every
300. A gated run is ~40–60 min, not ~4.

---

## 10. Machine-readable coverage on every row

Every verdict row carries `values_dispatched`, `distinct_bytes`,
`encodable_range`, `start`, `width`, plus `dense_required`, `dense_ok`,
`bytes_per_value` and `under_covered` — and, where it applies,
`undecidable_values` / `decidable_values` / `undecidable_why`.

`distinct_bytes` is counted from each record's own `bytes` key, **never** from the
dispatched-value count: it is the only thing that reveals the DEF-0166-1
signature, where a sweep dispatches 256 values while the hardware sees far fewer
distinct encodings. `bytes_per_value` makes it a ratio — `uniform_mov.dst` reads
14.0, which is the 14-form cross-product working.

All 28 fields this experiment touches were checked against the repo's **current**
`db.json` (`322847609d…`, which has moved since the freeze): **identical
`start`/`width` in both, and the frozen/current field-NAME sets are equal**, so
these rows will pass `merge_verdicts.py`'s stale-DB refusal rather than trip it.

---

## 11. Not attempted, and why

- **`matrix_mac.dst`** — needs a simdgroup-matrix carrier, and it is one of
  *twelve* withheld fields on `matrix_mac`, so repairing `dst` alone cannot
  recover the instruction. **NOT ATTEMPTED**, never reported as inert.
- **`copysign.operands`** — the second (high-pressure) carrier does not exist,
  because the compiler will not emit `copysign` there. **NOT REACHED** at two
  carriers; the one carrier's result is reported as a one-carrier result.
- **`SHIFTMOVE/uni`** — `k_rot_uni` yields no `shift_amt_move` occurrence and its
  `_agc.main` does not tokenize. `arm_not_run` **with the reason**.
- **`iter_at.grp`'s out-of-descriptor region** — 254 of 256 values are a decode
  desync that has hung the device in two prior experiments. Only the two legal
  values are swept; the byte-mate control dispatches the pin's own legal value
  only.

---

## 12. Reproduce

See `README.md`. The offline half needs no device:

```sh
python3 analysis/rescore_0144.py     # the EXP-0144 re-scoring
python3 analysis/bitcheck.py         # bit surgery vs isadb.assemble, all values
python3 harness/dryrun.py            # builds every arm's program
python3 analysis/verdicts.py --runs raw/g17p_20260830_run02 raw/g17p_20260830_run03
```
