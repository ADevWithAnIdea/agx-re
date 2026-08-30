# EXP-0187 — RESULTS

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6,
Metal family Apple9). **Nothing ran on the M4.**
**Clean-room:** `OWN-SHADER` + `HW-PROBE`. Every byte spliced, decoded or inspected is the compiled
form of our own MSL in `kernels/`. **No Apple binary was disassembled or introspected.**
**Gate:** `PRE_REGISTRATION.md` §6, implemented by `analysis/verdicts.py` and nothing else.

---

## 0. Headline

**Nothing is promoted, and the reason is stated rather than smoothed over: the gated PAIR did not
complete inside the run window.** What the one complete run does establish is a hardware fact that
contradicts the field's current label:

> **`n4_rt_word.dst` is NOT "framing only". It has an exact, reproducible hazard rule:
> `dst & 0b110 == 0b100` — 64 of 256 values — faults the command buffer with `ErrorHang`, on two
> independent carriers, with zero exceptions.** The other 192 values run clean and return the
> correct ray-query answer.

`validation.json` records the field as `tokenization-only`, *"framing only (round-trips; no value
semantics established)"*. 128 command-buffer faults in one run say otherwise. **The field keeps its
label** — one run is not two, and FIELD-SWEEP-PROTOCOL §5 forbids rounding up — but the next agent
should not re-derive this from scratch.

| item | result |
|---|---|
| `n4_rt_word.dst` | **NOT-GATED** (`untested` retained). 256/256 dense on 3 occurrences, 3 carriers; **128 moved**; hazard rule exact |
| `cubearray_coord_const` | **31 constructs authored and compiled, 0 signature hits, 0 walk hits** → bounded negative |
| `mesh_out_src` | **EMITTED** — first carrier ever found: `mesh_wide` mesh stage, 1 walk-confirmed occurrence |
| `n4_cf_word` | signature hits in 8 constructs, **0 walk-confirmed** → still no tokenizable carrier |
| instructions moved across the emittable line | **0** |

---

## 1. `n4_rt_word.dst` — the hazard rule (single run, NOT gated)

**Observed** (`raw/g17p_20260830_run02`, 961 cases, one run):

| arm | carrier / path | baseline `dst` | dispatched | distinct bytes | encodable | moved | outcomes |
|---|---|---:|---:|---:|---:|---:|---|
| `rq_mdist#0` | committed distance, triangle | `0x42` | 256 | 256 | 256 | **64** | 192 ok / 64 fault |
| `rq_inst#0` | instancing traversal | `0x22` | 256 | 256 | 256 | **64** | 192 ok / 64 fault |
| `rq_ccount#0` | candidate count, triangle | `0x42` | 256 | 256 | 256 | **0** | 256 ok |

Every one of the 256 values still re-decodes as `n4_rt_word` under the pinned tokenizer
(`encodable_range = 256`), so **the movement is not the sweep encoding a different instruction** —
the failure that withdrew three fields on 2026-08-30.

The faulting set is identical on the two moving arms and is exactly

> **`fault ⟺ (dst & 0b110) == 0b100`**

verified in both directions by `analysis/single_run_summary.py`: every one of the 64 faults
satisfies it and **no** clean value does. Bit 0 and bits 3..7 are irrelevant to the hazard; only
bits 1..2 decide it. All 368 fault classifications are `ErrorHang`; the 187 `InnocentVictim`
responses were retried first and are not scored.

**Interpretation.** `dst` is a structured selector, not framing: a 2-bit sub-field at bits 1..2
selects something the traversal hardware rejects at one of its four values, and the rejection is a
contained command-buffer error, not a device wedge. This is the same *shape* EXP-0184 found one
instruction over — `rt_query_traverse.dst` modelled 4 bits wide with only 2 live — but here the live
bits are **interior** (1..2) rather than at either end, and they gate legality rather than
correctness.

**What this does NOT show.** (a) It is **one run**; the two-run gate is not met and nothing is
promoted. (b) `rq_ccount#0` is fully inert across all 256 values *while its carrier-level control
fires*, so the occurrence is either not executed or the field is dead there — the two are not
separated. (c) The 192 clean values all return the *correct* answer, so no value has been shown to
select a *different working* destination; the field's positive semantics remain undecoded.

### The controls, and the one that did not fire

* **Carrier-level (`rt_query_traverse.opB`)**: fired on all three carriers — 8–9 of 9 values moved
  at occurrences `rtq6` / `rtq7` on `rq_mdist` and `rq_inst`, and at `rtq0`/`rtq6` on `rq_ccount`.
  This reproduces EXP-0184's reachability finding (only a couple of the fourteen rtq occurrences are
  on the executed path) on three new carriers.
* **Same program point (`if_push.scope_kind` at `off+4`, `rq_inst#0`)**: **16 of 16 values `ok`, did
  NOT fire.** Stated plainly because it is the weaker outcome: the strongest control available to
  this instruction produced no detection power at the one occurrence that had it.
* **Whole-word liveness probes (byte+2, byte+3, 96 dispatches)**: **all `ok`, none moved.** So the
  two fixed match bytes of `n4_rt_word` are inert on these occurrences *while `dst` bit 2 faults the
  command buffer* — the match bytes are not a proxy for the word being live, and a liveness probe
  built on them would have returned a false negative.

## 2. Target 2 — the opcode census (31 constructs, no device sweep)

`analysis/census.json`. Two numbers per construct: **signature hits** (the raw `match`-satisfying
byte pattern — an upper bound, since a hit may be another op's operand tail) and **walk hits** (the
mnemonic a resync tokenizer walk from offset 0 actually produces — the number that decides whether a
carrier exists).

* **`cubearray_coord_const`: 12 cube / cube-array constructs authored — plain cube sample, cube-array
  sample, nearest, explicit LOD, gradientcube, bias, gather (both), depth-cube-array
  `sample_compare`, half, cube-array `read`, and a dynamic-index dependent-direction shape — plus 19
  further constructs. 0 signature hits and 0 walk hits in all 31.** This is a **bounded negative**:
  *31 constructs tried, none emitted it.* It independently reproduces EXP-0148 (0 firings in 1080
  corpus files) and EXP-0184 (0 occurrences over 24 carriers) on G17P with constructs chosen
  specifically to provoke the cube face-select math. **Recommendation: this descriptor should be
  treated as unbuildable from MSL, not as an untested field.**
* **`mesh_out_src`: EMITTED — and this is the first time.** `mesh_wide` (12 vertices / 4 primitives,
  wide per-vertex and per-primitive payloads), **mesh stage**, 8 signature hits of which **1 is
  walk-confirmed**. The five other mesh constructs (one triangle, per-vertex-only, line topology,
  dynamic primitive count, no-object) give signature hits but **0** walk hits. Every previous census
  read 0 because all 24 carriers were compute kernels and this op is mesh-stage-only — the census was
  blind by construction, and `pinned/shdump_mesh.m` + `pinned/mesh_extract.py` (EXP-0135's own tools)
  fix that. **A carrier now exists; the sweep does not.**
* **`n4_cf_word`: 8 constructs carry the `04 01 00` signature (52 hits in the ray-query kernel, and
  1–2 in `k_cf_divbar`, `k_cf_ret`, `k_cf_simd`, `k_cu_dyn`, three mesh stages) but 0 are
  walk-confirmed.** Consistent with EXP-0172's DEF-0172-4 and with the tokenizer limitation in §4.

## 3. Why nothing is promoted — the run record, in full

Three captures exist. **All three are retained; none was topped up, deleted, or had its id reused.**

| run | arms | cases | fate |
|---|---|---:|---|
| `run01` | the **pre-amendment** 211-arm set | 2284 records | Started under the driving session's 2-minute command timeout, which killed the SSH channel; the remote process kept writing. **Defective as a gated half — it executed a different arm set from the frozen contract** (exactly EXP-0179's stale-harness failure). Retained, never paired. |
| `run02` | the frozen 25-arm set | 961 cases, 248 s | **The one complete run.** `rq_bbox` reported `carrier_start_failed` ("did not print READY in time") and contributed nothing; the other three carriers ran fully. |
| `run03` | the frozen 25-arm set | 80 records | Died on `rq_bbox#0` at `dst = 0x4c` after three `ErrorHang` command-buffer errors. Retained as a partial. |

The **scope amendment** between run01 and run02 is recorded in `analysis/gen_arms.py` rather than
applied silently: run01's first 180 cases showed a **25 % fault rate**, and a faulting case costs
majority-of-3 re-dispatches (~2.5 s vs ~11 ms), so the frozen 10 272-case set was ~110 minutes per
run and two gated runs did not fit. The reduction keeps the span (committed-triangle /
candidate-triangle / bounding-box / instancing, both compiled baselines `0x42` and `0x22`, and the
only occurrence with a same-program-point control) and drops redundancy; every target arm keeps its
full dense 256-value range. **What it costs: the inert-elsewhere claim now rests on 3 measured
occurrences, and the other 29 are UNSWEPT, not measured inert.**

**A sibling experiment (EXP-0188) was dispatching on the device throughout.** The dispatch said the
device was free; it was not by the time the gated runs ran. This is recorded as a measurement
(`raw/*/env.json` samples the process table) and is the most likely cause of both `rq_bbox`
`carrier_start_failed` events — the AS build retries on `InnocentVictim`, and 187 `InnocentVictim`
responses were observed in run02 alone. Per FIELD-SWEEP-PROTOCOL §7 a busy-machine run is fine for a
*sweep* and not for a *confirmation*; this was a sweep.

### The host stopped answering at the end

Immediately after the final pull, `192.168.10.243` went to **100 % ping loss and SSH connect
timeout**, twice. **STOPPED and reported BLOCKED; `macvdmtool` was NOT run.** No evidence was lost —
everything was already pulled back and `manifest.json` hashes all 46 files. The last device activity
was this experiment's bounding-box `dst` sweep (where run03 had already died on three consecutive
`ErrorHang`s) *and* EXP-0188 dispatching concurrently; **which workload wedged the host is not
established here**, and this experiment cannot separate them. Details in `PROGRESS.md` M5.

## 4. Limitations

1. **One complete run. No promotion.** The two-run gate is the promotion rule and it was not met.
2. **The tokenizer walk stops at 60–62 tokens on every intersection_query carrier**, so all
   `n4_rt_word` occurrences here are located by **signature scan**, cross-checked with `decode_one`
   at the offset. `walk = 0` for this opcode is a tokenizer limitation (EXP-0157 measured the same on
   RT programs), **not** evidence of absence — and it is why the target-2 census reports both numbers.
3. **`rq_bbox` never produced a gated measurement** (start failure in run02, hang-death in run03), so
   the bounding-box traversal path is unmeasured in the gated set. run01 and run03 both contain
   `rq_bbox` data and both are retained partials.
4. **The hazard rule is characterised behaviourally, not decoded.** We know which 64 values are
   rejected; we do not know what the two live bits name.
5. **`mesh_out_src` has a carrier but no sweep** — one walk-confirmed occurrence in one construct.

## 5. Recommended next

1. **`n4_rt_word.dst` is one clean gated pair away from a verdict.** Re-run the frozen 25-arm set
   twice on a quiet machine (~4 min each). Pre-registration, contract, arms and analysis are all
   committed and verified on the device; only the pair is missing.
2. **Sweep `mesh_out_src.sel` on `mesh_wide`** — the carrier now exists and is committed. It needs a
   mesh-stage *runner*, which this repo does not yet have (`agxrender_mesh.m` in EXP-0030 is the
   starting point).
3. **Stop treating `cubearray_coord_const` as an untested field.** 31 constructs, 0 hits, three
   independent censuses agreeing.
4. Re-run any long sweep with `nohup` from the first attempt: run01 was lost to the *driving
   session's* timeout, not the device's.

## 6. Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected:      kernels/{k_rq187,k_cube187,k_cf187,k_mesh187}.metal — authored by us — and
                       the `_agc.main` bytes the public Metal runtime compiled from them
Apple binary introspection: NONE
Reproduction:          README.md
Evidence:              raw/g17p_20260830_run02/sweep.jsonl (the one complete run)
                       raw/g17p_20260830_run01/, raw/g17p_20260830_run03/ (retained partials)
                       raw/prefreeze/{census.json, pilot01/, CAPTURE_CONTRACT.v1..v4.json}
                       analysis/census.json, analysis/field_verdicts.json
                       CAPTURE_CONTRACT.json (27 blob hashes, re-verified ON THE DEVICE, 25/25)
```
