# EXP-0147 — Emitting the pipeline-plumbing instructions (tilebuffer, vertex output, fences, matrix unit)

**Target:** local Apple M4 / G16G, 10 GPU cores, macOS 26.6.2 (25G82), Metal 4.
**M4 only.** The A18 Pro / G17P is hands-off; nothing here is a G17P claim.

**Clean-room provenance**

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/pipe_render.metal and kernels/pipe_compute.metal (authored by
                  us for this experiment), and the machine code the public
                  newLibraryWithSource: API produced from them.
Apple binary introspection: NONE
Reproduction: python3 harness/run.py --run-id <id> --out-root raw
              python3 analysis/verdicts.py --run01 <id1> --run02 <id2>
Evidence: raw/<run_id>/sweep.jsonl (append-only), analysis/field_verdicts.json
```

## Question

The acceptance bar is **emission, not decoding**. For ten pipeline-plumbing instructions
(`tile_read`, `tile_read_mrt`, `vtx_coord_xform`, `vtx_out_pos`, `pixel_order`,
`mesh_out_src`, `matrix_mac`, `scoreboard_fence`, `compute_fence_scoped`,
`n3_sample_read`), which fields can a driver actually choose a value for?

Diffing `tools/agx-isa/validation.json` against `db.json` gives **33 blocking fields** —
fields labelled weaker than `hardware-run` / `isolated-byte-diff`, which under the
`emittable` rule of `docs/evidence-classification.md` keep their instruction
"decodable, not yet emittable". This experiment sweeps **32 of the 33** on real hardware.
(`mesh_out_src.sel` is pre-registered as **not attempted** — it needs an object/mesh render
pipeline this harness does not build.)

`matrix_mac` matters most per unit effort: 10 of its 12 fields are already emitter-grade,
so `dst_desc` and `b11hi` alone decide whether the matrix unit becomes emittable.
`tile_read` matters most for P0.4, since a BG/EOT program is built from it.

## Method

Full pre-registration (hypotheses, refuters, oracles, coverage, controls, labelling rule,
stop rules) is in `PRE_REGISTRATION.md`, frozen before the gated runs.

For each instruction we author a **carrier**: our own MSL whose compiled program contains
that instruction on a path whose result reaches a read-back pixel, texel, or buffer. We
capture an unspliced baseline against a **host-computed** oracle, then splice one field at a
time in the compiled bytes and re-run on the GPU.

Coverage: every field of width ≤ 8 is swept **densely over all 2^w values**; wider fields
(`tail`, `operand`) get every constituent byte swept densely **plus** whole-field boundary,
power-of-two and asymmetric interior values. **12 532 swept cases per run, two gated runs.**

Each arm carries six controls: baseline, input-liveness, **litmus power**, identity splice,
a **sensitivity control pre-registered to fail**, and periodic baseline re-validation. The
litmus-power probe exists because EXP-0141 found its first tile litmus could not detect a
spliced-out barrier at all — it would have "proven" inert something it had no power to see.
No field of an arm whose litmus-power probe does not move the observable is promoted.

## Carriers

| arm | instruction | carrier | what makes the instruction observable |
|---|---|---|---|
| `matrix_mac` | `matrix_mac` | `k_mad_f32` | one 8×8 `simdgroup_multiply_accumulate`; oracle `A*B+C` in float32 on the host |
| `tile_read` | `tile_read` | `f_tile` + `v_arr` | `[[color(0)]]` read of a tile cleared to an exact float colour, combined by non-foldable ALU (`dst*2+src`) so the compiler cannot elide it |
| `tile_read_mrt` | `tile_read_mrt` | `f_mrt` + `v_arr` | two attachments read and written with *different* combines, so a mis-routed target index is visible |
| `vtx_out_pos` | `vtx_out_pos` | `v_tern` + `f_vary` | vertex program drives a spatial colour gradient across a 2×2 target |
| `vtx_coord_xform` | `vtx_coord_xform` | `v_arr` + `f_varyc` | vertex uniform scaled per vertex, interpolated into the pixel |
| `pixel_order` / `pixel_order_rel` | `pixel_order` | `f_rog` + `v_arr` | a **texture**-tagged `raster_order_group` (the shape EXP-0093 showed compiles to the dedicated acquire/release pair); 8 instances read-modify-write one texel, so lost updates are visible in both the texel and the accumulated pixel |
| `n3_sample_read` | `n3_sample_read` | `f_samp` + `v_samp` | a `[[sample_perspective]]` varying forces sample-rate execution |
| `scoreboard_fence` | `scoreboard_fence` | `k_atomic` | device atomic RMW + device/texture fence |
| `compute_fence_scoped` | `compute_fence_scoped` | `k_tgrw` | threadgroup store, barrier, then a **+137 (prime) far-neighbour** load so every lane reads a slot written by a different simdgroup |

## Files

```
PRE_REGISTRATION.md          frozen hypotheses, oracles, coverage, labelling rule
manifest.json                frozen SHA-256 of every authored input + repo revision
kernels/pipe_render.metal    authored MSL: the vertex/fragment carriers
kernels/pipe_compute.metal   authored MSL: the compute carriers
harness/sweepplan.py         the frozen plan: carriers, fields, controls, host oracles
harness/run.py               capture driver (append-only JSONL, flush+fsync per case)
harness/rendersweep.m        persistent render runner (authored for this experiment)
harness/shdump2.m            local derivative of tools/shdump adding --nrt / --samples
harness/rsdrv.py             driver + watchdog for rendersweep
analysis/freeze.py           writes manifest.json
analysis/verdicts.py         two raw runs -> analysis/field_verdicts.json
raw/<run_id>/sweep.jsonl     immutable per-case evidence
work/                        pre-freeze exploration (smoke1..smoke11); NOT evidence
```

## Reproduction

```sh
clang -fobjc-arc -framework Metal -framework Foundation -o work/bin/shdump        ../../tools/shdump/shdump.m
clang -fobjc-arc -framework Metal -framework Foundation -o work/bin/shdump2       harness/shdump2.m
clang -fobjc-arc -framework Metal -framework Foundation -o work/bin/rendersweep   harness/rendersweep.m
clang -fobjc-arc -framework Metal -framework Foundation -o work/bin/agxrun_persist ../../tools/agxtest/agxrun_persist.m
python3 analysis/freeze.py
python3 harness/run.py --run-id m4_20260828_run01 --out-root raw
python3 harness/run.py --run-id m4_20260828_run02 --out-root raw
python3 analysis/verdicts.py --run01 m4_20260828_run01 --run02 m4_20260828_run02
```

Verdict, limitations and the honest field count are in `RESULTS.md`.
