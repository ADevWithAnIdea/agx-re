# EXP-0219 — PRE-REGISTRATION

**Frozen before any build or device dispatch.** Amendments are appended in §12 and each
one is frozen *before* the dispatch that uses it. Nothing above §12 is edited after the
first gated dispatch.

**Target:** Apple A18 Pro / G17P (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, `Mac17,5`, Metal family Apple9), `192.168.170.254`. **No M4 dispatch.**

**Clean-room category:** OWN-SHADER + HW-PROBE. Every byte compiled, spliced, decoded or
inspected is the compiled form of MSL in `kernels/`, which we wrote. **No Apple binary is
disassembled, decompiled, symbol-dumped or introspected.**

**Repo revision at pre-registration:** `3cea1bc4d8d569bcd2ee917d518222188b1fdf9e`, working
tree clean except this experiment's own new directory. Per `SUBAGENT_BRIEF`, captures are
gated on the *authored blob hashes* recorded in `CAPTURE_CONTRACT.json`, **not** on `HEAD`
staying put.

---

## 1. Why this experiment exists

Two careful experiments ended by naming, exactly, the dispatch that would settle what they
could not decide. This experiment does those dispatches and **opens no new question**.

| # | question | named by | the dispatch it named |
|---|---|---|---|
| A1 | Is `imad`'s addend-source selector **bit 3** of byte+9 on G17P, or bit 1? | EXP-0218 §6.1 | dispatch `b9 = 0x2c` (bit3=1, bit1=0) and `b9 = 0x22` (bit1=1, bit3=0) on G17P |
| A2 | In fetch mode, is the source index **5 bits** (`K`) or **8 bits** (`K \| (b8&7)<<5`)? | EXP-0218 §6.2 | a carrier whose constant file holds a non-zero value above half-index 31, then sweep `b8`'s low nibble |
| A3 | Does a 32-bit fetch pair `(K, K+1)` or read word `K>>1`? | EXP-0218 §6.3 | `b9` bit 0 = 1 at **odd** K |
| A4 | Is the immediate branch `A = IMM8` true across all 32 K **on G17P**? | EXP-0218 §6.4 | sweep byte+7 on G17P with `b9 = 0x26` (the byte+7 × byte+9 cross product) |
| B | What does `tex_sample.mode` **bit 6** do, and why only on `msread`/`mslodq`? | EXP-0213 §2.5 | a carrier that can express it; if it is nondeterminism, characterise it (rate, per value, per arm) |

## 2. Desk step already done, BEFORE any dispatch (§B0)

`analysis/desk_mode_instability.py` reads only **committed** raw (EXP-0204's
`g17p_e0213_B1/B2/B3`, three quiet orders) and writes nothing into any `raw/`. Its output
is `work/desk_mode_instability.json` and `analysis/desk_class_maps.txt`. It establishes,
offline:

* **every** unstable `mode` value on all four unstable arms has **bit 6 set** (100 %), and
  **none** has bit 3 set;
* the instability is confined to the quadrant `bit6 = 1, bit3 = 0, bit2 = 0` — **32 of 256
  values per arm**, of which 20–26 are unstable across the three committed orders;
* the payload alternatives are a small, structured set: a result channel reading **0**, or a
  result channel whose 32-bit float has its **low 16 bits zero** (e.g. `10000.0f`
  `0x461C4000` → `9984.0f` `0x461C0000`; `20100.0f` → `20096.0f`), i.e. **only the high
  16-bit half of the destination was written**;
* on `msfilt` and `mscmp` bit 6 is byte-for-byte inert (rows `0x40–0x7f` equal rows
  `0x00–0x3f`).

These are the facts the hypotheses below are built on. They are **observations from
committed data**, not new hardware results.

---

## 3. Hypotheses, competing models and refuters

### A1 — the selector bit

* **H-A1a (bit 3 is the selector, G16G-direct fact generalises):** on G17P,
  `b9 = 0x2c` selects FETCH (`A = FILE[K]`) and `b9 = 0x22` selects IMMEDIATE (`A = IMM8`).
* **H-A1b (bit 1 is the selector on G17P):** the opposite assignment.
* **H-A1c (neither alone; both bits required):** `0x2c` and `0x22` both behave like one of
  the two modes, or like neither (a third behaviour / fault / silent zero).

**Refuter for H-A1a:** `b9 = 0x2c` returning `A = IMM8` at a K where `IMM8 != FILE[K]`.
**Discriminating K:** any K with `FILE[K] != K`. `K = 12` gives `IMM8 = 12` vs `FILE[12]`
(measured in the same run); `K = 13`, `K = 14`, `K = 15`, `K = 0`, `K = 2` likewise.

### A2 — the fetch index width

* **H-A2a (8-bit index):** `A = FILE[K | (b8&7)<<5]`. On a carrier whose file is non-zero
  above half-index 31, some case with `b8 & 7 != 0` returns a **non-zero** addend.
* **H-A2b (5-bit index + suppression):** `A = FILE[K]` if `b8 & 7 == 0`, else `A = 0`,
  on every carrier.

**Refuter for H-A2b:** a single reproducible non-zero addend at `b8 & 7 != 0`.
**Refuter for H-A2a:** all 224 such cases return 0 **while** the same carrier is shown to
hold non-zero constants that are not visible at half-indices 0..31.
**Named confounder, declared now:** a carrier can fail to place its constants in this file
at all (they may live in a memory constant buffer). If every half-index 0..31 is non-zero
and distinct, the carrier's remaining constants *must* live somewhere else; whether that
"somewhere else" is index ≥ 32 of the same file is exactly what is undecided, and a null
result is therefore reported as **still undecidable with a sharper question**, never as
"the index is 5 bits".

### A3 — the 32-bit fetch pairing

* **H-A3a (pair `(K, K+1)`):** `A32 = FILE[K] | FILE[K+1] << 16`.
* **H-A3b (word `K>>1`):** `A32 = FILE[K & ~1] | FILE[(K & ~1) + 1] << 16`.

The two agree at even K and disagree at odd K whenever `FILE[K] != FILE[K-1]` or
`FILE[K+1] != FILE[K]`. **`FILE[0..31]` is measured in the same run by 16-bit fetches
before the 32-bit cases are scored**, so both predictions are computed from data, and the
32-bit observation is held out with respect to the pairing rule.
**Odd K dispatched:** 1, 13, 15 and 3, 5, 7, 9, 11 (all 32 K are dispatched in 32-bit mode).

### A4 — the immediate branch on G17P over all K

* **H-A4a:** with `b9 = 0x26` (bit3 = 0, bit5 = 1) and `b8 = 0xd0`, `A = K` for all 32 K on
  G17P, exactly as on G16G.
* **H-A4b:** the immediate branch is G16G-only; G17P behaves differently at some K.
* **H-A4c (high three bits):** with `b8 = 0xd0..0xd7`, `A = K | (b8 & 7) << 5` on G17P.

**Refuter:** any K where `A != K` under `b9 = 0x26, b8 = 0xd0`, or any `b8` low-3 value
where `A != K | (b8&7)<<5`.

### B — `tex_sample.mode` bit 6

* **M-B1 (race / timing):** with bit 6 set (and bits 2,3 clear) the result of a texture
  instruction is consumed before it is architecturally available, so the payload is
  timing-dependent. **Predicts:** repeated dispatch of the *same* value inside the *same*
  process disagrees at a measurable, value-specific rate > 0; the observed payload set per
  value is small and consists of "channel written" / "channel not written" / "only the high
  half written".
* **M-B2 (deterministic, per-process state):** bit 6 selects a different, deterministic
  behaviour; the cross-capture disagreement comes from state that differs between
  *processes* (pipeline compile, allocation, warm-up). **Predicts:** within one process,
  repeats agree 100 %; across freshly-launched processes on the same value they may differ.
* **M-B3 (measurement artefact):** the disagreement is in the harness/readback path.
  **Predicts:** under the same number of repeats, values with bit 6 **clear** disagree at a
  comparable rate.

**Refuters:** M-B1 is refuted by 100 % within-process agreement over ≥ 16 repeats on every
value that EXP-0213 recorded unstable. M-B2 is refuted by within-process disagreement.
M-B3 is refuted by a bit6-clear control set that agrees 100 % under the identical repeat
count in the identical processes.

**Secondary, structural (bounded, may end UNDECIDED):** the desk step shows bit 6 appears
to *move which result slot* the other mode bits affect (on `msread/0`, `bit1` suppresses the
low half of channel `b` when bit 6 is clear and of channel `c` when it is set). Two
dispatches probe it, and either may return `carrier-undecidable`:
* **occ-2 arms** — `mode` on the *third* (never-armed) `tex_sample` of `k_msread`, and on
  the third and fourth of `k_mslodq`. If the effect of a mode bit is indexed relative to the
  instruction's own position, the last instruction in the chain has no successor to shift
  into.
* **a one-read carrier** (`kernels/k_msread1.metal`, authored here) — a fragment shader with
  exactly **one** `read()`. If bit 6's liveness needs an adjacent texture instruction, it is
  inert here.

**No new question is opened.** Anything these two probes surface beyond "what does bit 6
do" is recorded as an observation with an explicit `still undecidable` verdict.

---

## 4. Carriers, and why each has detection power

| id | file | what it is | detection power |
|---|---|---|---|
| `C-DAG` | `kernels/carrier_dag.metal` | **byte-identical copy** of EXP-0160's carrier (cited; our own MSL, same project) | the carrier the whole `imad` corpus was measured on, so A1/A3/A4 are directly comparable with EXP-0154/0160/0218 and its `FILE` table is already published |
| `C-CONST` | `kernels/carrier_const.metal` | **new**: 48 distinct 32-bit float constants built with `as_type<float>` so both 16-bit halves of each are unique and identifiable | the only carrier that can put a non-zero value above half-index 31 — the dimension A2 needs |
| `C-IMAD` | `kernels/probes_imad.metal` | **new** (same one-line shape as EXP-0160's `k_imad`, re-authored): `out[g] = a[g]*b[g] + 12345` | supplies the lifted `imad` anchor block |
| EXP-0204's `msread`, `mslodq`, `msfilt`, `mscmp`, `msgath`, `msfixl` | `kernels/k_*.metal` (**byte-identical copies**) | the ten arms EXP-0213 measured | required: the claim under test is about *those* arms |
| `C-READ1` | `kernels/k_msread1.metal` | **new**: one `read()`, nothing else | differs in the dimension M-B's structural probe implicates (number of adjacent texture ops) |

The `imad` carriers are **SYNTH-WITH-LIFTED-BLOCK** (EXP-0154/0160 shape, cited): the whole
`_agc.main` is replaced by a program assembled from `tools/agx-isa`'s own field rules —
seeds → PRE sentinel → the lifted 12-byte `imad` with one byte mutated → 16-register dump →
POST sentinel → `stop`. Every operand the instruction names is a register **we** seeded.
The external constant file is a property of the *carrier*, which is exactly why A2 needs a
new one.

## 5. §3z — the stop-ruler precondition

`isadb.decode_one` answers "do these bytes match a descriptor", never "does an instruction
start here". Before any sweep at a site this experiment did not itself construct:

* **Part A sites are constructed, not found.** The mutated `imad` is placed by our own
  assembler at a known offset inside a program we built instruction by instruction, so its
  boundary is a property of the build, not of a signature scan. The stop-ruler does not
  apply; what does apply is the **unmutated-anchor baseline**, which is dispatched first
  for every arm and every seed set and must reproduce.
* **Part B sites are inherited from EXP-0204 and two of the four are `located_via: scan`**
  (`mslodq/0`, `mslodq/1`) — signature-derived. **A targeted stop-ruler is therefore run
  first**, before any part-B sweep: splice a 4-byte `stop` at each arm's own offset and at
  `offset ± 2` and `offset ± 4`, and record whether the fragment shader stops producing
  output. **The claim is one-sided:** a halt proves a boundary; a no-halt is INCONCLUSIVE.
  Anchor inconsistency (a byte-identical fill reading `halt` at one offset and `ok` at
  another with no consistent span) returns **`carrier-undecidable`**, not a refutation.
  The confound `RE_EXPERIMENT_PROCESS_CORRECTIONS`/`FIELD-SWEEP-PROTOCOL` §3z names —
  `not_written` has three producers — is recorded per case; here the observable is the
  render target holding its **clear** value, which is a fourth producer and is recorded as
  such rather than being read as a halt on its own.

## 6. Gates

**Gate A — actual-byte ledger, every case.** Requested field value, complete requested
instruction bytes, complete **actual** bytes re-read from the artifact handed to Metal, the
value independently decoded from those actual bytes by the pinned DB, program hash,
DB/harness revision. No hardware conclusion where `requested != decoded`.

**Gate B — a pre-registered positive control per arm.**
*Part A:* the arm's **unmutated anchor** must reproduce its baseline 16-register digest, and
each arm must contain at least one pre-registered pair of cases that the arm's own model
says must differ (e.g. `b9 = 0x26` vs `b9 = 0x2e` at a K where `IMM8 != FILE[K]`). A failed
control makes the arm **`carrier-undecidable`**, never `inert`.
*Part B:* `mode = 0x08` (bit 3) is dispatched as the positive control on every arm before
its repeat block; it moves the observable deterministically on all ten arms in the
committed data. An arm whose control does not move is `carrier-undecidable`.

**Gate C — an independent predictor, stated before output is seen.** `analysis/oracle_a.py`
computes, for every part-A case, the predicted destination under **each** competing model
from `dest = m·(SEED[b5>>2]·SEED[b6>>3]) + A`, with `m` from `b7 & 3` and `A` from the
model. It distinguishes: correct value · a different but coherent value · silent
zero/no-write (poison) · fault/hang · invalid measurement. For part B the predictor is the
three-way model set M-B1/M-B2/M-B3 and the pre-stated repeat-rate predictions in §3.

**Gate D — not attempted.** No compiler recipe is claimed by this experiment.

**Gate E — two clean runs in reversed or shuffled order on a machine measured quiet.**
Every capture is bracketed by a process-table and IOKit sampler (`harness/quiet.py`,
2 s interval) and by a `recoveryCount` snapshot **before and after**. `recoveryCount` is
**reported, not gated** (our own pre-registered illegal encodings reset the device).
The designated Gate E pair for every arm is **`run01` (forward) × `run02` (reverse)**,
designated here, before any capture.

**Hang classification, required per capture:** driver-recoverable (`recoveryCount`
advances, no cascade) vs **accumulating** (`recoveryCount` frozen and every later value
hangs). Both `recoveryCount` values and the per-value hang sequence are recorded.

## 7. Declared budgets

| | |
|---|---|
| **hang budget** | **8 per arm**, **32 for the whole experiment**. On reaching an arm's budget the arm stops and is reported PARTIAL with the exact coverage. On reaching 32 the experiment stops dispatching and reports. |
| accumulating-cascade rule | if `recoveryCount` is unchanged across ≥ 6 consecutive hangs, the arm is stopped immediately regardless of budget and the capture is marked `cascade-contaminated` from the first of those hangs |
| wall clock | ≤ 45 min per capture, ≤ 5 h of device time total |
| request timeout | 8 s (compute), 15 s (render) |
| concurrency | this agent owns the device; no other GPU work is expected. Quiet is **measured**, not assumed |
| repeats | part A: 3 attempts per case, as EXP-0160 (majority for non-OK). Part B: **16 repeats per (arm, value)** in one process, each recorded separately |

## 8. Raw record schema (append-only, flushed + fsynced per case)

```
run_id, seq, t, case id, target, carrier/context id, arm, instr, field,
requested value, requested bytes, ACTUAL bytes, decoded actual value, gate_a_ok,
program hash, seed set / complete seeded input state, complete relevant output state
(16 registers + PRE + POST sentinels, or the probe surfaces), poison count,
host prediction per competing model, semantic-check result per model, outcome,
command-buffer status, OS fault-classification string, victim flag,
timeout/retry/measurement-failure flags, repeat index, case order index
```

`outcome` ∈ `ok | silent_zero | wrong_value | fault | hang | undecodable |
measurement_failure`. A malformed runner response is `measurement_failure`, **never** a
hardware outcome.

## 9. What this experiment may and may not advance

| axis | may advance |
|---|---|
| encoding geometry | yes (A1–A4: which bits carry which role) |
| liveness | yes |
| semantics | yes for A1/A3/A4 if the predictor selects one model; **B is expected to advance liveness + a characterisation, not a semantic map** |
| compiler recipe | **no** |
| target | G17P-direct only |
| reproducibility | yes |

**It may not** change any label, `tools/agx-isa/`, `docs/`, `PROVENANCE.md`, or commit
anything. It writes only under `experiments/EXP-0219-named-dispatches/`. New raw run
directories are pulled back **one directory at a time**; nothing is ever written into an
existing `raw/` path.

## 10. Known ways this method could produce a FALSE verdict

1. **`bytes` trusted to be what ran.** Mitigated by Gate A re-reading the actual spliced
   window, but the standing EXP-0215 §7.6 caveat holds.
2. **The `FILE` table is carrier state, not a hardware fact.** Every A2/A3 statement is
   about *this* carrier's file; the hardware claim is only about the *indexing rule*.
3. **A2's null is weak by construction** (§3, named confounder).
4. **Repeat-within-process is a different dispatch shape** from EXP-0213's one-per-capture,
   exactly as EXP-0213's per-arm invocation was a different shape from the full-set run.
   Both shapes are therefore recorded, and the cross-process comparison is kept.
5. **A control that cannot fail.** Gate B's part-B control is a value known to move; if it
   moves in every capture the control proves detection power and nothing else, and it is not
   counted as a result.
6. **Order effects.** Two orders per capture pair; the repeat blocks are additionally
   interleaved (`--repeat-order interleaved`) in one of the two runs so a value's 16 repeats
   are not always adjacent.

## 11. Stopping rule

Part A stops when every declared case has a scored record or an arm has hit its budget.
Part B stops when the four unstable arms plus the two stable controls have their repeat
blocks in two orders, or on the experiment-wide hang budget. **"Still undecidable, and here
is the sharper question" is an accepted terminal verdict for any row.**

## 12. Amendment log

*(empty at freeze)*
