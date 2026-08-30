# PRE-REGISTRATION — EXP-0178: can a compiler back end emit a system-value read on G17P, and does the silent-zero tile-read hazard reproduce there?

**Frozen before any build, any SSH and any dispatch.** Everything below was written
against committed evidence only; no device was touched while it was drafted. Exploration
after this freeze lives in `work/` under `pilotNN` ids and is **retained, not reused**;
nothing in `work/` is evidence.

**Target:** **A18 Pro / G17P** — `users-MacBook-Neo.local`, `192.168.10.243`,
`AGXAcceleratorG17P`, arch `applegpu_g17p`, 5 GPU cores, macOS 26.6, Metal family Apple9.
Closure is measured against **full G17P** (`CLAUDE.md`, user directive 2026-08-28). The
local M4 is the repo host and analysis machine only. **No M4 claim is made anywhere in this
experiment**, and no M4 result is promoted; the M4 evidence cited below is the *prior* this
experiment tries to reproduce or refute **on a different target**.

**Governing documents:** `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md` (including the five rules added 2026-08-30),
`docs/evidence-classification.md`.

**Repo revision at freeze:** `12e059e5aab38258c55ce490a01e146e6fae30d9`, working tree dirty
(four EXP-0169 analysis artefacts and two of its raw run directories). Per
`SUBAGENT_BRIEF.md`'s pinned-revision rule this experiment's cross-run gate compares
**authored blob hashes**, never live `HEAD`: a sibling experiment landing between run01 and
run02 is not a gate failure.

---

## 1. The two questions, and why they are the right two

`EXP-0177` assembled P0.8 / DRV-ABI-01 — the VS/FS/CS stage ABI, the only closure row that
had cited no experiment at all — and ranked what blocks it. These are its top two.

### Q1 — `get_sr.sr_sel` is `untested` on G17P, so **no system value can be emitted at all**

Every `[[thread_position_in_grid]]`, `[[vertex_id]]`, `[[instance_id]]`, `[[base_vertex]]`,
`[[base_instance]]`, fragment pixel X/Y, `[[front_facing]]` and helper-thread read goes
through `get_sr`. `tools/agx-isa/validation.json` (`generated: 2026-08-28`,
`db_sha256 a77f8cfa…`) marks `get_sr.sr_sel`, `.dp_width` and `.dp_marker` all **`untested`,
target G17P, evidence EXP-0169**, each recorded as *"0..255 dense (all 256 values) … 1
carriers"* with the note *"no (arm,carrier) passed its liveness ladder"*. Only `dst` and
`dst_hi` are emitter-grade. **The instruction is therefore not emittable**, and a clean-room
compiler back end cannot read a single builtin on the documentation target.

**Why EXP-0169's sweep produced nothing — root-caused here, from its own committed files.**
Its `GET_SR` arm ran a *lifted* `k_sr` probe inside a synthesized program at
**grid=1 / tg=1**; `harness/casematrix.py:78` states the relaxation explicitly
(*"with grid=1/tg=1 every SR this harness reaches is deterministic"*). At that geometry
essentially every reachable special register reads **0**, so `L_sr_sel` could not move and
the ladder failed. `RESULTS.md` §8 reports it honestly as a limit of the carrier, not as
"the field is inert". The fix is not a new investigation: it is a dispatch geometry and a
carrier in which distinct selectors produce distinct **host-computable** patterns — which is
what our own **EXP-0092** used to produce the strongest field characterization in the
repository, exhaustively over `0x00–0xFF` across two gated runs. On **M4**.

### Q2 — `tile_read` / `tile_read_mrt` are measured only on M4

Every field of both instructions carries `target: M4` in `validation.json`; neither is
emittable. EXP-0177 calls this *"the cheapest large win in the row: the harness, the
carriers, the oracle and the liveness probe all exist and only the target changes."*

The specific fact to carry across and re-verify is a **driver-safety** fact:
**byte+6 bit 0 is a read-enable whose EVEN values return a SILENT ZERO rather than
faulting** — and so does a wrong `rt_index`. In a BG/EOT program that is a **black tile,
not a loud failure**. An implementer must have this; it is the difference between a bug that
announces itself and one that ships.

**A documented negative on either question is worth more than a promoted field elsewhere.**

---

## 2. Hypotheses, expected observations and refuters

**H1 (sysval emittability).** On G17P, `get_sr.sr_sel` has a decidable partition of its full
256-value encodable range into values an emitter may use and values it may not, observable
through carriers in which the read reaches a read-back.

*Expected if true:* on the compute carrier, selectors with a documented meaning reproduce
their **host-computed** 64-thread patterns; the sweep separates into at least two distinct
observation classes over the 256 values.
*Refuter:* the observation does not move for **any** selector **and** the liveness ladder
shows the measurement could not have seen a change anyway — in which case `sr_sel` is
reported `untested` **again**, as a limit of these carriers, and this experiment's headline
answer to "can a compiler back end emit a system-value read on G17P?" is **no, still not
established**, stated plainly.

**H2 (bit 7 is a structural discriminator).** EXP-0092 found on M4 that `sr_sel` bit 7 splits
the space exactly: `0x80–0xFF` reads the special-register file; `0x00–0x7F` **materializes the
selector byte itself** into the destination at a single fixed slot; and **no value anywhere in
`0x00–0xFF` faults**.
*Expected if it transfers:* the same 128/128 split on G17P, with `out[0] == sr_sel` exactly
for every bit-7-clear value on the compute carrier.
*Refuter:* any G17P selector that faults or hangs; any bit-7-clear value that does not
materialize; any bit-7-set value that materializes. **This is a cross-target test with a real
chance of failing** — `EXP-0141` vs `EXP-M4-14` already produced one genuine A18↔M4
divergence (`tg_addr_compute`), so "M4 said so" is a hypothesis here, never a premise.

**H3 (stage-contextual namespace).** EXP-0031 established that the SR namespace is
stage-contextual. Two carriers in the same stage are therefore **one carrier** for this
field.
*Expected if true:* the fragment carrier resolves `0xa0`/`0xa1` as pixel X/Y and the vertex
carrier resolves `0xdd`/`0xd8`/`0x88`/`0x8a` as vertex_id / instance_id / base_vertex /
base_instance, while the compute carrier resolves the thread/threadgroup family — i.e. the
**same selector byte means different things in different stages**.
*Refuter:* a selector that reads the same value in all three stages where the documented
meanings differ, or a stage in which the documented meaning does not appear at all.

**H4 (tilebuffer read-enable and rt_index).** On G17P, `tile_read`/`tile_read_mrt` byte+6
bit 0 gates the read: odd values read, **even values return a silent zero, with no fault**;
and a wrong `rt_index` also returns a silent zero rather than faulting.
*Expected if true:* on the tile carriers, all 128 odd byte+6 values give the byte-exact
correct pixel and all 128 even values give the byte-exact **zero oracle**; `rt_index` is
correct only on a small set and silently zero elsewhere.
*Refuter:* any even byte+6 value that reads correctly; any wrong `rt_index` that **faults**
instead of zeroing (which would be a *better* world for a driver and must be reported as
such); or a pattern that does not reproduce across the two gated runs at the promotion bar.

**H5 (`fmt` selector).** `tile_read_mrt.fmt` is correct only at
`{0x2e,0x2f,0x6e,0x6f,0xae,0xaf,0xee,0xef}` — bits 0, 6, 7 don't-care, bits 1–5 the format
selector.
*Refuter:* any other value correct, or any of those eight not correct, on G17P.

---

## 3. Sweepability check — run before designing anything

`python3 tools/agx-isa/match_overlap_report.py` (run 2026-08-30 against the pinned
`db.json`, sha `a77f8cfa…`). It reports **34 fields that overlap their own descriptor
`match`**, of which 0 have zero free bits under this db revision.

**None of `get_sr.*`, `tile_read.*` or `tile_read_mrt.*` appears in that list.** Every field
under test has its full nominal encodable range and none is a one-legal-value pseudo-field.
The geometries this experiment will use, read from the **pinned** db and from nothing else:

| field | start | width | encodable range |
|---|--:|--:|--:|
| `get_sr.sr_sel` | 8 | 8 | 256 |
| `get_sr.dp_width` | 16 | 8 | 256 |
| `get_sr.dp_marker` | 24 | 5 | 32 |
| `get_sr.dst` *(foreign)* | 4 | 4 | 16 |
| `get_sr.form` *(foreign)* | 3 | 1 | 2 |
| `tile_read.b2 / .dst / .b4 / .rt_index / .b7` | 16/24/32/40/56 | 8 | 256 |
| `tile_read.read_en` | 48 | 1 | 2 |
| `tile_read.b6_hi` | 49 | 7 | 128 |
| `tile_read.tail` | 64 | 32 | 2^32 |
| `tile_read_mrt.dst / .b4 / .rt_index / .fmt` | 24/32/40/56 | 8 | 256 |
| `tile_read_mrt.read_en` / `.b6_hi` / `.tail` | 48 / 49 / 64 | 1 / 7 / 32 | 2 / 128 / 2^32 |

Note the pinned db has **already** split EXP-0147's `b6` into `read_en` (bit 0) + `b6_hi`
(bits 1–7), so this experiment sweeps them as two fields rather than as one byte, and counts
`encodable_range` accordingly.

---

## 4. Independent variables, carriers, and the co-variation audit

### 4.1 The rule that shapes the design — FIELD-SWEEP-PROTOCOL §3(a)

> The observable must not CO-VARY with the field under test.

EXP-0140 swept `uniform_mov.dst` with a read-back built as `device_store(data_reg = D)`
where `D` **was** the swept dst, so a correct hardware result was a constant observed vector
**by construction** and *"16 values, 0 moved"* was the **passing** outcome of a test that
could not return anything else. EXP-0168 then committed the same defect with r15 and had to
retract. The defect is invisible in the results and visible only in the design, so it is
checked **mechanically, before the freeze**, by `analysis/covary_audit.py`
(→ `analysis/covary_audit.json`, verdict **PASS**, 45 fields checked, 0 errors).

What that check asserts, per arm and per field:

* the mutated bytes are **only** `[abs_off, abs_off + descriptor length)` of the resolved
  anchor — exactly one instruction is ever spliced per case;
* the instruction that **produces the observable** is a different instruction, declared per
  arm in `never_spliced`, and is never touched;
* at least one **integrity channel** is produced on a path the field under test cannot name,
  so "the observation did not move" is falsifiable rather than tautological;
* for a **destination-selecting** field the consumer is **not** relocated with it — moving
  `dst` alone must *break* the consumer's read, so a correct hardware result is a **changed**
  observation, never a constant one.

`get_sr` is precisely where this risk lives, because the destination register and the value
read are easy to entangle. They are not entangled here: in every `get_sr` carrier the value
travels through a **later, separate** instruction and reaches memory through a store whose
own operands come from somewhere else.

### 4.2 The three `get_sr` carriers (one per stage — H3 makes that mandatory)

All three are in `kernels/sysval.metal`.

**C_COMPUTE `k_sr_c`** — body identical to our own EXP-0092 `srprobe.metal`, plus a second
output buffer carrying an integrity sentinel. Dispatched at **grid = 64, tg = 64**, the
geometry EXP-0169 lacked. The `get_sr` under test reads `[[thread_index_in_simdgroup]]`
(baseline selector `0x82`); a **separate, later** add (+1000) consumes it and a **third,
separate** `device_store` writes `out[gid]`, where `gid` comes from a **different, unspliced**
`get_sr` (`0xa0`). This is the later-read discipline of
`docs/isa/register-move-and-liveness.md`, required after EXP-0086 found a producer-side bit
that corrupts only a *later separate* instruction's read. Observable: 64 words.

**C_FRAG `v_full` / `f_sr`** — 4×4 RGBA32Float. The fragment `[[position]]` read lowers to
two `get_sr` (`0xa0` = pixel X, `0xa1` = pixel Y). `.r` carries the register under test,
`.g` carries the **other, unspliced** one, `.b` a second differently scaled reading of the
same value (which would expose an aliased or partial write), and `.a` the uniform alone.
`.g` and `.a` are integrity sentinels on paths the instruction under test cannot name.

**C_VERTEX `v_sr` / `f_sv`** — 4×4, drawn **indexed** with indices `{0,1,2}`,
`baseVertex = 9`, `baseInstance = 5`, `instanceCount = 3`. `[[vertex_id]]` (`0xdd`) drives
the triangle's **geometry** and is never spliced, so the rasterised coverage is constant
across the whole sweep; `[[instance_id]]` (`0xd8`) is the register under test and feeds an
interpolated varying. The four vertex-stage system values are then mutually distinguishable:
`vertex_id` → a spatial **ramp** 9,10,11; `instance_id` → **flat 7** (last instance wins);
`base_vertex` → **flat 9**; `base_instance` → **flat 5**. `[[base_vertex]]`/`[[base_instance]]`
are HW-VALIDATED on **M4 only** (EXP-0092); this carrier is what puts them on G17P.

An indexed draw is the only Metal form that gives `[[base_vertex]]` a non-zero value, so
`harness/rendersweep.m` gains that one capability over our EXP-0147 original and nothing
else; the default path is byte-for-byte the old one.

### 4.3 The four tilebuffer carriers

All in `kernels/tilebuf.metal`. `f_tile` and `f_mrt` reproduce our EXP-0147 carriers exactly,
so the G17P numbers are directly comparable to the M4 numbers they must confirm or refute.
`f_tile2` and `f_mrt3` are the **second, structurally different** carriers EXP-0164 demanded
before any never-moving field can be ruled on:

| arm | carrier | attachments | size | differs from its sibling in |
|---|---|--:|---|---|
| `tile_ct1` | `v_arr`/`f_tile` | 1 | 2×2 | *(the EXP-0147 reference)* |
| `tile_ct2` | `v_arr`/`f_tile2` | 2 | 4×4 | attachment **count**, spatial extent, the arithmetic, and a second store that performs **no** tilebuffer read |
| `mrt_cm1` | `v_arr`/`f_mrt` | 2 | 1×1 | *(the EXP-0147 reference)* |
| `mrt_cm2` | `v_arr`/`f_mrt3` | 3 | 2×2 | attachment **count** (widening exactly the dimension `rt_index` selects) and spatial extent |

The clear colour is both the tilebuffer's resident value **and** the fixed-function integrity
sentinel: it is written by hardware on a path that cannot involve the fragment program, so a
pixel still holding it exactly means nothing was drawn. Gate **G3** of `harness/selftest.py`
proves offline that for every carrier the **correct** value, **every** silent-zero candidate
and the **clear** colour differ in **every component of every pixel** — without that, a
silent zero is indistinguishable from "the draw never happened", which is the EXP-0141 trap.

`tile_ct2` may compile to either `tile_read` (`67 0e 54`) or `tile_read_mrt` (`67 06 54`).
The resolution rule is frozen: the anchor actually present in the compiled bytes is recorded
in `raw/<run>/00_arm_resolution.json` **before the first gated dispatch**, the arm is
attributed to the instruction found, and its field list is **intersected** with that
descriptor's real field names. If neither anchor is present the arm is reported
**NOT ATTEMPTED** with that reason, never guessed at.

---

## 5. Coverage, oracles, ladder, falsifier

**Coverage (FIELD-SWEEP-PROTOCOL §3.3).** `w ≤ 8` → **every** value of the encodable range.
`w > 8` (`tail`, 32 bits) → every value of each constituent **byte** with the others held at
baseline, **plus** the structured whole-field set: `{0,1,2,max−1,max}`, all 32 powers of two,
and 16 asymmetric interior values. Gate **G7** checks this offline.

**Oracles.** Every expected value is computed on the **host**, before any dispatch, in
`harness/sweepplan.py`, and is never adjusted to match an observation.

* *Sysvals* use two tiers, following EXP-0169's shape. **Tier 1 (semantic)** is the value the
  **pinned `db.json` enum claims** for that selector, evaluated at this dispatch geometry —
  so a mismatch **falsifies the documented meaning** and is recorded as such. **Tier 2
  (movement)** is the unmutated baseline, which is defined for every case including
  undocumented selectors. Selectors with no documented meaning in a stage carry
  `oracle = null` and are classified by the analysis (`KNOWN_MATCH` / `ALIAS` / `CONSTANT` /
  `STRUCTURED` / `IDENTITY_MATERIALIZE`) exactly as EXP-0092 reported the same sweep on M4.
  **A `wrong_value` outcome on an undocumented selector is the informative result, not a
  defect**, and the analysis says so.
* *Tilebuffer* oracles are exact float32 formulas compared **bit-exactly**, with one
  silent-zero candidate **per attachment** — because which attachment the resolved anchor
  feeds is read from the compiled bytes, not assumed. The matching candidate's label is
  recorded, so `SILENT_ZERO:rt1` is itself evidence about `rt_index` routing.

**Two calibrations, both confirmed against the baseline before any swept case is classified,
never fitted per case:**

1. `threadExecutionWidth`, read from the compute pipeline's own build log. A device
   *configuration* value that parameterises the oracle; not an observation of the field.
2. The fragment **pixel-centre offset** `C` in `pos.x = f(SR) + C`. The instruction supplying
   it is a documented open question (EXP-0177 §4). The pre-registered value is `0.5`, and the
   baseline selector is the documented pixel-X register, so `(.r − px)` must be **one
   constant across all 16 pixels**. If it is not, the affine model is **refuted**, the
   fragment arm's *semantic* oracle is withdrawn and only the movement oracle stands. Both
   the pre-registered value and the measured one are recorded.

**Liveness ladder (gate zero).** Pre-registered mutations that **must move**. A carrier that
fails any step has no demonstrated detection power and **all** its readings — live *or*
inert — stay `untested`. This is the `iter_at.loc` / EXP-0169 failure mode, named in advance.

| arm | ladder | power probe (must land on a specific host-computed value) |
|---|---|---|
| `sr_compute` | `sr_sel` 0x82→0xa0 (lane pattern → grid pattern); `dst` relocation | `sr_sel` → 0x9d: `threadgroup_position_in_grid.y` is 0 in a one-threadgroup dispatch, so every slot must read exactly `SR_BIAS` |
| `sr_frag` | `sr_sel` 0xa0→0xa1 (pixel X → pixel Y, a clean mutual swap); `dst` relocation | `sr_sel` → 0x9c: `.r` must lose its spatial structure while `.g` and `.a` stay correct |
| `sr_vertex` | `sr_sel` 0xd8→0xdd (flat 7 → ramp 9,10,11); `dst` relocation | `sr_sel` → 0x9c: the varying must go flat while `.a` stays correct |
| `tile_*`, `mrt_*` | `dst` and `rt_index` relocation | byte+7 → 0x00 must collapse the read to **zero**, so the pixel falls to the no-read oracle on every pixel and every component (EXP-0147's litmus) |

Gate **G4** proves offline that each ladder's two selectors are host-distinguishable, so the
step *can* move.

**Falsifier — a case pre-registered to FAIL.** Per arm, a `sensitivity` mutation whose
observation **must not** equal the baseline: for `get_sr`, clearing byte0 bit 2 so the four
bytes are no longer a `get_sr`; for the tilebuffer arms, corrupting byte+1, part of the
descriptor match. If everything passes, the sweep proves nothing about our ability to detect
a difference.

**Round-trip is NOT cited anywhere.** FIELD-SWEEP-PROTOCOL §3(b): `roundtrip_test.py` passes
unmodified against an assembler that could not clear a bit, and with `falu3.srcA`↔`srcB`
swapped. `rt_ok` appears in no record of this experiment and in no verdict.

**Tokenization is recorded per case.** EXP-0169 withdrew `falu2_uni.uni_mode` after its own
tokenization column showed the two values tokenize as **different instructions** — the
"movement" was the sweep encoding something else entirely. `get_sr.sr_sel` is exactly that
shape of field, so every case records the mnemonic and length the **pinned** tokenizer
decodes from the spliced anchor (`tok_instr`, `tok_len`, `tok_same_instr`). Any case where
the anchor stops decoding as its own descriptor is excluded from the field's verdict and
reported separately.

---

## 6. Known confounders

1. **Absence of a fault proves nothing.** EXP-0169's DSTORE arm (2026-08-30) found that a
   `device_store` through an unbound binding slot is **silently dropped** — only `0x00` and
   `0x80` store at all, and the other 254 values give no fault and no diagnostic. The
   tilebuffer read-enable is in the same silent-failure family. The **poison** is what
   distinguishes the three states: the compute read-back is pre-filled with `0xDEADBEEF`
   and a sentinel buffer proves the dispatch ran, so "sentinel written **and** read-back
   still poison" is a distinct outcome, `not_written`, and is never recorded as
   `silent_zero`.
2. **Contamination can destroy an observation but never fabricate a coherent one**
   (EXP-0160). Non-`ok` cases are re-run in place first — a sibling's reset makes the very
   next submission a victim and a *fresh* child's first request just becomes the next victim
   (EXP-0147 measured this) — and the OS fault-classification string is recorded on every
   one. `Discarded (victim…)` / `Ignored (for causing prior…)` are segregated as
   `invalid_run`, never as `fault`.
3. **A contaminated dispatch can report `STATUS OK` and write nothing**, with no victim
   string anywhere (EXP-0160 saw 25 such). The clear-colour sentinel (render) and the poison
   + sentinel buffer (compute) adjudicate that offline, from data already captured.
4. **Spliced ≠ compiler-emitted.** A splice is `HW-VALIDATED`-tier evidence for the *field's*
   legality and effect; it is not proof that Apple's compiler ever emits that value. Nothing
   here claims otherwise.
5. **Cross-target inference is a hypothesis, not a premise.** The M4 results are what this
   experiment tries to reproduce; `EXP-0141` vs `EXP-M4-14` already produced one genuine
   A18↔M4 divergence.
6. **`DEF-0169-1`: `device_load` on G17P is asynchronous.** Not applicable here by
   construction — no carrier seeds an operand with `device_load`; the compute inputs are
   host-written and the shaders only store.
7. **Compiler determinism.** Every arm records its full compiled `program_hex`, the anchor
   offset and the anchor's bytes in `arm_meta`, in both runs, so a toolchain change between
   runs is visible rather than silent.

---

## 7. Safety — and why there is no hang budget

`FIELD-SWEEP-PROTOCOL §3(c)`: **a per-field hang budget cannot characterise a contiguous
hazard — it guarantees the region is never mapped.** `frag_color_pack.dst` has an exact wall
at `0xC0`; three experiments walked into it and none saw it, because a budget of 2 discovers
exactly two more bad values per run. EXP-0168's own "defer the known-bad values" fix only
moved the wall, twice.

So this experiment has **no per-field budget and no per-arm abort**: every planned value of
every field is dispatched regardless of outcome. That is how EXP-0169's DSTORE arm mapped two
contiguous fault walls **exactly, inside the gated run** — `device_store.index_reg` faults iff
`(v & 0x60) == 0x60` (64 values, zero counterexamples, both carriers, both runs) and
`extmode` faults iff `v ≥ 0xFC` — with no mapping pass. EXP-0168 separately showed the device
survives such a region: 64 hangs, no reset, no wedge, no `macvdmtool`. The only stop is a
**global circuit breaker at 128 hangs per run** against a runaway, recorded if it fires.

**Courtesy notice (FIELD-SWEEP-PROTOCOL §7):** the `tile_read.dst` / `tile_read_mrt.dst` arms
sweep byte+3 over 0..255. EXP-0147 recorded `fault` at `0xf6–0xff` on M4, and the analogous
register-ceiling crossing **hangs** on G17P (EXP-0155, seven fields). Hangs are possible
there, and `PROGRESS.md` carries the notice.

**`get_sr.dst_hi` is deliberately NOT swept.** Values 6–7 select registers ≥ 96, which is the
G17P hang region EXP-0155 measured across seven fields; the field is already `hardware-run` on
G17P via EXP-0168; and nothing here needs it. The exclusion is recorded in
`sweepplan.py::ARMS[*].not_swept` and in `00_arm_resolution.json`, so the omission is
auditable rather than silent.

Every device operation has a hard timeout (10 s per request), the persistent runners have
watchdogs that kill and respawn, every case is appended and `fsync`'d before the next one
starts, and `PROGRESS.md` gets an entry per arm. A kill costs at most one case.
**If the neo stops answering: STOP and report BLOCKED.** No `macvdmtool`, no scanning.

---

## 8. Runs, promotion gate, and what gets written

**Gated pair:** `g17p_20260830_run01` and `g17p_20260830_run02`, both arms, both runs
identical in every parameter. Pilots run first under `work/pilotNN` and are retained, never
reused. A run id is never reused or overwritten.

**Concurrency:** sweeps run unlocked per `FIELD-SWEEP-PROTOCOL §7`. The orchestrator has
confirmed the machine is otherwise idle for this window; EXP-0179 will announce before it
dispatches. Concurrency is recorded rather than claimed: `00_env.json` per run, and any
victim string on any case.

**Promotion gate (frozen):**

| term | value |
|---|---|
| `gate_zero` | the arm's liveness ladder moved on **every** step in **both** runs, and its pre-registered falsifier failed as pre-registered |
| `min_agree_pct` | **99.0 %** per-value cross-run outcome agreement |
| `moved_over_disagree` | movement ≥ **2.0 ×** the number of disagreeing values, and > 0 |
| `min_common_values` | 2 |
| coverage | `hardware-run` additionally requires the **full** encodable range for `w ≤ 8`; otherwise the ceiling is `isolated-byte-diff` |
| never-mover | promotable **only** if the carriers differ in the dimension the field controls. That dimension is unknown for every `raw`-typed byte here, so a never-moving field is reported **`untested` with the reason**, never "inert" |
| foreign | `get_sr.dst` (EXP-0168) and `get_sr.form` (EXP-0172) are **swept and recorded but never ruled on** |

Gate **G6** proves offline that this gate is both satisfiable and refusable, including that a
failed ladder refuses promotion and that an all-agreeing but never-moving field is refused.

**Labels** come from `docs/evidence-classification.md` §2 and nothing else.

**Per-case record** (`raw/<run_id>/sweep.jsonl`, one object per line, flushed + `fsync`'d):
`idx, t, kind, arm, carrier, stage, instr, field, value, bytes, observed, oracle, match,
outcome, class, moved, tok_instr, tok_len, tok_same_instr, sent_ok, victim, own_fault,
sentinel_bad, attempts, restarts, foreign, start, width, encodable_range, values_dispatched,
distinct_bytes, note`. `distinct_bytes` counts **distinct spliced byte strings**, never the
dispatched-value count.

`outcome` ∈ the frozen protocol enum `ok | silent_zero | wrong_value | fault | hang |
undecodable`, plus four **documented** extensions established by earlier experiments and
listed in `CAPTURE_CONTRACT.json`: `invalid_run` (collateral damage from another context —
says nothing about our encoding), `no_draw` / `no_dispatch` (the integrity sentinel proves
the work never executed), and `not_written` (the dispatch ran but the read-back is still
poison — the silent-drop mode EXP-0169's DSTORE arm found).

**Deliverables:** `RESULTS.md` answering both headline questions in plain words,
`analysis/field_verdicts.json` with flat `<mnemonic>.<field>` keys per §5, `manifest.json`,
and every raw record. **No `git commit`. No edits to `db.json`, `validation.json`, `docs/`
or `PROVENANCE.md`.**

---

## 9. Clean-room attestation

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/sysval.metal and kernels/tilebuf.metal (authored by us for this
  experiment; f_tile / f_mrt / v_arr reproduce our own EXP-0147 carriers, k_sr_c reproduces
  our own EXP-0092 srprobe), and the AGX bytes the public newLibraryWithSource: API compiled
  from them.
Apple binary introspection: NONE. No Apple binary, framework, kext or firmware is
  disassembled, decompiled, symbol-dumped, strings-scanned or debugged. The only machine code
  inspected or spliced is the compiled form of MSL we wrote.
Reproduction: harness/selftest.py ; harness/sync.sh push|build ;
  harness/run.py --run-id <id> --out-root raw ; analysis/verdicts.py --run01 .. --run02 ..
Evidence: raw/<run_id>/{00_env.json,00_arm_resolution.json,sweep.jsonl,02_summary.json}
Pinned toolchain: pinned/{isadb.py,db.json,agxparse.py}, sha256 in CAPTURE_CONTRACT.json,
  resolved by absolute path with a hard failure if absent.
```
