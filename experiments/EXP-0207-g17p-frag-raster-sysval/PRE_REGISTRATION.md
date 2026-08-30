# EXP-0207 — PRE-REGISTRATION

**Frozen before any build or device time.** Amendments are numbered, dated and appended in §10;
every superseded `CAPTURE_CONTRACT.json` is retained under `raw/prefreeze/`. Nothing above §10 is
edited after the first capture.

**Target:** Apple A18 Pro / **G17P** (`192.168.170.254`, SSH user `user`, `applegpu_g17p`,
`AGXAcceleratorG17P`, 5 cores, macOS 26.6, Metal family Apple9). **Nothing runs on the M4**, which
is the repo host and analysis machine only.

**Repo revision pinned at pre-registration: `f59821fe5e896b09a1bd33b41e7a9f1b7df6b4b4`** (working
tree dirty: 25 paths, all belonging to sibling experiments). Captures are gated on the **authored
blob hashes** in `CAPTURE_CONTRACT.json`, never on live `HEAD` — sibling experiments land
continuously and a "HEAD must not move" gate would abort this run through no fault of its own
(EXP-0082).

---

## 1. The question

Seven fields across six instructions are the last thing standing between those instructions and
emitter-grade status. Every one of them has already been *refused once*, on a recorded basis:

| field | current label | why it was refused, in the record's own words |
|---|---|---|
| `frag_color_store.store_mode` | `single-template-inference` | INERT on 8 arms / 7 carriers / 256 dense (EXP-0163). **Declined again by EXP-0188 without device time**: "needs a fragment-stage render harness" for a pipeline-state dimension. |
| `iter.b9` | `single-template-inference` | INERT on 6 arms / 6 carriers / 256 dense (EXP-0163). Same EXP-0188 decline, same reason. |
| `vtx_coord_xform.operand` | `untested` | **WITHDRAWN 2026-08-30 by EXP-0193**: 1 distinct VALID payload across **817 legal values**; the apparent movement was 987 `no_draw` + 39 `fault` — a reproducible hazard map, not a semantic. |
| `get_sr.form` | `untested` | Declined on eight arms by EXP-0172; promoted by the orchestrator; **that promotion WITHDRAWN 2026-08-30** because all 12 supporting records are `oracle: null` / `foreign: true` and score the unmutated baseline `wrong_value` — no predicted effect was ever established. |
| `get_sr.dst_hi` | `untested` | Withheld INERT-SINGLE by EXP-0189: "8 values dispatched over **1 arm**, 0 observations moved". One arm; the domain is only 8 values. |
| `mesh_out_src.sel` | `tokenization-only` | Declined on a measured 0-occurrence census across 24 carriers — **all 24 of which were COMPUTE kernels for a MESH-STAGE-ONLY op.** EXP-0187 found the first carrier (`mesh_wide`) but only censused it. |
| `dev_scoreboard_fence.scope_flag` | `corpus-correlation` | EXP-0141 synthesised it into a load/ALU/store program that "has no scoreboard/ordering observable". Every value was accepted without fault. |

So the question is **not** "is field X inert". It is:

> For each field, what dimension does it plausibly control; can a carrier be built that differs in
> that dimension **and demonstrates it can differ**, by moving on a control in the *same* dimension;
> and does the field move there, with **more than one distinct VALID payload**?

A field that stays inert on a carrier that provably *can* express its dimension is a materially
stronger result than today's label and is reported as such. A field whose "movement" is entirely
hard outcomes (fault / no_draw / hang / undecodable) is **not** movement, and is reported as the
hazard map it is — the exact defect that withdrew `vtx_coord_xform.operand` this morning.

## 2. What each field plausibly controls, and the dimension built for it

| # | field | dimension it plausibly controls | dimensions ALREADY spanned (do not repeat) | dimension built HERE |
|---|---|---|---|---|
| 1 | `frag_color_store.store_mode` (byte+2, w8, baseline 0x54) | the **memory-family address/store mode**: byte+2 is the same slot as `device_store.addr_mode` (0x54 ALU-data / 0x56 direct-load-data / 0x64 mesh-extended) and `imageblock_store`'s pinned 0x54 | MRT count, tile read, layered/array slice, 4× MSAA centroid, 16-bit attachment, raster-order groups, flat varyings (EXP-0163: cent4, ibhalf, layer, mrt3, tileread, tilerw2, vflat) | **the store's DESTINATION KIND and DATA PATH**: dual-source blend (a second store to the *same* RT that is not an rt_index change), fixed-function blending, **per-sample** shading, `[[sample_mask]]` output, an **integer (RGBA32Uint)** attachment, and a **depth-writing** fragment |
| 2 | `iter.b9` (byte+9, w8, baseline 0) | the **interpolation LOCATION descriptor**, of which `loc` (byte+8) is the documented low half — b9 is the adjacent byte of the same 16-bit tail | wide/half/flat varyings, MRT, 4× centroid, pull-model `interpolate_at_offset` at 1 sample | **per-sample invocation frequency**: `[[sample_id]]`-driven per-sample shading at 4 samples, `sample_perspective`/`sample_no_perspective` qualifiers, and `interpolate_at_sample(dynamic)` at 4 samples. At 1 sample, and under per-*pixel* shading, every sample location collapses to one point — the `iter_at.loc` failure exactly |
| 3 | `vtx_coord_xform.operand` (bytes 5..9, w40) | the **coordinate SOURCE selector** ("reads a vertex-array / constant-indexed coordinate") | one vertex carrier with a single coordinate source and a 4×4 pixel observable (EXP-0147) | **several mutually distinguishable coordinate sources in one program**, and a **16×16** raw-byte observable so a *different but legal* coordinate shows as a different payload instead of collapsing to `no_draw` |
| 4 | `get_sr.form` (byte0 bit3, w1) | a **datapath / width modifier**, documented as set for the position-in-grid SR family | 8 arms with `oracle: null`; movement seen, meaning never established | **a real host-computed oracle**: the joint (`form` × `sr_sel`) space over SRs whose value this project has already documented, in **three stages**, so the ok/silent-zero/wrong pattern is predicted per case rather than merely observed to differ |
| 5 | `get_sr.dst_hi` (byte0 bits 29..31 of the 4-byte word, w3) | the destination-register **extension** (dst = byte0[4:8] \| dst_hi<<4) | **one** compute arm | **stage** (compute / fragment / vertex — the discriminator EXP-0178 measured: 128/128 bit-7-clear selectors fault in VERTEX and none in compute) **and register-allocation baseline** (a high-pressure kernel whose compiled `dst_hi` is already non-zero, so 0 is an off-baseline value) |
| 6 | `mesh_out_src.sel` (byte+1, w8) | which mesh output value feeds the immediately-following device store | **nothing** — never dispatched at all; only ever censused | **the mesh stage itself.** A mesh render pipeline runner, spliced-archive-driven, on `mesh_wide`-shaped carriers |
| 7 | `dev_scoreboard_fence.scope_flag` (byte+3, w8) | memory/scoreboard **scope** of a device-wide fence | a synthesised carrier with no ordering observable (EXP-0141) | a carrier the **compiler itself** emits the fence into (divergent control flow + device atomics + a release/acquire handoff), with an ordering-sensitive observable and an explicit detection-power control |

## 3. Hypotheses, predicted observations, refuters

Each hypothesis names the **oracle** used and at least one **refuter**. "Oracle kind" is recorded on
every raw record so a reviewer can see which cases carry a real host prediction and which carry only
a baseline-equality prediction.

### H1 — `frag_color_store.store_mode` is the memory-family address/store-mode byte
byte+2 sits in the same slot as `device_store.addr_mode`, whose documented values are
{0x04, 0x24, 0x54, 0x56, 0x64}. `frag_color_store` is 0x54 in 130/130 of the corpus and
`imageblock_store` pins 0x54 in its own `match`.

* **Oracle (`structural_partition`, per value, 2 distinct payloads):** values in
  **A = {0x04, 0x24, 0x54, 0x56, 0x64}** → the store executes and the observable equals the baseline;
  every other value → the store does not execute as-written (pixel keeps the clear colour, a
  different payload, or a fault).
* **Predicted if H1 true:** the observable partitions on A, on at least one carrier, reproducibly.
* **Refuter A (inert):** dense-inert on every new carrier while the in-dimension control fires.
  Then the byte is a don't-care across destination kind and data path too — a real
  `proven-dont-care`, reported as `single-template-inference` with a much larger envelope, **not**
  promoted.
* **Refuter B (hazard-only):** values move, but every moving cell is a hard outcome and
  V (distinct VALID payloads) ≤ 1. Then it is a hazard map, reported as such, **not** promoted.
* **Confounders:** (i) the pipeline key of the binary archive must match the render pipeline
  exactly or `FailOnBinaryArchiveMiss` silently refuses — blend/format/samples/depth are therefore
  passed identically to `shdump207` and `rendersweep207`, and a mismatch surfaces as
  `PIPELINE_MISS`, recorded as a build failure, never as an observation; (ii) a dual-source-blend
  fragment emits **two** `frag_color_store`s — the occurrence index is recorded and both are
  resolved separately; (iii) MSAA resolve averages samples, so a per-sample difference is visible
  but attenuated — the observable is the **raw resolved bytes**, compared byte-exactly.

### H2 — `iter.b9` is the high half of the interpolation-location descriptor whose low half is `loc`
`loc` (byte+8) is `hardware-run` and is **known to move at 4 samples and not at 1** (EXP-0163 vs
EXP-0155). b9 is the adjacent byte and the last byte of the 10-byte descriptor.

* **Oracle (`structural_partition`, per value, 2 distinct payloads):** b9 = baseline → observable
  equals baseline; b9 ≠ baseline → the interpolation location changes, so on a carrier where
  sample locations are distinguishable the observable differs from baseline.
* **In-dimension positive control (required before any b9 verdict is filed):** splicing **`loc`**
  on the same arm must move the observable. `loc` is the documented location field; if it cannot
  move on this carrier the carrier does not express the location dimension and b9 is reported
  **STILL-UNDERPOWERED**, not inert.
* **Predicted if H2 true:** some subset of the 256 b9 values changes the resolved pixel on the
  per-sample carriers, and does not on the single-sample control carrier.
* **Refuter:** dense-inert on the per-sample carriers **with the `loc` control firing on those same
  arms**. Then b9 is a don't-care across invocation frequency as well, reported as
  `proven-dont-care` at that envelope.
* **Confounders:** (i) the compiler may lower `[[sample_id]]` fragments without per-sample
  invocation — the census records the compiled `loc`/`mode` per carrier and any carrier whose
  `iter` bytes are identical to an EXP-0163 carrier's is reported as **not a new dimension**;
  (ii) `iter` shares byte0 low bits with other ops — every case records the pinned tokenizer's
  mnemonic and length for the mutated bytes (`tok_same_instr`).

### H3 — `vtx_coord_xform.operand` selects among the vertex program's coordinate sources
EXP-0147's carrier had exactly one coordinate source, so *any* legal alternative selection had
nothing else to select; V = 1 is the expected result of that carrier, not a property of the field.

* **Gate (explicit, and it is NOT an oracle-match gate):** **V > 1 distinct VALID payloads**, with
  `fault` / `no_draw` / `hang` / `undecodable` counted separately and never as movement. The oracle
  recorded is `baseline_equality` and this is stated, not hidden: the operand bytes are left raw by
  design (clean-room rule 5 — the coordinate-select sequence is not reconstructed), so **no
  semantic per-value oracle is authored for this field and none is claimed.**
* **Predicted if H3 true:** on a carrier holding four mutually distinct coordinate sources, at
  least two legal operand values produce two *different, non-degenerate* 16×16 images.
* **Refuter:** V ≤ 1 again. Then the field is reported **withheld, again, on a stronger carrier**,
  and the note says so.
* **Confounders:** (i) a changed clip-space position changes coverage, and a 4×4 target quantises
  that to "same" or "nothing" — hence 16×16 and a raw-byte observable; (ii) `no_draw` is the
  dominant outcome in EXP-0147 and is **hard**, never movement.

### H4 — `get_sr.form` is a datapath/width modifier, so its effect is *conditional on the selector*
`db.json`: "bit3 (form) is a datapath/width modifier (set for the position-in-grid SR family) that
does not change the SR select."

* **Oracle (`sr_value`, per case, many distinct payloads):** for each (stage, `sr_sel`) whose value
  this project has documented, the host computes the expected read-back independently of the GPU
  (lane id, threadgroup dims, grid position, pixel x/y, front-facing, vertex/instance id). Each case
  is then `ok` / `silent_zero` / `wrong_value` against that prediction. **The baseline must score
  `ok`** — a calibration record asserts it, and an arm whose baseline does not match its own
  documented oracle is reported `CALIBRATION_FAILED` and files no verdict. (This is precisely the
  defect that withdrew the previous ruling: 12 records with `oracle: null` scoring the unmutated
  baseline `wrong_value`.)
* **Predicted if H4 true:** the `ok`/not-`ok` pattern over selectors **differs between form = 0 and
  form = 1**, in a way that is stable across runs and stages.
* **Refuter:** the per-selector outcome vector is identical at form = 0 and form = 1 on every arm
  whose selector control fires. Then `form` is inert over the documented selector set and is
  reported as such — no promotion.
* **Confounders:** (i) **stage**, not target, is the discriminator for `get_sr`: EXP-0178 measured
  128/128 bit-7-clear selectors faulting in the VERTEX stage and none in compute; every arm records
  its stage and no cross-stage generalisation is made; (ii) `form` is **width 1** — see §6 rule R5
  on the gate arithmetic, which refuses width-1 fields if written `moved >= 2*max(disagree,1)`.

### H5 — `get_sr.dst_hi` is the destination-register extension, so it is only visible where the destination register is the observable
If `dst_hi` moves the write to `dst + 16*dst_hi`, then the consumer — which still reads the compiled
register — reads whatever the program left there. The *value* is not host-predictable, but the
**class** is: it is not the SR value.

* **Oracle (`dst_routing`, per value, 2 distinct payloads):** `dst_hi` = baseline → the observable
  equals the documented SR value; `dst_hi` ≠ baseline → the observable is **not** the SR value.
* **In-dimension positive control (required):** splicing **`dst`** (the low 4 bits of the same
  register number, `hardware-run`, 15/16 moved in EXP-0168) must move the observable on the same
  arm. Two carriers that cannot both express "the destination register number" are one carrier.
* **Predicted if H5 true:** on an arm whose `dst` control fires, at least one `dst_hi` ≠ baseline
  value changes the observable.
* **Refuter:** `dst` moves and `dst_hi` does not, on all four arms across three stages. That is a
  real and surprising negative and is reported without promotion.
* **Confounders:** (i) `dst_hi` ∈ {6, 7} selects registers ≥ 96, the G17P region EXP-0155 measured
  as a **hang** across seven fields. Rule 3(c) forbids a per-value budget from turning a contiguous
  hazard into an unmapped region, so **all 8 values are dispatched** and hangs are recorded as
  results; a courtesy note goes in `PROGRESS.md` before the run; (ii) a fragment carrier's
  destination register may be re-read by the epilogue, so both a `sr`-consuming and a
  `sr`-plus-arithmetic fragment carrier are built.

### H6 — `mesh_out_src.sel` selects which mesh output value feeds the following device store
* **Oracle (`structural_partition`, per value, 2 distinct payloads):** `sel` = baseline → observable
  equals baseline; `sel` ≠ baseline → a different output value is stored, so the rasterised image
  differs.
* **Gate:** **V > 1 distinct VALID payloads**, hard outcomes separate.
* **In-dimension positive control:** the following 14-byte `device_store`'s own `st_format`/
  `index_reg`, and the `mesh_out_src` occurrence's *neighbouring* occurrence, must be shown to move
  the image — i.e. the mesh output path is observable at all. If the image cannot be moved by
  anything, the arm has no detection power and the field is reported STILL-UNDERPOWERED.
* **Refuter:** dense-inert with the control firing → `proven-dont-care` on the mesh stage.
* **Confounders:** (i) the `mesh_wide` carrier of EXP-0187 emits degenerate geometry (positions
  `float4(lane*0.1, lane*0.2, 0, 1)`) that may cover no pixels — a viewport-covering variant is
  authored **and** the original is kept as the census control, and any carrier that draws nothing is
  reported as such, never swept; (ii) mesh pipelines need their own binary-archive path
  (`addMeshRenderPipelineFunctionsWithDescriptor:`) and their own `__mesh` section carve — a build
  or locate failure is recorded as `NOT_ATTEMPTED`, never as inertness.

### H7 — `dev_scoreboard_fence.scope_flag` selects the fence's memory scope
* **Oracle (`ordering`, per value, 2 distinct payloads):** the carrier's release/acquire handoff has
  a host-computed correct answer; `scope_flag` values that preserve the required scope → correct
  answer, values that do not → a stale or partial read.
* **Detection-power control (required, and this is the point of the arm):** neutralising the fence
  itself must change the observable. If neutralising the fence changes nothing, **the carrier has no
  ordering sensitivity**, the arm has no detection power, and the field is reported
  STILL-UNDERPOWERED **with that null control as the measured proof** — not as inertness.
* **Refuter:** the control fires and the sweep is dense-inert → `proven-dont-care` at that envelope.
* **Confounder:** a race-based observable is nondeterministic. The carrier is therefore built so
  the *correct* answer is deterministic and only a *broken* ordering is nondeterministic; a case
  whose two gated runs disagree is scored a cross-run disagreement, never a movement.

## 4. Independent / controlled variables

* **Independent:** exactly one field's bit-span in exactly one located instruction occurrence, per
  case. Every other byte of the program is byte-identical to the arm's baseline archive.
* **Controlled:** the carrier MSL, the pipeline state (format, MRT count, sample count, blend,
  depth), the draw/dispatch geometry, the input buffers, the pinned tokenizer, the runner binary.
* **Measured, not assumed:** concurrent GPU processes are sampled into each run's `00_env.json`.

## 5. Raw record schema (append-one-JSON-object-per-line to `raw/<run_id>/sweep.jsonl`, flushed + fsync'd)

```json
{"kind":"case","arm":"fcs_dual#1","stage":"fragment","instr":"frag_color_store",
 "field":"store_mode","value":86,"bytes":"e70656...","observed":{"raw":"…hex…"},
 "oracle":{"expect":"store"},"oracle_kind":"structural_partition","match":true,
 "outcome":"ok","class":"BASELINE_EQ","moved":false,"tok_instr":"frag_color_store",
 "tok_len":12,"tok_same_instr":true,"sent_ok":{...},"victim":"","own_fault":false,
 "attempts":1,"restarts":0,"start":16,"width":8,"encodable_range":256,
 "values_dispatched":256,"distinct_bytes":256,"note":"dense"}
```

`kind` ∈ `arm_meta` | `baseline` | `calibration` | `ladder` | `power_probe` | `sensitivity` |
`case` | `arm_done` | `arm_error` | `arm_not_attempted` | `run_stopped`.
`outcome` ∈ `ok` | `silent_zero` | `wrong_value` | `fault` | `hang` | `undecodable` | `no_draw` |
`no_dispatch` | `not_written` | `invalid_run` | `measurement_failed`.
**`measurement_failed` is NOT an observation** (DEF-0178-1) — a malformed runner response keeps its
raw lines and is never scored as a hang or a fault.

## 6. The gate — `analysis/verdicts.py` implements this and nothing else

Verdicts are recomputed from `raw/` on every invocation, never read back from a run manifest.
A field is promoted only if **all** of R1–R8 hold.

* **R1 — two gated runs.** ≥ 2 run directories, each with a matching `00_env.json` whose pinned
  blob hashes equal `CAPTURE_CONTRACT.json`.
* **R2 — cross-run agreement ≥ 99 %** per value on the arm being ruled on, computed over values
  present in both runs.
* **R3 — movement:** `moved >= 2.0 * disagree` **AND** `moved > 0`. Written exactly that way.
  **R5 below is the reason it is not written `2.0 * max(disagree, 1)`.**
* **R4 — V > 1 distinct VALID payloads.** `V` counts distinct `observed` payloads over cases whose
  outcome is **not** hard. **Hard = `fault` | `hang` | `no_draw` | `no_dispatch` | `undecodable` |
  `not_written` | `invalid_run` | `measurement_failed`.** A field whose entire movement is hard
  outcomes is **not** promoted; its hazard map is reported separately. This is the EXP-0193 rule
  applied to my own data before anyone else applies it to me.
* **R5 — width-1 arithmetic.** A 1-bit field has at most one off-baseline value, so any gate
  demanding `moved >= 2` refuses it by arithmetic rather than by evidence (EXP-0178 found this in
  its own frozen text). `analysis/verdicts.py` carries a **self-test** that feeds it a width-1 field
  with 1 move and 0 disagreements and asserts the gate PASSES, and a second that feeds it a field
  whose only movement is faults and asserts the gate REFUSES.
* **R6 — detection power (the INERT conjunct).** An arm may support an **inert** verdict only if
  its `__ladder_*` / `__power_*` / `__sens_*` control records **moved** on that same arm. An arm
  whose observable never moved for a known-live control cannot establish that anything is inert
  (DEF-0190-1). An inert verdict from an arm with no firing control is reported
  **STILL-UNDERPOWERED**, which is not a label and does not enter `field_verdicts.json` as one.
* **R7 — the mutated bytes still decode as the same instruction.** `tok_same_instr` must hold for
  the moving cells, or the "movement" may be the sweep encoding a different instruction (the defect
  that withdrew `falu2_uni.uni_mode`).
* **R8 — the observable must not co-vary with the field.** No arm's read-back path may be indexed,
  addressed or selected by the field under test (EXP-0140/EXP-0168). `analysis/covary.py` asserts
  this per arm from the arm table and fails the run if violated.

**Labels** are the eight of `docs/evidence-classification.md` and nothing else. An inconclusive
sweep is `corpus-correlation` or `untested`; nothing is rounded up. `hardware-run` additionally
requires that arbitrary values executed **with the predicted effect**, so a field with a
`baseline_equality` oracle only (H3) can reach at most `isolated-byte-diff`, and only with V > 1.

**This gate can return "no", and three separate things make it do so:** R4 refuses a hazard map,
R6 refuses an underpowered inert claim, and the R5 self-test refuses a gate that cannot pass a
width-1 field. Each is checked by an assertion in `analysis/verdicts.py::selftest()` that fails the
whole analysis if it does not hold.

## 7. Coverage per field

| field | width | plan |
|---|---:|---|
| `frag_color_store.store_mode` | 8 | **256 dense** on every new carrier arm |
| `iter.b9` | 8 | **256 dense** on every new carrier arm |
| `vtx_coord_xform.operand` | 40 | per constituent byte **dense (5 × 256)** + the structured whole-field set, per arm — the EXP-0147 plan, on new carriers |
| `get_sr.form` | 1 | **2 of 2** values × the documented selector set × 3 stages |
| `get_sr.dst_hi` | 3 | **8 of 8** values × 4 arms, hangs dispatched and recorded (rule 3c) |
| `mesh_out_src.sel` | 8 | **256 dense** per mesh arm |
| `dev_scoreboard_fence.scope_flag` | 8 | **256 dense** on any arm whose detection control fires |

Plus, on every arm: a baseline, a calibration record, a `__ladder_*` chain, a `__power_*` probe in
the field's own dimension, and a `__sens_*` falsifier pre-registered to FAIL.

## 8. Environment, timeouts, safety

* Per-request watchdog **10 s**; build timeout **120 s**; every remote call wrapped in a hard alarm.
* **Per-child reader thread, tagged by owner** (`harness/saferunner207.py`, the EXP-0178 pattern):
  the shared `rsdrv.py` / `persistrun.py` start a fresh reader thread per line and abandon it on
  timeout, after which the abandoned thread wakes on the *replacement* child's stdout and
  manufactures a hang cascade (DEF-0178-1). A malformed response is recorded
  `measurement_failed` with its raw lines, **never** as a hang.
* **No per-field hang budget** (rule 3c). The only stops are a global circuit breaker and a
  harness/device-health stop when the *unspliced* carrier itself will not run after five
  consecutive full recovery cycles.
* Poisoned read-back (`0xDEADBEEF`) on every compute dispatch; for render/mesh carriers the clear
  colour is the poison and an all-clear read-back is `no_draw`, not `silent_zero`.
* Integrity sentinel through a path the instruction under test cannot name, recorded per case.
* OS fault-classification string recorded on every non-`ok` case; `InnocentVictim` / "Ignored (for
  causing prior" are collateral, retried in place first, and never scored as faults.
* `PROGRESS.md` entry per milestone; `raw/` append-only; run ids never reused or topped up.
* **`macvdmtool` is forbidden.** If the neo stops answering: STOP and report BLOCKED.

## 9. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (authored by us) and the AGX bytes the public
                  newLibraryWithSource: API compiled from them
Apple binary introspection: NONE
Reproduction: harness/sync.sh push; harness/verify_remote.py;
              harness/run207.py --run-id <id> --out-root raw; analysis/verdicts.py
Evidence: raw/<run_id>/sweep.jsonl (append-only), analysis/field_verdicts.json
```

`kernels/k_mesh207.metal` reuses the *shape* of `experiments/EXP-0187-g17p-rtword-census/kernels/
k_mesh187.metal`, which is **our own** committed MSL; it is cited as such and is not third-party.

## 10. Amendments

### Amendment 1 — 2026-08-30, BEFORE any gated capture (census only)

`raw/prefreeze/census01/` (the pre-freeze census, run into `work/` and copied to
`raw/prefreeze/`) measured three things that change the carrier set. No gated run had
occurred; `raw/prefreeze/CAPTURE_CONTRACT.v1.json` retains the superseded contract.

1. **`interpolant<>` may not be a VERTEX return type** on this toolchain ("invalid return
   type … field of illegal type `__metal_interpolant_t`"). The pull-model carrier is split
   into a plain-float vertex struct and an `interpolant<>` fragment struct — the shape
   EXP-0163's `k_atoff1` already uses. One compile error in the file had failed the whole
   library, which is why all eight fragment arms reported a build failure.
2. **MSL on this toolchain declares only `memory_order_relaxed`.** `memory_order_release`
   and `memory_order_acquire` are undeclared identifiers. This is a *measured fact about
   the API surface*, recorded as a result: ordering in MSL comes from barriers, never from
   an atomic's own memory order. Both fence carriers now use relaxed atomics plus
   `threadgroup_barrier(mem_flags::mem_device)` — which is exactly the construct `db.json`
   says the compiler decorates with `dev_scoreboard_fence`.
3. **`mesh_wide2` and `mesh_wide3` emit NO `mesh_out_src`, while `mesh_wide` emits exactly
   one (`04 04`).** The rewrite changed too much at once. Three MINIMAL-DELTA carriers are
   added (`mesh_wideP1/P2/P3`) that alter **only the position expression** and keep every
   payload assignment byte-for-byte as `mesh_wide` has it, so a carrier that both emits the
   op and covers pixels can be found by bisection. The original `mesh_wide` stays as the
   census control; `mesh_wide2`/`mesh_wide3` stay as measured negatives.

Also recorded from the same census, unchanged and not amended: `v_pos2` emits **no**
`vtx_coord_xform` (`pattern_absent`) and is retained as a measured negative;
`sr_c`'s compiled `dst_hi` is **1**, not 0, so that arm already carries the two-sided
`dst_hi` baseline the plan hoped the high-pressure kernel would provide; and the compiler
emits **both** `form` values by itself across the five `get_sr` carriers (0 on `sr_c`/`sr_hi`,
1 on `sr_f`/`sr_f2`/`sr_v`) — the strongest available evidence that the carrier set can
express that field.

**Courtesy note (FIELD-SWEEP-PROTOCOL §7):** the `get_sr.dst_hi` sweep dispatches values 6
and 7, which select registers ≥ 96 — the G17P region EXP-0155 measured as a hang across
seven fields. Rule 3(c) forbids a per-value budget from leaving a contiguous hazard
unmapped, so all 8 values are dispatched and hangs are recorded as results.

### Amendment 2 — 2026-08-30, BEFORE any gated capture (census02, still work/ only)

`raw/prefreeze/census02/` measured the carrier set again after Amendment 1. Four results,
one of which changes the plan:

1. **Neither fence carrier emits `dev_scoreboard_fence`** — `occ_absent(0 of 0)` on both,
   reproducing EXP-0141's "no own-MSL kernel we could compile emits `80 02 00 xx`" on a far
   stronger carrier (divergent device atomics **plus** a device-scope barrier). What
   `k_fence_at` *does* emit is the 4-byte sibling `scoreboard_fence` `07 02 00 00` at offset
   34, immediately before the divergent atomics, with a `threadgroup_barrier`
   `07 04 54 85 08 00` (`mem_scope = 0x85 mem_device`) at offset 178.
   **New arm `fen_syn`:** `dev_scoreboard_fence` is `80 02 00 <scope_flag>` — the same
   length and the documented byte0 sibling of that op — so it is **pre-spliced** into that
   exact slot and the sweep runs there. This is still a synthesis, and it is labelled one;
   the difference from EXP-0141 is that the position is a fence site with an ordering
   observable. The arm carries a **detection-power probe on a different instruction** — the
   barrier's own `mem_scope`, 0x85 → 0x41 `mem_none`. **If that probe does not move the
   observable, the carrier has no ordering sensitivity and no `scope_flag` verdict is
   filed** (reported STILL-UNDERPOWERED with the null control as the measured proof).
2. **`mesh_wideP2` emits `mesh_out_src` (`04 04` at offset 40, clean tokenization, followed
   by the 14-byte `device_store` at 42) with non-degenerate geometry.** `me_p2` is the
   sweepable mesh arm. `mesh_wideP1` and `mesh_wideP3` do not emit it (their leftover
   carries `34 04 e7 02 54 …` — a *different* 2-byte source op at that slot), and are kept
   as measured negatives that bound how the op is reached.
3. **`f_dual` compiles to ONE `frag_color_store`, not two** — dual-source blending is fused
   into the fragment program (the census shows `tile_read_mrt` + `falu_acc` + a single
   store), which is the in-shader blend Apple TBDR does. `sm_dual1` (occurrence #1) is
   therefore `arm_not_attempted (1 of 1)`, recorded, not swept.
4. **`f_mask` (a `[[sample_mask]]` output) emits NO `frag_color_store` at all and does not
   tokenize cleanly** (`<unknown>` plus a 20-byte leftover). That is a first-class negative:
   the sample-mask path is a store shape this project's DB cannot yet decode. Recorded; not
   swept.

Also unchanged from census02 and worth stating because it is the single strongest fact
about the `get_sr.form` carrier set: **the compiler emits both `form` values by itself** —
0 on `sr_c`/`sr_hi`, 1 on `sr_f`/`sr_f2`/`sr_v` — and **`sr_c`'s compiled `dst_hi` is 1**, so
the `dst_hi` sweep is two-sided on that arm without needing the high-pressure kernel.

### Amendment 3 — 2026-08-30, BEFORE any gated capture (pilots in `work/` only)

**`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` was published by the user mid-build. It is
normative and it wins where it conflicts with §6 above.** Everything in §6 stays; the
following is added, and the gate implementation in `analysis/verdicts.py` was rewritten to
match. No gated run had occurred (`raw/prefreeze/census0{1,2,3}/`, `work/pilot0{1,2}/`).

1. **Gate A — an actual-byte ledger on every case.** `harness/run207.py::ledger()` reads the
   bytes back out of the *file the runner was handed*, decodes them independently with the
   pinned tokenizer, and records requested value, requested bytes, **actual dispatched
   bytes**, the value decoded from those actual bytes, the program sha256, the instruction
   offset, and the db + harness revisions. `requested == decoded from actual` is asserted
   before any hardware conclusion. Verdicts report **distinct requested values vs distinct
   ACTUAL encodings** and the alias count. A round trip is not this gate.
2. **Gate B — a positive control in every arm, or the arm is `carrier-undecidable`.** Zero
   movement is no longer read as inertness anywhere. The mesh arms gain two `probe_other`
   controls on the 14-byte `device_store` the op *feeds* (`st_format`, `index_reg`), because
   `work/pilot02` showed their only moving control was the destructive byte0 falsifier.
3. **Gate C — liveness is not semantics.** `analysis/verdicts.py::legacy_label()` now
   refuses `hardware-run` whenever `sem_checked == 0`, and refuses it as well when the
   pre-registered predictor was *refuted*; such a field is reported `live; role unknown`
   with the legacy label left at `untested`.
4. **Gate E — the confirmation run uses a reversed case order** (`run207.py --order
   reverse`), and the gate additionally requires the two runs' **actual-byte ledgers to be
   identical per value**.
5. **§6 "Sources and destinations" — a SECOND DISJOINT READBACK PLAN for `get_sr.dst_hi`.**
   New carrier `k_sr_dump` holds **sixteen unique codewords** live and stores **all of them**
   beside the system value, at an index derived from the thread id and never from a field
   under test. A relocated write that lands on a live register clobbers a *named* codeword;
   a single-slot read-back cannot distinguish that from "the write did not move". This is
   the EXP-0168 failure §11 names, addressed directly. `sr_c`'s compiled `dst_hi` is 1 and
   `sr_dump`'s is 0, so the two plans also carry opposite baselines.
6. **§5 Phase 3 — non-affine values.** Every fragment carrier's triangle now carries a
   **different w per corner** (1.0 / 2.5 / 0.625), so perspective-correct interpolation is a
   rational function of screen position while linear interpolation is affine. With w = 1
   everywhere, centre / centroid / sample / perspective / no-perspective all compute the
   *same* number and an interpolation-location field is indistinguishable no matter how it
   is swept.
7. **Verdict shape — six independent axes** (encoding geometry, liveness, semantics,
   compiler recipe, target, reproducibility) with **exact numerators and denominators**
   (encodable, dispatched, distinct requested, distinct actual encodings, legal, silent,
   faults, hangs, no-draws, aliases, untested), never a percentage alone. The safe negative
   wording is `inert in <exact tested envelope>; global role unknown`.
8. **A runner defect found by `work/pilot02` and fixed before any gated run:** a NaN or
   infinity in the convenience `pixels` array printed as the bare tokens `nan` / `inf`,
   which are not valid JSON, so five cases came back unparseable. Per Gate E those were
   recorded `measurement_failed` and **not** as hardware outcomes. The runners now emit JSON
   `null` for non-finite values; the authoritative observable was always the exact `raw`
   byte string, which was never affected.
9. **Baseline robustness.** `sr_v` and `me_w1` lost their baselines to
   `kIOGPUCommandBufferCallbackErrorInnocentVictim` in `work/pilot02` — a sibling's device
   reset, not our encoding. The baseline is now retried through up to four full health
   cycles before an arm is failed.
10. **A pre-spliced arm records the unmodified program's output too** (`kind:
    "pre_reference"`), so whether the `0x07 → 0x80` swap itself changed behaviour is a
    recorded fact rather than an assumption.

**Pre-registered consequence of Gate B for `fen_syn`, stated before the gated runs:**
`work/pilot02` already shows the barrier `mem_scope` probe (0x85 mem_device → 0x41 mem_none)
**not moving** the observable, and the arm's read-back is one constant across all 64 lanes.
If that reproduces in the gated pair, `dev_scoreboard_fence.scope_flag` is reported
**carrier-undecidable** — no verdict — with that null control as the measured proof, exactly
as §3 of this pre-registration said it would be.

### Amendment 4 — 2026-08-30, frozen BEFORE its own first dispatch

The two gated runs `g17p_20260830_run01/02` are **unaffected** by this amendment: they were
captured under the §1–§9 plan as amended through Amendment 3, and their verdicts stand on
that plan. This amendment adds a **new question with its own named captures**
(`g17p_20260830_int01` forward and `int02` reverse), because §4 of
`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` requires a design change made after seeing
observations to be a named amendment frozen before *its* first dispatch, never an edit to a
hypothesis that already has data.

**What run01 showed that raises the question.** `get_sr.form` is inert on five of the six
carriers and **moves on exactly one**: `sr_hi`, the high-register-pressure compute kernel.
There, over the 18-selector map, `form = 1` collapses the output to **one payload for all 18
selectors** while `form = 0` gives six distinct payloads, and the per-lane arithmetic is
exact — `out(form=1) == out(form=0) − lane·65536` for all 64 lanes, i.e. **the system-value
read contributed exactly zero.** The one thing that distinguishes `sr_hi` from the five inert
carriers is its compiled `dp_width`: **0x14 on `sr_hi`, 0x10 on all five others.**

**H8 (frozen now, before the interaction capture):** `get_sr.form` is a **read-enable whose
effect is conditional on `dp_width`**.

* **Predicted:** at `dp_width == 0x14` the two `form` values produce **different** outputs
  (form = 1 contributing a silent zero); at `dp_width == 0x10` they produce the **same**
  output. This must hold on carriers whose *compiled* `dp_width` is 0x10 once `dp_width` is
  spliced to 0x14 — i.e. the effect must follow the **field**, not the carrier.
* **Refuter A:** splicing `dp_width = 0x14` into `sr_c` / `sr_dump` / `sr_f` / `sr_f2` and
  flipping `form` changes nothing. Then the effect belongs to something else about `sr_hi`
  (register pressure, allocation, the destination bank) and H8 is refuted; `form` is
  reported live on one carrier with the cause **unknown**, not as a read-enable.
* **Refuter B:** `form` changes the output at `dp_width == 0x10` too. Then the conditional
  is wrong and `form` is simply live wherever the read is on a path we can see.
* **Coverage:** `dp_width` ∈ {0x00, 0x04, 0x10, 0x11, 0x14, 0x15, 0x50, 0x54} × `form` ∈
  {0, 1}, on all six `get_sr` arms, two gated runs in opposite case order. The values
  bracket the two the compiler emitted and include the documented 0x50 "top dst bank".
* **This is one carrier's finding until the interaction capture confirms it**, and §7 of the
  corrections document wants three structurally different carriers before an
  interaction becomes a general rule. Whatever the outcome, the claim is bounded to the
  tested envelope.

**Gate B is also tightened, and the tightening is applied to run01/run02 as well because it
can only ever refuse, never promote.** A control that moved the observable **only into a
fault, a hang, or a suppressed draw** shows that the program can be *broken*, not that a
different legal result would have been visible. Such a control no longer counts as detection
power. This decides three arms: `fen_syn` (0 of 4 controls moved at all), `me_p2` and `sr_v`
(controls moved, but every one of them only destroyed the observation). All three are
**carrier-undecidable**, and their zero movement is **not** evidence of inertness.
