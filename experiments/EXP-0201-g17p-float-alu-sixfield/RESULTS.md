# EXP-0201 — RESULTS

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6,
Metal family Apple9), `192.168.170.254`. **Nothing ran on the M4.**
**Clean-room:** `HW-PROBE` + `OWN-SHADER`. Every byte spliced, decoded or inspected is the compiled
form of our own MSL in `kernels/k_falu201.metal`. **No Apple binary was disassembled or
introspected.**
**Gate applied:** `PRE_REGISTRATION.md` §7 as amended by `PRE_REGISTRATION-A.md`, implemented by
`analysis/verdicts.py` and nothing else. Verdicts are recomputed from `raw/` on every invocation,
never read back from a run manifest.

---

## 0. Headline

**No field is promoted. One gate blocks all six, and it is the same gate: the machine was never
quiet.** Everything else passes for five of the six.

Five sibling experiments (EXP-0200, 0202, 0204, 0205, 0206) dispatched GPU work continuously
throughout this experiment's eight runs. `harness/gpuwatch.py` measured it rather than assuming
it: of the eight runs, **exactly one (`run01`) had zero foreign *dispatch* runners**, and even that
one saw a sibling's `shdump`/`MTLCompilerService` in 6 of 128 samples. Under
`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` Gate E a contaminated run **cannot confirm at all**, so this
experiment reports `reproducibility: incomplete — no clean confirmation window` and promotes
nothing, exactly as `PRE_REGISTRATION-A.md` §A4 pre-committed.

That is a bounded, single-cause gap, and it is worth separating from what the runs *did* establish:

Arm counts per field: `falu3.op` 4, `falu3_ext.op` 5, `fspecial_est.srcA` 5,
`falu3_srcmod12.opsel` 3, `falu3_srcmod12.ctrl` 3, `copysign.operands` 5.

| field | geometry | liveness | semantics | recipe | reproducibility | blocked by |
|---|---|---|---|---|---|---|
| `falu3.op` | geometry-mapped | **live** | **bounded-map** | not-generated | auditable | Gate E only |
| `falu3_ext.op` | geometry-mapped | **live** | **bounded-map** | not-generated | auditable | Gate E only |
| `falu3_srcmod12.opsel` | geometry-mapped | **live** | **bounded-map** | not-generated | auditable | Gate E only |
| `falu3_srcmod12.ctrl` | geometry-mapped | **live** | **bounded-map** | not-generated | auditable | Gate E only |
| `copysign.operands` | geometry-mapped | **live** | hypothesis | not-generated | auditable | Gate E only |
| `fspecial_est.srcA` | geometry-mapped | live at **1 of 256**; control FAILED, so the remaining 255 are **carrier-undecidable, not inert** | hypothesis | not-generated | auditable | Gate B **and** Gate E |

**Three new hardware facts came out of the adversarial-input arms**, and all three contradict or
sharpen what `db.json` currently says (§4). **Two prior refusals are explained rather than merely
re-measured** (§5).

### Run hygiene

8 runs, 4405 cases each for runs 01–04 and 5634 each for the four amendment runs — **40,156 dispatched cases**.
**0 hangs. 0 watchdog timeouts. 0 malformed responses. 0 `invalid_run`. 0 `InnocentVictim`.
0 Gate-A ledger mismatches in 22,536 amendment cases.** Contained command-buffer faults occurred
only in the pre-registered `(v & 7) == 7` class and in the `ctrl` length-selector region.
The device was never wedged and `macvdmtool` was never used.

---

## 1. Gate A — the caller-to-actual-byte ledger, and what it settles about the aliasing hazard

`falu3_srcmod12.opsel` was dispatched here to a **named prior defect**: its earlier sweep was
*aliased*, because `match`-pinned bits an assembler could not clear made nominal values 4 and 6
assemble to identical bytes, and the oracle therefore described a program that never ran.

This experiment did not use an assembler at all. Values are written by a direct little-endian bit
replace over the instruction's own bytes, and **three independent checks confirm the encodings
really differ**:

1. **Before dispatch.** `analysis/gen_arms.py` computes the mutated bytes for every value of every
   arm on the host and refuses to emit the arm unless the byte strings are pairwise distinct and
   every XOR against the baseline is confined to the field's own `start`/`width` span.
   **69 arms, 5634 cases, 0 aliasing or span violations.**
2. **At dispatch (Gate A).** Every amendment case records the instruction bytes **re-extracted from
   the blob that was about to be dispatched**, the field value decoded back out of those bytes by
   an expression independent of the patch routine, the program `sha256`, the offsets, and the db
   and harness hashes. **22,536 of 22,536 cases carry a ledger; 0 mismatches between the requested
   value and the value decoded from the actual dispatched bytes.**
3. **After the fact.** `tools/agx-isa/wave_audit.py` over this directory reports
   `distinct encodings dispatched` ≥ `legal values` for every field — no `match`-bit collision.

| field | distinct requested values | distinct ACTUAL encodings | ledger mismatches |
|---|---:|---:|---:|
| `falu3.op` | 256 | 256 | 0 |
| `falu3_ext.op` | 256 | 256 | 0 |
| `fspecial_est.srcA` | 256 | 256 | 0 |
| `falu3_srcmod12.opsel` | 8 | 8 | 0 |
| `falu3_srcmod12.ctrl` | 128 | 128 | 0 |
| `copysign.operands` | 256 | 256 | 0 |

**The `opsel` sweep here is not aliased.** But the geometry it reveals is the real content of the
prior defect, and it is a `db.json` model error, not a tooling accident — see §4.1.

---

## 2. `falu3.op` and `falu3_ext.op` — the UNSTABLE debt, and what it actually was

### 2.1 The instability was the fault-class boundary, not the semantics

Both fields were withheld as **UNSTABLE** — 428 and 450 observations moved, one arm each, 87.5 %
cross-run agreement. This experiment ran them on **4 and 5 independent arms respectively** (the
deficiency was one arm each, not too few values) and measured every cross-run disagreement rather
than reporting a percentage:

| pair | `falu3.op` | `falu3_ext.op` |
|---|---|---|
| `run01` / `run02` (original gate, forward order, both busy) | 93.36 % — **17 of 17 disagreements are values with `(v & 7) == 7`** | 93.36 % — same |
| `a_run01` fwd / `a_run02` rev (amendment) | 99.22 % — 2 disagreements, `0x37`, `0x3F` | 99.61 % — 1 disagreement, `0xAF` |
| `a_run03` fwd / `a_run04` rev (amendment) | **100.00 %**, 0 of 256 | **100.00 %**, 0 of 256 |

Every single disagreement in the whole experiment is a **`fault` ⟷ `wrote-nothing` flip on a value
in the pre-registered fault class**. The two runs agree on the substance — the program produced no
result — and differ only in whether the OS flagged the command buffer, which is precisely what a
sibling context's device reset changes. `analysis/verdicts.py` reports this as a clearly-labelled
secondary figure (`agree_pct_adjudicated`, `PRE_REGISTRATION.md` §8 route (b)): **100.00 % for both
fields, 0 residual disagreements**, alongside the primary figure, never instead of it.

**This does not promote either field.** It bounds the debt: the fields are stably live and stably
semantic, and the residual variance sits entirely on 32 encodings that produce no output at all.

### 2.2 The operation map — confirmed in part, refuted in part

`db.json`'s `falu3.op` note publishes an operation map for the low 3 bits (EXP-0160, G17P, on a
synthesized-and-lifted carrier with seeded registers). It was pre-registered here as a
**prediction** on a *compiled* `fma(a,b,c)` carrier, and the host oracle predicted a **different
8-lane vector per class** before any dispatch.

| low 3 bits | `db.json` says | measured on `f3_fma` (compiled 3-source fma, bits 6/7 clear) |
|---|---|---|
| 0 | `a+b` | **REFUTED** — lane-uniform `7.5`, the carrier's unrelated sentinel constant |
| 1 | `a*b` | **REFUTED** — all lanes `+0.0` |
| 2 | `a*b+a` | **REFUTED** — lane-uniform `7.5` |
| 3 | *(unmapped)* | lane-uniform `56.25` (= 7.5²) |
| 4 | `-b` | **CONFIRMED**, bit-exact, including `-(-0.0) = +0.0` and `-inf` |
| 5 | `0` | **SHARPENED — it is `0.0 * b`, not a constant zero.** See §4.2 |
| 6 | `a*b+c` | **CONFIRMED**, bit-exact fused multiply-add |
| 7 | fault | **CONFIRMED** — every value with `(v & 7) == 7` produces no output |

Bits 3, 4 and 5 of the byte are **inert in this envelope** (each of classes 4/5/6 accepts all 8
combinations of them); bits 6 and 7 are corruptors — with either set, the instruction returns
operand `a` or a zero regardless of the class.

The accept rule measured on the **10-byte saturating form** is tighter and exact:
**`(v & 0xC7) == 0x06`** — 8 of 256 values, the same three inert bits, and **only class 6 works**.
`-b` and the multiply-by-zero do *not* reproduce on the extended form, and class 5 there leaves the
output completely unwritten. **The two `op` fields do not share an operation map**, which is itself
a result: `db.json` currently carries one identical note on both descriptors.

*Interpretation, offered as hypothesis not measurement:* classes 0/2/3 returning lane-uniform
constants drawn from an unrelated live register is most economically explained by those classes
re-decoding the operand descriptors to a different source class that a three-source carrier's
descriptors do not name. That would reconcile them with the published two-source map without
either record being wrong. It is not established here.

---

## 3. `copysign.operands` — the Case-C non-result is broken, with a discriminating oracle

The binding constraint on this field was **the oracle, not the range**. A prior M4 sweep dispatched
**256 legal values and 256 distinct encodings**, produced no faults and 100 % cross-run agreement,
and still left the field `untested`, because it produced **one** distinct valid payload against
**one** constant oracle: the values ran legally and were *indistinguishable*.

This experiment therefore spent nothing on more values and everything on the oracle:

* inputs chosen so that `copysign(a,b)`, `copysign(b,a)`, `a`, `b`, `|a|`, `|b|`, `-a`, `-b`,
  `-|a|`, `-|b|`, `0`, `a*b` and `a+b` are **thirteen pairwise-distinct 8-lane vectors**, asserted
  bit-exactly on the host by `analysis/oracle_check.py` before the contract was frozen;
* a **`-0.0` sign source**, and two lanes where `sign(a) == sign(b)` on purpose — with all signs
  opposite, `copysign(a,b)` *equals* `-a` and the library cannot tell a sign copy from a negation.
  `oracle_check.py` caught exactly that collision in the first draft of the adversarial set, before
  any device time;
* a **role-exchanged carrier** (`copysign(b,a)`), which is the dimension `operands` is modelled to
  control, so the two carriers are not one carrier twice;
* an **adversarial input set** carrying `±0.0`, `±inf`, `NaN`, the smallest denormal and `2^24`.

**Result — the field is emphatically live, and it names a function:**

| | value |
|---|---|
| V (distinct valid payloads) | **19** across the directory, **4** on the chosen arm — not 1 |
| distinct oracles | 65 (per-value equivalence class, not a constant) |
| moved | **252 of 256**, in every one of 8 runs |
| cross-run disagreements | **0 of 256**, all four pairs |
| accept set | **exactly `{0x00, 0x01, 0x80, 0x81}` — the rule `(v & 0x7E) == 0x00`** |
| named function at the accept set | `copysign(a,b)` on `cs_load`, **`copysign(b,a)` on `cs_swap`** |

Bits 0 and 7 are inert; bits 1..6 must all be zero. That is the `(reg << 1) | size` operand-byte
shape `db.json` documents for `falu2`, with the inert top bit HW-tested on five other families —
now measured on a sixth. Every other value degrades quietly: 252 of 256 produce a partition of
"even lanes correct, odd lanes zero or unwritten", never a fault.

The role-exchanged carrier is the sharpest part: **`cs_load` and `cs_swap` compile to byte-identical
instructions (`07 c2 88 00` at the same offset) and produce different functions.** So `operands`
selects *an* operand descriptor, but the assignment of magnitude-source vs sign-source role is
**not** carried in it — it comes from the surrounding register allocation, i.e. from bytes
`db.json` currently models as `match` constants. That is recorded as a db defect in §4.3.

**Why the semantics axis still reads `hypothesis` and not `bounded-map`:** the frozen criterion
requires ≥ 3 distinct outcome buckets, and this field produces only two (`correct_effect`,
`different_unclassified`) because it never faults and never silently zeros every lane. The
substantive evidence — a named function, on two role-differing carriers, bit-exact, reproduced in
8 runs — is stronger than that mechanical label. The label is left as the frozen gate computed it
rather than adjusted after the fact.

---

## 4. Three new hardware facts, and the `db.json` defects they imply

Recorded here with evidence; **`tools/agx-isa/db.json` is NOT edited** — the orchestrator owns it.
Machine-readable form: `analysis/field_verdicts.json` → `db_defects`.

### 4.1 DEF-0201-1 — `falu3_srcmod12.opsel` overlaps its own descriptor's `match` bit

`opsel` is modelled as bits 16..18 (width 3), and the same descriptor pins `[17, 1, 1]`.
**Bit 17 is `opsel`'s middle bit.** Only 2 of the field's 3 bits are free within this mnemonic, so
its encodable range is **4 values `{2,3,6,7}`, not 8**.

Measured, with the pinned tokenizer's opinion recorded per case: values `{0,1,4,5}` clear bit 17 and
the bytes re-tokenize as **`falu_srcmod12b`** — a different instruction, the `emit_unsafe` sibling
where `opsel == 4` is documented to corrupt an unrelated register. **Movement on those four values
is excluded from this field's `moved` count and reported separately**; that is the trap that
withdrew two fields elsewhere on 2026-08-30. Within the mnemonic the accept rule is `(v & 7) == 6`
and `moved = 3 of 4` in every run, with 0 cross-run disagreements.

*This is the real content of the earlier aliasing defect.* An assembler that cannot clear a
`match` bit was the symptom; the cause is a descriptor whose field span overlaps its own match
constraint. An emitter reading `db.json` today will believe it may choose 8 values for this field.

### 4.2 DEF-0201-2 — `falu3.op` low-3 class 5 is a MULTIPLY BY ZERO, not a constant zero

`db.json` says `5 = 0`. Measured bit-exactly on two independent input sets
(`analysis/op_semantics.py`, over immutable raw):

| srcB lane | 2.0 | −3.0 | 4.0 | 0.5 | 8.0 | 1.25 | −2.0 | 9.0 |
|---|---|---|---|---|---|---|---|---|
| result (u32) | `00000000` | **`80000000`** | `00000000` | `00000000` | `00000000` | `00000000` | **`80000000`** | `00000000` |

| srcB lane | 3.0 | −0.0 | **inf** | 2.0 | 1.0 | 2.0 | 0.0 | −4.0 |
|---|---|---|---|---|---|---|---|---|
| result (u32) | `00000000` | `80000000` | **`7fc00000`** | `00000000` | `00000000` | `00000000` | `00000000` | `80000000` |

The sign follows srcB, and an **infinite srcB yields NaN** — exactly `0.0 * b`. An implementer told
"this class returns 0" would emit a NaN into any shader that feeds it an infinity, and would lose a
sign in every negative lane. Confirmed on all four amendment runs, forward and reversed order.

### 4.3 DEF-0201-3 — `copysign` operand ROLE is not in `operands`

`db.json` models `copysign` as `07 c2 88 <operands>` with bits 0..23 fixed by `match` and byte+3
carrying "the src/dst register operand descriptor". Two carriers whose only difference is which
argument is the magnitude source compile to **byte-identical instructions** and compute different
functions. So byte+3 is a live operand descriptor with an accept set of 4 (§3), but it does **not**
encode the operand-role assignment; that lives in the surrounding allocation, i.e. behind bytes the
descriptor currently treats as constants. `copysign._instruction` therefore stays
`corpus-correlation`: the 4-byte word can be generated from the descriptor and executes correctly
(`generated-point`), but a **canonical recipe** would have to state how the roles are established,
and this experiment cannot.

### 4.4 Bonus observation — denormal results are flushed to zero

On the adversarial arm, lane 3 computes `1.4e-45 * 2.0 + 0.0`, whose IEEE result is the denormal
`2.8e-45` (`0x00000002`). The hardware returned **`0x00000000`**. Bounded statement: **a denormal
operand and/or a denormal result does not survive the `falu3` fused multiply-add on G17P — the two
are not separated by this arm.** This slipped past the sweep's own tolerance-based comparison and
was found only by the bit-exact offline classifier; it is reported as an observation, not a
promotion.

Also recorded, as a compiler observation about our own source rather than a hardware claim: on
G17P `precise::rsqrt` and `precise::sqrt` both lower to `fspecial_est` subop **`0x0f`**, and
`precise::divide(1,x)` to subop **`0x0d`**, where `db.json`'s enum reads 9 = rcp, 11 = rsqrt,
13 = sqrt, 15 = rsqrt.

---

## 5. `fspecial_est.srcA` — the prior refusal is explained, not merely repeated

The prior record was "256 values over 4 arms, 1 observation moved" — read as near-inert. This
experiment ran **5 arms** (`precise::rsqrt`, `precise::divide`, `precise::sqrt`, and a two-estimate
kernel contributing two occurrences), each with a second live float **orders of magnitude away**
from the estimate's argument so a wrong-register seed could not be rescued by the Newton–Raphson
refinement, and each with a positive control and a pre-registered falsifier at the same occurrence.

**Every one of them is blind.**

| arm | srcA values | moved | control (`subop`, 20 values) | falsifier (`subop = 0`) |
|---|---:|---:|---:|---:|
| `fsp_rsqrt#0` | 256 | 0 | **0 moved** | **did not fire** |
| `fsp_rcp#0` | 256 | 1 (`0x81`) | **0 moved** | **did not fire** |
| `fsp_sqrt#0` | 256 | 0 | **0 moved** | **did not fire** |
| `fsp_two#0` | 256 | 0 | **0 moved** | **did not fire** |
| `fsp_two#1` | 256 | 0 | **0 moved** | **did not fire** |

All 1280 read-backs, on every arm and in every run, are the carrier's exactly correct
`rsqrt`/`rcp`/`sqrt`. Mutating byte+3 to `0x00` — which our own tokenizer then reads as a
completely different instruction — changes the output by **nothing at all**.

**Verdict: `carrier-undecidable`, not inert.** Under Gate B a failed positive control means zero
movement is not evidence of inertness, and the safe wording is
**`inert in this exact tested envelope; global role unknown`**. The refined statement this
experiment can make, which the prior record could not, is *why*: **the `fspecial_est` occurrence's
own result is not observable at the refined output of a `precise::` lowering on these carriers** —
the Newton–Raphson refinement is self-correcting, or the seed's destination is redefined before
use. A future arm must read the seed register directly (redirect the store, as EXP-0026 did) rather
than observe the refined result.

**The one thing that did move is worth keeping.** `srcA = 0x81` — and only `0x81`, in all four
amendment runs and both original runs — makes the *auxiliary* output word read `0.125` in every
lane, i.e. **the register holding the second live float reads as `0.0`**. The estimate's own result
is untouched. The most economical reading is the release-on-read lifecycle `db.json` documents for
`falu2` (a released source register returns zero to a later reader), reached here through a source
descriptor of `(reg 64 << 1) | 1`. It is a reproducible hardware effect of the field on state the
instruction was not supposed to touch, and it is the reason the auxiliary word was instrumented.
One moving value with a dead control promotes nothing.

---

## 6. `falu3_srcmod12.ctrl` — open ground, and the length rule holds

128 values, dense, two carriers, 0 cross-run disagreements in all four pairs, `moved = 31`.

* accept set is **exactly `{0x03}`**, rule `(v & 0x7F) == 0x03` — every one of the 7 bits is
  load-bearing on this carrier;
* the pre-registered length model `length = 6 + 2*(v & 3)` is **not contradicted**: only
  `(v & 3) == 3` preserves the 12-byte framing, and values that re-length the instruction
  re-tokenize everything after it. Movement produced by re-framing is recorded with the mutated
  token and reported as a framing effect, never as operand semantics;
* 64 of 128 values return an all-zero vector, 28 return `a*b` (the third source dropped), one
  returns `a*b-c`, and 24 fault. The faults are confined to a contiguous region and were dispatched
  without a budget, per the protocol rule that a per-field hang budget guarantees a contiguous
  hazard is never mapped.

---

## 7. Quietness, measured

| run | order | samples | samples with **any** foreign GPU process | samples with a foreign **dispatch** runner |
|---|---|---:|---:|---:|
| `run01` | forward | 128 | 6 | **0** |
| `run02` | forward | 65 | 63 | 47 |
| `run03` | forward | 32 | 32 | 32 |
| `run04` | forward | 18 | 18 | 18 |
| `a_run01` | forward | 53 | 53 | 53 |
| `a_run02` | **reverse** | 59 | 59 | 59 |
| `a_run03` | forward | 33 | 33 | 33 |
| `a_run04` | **reverse** | 12 | 12 | 12 |

The foreign processes are named in `raw/*/gpuwatch.jsonl`: `EXP-0200`, `EXP-0202`, `EXP-0204`,
`EXP-0205` and `EXP-0206` running `gfrun4`, `gfrun5`, `agxrun_persist`, `agxrun_persist_as` and
`shdump`. **The machine was busy for the whole dispatch and no quiet window was obtainable.**
`run01` came closest and is the only run with zero foreign dispatch runners; its pair partner was
heavily contended.

Both figures are reported and **the gate uses the strict one**, so the compile-vs-dispatch
distinction can inform a reader but can never loosen a verdict. Consistent with the corrections
document, **no field is promoted on a busy-machine confirmation**, and the cross-run figures above
are labelled `CONTAMINATED` rather than presented as clean.

---

## 8. How this method could have failed to say "no"

Stated because a criterion that cannot return "no" is broken, and thirteen such criteria have
already been paid for in this corpus.

1. **`analysis/verdicts.py` carries a self-test that must pass before any verdict is computed**, and
   it asserts eight ways the gate must refuse: an indistinguishable field (`V ≤ 1`), an aliased
   sweep, a constant oracle, a Gate-A ledger mismatch, a missing ledger, a `match`-bit collision,
   `sem_checked == 0`, and a contaminated confirmation. It also asserts the gate **does not** refuse
   a width-1 field with `moved = 1, disagree = 0` — the arithmetic bug that silently suppressed a
   read-enable field elsewhere. The gate did in fact return NOT PROMOTED for all six fields, twice,
   for reasons it computed rather than reasons I chose.
2. **A fault is not movement.** Hard outcomes are excluded from `moved` by construction, and the
   selftest asserts it. They *are* included in the cross-run comparison as their own class, so a
   fault/clean flip counts as the disagreement it is rather than silently dropping out of the
   common set — a leniency I found and closed **while run01 was still executing and before any
   verdict had been computed** (recorded in `PROGRESS.md`).
3. **Our own disassembler failing is not movement.** The pinned tokenizer's opinion of the mutated
   bytes is recorded per case, and movement on a value whose mnemonic changed is excluded from the
   field's count and reported separately. That is what keeps `opsel`'s four out-of-mnemonic values
   from inflating its result.
4. **A round trip is not consulted anywhere.** It is symmetric and cannot be an emitter gate.
5. **Where the method still could have failed.** (a) The `fspecial_est` arms are blind, and if I had
   scored "0 of 256 moved" as inertness this experiment would have published a confident false
   inert claim on five carriers — the control conjunct is the only thing preventing it, and it is
   the reason that field's verdict is `carrier-undecidable`. (b) The bit-exact comparison in
   `op_semantics.py` found the denormal flush and the signed zero; the sweep's own tolerance-based
   comparison accepted both as correct, so **the frozen oracle was too generous and only the offline
   analysis caught it**. (c) `cs_alu` emitted no `copysign` at all — a carrier that silently
   contributes nothing is reported rather than dropped, but a design where *all* carriers did that
   would look like a clean null result. (d) No arm can distinguish a denormal operand flush from a
   denormal result flush, and the write-up says so instead of choosing one.

---

## 9. What an implementer may take from this today

**Nothing at emitter grade.** Every row is blocked on a clean confirmation run. What is available
as bounded, auditable observation on G17P:

* `falu3.op`: `(v & 7) == 7` produces no output; classes 4/5/6 with bits 6/7 clear compute `-b`,
  `0.0*b` and `a*b+c`; bits 3/4/5 are inert in that envelope. **Do not read class 5 as a constant
  zero.**
* `falu3_ext.op`: the only value class that computes the saturating fma is `(v & 0xC7) == 0x06`.
* `copysign.operands`: `{0x00, 0x01, 0x80, 0x81}` reproduce `copysign`; everything else degrades
  silently, never faults. The operand *roles* are not in this byte.
* `falu3_srcmod12.opsel`: the encodable range within this mnemonic is 4 values, not 8.
* `falu3_srcmod12.ctrl`: only `0x03` preserves the compiled behaviour and the 12-byte framing.
* `fspecial_est.srcA`: **do not treat as inert.** No carrier here can see it.

## 10. Recommended next steps

1. **A quiet confirmation window.** Everything else is in place; two clean runs in reversed order
   would move four fields to the promotion gate. This needs orchestrator scheduling, not more
   experiment design.
2. **An `fspecial_est` arm that reads the seed register directly** (redirect the final store, as
   EXP-0026 did) instead of observing the Newton–Raphson-refined result.
3. **Separate the denormal operand flush from the denormal result flush** with an arm whose only
   denormal is an operand of an operation that cannot produce one.
4. **A `falu3.op` arm that seeds a two-source carrier**, to test the hypothesis in §2.2 that
   classes 0/2/3 re-decode the operand descriptors rather than being wrong in the published map.

---

## 11. Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected:      kernels/k_falu201.metal (authored by us) and its compiled _agc.main bytes
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled, symbol-dumped,
                       strings-scanned, debugged or otherwise introspected. The only machine code
                       inspected is what the public runtime compiler produced from our own MSL.
Reproduction:          README.md "Reproduction"; run ids in raw/
Evidence:              raw/<run_id>/sweep.jsonl and raw/<run_id>/gpuwatch.jsonl (append-only),
                       CAPTURE_CONTRACT.json hashes, manifest.json
```
