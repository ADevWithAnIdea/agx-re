# EXP-0204 — pre-registration (FROZEN before any build or device run)

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6,
Metal family Apple9), host `users-MacBook-Neo.local` at `192.168.170.254`. Nothing runs on the M4.

**Clean-room category: OWN-SHADER + HW-PROBE.** Every byte spliced, decoded or inspected is the
compiled form of MSL in `kernels/`, produced by the public Metal API from source we wrote. **No
Apple binary is disassembled, decompiled, symbol-dumped, strings-scanned or otherwise introspected
at any point.**

**Frozen at:** repo revision recorded in `CAPTURE_CONTRACT.json` (`repo_revision`), with the dirty
flag recorded. Per `SUBAGENT_BRIEF.md`, captures are validated against **that recorded value**, not
against live `HEAD` — sibling experiments land continuously and a "HEAD must not move" gate would
abort this one through no fault of its own (EXP-0082).

---

## 1. The question

Four fields, on four texture instructions, each of which blocks its instruction from being
emittable:

| instruction | field | current label | why it is still blocked |
|---|---|---|---|
| `tex_sample` | `mode` | `untested` | never swept; 2 values spliced in RT-5, no per-value records |
| `tex_deriv` | `dstsrc` | `untested` | EXP-0189 withheld **UNSTABLE**: 65 values, 4 arms, 198 observations moved — it failed on **cross-run stability**, not on liveness |
| `tex_write` | `amode` | `untested` | EXP-0163: "STILL-UNDERPOWERED: swept densely on 6 arms but only **2 distinct carriers with proven detection power** (the pre-registered bar is 3)" |
| `tex_write` | `rsv11` | `untested` | identical refusal text |

For each: **can an emitter choose this field's value and get documented hardware behaviour?**

## 2. The rule this experiment is built around

`docs/isa/emit-worklist.md` line 7 — *a field that never moves is promotable only if the carriers
differ **in the dimension the field controls**; two carriers identical in that dimension are ONE
carrier.* This corpus has been burned by it twice, **both times on texture**:

- `tex_sample.samp_extra` read **256/256 INERT on nine arms** and moved on **128/256** on the tenth,
  the explicit-LOD arm — nine arms that could not express the field were one arm.
- `iter_at.loc` read inert on every arm of EXP-0155, then **moved at 4 samples** once EXP-0163 varied
  `rasterSampleCount` — at one sample, centroid and pixel centre are the same point.

So the primary design decision here is **which dimension each field controls**, authored in
`harness/carriers.py::DIMENSION` and repeated in §4 below. **An inert reading from carriers that do
not differ in that dimension is recorded as a CARRIER FAILURE, not as an inert field.**

## 3. Hypotheses, with refuters

Each hypothesis is stated so that a specific observation refutes it.

### H1 — `tex_sample.mode` is a live operation-class selector
`mode` (op+6, bit start 80, width 8) selects the sample-operation class:
`0x10` filtered sample, `0x00` gather/read/sample_compare, `0x20` LOD query.

*Predicted:* the compiler's own baseline `mode` differs across the six carriers and takes at least
two of those three values; and splicing `mode` on a carrier of one class to the code of another
class changes that occurrence's result **in the direction of the other class** (see the oracle, §5).

*Refuters:*
- **R1a** every carrier compiles with the same baseline `mode` → the carriers do not span the
  dimension, and the result is reported as a carrier failure, not as evidence about the field.
- **R1b** `mode` is dense-swept on all six carriers and **nothing moves on any of them** → H1 is
  refuted; the field is reported `untested`/UNRESOLVED with the carrier set stated, **never** as
  inert (§9 of `FIELD-SWEEP-PROTOCOL.md`).
- **R1c** splicing `0x20` onto a filtered carrier produces a value that is neither LOD-shaped nor
  unchanged → the class-selector semantic is refuted even if the field is live.
- **R1d** RT-5's prior negative — "op+6 spliced 0x00/0x10/0x20 on a linear sample: filtering does
  NOT change" — reproduces at `0x00` on `msfilt`. This is pre-registered as an **expected partial
  refuter of the naming**: it would mean 0x10 vs 0x00 is not a filter switch, while 0x20 still
  selects the query. Recorded as such, not quietly dropped.

### H2 — `tex_deriv.dstsrc` is a live packed dst+src operand whose per-value partition is
**reproducible on a quiet machine**
EXP-0172 measured 37 of 39 compared values moving *identically in both runs*, with all cross-run
disagreement (5 values) being `fault` in one run and `InnocentVictim` in the other, at exactly the
values that hang. EXP-0189 withheld it as UNSTABLE.

*Predicted:* on a machine measured to be quiet, two gated runs agree at **≥99 % per value** over the
full pre-registered value set, on both carriers.

*Refuters:*
- **R2a** the runs disagree at ≥1 % of values even with the concurrency measurement showing a quiet
  machine → the instability is a property of the field or the carrier, not of siblings; report
  UNSTABLE and say so.
- **R2b** the machine is measurably **not** quiet during either run → the cross-run figure is
  reported as **CONTAMINATED and NOT USED**, per the coordinator's instruction. A contaminated 97 %
  looks like a refutation when it is only noise.
- **R2c** the hang values `0x3FFFF` / `0x7FFFF` do not reproduce as hangs → EXP-0172's hazard record
  is wrong and is corrected (and, per §3(d), a "hang" that was really a runner artefact is a
  measurement failure, not an observation).

### H3 — `tex_write.amode` is live in an ADDRESS-FORM / OPERAND-SOURCING carrier
The refusal is numeric and precise: 6 arms, only 2 distinct carriers with proven detection power,
bar 3. Those 2 (EXP-0163 `twdim`, `twtype`) are **one carrier in amode's own dimension**: every
write in both is `write(colour, uint2(LITERAL, LITERAL))` at implicit level 0, and both report
`amode == 0x54` on every occurrence.

*Predicted:* at least one of the four new address-form carriers (`twmip` explicit level, `twbuf`
linear texture buffer, `twcube` cube face, `twdyn` register-formed coordinate + no-ALU vec4 data)
either (a) makes the **compiler itself** emit an `amode` other than `0x54`, or (b) makes at least one
spliced `amode` value move the observation.

*Refuters:*
- **R3a** all four new carriers again emit `amode == 0x54` **and** the dense sweep moves nothing on
  any of them → report **UNREACHED with a larger, named carrier set**, explicitly *not* inert. This
  is the outcome the prior experiment chose and it remains the honest one.
- **R3b** a new carrier moves the observation but the two gated runs disagree at >1 % → live but not
  reproducible; `isolated-byte-diff` at most.

### H4 — `tex_write.rsv11` is live in a WRITE-DATA-FORMAT carrier
byte+11's positional sibling in the same 0x67/0xe7 memory family is `device_store.st_desc_hi`, "the
store data-format descriptor tail", and the neighbouring `st_format_ext` is documented as set only
for a **non-4-component** store. Every destination ever swept was 4-component.

*Predicted:* on a 1-component (R32Float) or 2-component (RG32Float) destination, either the
compiler's own `rsv11` is non-zero, or some spliced value moves the observation.

*Refuter:* **R4a** — as R3a. Report UNREACHED with the named component-count carrier, not inert.

### H5 (tier 3, one probe, no promotion possible) — `cubearray_coord_const`
Two independent experiments say the descriptor cannot be provoked from MSL at all (EXP-0148: 0
firings in 1080 files, its signature interior to a `tex_addr_setup` token; EXP-0187: 31 authored
cube constructs, 0 hits). This experiment does **not** re-run either. It runs one different probe:
**splice-synthesis** — write the 4 bytes `f0 c0 04 <b3>` over a known 4-byte instruction in one of
our own carriers and observe whether the program still runs.

*Predicted:* the program runs (the 4-byte length is real) or it does not (framing breaks).
*Pre-registered ceiling:* **whatever happens, `b3` is reported UNRESOLVED**, because the only
detection power such a probe can have is "we deleted the original instruction", which is power in
the wrong dimension. It is run because "the descriptor cannot be reached from MSL, and here is what
happens when it is placed by hand" is a real, bounded, first-class result and the descriptor's
existence is an open orchestrator question.

## 4. Independent variable, controlled variables, dimension per field

| field | INDEPENDENT variable | dimension the carriers span | controlled |
|---|---|---|---|
| `tex_sample.mode` | the 8-bit field value, spliced | sample-operation class: filtered / gather / read / compare / LOD-query | same texture content, same coordinate construction, same target format/size, same triangle |
| `tex_deriv.dstsrc` | the 24-bit field value, spliced | derivative dst/src register allocation | same target, same probe pixels; carrier 2 varies allocation deliberately |
| `tex_write.amode` | the 8-bit field value, spliced | address form / operand sourcing (const vs register coord, implicit vs explicit level, 2D vs cube vs linear buffer, ALU vs direct-load data) | same buffer contents, same target, same reset sentinels |
| `tex_write.rsv11` | the 8-bit field value, spliced | write-data format: component count and width of the destination | as above |

## 5. Oracles — host-computed and DISCRIMINATING

A constant oracle predicts the *instruction*, not the *field*, and `tools/agx-isa/wave_audit.py`
counts distinct oracle payloads. Every case therefore records an `oracle` object whose content
**differs by field value**.

- **`tex_sample.mode`** — `oracle = {"class": C}` where `C` is read off db.json's own enum:
  `0x00 → "gather_read_compare"`, `0x10 → "filtered_sample"`, `0x20 → "lod_query"`, everything else
  `"unspecified"`. The observation is independently classified host-side by the *numeric shape* of
  the probe pixels, using the texture content the harness itself wrote:
  `texel(x,y,L) = x + 100y + 10000L`, depth `= (x+8y)/64`.
  * `lod_query` ⇔ every probed channel is in `[-8, 8]` (an LOD, clamped max 2 over 3 levels);
  * `filtered_sample` ⇔ the channel equals the level-0 bilinear value `x + 100y + 50.5` (±1e-3);
  * `gather_read_compare` ⇔ the channel is an exact integer texel value, or (compare carrier) in
    `[0,1]`;
  * else `"other"`.
  `match` is true iff the classified observation equals the oracle class. **This is falsifiable in
  both directions and its payload takes ≥3 distinct values across the sweep.**
- **`tex_deriv.dstsrc`** — the varyings are linear in `[[position]]`, so every derivative is constant
  over the primitive and host-computable **from our own vertex shader's arithmetic**. The oracle is
  `{"model": "packed_dst_src", "baseline_value": B, "predict": "unchanged" | "changed"}` where
  `predict == "unchanged"` iff the swept value equals the occurrence's own baseline. That is a
  2-valued oracle; it is supplemented per case with the host-computed set of **legal derivative
  values** the carrier can produce (`{"legal_channel_values": [...]}`), so an observation outside
  that set refutes the "packed register operand" model rather than merely counting as movement.
- **`tex_write.{amode,rsv11}`** — `oracle = {"predict": P, "sibling_model": M}` where `M` is
  db.json's own `device_store.addr_mode` vocabulary and `P` is derived per value from it:
  `0x54 → "base_rel_alu_data"`, `0x56 → "direct_load_result_data"`, `0x44 → "indexed_terminal"`,
  `0x64 → "extended"`, else `"unspecified"`; for `rsv11`, `P = "format_tail_zero"` at 0 and
  `"format_tail_nonzero"` otherwise. `match` is true iff the write landed at the modelled
  destination with the modelled data (harness reset sentinels make "did not write" and "wrote
  elsewhere" separable).

## 6. Detection power — what makes a null mean anything

Copied from EXP-0172 because it is the shape that works, and strengthened:

1. **Per-arm detection profile before any sweep.** For every field db.json defines on the
   instruction, splice its bitwise complement and then zero, and record whether the observation
   moved and whether the patched bytes still decode as the same mnemonic **in context**. An arm with
   **no status-OK, same-mnemonic control that moves the observation** has NO detection power; its
   sweeps are recorded and **barred from supporting any verdict, inert or live**.
2. **Positive control in the field's own dimension** (`FIELD-SWEEP-PROTOCOL.md` §9 rule 1). Beyond
   the generic profile, each arm additionally records whether a control **in the named dimension**
   moved: for `amode`, the address-forming fields `coord_pack` / `coord_regs` / `coord_dim` /
   `layer_reg`; for `rsv11`, the data-format fields `data_desc` / `data_desc_hi` / `rsv8`; for
   `mode`, the class-adjacent fields `variant` / `result_desc` / `lod_present`; for `dstsrc`,
   `src_comp` and `b1`. **An inert verdict requires this dimension-specific control to have moved.**
3. **Rule (a), co-variance.** `run.py` splices only the instruction under test at a frozen absolute
   offset and observes fixed surfaces at probe points chosen before the run. No observed quantity is
   a function of the swept value (the EXP-0140 failure shape cannot occur).
4. **Rule (b).** No verdict in this experiment cites a round trip, `rt_ok`, or tokenization.
5. **Faults and `undecodable` are counted SEPARATELY from movement.** A GPU fault is not movement
   (found twice in this corpus this week) and neither is our own disassembler failing to decode.
6. **The width-1 arithmetic trap (§5b).** The gate is `moved >= 2*disagree AND moved > 0`, written
   literally, **not** `moved >= 2*max(disagree,1)`. Self-tested in `analysis/verdicts.py` against a
   synthetic 1-bit field with 0 disagreements before any real verdict is computed.

## 7. Coverage

- `tex_sample.mode` (w=8) — **all 256 values, dense, on all six carriers.**
- `tex_write.amode`, `tex_write.rsv11` (w=8) — **all 256 values, dense, on all five new carriers.**
- `tex_deriv.dstsrc` (w=24) — the pre-registered 65-value set (identical to EXP-0172's rule):
  `{0, 1, 2, 2^24-2, 2^24-1}` ∪ every power of two ∪ every all-ones prefix ∪ 16 hashed interior
  samples. **Hang budget: this field runs as a NAMED MAPPING PASS** (§3(c) of
  `FIELD-SWEEP-PROTOCOL.md`): a per-field budget of 2 is what stopped EXP-0172 at 39 of 65 and it
  "guarantees the region is never mapped". Budget for `dstsrc` is therefore **8 per arm**, declared
  in advance, declared in `PROGRESS.md` as a courtesy, and the run id says so.
- The `cubearray_coord_const` synthesis probe — 256 values of `b3`, one carrier, **no promotion
  possible** (§3 H5).

## 8. The promotion gate (frozen; `analysis/verdicts.py` implements exactly this)

A field is proposed `hardware-run` **only if all of**:

1. **≥2 gated runs** completed on the same frozen carrier and occurrence;
2. **≥99 % per-value cross-run agreement**, computed over values that are valid in *both* runs
   (`InnocentVictim` / `foreign` segregated and reported separately, both figures printed);
3. **`moved >= 2 * disagree` AND `moved > 0`**, with `moved` counting **only** status-OK,
   same-mnemonic, non-hard outcomes;
4. the arm has **detection power** (§6.1) **and** a moved control in the field's **own dimension**
   (§6.2);
5. **V (distinct valid observed payloads) ≥ 2** — a field whose every legal value produced the same
   payload ran legally and was INDISTINGUISHABLE, and its "movement" is a hazard map, not a
   semantic;
6. the machine-quiet measurement (§9) says the runs were not contaminated.

Otherwise: `isolated-byte-diff` if it moved reproducibly at points but the range gate fails;
`untested` / UNRESOLVED if nothing moved. **An INERT label is not available to this experiment for
any of these four fields** — §9 of the protocol declines inert promotions, and all four are already
on the declined/underpowered list.

## 9. Machine-quiet measurement (this is a measurement, not a claim)

`run.py` samples the device process table every 20 s for the duration of every run and appends each
sample to `raw/<run_id>/procs.jsonl`, counting processes whose command matches the other agents'
runner names (`gfrun*`, `frun`, `agxrun*`, `rendersweep`, `shdump`, and `python3 run.py`). A run is
**QUIET** iff no sample outside this experiment's own processes is seen; otherwise it is **BUSY** and
every cross-run figure derived from it is reported as **CONTAMINATED**. `tex_deriv.dstsrc` — the one
field whose whole open question is stability — is only promoted from a QUIET pair.

## 10. Confounders considered

- **Asynchronous `device_load` fabricating a positive against a diff oracle (EXP-0169).** All six
  `mode` carriers and both `deriv` carriers declare **no buffer at all**. The five `tex_write`
  carriers necessarily read a buffer (that is where the write data comes from); the ≥99 % cross-run
  gate is the detector there, and an intermittently landing load cannot reproduce a per-value
  partition twice.
- **The reader-thread cascade (§3(d)).** `harness/runner4.py` uses one pump thread per child tagged
  by owner, and records a malformed response as `MALFORMED` (a measurement failure) rather than as a
  hang. The shared `tools/agxtest/persistrun.py` is **not modified** — siblings are running against
  it.
- **A contaminated dispatch that reports STATUS OK and writes nothing (EXP-0160).** Every read-back
  surface is poisoned with `0xDEADBEEF` before dispatch; an all-poison surface is `POISON`, never
  `silent_zero`.
- **The integrity sentinel.** `gfrun4.m` re-reads every spliced window from the filesystem through a
  separate `NSData` read before the pipeline is built, and pipeline creation uses
  `MTLPipelineOptionFailOnBinaryArchiveMiss`, so "the bytes we chose are the bytes the GPU ran" is
  established through a path independent of the instruction under test.
- **Compiler-chosen occurrences moving between the census and the run.** Every arm freezes the
  instruction's exact bytes and offset at census time and the run aborts that arm if either changed.
- **Metal caching a library keyed on a reused file URL.** Every request writes its own scratch
  archive path (`gReqSeq`).

## 11. Timeouts and safety

- per-request watchdog **15 s**; child restart on timeout; per-run wall-clock deadline passed on the
  command line and recorded.
- `MAX_HANGS_PER_FIELD = 2` for every field **except** the declared `dstsrc` mapping pass (8).
  `MAX_HANGS_PER_ARM = 10`. After two genuine hangs in one area outside the mapping pass, that arm
  stops and is reported PARTIAL (§8 of the protocol).
- majority-of-3 before any `fault`/`hang` verdict; `InnocentVictim` retried up to 8 times and
  segregated as `foreign`.
- every case appended and `fflush`ed as it completes; `PROGRESS.md` written per milestone.
- **`macvdmtool` is never run.** If the neo stops answering the dispatch STOPS and reports BLOCKED.

## 12. Raw record schema (one JSON object per line, `raw/<run_id>/sweep.jsonl`)

```json
{"instr":"tex_sample","field":"mode","value":16,"bytes":"<hex of the patched instruction>",
 "observed":{"status":"OK","hh":{...},"probe":{...},"sentinel":"OK 1"},
 "oracle":{"class":"filtered_sample"},"match":true,"outcome":"ok",
 "carrier":"<arm id>","confirm":{...},"note":""}
```
`outcome` ∈ `ok` | `wrong_value` | `silent_zero` | `fault` | `hang` | `undecodable` | `foreign` |
`unreproduced` | `not_run` | `malformed`. Control records use the reserved field names `_baseline`,
`_detect`, `_detect_summary`, `_dimension_control`, `_baseline_recheck`, `_baseline_final`,
`_cascade_check`, `_arm_not_run`.

## 13. What is NOT claimed

- No result here is generalised to the M4/G16G, and no M4 label is carried onto a G17P row.
- No field is labelled from a round trip, and `rt_ok` is not recorded as evidence.
- `cubearray_coord_const.b3` cannot be promoted by this experiment under any outcome (§3 H5).
- An inert reading on carriers that do not span the named dimension is a carrier failure and is
  reported as UNREACHED, not as an inert field.

---

## 14. AMENDMENT LOG — every change made after the freeze, and when

All five amendments below were made **during pre-freeze calibration, before any gated run
existed**. `CAPTURE_CONTRACT.json` records both `source_hashes` (at freeze) and
`source_hashes_at_run` (after these amendments), so the difference is auditable rather than
silent. **None of them touches a hypothesis, a refuter, the promotion gate, the coverage, the
timeouts, or the raw schema.**

| # | file | what | why |
|---|---|---|---|
| A1 | `kernels/k_mscmp.metal` | the two compare samplers moved from `coord::pixel` to `coord::normalized`, and the coordinate is normalised to match | Metal **refuses to compile** a sampler that combines `coord::pixel` with a `compare_func`. The carrier could not be built at all; the fix is the smallest one that keeps the depth-compare operation class. Recorded in `raw/prefreeze/census_run1.json` as a build failure. |
| A2 | `harness/gfrun4.m` | cube-face `replaceRegion:` gained `bytesPerImage:` | compile error; no behavioural choice involved. |
| A3 | `analysis/census.py` | added `locate()` — the tokenize-prefix-then-anchored-scan rule, **byte-identical in wording and behaviour to `run.py::locate`** | forward tokenization stops early on eight of the thirteen carriers, so the census reported *no* `tex_sample`/`tex_write` occurrence where the run would later have found one. Having the census and the run disagree about occurrence indices is the exact failure EXP-0172 caught and refused arms over. |
| A4 | `analysis/gen_arms.py` | the arm-selection rule was written and refined (span carriers → span baseline values → span (carrier,value) pairs → round-robin fill) | §7 always said the arm list is generated from the census; this is that rule. Its first draft spent the whole `tex_write` budget on three carriers and dropped `twcomp` and `twdyn` — the two carriers that carry `rsv11`'s and the dynamic-coordinate dimension — which would have reproduced the very failure this experiment exists to avoid. |
| A5 | `harness/oracle.py`, `run.py` | exact host-computed baseline predictions added for the five `tex_write` carriers (colour attachment **and** the written texels) | `work/smoke_smoke01` showed `checked=0` for every write arm: the baseline oracle was checking nothing on them, which is the constant-oracle failure §5 exists to prevent. |

### Calibration outcome (`work/smoke_smoke01`, `work/smoke_smoke02` — calibration, not evidence)

- **All 28 arms have detection power**, and every one has at least one moved control **in the
  target field's own dimension**.
- **The host-computed baseline oracle matches the hardware exactly on every arm**: 28/28 channels
  for the sample carriers, 16/16 for the depth-compare carriers (whose nearest-filter channel is
  deliberately not predicted), 52/52 for the four write carriers with constant destinations, 28/28
  for the two dynamic-coordinate write arms, 28/28 for `k_deriv`.
- **One known oracle tolerance, recorded rather than papered over:** `deriv2` agrees on 22/28 —
  the six mismatches are all channel 3, the **half-precision** derivative pair, where the host
  arithmetic is `float` (e.g. observed 333.98438 vs predicted 333.33333). The three `float`
  channels agree exactly. Channel 3 of `deriv2` is therefore reported as *not host-validated*, and
  no verdict rests on it.
- **The pre-freeze census (`raw/prefreeze/census_run2.json`) confirms the carrier set spans the
  dimension for `tex_sample.mode`**: the compiler itself chooses `mode = 0x10` on `msfilt`/`msfixl`,
  `0x00` on `msgath`/`msread`/`mscmp`, and `0x20` on `mslodq`. **All three values db.json documents
  appear as compiler-chosen baselines.** For `tex_write.amode` it chooses **both `0x54` and `0x55`**
  (the latter on the last write of `twbuf` and `twcube`), which no prior experiment's arms contained.
  For `tex_write.rsv11` it chooses **0 everywhere, including the 1-component R32Float and
  2-component RG32Float destinations** — a first, negative, census-level result against H4.
