# PRE-REGISTRATION — EXP-0156 (A18 Pro / G17P)
## Control flow, memory, and the bf16/half cluster — on the documentation target

**Frozen before any gated capture.** Nothing below is edited after the first gated run;
deviations go in `RESULTS.md` §Deviations, never by rewriting this file.

**Target: Apple A18 Pro / G17P** (`users-MacBook-Neo`, `Mac17,5`, macOS 26.6,
`AGXAcceleratorG17P`, arch `applegpu_g17p`, 5 GPU cores, Metal family Apple9).
Every result this experiment produces is a **DIRECT G17P** result, not `INFERRED`.
The local M4 is the repo/analysis host only; no GPU work runs there.
`macvdmtool` is forbidden to this agent without exception.

---

## 0. Provenance of the harness, and what happened before this freeze

This experiment does **not** author a new harness. It reuses, verbatim and with citation:

* `harness/isa_helpers.py`, `carriers.py`, `cases.py`, `baseline.py`, `run.py`, `build.sh`
  from **EXP-0152** (which never captured; it reuses EXP-0140 → EXP-0128 → EXP-0112 →
  EXP-0090). EXP-0152's frozen CF case matrix is carried over **unchanged**, retargeted
  to G17P, and extended with the three new arm groups in §2.
* `kernels/carrier_cf.metal` (EXP-0112), `atomic_dev.metal`, `atomic_dev_imm.metal`,
  `atomic_tg.metal`, `dev_fence.metal` (EXP-0141) — byte-for-byte.
* `kernels/tg_tile.metal` = **EXP-M4-14's own `k_thr.metal`**, byte-for-byte, so the
  A18↔M4 `tg_addr_compute` divergence is re-tested on *the same source*.
* `kernels/bf_add.metal`, `bf_fma.metal`, `h_max.metal`, `h2_fma.metal` = **EXP-0145's**
  own-MSL bf16/half carriers, byte-for-byte.

**Disclosed pre-freeze activity (no GPU dispatch of any kind):** a compile-only pilot
(`harness/pilot_locate.py`, `harness/baseline.py`) compiled each carrier on the neo and
tokenized `_agc.main` with our own `tools/agx-isa` decoder, in order to pin each splice
site by content. Its outputs are retained at `work/pilot_loc.json` /
`work/pilot_baseline.json` and are cited in `RESULTS.md`. **No case was dispatched to the
GPU before this file was frozen.**

### Pilot result that this freeze depends on (and that is itself a finding)

Every M4-derived carrier assertion **reproduced on G17P**: `carrier_cf.metal`'s
`_agc.main` is again exactly **152 bytes**, its `base_slot` assignment is again
`a=2, n=1, out=0`, and the frozen 21-instruction skeleton layout
(`CF_STARTS_EXPECT`) matches exactly. The three atomic carriers' splice sites
(`atomic_mem` +70 len 14 ×2, `atomic_tg` +128 len 12) match exactly.
`tg_tile.metal` puts `tg_addr_compute` at **+46** with the bytes `1c 02 00 00 00 00` —
the identical form EXP-M4-14 and EXP-0141 both spliced.

---

## 1. Question

Per `tools/agx-isa/validation.json` at freeze, **45 of 171 instructions and 443 of 1036
fields** are emitter-grade. Twenty-seven instructions in three families are not, and
**loops are unemittable**, which blocks any real shader:

| family | instruction | blocking fields at freeze |
|---|---|---|
| CF | `if_push_pred` | `level` |
| CF | `jump` | `branch_ctrl` |
| CF | `pop_reconverge` | `reserved` |
| CF | `ret` | `linkmode`, `scoreboard` |
| CF | `ret_luse` | `linkmode`, `tail` |
| CF | `mask_op` | `mask_bank`, `scope_kind` |
| CF | `jump_cond` | `cf_scope`, `offset`, `reserved` |
| CF | `call` / `call_indirect` | 4 each |
| MEM | `atomic_mem` / `atomic_rmw` | `op_lsb`, `per_lane`, `op_msb` |
| MEM | `atomic_tg` | `op_desc`, `rsv10lo`, `op`, `op_hi_rsv` |
| MEM | `tg_addr_compute` | instruction-level `emit_unsafe` veto |
| MEM | `dev_scoreboard_fence`, `mem_fence`, `mem_fence8` | fence-scope fields |
| bf16 | `bf_alu`, `bf_add_dst`, `bf_mul_dst`, `bf_fma_dst`, `bf_alu8_var` | operands, all `untested` |
| half | `half_pack`, `hminmax`, `h_alu_hi`, `funary`, `funary_imm`, `fldexp` | operands |

**Three questions, in priority order:**

1. **Do loops become emittable on G17P?** A loop needs `if_push_pred`, `jump_cond`,
   `if_push`, `ret`, `jump` and `pop_reconverge` emittable simultaneously.
2. **Does the `tg_addr_compute` G16G↔G17P divergence reproduce on real A18 silicon?**
3. **What is a bfloat16 arithmetic result on this hardware?** No experiment in this
   repository has ever measured one; `docs`' P2-01/02 are "hardware YES, emit NO".

## 2. Hypotheses, each with its refuter

### Group A — control flow (EXP-0152's H1–H9, carried over unchanged, now on G17P)

**H1 (`jump.branch_ctrl`).** Inert across the whole byte inside a program whose oracle
proves the back-edge executed, except `{0,1}`, which EXP-0140 `run03` observed as
reproduced hangs (its `run02` saw both inert).
*Prediction:* 2..255 all reproduce the CF baseline oracle exactly.
*Refuter:* any value in 2..255 that changes the output or faults reproducibly.
*Safety:* `{0,1}` excluded from dispatch, recorded as `skipped` with the reason.

**H2 (`pop_reconverge.reserved`, 16 bit).** Inert over the protocol's wide-field sample
at both of the skeleton's two `pop_reconverge` sites.
*Refuter:* any sampled value that changes the output.

**H3 (`ret`).** `ret.linkmode` runs only when `(v & 7) == 4` (EXP-0140 M4: 224/256
faulted); `ret.scoreboard` accepts a masked subset.
*Refuter:* an accepted set differing from `(v & 7) == 4`. **This is also the first
G17P test of an M4 rule; a difference is a first-class cross-target result.**
*Safety:* `scoreboard` `{8,12}` excluded (EXP-0140 reproduced hangs).

**H4 (`ret_luse`).** `ret_luse` is `ret` with byte+2 `0x54→0x56` — same 4-byte length at
the same address, so it splices in place with no displacement change.
*Prediction:* `ret_luse.linkmode` has the same accepted set as `ret.linkmode`.
*Refuter:* a different accepted set, or byte+2 `0x56` alone breaking the program.
*Safety:* `tail` excludes `{8,12}`.

**H5 (`if_push_pred.level`).** Accepts only `(v & 0xFC) == 0x00` (EXP-0140, M4).
*Refuter:* an accepted value outside that mask.
*Safety:* `{62,63,180,181}` excluded (EXP-0140 reproduced hangs).

**H6 (`mask_op`).** `mask_op` (`0f 04 <bank> <kind>`) is 4 bytes — exactly the length of
the skeleton's `if_push` (`0f 05 54 1a`) at +56 — so it splices at a real execution-mask
site with no length or displacement change.
*Liveness gate, pre-registered `expect_match=False`:* the compiler-natural `mask_op`
spliced over `if_push` **must change the output**.
*Refuter:* it reproduces the baseline ⇒ the site cannot distinguish the two, the arm
proves nothing, and both fields stay `untested`.

**H7 (`jump_cond` LIVENESS — the loop unlock).** EXP-0140 found every `jump_cond` field
inert *because the branch was never taken*: with `n = [0,1,2,3,4,8,16,32]` some lane has
`cnt > 0`, the guard is false, and the branch falls through, so even out-of-program
targets reproduced the baseline. **Binding `n` to all zeros makes the guard uniformly
true and the branch actually taken**, changing no program byte, no length and no
displacement.
*Prediction:* with `n = 0` and the natural offset `0x40` the output equals the
fall-through oracle `a[tid] - 3`; with `n = 0` and a **poison offset** it **differs**
(`expect_match=False`), while the same poison offset under the original mixed `n`
**reproduces** the mixed oracle. Poison offsets **P1 = 0x5C**, **P2 = 0x52**.
*Refuter:* the poison offset reproduces the baseline under `n = 0` too ⇒ the carrier is
still dead and all three `jump_cond` fields stay `untested`, exactly as EXP-0140 reported.

**H8 (`jump_cond.offset`).** Under `n = 0` the displacement selects the resume point, so
a dense forward window is observable. **EXP-0115's branch reach is a CHECKERBOARD (13 of
162 displacements worked) and was measured on `jump`, not `jump_cond`, so it does not
transfer** — hence dense, not sampled.
*Range dispatched:* 58..110 dense (53 consecutive values) plus far probes {128,192,256}.
*Deliberate exclusion:* **no negative and no 0/1/2 displacement.** With the branch
genuinely taken those are infinite loops; EXP-0128 hung the GPU exactly that way.

**H9 (`jump_cond.cf_scope` / `.reserved`).** Swept densely at **both** poison offsets, so
each value is classifiable as *branch taken* / *not taken* / *other* and the conclusion
does not rest on one target.
*Refuter:* the two poison targets disagree on a value's class.

### Group A′ — MEM atomics (EXP-0152's H10, unchanged)

**H10.** `atomic_mem`/`atomic_rmw` byte+12 and `atomic_tg` bytes +5/+10/+11 each contain
2–4 modelled fields; a dense 0..255 sweep of the whole byte executes every value of every
field it contains crossed against its byte-mates.
*Prediction:* the accepted sets reproduce EXP-0141's M4 sets.
*Refuter:* a different accepted set on either independent device-atomic carrier — which,
on G17P, would be a cross-target result rather than an error.
*Safety:* `atomic_tg` byte+5 `{0x7E,0x7F}` excluded (EXP-0141 reproduced GPU hangs,
published DO NOT EMIT).

### Group B — `tg_addr_compute`, the only live cross-target contradiction

**H11.** EXP-M4-14 (recorded on A18) says byte0 `0x1c` **and `0xfc`** both reproduce the
baseline. EXP-0141 H5 (M4) says **only `0x1c`** does and `0xfc` does not reproduce.
We are now on the A18, running EXP-M4-14's own kernel.
*Pre-registered BOTH ways, so neither outcome is a surprise:*
* `0xfc` reproduces the tile oracle here ⇒ **a genuine per-target hardware difference**;
  the M4 veto is an M4 fact and G17P has a second accepted byte0.
* `0xfc` does not reproduce here ⇒ **EXP-M4-14's A18 record does not replicate** and the
  M4 result generalises; the `emit_unsafe` veto stands on both targets.
*Refuter for the arm as a whole:* the unmutated carrier failing its own host oracle, or
the falsifier matching — either means the carrier is not live and nothing is concluded.
*Also swept:* all six bytes densely (M4 says +2..+5 are inert; +0 and +1 are live).
**The `emit_unsafe` veto is NOT lifted by this experiment under any outcome**: byte0 and
byte+1 are not modelled as fields in `db.json`, so an emitter still cannot fill them from
the tables. Lifting the veto is a `db.json` change and the orchestrator owns `db.json`.

### Group C — bf16 / half

**H12 (bf16 numerics).** The `0x11`-group op at +32 of `bf_add.metal`
(`21 00 1c 00 11 00 c0 81`) computes a **native bfloat add**.
*Prediction:* with inputs chosen so `a+b` is exactly representable in bf16, the packed
16-bit read-back equals the host-computed bf16 bit pattern of `a+b`, on all 8 lanes.
*Refuter:* it does not — e.g. the result is an fp32 or fp16 pattern, or zero.
*Falsifier dispatched:* the same program scored against an unreachable oracle.

**H13 (bf16 rounding mode).** Identical program bytes, an input pair whose exact sum
(`1 + 3/512 = 1.005859375`) lies strictly between two adjacent bf16 values and **nearer
the upper one**. Two oracles are dispatched, `truncate → 0x3F80` and
`round-to-nearest-even → 0x3F81`. **Exactly one may match**; if neither does, the result
is `UNKNOWN` and reported as such.

**H14 (op-select enum, proven BY VALUE not by inertness).** byte+2 `0x1c → 0x1d` turns
`a+b` into `a*b`.
*Prediction:* the mutated program matches the host-computed **MUL** oracle and, in its
paired control, **fails** the ADD oracle.
*Refuter:* it matches neither.
`0x1e` (fma) is pre-registered to **break**: it is a 10-byte form spliced into an 8-byte
slot, so the following bytes are misframed.

**H15 (`hminmax.sel`, proven BY VALUE).** byte+4 low-3-bits `0 → 1` turns `max` into
`min` (`db.json`).
*Prediction:* matches the host-computed MIN oracle, fails the MAX oracle.
*Refuter:* it matches neither, or matches both (impossible for these inputs, which are
chosen with `a ≠ b` on every lane).

**H16 (`h_alu_hi` writes the HIGH half).** A `half2` fma compiles to **two** ops: a
`0x?0`-group op at +46 and a `0x?8`-group op at +54. Halves are independently
addressable, 2 per GPR (EXP-0020).
*Prediction:* corrupting the `0x?8` op changes **only the high 16 bits** of each output
word; corrupting the `0x?0` op changes **only the low 16 bits**. Both are dispatched as
pre-registered `expect_match=False` probes; `analysis/verdicts.py` classifies every case
in both dense sweeps as `lo_changed` / `hi_changed` / `both` / `neither`.
*Refuter:* the `0x?8` op's corruption changes the LOW half, or both.

**H17 (bf16/half operand fields).** `dst` (byte0 high nibble), `fmt` (byte+1), `srcA`
(byte+3), `srcB` (byte+4), `srcC` (byte+5, fma) and the tail bytes are dense-swept; the
accepted-value set and the *produced value* per case determine the operand map.
*Refuter:* the accepted set is not describable and the produced values do not vary with
the operand byte ⇒ the field is not the operand and is reported as a `db_defect`.

## 3. Deliberately OUT of scope, with the reason stated now

* **`mem_fence.{sub,memclass,b5}`, `dev_scoreboard_fence.scope_flag`,
  `mem_fence8.{mask,tail}` — NOT swept.** `FIELD-SWEEP-PROTOCOL` §3.2 requires the field
  to be live on the observed output path. EXP-0141 swept the first four densely and
  refused promotion because **neither carrier has a memory-ORDERING observable**;
  EXP-0147 reached the same `INSUFFICIENT` verdict on six fence fields; EXP-0152
  pre-registered the same refusal. A carrier that cannot detect the fence's *removal*
  cannot test the fence's *scope bits*, and a pass would be a false `hardware-run`.
  `mem_fence8` has no dispatchable carrier at all (emitted only by `intersection_query`
  traversal; `agxrun_persist` cannot bind an acceleration structure).
  **These six fields are pre-registered to be reported `untested` with an explicit
  insufficiency statement.** `dev_scoreboard_fence` is therefore reported as **still one
  field short**, and this experiment says so rather than promoting it.
* **`call` (14 B) and `call_indirect` (6 B) — NOT attempted.** Neither appears in the
  frozen 152-byte CF skeleton, and the only same-length splice sites available
  (`device_load`/`device_store` for `call`, `pop_reconverge` for `call_indirect`) would
  transfer control to an address computed from uninitialised state — the exact
  construction that hung the GPU in EXP-0128. Reported `untested`.
* **`bf_alu8_var`, `half_pack`, `funary`, `funary_imm`, `fldexp`, `bf_alu`, `bf_mul_dst`
  — no dedicated arm.** `bf_mul_dst` is exercised through the `bf.opsel` semantic control
  (its byte+2 = 0x1d form at the add site), which is honest evidence for the op select
  but not a full operand sweep of that descriptor. The others need their own carriers and
  are a successor's job.

## 4. Independent / controlled variables

Independent: exactly one named field (or one byte) of exactly one instruction, per case.
For the `jump_cond` arms a second independent variable is the **`n` input buffer**
(`cfN` = `[0,1,2,3,4,8,16,32]` vs `cf0` = all zeros); for the bf16 rounding arm it is the
**`a`/`b` input buffers** (`bfadd` vs `bfround`). In both cases the program bytes are
identical and the input is varied only in pre-registered paired-control cases, never
inside a field sweep.

Controlled: the frozen 152-byte CF skeleton (never padded — EXP-0140 §9 showed
lengthening a CF carrier is **not** semantically neutral even with `acc`-only padding);
each carrier's `_agc.main` length; every other instruction's bytes; the dispatch shape;
the authored inputs.

## 5. Oracles (host-computed, GPU-independent)

* CF: `H.cf_oracle(a,n)` per lane — loop `n` times adding 1.5, then
  `acc > 100 ? acc*2 : acc-3` (EXP-0112, HW-confirmed by EXP-0140). `cf0` baseline =
  `a[tid] - 3` = `[7,17,27,37,47,57,67,77]`.
* Atomics: EXP-0141's host-computed oracles, recomputed from the MSL we wrote.
* `tgac`: `o[i] = a[(i+1)&255] + a[(i+2)&255]` with `a[i] = i`, i.e. EXP-M4-14's quoted
  `o[i] = 2i+3` signature, compared on 14 lanes.
* bf16/half: exact bit patterns computed in Python from the IEEE encodings
  (`bf16 = top 16 bits of fp32`; fp16 via `struct` `<e`), with inputs chosen so every
  expected `a+b`, `a*b`, `a*b+c`, `max`, `min` is exactly representable — **except** the
  rounding arm, whose whole purpose is to be inexact.

## 6. Falsifiers dispatched (pre-registered `expect_match=False`)

1. `cf.falsifier` (×2 inputs) — unmutated skeleton against an unreachable oracle.
2. `mask_op` liveness gate (H6).
3. `jump_cond` poison-offset gate under `n = 0`, at P1 and P2 (H7), each with its paired
   `cfN` control pre-registered `expect_match=True`.
4. `atdev`/`atdevimm`/`attg` unreachable-oracle falsifiers, plus EXP-0141's op-splice
   controls (`atdev` byte+12 `→0x22`, `attg` byte+11 `→0x05`).
5. `atdev_rmw.control` — byte+1 `0x01→0x11` selects the `atomic_rmw` form, pre-registered
   to still add.
6. `ret_luse` byte+2 `0x56` alone, pre-registered `expect_match=True`.
7. `tgac.falsifier` — unreachable oracle on the unmutated tile carrier.
8. Four bf16/half unreachable-oracle falsifiers (`bfadd`, `bffma`, `hmax`, `h2fma`).
9. `bf.opsel.mul_neg` and `h.minmax.min_neg` — the mutated program scored against the
   *unmutated* oracle, which must FAIL.
10. `h2.halfprobe` ×2 (H16).
11. `bf.opsel` value `0x1e` at the 8-byte add site, pre-registered to break.

An arm whose falsifier does not fire is reported as proving nothing.

## 7. Known confounders

* **Concurrency.** Five other agents share the neo. A GPU hang triggers a device-level
  reset that discards other contexts' command buffers as
  `kIOGPUCommandBufferCallbackErrorInnocentVictim`. Mitigations in §8.
* **Silent zeros.** On Apple9 a wrong field value usually yields a wrong value or an
  unwritten word, not a fault. Recorded as `silent_zero`/`wrong_value`, never skipped.
* **Non-local tokenization.** `docs/isa/README.md`'s `_r9_succ_safe` makes some lengths
  depend on *following* bytes failing to decode. Every case here is either a
  **same-length in-place byte splice** or a whole-program build of the frozen skeleton, so
  **no displacement is ever recomputed**. Our decoder's view of the spliced region is
  recorded per case as `rt` but **never** used to skip a case — the hardware does not
  consult our decoder.
* **Our decoder mis-tokenizes the bf16 sites.** `bf_add_dst`, `bf_fma_dst`, `hminmax` and
  the `0x?8` high-half op are not the mnemonics our disassembler returns at those
  offsets. Those five sites are therefore pinned by **exact bytes at an exact offset**,
  asserted unique within `_agc.main` — a stricter check than a mnemonic match — and the
  mis-tokenization is reported as a `db_defect`.
* **`mov_imm` immediates** are restricted to 0..127 and never 12 (EXP-0140 db-defect 4).
* **Poisoned read-back.** Every output buffer is bound as an *input* pre-filled with
  `0xDEADBEEF + i` so an unwritten word is recognisable.
* **EXP-0138's self-inflicted trap** — reading `r11` as a source zeroes it. No sentinel
  or oracle here lives in a register a descriptor under test can name: the CF sentinel
  (when used) is r14/r15, and the bf16/half sentinels are written from the carrier's own
  MSL through a separate buffer, not a register.

## 8. Mandatory `FIELD-SWEEP-PROTOCOL` §7 defences (all binding)

1. **Majority-of-3 replication.** Every case runs 2 trials, and 3 whenever the first is
   not `ok` or the first two disagree. A `fault`/`hang` label requires the majority.
2. **OS fault-classification string recorded verbatim** for every failing trial;
   `...ErrorInnocentVictim` failures are segregated as `invalid_run` (environmental),
   never as a property of the encoding, and retried up to 4 times.
3. **Periodic baseline re-validation** every 250 cases; two consecutive failures ⇒ runner
   restart, then abort rather than record a cascade.
4. **Integrity sentinel** through an independent path on every carrier that has one
   (`atdev`, `atdevimm`, `attg`, `bfadd`, `bfround`, `bffma`, `hmax`, `h2fma`). **The CF
   carrier and the `tgac` carrier cannot carry one**: the CF skeleton fills its 152 bytes
   exactly and lengthening it changes its semantics (EXP-0140 §9), and `tg_tile.metal` is
   reused byte-for-byte from EXP-M4-14 precisely so the divergence test is
   source-identical. There the **poisoned read-back is the integrity check** and a case
   whose compared words are all still poison is `invalid_run` and repeated. Declared here,
   not discovered later.
5. **Unique splice-archive path per request**, unlinked afterwards.
6. **GPU lease** (`~/agxre/gpulease.sh`) held around the **hang-prone** captures only —
   the CF group and the `tgac` group — per the orchestrator's 2026-08-29 policy. MEM and
   bf16 run free and concurrent. Which runs held the lease is recorded per run and
   reported in `RESULTS.md`.

## 9. Safety budget (`FIELD-SWEEP-PROTOCOL` §8)

* Per-request watchdog **8 s**. **2 genuine hangs stop that arm. 4 stop every remaining CF
  arm. 8 abort the run.** Skipped cases are recorded as `skipped`, never dropped.
* Arm ORDER is part of the contract, so a CF-wide stop cannot cost the cheap arms:
  `cf.baseline` → `jump.branch_ctrl` → `pop_reconverge.reserved` → `ret.linkmode` →
  `ret_luse.*` → MEM → `jump_cond.*` → `if_push_pred.level` → `ret.scoreboard` →
  `mask_op.*` → `tgac.*` → bf16/half.
* Known-hang exclusion list, dispatched as `skipped` records carrying the reason:
  `jump.branch_ctrl {0,1}`, `if_push_pred.level {62,63,180,181}`, `ret.scoreboard {8,12}`,
  `ret_luse.tail {8,12}`, `atomic_tg` byte+5 `{0x7E,0x7F}`.
* If the neo stops answering: **STOP, report BLOCKED**, record exactly where. No
  `macvdmtool`, ever.

## 10. Capture plan and the gate

Captures are split by arm group so a stop in one cannot cost another, and so `raw/` can be
pulled back off the neo incrementally:

| run pair | arms | lease |
|---|---|---|
| `g17p-<date>-tg01` / `tg02` | `tgac.*` | **held** |
| `g17p-<date>-cf01` / `cf02` | CF (`cf.*`, `jump*`, `pop_*`, `ret*`, `if_push*`, `mask_op*`, `jc.*`) | **held** |
| `g17p-<date>-mem01` / `mem02` | `atdev*`, `attg*` | free |
| `g17p-<date>-bf01` / `bf02` | `bf*`, `h.*`, `h2.*` | free |

Run ids are **never reused, never topped up**. A partial capture is retained under its own
id and cited as partial.

A field verdict is promoted only if **all** of:

* both runs of its pair dispatched the same case set for that arm (`coverage_equal`);
* the **accepted-value sets are identical** across the two runs;
* the arm's own liveness gate / falsifier behaved as pre-registered;
* the periodic baseline checks in both runs passed (no cascade).

Anything else is reported at the weaker label.

## 11. Rounding-up is forbidden

If a sweep is inconclusive the verdict is `corpus-correlation` or `untested`. Specifically:
a field whose every value is inert **in a carrier whose liveness gate did not fire** is
reported `untested`, not `hardware-run` — the trap EXP-0140 avoided on `jump_cond` and
EXP-0141/EXP-0147/EXP-0152 avoided on the fences. Labels come from the eight in
`docs/evidence-classification.md` and nothing else. `target` is **G17P** on every verdict
this experiment produces; no M4 label is ever carried onto a G17P result or vice versa.

## 12. Clean-room

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: our own MSL (kernels/*.metal, all authored by this project or reused
                  byte-for-byte from a prior experiment of this project) and the machine
                  code compiled from it; instruction bytes assembled by our own
                  tools/agx-isa (read-only use)
Apple binary introspection: NONE
```
