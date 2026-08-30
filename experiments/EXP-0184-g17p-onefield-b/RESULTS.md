# EXP-0184 — RESULTS

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6
build 25G5043d, Metal family Apple9). **Nothing ran on the M4.**
**Clean-room:** `OWN-SHADER` + `HW-PROBE`. Every byte spliced, decoded or inspected is the compiled
form of our own MSL in `kernels/`. **No Apple binary was disassembled or introspected.**
**Gate applied:** `PRE_REGISTRATION.md` §6, implemented by `analysis/verdicts.py` and nothing else.
Verdicts are recomputed from `raw/` on every invocation, never read back from a run manifest.

---

## 0. Headline

**Two instructions move across the emittable line: `rt_query_traverse` and `copysign`.**
Two fields are proven inert on carrier sets that span the dimension they control and are therefore
**not** promoted. Six fields were declined before any device time, each with a named reason. Three
`db.json` defects are recorded with evidence and **not** applied (`EXP-0183` owns that file).

Read-only simulation against the live `validation.json` (`work/emitcheck/emittability_delta.json`):
**60 → 62 emittable instructions.**

| field | verdict | label | coverage (dispatched / distinct bytes / encodable) | cross-run |
|---|---|---|---|---|
| `rt_query_traverse.dst` | **LIVE** | `hardware-run` | 16 / 896 / 16 | **100.000 %**, 4 of 10 arms with power moved |
| `copysign.operands` | **LIVE** | `hardware-run` | 256 / 512 / 256 | **100.000 %**, 2 of 2 arms |
| `if_push.scope` | INERT-ROBUST | `single-template-inference` | 256 / 2560 / 256 | **100.000 %**, 10 arms, all controls fired |
| `cvt_f2i.b9` | INERT-ROBUST | `single-template-inference` | 256 / 1280 / 256 | **100.000 %**, 5 arms, all controls fired |

`distinct_bytes` is counted from **distinct `bytes` strings in `raw/`**, never from the dispatched
value count. `encodable_range` counts values that still re-decode as the target mnemonic under the
**pinned** tokenizer.

**Run hygiene.** 7176 cases × 2 gated runs, 67 s and 69 s. **0 hangs, 0 watchdog timeouts, 0
malformed responses, 0 invalid runs, 0 `InnocentVictim`, 0 cross-run disagreements on any of the
147 arms.** 90 contained command-buffer faults, every one of them inside a *control* arm.
`concurrent_gpu_procs` was empty in both runs' `env.json` — the machine being quiet is recorded as
a measurement, not asserted.

---

## 1. `rt_query_traverse.dst` — LIVE, and the field is half the width `db.json` says

### Observed

Four arms had detection power *and* moved: `rq_mdist#6`, `rq_mdist#7`, `rq_mprim#6`, `rq_mprim#7`.
On each, all 16 values were dispatched in both runs with **zero** cross-run mismatches, and the
accept set is exactly one 4-value block:

| arm | occurrence bytes | compiled `dst` | values that reproduce the oracle | values that do not |
|---|---|---:|---|---|
| `rq_mdist#6` | `7f 80 86 38 0f 22 82 3a` @4796 | 7 | **4,5,6,7** → 1.0 (correct) | the other 12 → **4.0** |
| `rq_mdist#7` | `3f 80 86 16 07 22 82 2a` @5036 | 3 | **0,1,2,3** → 1.0 | the other 12 → **3.0** |
| `rq_mprim#6` | `bf 80 86 3e 0f 22 82 40` @5994 | 11 | **8,9,10,11** → 2.0 | the other 12 → **0.0** |
| `rq_mprim#7` | `7f 80 86 14 0f 22 82 34` @6248 | 7 | **4,5,6,7** → 2.0 | the other 12 → **0.0** |

`analysis/finalize.py` searches for the smallest `k` such that "the accept set is the coset of the
compiled value under *the top k bits are live*" explains **every** arm. It finds **k = 2**, with no
exceptions in 4 arms × 16 values × 2 runs.

### Interpretation

`dst` is a live destination selector, and **only bits 6..7 of the instruction (the top 2 bits of
the modelled 4-bit field) are load-bearing; instruction bits 4..5 are HW-tested inert.** An emitter
may choose the top two bits and must expect the low two to do nothing. Off the accept block the
traversal commits a *different* hit on the committed-distance carrier (4.0 or 3.0 instead of 1.0)
and returns a **silent zero** on the committed-primitive-id carrier — the Apple9 failure mode
again, and the reason the read-back is poisoned: 0.0 here is a real write of zero, not an
unexecuted program (`unwritten` was empty and the sentinel was present in every one of those cases).

This independently reproduces, on a sixth instruction family, the inert-top-bit pattern EXP-0099
established for operand descriptors — here at the *bottom* of a destination field rather than the
top of a source one.

### What this does not show

The *meaning* of the two live bits is not decoded: we know which values preserve correctness and
which do not, not which architectural register each names. Only 4 of 56 swept arms moved; **10 of
56 had a control that fired at all**, and the other 46 arms sit on occurrences the query never executes by
these queries — which independently reproduces EXP-0157's reachability finding and EXP-M4-14's
"only the committed-path op is load-bearing". Two occurrences (`rq_cdist#6`, `rq_ccount#6`) had a
control that fired only 1–2 times of 15 and did **not** move on `dst`; they are reported, not
averaged in.

**This is why the pilot existed.** Had the arms been frozen blind at four of the fourteen
occurrences per carrier, the sweep would very likely have hit four unreached ones and published a
confident, meaningless INERT verdict on a field that in fact moves.

---

## 2. `copysign.operands` — LIVE on G17P, contradicting the M4 result

### Observed

Both carriers that emit `copysign` (`cs_load`, load-sourced operands; `cs_chain`, result consumed
by a following ALU op) give the **identical 4-group partition** over all 256 values, in both runs,
with **0 cross-run mismatches**:

| values | n | behaviour on `cs_load` (a = ±5, ±3.25, ±9.5, ±1.75; b = ∓2, ∓8, ∓0.5, ∓6) |
|---|---:|---|
| **{0, 1, 128, 129}** | 4 | correct: `[-5, 5, -3.25, 3.25, -9.5, 9.5, -1.75, 1.75]` |
| {2, 3, 130, 131} | 4 | lane 0 correct; **lanes 1..7 still POISON** (never written) |
| {4, 5, 132, 133} | 4 | even lanes correct; odd lanes return `b[t]` itself |
| all other 244 | 244 | even lanes correct; odd lanes **0.0** |

The same four groups, same value sets, on `cs_chain`.

### Interpretation

`operands` is a live **operand descriptor**, not the untyped `raw` byte `db.json` models. Bit 0 and
bit 7 are indistinguishable at every base value that has more than one behaviour — `{v, v|1,
v|128, v|129}` is a single group at v = 0, 2 and 4 — which is exactly the `(reg << 1) | size`
operand-byte shape `db.json` already documents for `falu2`, with the inert top bit EXP-0099
HW-tested on five other families. Only the compiled encoding (and its three inert-bit aliases)
reproduces `copysign`; every other operand selection degrades quietly.

**An emitter may set this byte to 0x00, 0x01, 0x80 or 0x81 and get `copysign(a, b)`. Any other
value silently produces something else — never a fault.** That accept set — 4 of 256 — is the whole
content of the `hardware-run` label here.

### The contradiction with EXP-0138, stated rather than smoothed over

EXP-0138 (M4) reported *"`copysign` (4 B) — `operands` (byte+3) is INERT: all 256 values return the
same result"*, and EXP-0164 withheld the field on that basis. **On G17P, with a compiled
`copysign(a[t], b[t])` kernel dispatched against real memory operands, 252 of 256 values move.**
Two explanations remain open and this experiment does not separate them:

1. a genuine **target** difference (M4/G16G vs A18/G17P), which the per-field `target` rule exists
   for; or
2. EXP-0138's carrier was a synthesized MODE-B *lift* rather than a dispatched compiled kernel, and
   its copysign operands were not on the observed output path in a way that masked byte+3.

Explanation 2 is the more economical, because EXP-0138's own detection-power control for that arm
was a **byte+1 sweep**, and byte+1 is a *match constant*: changing it changes which instruction the
bytes are (§4). A control that fires by encoding a different opcode does not demonstrate that the
carrier can see *this* instruction's operand field. Neither prior record is retracted here; the M4
row stands on its own target, and this row is `target: G17P`.

---

## 3. `if_push.scope` — INERT-ROBUST across nesting depth 1..3, with every control firing

### Observed

10 occurrences (3 in `cf_if2`, 7 in `cf_if3`), all 256 values, both runs: **5120 dispatches, every
one `ok`, 0 moved, 0 faults, 0 hangs.** The `scope_kind` control at the *same* occurrence fired on
**all 10** arms (11–15 of 16 values moved), and its per-lane partitions are rich and exact — lanes
that take the wrong branch, and lanes left at `0xDEADBEEF` because the mask narrowed and they were
never written.

### Interpretation

On G17P, in a conditional-skip (`scope_kind = 0x01`) region, **byte+2 of `if_push` does not affect
execution at any of the 256 values, at any nesting depth from 1 to 3** — including 0x56, the value
`db.json` names as the *other* mask bank. The instrument was demonstrably able to see a difference
at the same byte offset in the same instruction, so this is a hardware fact about the field, not a
dead carrier.

Under rule 8 an inert field is **not** promoted: emitter grade asserts an implementer may *choose*
the value, and "emit what the compiler emitted" is a captured-template dependency. The measurement
is not downgraded — it lives in full in `range`, `note` and the arm table.

### The limitation that keeps this PARTIAL, stated explicitly

The five authored control-flow carriers produced `if_push` in only two of them, and **every one of
the ten occurrences is `0f 05 54 01`** — `scope = 0x54`, `scope_kind = 0x01`. Our G17P compiler
never emitted `0x56` for a 3-deep if/else ladder, and none of our three loop shapes (`cf_loop`,
`cf_loopif`, `cf_if1`) emitted `if_push` at all, so **the loop-iteration region kind
(`scope_kind = 0x1a`), which is where `db.json`'s 0x54/0x56 nesting-parity claim actually comes
from (EXP-M4-13 R6, on M4), was never reached.** The carriers span nesting *depth*; they do not
span *region kind*. A future arm that reaches a `0x1a` push is the one thing that could still
overturn this, and it is the recommended next step.

Note in passing, as a compiler observation rather than a hardware one: `db.json`'s "ping-pongs
0x54/0x56 with nesting parity" is **not reproduced** by if-nesting on G17P.

---

## 4. `cvt_f2i.b9` — INERT-ROBUST across four destination types and two source widths

### Observed

5 carriers (`int`, `uint`, `short`, `ushort` destinations; `float` and `half` sources), 1
occurrence each, all 256 values, both runs: **2560 dispatches, every one `ok`, 0 moved, 0 faults,
0 hangs.** The `cvt_f2i.dst` control at the same occurrence fired on all 5 (31–32 of 32 values
moved, with faults and silent zeros exactly as EXP-0168 measured for that field on G17P).

### Interpretation

byte+9 is a **don't-care** across its full range on every destination width and sign we can reach,
with the instrument proven able to see a difference two bytes away. `db.json`'s "byte+9 = reserved
0x00" is correct as far as it goes, and this bounds it: it is reserved *and inert*, not merely
unobserved.

**The second pre-registered question is also answered.** H3's refuter B was: if the modelled 10-byte
length is wrong and byte+9 is really the next instruction's leader, sweeping it would fault, hang,
or corrupt the following op. **2560 dispatches, zero non-`ok` outcomes.** The 10-byte length is not
contradicted.

Not promoted, for the same rule-8 reason as §3.

---

## 5. `db.json` defects — recorded, NOT applied (`EXP-0183` owns that file)

Full machine-readable form: `analysis/field_verdicts.json` → `"db_defects"`.

1. **`rt_query_traverse.dst` is modelled 4 bits wide and is 2.** Only instruction bits 6..7 are
   live; bits 4..5 are inert on 4 arms × 2 runs with no exceptions. *Suggested action:* narrow to
   width 2 at start 6, or keep width 4 and document bits 0..1 of the field as inert.
2. **`copysign.operands` is typed `raw` and is a live operand descriptor** with the exact accept set
   `{0x00, 0x01, 0x80, 0x81}` and an inert bit 0 / bit 7. *Suggested action:* retype and record the
   accept set.
3. **`copysign` byte+1 and byte+2 are modelled as fixed match constants and are load-bearing** —
   248/256 and 224/256 values change the observable. **This is deliberately NOT reported as a field
   result.** `encodable_range` is **1** for both: every value other than the constant decodes as a
   *different instruction* (or as nothing at all) under the pinned tokenizer, so the movement is the
   sweep encoding something else, not evidence about a `copysign` field. It is recorded so the next
   agent does not mistake it for one — and it is the most likely reason EXP-0138's M4 arm believed
   it had detection power (§2).

---

## 6. Negative and bounded results (first-class)

- **`if_push.scope`: 0/256 across 10 occurrences, controls firing on all 10.** Bounded by §3's
  region-kind limitation.
- **`cvt_f2i.b9`: 0/256 across 5 carriers spanning destination width and sign, controls firing on
  all 5.**
- **46 of the 56 swept `rt_query_traverse` occurrences are never executed** by any of the four ray queries —
  the reachability result, reproduced independently of EXP-0157.
- **Three of five authored `copysign` carriers emit no `copysign`** (`cs_alu`, `cs_mix`, `cs_two`);
  the compiler folded them away. **Three of five control-flow carriers emit no `if_push`**
  (`cf_if1`, `cf_loop`, `cf_loopif`). *5 carriers authored, 2 usable* in each case — a measured
  bound, recorded in `harness/arms184.json` → `dropped_carriers`, not repaired after the fact.
- **No hazard wall exists anywhere in this experiment's swept ranges.** 7176 × 2 dispatches with
  **no abort path** produced 0 hangs. That is a real negative for `if_push`, which EXP-0168 hung on:
  on G17P, sweeping byte+2 of a conditional-skip `if_push` on a 32-lane dispatch is not hazardous.

## 7. Declined before any device time

`iadd2.b2_fmt` (EXP-0171 already swept it dense and inert) · `n4_cf_word.b3` (EXP-0172 already
dispatched 256 values, STILL-UNDERPOWERED) · `cubearray_coord_const.b3` and `mesh_out_src.sel`
(measured 0 occurrences across 24 carriers) · `n4_rt_word.dst` (in scope in principle, deferred
rather than half-done — the recommended next step) · `ret.scoreboard` and
`dev_scoreboard_fence.scope_flag` (declined four experiments deep; EXP-0179 declined the first
**on a control that fired**). Reasons in full: `PRE_REGISTRATION.md` §8.

## 8. Limitations

1. **Target.** Everything here is G17P. The `copysign.operands` result **contradicts** the M4 row
   and neither is retracted; §2 gives both candidate explanations and does not choose.
2. **`if_push.scope` never reached a loop-iteration (`0x1a`) region**, which is where the
   nesting-parity claim originates. The inert verdict is therefore about conditional-skip regions
   at depth 1..3.
3. **`rt_query_traverse.dst`'s two live bits are characterised behaviourally, not decoded.** We know
   the accept set; we do not know which register each value names.
4. **`copysign`'s inert-bit claim rests on three base values** (0, 2, 4) where more than one
   behaviour exists; across the 244-value collapsed region bit 0 and bit 7 are trivially
   indistinguishable, so the claim is supported there but not independently determined.
5. **One quiet-machine window.** Both gated runs saw an empty process table for GPU peers. That is
   good for reproducibility and means these numbers have **not** been stress-tested against the
   contention EXP-0158 measured (102 of 174 cases MIXED across five runs on a busy machine).

## 9. Reproduction

```bash
export SSHPASS='...'
bash harness/sync.sh push
python3 harness/verify_remote.py                       # separate step, exit 0 required
bash harness/sync.sh build
bash harness/sync.sh shell 'cd ~/agxre/EXP-0184 && python3 analysis/census.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0184 && python3 analysis/gen_arms.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0184 && python3 run.py --run-id g17p_20260830_run01'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0184 && python3 run.py --run-id g17p_20260830_run02'
bash harness/sync.sh pull
python3 analysis/verdicts.py  raw/g17p_20260830_run01 raw/g17p_20260830_run02
python3 analysis/partitions.py raw/g17p_20260830_run01 raw/g17p_20260830_run02
python3 analysis/finalize.py
```

## 10. Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected:      kernels/{k_cs184,k_cvt184,k_cf184,k_rq184}.metal — authored by us — and
                       the `_agc.main` bytes the public Metal runtime compiled from them
Apple binary introspection: NONE
Reproduction:          §9
Evidence:              raw/g17p_20260830_run01/sweep.jsonl (7516 lines, sha256 320c061b…)
                       raw/g17p_20260830_run02/sweep.jsonl (7516 lines, sha256 b341a095…)
                       raw/prefreeze/{census.json, pilot01/, CAPTURE_CONTRACT.v1..v5.json}
                       CAPTURE_CONTRACT.json (23 blob hashes, re-verified ON THE DEVICE)
```
