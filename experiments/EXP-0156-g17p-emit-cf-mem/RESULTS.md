# RESULTS — EXP-0156 (A18 Pro / G17P): control flow, memory, and the bf16/half cluster

**Target: Apple A18 Pro / G17P** (`Mac17,5`, macOS 26.6, `AGXAcceleratorG17P`,
`applegpu_g17p`, 5 GPU cores, Metal family Apple9). Every number below is a **DIRECT
G17P measurement**. No M4 GPU work was done; no M4 label is carried onto a G17P verdict.

| | |
|---|---|
| Frozen contract | `PRE_REGISTRATION.md` (sha256 `f1e0ec2d…`), `CAPTURE_CONTRACT.json`, frozen 2026-08-30T05:18:58Z at repo revision `7dc67d76` |
| Addenda | `ADDENDUM-PREREG.md` §1 (`tgac141`) and §2 (`jump_cond.*@NAT`), each frozen before its own arm ran |
| Gated captures | 9 run pairs, ~29 000 measured cases |
| Retained partial | `raw/g17p-20260830-cf01a` (transport failure, `PARTIAL.md`), plus nine empty run dirs from batch #1's harness fault |
| Concurrency | five other agents shared the GPU throughout; CF and `tgac` ran under `~/agxre/gpulease.sh`, MEM and bf16 ran free (orchestrator directive 2026-08-29) |

---

## 0. Headline results

### H-1. `tg_addr_compute` — **the corpus's only cross-target contradiction is REAL, and it is the TARGET, not the carrier.**

EXP-M4-14 (A18) recorded byte0 `0x1c` **and `0xfc`** reproducing the tile dataflow.
EXP-0141 H5 (M4) found **only `0x1c`** did. This experiment settles it, and had to remove a
confound to do so.

| carrier | byte0 accepted | `0x1c` | `0xfc` | byte+1 accepted | bytes +2..+5 |
|---|---:|---|---|---:|---|
| **G17P**, EXP-M4-14's own `k_thr.metal` | **104 / 256** | ok | **ok** | **96 / 256** | 256/256 inert each |
| **G17P**, EXP-0141's own tile litmus (addendum) | **102 / 256** | ok | **ok** | **96 / 256** | — |
| M4, EXP-0141's own tile litmus (published) | **1 / 256** | ok | **not reproduced** | 32 / 256 | inert |

**The confound and its removal.** EXP-0141's contradicting M4 measurement was *not* made on
`k_thr.metal`: it used EXP-0141's own lane-0-fills-the-tile litmus with the op at **+422**,
a different program. Reporting a hardware divergence from those two records alone would
have compared two things that differ in **both target and carrier**. So the addendum
(`ADDENDUM-PREREG.md` §1, frozen with **both** outcomes pre-registered) ran **EXP-0141's
own carrier, byte-for-byte, here on the G17P**. A compile-only pilot first confirmed it
reproduces EXP-0141's exact M4 offsets (`tg_addr_compute` at +422, `threadgroup_barrier` at
+428), so it is the same program.

**Result: HA.** On EXP-0141's own carrier the G17P accepts **102 of 256** byte0 values
including `0xfc`, and **the identical 96-value byte+1 set** as `k_thr.metal`. Same carrier,
same offsets, same oracle shape — **the difference is the target.** G17P accepts a large
family of byte0 forms that G16G rejects, and the M4's 32-value byte+1 rule
(`v & 0x03 == 2 and v & 0x10 == 0`) is a **strict subset** of G17P's 96.

**What this rests on, stated plainly.** The G17P half is measured here, twice, on two
carriers. The G16G half is **EXP-0141's published record**, not re-measured — the M4 is
retired for GPU work, so the symmetric experiment (`k_thr.metal` on an M4) was not
available. If EXP-0141's M4 numbers are right, this is the corpus's first confirmed
G16G↔G17P hardware divergence (EXP-0153 checked seven findings and found none). If they
are wrong, what remains is still a complete, gated G17P characterisation of
`tg_addr_compute`'s six bytes, which is the part an implementer needs.

Both G17P arms gated at **100.0 % exact cross-run agreement, 0 hangs, 0 baseline failures**,
with baseline and unreachable-oracle falsifier firing as pre-registered in both. The
addendum carrier additionally carries its own integrity sentinel (`o[256] = 0xA5A5A5A5`),
which `k_thr.metal` cannot.

**The `emit_unsafe` veto STANDS on G17P** and this experiment does not lift it: byte0 and
byte+1 are *live operand selectors* that `db.json` pins in `match` and models as no field
at all, so an emitter still cannot fill them from the tables. What *is* now closed is
`b3`/`b4`/`b5` — **256/256 inert in both carriers and both runs**.

### H-2. bf16 arithmetic MEASURED for the first time — and it rounds to **nearest-even**.

No experiment in this repository had ever measured a bfloat16 numeric result; `P2-01/02`
stand as "hardware YES, emit NO". All four bf16/half carriers reproduced their
**host-computed exact bit-pattern oracles** on every lane, in both gated runs:

| carrier | what was proven | example (lane 0/1 packed word) |
|---|---|---|
| `bf_add` | `out = bf16(a+b)` exactly | `0x40103fc0` = (1.5, 2.25) for a=(1.0,2.0), b=(0.5,0.25) |
| `bf_fma` | `out = bf16(a*b+c)` exactly | `0x3f803f40` |
| `h_max` | `out = fp16(max(a,b))` exactly | `0x40003c00` |
| `h2_fma` | `out = fp16(a*b+c)` **per half** | `0x4c403a00` |

**Rounding mode — decided by a pre-registered two-oracle probe.** Identical program bytes,
an input pair whose exact sum `1 + 3/512 = 1.005859375` falls strictly between two adjacent
bf16 values and nearer the upper one. The hardware returned **`0x3F81` (1.0078125)** on
every lane in both runs: the **round-to-nearest-even** oracle matched and the
**truncate** oracle failed. bf16 on Apple9 is *not* a truncated fp32 store — it rounds.

**The op-select enum is proven BY VALUE, not by inertness.** Splicing byte+2 `0x1c → 0x1d`
turns `a+b` into `a*b`: the mutated program matched the host-computed **MUL** oracle
(`0x3f003f00` = (0.5, 0.5) for a·b) and its paired control **failed** the ADD oracle,
exactly as pre-registered. Same for `hminmax`: byte+4 low bit `0 → 1` turns `max` into
`min`, matching the host **MIN** oracle and failing the MAX oracle.

**New hardware fact: bf16 SUBTRACT is directly emittable.** byte+5 is not opaque tail — it
carries a **source modifier**. Dense sweep, gated, 100.0 % agreement:
`0x00` → `a+b` (8 accepted values, `v & 0x1F == 0x00`); **`0x08` → `a−b` exactly**;
`0x09` → `−b`; `0x01` → `b`. `db.json` models bytes +5..+7 as one opaque 24-bit `tail`; it
is at least (modifier, cache, marker).

Checked against the host oracle in **both** gated runs, all eight lanes, bit-exact:

| byte+5 | observed (both runs) | host prediction |
|---|---|---|
| `0x08` | `[0.5, 1.75, 2.0, 0.0, −1.0, 0.375, 4.0, 4.0]` | `a − b` ✓ |
| `0x09` | `[−0.5, −0.25, −1.0, −4.0, −2.5, −0.125, −2.0, −6.0]` | `−b` ✓ |

An emitter that needs `bf16 a − b` does **not** need a different opcode: set byte+5 bit 3.

### H-3. `h_alu_hi` writes the HIGH half — confirmed with a clean 2 048-case asymmetry.

A `half2` fma compiles to **two** ops: a `0x?0`-group op at +46 and a `0x?8`-group op at
+54. Every case in both dense sweeps was classified `lo_changed` / `hi_changed` / `both` /
`neither` from the observed packed word:

| swept byte | `hi_changed` | `lo_changed` | `both` | `neither` |
|---|---:|---:|---:|---:|
| `0x?8` op byte+1 (srcA) | **250** | **0** | 4 | 2 |
| `0x?8` op byte+2 (opsel/opflags) | **240** | **0** | 0 | 16 |
| `0x?8` op byte+3 (srcB) | **250** | **0** | 4 | 2 |
| `0x?0` op byte+1 | 0 | **246** | 8 | 2 |
| `0x?0` op byte+3 | 0 | **246** | 8 | 2 |
| `0x?0` op byte+5 | 0 | **246** | 8 | 2 |
| `0x?0` op byte+6 | 0 | **252** | 0 | 4 |

**The `0x?8` op never changes the low half alone and the `0x?0` op never changes the high
half alone**, across 2 048 gated cases with cross-run agreement. Halves are independently
addressable, 2 per GPR (EXP-0020), and `byte0` low-nibble **8 selects the high one**.
The `both` cases are the byte0 sweeps (which move the destination register, so both halves
move) and a few operand values.

### H-4. Loops: **NOT yet emittable — but `jump_cond`'s carrier-liveness blocker is GONE and four CF instructions closed.**

EXP-0140 reported that `jump`, `ret`, `pop_reconverge` and `if_push_pred` were "one gated
capture short, not one hardware result short", and that `jump_cond` had failed on **carrier
liveness**. This experiment supplied the missing capture for all of them and built the live
`jump_cond` carrier. **`jump`, `pop_reconverge`, `ret_luse` and `jump_cond` closed.**
`ret` and `if_push_pred` did **not**, because four GPU hangs truncated their second run and
the pre-registered stop rule fired (§7) — they are one short leased re-run away, not one
hardware result away. `mask_op` is swept but unclassifiable (§5.1) and `call` /
`call_indirect` were not attempted (§5.3). `icmp_pred`, the loop guard, was outside this
dispatch and is still `untested`.

*(§2 has the full table and the exact rules.)*

---

## 1. What was directly OBSERVED — control flow

All CF cases splice into EXP-0090/EXP-0112's **HW-validated 152-byte skeleton**, perturbing
exactly one named field of one instruction, so no branch displacement is ever recomputed and
the carrier is never lengthened. The skeleton's own per-lane oracle proves the surrounding
control flow really executed: the results require the loop to run 1, 2, 3, 4, 8, 16 and 32
times on lanes 1..7 and lane 7 to take the if/else TRUE arm.

**The pilot's first finding: the frozen M4 skeleton reproduces byte-for-byte on G17P.**
`carrier_cf.metal` compiles to `_agc.main` of exactly **152 bytes** with the same
`base_slot` assignment (`a=2, n=1, out=0`) and the identical 21-instruction layout
(`CF_STARTS_EXPECT`). EXP-0112's reconstruction is a G17P program as well as an M4 one.

### 1.1 The `jump_cond` liveness unlock — the pre-registered gate FIRED

EXP-0140 found every `jump_cond` field inert *because the branch was never taken*. Binding
`n` to all zeros makes the guard uniformly true and the branch actually taken, changing no
program byte, no length and no displacement. All six pre-registered gate cases behaved
exactly as registered, in both gated runs:

| input | offset | expected | observed |
|---|---|---|---|
| `n = 0` | natural `0x40` | must equal the fall-through oracle | **matched** `[7,17,27,37,47,57,67,77]` |
| `n = 0` | poison `0x5C` / `0x52` | must **differ** | **differed** — the output store never ran; all eight words still `0xDEADBEEF+i` |
| `n` mixed | poison `0x5C` / `0x52` | must **reproduce** (branch not taken) | **reproduced** |

**That is the loop unlock**: the same bytes behave differently only because the branch is
now decided, which is precisely the carrier-liveness property EXP-0140 reported missing.

### 1.2 Branch reach on `jump_cond` — a CHECKERBOARD, measured for the first time

EXP-0115's reach was measured on `jump`. On `jump_cond`, over the dense forward window
58..110 plus far probes {128, 192, 256}:

* **2 of 56 displacements** land and reproduce the fall-through oracle (58 and the natural 64);
* **27 fault** reproducibly;
* **27 leave the output store unexecuted** (`no_store`, see §4).

Sparse and irregular — the same checkerboard shape EXP-0115 found on `jump` (13 of 162),
now confirmed for the conditional form. **An emitter may not assume a displacement is
reachable because a nearby one is.**

### 1.3 The per-field CF table

**Bold rows gated** (both runs dispatched the same case set and produced the identical
accepted-value set). The two rows marked NOT GATED lost their second run to the hang
budget (§7) and are reported `untested`; their single-run numbers are published as such.

| field | swept | accepted | exact rule | verdict |
|---|---|---|---|---|
| **`jump.branch_ctrl`** | 254 of 256 (0,1 excluded as known hangs) | **254** | — | **INERT across the whole dispatched byte** |
| **`pop_reconverge.reserved`** (16 bit) | 35-value protocol sample, at **both** skeleton sites | **35 / 35** at each | — | **INERT** |
| **`ret.linkmode`** | 0..255 dense | **32** | **`v & 0x07 == 0x04`** | 224 values **fault** |
| **`ret_luse.linkmode`** | 0..255 dense | **32** | **`v & 0x07 == 0x04`** | identical set to `ret.linkmode` — H4 confirmed |
| `ret.scoreboard` | 254 of 256 (8,12 excluded) | 12 | `{33,34,35,97,98,99,161,162,163,225,226,227}` | **NOT GATED — one run only (§7).** Not a single mask; bits 7:6 free, bit 5 set, bits 4:2 clear, bits 1:0 ≠ 0 |
| **`ret_luse.tail`** | 254 of 256 | **12** | same 12-value set | `ret_luse` is a drop-in variant of `ret` |
| `if_push_pred.level` | 252 of 256 | 16 | `(v & 0x3C) == 0x00` | **NOT GATED — one run only (§7).** See §3 on the M4 comparison |
| **`jump_cond.offset`** | 56 (dense 58..110 + far) | **2** | — | checkerboard, §1.2 |
| **`jump_cond.cf_scope`** | 0..255 dense at **three** targets (P1, P2, natural) | **256/256 at the natural offset** | — | INERT: at the natural offset every value reproduces the exact fall-through oracle; at both poison targets every value still takes the branch |
| **`jump_cond.reserved`** | 0..255 dense at three targets | **256/256 at the natural offset** | — | INERT, same as `cf_scope` |

`ret.linkmode`'s rule is **exactly EXP-0140's M4 rule**, now measured independently on
G17P — the first cross-target confirmation of that rule.

The `ret_luse` byte+2 `0x54 → 0x56` drop-in control was pre-registered `expect_match=True`
and matched in both runs, so `ret_luse` really is `ret` with one byte changed, at the same
address and the same length.

---

## 2. Loops: what closed, what did not, and exactly what still blocks them

A loop needs `if_push_pred`, `jump_cond`, `if_push`, `ret`, `jump` and `pop_reconverge`
emittable simultaneously — plus, in the skeleton that actually implements one, `icmp_pred`
(the guard comparison), `iadd2`, `get_sr`, `device_load`, `device_store` and `stop`.

| instruction | before EXP-0156 | after |
|---|---|---|
| `jump` | blocked on `branch_ctrl` (`corpus-correlation`) | **closed** — inert over 254/256 |
| `pop_reconverge` | blocked on `reserved` (`tokenization-only`) | **closed** — inert at both sites |
| `ret` | blocked on `linkmode` + `scoreboard` | **`linkmode` closed** (`v & 7 == 4`), `scoreboard` NOT gated — the hang budget truncated its second run (§7). **`ret` does not close.** |
| `ret_luse` | blocked on `linkmode` + `tail` | **closed** — both gated; same accepted sets as `ret.linkmode` / `ret.scoreboard` |
| `if_push_pred` | blocked on `level` (`tokenization-only`) | **NOT closed** — one complete run gives `(v & 0x3C) == 0x00` (16 values); the paired run was truncated by two hangs (§7) |
| `jump_cond` | blocked on `cf_scope`, `offset`, `reserved` | **closed**, with the offset's reach explicitly a checkerboard |
| `if_push` | already emittable (EXP-0140) | unchanged |
| `mask_op` | blocked on `mask_bank`, `scope_kind` | **still blocked** — §5 |
| `call`, `call_indirect` | blocked, 4 fields each | **not attempted** — §5 |

**Answer to the dispatch question: NO, loops are not emittable yet.** Four of the nine
dispatched CF instructions closed (`jump`, `pop_reconverge`, `ret_luse`, `jump_cond`), and
the structural blocker EXP-0140 identified — that no carrier made `jump_cond` live — is
**gone**: the branch is now decided, observable, and its whole field set is swept. Three
things still stand between here and a generated loop:

1. **`ret.scoreboard` and `if_push_pred.level`** — one complete run each, second run
   truncated by the GPU-hang budget (§7). Both need one short leased re-run with the newly
   found hang values excluded. This is the cheapest remaining item by far.
2. **`mask_op`** — swept, unclassifiable, see §5.1.
3. **`icmp_pred`** — the loop-guard comparison.

`tools/agx-isa/validation.json` still records **`icmp_pred.srcA` and `.srcB` as `untested`
and `.opclass` as `corpus-correlation`** — the loop-guard comparison is a piece of a real
loop that no experiment has made emitter-grade, and it was not in this dispatch's scope.
Everything else the frozen skeleton uses — `get_sr`, `iadd2`, `device_load`,
`device_store`, `if_push`, `stop` — is already emittable.

**So the honest statement is:** after EXP-0156 an implementer can synthesise `jump`,
`pop_reconverge`, `ret_luse` and **`jump_cond` — including its displacement, whose reach is
now measured and is a checkerboard** — with arbitrary operands inside the stated ranges.
Three named, individually cheap items remain: a leased re-run of `ret.scoreboard` +
`if_push_pred.level`, a usable `mask_op` carrier, and `icmp_pred`'s operands.

---

## 3. Cross-target comparisons (G17P measured here vs the published M4 numbers)

Stated as comparisons, never as promotions. Where the carrier differs, that is said.

| claim | M4 (published) | G17P (here) | reading |
|---|---|---|---|
| `ret.linkmode` accepted set | `(v & 7) == 4`, 32/256 (EXP-0140) | **identical**, 32/256 | **reproduces** |
| `jump.branch_ctrl` | inert across the byte (EXP-0140 run02) | **inert**, 254/254 dispatched | **reproduces**; and this is the *second gated capture* EXP-0140 said it was missing |
| `pop_reconverge.reserved` | inert, 34 samples (EXP-0140 run02) | **inert**, 35 samples at **two** sites | **reproduces** |
| `if_push_pred.level` | `(v & 0xFC) == 0x00`, 4 values — **but over a PARTIAL 64/256 sweep, stopped by a 2-hang budget** | `(v & 0x3C) == 0x00`, **16 values over the full 252 dispatched** | **not a contradiction**: the M4 rule was fitted to a truncated sweep and the G17P set is its superset. The G17P rule is the one an emitter should use, and only on G17P |
| `atomic_tg` byte+11 accepted | 24 values (EXP-0141) | **24 values**, identical set | **reproduces** |
| `atomic_tg` byte+10 accepted | "only 0" (EXP-0141) | **{0, 128}** — bit 7 is a don't-care | minor widening |
| `atomic_mem` byte+12 accepted | 56 (EXP-0141) | **56** on the immediate carrier, **48** on the register carrier | reproduces per carrier |
| `atomic_rmw` byte+12 accepted | 48 (EXP-0141) | **48** | **reproduces** |
| `atomic_tg` byte+11 `0x04 → 0x05` = smax | **changes the result** (EXP-0141's own falsifier) | **INERT — the falsifier did NOT fire** | see below |
| `tg_addr_compute` byte0 / byte+1 | 1 / 32 accepted | **102–104 / 96** accepted | **genuine target divergence** (H-1) |

**The one falsifier that did not fire.** EXP-0141's `attg.opctl` control — `atomic_tg`
byte+11 `0x04 → 0x05`, published there as turning `add` into `smax` — **reproduced the sum
oracle exactly on G17P**, in the smoke run and in both gated runs. `sum(a[0..15]) = 120112`
and `max = 15007`, so this is not a coincidence of values. Either the op enum differs
between targets at that code point, or EXP-0141's reading of byte+11 as the op selector is
partly wrong. **This experiment does not resolve it and does not promote any semantic claim
about `atomic_tg`'s op enum.** The `atomic_tg` byte sweeps' *accepted sets* are reported
(they gate cleanly and agree with EXP-0141 for byte+11), but the op *meaning* is left open
and flagged.

---

## 4. `no_store` — a real outcome class, separated from contamination

On the CF and `tgac` carriers there is no room for an integrity sentinel (the skeleton fills
its 152 bytes exactly and lengthening it is *not* semantically neutral — EXP-0140 §9; and
`k_thr.metal` is reused byte-for-byte on purpose). There "no output word was written" is
ambiguous between contamination and a field value that suppresses the store.

EXP-0140 §8's rule is reused verbatim and applied **in analysis only** — `raw/` is never
edited: a case that is `invalid_run` in **both** gated runs with **every trial reporting
`STATUS OK`** cannot be contamination, because contamination does not reproduce that way.
Those are re-labelled `wrong_value` with a `no_store` note; cases that do not reproduce stay
`invalid_run` and are **excluded from every claim**.

| pair | reclassified `no_store` |
|---|---:|
| `cf01b` / `cf02e` (jump_cond) | **1 038** |
| `bf03` / `bf04` | 1 120 |
| `t141a` / `t141b` | 2 |
| every other pair | 0 |

On the `jump_cond` arms `no_store` is not noise — **it is the measurement**: at a poison
offset, "the store never ran" *is* "the branch was taken", and that is what makes the
carrier live.

---

## 5. NEGATIVE and INSUFFICIENT results (first-class; nothing rounded up)

### 5.1 `mask_op` — swept, and deliberately NOT promoted

The pre-registered liveness gate was: the compiler-natural `mask_op` (`0f 04 04 19`)
spliced over the skeleton's `if_push` (`0f 05 54 1a`, same 4-byte length, same address, no
displacement change) **must change the output**. It did — and more than expected: it
**HUNG the GPU** in the smoke run (reproduced, majority-of-3) and **faulted** reproducibly
in the gated run. So the site is demonstrably live.

But every swept value of `mask_bank` and `scope_kind` then either faults or leaves the
output store unexecuted, which leaves **no classification to make**. Per
`PRE_REGISTRATION.md` §11 both fields are reported **`untested`**, not rounded up to
"inert". `mask_op` stays blocked.

### 5.2 The fences — the line held, deliberately

`dev_scoreboard_fence.scope_flag`, `mem_fence.{sub, memclass, b5}` and
`mem_fence8.{mask, tail}` were **not swept**, and this was pre-registered rather than
discovered. `FIELD-SWEEP-PROTOCOL` §3.2 requires the field to be live on the observed output
path; EXP-0141 swept the first four densely and refused promotion because **neither carrier
has a memory-ORDERING observable**, EXP-0147 reached the same `INSUFFICIENT` verdict on six
fence fields, and EXP-0152 pre-registered the same refusal. A carrier that cannot detect the
fence's *removal* cannot test the fence's *scope bits*, and a pass would be a false
`hardware-run`. `mem_fence8` has no dispatchable carrier at all (emitted only by
`intersection_query` traversal; `agxrun_persist` cannot bind an acceleration structure).

**So `dev_scoreboard_fence` — one of the four the dispatch called "one field from
emittable" — is still one field short, and this experiment says so rather than closing it
on general sensitivity.** Closing it needs a carrier with a detectable ordering observable,
built and *proven to detect a spliced-out fence* before any scope bit is swept. That is a
successor's job and it is a real piece of work, not a sweep.

### 5.3 `call` and `call_indirect` — not attempted

Neither appears in the frozen 152-byte skeleton, and the only same-length splice sites
available (`device_load`/`device_store` for the 14-byte `call`, `pop_reconverge` for the
6-byte `call_indirect`) would transfer control to an address computed from uninitialised
state — the exact construction that hung the GPU in EXP-0128. Reported `untested`.
Authoring a call carrier is a successor's job.

### 5.4 Instructions that did NOT become emittable despite good field coverage

| instruction | why not |
|---|---|
| `h_alu_hi` | 4 of its fields reached `hardware-run`, but the **observed high-half op is 4 bytes in this form** (`28 01 1b 09`), so `db.json`'s modelled `ctrl`/`mods` (byte+4/+5 of a 6-byte descriptor) are not part of it and were not swept. See `db_defects`. |
| `bf_fma_dst` | `dst`/`fmt`/`srcA`/`srcB`/`srcC` closed, but its `tail` is byte+6..+9 and only bytes 0..5 were dispatched. |
| `bf_mul_dst` | the op-select is proven **by value**, but the operand fields were swept in the `0x1c` (add) form, not the `0x1d` (mul) form. |
| `tg_addr_compute` | all three modelled fields are now `hardware-run` inert, but byte0 and byte+1 are **live and unmodelled**, so the instruction-level `emit_unsafe` veto stands. |

---

## 6. bf16 / half — the per-field table (all gated, both runs' accepted sets identical)

Every rule below is a machine-derived exact `(mask, pattern)` where one exists; where none
exists the accepted set is printed verbatim rather than described by a rule that does not
hold.

### 6.1 `bf_add_dst` (`21 00 1c 00 11 00 c0 81` at +32 of `bf_add.metal`)

| byte | field | accepted | rule | what the wrong values do |
|---|---|---:|---|---|
| 0 | `dst` (high nibble) | **1** | `v == 0x21` | 22 fault, 103 silent-zero, 130 wrong value |
| +1 | `fmt` | **2** | `v & 0x7F == 0x00` | `≥ 0x04` ⇒ output becomes exactly **`b`** (one addend vanishes); `0x02/0x03` garbage |
| +2 | op-select | **8** | `v & 0xC7 == 0x04` | `0x1d` = **mul, proven by value**; `0x1e` (the 10-byte fma form) breaks, as pre-registered |
| +3 | `srcA` | **2** | `v & 0x7F == 0x00` | `≥ 0x02` ⇒ output becomes exactly **`a`** — a live operand selector reading 0 |
| +4 | `srcB` | **2** | `{0x09, 0x11}` | `0x81/0x89` ⇒ output **`a`**; most values ⇒ 0 |
| +5 | modifier | **8** | `v & 0x1F == 0x00` | **`0x08` ⇒ `a−b`**, `0x09` ⇒ `−b`, `0x01` ⇒ `b` |
| +6 | tail | **32** | `v & 0xC2 == 0xC0` | |
| +7 | tail | **32** | `v & 0x83 == 0x81` | |

### 6.2 `hminmax` (`22 00 1c 00 10 c0` at +32 of `h_max.metal`)

| byte | field | accepted | rule | semantics proven by value |
|---|---|---:|---|---|
| 0 | `dst` | 1 | `v == 0x22` | 18 fault |
| +1 | `dst_full` | 2 | `v & 0x7F == 0x00` | `≥ 0x04` ⇒ output = `b` |
| +3 | `srcA` | 2 | `v & 0x7F == 0x00` | `≥ 0x02` ⇒ output = `a` |
| +4 | `sel`/`selhi` | 8 | `{0x08,0x0A,…,0x16}` (even) | **even ⇒ `max(a,b)`, the odd neighbour ⇒ `min(a,b)`**, both matched against exact host oracles; `0x00..0x07` ⇒ `a`; `0x18..0x1F` ⇒ `b`; `≥ 0x20` ⇒ 0 |
| +5 | `srcB` | 1 | `v == 0xC0` | `0xC1` ⇒ `b`; `0xC2+` ⇒ `a` |

`hminmax` therefore has **every modelled field at `hardware-run` and becomes emittable on
G17P evidence alone**.

### 6.3 `bf_fma_dst` and the two half2 ops

`bf_fma_dst`: `dst` 1 (`0x21`, 44 fault), `fmt` 2 (`v & 0x7F == 0x00`), `srcA` 2
(`v & 0x7F == 0x00`), `srcB` 4 (`v & 0x77 == 0x06`), `srcC` 2 (`v & 0x7F == 0x04`).
`half_alu` (low half): byte0 2 (`v & 0xFE == 0x20`), byte+1 2, byte+2 8 (`v & 0xC7 == 0x06`),
byte+3 2, byte+4 8 (`v & 0x73 == 0x01`), byte+5 2, byte+6 4, byte+7 1 (`v == 0xC0`).
`h_alu_hi` (high half): byte0 1 (`v == 0x28`, 60 fault), byte+1 2 (`v & 0x7F == 0x01`),
byte+2 **16** (`v & 0xC3 == 0x03`), byte+3 2 (`v & 0x7F == 0x09`).

---

## 7. Safety: five GPU hangs, the stop rule firing, and two new DO-NOT-EMIT holes

**Total hangs in this experiment: 5.** One in the smoke run (`mask_op` spliced over
`if_push`, reproduced majority-of-3) and four in the CF chunk-C run `cf02f`:

| arm | value | trial statuses |
|---|---|---|
| `if_push_pred.level` | **170** | `CMDBUF_ERROR, HANG, HANG` |
| `if_push_pred.level` | **171** | `HANG, HANG, HANG` |
| `ret.scoreboard` | **0** | `HANG, HANG, HANG` |
| `ret.scoreboard` | **4** | `HANG, HANG, HANG` |

The pre-registered budget then fired exactly as written: 2 hangs stopped
`if_push_pred.level` (82 cases `skipped`), 2 more stopped `ret.scoreboard` (249 `skipped`),
and the CF-wide 4-hang budget stopped `mask_op` entirely (513 `skipped`). Every skipped case
is recorded with its reason; none was silently dropped. **The host never wedged and every
periodic baseline re-validation passed in every run (0 cascades across all 9 pairs).**

**These four values are nondeterministically hang-prone, which is itself the finding.**
The paired run `cf01c` executed all four **under the same GPU lease with zero hangs**, and
`if_push_pred.level` 170/171 both returned ordinary results there. So this is not a
deterministic per-value property — it is a hang that reproduces within a run
(3 trials) but not across runs. That is exactly the class `FIELD-SWEEP-PROTOCOL` §7A warns
about, and the honest conclusion is a **do-not-emit hole plus a downgrade, not a rule**:

> **DO NOT EMIT (G17P):** `if_push_pred.level` ∈ {170, 171}; `ret.scoreboard` ∈ {0, 4}
> (in addition to the inherited M4 exclusions `jump.branch_ctrl` {0,1},
> `if_push_pred.level` {62,63,180,181}, `ret.scoreboard` {8,12},
> `ret_luse.tail` {8,12}, `atomic_tg` byte+5 {0x7E,0x7F}, all of which were dispatched as
> `skipped` records here rather than tested).

**CF work was then STOPPED**, per the dispatch's explicit instruction ("EXP-0128
safety-stopped its CF arm after two hangs; stop after two") and `PRE_REGISTRATION.md` §9.
A partial sweep honestly bounded is worth more than a wedged host.

**Precisely what "stopped" means here**, since one CF arm did complete afterwards — an
earlier draft of this section overstated it as "no further hang-prone control-flow arm was
launched", which was wrong. The stop applies to **the three arms the hangs came from**:
`if_push_pred.level`, `ret.scoreboard` and `mask_op`. **None of those three was
re-dispatched.** The `jump_cond.*@NAT` arm was **launched at 06:28:18Z, before `cf02f`'s
hangs**, and its second half (`jcn1`) had to be relaunched only because `gpulease.sh`
**timed out waiting for the GPU lease** — exit **75**, `run.py` never started, **no run
directory created and the id never consumed**. That is a scheduling failure, not a hang.
`jump_cond` arms have a **zero-hang record across four complete runs** (`cf01b`, `cf02e`,
`jcn1`, `jcn2`) and take 3-6 seconds each. Finishing an already-dispatched arm with that
record is not the same as opening new hang-prone work, and the distinction is recorded here
rather than left to the reader.

### Consequence for the verdicts

`if_push_pred.level` and `ret.scoreboard` therefore have **one complete run and one
truncated run**, so they do **not** clear the cross-run gate and are reported **`untested`**
rather than rounded up. Their single-run observations are published, clearly labelled as
single-run:

* `if_push_pred.level` (run `cf01c`, complete, 0 hangs, 252 dispatched):
  **16 accepted, `(v & 0x3C) == 0x00`** — `{0,1,2,3,64,65,66,67,128,129,130,131,192,193,194,195}`.
* `ret.scoreboard` (run `cf01c`, complete, 254 dispatched): **12 accepted**,
  `{33,34,35,97,98,99,161,162,163,225,226,227}` — the identical set to `ret_luse.tail`,
  which **did** gate cleanly in chunk A.

**So `ret` does NOT close** (its `linkmode` gated, its `scoreboard` did not) while
**`ret_luse` DOES** (both its fields gated in chunk A). The successor is one short leased
run of `ret.scoreboard` alone, with 0 and 4 added to the exclusion list.

---

## 8. Robustness — what evidence this actually is

**Concurrency (`FIELD-SWEEP-PROTOCOL` §7.4).** Five other agents shared the neo throughout.
Per the orchestrator's 2026-08-29 directive the CF and `tgac` groups ran **inside
`~/agxre/gpulease.sh`** and the MEM and bf16 groups ran **free and concurrent**. Which runs
held the lease is recorded per run in `00_inputs.json` and in `CAPTURE_CONTRACT.json`.

**Defences, all pre-registered and all active:**

1. **Majority-of-3**: every case ran 2 trials and 3 whenever the first was not `ok` or the
   first two disagreed; a `fault`/`hang` label required the majority. The OS
   fault-classification string is recorded verbatim on every failing trial.
2. **`...ErrorInnocentVictim` segregation**: those failures are environmental, retried up to
   4 times, and never recorded as a property of an encoding.
3. **Periodic baseline re-validation** every 250 cases: **0 failures across all runs**,
   so no capture is a cascade.
4. **Integrity sentinel** on every carrier that can hold one (`atdev`, `atdevimm`, `attg`,
   `bfadd`, `bfround`, `bffma`, `hmax`, `h2fma`, and the addendum `tgac141`). The CF and
   `k_thr.metal` carriers cannot; there the **poisoned read-back** (`0xDEADBEEF + i`) is the
   integrity check, which is declared in the pre-registration rather than discovered later.
   Following EXP-0138's self-inflicted trap (reading `r11` as a source zeroes it), no
   sentinel lives in a register any descriptor under test can name.
5. **Unique splice-archive path per request**, unlinked afterwards.
6. **Cross-run gate on ACCEPTANCE**, with exact-outcome agreement published separately
   (EXP-0141 §4.6's distinction). Both numbers are in
   `analysis/field_verdicts.json` for every field.

**Cross-run agreement, per pair:** every promoted arm has an **identical accepted-value
set** across its two runs. Exact-outcome agreement is 100.0 % for most arms and drops only
where the `no_store` / `wrong_value` boundary is noisy (`ret_luse.tail` 58.2 %,
`bffma.srcB` 87.5 %) — in every such case the two runs still agree case-for-case on
acceptance, which is what the label asserts.

**Deviations from the frozen contract (all disclosed, none repaired in place):**

* **D1 — `raw/g17p-20260830-cf01a` is a retained PARTIAL.** Launched from an interactive
  `ssh` whose local wrapper timed out; the remote `run.py` survived the disconnect, kept
  capturing to record 887, then blocked writing progress to the dead pipe. Killed
  deliberately; retained with `PARTIAL.md`; **id never reused**; successor `cf01d`.
  Every later capture ran under `nohup` with output redirected on the neo.
* **D2 — nine empty run directories** (`cf02a/b/c`, `mem01/02`, `mtg01/02`, `bf01/02`).
  Batch #1's remaining steps aborted in `baseline.py` because the addendum carrier was
  pushed to the neo with `main_len: None` **while the batch was still running**. Those ids
  are retained empty and never reused; batch #2 used new ids. Lesson recorded: never push a
  partially-edited harness while a capture batch is live.
* **D3 — `harness/run.py` changed after the freeze**, to add `--cases` / `--replicates` for
  the `FIELD-SWEEP-PROTOCOL` §7A fault re-validation that landed mid-experiment, and
  `--exclude` / a lease-wait argument. The change is **additive and inert at default
  settings** (still 3 trials, same early-exit logic). The freeze-critical files —
  `cases.py`, `carriers.py`, `isa_helpers.py`, `baseline.py`, `build.sh`, `pilot_locate.py`
  — are byte-identical to their frozen hashes for the CF/MEM/tgac case matrix; `cases.py`
  and `carriers.py` grew only by **appending** the two addendum arms after every existing
  arm, which is why **no frozen case index moved** (verified: `tgac.baseline` is still case
  4755 before and after).
* **D4 — `tools/agxtest/persistrun.py` was re-copied to the neo** mid-experiment after the
  orchestrator fixed its infinite `readline()` spin (`fb057160…` → `cc53d8ef…`).
* **D5 — the GPU lease is broken automatically after 15 minutes**, so the leased captures
  were **chunked** into sub-15-minute runs rather than run as the two whole-group runs the
  contract named. Each chunk is gated against its own pair; the arm order within the group
  is preserved.

---

## 9. Alternative explanations NOT excluded

1. **One carrier shape per instruction.** The CF results are for EXP-0090/EXP-0112's single
   skeleton; the bf16 results are for scalar `bfloat` add/fma and `half`/`half2` in one
   dispatch shape (grid 8 / tg 8). A field inert here may be live in another shape.
2. **"Inert" always means "inert on this observable."** This was the weakest of the
   promotions and `ADDENDUM-PREREG.md` §2 was written to fix it — **and it did**:
   `jump_cond.cf_scope` and `.reserved` are now dense-inert at the **natural** offset,
   where the branch is taken *and lands correctly*, so all 512 cases reproduce the exact
   host-computed fall-through oracle. Inertness there means the program still computes its
   right answer, which is the same standard EXP-0140 used for `jump.branch_ctrl`. What
   remains unexcluded is narrower: a scope effect invisible in an 8-lane,
   single-threadgroup dispatch — one that only matters across threadgroups or under
   contention, say — would still not show up.
3. **The bf16 operand map is only half decoded.** byte+3 and byte+4 are *proven* live
   operand selectors — out-of-range values make exactly one addend vanish, which is
   directly visible because the output becomes exactly `a` (or exactly `b`) rather than
   garbage. But the **value → register map is not established**: the compiler's own
   `srcA = 0x00`, `srcB = 0x11` do not fit the `(reg << 1) | size` convention the rest of
   the ISA uses, and only two values of each byte work in this carrier. The accepted sets
   and the produced values are `hardware-run`; the *mapping* is explicitly not claimed.
4. **`atomic_tg`'s op enum is open**, because EXP-0141's own `0x04 → 0x05` = smax control
   did not fire here (§3). The byte sweeps' accepted sets gate cleanly and are reported;
   no op *meaning* is promoted.
5. **The `tg_addr_compute` divergence is a difference in the ACCEPTED SET, not a decoded
   semantics.** We know G17P accepts 102–104 byte0 values where G16G accepts 1, on the same
   program. We do **not** know what the extra forms *mean*, and both carriers observe only
   "the tile dataflow is still correct". A form that computed the same address by a
   different route would look identical here.
6. **Single target for the new results.** Everything here is G17P. Where an instruction
   becomes emittable by combining this experiment's G17P verdicts with `validation.json`'s
   existing M4 labels, that is **mixed-target emittability** and
   `analysis/emittability.json` says so per instruction under `target_mixing`.
7. **The `no_store` rule assumes contamination does not reproduce identically in two
   independent runs with every trial reporting `STATUS OK`.** That is EXP-0140's reasoning
   and it is inherited, not re-derived here.

---

## 10. The honest field ledger

`analysis/field_verdicts.json` carries the per-field verdicts in `FIELD-SWEEP-PROTOCOL` §5
shape, plus a `db_defects` block (5 entries) and an `insufficient` block (12 entries) naming
every field this experiment deliberately did not close and why.
`analysis/emittability.json` recomputes instruction-level emittability from
`tools/agx-isa/validation.json` (read-only) plus these verdicts.

**The DELTA is the stable number; the absolute totals drift.** The orchestrator edits
`db.json` and `validation.json` continuously while eleven experiments run — during this
experiment alone the instruction total moved 171 → 172 and the field total 1057 → 1060 — and
by the time the analysis was last re-run the orchestrator had **already merged these
verdicts into `validation.json`** (commit `39520163`), which made a naive before/after
delta collapse to zero. `analysis/emittability.py` therefore computes its baseline by
**subtracting every `EXP-0156`-attributed label** from `validation.json` rather than
trusting a snapshot, so the delta is reproducible whenever it is re-run.

| | delta | absolute, at the pinned snapshot |
|---|---:|---|
| instructions emittable | **+9** | 52 → **61** of 172 |
| fields at emitter grade | **+44** | 525 → **569** of 1060 |

Snapshot pinned in `analysis/emittability.json`:
`db.json` sha256 `83b83a350ece33b8…`, `validation.json` sha256 `631af9202ddd5457…`.

**Newly emittable (9):** `jump`, `jump_cond`, `pop_reconverge`, `ret_luse`, `atomic_mem`,
`atomic_rmw`, `atomic_tg`, `bf_add_dst`, `hminmax`.

**Newly emittable on G17P evidence ALONE (4):** `bf_add_dst`, `hminmax`, `jump_cond`,
`ret_luse` — every one of their fields was measured here. The other five close only by
combining this experiment's G17P verdicts with `validation.json`'s existing M4 labels for
the fields not swept here; `emittability.json`'s `target_mixing` block lists exactly which
fields those are, per instruction.

Per-field labels produced: **48 `hardware-run`, 4 `untested`** (`if_push_pred.level`,
`ret.scoreboard`, `mask_op.mask_bank`, `mask_op.scope_kind`) — nothing rounded up.

**`db.json` and `validation.json` were NOT edited.** The verdicts are offered to the
orchestrator; the five `db_defects` are recorded, not applied.

---

## 11. Reproduction

```sh
# on the neo (A18 Pro), under ~/agxre/experiments/EXP-0156-g17p-emit-cf-mem
sh harness/build.sh work/bin
python3 harness/pilot_locate.py work/bin work/pilot_loc      # compile-only, no GPU
python3 harness/baseline.py work/bin work/baseline_bin       # compile-only, no GPU
python3 harness/cases.py                                     # frozen case matrix, no GPU
bash harness/batch2.sh                                       # the gated captures
python3 harness/revalidate.py list RUN_A RUN_B > work/r.idx  # §7A fault re-validation list
bash harness/drive.sh lease <new_id> "" 3600 --cases work/r.idx --replicates 5

# on the repo host (analysis only, no GPU)
python3 analysis/verdicts.py          # cross-run gate over the frozen run pairs
python3 analysis/field_verdicts.py    # FIELD-SWEEP-PROTOCOL §5 verdicts + db_defects
python3 analysis/emittability.py      # instruction-level emittability delta
python3 analysis/make_manifest.py     # artifact hashes
```

## 12. Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: our own MSL (kernels/*.metal — authored by this project or reused
                  byte-for-byte from EXP-0090/0112/0141/0145/M4-14) and the machine code
                  compiled from it; instruction bytes assembled by our own tools/agx-isa
                  (read-only use)
Apple binary introspection: NONE
Reproduction: §11
Evidence: raw/g17p-20260830-*/sweep.jsonl (append-only), each run's 00_inputs.json and
          01_summary.json, raw/smoke-s01/ (retained, cited by no verdict),
          raw/g17p-20260830-cf01a/ (retained PARTIAL), analysis/gate_report.json,
          analysis/field_verdicts.json, analysis/emittability.json, manifest.json,
          CAPTURE_CONTRACT.json, PRE_REGISTRATION.md, ADDENDUM-PREREG.md
```

No Apple binary was disassembled, decompiled, symbol-dumped, strings-scanned or debugged.
The only machine code inspected or spliced is the compiled form of MSL we wrote.
`tools/agx-isa/db.json`, `tools/agx-isa/validation.json`, `docs/` and `PROVENANCE.md` were
**not** edited, and nothing was committed.

---

## 13. The two confirmation runs — both PASSED

### 13.1 `revbf1` / `revbf2` — every bf16/half fault is REAL (complete)

`FIELD-SWEEP-PROTOCOL` §7A (added mid-experiment, after EXP-0153 found that majority-of-3
plus cross-run agreement can still be defeated by sustained sibling load) requires every
`fault`/`hang` verdict to be **confirmed inside the GPU lease** before promotion. The
bf16/half captures ran **free and unleased**, so all **154** cases that *both* gated runs
recorded as `fault` were re-dispatched under `~/agxre/gpulease.sh`, **5 replicates each,
twice** (`raw/g17p-20260830-revbf1`, `revbf2`; forced `--replicates 5`, 0 hangs, 0 aborts).

| outcome pair across the two isolated runs | cases |
|---|---:|
| `fault` / `fault` (5 of 5 trials each) | **150** |
| `fault` / `invalid_run` | 3 |
| `invalid_run` / `fault` | 1 |
| **became `ok`** | **0** |

**Zero of the 154 flipped to `ok`.** The four non-`fault`/`fault` cases are all
`h2.h_alu_hi.b0` (`0x67`, `0xD7`, `0xE7`, `0xFE`); every one of them still shows `fault` on
its first trial in the run that scored it `invalid_run`, and the `invalid_run` label there
is the *integrity sentinel failing because the fault left the buffer unwritten* — not a
value that works. The recorded OS fault classification is
`kIOGPUCommandBufferCallbackErrorPageFault` (**a GPU address fault caused by our own
encoding**), never `...ErrorInnocentVictim`, so these are not sibling contamination.

**Consequence: nothing moves.** No accepted-value set changes, so no label, no rule and no
emittability count in this document changes. The fault counts quoted in §1 and §6 are
confirmed. This is the opposite of EXP-0153's experience — where four of five "reproducible"
faults evaporated under isolation — and the difference is worth recording: those free-running
bf16 captures were clean, and we now know that rather than assuming it.

### 13.2 `jcn1` / `jcn2` — COMPLETE, and the `jump_cond` scope verdicts are now strong

`ADDENDUM-PREREG.md` §2 asked whether `jump_cond.cf_scope` and `.reserved` are inert in a
program that still **computes its exact right answer**, rather than only inert on
taken-vs-not-taken. Both runs are in:

| | `jcn1` | `jcn2` |
|---|---|---|
| cases | 512 | 512 |
| `jump_cond.cf_scope@NAT` | **256 / 256 `ok`** | **256 / 256 `ok`** |
| `jump_cond.reserved@NAT` | **256 / 256 `ok`** | **256 / 256 `ok`** |
| hangs / invalid runs | 0 / 0 | 0 / 0 |
| baseline re-validations | 3 / 3 passed | 3 / 3 passed |
| duration | 5.7 s | 3.2 s |

Gate: 512 common cases, **0 only-in-one-run, accepted sets identical, 100.0 % exact
cross-run agreement**. Every one of the 512 cases reproduced the exact host-computed
fall-through oracle `[7, 17, 27, 37, 47, 57, 67, 77]`.

**Prediction met, refuter did not fire.** So the two verdicts no longer rest on the coarse
observable: `analysis/field_verdicts.json` now cites the `@NAT` arm for both fields
(`accepted_count: 256`), and `analysis/field_verdicts.py` picks the **strictest** arm when
two cover one field rather than the first one it happens to see.

**`jcn1` had to be relaunched**, and the reason matters: its first attempt exited **75**
from `gpulease.sh` after waiting 3600 s for the lease behind eight other waiters.
`run.py` never started, so **no directory was created and the id was never consumed** — the
same benign failure the first `cf01d` attempt hit, already documented in
`raw/BURNED_RUN_IDS.md`. It is a scheduling failure, not a hang, and §7 explains why
finishing this already-dispatched arm is consistent with the CF stop.

---

## 14. What the orchestrator should merge (and what it must not)

`analysis/field_verdicts.json` is the machine-readable form. Summary, all `target: G17P`,
all `evidence: [EXP-0156]`:

| field | label | range | accepted | rule |
|---|---|---|---:|---|
| `atomic_mem.op` | `hardware-run` | 0..255 dense (all 256 values) | 56 | `—` |
| `atomic_mem.op_lsb` | `hardware-run` | 0..255 dense (all 256 values) | 56 | `—` |
| `atomic_mem.op_msb` | `hardware-run` | 0..255 dense (all 256 values) | 56 | `—` |
| `atomic_mem.per_lane` | `hardware-run` | 0..255 dense (all 256 values) | 56 | `—` |
| `atomic_rmw.op` | `hardware-run` | 0..255 dense (all 256 values) | 48 | `—` |
| `atomic_rmw.op_lsb` | `hardware-run` | 0..255 dense (all 256 values) | 48 | `—` |
| `atomic_rmw.op_msb` | `hardware-run` | 0..255 dense (all 256 values) | 48 | `—` |
| `atomic_rmw.per_lane` | `hardware-run` | 0..255 dense (all 256 values) | 48 | `—` |
| `atomic_tg.op` | `hardware-run` | 0..255 dense (all 256 values) | 24 | `—` |
| `atomic_tg.op_desc` | `hardware-run` | 0..255 dense (all 256 values) | 4 | `—` |
| `atomic_tg.op_hi_rsv` | `hardware-run` | 0..255 dense (all 256 values) | 24 | `—` |
| `atomic_tg.rsv10lo` | `hardware-run` | 0..255 dense (all 256 values) | 2 | `v & 0x7F == 0x00` |
| `bf_add_dst._opsel_byte2` | `hardware-run` | 0..255 dense (all 256 values) | 8 | `v & 0xC7 == 0x04` |
| `bf_add_dst.dst` | `hardware-run` | 0..255 dense (all 256 values) | 1 | `v & 0xFF == 0x21` |
| `bf_add_dst.fmt` | `hardware-run` | 0..255 dense (all 256 values) | 2 | `v & 0x7F == 0x00` |
| `bf_add_dst.srcA` | `hardware-run` | 0..255 dense (all 256 values) | 2 | `v & 0x7F == 0x00` |
| `bf_add_dst.srcB` | `hardware-run` | 0..255 dense (all 256 values) | 2 | `—` |
| `bf_add_dst.tail` | `hardware-run` | 0..255 dense (all 256 values) | 32 | `v & 0x83 == 0x81` |
| `bf_fma_dst.dst` | `hardware-run` | 0..255 dense (all 256 values) | 1 | `v & 0xFF == 0x21` |
| `bf_fma_dst.fmt` | `hardware-run` | 0..255 dense (all 256 values) | 2 | `v & 0x7F == 0x00` |
| `bf_fma_dst.srcA` | `hardware-run` | 0..255 dense (all 256 values) | 2 | `v & 0x7F == 0x00` |
| `bf_fma_dst.srcB` | `hardware-run` | 0..255 dense (all 256 values) | 4 | `v & 0x77 == 0x06` |
| `bf_fma_dst.srcC` | `hardware-run` | 0..255 dense (all 256 values) | 2 | `v & 0x7F == 0x04` |
| `h_alu_hi.dst` | `hardware-run` | 0..255 dense (all 256 values) | 1 | `v & 0xFF == 0x28` |
| `h_alu_hi.opflags` | `hardware-run` | 0..255 dense (all 256 values) | 16 | `v & 0xC3 == 0x03` |
| `h_alu_hi.opsel` | `hardware-run` | 0..255 dense (all 256 values) | 16 | `v & 0xC3 == 0x03` |
| `h_alu_hi.srcA` | `hardware-run` | 0..255 dense (all 256 values) | 2 | `v & 0x7F == 0x01` |
| `h_alu_hi.srcB` | `hardware-run` | 0..255 dense (all 256 values) | 2 | `v & 0x7F == 0x09` |
| `hminmax.dst` | `hardware-run` | 0..255 dense (all 256 values) | 1 | `v & 0xFF == 0x22` |
| `hminmax.dst_full` | `hardware-run` | 0..255 dense (all 256 values) | 2 | `v & 0x7F == 0x00` |
| `hminmax.sel` | `hardware-run` | 0..255 dense (all 256 values) | 8 | `—` |
| `hminmax.selhi` | `hardware-run` | 0..255 dense (all 256 values) | 8 | `—` |
| `hminmax.srcA` | `hardware-run` | 0..255 dense (all 256 values) | 2 | `v & 0x7F == 0x00` |
| `hminmax.srcB` | `hardware-run` | 0..255 dense (all 256 values) | 1 | `v & 0xFF == 0xC0` |
| `if_push_pred.level` | `untested` | 0..255 dense (all 256 values) | 16 | `v & 0x3C == 0x00` |
| `jump.branch_ctrl` | `hardware-run` | 0..255 dense (all 256 values) | 254 | `—` |
| `jump_cond.cf_scope` | `hardware-run` | 0..255 dense (all 256 values) | 0 | `—` |
| `jump_cond.offset` | `hardware-run` | 56 values sampled | 2 | `—` |
| `jump_cond.reserved` | `hardware-run` | 0..255 dense (all 256 values) | 0 | `—` |
| `mask_op.mask_bank` | `untested` | 0..255 dense (all 256 values) | 0 | `—` |
| `mask_op.scope_kind` | `untested` | 0..255 dense (all 256 values) | 0 | `—` |
| `pop_reconverge.reserved` | `hardware-run` | 35 values sampled | 35 | `—` |
| `ret.linkmode` | `hardware-run` | 0..255 dense (all 256 values) | 32 | `v & 0x07 == 0x04` |
| `ret.scoreboard` | `untested` | 0..255 dense (all 256 values) | 12 | `—` |
| `ret_luse.linkmode` | `hardware-run` | 0..255 dense (all 256 values) | 32 | `v & 0x07 == 0x04` |
| `ret_luse.tail` | `hardware-run` | 0..255 dense (all 256 values) | 12 | `—` |
| `tg_addr_compute._byte0_unmodelled` | `hardware-run` | 0..255 dense (all 256 values) | 104 | `—` |
| `tg_addr_compute._byte1_unmodelled` | `hardware-run` | 0..255 dense (all 256 values) | 96 | `—` |
| `tg_addr_compute._byte2_unmodelled` | `hardware-run` | 0..255 dense (all 256 values) | 256 | `—` |
| `tg_addr_compute.b3` | `hardware-run` | 0..255 dense (all 256 values) | 256 | `—` |
| `tg_addr_compute.b4` | `hardware-run` | 0..255 dense (all 256 values) | 256 | `—` |
| `tg_addr_compute.b5` | `hardware-run` | 0..255 dense (all 256 values) | 256 | `—` |

**Must NOT be merged as an encoding change:** the five `db_defects` entries are *reports*,
not patches. `tools/agx-isa/db.json` was not edited and the `tg_addr_compute`
`emit_unsafe` veto is **not** lifted by this experiment — its byte0 and byte+1 are live
operand selectors that `db.json` models as no field at all, so an emitter still cannot
fill them from the tables.

**Note the three `_byte*_unmodelled` keys** (`tg_addr_compute._byte0/1/2_unmodelled`):
those are bytes `db.json` pins in `match` rather than exposing as fields. They are
reported with their measured accepted sets so the information is not lost, but they
have no `validation.json` slot to merge into until `db.json` models them.

---

## 15. Defects found in THIS experiment's own analysis code

Three bugs in the analysis scripts were found and fixed after the captures were complete.
None of them touched `raw/`, and all three are recorded because each one had, for a while,
made this document say something slightly wrong.

**A-1 — the GATE table silently kept the WEAKER arm.** `analysis/field_verdicts.py` gates
each arm on its pre-registered liveness/falsifier controls. The two `@NAT` arms added by
`ADDENDUM-PREREG.md` §2 were never given entries in that table, so `GATE.get(arm, [])`
returned `[]`, `gate_ok` evaluated false, and both scored `corpus-correlation` instead of
`hardware-run`. The `@P1` arm — which has an accepted set of **0** because at a poison
offset the store never runs — then overwrote them as the "stronger" label. For a while
`field_verdicts.json` therefore cited the coarse poison-offset evidence for
`jump_cond.cf_scope`/`.reserved` while the far better natural-offset evidence sat unused.
Fixed by adding the missing GATE entries.

**A-2 — first-seen beat strictest.** The same function's de-duplication kept whichever arm
it happened to encounter first when two arms cover one field. It now prefers a
`hardware-run` over anything weaker and, among equals, the arm with the **strictest
observable** (`@NAT`, where inertness means the program still computes its right answer,
over `@P1`/`@P2`, where it only means the branch was taken).

**A-3 — the emittability baseline was reading our own rows back.** `analysis/emittability.py`
computed "before" straight from `tools/agx-isa/validation.json`. By the time the analysis
was last re-run the orchestrator had already merged EXP-0156's verdicts into that file
(commit `39520163`), so "before" already contained them and the reported delta collapsed to
**zero newly emittable instructions**. The baseline now **subtracts every
`EXP-0156`-attributed label**, which makes the delta reproducible no matter when the script
is run, and `emittability.json` pins the `db.json` / `validation.json` hashes behind the
absolute totals. See §10.

---

## 16. DEF-0156-1 — this document was destroyed by a runaway write, and reconstructed

**What happened.** After the last commit of this file (`2013bf66`), the edit that replaced
§13.2 with the completed `jcn1`/`jcn2` section computed its target range as
`s[s.index("### 13.2 …") : s.index("## 14. …")]`. By then an earlier edit had inserted §14
**ahead of** §13, so that slice was **reversed and evaluated to the empty string**, and
`str.replace("", new_section)` inserts its argument at *every character position*. The
result was `RESULTS.md` at **83,178,232 bytes / 1,531,963 lines**, of which `sort -u` finds
only **116 unique lines**: the new §13.2 block repeated roughly fifty thousand times with
the original document's characters interleaved one at a time between the copies. Every
other section was gone, including the `# `-level title.

**What was NOT affected.** `raw/` (all 24 run directories, append-only), every
`analysis/*.json`, `manifest.json`, `PROGRESS.md`, `PRE_REGISTRATION.md`,
`ADDENDUM-PREREG.md`, `CAPTURE_CONTRACT.json`, `README.md`, `harness/` and `kernels/`. The
corruption hit exactly one file. No hardware run was repeated for this repair.

**How it was reconstructed.** The broken file was preserved outside the repository; the
committed version at `2013bf66` (756 lines, 47,780 bytes) was restored, and the post-commit
edits were re-applied **once each**, every replacement now asserting that its anchor is
non-empty and occurs exactly once — the guard whose absence caused this. The §13.2 text was
lifted verbatim from one surviving copy in the broken file. The §13/§14 inversion that made
the reversed slice possible was also corrected.

**Honest limitation.** The reconstruction is faithful for everything listed in §15 and in
the edits above, but the corrupted window is not byte-recoverable: **some post-commit
wording may not be restored verbatim.** Any small phrasing difference between this document
and the version that existed immediately before the corruption is unrecorded. Nothing
numeric was reconstructed from memory — every figure in this document is regenerated from
`analysis/gate_report.json`, `analysis/field_verdicts.json` and `analysis/emittability.json`,
which were untouched, and was re-checked against them after the repair.
