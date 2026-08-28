# RESULTS — EXP-0089 M4 register-lifecycle model (successor to EXP-0086)

## Evidence status (read this first)

**Both contracted runs are complete: `raw/m4-lifecycle-20260828-run01` and
`raw/m4-lifecycle-20260828-run02`, 549/549 cases each**, `verify.py
--selftest` (16/16) and `--seqtest` (14/14) passed before each capture,
`--preflight`/`--between-runs` passed live at capture time.

**The strict `verify.py --captured` gate (full 549-line byte-identical
cross-run comparison) FAILS**, and this is reported honestly rather than
forced or hidden: `FAIL byte-exact gated repeat`. The cause is fully
characterized, not a mystery — **8 of 549 lines (1.5%) differ between the two
independent runs, and all 8 are inside the NEW exploratory `CTRL_SWEEP` census
(item 4), none in CAND_A/CAND_B/BASELINE/positive-control/LIT17/DISCRIM**.
Directly verified (`verify.py`'s own `static()`+`one_run()` checks, run
standalone): both runs are individually well-formed, authored-source-hash
provenance is identical between runs, and the *only* failing check is the
gated-file byte-identity comparison. This is itself a first-class finding,
precisely responsive to item 4's own question ("check whether \[intermittency\]
holds here") — see §4.

**Consequently this report distinguishes two closure levels**:

- **CLOSED, 100% two-run-clean (541/549 lines, all non-CTRL_SWEEP cases)**:
  EXP-0086's original CAND_A/CAND_B/baseline/positive-control design on the 7
  carried-over kernels, PLUS the two new LIT17 kernels and the new DISCRIM3
  kernel. Every one of these lines is byte-identical across two independent
  full runs, on top of 3/3 identical fresh-process repeats within each run
  (0 intermittent case-groups outside `CTRL_SWEEP`). This is the formal
  two-run gate item 1 of the dispatch asked for, and it is met for this scope.
- **NOT two-run-clean (8/336 CTRL_SWEEP lines)**: 3 case-groups showed
  intra-run intermittency (disagreement among the 3 fresh-process repeats
  *within* `run01` itself) and a further 5 case-groups (a superset containing
  those 3 plus 2 more) showed cross-run disagreement. All 8 are confined to 4
  specific `(kernel, site, mask)` combinations, always mask `0x01` or `0x02`
  on `adjacent`/`if_boundary`. This is reported as a genuine hardware finding
  (§4), not swept under the rug, and the `--captured` gate is left FAILING
  rather than the contract being edited after the fact to exclude it.

All findings below are **HW-VALIDATED** (splice-and-observe on real M4
hardware, 3 fresh-process repeats per case per run, two independent full
runs) unless stated otherwise. Target: **M4/G16G only**; not promoted to
G17P without a recorded validation (per `CLAUDE.md`).

---

## Verdict on each of the five dispatch items

### 1. The formal two-run gate

**MET for the decisive claims; NOT MET for the full matrix — see above.**
EXP-0086's own scope (CAND_A/CAND_B/baseline/positive_control_c2 on the 7
kernels: `adjacent`/`near`/`far4`/`far16`/`pressure`/`if_boundary`/
`loop_boundary`) is now formally closed under a fresh contract, fresh run
ids (`m4-lifecycle-20260828-run01`/`run02`, distinct from EXP-0086's own
`m4-20260828-run01`/`run02` — EXP-0086's files were not touched, reused, or
repaired), and fresh hashes. Both runs reproduce EXP-0086's `run01` finding
exactly and reproduce EACH OTHER exactly for this scope: `candB_flip_c1`/
`candB_flip_both` corrupt the target output on **all 7 kernels** (not just
`adjacent`), `candA_flip_*` is null on all 7, `positive_control_c2` detects a
deviation on all 7 original kernels. See item 3 for the generalization detail.

### 2. The literal bit 17

**HW-VALIDATED, in two independent instruction families, both corrupt.**
`docs/isa/README.md:770`'s literal `0x54<->0x56` field (byte+2 bit 1,
instruction bit 17) was located in two families where `tools/agx-isa/db.json`'s
own `match` table proves the bit is genuinely free (not opcode-determining,
unlike every family EXP-0086 could reach): `unpack_convert` (`cache` field)
and `cvt_i2f` (`mode` field). Kernels `lit17_unpack.metal`/`lit17_cvt.metal`
each get the compiler to emit TWO separate instructions reading the SAME
source register (defeating CSE by using two different MSL builtins/casts on
the identical source value), reproducing the doc's claimed natural polarity
exactly: first/earlier reader `0x56` (bit17=1), second/later reader `0x54`
(bit17=0).

| kernel | case | splice | out (3/3 reps, both runs identical) | expected | verdict |
|---|---|---|---|---|---|
| `lit17_unpack` | baseline | — | `0.50000763, 6.0000305` | same | MATCH |
| `lit17_unpack` | `lit17_flip_c1` (c1 `0x56`->`0x54`) | `@0x14: 56->54` | **`0, 5`** | `0.5.., 6.0..` | **MISMATCH** |
| `lit17_unpack` | `lit17_flip_c2` (c2 `0x54`->`0x56`) | `@0x1c: 54->56` | `0.50000763, 6.0000305` | same | MATCH |
| `lit17_unpack` | `lit17_flip_both` | both | **`0.50000763, 5`** | `0.5.., 6.0..` | **MISMATCH** |
| `lit17_cvt` | baseline | — | `1244, 1254` | same | MATCH |
| `lit17_cvt` | `lit17_flip_c1` | `@0x14: 56->54` | **`10, 20`** | `1244, 1254` | **MISMATCH** |
| `lit17_cvt` | `lit17_flip_c2` | `@0x1c: 54->56` | `1244, 1254` | same | MATCH |
| `lit17_cvt` | `lit17_flip_both` | both | **`10, 1254`** | `1244, 1254` | **MISMATCH** |

**Observed**: flipping the LITERAL bit 17 on the EARLIER/producer instruction
(`lit17_flip_c1`) corrupts the shared source to read as **zero** — matching
CAND_B's exact failure signature — in BOTH independent families, fully
deterministic (6/6 repeats across both runs, all cross-run-identical, none of
these lines are in the 8-line diff set). Flipping only the LATER/consumer
instruction's bit (`lit17_flip_c2`) is a no-op in both families, matching
CAND_B's polarity finding (the "claim reuse when none is pending" direction
on the producer is what's dangerous).

**New signature not seen in EXP-0086's CAND_B**: `lit17_flip_c1` corrupts
**both** the flipped instruction's OWN result (`lit17_unpack`'s `x1` reads
`0` instead of `0.5..`; `lit17_cvt`'s `x1` reads `10` instead of `1244`) **and**
the separate later instruction's result. CAND_B (`opflags` bit0 on `falu2i`)
never corrupted the flipped instruction's own output in EXP-0086 or in this
experiment's re-run. This is direct evidence the LITERAL bit-17 field and
the CAND_B `opflags` bit are **not the same mechanism**, even though both
are in the "source cache / last-use" conceptual family and both corrupt via
the same "reads as zero" failure mode. A plausible (not proven) reading: the
literal bit governs whether the CURRENT instruction fetches its own operand
fresh from the register file vs. from a bypass/forward path (so a wrongly
claimed "reuse" corrupts the current op's own read, consistent with
`fspecial`'s db.json framing "0x56 fresh (operand)"), while `opflags` bit0
governs something more downstream (consistent with a producer-side
writeback-suppression role, see item 5).

**`flip_both` is family-asymmetric** (both directions HW-confirmed,
deterministic, reproduced cross-run): `lit17_unpack`'s `flip_both` RECOVERS
`x1` to correct while `x2` stays corrupted; `lit17_cvt`'s `flip_both` leaves
`x1` corrupted while `x2` RECOVERS to correct. This is reported as an
observed fact, not explained by a single clean model — see limitations.

**Positive-control limitation (honest downgrade)**: `positive_control_c2`
for BOTH `lit17_unpack` (raw-byte redirect of the presumed source-register
byte+4, `0x01->0x02`) and `lit17_cvt` (field-based redirect of `src`,
`4->5`) **matched baseline exactly** (`MATCH_EXPECTED`, 3/3 reps, both runs) —
the detection-capability proof FAILED for these two kernels specifically
(overall `positive_control` score: **7/9** kernels detected, the 2 misses
being exactly the 2 new lit17 kernels). Per this experiment's own
pre-registered rule, this downgrades the `lit17_flip_c2` NULL result to
`UNKNOWN` rather than `PASS` for these two kernels specifically — **the
`lit17_flip_c1` corruption finding itself is unaffected** (a directly
observed value change needs no separate detection-capability proof). The
splice mechanism is confirmed working (the byte/field DID change, verified
in the raw record); either register `2`/`5` coincidentally held the same
value at that point, or the byte+4/`src` fields are not exactly what this
experiment hypothesized (a companion field may also need to change, or the
addressed register space differs from assumed). **Open question, not
resolved by this experiment.**

**Structural finding on `falu_acc`**: `tools/agx-isa/db.json`'s own `match`
table for `falu_acc` fixes bits 17-20 to `0b1100` — i.e. **bit 17 is
opcode-determining in `falu_acc` too**, confirming (by direct table
inspection, not just failed compilation attempts as in EXP-0086) that this
family could never have tested the literal bit either way. `falu_acc`'s own
`cache` field is bit 21 (byte+2 bit 5), not bit 17.

### 3. CAND_B sweep across conditions

**Universal in the sense that `candB_flip_c1`/`candB_flip_both` corrupt the
target output in ALL 7 kernels — but the SCOPE and symmetry of the
corruption is condition-dependent, diverging sharply for `loop_boundary`.**

| kernel | distance/condition | `candB_flip_c1` | `candB_flip_c2` | `candB_flip_both` |
|---|---|---|---|---|
| adjacent | 0 intervening instrs | corrupts idx1 (`27.5`->`20`) | null | = flip_c1 |
| near | 1 intervening instr | corrupts idx1 | null | = flip_c1 |
| far4 | 2 intervening instrs | corrupts idx1 | null | = flip_c1 |
| far16 | ~25 intervening instrs | corrupts idx1 | null | = flip_c1 |
| pressure | ~40 live values | corrupts idx1 | null | = flip_c1 |
| if_boundary | real runtime `if` boundary | corrupts idx0 (`17.5`->`10`) | null | = flip_c1 |
| **loop_boundary** | real runtime `for` loop, c1 is the 12-byte extended `falu_srcmod12b` form, EXECUTED 3x inside the loop | **corrupts ALL THREE indices** (`17.5,27.5,624`->`10,20,609`) | **ALSO corrupts idx1** (`27.5`->`20`) — the ONLY kernel where the consumer's own bit matters | = flip_c1 |

**Observed**: 6/7 kernels reproduce EXP-0086's `adjacent` finding exactly —
only the target (`c2_out_idx`) is corrupted, the producer's own bit alone
decides, consumer's bit alone is null, `flip_both` == `flip_c1`. This is
100% deterministic across 3 in-run repeats and both independent runs for
every one of these 6 kernels (none in the 8-line cross-run diff set).

`loop_boundary` diverges on **both** axes the task asked to check: (a) the
corruption is NOT confined to the single "next" reader — the loop
accumulator (`acc`, a THIRD, repeatedly-computed value) is also wrong, and
(b) the consumer's OWN bit, alone, now also corrupts (`candB_flip_c2` alone:
idx1 wrong, idx0/idx2 correct) — a genuinely different sub-pattern from
`candB_flip_c1`'s (all three wrong). **Interpretation, not fully resolved**:
`loop_boundary`'s `c1` is both (i) inside a real, runtime-trip-count loop
(the same physical instruction executes 3 times) and (ii) a structurally
different, 12-byte extended instruction form (`falu_srcmod12b`) rather than
the 6-byte `falu2i`/`falu2` form every other kernel's `c1`/`c2` use. This
experiment cannot separate which of those two factors (loop repetition vs.
instruction-form difference) drives the broader corruption — both are
plausible and neither is excluded. **No intermittency**: `loop_boundary`'s
CAND_B rows are fully deterministic (6/6 reps across both runs).

**Refuter check**: the pre-registered null-result condition (a kernel where
`candB_flip_c1` matches baseline) never occurred — CAND_B never showed a
genuine negative in any of the 7 tested conditions. `positive_control_c2`
detected a deviation in 7/7 of the original kernels, so these nulls
(`candB_flip_c2`, `candA_flip_*`) are interpretable, not harness-blind.

### 4. `ctrl`/`ctrl_lo` characterization

**A clean, mostly bit-position-consistent map for the compact 6-byte form,
sharply different for the 12-byte extended form — plus a genuine
intermittency finding.**

8-value XOR sweep (`0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x7f`) applied to BOTH
`c1` and `c2` across all 7 kernels (112 case-groups, `run01`):

| bit (mask) | fault | mismatch | safe | note |
|---|---|---|---|---|
| bit0 (`0x01`) | 9/14 | 5/14 | 0/14 | always dangerous |
| bit1 (`0x02`) | 7/14 | 7/14 | 0/14 | always dangerous; **source of ALL 8 cross-run-nondeterministic lines** |
| bit2 (`0x04`) | 1/14 | 0/14 | **13/14** | safe except `loop_boundary`/c1 (12-byte form: **genuine GPU HANG**, `NO_STATUS`, full 60s timeout) |
| bit3 (`0x08`) | 1/14 | 12/14 | 1/14 | almost always corrupts (silently) |
| bit4 (`0x10`) | 1/14 | 0/14 | **13/14** | safe except `loop_boundary`/c1 (`CMDBUF_ERROR`) |
| bit5 (`0x20`) | 0/14 | **14/14** | 0/14 | ALWAYS silently corrupts, never faults |
| bit6 (`0x40`) | 0/14 | **14/14** | 0/14 | ALWAYS silently corrupts, never faults |
| all (`0x7f`) | 1/14 | 13/14 | 0/14 | dangerous (union of the above) |

**Observed, by kernel/site (13/14 non-`loop_boundary`/c1 "safe" cells span
bits 2 and 4 only; `loop_boundary`/c1 is 0/8 safe — every tested value there
is fault or mismatch)**: for the 6-byte `falu2i`/`falu2` compact form, bits 2
and 4 of the 7-bit `ctrl`/`ctrl_lo` field are safe/inert in 13 of the 14
tested (kernel x site) contexts (the sole exception in each is `if_boundary`
which is safe at bit3 too, `c1` only — the single case in the bit3 "safe"
column). Bits 0, 1, 3, 5, and 6 are load-bearing everywhere tested — either
they fault the command buffer or silently change the output, with bit5/bit6
being the cleanest ("always corrupts, never faults") and bit0/bit1 the most
volatile (see intermittency below).

`loop_boundary`'s `c1` (the 12-byte extended `falu_srcmod12b` form, executed
inside a real loop) is qualitatively different: **every one of the 8 tested
values either FAULTS or MISMATCHES; none are safe**, including a genuine
**HANG** (bit2, `0x04`: `NO_STATUS`, needed the full 60s per-case timeout to
resolve, 3/3 reps — contained, no host wedge, but a materially different
failure class from EXP-0086's fast `CMDBUF_ERROR`s). This is reported as-is;
this experiment cannot determine whether the danger is because this specific
bit-position means something different in the 12-byte form, or because
executing the mutated instruction inside a real loop (3x) is what makes an
otherwise-survivable single-shot corruption fatal.

**Intermittency (a genuine, first-class finding, unlike everything else
tested here and in EXP-0086)**: 3 of the 112 `ctrl_sweep` case-groups showed
DISAGREEING verdicts among their own 3 fresh-process repeats within `run01`
(`adjacent ctrl_sweep_c1_b02`: `FAULT,FAULT,MISMATCH`; `adjacent
ctrl_sweep_c2_b02`: `FAULT,MISMATCH,FAULT`; `if_boundary ctrl_sweep_c2_b01`:
`FAULT,MISMATCH,MISMATCH`). A further 2 case-groups agreed within `run01`
but disagreed against `run02` (`adjacent ctrl_sweep_c2_b04`, 2/3 reps:
`run01` MATCH `17.5,27.5` vs `run02` MISMATCH `0,0` — the SAME splice byte
giving a CORRECT answer in one process launch and a WRONG one in another;
`far16 ctrl_sweep_c1_b7f`, 2/3 reps: both runs MISMATCH but with two
DIFFERENT wrong sum values, `17802.133`/`16775.623` vs `13669.634`/
`17802.133`). **All 8 non-reproducible lines involve only bit0 or bit1
(`0x01`/`0x02`), only on `adjacent`/`if_boundary`, only at the c1/c2
boundary near the small-distance kernels.** This is a genuinely different
character of result from every CAND_A/CAND_B/LIT17/DISCRIM case in this and
the prior experiment (135 + 549 - 8 = 676 case executions with ZERO
intermittency) and from the rest of the `ctrl_sweep` census itself (108/112
case-groups fully deterministic, both within-run and cross-run). The most
plausible reading is that bit0/bit1 push the hardware into a genuinely
racy/undefined state (plausibly close to a scoreboard/hazard boundary) for
these two specific low-register-pressure kernels, rather than any
Heisenbug in the harness (`inert_control`-style methodology point: this
non-determinism is confined to a specific, small subset of a specific
field, not smeared across the dataset).

### 5. Producer/consumer discriminating case

**Decisive, in favor of a persistent "producer fails to commit the value"
model over a one-shot bypass/forwarding-cache model, and directly ruling out
any backward/earlier-reader effect.**

`discrim3.metal` (`v+10, v+20, v+30`; natural CAND_B pattern `x1=0,x2=0,x3=1`
— an honestly-reported non-alternating pattern, see `PRE_REGISTRATION.md`
§5):

| case | x1 (idx0) | x2 (idx1) | x3 (idx2) | verdict |
|---|---|---|---|---|
| baseline | `17.5` | `27.5` | `37.5` | MATCH |
| `discrim_flip_x1` (x1's bit 0->1) | `17.5` (unaffected) | **`20`** (corrupted) | **`30`** (corrupted) | MISMATCH idx1+idx2 |
| `discrim_flip_x2` (x2's bit 0->1) | `17.5` (unaffected) | `27.5` (unaffected — self-read fine) | **`30`** (corrupted) | MISMATCH idx2 only |
| `discrim_flip_x1_x2` (both) | `17.5` | `20` | `30` | = flip_x1 |
| `discrim_flip_x3` (x3's bit 1->0, adversarial control) | `17.5` | `27.5` | `37.5` | MATCH (null, as predicted) |

All 4x2=8 case-groups fully deterministic (3/3 reps, both runs identical,
none in the 8-line diff set).

**What this discriminates**:

1. **Causality (H5, refuter test)**: in NO case does corruption reach a
   reader SCHEDULED BEFORE the flipped instruction — `x1` is untouched in
   both `discrim_flip_x1`... (trivially, it IS the flipped instruction and
   reads its own value correctly, matching every other "producer's own read
   is fine" observation in this dataset) and, decisively, in
   `discrim_flip_x2` (`x1`, scheduled and EXECUTED before `x2`, stays
   correct while `x2`'s bit is the one flipped). **H5 survives**: no
   backward-in-schedule effect was observed anywhere in 8 case-groups x 2
   runs. This rules out any model requiring symmetric/bidirectional
   agreement or a global "poison" that isn't strictly forward-propagating.
2. **Persistence vs. one-shot (the (a) vs (b) question)**: `discrim_flip_x1`
   corrupts **both** `x2` AND `x3` — not just the immediately-following
   reader. Under a one-shot forwarding/bypass-cache model, `x2` (the first
   subsequent consumer) would be expected to "drain" or "reset" whatever
   transient corrupted forwarding state exists, leaving `x3` (a later,
   independent read) free to read the value correctly from the ordinary
   register file. That is NOT observed: `x3` is corrupted identically
   whether `x2`'s own bit is also flipped or not (`discrim_flip_x1` ==
   `discrim_flip_x1_x2`, byte-for-byte identical output). This is the
   signature predicted by a **persistent-discard / producer-skips-writeback**
   model: the producer, wrongly marked "already consumed", never commits `v`
   to the durable register-file location every later reader depends on, so
   EVERY subsequent reader gets the same missing/zeroed value, not just the
   next one. `loop_boundary`'s CAND_B result (item 3: `candB_flip_c1`
   corrupts x1/x2/**and the loop accumulator, across 3 loop iterations**) is
   independent corroborating evidence for the same persistence signature.
3. **Consumer-bit irrelevance, replicated at a new site**: `discrim_flip_x3`
   (the LAST reader's own bit, flipped alone) is null — extending, not just
   replicating, EXP-0086's "consumer's own bit is irrelevant" finding to a
   third position.

**Verdict on the dispatch's (a)/(b)/(c) framing**: the evidence supports
**(a) a last-use/discard hint the hardware acts on** (specifically: a
producer-side "do not write this value back to the durable register store"
signal, when wrongly asserted) over **(b) a register-cache residency flag**
in the sense of a transient, per-request bypass/forwarding structure — the
persistence to a THIRD, independent reader is the load-bearing observation.
This experiment cannot rule out a *residency* flag if "residency" is defined
broadly enough to mean "this value's slot in the persistent register file",
which collapses into the same model as (a) under that reading — the
distinction that WAS testable (one-shot bypass-path glitch vs. persistent
loss) is the one this experiment resolves.

---

## Exact doc correction proposed (text only — not applied)

**`docs/isa/README.md`**, in the `⚠️ 0x54↔0x56 cache bit` paragraph
(currently lines ~773-789), APPEND (do not delete the existing EXP-0086 text,
which remains accurate for what it covered):

> **UPDATE (EXP-0089, M4, HW-VALIDATED).** The literal bit 17 has now been
> tested directly, in two independent instruction families where db.json's
> own `match` table proves it is a genuinely free field:
> `unpack_convert`'s `cache` field and `cvt_i2f`'s `mode` field. Both
> reproduce the exact corruption signature found for the `opflags`-bit0
> analog (EXP-0086): flipping the LITERAL bit 17 from `0x56`(fresh) to
> `0x54`(reuse) on the EARLIER/producer instruction, when nothing was
> legitimately available to reuse, makes a LATER, separate instruction's
> read of the same source register return **zero** — deterministic, no
> fault, silently wrong, across two independent full hardware runs (6/6
> repeats each). NEW: unlike the `opflags` bit, the literal bit-17 flip ALSO
> corrupts the FLIPPED instruction's OWN result in both families — i.e. this
> specific field governs (at least in part) whether the CURRENT instruction
> fetches ITS OWN operand fresh vs. from a bypass path, not only whether a
> later instruction can reuse this instruction's output. Flipping only the
> LATER/consumer instruction's bit is a no-op in both families (matches
> `opflags`-bit0's polarity). `falu_acc`'s bit 17 is confirmed
> opcode-determining by direct `match`-table inspection (bits 17-20 fixed to
> `0b1100`); `falu_acc`'s own `cache` bit is bit 21, still untested against
> a later read. `ret`/`ret_luse` select the MNEMONIC via byte+2, not a free
> bit. `if_push_pred`'s byte+2 is free but untested (no natural
> shared-source-read-twice shape found). `simd_reduce`/`fspecial`/
> `cvt_f2i`/`shl_reg`/`ibfins` remain UNTESTED by a direct later-read splice
> and should stay `UNKNOWN`. Evidence: `experiments/EXP-0089-m4-register-lifecycle-model/RESULTS.md` §2.
>
> **Also new (EXP-0089): the `opflags`-bit0 corruption from EXP-0086 is
> confirmed on ALL 7 of EXP-0086's kernels (not just `adjacent`), but its
> SCOPE is condition-dependent**, not universal in detail: 6/7 kernels show
> exactly EXP-0086's pattern (only the immediate next reader corrupted,
> consumer's own bit irrelevant); the 7th (`loop_boundary`, whose flipped
> instruction is a 12-byte extended form executed inside a real runtime
> loop) shows corruption reaching a THIRD value (the loop accumulator) and,
> uniquely, the consumer's OWN bit also mattering. A 3-reader kernel
> (`discrim3`) directly shows the corruption from a single flipped producer
> reaches every later reader, not just the next one, and never an earlier
> one — evidence for a persistent "producer skips register-file writeback"
> mechanism over a one-shot bypass-cache glitch. Evidence: same RESULTS.md,
> §3/§5.
>
> **Also new (EXP-0089): the `ctrl`/`ctrl_lo` tail field EXP-0086 found was
> "not actually inert" has now been value-swept (8 bit-patterns x both
> operand sites x all 7 kernels).** In the compact 6-byte `falu2i`/`falu2`
> form, bits 2 and 4 (of 7) are safe in 13/14 tested contexts; bits 0, 1, 3,
> 5, 6 are load-bearing (fault or silently corrupt) essentially everywhere
> tested. In the 12-byte extended `falu_srcmod12b` form (only reached inside
> a real loop body in this corpus), EVERY tested value is dangerous,
> including a genuine GPU hang (not just a fast command-buffer error) at
> bit2 — the same bit position that is safe in the compact form. Bit0/bit1
> ALSO showed genuine cross-process/cross-run non-determinism (8/112
> case-groups), the only non-deterministic field in ~1200 total hardware
> case executions across EXP-0086 and EXP-0089. Implementer guidance: do not
> assume ANY value of this field is safe by extrapolation from a different
> instruction length or a different bit position; emit exactly what the
> compiler emitted for the matching operand shape. Evidence: same
> RESULTS.md, §4.

**`db.json` descriptors to annotate** (report only — not edited): add
`unpack_convert` (`cache` field) and `cvt_i2f`/`cvt_i2f_src` (`mode`/
`src_cache` fields) to the "later-read HW-VALIDATED, corrupts" list
(currently only inferred from EXP-0086's `opflags` analog); `falu_acc`'s
provenance note should state plainly that bit 17 is `match`-fixed (not just
"could not compile into this shape") citing this experiment; the `ctrl_lo`/
`ctrl` fields on `falu2i`/`falu2`/`falu_srcmod12b` should get a `mod, PARTIAL
— bits 2/4 safe in 6-byte form / bits 0,1,3,5,6 load-bearing / 12-byte form
fully load-bearing / bit0-1 non-deterministic` annotation replacing any
"unassigned"/generic tail-field framing.

**`docs/isa/register-move-and-liveness.md`** §2.3's bullet "The literal bit
17 could not be tested" should be updated to state it HAS now been tested
(twice, independently) and both instances corrupt; §3's "Open" list item for
"literal bit-17 later-read test" should move from open to closed with this
experiment cited, while the CAND_B condition-dependence, `ctrl` bit map, and
producer/consumer model items should be added as newly-closed rows.

---

## Limitations / honest gaps

- **The strict two-run gate does not close over the full 549-line matrix**
  (see Evidence status). This is disclosed, not hidden or forced; a
  follow-up could narrow the `CTRL_SWEEP` census to avoid mask `0x01`/`0x02`
  on small-distance kernels if a byte-identical closure is later required
  for `docs/` promotion of ctrl-field claims specifically — the CAND_A/
  CAND_B/LIT17/DISCRIM claims do NOT depend on this and are fully closed.
- **`lit17_unpack`/`lit17_cvt`'s positive controls did not detect** (§2) —
  the `lit17_flip_c2` null results for these two kernels are `UNKNOWN`, not
  confirmed-safe, pending a working register-redirect for these specific
  instruction encodings. The corruption finding (`lit17_flip_c1`) is
  unaffected by this gap.
- **`lit17_unpack`'s presumed "byte+4 = source register" and `lit17_cvt`'s
  `src` field's exact addressing** are not independently confirmed beyond
  the failed positive control — plausible but unproven; do not treat as a
  validated field map.
- **`loop_boundary`'s divergence (item 3/4) conflates two variables** (real
  loop repetition vs. 12-byte instruction form) that this experiment did not
  separate — a follow-up isolating a 12-byte `falu_srcmod12b` CAND_B/ctrl
  test OUTSIDE a loop (if the compiler can be made to emit one) would
  resolve this.
- **The producer/consumer model verdict (item 5)** is drawn from ONE kernel
  family (float-ALU `falu2i` `opflags` bit) and is corroborated, not
  independently re-derived, by `loop_boundary`'s CAND_B pattern — it is not
  re-tested on the LITERAL bit-17 families (`lit17_flip_both`'s
  family-asymmetric recovery pattern, §2, suggests the literal bit's
  mechanism may not be identical, and this experiment does not have a
  3-reader literal-bit-17 kernel to test that directly).
- **CAND_A remains null everywhere it was re-tested** (all 7 original
  kernels, both runs) — consistent with EXP-0086, not re-litigated further
  here.
- **`falu_acc`'s own literal `cache` field (bit 21, not bit 17) remains
  untested** against a later, separate read — outside this experiment's
  scope (it targeted the literal bit-17 gap specifically).

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: kernels/*.metal (7 carried over verbatim from EXP-0086, 3
  new: lit17_unpack, lit17_cvt, discrim3), compiled via tools/shdump
  (newLibraryWithSource:), decoded/spliced with tools/agx-isa (read-only),
  executed on the real M4 GPU via tools/agxtest. unorm/snorm/int-float
  conversion oracle formulas are documented public Metal Shading Language
  builtin semantics (PUBLIC), independently re-implemented in Python
  (casematrix.py), not learned from any Apple binary. No Apple binary,
  archive, BO, or command-stream inspection.
Apple binary introspection: NONE
Reproduction: python3 -B verify.py --selftest / --seqtest (synthetic, no GPU);
  python3 -B run.py --execute --run-id <id> (real GPU, append-only);
  python3 -B analysis.py --run-a m4-lifecycle-20260828-run01 --run-b
  m4-lifecycle-20260828-run02 --write
Evidence: raw/m4-lifecycle-20260828-run01/ (complete, 549/549),
  raw/m4-lifecycle-20260828-run02/ (complete, 549/549), analysis.json
```
