# EXP-0206 — RESULTS

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6
build 25G5043d, Metal family Apple9). **Nothing ran on the M4.**
**Clean-room:** `OWN-SHADER` + `HW-PROBE`. Every byte spliced, decoded or inspected is the compiled
form of our own MSL in `kernels/`. **No Apple binary was disassembled or introspected.**
**Gate:** `PRE_REGISTRATION.md` §7 plus `PRE_REGISTRATION_A2.md` (Gates A/B/C/E of
`/RE_EXPERIMENT_PROCESS_CORRECTIONS.md`), implemented by `analysis/verdicts206.py` and
nothing else. Verdicts are **recomputed from `raw/` on every invocation**, never read back from a
manifest, and the gate **runs a five-case self-test first and refuses to produce verdicts if it
fails**.

**Gated pair:** `g17p_20260830_run03` (forward case order) and `g17p_20260830_run04` (reversed
case order), 5,231 cases each. Regenerate everything with:

```bash
python3 analysis/verdicts206.py raw/g17p_20260830_run03 raw/g17p_20260830_run04
python3 analysis/emit_verdicts.py
python3 analysis/report_tables.py
```

---

## 0. Headline

**No field is proposed for promotion to `hardware-run` on its liveness alone, and for the three
that read inert the experiment now has the positive control that the previous refusals lacked.**
Four hardware facts are new, and two of them explain *why* the earlier measurements failed.

| # | Finding | Where |
|---|---|---|
| 1 | **`ret` / `ret_luse` `linkmode` decoded.** Accepted set is `v & 3 == 2` — **64 of 256**, not EXP-0156's `v & 7 == 4`. Within it, **bit 4 (0x10) is the restore-link flag**: at a genuine non-leaf return, clearing it gives a *different, deterministic, non-faulting* result; at a leaf return it is a don't-care. | §2.5 |
| 2 | **`pop_reconverge.reserved` is not reserved.** Its **low byte (bits 32..39) is load-bearing** — every sampled value with a zero low byte is correct, every value with a non-zero low byte gives one identical wrong result. Its high byte is inert over 9 tested values. | §2.3 |
| 3 | **A mid-program `stop` genuinely terminates, and the final `stop` word is executed.** Byte 0 → `0x0f` or `0x8f` faults reproducibly on three carriers in both runs; six other byte-0 values are harmless. | §2.7 |
| 4 | **`if_push.scope` is live and context-dependent.** At the one occurrence whose compiled value is `0x56`, all 128 bit-1-set values are correct and **none** of the 128 bit-1-clear values is; at three other occurrences — two of them the same `scope_kind == 0x1a` region kind — all 256 values are correct. | §2.1 |

Plus a **db defect that is the same gap as an evidence gap**: every non-leaf callee our compiler
emits ends with the 6-byte word `ef 02 54 00 00 50`, for which the pinned `db.json` has **no
descriptor**. A linear tokenizer walk dies there — immediately before the only occurrences in this
corpus carrying `linkmode == 0x12`, the exact value the leaf-only carriers of the withdrawn
`ret_luse.linkmode` measurement could never reach.

---

## 1. What was observed, before any interpretation

### 1.1 The census is evidence in its own right

`analysis/census.py` → `raw/prefreeze/census.json`. **Pre-freeze calibration; no verdict cites it.**

* **All 15 carriers compiled; every one emitted its target instruction.**
* **`if_push` with `scope_kind == 0x1a` (loop-iteration) is reached on all six loop shapes**, plus
  `0x21`, `0x25` and `0x29`. **`0x29` is not in `db.json`'s enum** `{1, 5, 26, 33, 37}`. EXP-0184's
  stated limitation was that this region kind was never reached; putting the trip counts in device
  memory and nesting the loops produces it every time.
* **The compiler emits both documented `if_push` banks** (`0x54`, `0x56`) and **both documented
  `pop_reconverge` banks** (`0x04` in every loop carrier, `0x24` in `cf_ifnl` and `cl_atomic`).
* **`ret` appears in ZERO carriers if you only look at `_agc.main`.** The callee lives in its own
  symbol region of the shader `__text` section: `_agc.main` holds the CALL, not the RETURN. This
  experiment's first census found exactly that, and `compile_carrier` was rewritten to carve every
  region separately.
* **`cl_atomic` carries a REAL compiler-emitted `ret_luse`**, `8f 12 56 00` — byte+2 `0x56` *and*
  `linkmode 0x12`. That occurrence needs no synthesis, and it refutes EXP-0156's `v & 7 == 4`
  accepted-set rule from our own compiled bytes before any sweep (`0x12 & 7 == 2`).
* **There is no natural mid-program `stop`.** `follows_code` is False at all nine natural stops.
  This **refuted the experiment's own H6 premise** and forced the constructed terminator (contract
  amendment 2).

### 1.2 Gate A — the actual-byte ledger

Every case re-reads its instruction bytes **out of the final dispatched blob** at the region's
absolute file offset and re-decodes the field with a bit-extract independent of the patcher that
wrote it. Across the gated pair: **ledger_ok on every case, 0 failures**, and distinct actual
encodings equal distinct requested values on every arm (no `match`-bit collision, no aliasing).
A symmetric assemble/disassemble round trip is not used anywhere in this experiment.

### 1.3 Gate E — how busy the machine was, measured rather than claimed

`raw/<run>/procs.jsonl` samples the process table at run start, every 100 cases, and at run end.
Throughout both gated runs the neo carried **8–21 other GPU processes** from sibling experiments
(EXP-0200, EXP-0201, EXP-0202, EXP-0207). Consequences, stated rather than hidden:

* **No verdict here claims `independently-confirmed`.** Per the orchestrator's ruling of
  2026-08-30, **Gate E is currently unmeetable for the whole wave** — EXP-0204's dedicated
  quiet-window helper sampled 86 times and never once found a quiet machine, with up to 17
  concurrent foreign GPU processes. Every reproducibility axis here therefore reads
  **`INCOMPLETE - Gate E not met`**, even on the rows where the two runs agree perfectly. A
  serialized quiet confirmation is owed and is listed in §6.
* Contamination is concentrated in the **fault** cases, where a device reset produces
  `InnocentVictim` on the retries. It is nearly absent from the **valid** cases that carry all the
  semantic content — e.g. 8 of 174 valid cases on the decisive `if_push` arm, 4 of 119 on the
  decisive `ret_luse` arm, 0 of 146 on the `stop@synth_mid` arms. This is EXP-0160's filter:
  contamination can destroy an observation but never fabricate a coherent one.
* **EXP-0204 declared ~18 genuine device hangs from a budgeted `tex_deriv` mapping pass between
  20:00 and 20:25 UTC.** Because this family faults and hangs *legitimately*, a foreign cascade in
  that window would be easy to misattribute to `stop.reserved` or `pop_reconverge`. So it is
  checked as a **computation over raw**, not asserted in prose: `verdicts206.py` re-scores any hard
  outcome timestamped inside the window as `measurement_failure` and reports the count.
  **Zero of this experiment's cases fall in it** — run03 spans 19:27:16–19:45:43Z, run04
  19:31:00–19:50:28Z and run05 19:50–19:5xZ, all before the window opens. The `if_push` faults and
  hangs reported in §2.1 are ours.
* It is also why `g17p_20260830_run01` was killed at 152 cases: it measured **1.756 s/case**
  against the pilot's **0.234 s/case**. It is retained exactly as it is, never topped up, its id
  never reused, and no verdict cites it.

---

## 2. Per field

Numerators and denominators are exact throughout; **no percentage is reported alone**. Hard
outcomes (fault / hang / invalid / measurement-failure) are counted **separately** from valid
payloads everywhere — a GPU fault is never scored as movement.

### 2.1 `if_push.scope` (start 16, width 8) — **LIVE, context-dependent; both pre-registered models refuted**

| occurrence | `scope_kind` | compiled `scope` | correct | fault | all-lanes-masked | V | L |
|---|---|---|---:|---:|---:|---:|---:|
| `cf_nl2` +106 | `0x1a` loop-iter | **`0x56`** | **128** (exactly the bit-1-**set** values) | 126 | 2 | 2 | 130 |
| `cf_nl3` +182 | `0x1a` loop-iter | `0x54` | 256 | 0 | 0 | 1 | 256 |
| `cf_ifnl` +126 | `0x1a` loop-iter | `0x54` | 256 | 0 | 0 | 1 | 256 |
| `cf_nl2` +140 | `0x25` | `0x54` | 256 | 0 | 0 | 1 | 256 |

**Observed.** At `cf_nl2+106` the split is exact and reproduced in both runs (122 values common to
both runs at the time of writing, **122/122 identical**): every value with bit 1 set is correct,
no value with bit 1 clear is. Two of the bit-1-clear values (12, 57) return the *sentinel-only*
payload — the program ran, wrote the pre-region sentinel, and left all 32 value words at their
poison — instead of faulting.

**Interpretation, bounded.** The `0x54`/`0x56` "nesting parity" claim in `db.json` is a **real
constraint**, not an annotation — but only in one direction and only at one of the three
loop-iteration pushes tested. **Both pre-registered models are refuted**: M2 (EXP-0188's literal
"bit 1 must be set at a loop-iteration push") fails at `cf_nl3+182` and `cf_ifnl+126`, and M1
("bit 1 must match the compiled bank") fails there too, because those occurrences accept *both*
polarities. The surviving description — *bit 1 is load-bearing exactly where the compiler set it*
— is **post-hoc** and is offered only as a hypothesis for a successor to pre-register.

**Why EXP-0184 saw nothing** is now clear and is *not* only the region kind: it is the region kind
**and** the compiled bank. Reaching `scope_kind == 0x1a` is necessary and not sufficient.

**The two masked-lane cases matter.** They are the payload a wrong reconvergence bank should
produce, and against a zero-initialised read-back buffer they would have been indistinguishable
from a silent zero. This is the poisoned-buffer instrument doing exactly its job.

### 2.2 `pop_reconverge.scope` (start 16, width 8) — **accepted-inert in the tested envelope**

Three occurrence classes, 256 values each, both runs: **768 of 768 correct in each run, one
distinct valid payload, zero hard outcomes.** The occurrences span loop-body (`scope_kind 0x02`,
compiled `0x04`), guard/outermost (`scope_kind 0x01`, compiled `0x04`) and call-reconvergence
(`scope_kind 0x02`, compiled **`0x24`** — the other documented bank, compiler-emitted). The
detection-power control (`scope_kind` at the same occurrence) **fires at all three**.

`M3_inert` is the sole surviving model. Both bank models are refuted: `M1_bank_bit5` (correct iff
bit 5 matches the compiled bank) and `M2_low_nibble` (correct iff `v & 0xF == 4`) each miss.

> **Safe negative wording:** *inert over 0..255 dense at three occurrence classes on two carriers,
> with the same-word control firing at each; global role unknown.* Note that this falls one
> carrier short of §7's "three structurally different carrier classes" — it is three *context*
> classes on two carriers.

### 2.3 `pop_reconverge.reserved` (start 32, width 16) — **LIVE: the low byte is load-bearing**

| occurrence | compiled | correct | different-but-coherent | V | L |
|---|---|---:|---:|---:|---:|
| `cf_ifnl` +184 (`0x24` bank, if/else on the **lane id**) | 0 | **9** | **43** | 2 | 52 |
| `cf_nl2` +216 | 0 | 52 | 0 | 1 | 52 |
| `cl_atomic` +66 | 0 | 0 | 0 | 1 | 52 |

**Observed at `cf_ifnl+184`, with no exceptions in the sampled set:**

* the **9** correct values are exactly `{0x0000, 0x0100, 0x0200, 0x0400, 0x0800, 0x1000, 0x2000,
  0x4000, 0x8000}` — i.e. **every sampled value whose low byte is zero**, spanning **9 distinct
  high-byte values** `{0,1,2,4,8,16,32,64,128}`;
* the **43** values with a non-zero low byte all produce **one identical wrong payload**.

**Interpretation.** `db.json` models bits 32..47 as a single 16-bit `reserved` field of type `mod`.
That model is wrong: **byte+4 (bits 32..39) is a live operand that must be zero** on this envelope,
and **byte+5 (bits 40..47) is inert over the 9 high-byte values tested**. Recorded under
`db_defects` in `analysis/field_verdicts.json`; `db.json` is not edited.

**Why two of three arms saw nothing.** `cf_ifnl` branches on the **lane id**, so a reconvergence
error surfaces as the wrong *lanes*; the loop carriers' divergence is largely uniform across the
threadgroup and cannot express it. That is a detection-power difference between arms, not a
liveness difference between occurrences — precisely the failure mode
`RE_EXPERIMENT_PROCESS_CORRECTIONS` Gate B exists to name. The two null arms are therefore reported
as **`carrier-undecidable` for this dimension**, not as evidence of inertness.

No pre-registered model survives: `M1_inert` misses the 43 coherent cases, `M3_any_live` misses the
9 correct ones. The refined model (*low byte must be zero*) is **post-hoc**.

### 2.4 `call.tail` (start 104, width 8) — **accepted-inert in the tested envelope; NOT a global claim**

Three carriers × 256 values × 2 runs: **all correct, one distinct valid payload, zero hard
outcomes, ledger clean.** `M1_inert` is the sole surviving model; `M2_exact` and `M3_low_bit` are
refuted.

The carriers differ in callee structure — `cl_leaf` (leaf callee), `cl_chain` (**non-leaf** callee
`c_mid`, which itself calls two leaves), `cl_atomic` (callee performing an atomic RMW and returning
through a real `ret_luse`) — which is the axis EXP-0179 lacked when its two carriers *shared a
generated leaf callee*. Detection-power controls at the same occurrences fire: `call.b6` produces
2 distinct valid payloads at `cl_leaf` and 3 at `cl_chain`, and the `call.offset` perturbation
produces a valid↔hard split at every call site.

**Second method (independent of the sweep):** a compiler differential over our own shaders —
`call.tail` is `0x00` in **8 of 8** compiled call sites across nine authored kernels. The compiler
never varies it.

> **Limitation, stated because §5 Phase 5 requires it:** all three carriers share **one observation
> path** (32 per-lane words at fixed addresses). They differ in the callee dimension but not in how
> the result is read back. The honest reading is *accepted-inert over 0..255 dense on three callee
> structures with the same read-back plan*, not *globally inert*.

**A finding against the prior record.** EXP-0179 arm S concluded `call.b6` bit 1 is load-bearing and
*must be set*, giving an encodable range of 128. Our own compiler emits `b6 = 0x54` (**bit 1
clear**) for both calls inside `c_mid`, and the b6 control accepts several bit-1-clear values at
`cl_leaf` and is **completely inert over all 16 sampled values at `cl_atomic`**. The rule is
carrier-dependent, not universal. Recorded under `db_defects`.

### 2.5 `ret.scoreboard` (start 24, width 8) — **accepted-inert across the ORDERING dimension**

Four occurrences × 256 values, **1024 of 1024 correct, one distinct valid payload per arm, zero
hard outcomes**:

| carrier | what is outstanding at the `ret` | result |
|---|---|---|
| `cl_pure` | **nothing** — the callee has no memory access at all | 256/256 correct |
| `cl_ldret` | a device **load inside the callee**, its value returned | 256/256 correct |
| `cl_stacross` | a **store→load hazard spanning the return** (caller stores, calls, reads back) | 256/256 correct |
| `cl_chain` | a **non-leaf** return (`linkmode 0x12`) with a saved link | 256/256 correct |

EXP-0179 declined this field with the exact words *"neither carrier differs in that dimension —
both return from a leaf callee with no outstanding asynchronous operation to wait on. Zero movement
here therefore means 'this carrier cannot ask the question'."* **The question has now been asked.**
The `ret.linkmode` control fires at every one of the four occurrences (4 valid / 12 hard over 16
values).

`M2_inert` survives 1024/1024. `M1_wait_mask` also "survives", but **uninformatively**: as written
it makes no prediction off the compiled value on the hazard carriers, so it cannot be refuted
there. The informative statement is M2's.

> **Safe negative wording:** *inert over 0..255 dense at four occurrences spanning
> nothing-outstanding → load-in-callee → store→load-across-the-return → non-leaf-frame, with the
> same-word control firing at each; global role unknown.*
>
> **What is still untested:** a genuine multi-invocation ordering litmus (corrections §5 Phase 3:
> *"for synchronization, use a real multi-invocation ordering litmus; scalar success cannot assign
> ordering semantics"*). Every carrier here is single-threadgroup and each lane touches only its
> own word. If the scoreboard governs *inter-lane* or *inter-threadgroup* ordering, these carriers
> still cannot see it.

### 2.6 `ret_luse.linkmode` (start 8, width 8) — **LIVE, 2 distinct valid payloads: EXP-0192's Case C is cleared**

| occurrence | kind | accepted (`v&3==2`) | correct | different-but-coherent | fault | V |
|---|---|---:|---:|---:|---:|---:|
| `cl_chain` `c_mid`+104 (synthesized `0x54`→`0x56`) | **NON-LEAF**, has a `link_save_restore` pair | 64 | **32** (bit 4 **set**) | **32** (bit 4 **clear**) | 190 | 3 |
| `cl_leaf` `lf_add`+30 (synthesized) | leaf | 64 | 64 | 0 | 192 | 1 |
| `cl_atomic` `m_at`+32 (**real**, compiler-emitted `8f 12 56 00`) | leaf-with-atomic, **no** link save | 64 | 64 | 0 | 192 | 1 |

**Observed.**

1. The accepted set is **`v & 3 == 2` — 64 of 256** — identically at all three occurrences, and
   identically for the plain `ret` (`byte+2 = 0x54`) via its own control arm. **EXP-0156's
   `v & 7 == 4` rule does not hold on G17P**; `0x04` and `0x05`, which `db.json` lists as
   `cf_merge` / `cf_merge_push`, **fault** here.
2. Within the accepted set, at the **non-leaf** return, the 32 values with **bit 4 (0x10) set** are
   correct and the 32 with bit 4 **clear** produce **one identical, deterministic, non-faulting
   wrong result**. The `ret.linkmode` control at the same offset reproduces it exactly:
   `{0x12, 0x1a, 0x56}` correct, `0x02` coherent-wrong, everything else faults.
3. At both **leaf** returns, all 64 accepted values — bit 4 set *and* clear — are correct.

**Interpretation.** Bit 4 is the **restore-link** flag, and it is load-bearing exactly where a link
was actually saved: `c_mid` carries `link_save_restore` around its calls, `lf_add` and `m_at` do
not. Bits 2, 3, 5, 6 and 7 are don't-cares over the tested envelope. This is the
`0x02 leaf` / `0x12 nonleaf_restore_link` semantic in `db.json`, now **directly observed on G17P
with a controlled comparison**, and it is the **two distinct valid payloads** that EXP-0192 said
were missing.

**No pre-registered model survives.** `M1_link` keyed on the *compiled* `linkmode` rather than on
whether a link was saved, so it mispredicts at `cl_atomic` (compiled `0x12`, yet `0x02` is
correct). `M2_accepted_set` is refuted as above. The refined model — *`v & 3 == 2` to be accepted;
bit 4 = restore-link, load-bearing iff a `link_save_restore` pair is present* — is **post-hoc**,
and under Gate C that caps the semantics axis at `hypothesis`. A successor that pre-registers it
can close this field.

**Bonus observation.** The `ret_luse.tail` / `ret.scoreboard` byte (byte+3) is inert over all 16
control values at every occurrence, consistent with §2.5.

### 2.7 `stop.reserved` (start 8, width 24) — **accepted-inert at BOTH stop positions, with the positive control firing**

| arm | carriers | values | result, **both runs** | control |
|---|---|---:|---|---|
| final stop | `cf_nl2`, `cl_leaf`, `cl_atomic` | 73 each | **73/73 correct**, one payload | byte 0: **6/8 harmless, 2/8 fault** — **fires** |
| synthesized **mid-program** stop | `cl_leaf`, `cl_chain` | 73 each | **73/73 sentinel-only** (program terminates; all 32 value words still poison), one payload | whole word: `0e 00 00 00` terminates, original frame marker and all-zeros do not — **fires** |

**The termination-dimension positive control the protocol demands now exists, and it fired in both
directions.**

1. **A mid-program `stop` genuinely terminates.** Constructed by overwriting the 4-byte
   `frame_marker` — an instruction EXP-0179 established is **optional**, so the only semantic change
   is the presence of a terminator — the program writes its pre-region sentinel and nothing else,
   identically in both runs on both carriers.
2. **The final `stop` word is executed.** Replacing byte 0 with a control-flow leader — `0x0f`
   (the `if_push`/`call`/`pop` leader) or `0x8f` (the `ret` leader) — **faults reproducibly on all
   three carriers in both runs**, while `0x00`, `0x01`, `0x0c`, `0x0d`, `0x2e` and `0xff` leave the
   program fully correct.

This **bounds** `db.json`'s claim, inherited from EXP-0003/EXP-0010, that *"corrupting any of it is
a no-op"*: that is true for the byte values previously tried and false for a branch/return leader.
The driver rule `emit 0x000000` is unaffected and is reconfirmed.

`M1_inert` is the sole surviving model over 730 gated cases (438 final + 292 mid-program).

> **Safe negative wording:** *inert over 73 of 2^24 values (protocol §3 sampling for w > 8:
> boundaries, every single-bit value, every single-bit hole, and 23 asymmetric interior samples) at
> two stop positions on three carrier classes, with a termination-dimension positive control firing
> at each; global role unknown.*

---

## 3. Verdicts, on the six independent axes

`analysis/field_verdicts.json` carries these machine-readably, keyed `<mnemonic>.<field>`, with the
per-arm axis values, exact counts, hard-outcome counts kept separate, the per-model
hit/checked tallies, and the `db_defects` block. Summary:

| field | geometry | liveness | semantics | recipe | target | reproducibility | proposed legacy label |
|---|---|---|---|---|---|---|---|
| `if_push.scope` | geometry-mapped | **live** (1 of 4 occ) / accepted-inert (3 of 4) | hypothesis — both models refuted | not-generated | G17P-direct | INCOMPLETE (Gate E) | `untested` |
| `pop_reconverge.scope` | geometry-mapped | accepted-inert | bounded-map (`M3_inert`) | not-generated | G17P-direct | INCOMPLETE (Gate E) | `untested` |
| `pop_reconverge.reserved` | geometry-mapped | **live** (1 of 3) / carrier-undecidable (2 of 3) | hypothesis — both models refuted | not-generated | G17P-direct | INCOMPLETE (Gate E) | `untested` |
| `call.tail` | geometry-mapped | accepted-inert | bounded-map (`M1_inert`) | not-generated | G17P-direct | INCOMPLETE (Gate E) | `untested` |
| `ret.scoreboard` | geometry-mapped | accepted-inert | bounded-map (`M2_inert`) | not-generated | G17P-direct | INCOMPLETE (Gate E) | `untested` |
| `ret_luse.linkmode` | geometry-mapped | **live**, 2 distinct valid payloads | hypothesis — both models refuted | not-generated | G17P-direct | INCOMPLETE (Gate E) | `untested` |
| `stop.reserved` | geometry-mapped | accepted-inert, control firing | bounded-map (`M1_inert`) | not-generated | G17P-direct | INCOMPLETE (Gate E) | `untested` |

**Why every legacy label is `untested` rather than rounded up.** `PRE_REGISTRATION_A2.md` §A2.6
caps the legacy label by the semantics axis, per Gate C: *`sem_checked == 0` or no surviving
pre-registered model can never produce `hardware-run`*. Three fields have live behaviour whose
explanatory model is post-hoc, and four read inert with a surviving *inertness* model — which is
liveness plus a null, not a semantic map. The orchestrator may reasonably promote the four inert
rows to `hardware-run` **within their exact stated envelopes**; this experiment does not do it on
its own authority, because **Gate E is unmet wave-wide** and the reproducibility axis is
`INCOMPLETE` on every row.

---

## 4. Limitations, and how this method could have failed to say "no"

1. **The machine was never quiet, and Gate E is unmeetable wave-wide.** 8–21 sibling GPU
   processes throughout. Gate E's "two clean runs" was met in *form* (two runs in different case
   orders, ledgers identical, agreement computed only over values valid in both) but not in
   *quiet*. The defence is the poisoned buffer, the sentinel, majority-of-3, `InnocentVictim`
   retries, and the offline adjudication that contamination lands overwhelmingly on the fault
   cases. **Every row reads `reproducibility: INCOMPLETE - Gate E not met`.** A serialized quiet
   confirmation is owed.
   Relatedly, and worth carrying forward: EXP-0201 found that across 40,156 cases *every*
   cross-run disagreement was a `fault` ⟷ `wrote-nothing` flip inside one pre-registered fault
   class, and adjudicated agreement was 100.00%. Much of this family lives on a fault boundary, so
   hard outcomes are partitioned out of the payload set before anything is called unstable — which
   is why no arm here is reported as unstable.
2. **A shared observation path.** Every arm reads back 32 per-lane words at fixed addresses plus a
   sentinel and a poison tail. That satisfies Gate B (the observable cannot co-vary with the swept
   field) but means a hidden effect invisible to *that* plan is invisible to *every* arm here. It is
   the one dimension in which all 15 carriers count as one method.
3. **Inertness is bounded by detection power, and this experiment demonstrated that on itself.**
   `pop_reconverge.reserved` reads inert on two arms and live on a third that differs only in
   whether divergence depends on the lane id. Any of the four "accepted-inert" verdicts above could
   be the same mistake with a carrier we did not build. That is why none is written as `unused` or
   `don't-care`.
4. **Post-hoc models are labelled post-hoc.** Three fields moved in ways no pre-registered model
   predicted. The refined rules in §2.1, §2.3 and §2.6 are stated as hypotheses for a successor to
   pre-register, not as results of this experiment.
5. **No compiler recipe was generated.** Every case mutates one field of our own compiled carrier.
   The `compiler_recipe` axis is `not-generated` for all seven fields, by construction.
6. **`wave_audit.py` run over the whole experiment directory reports inflated `V` and ~0%
   cross-run agreement**, because it globs every run under `raw/` and keys on `(instr, field)`.
   Pooled that way it mixes the census/pilot/smoke/killed-run01 captures with the gated pair, and
   mixes carriers whose *correct* answers legitimately differ. `analysis/gated_view.py` builds a
   gated-pair-only view and a per-arm view; both outputs are quoted in §5, neither is hidden.
7. **`ret.scoreboard` still has no multi-invocation litmus** (§2.5).
8. **The `if_push.scope` bit-1 result rests on one occurrence.** Three others accept both
   polarities. A successor should sweep every `0x56`-compiled push in the corpus before the rule is
   trusted.

## 5. Audit outputs

* `analysis/gate206.json` — per-arm and per-field, recomputed from raw.
* `analysis/field_verdicts.json` — the proposed verdicts, six axes, exact counts, `db_defects`.
* `analysis/report_tables.py` — the per-arm tables above.
* `analysis/wave_audit_all.txt`, `analysis/wave_audit_gated.txt` — `tools/agx-isa/wave_audit.py`
  over the whole directory and over the gated-pair-only view, both retained.

## 6. Recommended next experiments

1. **Pre-register the `ret`/`ret_luse` `linkmode` map** (`v & 3 == 2` accepted; bit 4 = restore-link,
   load-bearing iff a `link_save_restore` pair is present) and confirm it on a quiet machine with a
   carrier ladder of 1/2/3 nested non-leaf frames. This is the closest field to closure.
2. **Sweep `pop_reconverge.reserved` byte+4 densely (0..255) on lane-dependent carriers**, and
   sweep byte+5 densely too. The split into two fields should be confirmed before `db.json` changes.
3. **Sweep every `0x56`-compiled `if_push` in the corpus**, and pair each push with its matching
   pop, to test whether the constraint is "push bank must match pop bank".
4. **A multi-invocation ordering litmus for `ret.scoreboard`** — two threadgroups, cross-lane
   dependencies, and a real happens-before check.
5. **A serialized quiet-window confirmation** of all seven fields once the fan-out drains — the
   only thing standing between the four inert rows and a promotable label.
6. **A descriptor for `ef 02 54 00 00 50`**, the non-leaf epilogue. Until it exists, every
   experiment that locates instructions by a linear walk silently loses every non-leaf frame.

## 7. Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected:      kernels/k_cf206.metal, kernels/k_cl206.metal -- authored by us -- and
                       the AGX bytes the public Metal runtime compiled from them
Apple binary introspection: NONE
Reproduction:          README.md -> Reproduction
Evidence:              raw/g17p_20260830_run03/, raw/g17p_20260830_run04/,
                       raw/prefreeze/census.json, CAPTURE_CONTRACT.json, manifest.json
```

No Apple binary was disassembled, decompiled, symbol-dumped or otherwise introspected. Every byte
inspected or mutated is the compiled form of MSL in `kernels/`, written by us.
