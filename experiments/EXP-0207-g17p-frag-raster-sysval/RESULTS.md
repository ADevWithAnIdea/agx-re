# EXP-0207 — RESULTS

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores,
macOS 26.6, Metal family Apple9). **Nothing ran on the M4.**
**Clean-room:** `OWN-SHADER` + `HW-PROBE`. Every byte spliced, decoded or inspected is the
compiled form of our own MSL in `kernels/`. **No Apple binary was disassembled or
introspected.**
**Gate:** `PRE_REGISTRATION.md` §6 **as superseded by `RE_EXPERIMENT_PROCESS_CORRECTIONS.md`**
(normative; six independent axes, Gates A/B/C/E, exact numerators and denominators).
Implemented by `analysis/verdicts.py` and nothing else; verdicts are recomputed from `raw/`
on every invocation and the analysis refuses to write anything unless its own self-test
proves the gate can say **no** (six refusal assertions, all passing).

---

## 0. Headline

**Two of the seven fields moved; three are now inert with real detection power on far larger
envelopes; two are honestly `carrier-undecidable`. Nothing was rounded up.**

| field | verdict | liveness axis | semantics axis | legacy label | the number that decides it |
|---|---|---|---|---|---|
| `get_sr.form` | **LIVE** | `live` | **`bounded-map`** | `isolated-byte-diff` | live at `dp_width` 0x14 on **5 of 6** carriers, inert at 0x10 on **6 of 6** — and **the effect follows the FIELD into carriers whose compiler chose 0x10** |
| `vtx_coord_xform.operand` | **LIVE** | `live` | `unknown` | `untested` | **11 distinct VALID payloads** across 1096 legal values (EXP-0147/EXP-0193 had **1** across 817) |
| `frag_color_store.store_mode` | INERT | `accepted-inert` | `hypothesis` (model refuted) | `single-template-inference` | 256/256 × **6 new carriers**, 0 moved, 10/10 controls fired |
| `iter.b9` | INERT | `accepted-inert` | `hypothesis` (model refuted) | `single-template-inference` | 256/256 × 4 carriers incl. **per-sample shading**, 0 moved, `loc` control fires on every arm |
| `get_sr.dst_hi` | INERT | `accepted-inert` | `hypothesis` (model refuted) | `single-template-inference` | 8/8 × **5 arms across 2 stages**, 0 moved, **and a relocated write IS visible** — `dst` clobbers a *named* codeword slot |
| `mesh_out_src.sel` | **CARRIER-UNDECIDABLE** | `carrier-undecidable` | `hypothesis` | `untested` | **dispatched for the first time ever** (256/256) — but no control could move the frame to a different VALID payload |
| `dev_scoreboard_fence.scope_flag` | **CARRIER-UNDECIDABLE** | `carrier-undecidable` | `hypothesis` | `untested` | 256/256 dispatched, **0 of 4 controls moved anything at all** |

**Run hygiene.** 2 gated runs × 6193 / 6192 records, plus 2 interaction runs × 150, in
**opposite case order** (Gate E). **0 hangs, 0 watchdog timeouts, 0 malformed responses, 0
`macvdmtool`.** 11 `invalid_run` (`InnocentVictim`, a sibling experiment's device reset)
retried in place and never scored. Cross-run per-value agreement **100.00 %** on every field
except `sm_dual` (0.9883, 3 victim cases) and the two vertex arms (0.9970 / 0.9978).
**Gate A: 0 ledger failures in 12 685 records** — every dispatched case's requested value
equals the value independently decoded from the bytes actually in the dispatched program,
and the two runs' per-value actual bytes are identical.

---

## 1. `get_sr.form` — LIVE, and it is a **read-enable conditional on `dp_width`**

This row was declined on eight arms, promoted by the orchestrator, and that promotion
**withdrawn** because all twelve supporting records were `oracle: null` and scored the
unmutated baseline `wrong_value`. So the fix was never more arms; it was a predictor.

### Observed

**Step 1 — where it moves.** Six carriers, three stages, `form` ∈ {0, 1} dense, two gated
runs, 100 % agreement. It is inert on five and moves on **one**: `sr_hi`, the
high-register-pressure compute kernel.

**Step 2 — what it does there, checked arithmetically on already-captured data.**
`k_sr_hi` stores `out[tid] = sr + (lane + 1000)·65536`, so a change in the system-value read
is separable from everything else in the word. Across all 64 lanes, in both gated runs:

> **`out(form=1)[t] == out(form=0)[t] − lane(t)·65536` for all 64 of 64 lanes.**

That is exactly "the system-value read contributed **zero**", and nothing else.
Adversarially confirmed by the 18-selector map on the same arm: at `form = 0` the eighteen
documented selectors give **6 distinct payloads**; at `form = 1` they give **1** — the
selector stops mattering because nothing is read.

**Step 3 — the interaction, pre-registered and then tested.** The only thing separating
`sr_hi` from the five inert carriers is its compiled `dp_width`: **0x14 vs 0x10**. That
became **H8**, frozen in `PRE_REGISTRATION.md` Amendment 4 **before** its own capture, with
Refuter A named ("if splicing `dp_width = 0x14` into the inert carriers changes nothing,
the effect belongs to something else about `sr_hi`"). `raw/g17p_20260830_int01` and
`int02` (forward and reverse order) dispatched `dp_width` ∈ {0x00, 0x04, 0x10, 0x11, 0x14,
0x15, 0x50, 0x54} × `form` ∈ {0, 1} on all six arms:

| `dp_width` | 0x00 | 0x04 | **0x10** | 0x11 | **0x14** | 0x15 | 0x50 | 0x54 |
|---|---|---|---|---|---|---|---|---|
| `sr_c` (compute) | same | same | **same ✓** | same | **DIFFER ✓** | same | same | same |
| `sr_dump` (compute) | same | same | **same ✓** | same | **DIFFER ✓** | DIFFER | DIFFER | DIFFER |
| `sr_f` (fragment) | same | same | **same ✓** | same | **DIFFER ✓** | DIFFER | same | same |
| `sr_f2` (fragment) | same | same | **same ✓** | same | **DIFFER ✓** | DIFFER | same | same |
| `sr_hi` (compute) | same | same | **same ✓** | same | **DIFFER ✓** | DIFFER | same | same |
| `sr_v` (vertex) | hard | hard | **same ✓** | hard | same ✗ | hard | hard | hard |

Identical in both runs. **22 of 24 predicted cells as predicted, 2 against** — and both
exceptions are the vertex arm, which is independently `carrier-undecidable` (every control
on it produces `no_draw`).

### Interpretation

> **`get_sr.form` (byte0 bit 3) gates whether the system-value read happens at all, and the
> gate is only armed for certain `dp_width` (byte+2) values. At `dp_width == 0x10` — what the
> compiler emits on five of our six carriers — `form` is inert in both directions. At
> `dp_width == 0x14` (and 0x15), `form = 1` makes the read contribute a silent zero.**

The load-bearing part is that **the effect follows the field, not the carrier**: `sr_c`,
`sr_dump`, `sr_f` and `sr_f2` all compiled `dp_width = 0x10`, and all four became sensitive
to `form` the moment `dp_width` was spliced to 0x14. Refuter A is refuted.

`db.json` currently says `form` is "a datapath/width modifier … that does not change the SR
select". It does not change the *select*; it changes whether the read happens. Recorded as a
`db_defects` candidate — **not applied**, `db.json` is the orchestrator's file.

### Limitations, stated

* Two of 256 `dp_width` values were tested for the conditional (0x10 and 0x14) plus six
  bracketing values. The rule is bounded to that set.
* `0x15` also makes `form` live on four of six arms. That is **unpredicted** and recorded as
  such; a `0x14`-family reading is plausible and untested.
* The legacy label proposed is `isolated-byte-diff`, **not** `hardware-run`: there is a
  predicted semantic effect at the tested points, but the conditioning dimension was sampled
  at 8 of 256 values. What would make it `hardware-run` is a dense `dp_width` × `form` map.

---

## 2. `vtx_coord_xform.operand` — LIVE. The 2026-08-30 withdrawal was a carrier limit, not the field

EXP-0193 withdrew this field the same morning under a criterion it stated precisely:
**1 distinct VALID payload across 817 legal values**, its apparent movement being 987
`no_draw` plus 39 `fault` — a reproducible hazard map. The diagnosis in `PRE_REGISTRATION.md`
§3 H3 was that a carrier holding **one** selectable coordinate source cannot produce a second
valid payload however many values are dispatched.

### Observed (per gated run; identical in both)

| arm | sources in the carrier | dispatched | **legal** | **V (distinct VALID payloads)** | moved (valid) | `no_draw` | `fault` | `invalid_run` |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `vx_multi` | 3 indexed constant arrays | 1338 | 881 | **2** | 4 | 438 | 13 | 6 |
| `vx_wide` | **1 array with 8 distinct entries + a runtime index** | 1338 | 1096 | **11** | 1023 | 239 | 1 | 2 |

Hard outcomes are counted **separately** and are never movement. `tok_same_instr` holds on
every moving cell (Gate R7): the movement is not the sweep encoding a different instruction.
The eleven payloads are not a smear — they cluster by which byte of the 40-bit field was
swept: byte 2 alone produces three of them (33 / 33 / 32 values each), byte 1 two, byte 3
four singletons. The baseline's own payload accounts for only 73 of the 1096 legal values.

### Interpretation

> **Liveness only.** With a carrier holding several mutually distinguishable coordinate
> sources, `vtx_coord_xform.operand` produces **eleven** distinct legal results where the
> single-source carrier produced one. The field is live and it is not a hazard map.

**No semantic claim is made and none is possible from this experiment.** The operand bytes
are left raw by design — clean-room rule 5 forbids reconstructing the coordinate-select
sequence — so the recorded oracle is `baseline_equality`, which is a *liveness* test, not a
model. `analysis/verdicts.py` therefore refuses any semantic label for this field and leaves
it `untested` with `liveness: live`. `tools/agx-isa/wave_audit.py` flags the constant oracle,
correctly; that flag is the honest description of this row, not a defect in it.

---

## 3. Three fields are now inert **with detection power** — a materially stronger negative

All three were previously "inert on carriers that could not express the dimension". Each now
has a control that **moves the same observable to a different valid payload on the same arm**.

### 3.1 `frag_color_store.store_mode` — 6 new carriers, 256/256 dense, 0 moved

EXP-0163 covered MRT / tile-read / layered / 4× centroid / 16-bit / raster-order / flat.
EXP-0188 declined it again without device time for want of a fragment harness. The dimension
built here is the store's **destination kind and data path**: dual-source blend, fixed-function
blending, per-sample invocation, an integer (RGBA32Uint) attachment, a depth-writing fragment,
and a packed 8-bit attachment.

| arm | dimension | dispatched | legal | V | moved | controls fired |
|---|---|---:|---:|---:|---:|---:|
| `sm_dual` | dual-source blend | 256 | 253 | 1 | 0 | 10/10 |
| `sm_blend` | fixed-function alpha blend | 256 | 256 | 1 | 0 | 10/10 |
| `sm_samp` | per-sample invocation, 4 samples | 256 | 256 | 1 | 0 | 10/10 |
| `sm_u32` | RGBA32Uint attachment | 256 | 256 | 1 | 0 | 10/10 |
| `sm_depth` | fragment also writes `[[depth]]` | 256 | 256 | 1 | 0 | 10/10 |
| `sm_r8` | RGBA8Unorm attachment | 256 | 256 | 1 | 0 | 10/10 |

The pre-registered model (H1: byte+2 is the memory family's address/store mode, so
{0x04, 0x24, 0x54, 0x56, 0x64} store and everything else does not) is **refuted**: 5 of 256
predicted cells hold, and they hold only because those five are the ones predicted to behave
like the baseline. **`inert in this envelope; global role unknown.`**

### 3.2 `iter.b9` — the per-sample dimension, and the control proves the dimension is live

`iter.b9` had only ever been swept under **per-pixel** shading. Here it is swept with
`[[sample_id]]` forcing **per-sample** invocation at 4 samples, with each sample's own
interpolated values written to a poisoned device buffer so no resolve average can hide a
permutation, on a triangle whose **corners carry different w** so perspective interpolation
is genuinely non-affine.

| arm | samples | shading | dispatched | V | moved | `loc` control moved? |
|---|---:|---|---:|---:|---:|---|
| `it_ps4` | 4 | per-sample | 256 | 1 | 0 | **yes** (both `loc` steps + `__power_loc`) |
| `it_ps4b` | 4 | per-sample, 2nd occurrence | 256 | 1 | 0 | **yes** |
| `it_ps1` | 1 | per-sample (control arm) | 256 | 1 | 0 | **yes** |
| `it_atsamp` | 4 | `interpolate_at_sample(dynamic)` | 256 | 1 | 0 | **yes** |

`loc` is byte+8; `b9` is byte+9 — the adjacent byte of the same descriptor tail. The
location field moves the observable on every arm; the byte beside it does not, at any of its
256 values. **`inert in this envelope; global role unknown.`**

### 3.3 `get_sr.dst_hi` — inert, and this time a relocated write *would* have been seen

The prior withholding was "8 values, one arm, 0 moved" — the EXP-0168 co-variation failure
that `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` §11 names. §6 of that document prescribes the
fix, and it was built: **two disjoint read-back plans**, the second (`k_sr_dump`) holding
sixteen **unique codewords** live and storing *all* of them beside the system value at an
index derived from the thread id and never from a field under test.

| arm | stage | plan | dispatched | legal | V | moved | `dst` control |
|---|---|---|---:|---:|---:|---:|---|
| `sr_c` | compute | single slot, compiled `dst_hi = 1` | 8 | 8 | 1 | 0 | moves |
| `sr_dump` | compute | **16 codewords + SR**, compiled `dst_hi = 0` | 8 | 8 | 1 | 0 | moves **and clobbers codeword slot 9** |
| `sr_hi` | compute | high register pressure | 8 | 8 | 1 | 0 | moves |
| `sr_f` | fragment | pixel read-back | 8 | 8 | 1 | 0 | moves |
| `sr_f2` | fragment | read consumed through arithmetic | 8 | 8 | 1 | 0 | moves |
| `sr_v` | vertex | — | 8 | **1** | 1 | 0 | **only `no_draw`** → carrier-undecidable |

The decisive detail is the codeword ledger. Splicing `dst` (the **low** half of the same
register number) to 10 relocates the write onto a live register and **clobbers named codeword
slot 9**; splicing `dp_width` to the documented 0x50 "top dst bank" clobbers **slot 8**.
Splicing `dst_hi` across all eight values clobbers **nothing** and changes nothing.

> So the read-back plan can see a relocated write, and `dst_hi` does not relocate one.
> `db.json` says `dst = byte0[4:8] | (dst_hi << 4)`, reaching r0..r127. **On G17P, byte+3
> bits 5-7 do not extend the destination register; what moves the destination bank is
> `dp_width` (byte+2).** Recorded as a `db_defects` candidate, not applied.

In the **vertex** stage `dst_hi` ∈ 1..7 suppresses the draw entirely (7 of 8 values). That is
a hazard map on an undecidable carrier and is reported as one, not as a semantic — the same
error that withdrew `vtx_coord_xform.operand`.

---

## 4. Two fields are `carrier-undecidable`, and that is the honest result

`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` Gate B: if the positive control fails, **zero movement
is not evidence of inertness**. This experiment tightened Gate B further — a control that
moves the observable only into a *fault*, a *hang* or a *suppressed draw* shows the program
can be **broken**, not that a different legal result would have been visible.

### 4.1 `mesh_out_src.sel` — dispatched for the first time, on a runner that did not exist

The prior decline rested on a 0-occurrence census across 24 carriers, **all of them compute
kernels for a mesh-stage-only op**. EXP-0187 found the first carrier that emits it. It was
still never dispatched, because **no runner in this repository could execute a spliced mesh
pipeline**. `harness/meshsweep207.m` is that runner, and it works:

* `mesh_wideP2` emits `mesh_out_src` `04 04` at offset 40, cleanly tokenized, followed by
  the 14-byte `device_store` at 42 — with **non-degenerate geometry that actually covers
  pixels**. (The EXP-0187 carrier `mesh_wide` puts every vertex on the line *y = 2x*, so it
  rasterises nothing; it is retained as the census control and its baseline is recorded as a
  measured `no_draw`.)
* All 256 `sel` values dispatched, both runs, 100 % agreement over the 127 legal values.
* **129 of 256 values suppress the draw entirely.** The other 127 produce one payload.

**But the arm has no demonstrated detection power.** Its two `device_store` probes and its
byte0 falsifier move the frame only into `fault` / `no_draw`; nothing we could splice made
the mesh output path show a *different legal* frame. So the 127-value inertness establishes
nothing, and only the 129-value hazard map is a finding. `mesh_out_src.sel` stays
`tokenization-only`; what changed is that it is now **sweepable**, and the next experiment
needs a mesh carrier whose output value is separately observable.

### 4.2 `dev_scoreboard_fence.scope_flag` — the carrier cannot see ordering, and that was pre-registered

Two carriers built exactly to `db.json`'s own description ("the compiler inserts it around
divergent control flow and before atomics/calls") — divergent device atomics plus
`threadgroup_barrier(mem_flags::mem_device)` — emit **zero** occurrences of the op. They emit
the 0x07 `scoreboard_fence` sibling instead. So the op was **pre-spliced** into that exact
slot (`07 02 00 00` → `80 02 00 00`, same length, documented byte0 sibling), immediately
before the divergent atomics, and all 256 `scope_flag` values were dispatched: **all legal,
no faults, no hangs, one payload, 100 % agreement.**

The arm's whole standing rested on one pre-registered control: **drop the device-scope
barrier (`mem_scope` 0x85 `mem_device` → 0x41 `mem_none`) and the observable must move.**
It did not — nor did any of the other three controls. `PRE_REGISTRATION.md` §3 H7 said in
advance that this outcome means the carrier has no ordering sensitivity and **no verdict may
be filed**, and none is. The measured null control is the result.

*(A useful negative recorded along the way: MSL on this toolchain declares only
`memory_order_relaxed`. `memory_order_release` and `memory_order_acquire` are undeclared
identifiers, so ordering in MSL comes from barriers, never from an atomic's own memory order.)*

---

## 5. Facts established that were not the question

1. **A `[[sample_mask]]` fragment output emits no `frag_color_store` at all** and its program
   does not tokenize — one `<unknown>` record and a 20-byte leftover
   (`a2113f15801003c09f015410031e600014041215`). An undecoded store form; recorded as a gap.
2. **Dual-source blending fuses into ONE store**, not two: `f_dual` returns
   `[[color(0), index(0)]]` and `[[color(0), index(1)]]` and compiles to a single
   `frag_color_store` preceded by `tile_read_mrt` + `falu_acc` — the in-shader blend Apple
   TBDR does. `sm_dual1` (occurrence #1) is `arm_not_attempted (1 of 1)`.
3. **`get_sr.sr_sel = 168` contradicts its documented meaning.** `db.json` calls it
   `threadgroups_per_grid.x`; under `dispatchThreads(64)` / `threadsPerThreadgroup(64)` —
   one threadgroup — it returns **64**, the same value selector 152
   (`threads_per_threadgroup.x`) returns, where the documented reading predicts 1. Selectors
   169/170 return 1, which both readings predict. It is the **only** selector where the host
   oracle was refuted, and it was refuted identically at `form = 0` and `form = 1`, so it is
   not a `form` effect. Candidate correction: 168 reads a grid size **in threads**.
4. **A carrier census is evidence.** `mesh_wideP1`/`P3` and `mesh_wide2`/`3` emit no
   `mesh_out_src`; `v_pos2` emits no `vtx_coord_xform`; `f_mask` emits no
   `frag_color_store`. Each is recorded as a measured negative that bounds how these ops are
   reached, rather than as a silent gap in the arm table.
5. **A runner defect, found and fixed before any gated run.** A NaN or infinity in the
   convenience `pixels` array printed as the bare tokens `nan` / `inf`, which are not valid
   JSON, so five pilot cases came back unparseable. Per Gate E they were recorded
   `measurement_failed` and **not** as hardware outcomes; the runners now emit JSON `null`
   for non-finite values, and the authoritative observable was always the exact `raw` byte
   string, which was never affected.

---

## 6. What was directly observed vs what is interpreted

**Directly observed:** every number in §§1–5, from `raw/g17p_20260830_run01`,
`run02`, `int01`, `int02` and `raw/prefreeze/`, all append-only, each case carrying its
actual-byte ledger.

**Interpreted:** (a) that `form` is a *read-enable* rather than some other gate that happens
to zero the result — the evidence is the exact per-lane arithmetic and the collapse of the
18-selector map to one payload, which no other reading explains as simply; (b) that
`dst_hi` is not a register extension **on G17P, on these carriers** — the alternative
"it extends a register nothing in these programs reads" is bounded by the codeword ledger,
which would have caught a write landing on any of sixteen live registers, but not one landing
outside them; (c) that `vtx_coord_xform.operand` selects among coordinate sources — the eleven
payloads are consistent with it and this experiment did **not** establish which value selects
which source, and does not claim to.

**Not excluded:** for every INERT row, that the field is live in a dimension no carrier here
spans. That is why the wording is `inert in <exact tested envelope>; global role unknown` and
why nothing was promoted to `hardware-run`.

**Target:** every result is `G17P-direct`. No M4 result is cited as a premise anywhere.

---

## 7. Exact numerators and denominators

`analysis/summary_table.txt` (per arm, per run) and `analysis/field_verdicts.json` (per
field, with the six axes). Never a percentage alone.

| field | encodable | dispatched | distinct actual encodings | legal | silent | faults | hangs | no-draw | aliases | untested |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `frag_color_store.store_mode` | 256 | 256 | 256 | 256 | 0 | 0 | 0 | 0 | 0 | 0 |
| `iter.b9` | 256 | 256 | 256 | 256 | 0 | 0 | 0 | 0 | 0 | 0 |
| `get_sr.form` | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| `get_sr.dst_hi` | 8 | 8 | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| `mesh_out_src.sel` | 256 | 256 | 256 | 127 | 0 | 0 | 0 | 129 | 0 | 0 |
| `dev_scoreboard_fence.scope_flag` | 256 | 256 | 256 | 256 | 0 | 0 | 0 | 0 | 0 | 0 |
| `vtx_coord_xform.operand` | 2^40 | 1334 | 1334 | 1092 | 0 | 1 | 0 | 239 | 0 | 2^40−1334 |

(Best arm per field; `analysis/field_verdicts.json` carries every arm.)

---

## 8. How this could still have failed to say "no", and what stops it

* **A gate that cannot refuse.** `analysis/verdicts.py::selftest()` asserts six refusals and
  fails the whole analysis if any is missing: a fault-only field is refused; a width-1 field
  with 1 move and 0 disagreements is *accepted* (the arithmetic bug EXP-0178 found in its own
  text); an inert claim from an arm with no firing control is refused; a **destructive-only**
  control is refused as detection power; a broken actual-byte ledger is refused; and liveness
  with `sem_checked == 0` — or with only a `baseline_equality` oracle — cannot reach a
  semantic label.
* **Hard outcomes counted as movement.** `V` counts distinct payloads over **non-hard** cases
  only, and every table above prints the hard counts beside it. `mesh_out_src.sel` and
  `dev_scoreboard_fence.scope_flag` come out `V = 1`, which is what withdrew
  `vtx_coord_xform.operand` this morning; both are refused.
* **Our own disassembler failing counted as hardware movement.** `tok_same_instr` is recorded
  on every case and Gate R7 refuses a field whose moving cells stopped decoding as the
  instruction. 0 such cells.
* **Requested bytes that were never dispatched.** Gate A reads the bytes back out of the file
  the runner was handed and decodes them independently: **0 ledger failures in 12 685
  records**, and the two runs' per-value actual bytes are identical.
* **An order-dependent artefact.** The confirmation run dispatches every field's values in
  **reversed** order.
* **A busy machine.** Sibling experiments were running throughout; `00_env.json` records the
  concurrent GPU processes as a measurement. 11 `InnocentVictim` cases were retried in place
  and never scored, and no result in this document rests on a single observation.

The one thing that would still get past all of it: a field that is live only in a dimension
none of these thirty carriers varies. Section 6 says so, and every negative here is worded to
leave that open.

---

## 9. Proposed labels

`analysis/field_verdicts.json`, keyed `<mnemonic>.<field>`, with `label`, `range`, `target`,
`evidence`, `note`, `start`, `width`, the six axes, and the exact counts including
**distinct VALID payloads, legal values and hard-outcome counts kept separate**. Six
`db_defects` candidates are recorded there too, with evidence and **not applied** —
`tools/agx-isa/db.json` is the orchestrator's file.
