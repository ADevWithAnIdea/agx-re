# RESULTS — EXP-0147: emitting the pipeline-plumbing instructions

**Target:** local Apple M4 / G16G, 10 GPU cores, macOS 26.6.2 (25G82), Metal 4.
**M4 only.** No A18 Pro / G17P claim is made anywhere below; the A18 is hands-off.

**Gated evidence:** `raw/m4_20260828_run01/sweep.jsonl`, `raw/m4_20260828_run02/sweep.jsonl`
(append-only, one JSON object per case, `flush`+`fsync` per record).
**Analysis:** `analysis/field_verdicts.json`, `analysis/emittability.json`.
**Frozen contract:** `PRE_REGISTRATION.md`; frozen input hashes in `manifest.json`.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/pipe_render.metal, kernels/pipe_compute.metal (ours), and the
                  machine code the public newLibraryWithSource: API produced from them.
Apple binary introspection: NONE
Reproduction: python3 harness/run.py --run-id <id> --out-root raw
              python3 analysis/verdicts.py --run01 m4_20260828_run01 --run02 m4_20260828_run02
```

---

## 1. Verdict

**26 of the 32 attempted blocking fields are now emitter-grade, and 7 of the 10
instructions become EMITTABLE — including both of the two the dispatch singled out.**

| | |
|---|---|
| blocking fields at start (validation.json vs db.json) | **33** |
| attempted here | **32** (`mesh_out_src.sel` pre-registered as not attempted) |
| promoted | **26** — 18 `hardware-run` + 8 `isolated-byte-diff` |
| still `untested` | **7** — the six fence fields (swept, unexplained) + `mesh_out_src.sel` (not attempted) |
| fields recorded in `analysis/field_verdicts.json` | **33** (all fields of all ten instructions) |
| swept cases | **12 532 per run x 2 gated runs = 25 064** |
| cross-run agreement | **12 328 / 12 532 = 98.37 %** |

**`matrix_mac` — YES, emittable.** Both blockers resolved by dense full-range sweeps
(`dst_desc` 256/256, `b11hi` 128/128, 100 % cross-run agreement, zero unstable cases).
All 12 fields are now `hardware-run` or `isolated-byte-diff`, so the matrix unit clears the
`emittable` rule. The sweep also found a capability Metal never emits: **`A*B - C`**, plus a
half-tile variant (section 2.1).

**`tile_read` — YES, emittable**, and so is `tile_read_mrt`. All 7 / 6 fields promoted, with
the tilebuffer read proven live on the observed pixel by a clear-colour control and by a
litmus-power probe that collapses the read to zero. This directly advances **P0.4**: a BG/EOT
program's tilebuffer read is now a specified encoding with a stated legal-value set per
field, not a copied template.

| instruction | fields | verdict |
|---|---|---|
| `tile_read` | 7/7 promoted | **EMITTABLE** |
| `tile_read_mrt` | 6/6 promoted | **EMITTABLE** |
| `matrix_mac` | 2/2 promoted | **EMITTABLE** |
| `vtx_out_pos` | 2/2 promoted | **EMITTABLE** |
| `vtx_coord_xform` | 3/3 promoted | **EMITTABLE** |
| `pixel_order` | 3/3 promoted | **EMITTABLE** (see the `flags` defect below) |
| `n3_sample_read` | 3/3 promoted | **EMITTABLE** |
| `scoreboard_fence` | 0/3 | blocked — no ordering-specific litmus power |
| `compute_fence_scoped` | 0/3 | blocked — same, though `mask` shows a live signal |
| `mesh_out_src` | 0/1 | **not attempted** (needs a mesh pipeline) |

Two caveats stated up front rather than buried:

- **`pixel_order` is emittable at the encoding `db.json` currently describes**, but the sweep
  shows `db.json` cannot express what the hardware accepts: its `flags` field and its match
  constant claim the same bits (section 2.3). Fixing that descriptor is a prerequisite for an
  emitter to use the larger legal set.
- Four fields (`tile_read.dst`, `tile_read_mrt.dst`, `vtx_coord_xform.operand`,
  `n3_sample_read.tail`) are `hardware-run` under the **literal** frozen rule (intra-run
  replicate stability, which they pass 100 %) and were demoted to `isolated-byte-diff` by the
  **stricter** cross-run requirement this analysis added. Their cross-run misses are boundary
  cases that came back `invalid_run` / `fault` under concurrent GPU load from EXP-0140 and
  EXP-0144. Both readings are recorded per field in `analysis/field_verdicts.json`
  (`label` vs `label_under_frozen_rule_literal`); the stricter one is what is claimed.

---

## 2. What was directly OBSERVED

Every statement in this section is a machine-checkable property of the two raw files, and
each bit-rule below was re-derived from the raw records by
`analysis/summarize.py` and asserted exactly (not approximately).

### 2.1 `matrix_mac` — both blocking fields resolved, and a capability Metal never emits

`dst_desc` (byte+9, 8 bits, all 256 values, twice):

| outcome | values |
|---|---|
| correct `A*B+C` | `0x40-0x7f` (64/64) |
| **silent zero** | `0x00-0x3f`, `0x80-0xbf` (128) |
| wrong value | `0xc0-0xff` (64) |

The rule is exactly **bit6 = 1 and bit7 = 0**; bits 0-5 are don't-care. Verified as a set
identity against the raw records, not by eyeballing ranges.

`b11hi` (byte+11 bits 1-7, 7 bits, all 128 values, twice): correct `A*B+C` **iff
`(b11hi & 3) == 0`** (32/128); bits 2-6 are don't-care. The two low bits are not padding —
they are **accumulator sign controls**, resolved per tile row:

| `b11hi` | rows 0-3 | rows 4-7 |
|---|---|---|
| `0` | `+C` | `+C` |
| `1` (bit0) | `-C` | `+C` |
| `2` (bit1) | `-C` | `-C` |
| `3` (both) | `+C` | `-C` |

So the matrix unit performs **`A*B - C` (matrix multiply-subtract), and a half-tile variant**,
neither of which `simdgroup_multiply_accumulate` ever emits. This is a hardware capability
found by perturbing a field the database called opaque `raw` — the "extrapolate and test"
method, with the negative-space value map recorded alongside.

### 2.2 `tile_read` / `tile_read_mrt` — the tilebuffer read is now a specified encoding

Liveness was proven, not assumed: the `dst_alt` control changes only the **clear colour**
(the value the tilebuffer read returns) and the pixel follows its host oracle exactly; the
litmus-power probe forces the read to return zero and the pixel collapses to `src` alone.

| field | rule measured over all 256 values, twice |
|---|---|
| `b2` | **fully inert** — all 256 values give the byte-exact correct pixel |
| `b4` | **fully inert** — all 256 values correct |
| `b6` | **bit0 is a read-enable**: all 128 odd values correct, all 128 even values give a **silent zero**. Bits 1-7 don't-care. Identical on `tile_read_mrt`. |
| `rt_index` | correct only at `0x00,0x01,0x80,0x81` (baseline `0x00`) — bit0 and bit7 don't-care, every other index **silently returns zero** with one attachment bound |
| `dst` | correct only at `0x00,0x01,0xc0,0xc1`; `0x02-0x07` wrong; the bulk silently zero; `0xf6-0xff` fault or collateral |
| `b7` | correct only at `0xae,0xaf,0xee,0xef` (baseline `0xae`); 85 of 256 values are **nondeterministic** across replicates |
| `tail` | bytes 1 and 3 almost entirely **silent zero** off their baseline; byte 0 is nondeterminism-heavy |

`tile_read_mrt` reproduces the same shape shifted by its baseline (`dst` ok at
`0x08,0x09,0xc8,0xc9`; `rt_index` ok at `0x08,0x09,0x88,0x89`), and additionally resolves
**`fmt`**: correct only at `0x2e,0x2f,0x6e,0x6f,0xae,0xaf,0xee,0xef` — i.e. **bits 0, 6 and 7
are don't-care and bits 1-5 are the format selector**.

The single most useful driver fact here: **an emitter that gets `rt_index`, `dst`, `b6` or
`fmt` wrong does not get a fault — it gets a silent zero**, which for a BG/EOT program means
a tile that reads as black rather than a program that fails loudly.

### 2.3 `pixel_order` — the raster-order pair, and a database defect

**Detection strength first** (the EXP-0141 requirement, in numbers): with the acquire
member's byte+4 corrupted, the read-back texel falls from `8*src` to `1*src` — **7 of the 8
serialised read-modify-writes are lost** — and the accumulated pixel falls from
`clear + 36*src` to `clear + 8*src`. Byte-identical in both gated runs. So this litmus
demonstrably counts lost updates, and an "inert" verdict from it is a measurement rather
than a blind spot. The acquire/release asymmetry is itself a result: **the same corruption
on the release member loses no updates at all** (texel stays `8*src` in both runs), which is
why the release arm's sensitivity control did not fail and why that arm promotes nothing.

The carrier draws 8 instances over one texel under a **texture**-tagged
`raster_order_group`; with ordering intact the texel ends at exactly `8*src` and the
programmable-blend pixel at `clear + 36*src` (`sum(1..8)`), so a single lost update is
visible in both. Neutering the acquire marker loses 7 of the 8 updates — the litmus has
demonstrated power to see exactly the failure it is being used to exclude.

| field | acquire member (`07 14 54 50 06 00`) | release member (`07 04 54 d0 06 00`) |
|---|---|---|
| `scope` (byte+3) | correct iff **bit4 = 1 and bit6 XOR bit7 = 1** (64/256) | correct iff **bit4 = 1 and bit7 = 1** (64/256) |
| `flags` (byte+4) | correct iff **bit0 = 0 and (v & 0x0e) != 0** (112/256) | correct iff **(v & 0x0f) >= 2** (224/256) |
| `b5` (byte+5) | **fully inert**, all 256 | **fully inert**, all 256 |

This settles the db's open note ("scope {0x50,0xd0}, bit7 differs") with the full accepted
set, and it exposes a real **`db.json` defect**: `pixel_order` declares a field `flags` at
bits[32:40] *and* a match constant `[32,8,6]` pinning the same bits to `0x06`. The hardware
accepts 112 (acquire) / 224 (release) distinct values there with the program still
byte-exactly correct, so byte+4 is a genuine field, not a constant — and as modelled, every
legal encoding with byte+4 != 0x06 is neither decodable nor emittable.

### 2.4 `vtx_out_pos`, `vtx_coord_xform`, `n3_sample_read`

- **`vtx_out_pos`**: `dst` (16 values) and `slot` (256 values) are **fully inert** in this
  carrier — every value leaves the interpolated pixel byte-exact. The arm's litmus-power
  probe (corrupting the op-select constant) does move the pixel, so this is measured
  inertness, not a blind spot. **Scope limit:** the carrier has a single output slot, so
  this says nothing about `slot` in a program with several varyings; that is stated as the
  bound, not papered over.
- **`vtx_coord_xform.mode`**: correct exactly when `(mode & 0xf3) ∈ {0x22, 0xe2}` (8/256);
  240 of 256 values **suppress the draw entirely** (`no_draw`), 8 give a wrong pixel.
  `sel`: 91 correct, 143 `no_draw`, 19 genuine `Caused GPU Hang Error` faults.
  `operand`: bytes 0 and 4 are **fully inert** (256/256 each), byte 3 is fault-prone.
- **`n3_sample_read`**: `b1` and `b3` are **fully inert** (256/256 each), and 5 of the 6
  `tail` bytes are fully inert; only `tail` byte 0 matters, where 53 values fault.

### 2.5 The fences — a bounded negative, with the litmus power to make it mean something

`scoreboard_fence` (`07 42 02 00`, in a device-atomic carrier): **all 256 `kind`, all 128
`scope`, all 256 `mask` values leave the result bit-exact** — and so does corrupting byte 0,
the opcode itself. `compute_fence_scoped` (`87 00 80 04`, threadgroup store → barrier →
+137 far-neighbour load, so every lane reads a slot written by a different simdgroup):
`kind` and `scope` fully inert; **`mask` breaks the result at exactly 10 of 256 values**
(`0x00,0x08,0x0c,0x10,0x18,0x80,0x88,0x8c,0x90,0x98`), reproducibly.

The carriers are not powerless: neutering the *neighbouring* `threadgroup_barrier` in each
one breaks the program outright. But that probe demonstrates general detection sensitivity,
**not ordering-specific sensitivity**, and the pre-registered sensitivity control (corrupt
the fence's own byte 0) *passed* when it was registered to fail. Under the frozen rule that
forbids promotion, so **all six fence fields are reported `untested`** with the observations
recorded — including the live `compute_fence_scoped.mask` signal, which is the single
highest-value follow-up in this experiment.

---

## 3. INTERPRETATION, and what is NOT concluded

1. **"Inert" means inert in the tested carrier.** Where a field takes all values with no
   observable change, the honest reading is that *this program* does not depend on it. A
   program with more render targets, more varyings, or a different format may. Each such
   field's `range` in `field_verdicts.json` says exactly which carrier established it.
2. **Silent zeros dominate the failure modes**, as `docs/evidence-classification.md`
   predicts. Across the tilebuffer fields the most common wrong-value outcome is not a fault
   but a zero result, which is why the zero-oracle is computed on the host and classified
   separately rather than lumped into "wrong".
3. **Nondeterminism is a result, not noise.** `tile_read.b7` and `tile_read.tail` byte 0
   contain values whose output differs between replicates *and* between runs. Those values
   are recorded `unstable` and are explicitly not promoted; they most likely expose stale
   register or tile state.
4. **The fence negative is bounded, not universal.** It says these fence encodings are not
   load-bearing for correctness *in these two carriers*, which are the shapes our own
   compiler produced. It does not say the fences are no-ops in general.

---

## 4. Method reliability — what had to be fixed, and what it cost

This experiment ran **concurrently with EXP-0140 and EXP-0144 sweeping the same GPU**, which
is recorded in `manifest.json` and is the reason for most of the machinery below.

1. **Persistent-render-runner memoization (measured, then fixed).** A persistent render
   runner that builds its `MTLFunction` from *source* returns the **baseline pixel for every
   splice**, because Metal memoizes native code per AIR identity. Verified by contradiction:
   one-shot processes gave four different pixels for four splices where the persistent
   runner gave one. `harness/rendersweep.m` therefore loads a fresh `MTLLibrary` from the
   spliced archive's own bytes per request (the fix `agxrun_persist.m` already used). **Any
   future fragment-stage sweep that skips this will silently conclude that every field is
   inert.**
2. **The GPU error cascade, and the wrong fix for it.** After another process's command
   buffer faults, the next submission here returns `Discarded (victim of GPU error/recovery)`
   and then **succeeds again with no restart**. An earlier recovery loop restarted the child
   first — which made the fresh child's first request the next victim, so the sweep never
   recovered and produced 138 consecutive false `invalid_run`s. Retrying **in place** first
   fixed it. Collateral (`Discarded (victim…)`, `Ignored (for causing prior…)`) is never
   recorded as `fault`; only `Caused GPU Hang Error` is.
3. **The integrity sentinel earned its place twice.** It caught its own check bound being
   wrong (64 slots checked, 32 threads dispatched) rather than passing a bad measurement,
   and in the render arms it caught real cases where the runner returned `STATUS OK` and
   nothing was drawn — the EXP-0141 mode, which without the sentinel reads as a silent zero.
   Those are recorded as `no_draw`/`no_dispatch`, a distinct outcome from `silent_zero`.
4. **Two oracle bugs were caught by the controls, not by inspection**: the `k_tgrw` host
   oracle still used the old `+1` neighbour after the kernel moved to `+137`, and the
   litmus-power test compared `k_atomic`'s arrival-ordered raw output, which differs between
   two identical runs and would have declared power that did not exist.

**Cross-run agreement: 12 328 / 12 532 = 98.37 %** (204 disagreements). They are concentrated
in exactly the fields flagged `unstable` intra-run, and **no field labelled `hardware-run`
contains a single `unstable` case** — checked mechanically, not by inspection.

Every field entry carries a `detection_proof` string stating, in numbers, what the
measurement was shown able to see; the two fence arms carry an explicit **INSUFFICIENT**
detection proof, which is why they are `untested` rather than "inert".

---

## 5. Limitations

- **M4 only.** Nothing here transfers to G17P without a recorded validation.
- **`mesh_out_src.sel` was not attempted** (pre-registered): it needs an object/mesh render
  pipeline this harness does not build. It remains `untested`, with that reason.
- **One carrier per instruction.** Every "inert" verdict is bounded by that carrier's shape.
- **`pixel_order` sweeps one member at a time**, leaving the other intact; joint corruption
  of both members was not swept.
- **The fence arms lack ordering-specific litmus power**, so their fields are reported
  `untested` even though `compute_fence_scoped.mask` shows a reproducible live signal.
- Wide fields were swept per constituent byte plus structured whole-field values, not over
  all 2^32 / 2^40 / 2^48 combinations.

## 6. Recommended next steps

1. **`compute_fence_scoped.mask`** — 10 reproducible breaking values out of 256 in a carrier
   with a genuine cross-simdgroup hazard. A successor with an ordering-specific litmus
   (stale-lane counting, as EXP-0141 did at 224/256) should promote this field.
2. **`tile_read.b7` / `tail` byte 0 nondeterminism** — identify what stale state those
   values expose.
3. **`vtx_out_pos.slot` in a multi-varying carrier** — the single-slot carrier here cannot
   distinguish "don't-care" from "only one legal slot exists".
4. **`mesh_out_src.sel`** — needs a mesh-pipeline harness.
5. The `db.json` corrections in `analysis/field_verdicts.json` → `db_defects`, above all the
   self-contradictory `pixel_order.flags`.
