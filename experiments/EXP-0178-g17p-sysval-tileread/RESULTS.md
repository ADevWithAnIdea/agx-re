# EXP-0178 Results — G17P system values (`get_sr`) and the tilebuffer read

**Target: A18 Pro / G17P only.** No M4 claim is made anywhere in this experiment. Every M4
result cited below is a **cross-target hypothesis** that this experiment tried to reproduce or
refute on the documentation target — never a premise.

Clean-room provenance: **OWN-SHADER + HW-PROBE**
Inputs inspected: `kernels/sysval.metal`, `kernels/tilebuf.metal`, and the AGX bytes the public
`newLibraryWithSource:` API compiled from them.
Apple binary introspection: **NONE**
Reproduction: `harness/selftest.py`; `harness/sync.sh push`; `harness/verify_remote.py`;
`harness/run.py --run-id <id> --out-root raw`; `analysis/verdicts.py`; `analysis/answers.py`
Evidence: `raw/g17p_20260830_run03/`, `raw/g17p_20260830_run04/`,
`analysis/answers.json`, `analysis/field_verdicts.json`
Pinned toolchain: `pinned/{isadb.py,db.json,agxparse.py}`, sha256 in `CAPTURE_CONTRACT.json`,
resolved by absolute path with a hard exit if absent.

---

## The two questions, answered in plain words

**1. Can a compiler back end emit a system-value read on G17P?**

**Yes — and it must obey a stage-dependent legality rule that was not previously known, because
getting it wrong in a vertex shader is a fault rather than a wrong pixel.**

`get_sr.sr_sel` was `untested` on G17P before this experiment, which meant no system value could
be emitted at all on the documentation target. Its full 256-value encodable range has now been
dispatched on **three structurally different carriers, one per shader stage**, across two gated
runs, and the space partitions exactly on **bit 7** — but into different behaviours per stage.
The compute stage reproduces every one of EXP-0092's unexplained M4 constants and aliases; the
fragment stage resolves pixel X, pixel Y and `front_facing` against a host oracle; and the vertex
stage **faults on all 128 bit-7-clear selectors and on none of the 128 bit-7-set ones**.

**2. Does EXP-0147's silent-zero tile-read hazard reproduce on G17P?**

**Yes, exactly — and it is worse than "no loud failure": across 256 `rt_index` values on four
carriers and two gated runs there is not a single fault.** `byte+6` bit 0 is a read-enable whose
even values return a silent zero with `STATUS OK`; every wrong render-target index does the same;
and `tile_read_mrt.fmt` is correct at exactly the eight M4 encodings and silently zeroes at 104
others. Every legal-value set EXP-0147 measured on M4 transfers to G17P **unchanged**, including
a contiguous `0xf6`–`0xff` fault wall in `dst` that is byte-identical on all four carriers. In a
BG/EOT program the failure mode is a black tile with no diagnostic — so **absence of a fault
proves nothing about whether the read landed**.

---

## 1. What was run

| arm | stage | carrier | anchor resolved | ruled-on fields |
|---|---|---|---|---|
| `sr_compute` | compute | `k_sr_c`, grid 64 / tg 64 | `04 82 10 06` at +0, clean tokenization | `sr_sel`, `dp_width`, `dp_marker` |
| `sr_frag` | fragment | `v_full`/`f_sr`, 4×4 RGBA32Float | `0c a0 11 06` at +0, clean tokenization | same |
| `sr_vertex` | vertex | `v_sr`/`f_sv`, 4×4, **indexed draw**, `baseVertex 9`, `baseInstance 5`, 3 instances | `0c d8 10 06` at +28, resolved by scan | same |

`get_sr.dst` and `.form` were swept and recorded but **not ruled on** — EXP-0168 and EXP-0172 own
those field names. `get_sr.dst_hi` was **not swept at all**: its values 6–7 select registers ≥ 96,
the G17P region EXP-0155 measured as a **hang** across seven fields, and EXP-0168 already has it
emitter-grade on G17P. The exclusion is recorded in `sweepplan.py::ARMS[*].not_swept` and in each
run's `00_arm_resolution.json` so the omission is auditable rather than silent.

Every arm passed its pre-registered liveness ladder and its pre-registered falsifier in both runs
(§4). No arm was promoted on a carrier that could not demonstrate detection power.

---

## 2. Why the previous G17P answer was `untested` — a named finding

**Observation.** `tools/agx-isa/validation.json` carries `get_sr.sr_sel`, `.dp_width` and
`.dp_marker` as `untested` on G17P, evidence EXP-0169, each recorded as
*"0..255 dense (all 256 values) … 1 carriers"* with the note *"no (arm,carrier) passed its
liveness ladder"*. EXP-0169's `RESULTS.md` §8 reports it honestly: *"`L_form` and `L_sr_sel` do
not [move] — every probed `sr_sel` returned the same value."*

**Cause, read from that experiment's own committed files.** Its `k_sr` probe was **lifted** into
a synthesized program and dispatched at **grid = 1 / tg = 1**. The relaxation is stated in the
source: `experiments/EXP-0169-g17p-rerecord/harness/casematrix.py:78` —
*"with grid=1/tg=1 every SR this harness reaches is deterministic"*. At that geometry every
special register the probe can reach reads **0**, so no selector can move anything, the ladder
correctly failed, and the field was correctly recorded as `untested`.

**Interpretation.** This is the third member of a family the protocol already names twice.
`iter_at.loc` failed because the **carrier** could not express the field (every arm was
`samples=1`, where centroid and sample are the same point). `uniform_mov.dst` failed because the
**oracle** could not (field and observable moved together by construction). Here it is the
**dispatch geometry**. All three produce a null that looks like a passing test, and none is
visible in the results — only in the design.

**Consequence.** The `untested` verdict on those three fields is a limit of that carrier, not a
property of the hardware, and this experiment retires it rather than contradicting it. Restoring
EXP-0092's grid=64/tg=64 geometry — where distinct special registers produce distinct,
**host-computable** 64-thread patterns — was sufficient; nothing else about the probe changed.

---

## 6. Three defects found in the measuring apparatus, and what they cost

These are reported because two of them would have produced clean-looking wrong answers, and one
already destroyed a gated run.

### 6.1 `DEF-0178-1` — on the shared driver, the first timeout can manufacture every "hang" after it

**Observed.** `tools/agxtest/persistrun.py` and the `rsdrv.py` render driver read one line by
starting a **fresh daemon thread per read** and **abandoning it on timeout**. The thread body
resolves `self.proc` at *execution* time, so after the first watchdog timeout the abandoned
thread wakes on the **replacement child's** stdout and races the foreground reader. Responses
come back truncated — `OUT 0 ` with the hex missing — and the shared parser raises
`ValueError: not enough values to unpack (expected 3, got 2)`.

**Cost, measured.** In `work/pilot02`…`pilot05` **one benign case poisoned every later request,
including the unspliced health check**, and three consecutive cases were recorded `hang` with
`restarts=99`. All false. This experiment deliberately has no hang budget, so hangs are expected,
and this defect would have manufactured a cascade of artefacts on top of real ones.

**Fix.** `harness/saferunner.py`: one reader thread per child, tagged with the process it came
from, so lines from a dead child are discarded rather than handed to the wrong request; and a
malformed response recorded as a **measurement failure** with the raw lines kept, never as a
hang. It carries an `UPSTREAM NOTES` block with the before/after for both changes and a
defaults-preserving statement. The shared tools were deliberately **not** modified while a
sibling experiment was running against them.

**The half that matters.** *A malformed response is not an observation and must not be scored as
one.* Not as a hang, and — as §6.3 shows — not as a fault either. `harness/fakerunner.py` speaks
the same protocol with no Metal, and selftest gate **G9** asserts that a truncated response
yields `MALFORMED` with the raw kept, never a crash and never a `hang`.

### 6.2 A frozen contract hashes what you authored, not what the device is running

**Observed.** `harness/verify_remote.py` hashes the pushed blobs **on the neo** and compares them
to the contract's frozen `authored_sha256`. On its **first run** it reported **11 of 18 blobs
matching**: `analysis/answers.py` and `harness/fakerunner.py` were **missing** and
`harness/{run,saferunner,selftest,sweepplan}.py` plus `analysis/verdicts.py` were **stale**.
Every amendment since the first push had silently failed to reach the device.

**What that would have cost.** A gated pair captured at that moment would have executed the
**pre-amendment harness under a contract asserting otherwise** — and every hash in that contract
would have verified, because it hashes the *local* files. No existing check in the protocol
covers that gap, before or after the fact.

**Why the gap existed.** `SUBAGENT_BRIEF.md` records two failures on 2026-08-30 in which a
state-changing step behind `&&` silently did not run while the exit code looked clean. The
verification must therefore be a **separate step, never chained behind the push it checks** —
chaining it would reintroduce exactly the defect it exists to catch.

### 6.3 `raw/g17p_20260830_run01` — a closure-shadowing defect wearing the costume of §6.1

**Observed.** The compute arm bound its read-back **size** as `nb`, and the `raw_case` closure
passed it as `outs={0: nb, 4: nb}`. Two hundred lines later the pre-registered falsifier did
`nb = bytearray(blk0)` in the same enclosing scope. A closure resolves a free variable at **call**
time, so from the falsifier onward every request asked the runner for a read-back of *a bytearray*
bytes and raised inside the request builder.

**Why it survived four pilots.** It presented as a **hang cascade** — one clean case, then
everything unrecoverable including the health check — which is byte-for-byte the signature of
§6.1, fixed twenty minutes earlier. The evidence was read as "the fix is not taking effect"
rather than "a second, independent defect produces the same signature". The tell was there and
was missed twice: the exception *text* had changed from `not enough values to unpack` to
`%d format: a number is required, not bytearray`, i.e. a different call site entirely.

**The general lesson, which is not a Python one.** *Having just fixed a cascade-shaped defect
makes the next cascade-shaped defect harder to see*, because the first explanation is available
and fits. What resolved it was **instrumentation, not reasoning** — a `traceback.format_exc()`
added to the runner-exception handler an hour earlier named `saferunner.py:188` on the first run
that hit it. Check an exception's **identity** — text, call site, stack — not its shape.

**Two instruments earned their keep before measuring anything.** Because a malformed runner
response was already classified as a **non-observation** rather than a `hang` or a `fault`, this
harness bug could never have entered a verdict as an inertness reading on `get_sr.sr_sel`; under
the pre-amendment classifier it would have been recorded as `fault` — a harness bug promoted to a
hardware claim. And because the falsifier is dispatched *before* the sweep, the defect fired on
case zero rather than in the middle of 562.

**Fix, and the check that generalises it.** Both names are now unique and deliberately
dissimilar. `harness/closure_scan.py` — written to be upstreamed — walks the AST and reports any
name a nested closure reads that the enclosing scope assigns more than once; selftest gate
**G10** runs it over `run.py`. It found three further candidates (`mnem`, `off`, `runner`); all
three are assigned in **mutually exclusive branches of one `if`/`else`** and are carried as an
explicit allow-list *with that reason*, rather than by weakening the rule.

The run id is **burned**: `raw/g17p_20260830_run01` is retained exactly as it landed, never
topped up, deleted or reused, and `DEFECTIVE-run01.md` records why. `g17p_20260830_run02` was
never dispatched and is retired too, so no id is ambiguous.

## 3. `get_sr.sr_sel` on G17P — the answer to Q1

**Coverage.** 256 dense values × 3 stage carriers × 2 gated runs = 1,536 dispatched cases.
**Cross-run agreement: 100.00 % on every value of every carrier. Zero disagreements.**

### 3.1 The rule an implementer must act on

> **On G17P, `get_sr.sr_sel` bit 7 partitions the encodable range, and what the bit-7-clear half
> DOES is stage-dependent. In a VERTEX shader every selector with bit 7 clear FAULTS the command
> buffer — all 128 values, `0x00`–`0x7F`, contiguous, zero counterexceptions, both gated runs.
> Nothing at or above `0x80` faults in any stage. The same encoding in a COMPUTE shader does not
> fault at all: it writes ONE lane of 64 and leaves the other 63 untouched. A back end must
> therefore never emit a bit-7-clear selector, and must be aware that the failure mode differs by
> stage: loud in vertex, near-silent in compute.**

**This REFINES a committed M4 result; it does not refute it.** EXP-0092 established
exhaustively on M4 that *"no `sr_sel` value in the full 256-value space raises `STATUS != OK`"* —
its `srsweep.faulted_sr` is the empty list — and on G17P **half the space faults in the vertex
stage**. That looks like a target disagreement and is not one. **EXP-0092's sweep ran on a
COMPUTE carrier, and this experiment's compute arm reproduces it exactly: 0 faults in 256 values,
both gated runs.** The M4 record is correct about what it measured. The divergence is **stage,
not target**, and the M4 row deserves `REFINED`, never `SUPERSEDED`.

The general point is sharper than a target disagreement would have been, and it is the reason
`CLAUDE.md` requires closure against full G17P: **an experiment can be perfectly executed,
densely swept, exhaustive over the whole encodable range and cross-run agreed, and still be
blind — because one carrier cannot see a dimension it does not vary.** EXP-0092 swept every one
of 256 values twice and could not have found this, and neither could any number of further
compute carriers. The `iter_at.loc` lesson (the carrier could not express the field), the
`uniform_mov.dst` lesson (the oracle could not), EXP-0169's `get_sr` failure (the dispatch
geometry could not) and this one are the same lesson at four different levels.

**The wall was mapped inside the gated run, not by a follow-up pass.** It is contiguous over 128
values, and a per-field hang budget of 2 would have stopped at the second faulting value and
reported "two bad values" — the exact failure FIELD-SWEEP-PROTOCOL §3(c) describes for
`frag_color_pack.dst`. This experiment pre-registered **no hang budget and no per-arm abort**, so
the region characterised itself. That is the third time this design has paid in one session:
EXP-0169's DSTORE arm pinned `device_store.index_reg` and `extmode` the same way.

### 3.2 Per-stage behaviour, both runs identical

| selector region | compute (grid 64/tg 64) | fragment (4×4) | vertex (indexed, 3 instances) |
|---|---|---|---|
| `0x80`–`0xFF` | 17 match the host oracle, 99 silent-zero, 12 other | 3 match, 100 silent-zero, 25 other | 2 match, 126 other |
| `0x00`–`0x7F` | **128 × one-lane partial write** | 127 other, 1 silent-zero | **128 × FAULT** |
| faults anywhere | **0** | **0** | **128**, span `0x00`–`0x7F`, contiguous |

### 3.3 The bit-7-clear region measured more sharply than it could be on M4

For every bit-7-clear selector the compute read-back holds `1000 + sel` in **slot 0 only**, with
**63 of 64 lanes still holding `0xDEADBEEF`** and **exactly 1 of 64 integrity-sentinel lanes
written**.

EXP-0092 ran against a **zero-initialised** buffer and could only report that the other slots
"remain 0 (the buffer's pre-dispatch state)", recording the mechanism as `UNKNOWN` and explicitly
declining to say whether it was "a uniform/scalar write that only one SIMD lane's dependent chain
retires, some other scheduling collapse, or a different mechanism entirely". A poisoned read-back
distinguishes *wrote 0* from *did not write*, per FIELD-SWEEP-PROTOCOL §7 instrument 1, so the
lane count here is a measurement rather than an inference.

**The new fact: it is not the special-register read that collapses to one lane, it is the whole
program.** The integrity sentinel is written by a **separate `device_store` containing no
special-register value at all**, and it lands on exactly the same single lane. Whatever
bit-7-clear encodes, its effect is on which invocations retire their stores, not on the datapath
of the read.

### 3.4 Every unexplained M4 constant reproduces on G17P

The compute arm reproduces **all four** of EXP-0092's unexplained M4 constants exactly —
`0x90` → 3, `0x96` → 4, `0x97` → 32, `0xb9` → 256 — plus both of its aliasing oddities
(`0x95` and `0xea` each reproduce `simd_lane_id`'s 0–31 pattern bit-for-bit, and are the only two
selectors in the entire 256-value space whose observation is **identical to the baseline**) and
its period-4 pair (`0x83` and `0x94` → `0,1,2,3` repeating across all 64 threads). Four constants
and four aliases, on a different target, with no parameter in common but the dispatch geometry.

**One `db.json` enum entry is refuted.** `sr_sel = 0xa8` is documented as
`threadgroups_per_grid.x`, which is **1** in this single-threadgroup dispatch. It reads **64** —
`threads_per_threadgroup.x`. Its neighbours `0xa9` and `0xaa` read 1 and **match** the documented
`threadgroups_per_grid.y`/`.z`, so the enum is wrong on exactly one entry, not on the family. This
independently reproduces RT-7's A18 finding and EXP-0092's M4 re-test on a third target.

**Seventeen selectors match a host-computed oracle in compute** — `0x82`, `0x85`, `0x98`, `0x99`,
`0x9a`, `0x9c`, `0x9d`, `0x9e`, `0xa0`, `0xa1`, `0xa2`, `0xa4`, `0xa5`, `0xa6`, `0xa7`, `0xa9`,
`0xaa` — and **three in fragment**: `0xa0`, `0xa1` (integer pixel X and Y) and **`0xc5`
(`front_facing`)**, which was `INFERRED` on G17P by byte-diff and is now matched against a host
oracle over a 4×4 target in both runs.

**The fragment pixel-centre offset is exactly 0.5, confirmed rather than fitted.** The
pre-registered affine model `pos = SR + C` with `C = 0.5` was checked against the baseline before
any swept case was classified: `(.r − px)` is `0.5` at all 16 pixels, `affine_model_holds` true,
`preregistered_c_confirmed` true. The instruction that supplies the offset remains unidentified
(EXP-0177 §4); its **value** is now measured on G17P.

### 3.5 The vertex arm produced a result it was not designed for — reported differentially

**A confound, disclosed.** `v_sr` writes `float(iid)` where `iid` is MSL's `[[instance_id]]`.
Seven selectors that have **no vertex-stage meaning** (`0x9c`, `0x9d`, `0x9e`, `0xa0`, `0xa1`,
`0xa4`, `0xc5`) all read **exactly 5** — seven independent zero-expectations agreeing, which
**measures** a compiler-inserted constant `K = 5 = baseInstance` rather than assuming one.

**Consequence for this experiment's own scoring, stated plainly:** the harness scored `0x8a`
(`base_instance`) as `ok`, because the oracle predicted 5 and the observation was 5. **That
agreement is an artefact of the very confound above** — a right answer for a wrong reason, which
is worse than a wrong one because nothing downstream would flag it. The vertex arm is therefore
reported **differentially**, and its two `ok`s are **not cited as validations** of anything.

Subtracting the measured `K`:

| selector | raw SR value on G17P | reading |
|---|---|---|
| `0xdd` | ramp `9, 10, 11` across the three vertices | `vertex_id` **is base-inclusive in hardware** (`index + baseVertex`, `baseVertex = 9`) — as EXP-0092 found on M4 |
| `0xd8` | flat `2` | `instance_id` is the **raw instance ordinal**; `baseInstance` is **added in software** |
| `0x88` | `0` | `base_vertex` per `db.json` — reads zero here |
| `0x8a` | `0` | `base_instance` per `db.json` — reads zero here |

**The asymmetry is the driver-relevant result:** `vertex_id` arrives base-inclusive from the
hardware, `instance_id` does not. A back end that assumes both behave alike gets instanced
draws with a non-zero `baseInstance` silently wrong.

**On `0x88`/`0x8a`, the bounded statement.** *In a vertex program that does not declare
`[[base_vertex]]`/`[[base_instance]]`, those selectors read 0 on G17P.* Alternative **not
excluded**: the driver may only arm them when the shader declares the builtin, in which case the
`db.json` enum is right and this carrier simply never asked for them. This is deliberately **not**
recorded as a refutation of the enum — unlike `0xa8`, where the shader asks for nothing and the
register still reads a value that contradicts its documented meaning.

---

## 4. Detection power — every arm proved it before any verdict

Gate zero is the pre-registered liveness ladder plus a case pre-registered to **fail**. An arm
that fails any step has no demonstrated detection power and all its readings — live *or* inert —
stay `untested`; that is the `iter_at.loc` / EXP-0169 failure mode named in advance.

| arm | `L_sr_sel` | `L_dst` | litmus (power probe) | falsifier (must NOT match baseline) |
|---|---|---|---|---|
| compute | `0x82`→`0xa0` **moved** | **moved** — collapses to `SR_BIAS`, i.e. the consumer reads the vacated register | `0x9d` (`threadgroup_position_in_grid.y`, documented 0 here) drove **every lane to exactly 1000** | byte0 bit 2 cleared → bytes decode as `pad_operand`, observation **moved** |
| fragment | `0xa0`→`0xa1` (clean mutual swap, both host-computable, different at 4×4) **moved** | **moved** | `0x9c` flattened `.r` while `.g` and `.a` stayed correct | decodes as `operand_word`, **moved** |
| vertex | `0xd8`→`0xdd` (flat → ramp) **moved** | **moved** — *suppresses the draw entirely* | **moved** | decodes as `UNDECODABLE`, **moved** |

Both gated runs, all three arms. The falsifier is worth one line on its own: clearing byte0 bit 2
so the four bytes are **no longer a `get_sr`** does **not** fault on G17P — it runs clean, writes
the sentinel, and returns the silent-zero pattern. That was verified by hand against the runner
outside the harness, and it is why every `hang` recorded in `work/pilot02`…`pilot05` was an
artefact rather than a device event (§6).

**Tokenization was recorded on every case** (`tok_instr`, `tok_len`, `tok_same_instr`), after
EXP-0169 withdrew `falu2_uni.uni_mode` when its swept values turned out to decode as *different
instructions*. No `sr_sel`, `dp_width` or `dp_marker` value changes the anchor's decoded
identity; the three falsifier mutations do, and are labelled accordingly.

**Round-trip is cited nowhere.** `rt_ok` appears in no record and no verdict of this experiment
(FIELD-SWEEP-PROTOCOL §3(b)).

---

## 4b. Verdicts — `analysis/field_verdicts.json`

| field | label | range | carriers | agreement |
|---|---|---|---|---|
| `get_sr.sr_sel` | **`hardware-run`** | 256 of 256, 256 distinct byte strings | 3 | **100.00 %**, 253/254/253 moved, 0 disagreements |
| `get_sr.dp_width` | **`hardware-run`** | 256 of 256 | 3 | **100.00 %**, 0 disagreements (231 common on the fragment arm; 25 values lost to victims) |
| `get_sr.dp_marker` | **`hardware-run`** | 32 of 32 | 3 | **100.00 %**, 24 moved, 0 disagreements |
| `get_sr.dst` | `untested` *(not ruled on)* | 16 of 16 | 3 | swept and recorded; **EXP-0168 owns this field name** |
| `get_sr.form` | `untested` *(not ruled on)* | 2 of 2 | 3 | swept and recorded; **EXP-0172 owns this field name** |

**`get_sr` is now one field short of emittable, and that field is not mine to rule on.** `sr_sel`,
`dp_width` and `dp_marker` were the three blockers `validation.json` listed; all three clear the
bar. `dst` and `dst_hi` are already emitter-grade (EXP-0168). The remaining field is **`form`**,
which EXP-0172 recorded as `single-template-inference` after finding it inert over its full
2-value range on 8 arms.

**Evidence this experiment adds to `form`, offered as a handoff and not as a ruling:** two more
carriers agree that it is inert — 2 of 2 values, both runs, no movement on the compute or the
fragment arm — and a **third disagrees**: on the **vertex** carrier, `form = 0` moves the
observation and `form = 1` does not, identically in both gated runs. So `form` is not inert
everywhere; it has an observable effect in the vertex stage. That is a live lead for whoever owns
the field, and it is the last thing standing between a G17P back end and an emittable
system-value read.

---

## 5. `tile_read` / `tile_read_mrt` on G17P — the answer to Q2

**Coverage.** 9,428 cases per run × 2 gated runs = 18,856 dispatched cases, over **four**
carriers: two for `tile_read` (`tile_ct2` resolved to `tile_read`, giving the second structurally
different carrier EXP-0164 asked for) and two for `tile_read_mrt`. **Zero measurement failures and
zero `InnocentVictim` cases in either run.**

### 5.1 The answer

> **Yes. EXP-0147's silent-zero hazard reproduces on G17P exactly, on both instructions and all
> four carriers, and it is worse than "no fault": across 256 `rt_index` values on four carriers
> and two runs there is not a single fault. Every wrong render-target index returns a SILENT ZERO.
> In a BG/EOT program that is a black tile with no diagnostic at all.**

`byte+6 bit 0` (`read_en`) is a **read-enable**: `1` reads, `0` returns zero with `STATUS OK`,
the draw completing normally and every other attachment byte-exactly correct. Identical on
`tile_read` and `tile_read_mrt`, identical on both carriers of each, identical in both runs.

### 5.2 Every legal-value set transfers from M4 unchanged

Each row below is EXP-0147's **M4** result on the left and this experiment's **G17P** measurement
on the right. Nothing was tuned to match; the M4 sets were written into `analysis/answers.py`
before the runs as the hypothesis under test.

| field | EXP-0147, M4 | EXP-0178, G17P | verdict |
|---|---|---|---|
| `tile_read.read_en` | bit 0 = read-enable, even → silent zero | **identical**, `1` → `ok`, `0` → `silent_zero` | **`hardware-run`** |
| `tile_read.rt_index` | correct only at `0x00,0x01,0x80,0x81`; others silently zero | **identical**, and **0 faults in 256 values** | **`hardware-run`** |
| `tile_read.dst` | correct only at `0x00,0x01,0xc0,0xc1`; `0xf6`–`0xff` fault | **identical**, hazard **exactly `0xf6`–`0xff`, 10 values, contiguous, on all four carriers** | **`hardware-run`** |
| `tile_read.b7` | correct only at `0xae,0xaf,0xee,0xef`; 85 values nondeterministic | correct at **exactly those four**; movement does **not** reproduce (91.0 % agreement, 23 disagreeing values) | `untested`, and the M4 instability reproduces |
| `tile_read_mrt.read_en` | identical rule to `tile_read` | **identical** | **`hardware-run`** |
| `tile_read_mrt.rt_index` | correct only at `0x08,0x09,0x88,0x89` | **identical**, 0 faults | **`hardware-run`** |
| `tile_read_mrt.dst` | correct only at `0x08,0x09,0xc8,0xc9` | **identical**, same `0xf6`–`0xff` hazard | **`hardware-run`** |
| `tile_read_mrt.fmt` | correct only at `{0x2e,0x2f,0x6e,0x6f,0xae,0xaf,0xee,0xef}`; bits 0/6/7 don't-care, bits 1–5 the selector | **identical, all eight, both carriers, both runs** | **`hardware-run`** |
| `b2`, `b4`, `b6_hi` | splice-inert on the one M4 carrier; EXP-0164 withheld pending a second | **inert again, on two structurally different carriers**, 256/256 and 128/128 `ok` | `untested` — see §5.4 |
| `tail` (32 bits) | bytes gate the read; some values unstable | `tile_read`: 91.7 % agreement → `untested`. `tile_read_mrt`: 99.9 %, 1 disagreeing value → **`isolated-byte-diff`** | as shown |

**The `dst` hazard is the second contiguous wall this experiment mapped inside a gated run.**
`0xf6`–`0xff` — ten values, contiguous, no exceptions, byte-identical across four carriers and two
runs. A per-field hang budget of 2 would have reported "two bad values near the top of the range".

**The silent-zero label identifies which attachment went dark.** The oracle carries one zero
candidate *per attachment* rather than assuming which one the resolved anchor feeds, and the
matching candidate's label is recorded. Every silently-zeroed `rt_index` case on the `tile_read`
carriers is `SILENT_ZERO:rt0`, and every one on the `tile_read_mrt` carriers is
`SILENT_ZERO:rt1` — so the anchor's routing is a *measurement*, not an assumption, and the other
attachments stayed byte-exactly correct throughout.

### 5.3 What a driver must do with this

1. **`byte+6` bit 0 must be 1.** Any even value gives a black tile, `STATUS OK`, no fault.
2. **`rt_index` must be the exact bound index** (`bit 0` and `bit 7` are don't-care, everything
   else is not). An unbound index does not fault on G17P — it returns zero. **Absence of a fault
   proves nothing about whether the read landed.**
3. **`tile_read_mrt.fmt` must be one of the eight legal encodings.** 104 of 256 values silently
   zero.
4. **`dst` must avoid `0xf6`–`0xff`**, which fault, and must be one of the four legal values —
   it is not a plain 8-bit GPR index.

### 5.4 What is still not emittable, and why

Neither instruction is emittable. `tile_read` is blocked by `b2`, `b4`, `b6_hi`, `b7` and `tail`;
`tile_read_mrt` by `b4`, `b6_hi` and `tail`.

`b2`, `b4` and `b6_hi` **never moved on either carrier**, over their full encodable ranges, in
both runs. Under this experiment's frozen rule a never-moving field is promotable only if the
carriers differ **in the dimension the field controls** — and for a `raw`-typed byte with no
semantics that dimension is unknown, so the honest label is `untested` **as a limit of the
carriers, not as "the field is inert"**. That is the same discipline that produced §2 and §3.1,
and after tonight it is not a formality: `sr_sel` looked exhaustively characterised on one carrier
too.

What this experiment *does* add for whoever takes them next: **EXP-0164's stated requirement is
now met.** Its withholding note reads *"Never moved anything on the ONE carrier tried… Needs a
second, structurally different carrier."* There are now two, differing in attachment **count**
(1 vs 2, and 2 vs 3), spatial extent (2×2 / 4×4 / 1×1), the arithmetic consuming the read, and
the presence of a colour store that performs no tilebuffer read at all — and both agree. If the
orchestrator judges that sufficient under the standing policy, the rows are ready; this experiment
declines to make that call for a field whose controlled dimension nobody has identified.

`b7` is different and more interesting: it **moves** (229 of 256 values) but its movement does
**not reproduce** — 91.0 % cross-run agreement, 23 disagreeing values. EXP-0164 withheld it on M4
for the same reason (*"the movement does not reproduce across the two gated runs… Needs a third
gated run"*), and **that instability now reproduces on G17P**, which makes it a property of the
field rather than of one machine's weather.

---

## 7. `get_sr.form` — referred to the orchestrator, not ruled on here

`analysis/field_verdicts.json` → `_referred_for_ruling`.

EXP-0172 owns this field name and **declined** it `single-template-inference` after finding it
inert over its full 2-value range on **8 arms**. This experiment does not label it. It does
contradict that decline on one carrier, so the row is referred **with the numbers** rather than
dropped.

`start = 3`, `width = 1`, `encodable_range = 2`. Full range dispatched on all three stage
carriers, both gated runs, **100.00 % cross-run agreement everywhere, 0 disagreements, 0
measurement failures, 0 victims.**

| carrier | `form = 0` | `form = 1` | reading |
|---|---|---|---|
| `sr_compute` | not moved, both runs | not moved, both runs | **inert** — corroborates EXP-0172 |
| `sr_frag` | not moved, both runs | not moved, both runs | **inert** — corroborates EXP-0172 |
| `sr_vertex` | **MOVED, both runs** | not moved, both runs | **live at `form = 0`** |

**Recommendation: `hardware-run`.** Reasoning, and the caveat, in full:

1. **Coverage.** The field's entire operand space executed, three carriers, twice, perfect
   agreement. `docs/evidence-classification.md` §2 asks for arbitrary operands executed and what
   happened recorded; for a 1-bit field this *is* the whole space.
2. **Gate zero.** All three arms passed their pre-registered ladder and their pre-registered
   falsifier in both runs, so no reading here comes from a carrier that cannot see.
3. **The inert readings are admissible now, and they are not the whole answer.** The standing
   policy is that an inert reading counts only if the carriers differ **in the dimension the field
   controls**. EXP-0172's 8 arms plus my compute and fragment arms agree it is inert — but the
   vertex arm differs in exactly the dimension §3 discovered `sr_sel` is organised by, and it is
   **live** there. *Eight arms that cannot express a field are one arm* — the same argument that
   retired EXP-0169's `sr_sel` null in §2.
4. **The falsifier for an inert verdict has already fired.** A field that moves an observation
   cannot be a don't-care, so `single-template-inference` — whose definition is *"no variation was
   observed"* — is refuted by observation rather than by argument.
5. **Caveat, stated plainly.** The movement is **one value on one of three carriers**, and this
   experiment did **not** identify what `form = 0` *does* in a vertex program, only that it
   changes the result. If a label recording an effect without a semantics is preferred,
   **`isolated-byte-diff` is defensible and is the conservative call.** What is no longer
   defensible is `single-template-inference`.

**Consequence if promoted.** `get_sr`'s six fields would be `sr_sel`, `dp_width`, `dp_marker`
(`hardware-run`, this experiment), `dst`, `dst_hi` (`hardware-run`, EXP-0168) and `form` — i.e.
**`get_sr` becomes emittable and a G17P back end can read a system value.** That is the P0.8
blocker this experiment was dispatched for.

---

## 8. What this experiment did NOT establish

- **`get_sr` is not yet emittable** — see §7. Everything this experiment owns clears the bar; the
  remaining field belongs to another experiment.
- **Neither tilebuffer instruction is emittable.** `tile_read` is blocked by `b2`, `b4`, `b6_hi`,
  `b7`, `tail`; `tile_read_mrt` by `b4`, `b6_hi`, `tail` (§5.4).
- **`b2` / `b4` / `b6_hi` are reported `untested`, not inert.** Two structurally different
  carriers agree they never move, which meets EXP-0164's stated requirement, but the dimension
  those bytes control is unknown and this experiment will not certify a never-mover it cannot
  argue about.
- **What `sr_sel` bit-7-clear encodes is unknown.** It is characterised — one lane of 64 retires,
  the whole program not just the read, faulting in vertex — but not explained.
- **What `form = 0` does in a vertex program is unknown**; only that it changes the observation.
- **`0x88` / `0x8a` are not resolved.** They read 0 in a vertex program that does not *declare*
  `[[base_vertex]]`/`[[base_instance]]`. The alternative that the driver arms them only on
  declaration is **not excluded**, and this is deliberately not recorded as a refutation of
  `db.json`. Only `0xa8` is.
- **The vertex arm's absolute semantic oracle is confounded** by a compiler-inserted
  `+ baseInstance` (§3.5). Its two `ok`s are not cited as validations of anything. A follow-up
  wanting absolute VS system-value semantics needs a carrier whose varying is not passed through
  MSL's `[[instance_id]]` lowering.
- **`b7` and `tile_read.tail` do not reproduce across runs** (91.0 % / 91.7 %). Reported as such;
  EXP-0164's M4 observation of the same instability reproduces rather than being explained.
- **No M4 claim is made.** Every M4 result cited was a hypothesis under test, and §3.1 records the
  one that needed `REFINED` rather than `SUPERSEDED`.
- **Untested parameter space:** one dispatch geometry per stage (grid 64 / tg 64; 4×4 and 2×2
  RGBA32Float targets; one indexed draw shape), one pixel format, `samples = 1` throughout, and
  1,062 of 2³² `tail` values.

## 9. Safe driver fallbacks

- **System values:** emit only selectors from the characterised `0x80`–`0xFF` set, and *never* a
  bit-7-clear selector — in a vertex shader it kills the command buffer, in compute it silently
  writes one lane in 64.
- **Tilebuffer:** `byte+6` bit 0 = 1; `rt_index` exactly the bound index; `fmt` one of the eight
  legal encodings; `dst` one of the four legal values and never `0xf6`–`0xff`. **Do not use
  fault-or-not as a check** — every wrong `rt_index` and every even `read_en` returns `STATUS OK`
  with a black tile.
- **Instanced draws:** `vertex_id` arrives base-inclusive from hardware; `instance_id` does not.
  Add `baseInstance` yourself.
