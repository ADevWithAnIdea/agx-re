# PRE-REGISTRATION — EXP-0147: emitting the pipeline-plumbing instructions

**Frozen before the gated runs `m4_20260828_run01` / `m4_20260828_run02`.**
Exploration before this freeze lives in `work/` (smoke ids `smoke1`..`smoke10`) and is
retained, not reused. Nothing in `work/` is evidence.

**Target:** local Apple M4 / G16G, 10 cores, macOS 26.6.2 (25G82), Metal 4. M4 only.
The A18 Pro is hands-off; no G17P claim is made anywhere in this experiment.

**Governing documents:** `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md`, `docs/evidence-classification.md`.

---

## 1. Question

The bar is **emission, not decoding**. For the ten pipeline-plumbing instructions
`tile_read`, `tile_read_mrt`, `vtx_coord_xform`, `vtx_out_pos`, `pixel_order`,
`mesh_out_src`, `matrix_mac`, `scoreboard_fence`, `compute_fence_scoped`,
`n3_sample_read`, **which fields can an emitter actually choose a value for?**

Blocking fields are those whose `tools/agx-isa/validation.json` label is weaker than
`hardware-run` / `isolated-byte-diff`. Diffing `validation.json` against `db.json`
(FIELD-SWEEP-PROTOCOL §3) gives **33 blocking fields** across the ten instructions:

| instruction | blocking fields | n |
|---|---|--:|
| `tile_read` | `b2` `dst` `b4` `rt_index` `b6` `b7` `tail` | 7 |
| `tile_read_mrt` | `dst` `b4` `rt_index` `b6` `fmt` `tail` | 6 |
| `vtx_coord_xform` | `mode` `sel` `operand` | 3 |
| `vtx_out_pos` | `dst` `slot` | 2 |
| `pixel_order` | `scope` `flags` `b5` | 3 |
| `mesh_out_src` | `sel` | 1 |
| `matrix_mac` | `dst_desc` `b11hi` | 2 |
| `scoreboard_fence` | `kind` `scope` `mask` | 3 |
| `compute_fence_scoped` | `kind` `scope` `mask` | 3 |
| `n3_sample_read` | `b1` `b3` `tail` | 3 |

`matrix_mac` is the closest near-miss in the whole ISA — 10 of its 12 fields are already
emitter-grade, so `dst_desc` and `b11hi` alone decide whether the matrix unit is emittable.

**This experiment attempts 32 of the 33.** `mesh_out_src.sel` is **not attempted**: it lives
in a mesh-stage program, which needs an object/mesh render pipeline that neither
`tools/shdump` nor this harness builds. It is pre-registered as **not attempted**, and will
be reported `untested` with that reason rather than guessed at.

## 2. Hypotheses and falsifiers

**H1 (per field).** For blocking field `F` of instruction `I`, there exists a decidable
partition of `F`'s encodable range into values an emitter may use and values it may not,
observable on real hardware through a carrier in which `I`'s result reaches a read-back.

*Refuter:* the observable does not move for ANY value of `F` **and** the litmus-power probe
(§4) shows the measurement could not have seen a change anyway. Then `F` is reported
`untested`, never "inert".

**H2 (`matrix_mac`).** `dst_desc` and `b11hi` have hardware-decidable value maps, making
all 12 `matrix_mac` fields emitter-grade and the matrix unit **emittable**.

*Refuter:* either field is undecidable, or a value that must work does not.

**H3 (`tile_read`).** All seven `tile_read` fields are decidable in a fragment carrier whose
pixel is a function of the tilebuffer value, advancing P0.4 (BG/EOT construction).

*Refuter:* the tilebuffer read cannot be shown to reach the observed pixel.

**H4 (fences, pre-registered as likely negative).** A fence's effect only manifests under a
data hazard. If the litmus-power probe cannot show the carrier detecting a *neutered
neighbouring barrier*, then no `scoreboard_fence` / `compute_fence_scoped` field may be
promoted from this experiment, whatever the sweep shows.

## 3. Independent / controlled variables

- **Independent:** exactly one field's bits inside exactly one instruction of one otherwise
  byte-identical compiled program.
- **Controlled:** carrier source (frozen hashes below), compile flags (`--no-fast-math`),
  render target format (`RGBA32Float`), clear colours, uniforms, grid/threadgroup size,
  input buffers. Every case is a delta against the unspliced baseline captured first.

## 4. Controls that every arm must carry

1. **Baseline** — unspliced program vs a **host-computed** oracle (§5). Recorded first.
2. **Liveness** — change an *input* and check the observable follows its oracle:
   `src_alt` (fragment uniform), `dst_alt` (**clear colour** — this is the value the
   tilebuffer read returns, so this control is what proves the tile read reaches the pixel),
   `vp_alt` (vertex uniform), `spatial` (all pixels differ, for the vertex carriers).
3. **Litmus power** — splice an instruction *other than the one under test* whose corruption
   must move the observable (for the fences: neuter the neighbouring `threadgroup_barrier`;
   for the tilebuffer ops: force the read to return zero). **Pre-registered stop rule:** if
   the observable does not move, the arm's fields stay `untested`. EXP-0141's first tile
   litmus could not see a spliced-out barrier and would have "proven" it inert; this probe
   exists so that cannot happen here.
4. **Identity splice** — rewrite a byte with its own value; must reproduce the baseline.
   Rules out the splice/reload mechanism itself as a confound.
5. **Sensitivity (pre-registered to FAIL)** — a splice chosen to break the program. If
   everything passes, the sweep proves nothing about our ability to detect a difference.
6. **Periodic baseline re-validation** — every 128 swept cases, so a block of `silent_zero`
   cannot be a quiet cascade.

## 5. Oracles (host-computed, GPU-independent)

| carrier | oracle | comparison |
|---|---|---|
| `k_mad_f32` | `A*B + C` accumulated in float32 in Python | bit-exact |
| `k_tgrw` | `in[(lid+137) % tgsz] + in[gid]` | bit-exact |
| `k_atomic` | order-independent: multiset of `out[tid] - 2*a[tid]` is `{0..7}` ×4 | exact |
| `f_tile` | `clear*2 + src` | bit-exact float32 |
| `f_mrt` | `c0 = d0*2+src`, `c1 = d1*4-src` | bit-exact float32 |
| `f_rog` | `texel = N*src`; `pixel = clear + src*N(N+1)/2` (N=8 instances, programmable-blend accumulation) | bit-exact float32 |
| `f_vary`, `f_varyc`, `f_samp` | barycentric interpolation at each pixel centre, computed on the host | rel. tol 1e-5 (the host cannot reproduce the interpolator's rounding bit-for-bit) |

A **zero-oracle** is also pre-computed for the tilebuffer carriers (what the read-back looks
like if the tile read contributes 0), because on Apple9 a wrong field value usually yields a
**silent zero, not a fault**; such a case is classified `silent_zero`, which is a result.

## 6. Coverage (FIELD-SWEEP-PROTOCOL §3.3)

- width ≤ 8 → **all 2^w values, dense**.
- width > 8 (`tile_read.tail` 32b, `tile_read_mrt.tail` 32b, `vtx_coord_xform.operand` 40b,
  `n3_sample_read.tail` 48b) → **every constituent byte swept densely (256 each)** *plus*
  whole-field structured values: `{0,1,2,max-1,max}`, all powers of two, and 16 fixed
  asymmetric interior samples.

Total: **12 532 swept cases per run**, plus controls, ×2 gated runs.

## 7. Known confounders and how each is handled

1. **Compiler elision.** A pure passthrough fragment shader is elided entirely — EXP-0130
   found `f_eot_evict` compiled to 16 bytes containing *neither* `tile_read` nor
   `frag_color_store`. Every carrier here therefore does genuinely non-foldable ALU with a
   runtime uniform, and each arm records the located instruction's bytes so elision is
   visible as "pattern not found".
2. **In-process code memoization.** Measured here: a persistent render runner that builds
   its `MTLFunction` from *source* returns the ORIGINAL pixel for every splice, because
   Metal memoizes the native code for a given AIR identity. `harness/rendersweep.m`
   therefore loads a fresh `MTLLibrary` **from the spliced archive's own bytes** each
   request (the same fix `tools/agxtest/agxrun_persist.m` already uses), and
   `MTLPipelineOptionFailOnBinaryArchiveMiss` proves the archived bytes supplied the code.
3. **Shared-GPU contamination.** EXP-0140 and EXP-0144 sweep the same device concurrently.
   Mitigations, all pre-registered: retry in place first (measured: a "Discarded (victim of
   GPU error/recovery)" request succeeds on the next attempt with no restart); record the OS
   fault-classification string on every failure; classify `Discarded (victim…)` /
   `Ignored (for causing prior…)` as **`invalid_run`, never `fault`**; re-observe every
   non-`ok` outcome **3×** on fresh archive paths and mark it `unstable` if the replicates
   disagree; re-validate the baseline every 128 cases.
4. **"STATUS OK with nothing executed"** (EXP-0141). Each compute carrier writes an
   **integrity sentinel** `0xA5A50000+tid` through a plain scalar store independent of the
   instruction under test, over a host-written poison buffer; the render carriers use the
   fixed-function clear as the equivalent independent path (all pixels still exactly the
   clear colour ⇒ nothing drew). A measurement without its sentinel is `invalid_run` and is
   repeated — it is **not** read as a silent zero.
5. **Shared archive path.** A unique splice-archive path per persistent-runner request
   (EXP-0141 measured ~8% phantom `CMDBUF_ERROR` when one path is reused).
6. **Register aliasing / immediates.** `r(R mod 64)` for R∈[64,112], faults at 126/127;
   `mov_imm` immediates 128..255 silently zero. No case here writes a `mov_imm` immediate.

## 8. Labelling rule (decided before looking at results)

A field is promoted to **`hardware-run`** only if **all** hold:
1. its full encodable range was swept on hardware and every outcome recorded;
2. the arm's **litmus-power** probe moved the observable (the measurement can see the
   instruction's contribution) **and** the **sensitivity** control failed as pre-registered;
3. the **identity-splice** control reproduced the baseline, and every baseline re-validation
   in the arm passed;
4. every non-`ok` case reproduced across its 3 replicates.

A field that is entirely splice-inert still qualifies under this rule (precedent:
`matrix_mac.pad4`, labelled `hardware-run` with range "splice-inert padding" from EXP-O2C) —
but **only** when (2) holds, i.e. the method demonstrably could have seen a difference.
If (2) fails, every field of that arm is reported **`untested`** with the observation in
`note`, per `docs/evidence-classification.md` ("a field that WAS exercised on hardware but
whose semantics remain unexplained is `untested` with the observation recorded in `note`").

`emittable` is claimed for an instruction only when **every** field in its `db.json`
descriptor is `hardware-run` or `isolated-byte-diff`.

## 9. Environment, timeouts, stop rules

- Per-request watchdog: **10 s**, child killed and restarted on expiry (`HANG`).
- Build timeout: 60 s. In-place retries: 5. Health back-off: up to 40 s per cycle.
- **Stop rules:** two genuine watchdog hangs in one arm → stop that arm, report PARTIAL;
  three unrecovered devices in one arm → stop that arm.
- `raw/<run_id>/sweep.jsonl` is append-only, one JSON object per case,
  `flush()` + `fsync()` after every record. Run ids are never reused.

## 10. Frozen inputs

Recorded at freeze time by `analysis/freeze.py` into `manifest.json`: SHA-256 of
`kernels/pipe_render.metal`, `kernels/pipe_compute.metal`, `harness/rendersweep.m`,
`harness/shdump2.m`, `harness/run.py`, `harness/rsdrv.py`, `harness/sweepplan.py`, the
unmodified `tools/shdump/shdump.m`, `tools/shdump/agxparse.py`,
`tools/agxtest/agxrun_persist.m`, `tools/agxtest/persistrun.py`, plus the repo revision and
dirty flag. Per SUBAGENT_BRIEF, captures are validated against **these recorded hashes**,
not against live `HEAD` — sibling experiments commit continuously and that is not
contamination.

## 11. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/pipe_render.metal, kernels/pipe_compute.metal (both authored
                  by us for this experiment) and the machine code the public
                  newLibraryWithSource: API produced from them.
Apple binary introspection: NONE
Reproduction: python3 harness/run.py --run-id <id> --out-root raw
Evidence: raw/<run_id>/sweep.jsonl, analysis/field_verdicts.json
```
