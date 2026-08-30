# EXP-0143 — M4 emission closure: fragment/varying + SIMD families

**Target:** Apple M4 (G16G), local host, the only test target. The A18 Pro was never touched.
**Status board row:** ISA emittability (`docs/evidence-classification.md` §2 `emittable` rule).

## Question

Twelve instructions this project can *decode* are not *emittable*: 64 of their fields carry a
label weaker than `hardware-run`/`isolated-byte-diff`, so an implementer may not choose values
for them. Which of the 64 can be moved to `hardware-run` by running arbitrary values on real
hardware, and what bounds the rest?

| instruction | blocking fields |
|---|---|
| `vary_slot` | 2 (`sel`, `slot`) |
| `frag_depth_store` | 3 (`b3`, `b4`, `b5`) |
| `frag_tile_setup` | 4 (`b1`, `sel`, `access`, `b5`) |
| `iter_flat` | 4 (`b1`, `sel`, `b4`, `b5`) |
| `frag_color_store` | 5 (`store_mode`, `flags`, `mask`, `fmt`, `slice_addr`) |
| `frag_color_pack` | 6 (`src_desc`, `fmt_class`, `dst`, `mode`, `comp_off`, `val`) |
| `iter_at` | 6 (`grp`, `lead`, `dst`, `c4`, `b5`, `loc`) |
| `simd_ballot` | 6 (`cache`, `dst`, `psrc`, `psrctype`, `form`, `form_sig`) |
| `vary_store` | 6 (`hint1`, `hint2`, `out_slot_hi`, `b5_tag`, `hint6`, `b7`) |
| `iter` | 7 (`grp`, `lead`, `dst`, `coeff_sel`, `c7`, `loc`, `b9`) |
| `simd_shuffle` | 7 (`cache`, `dst`, `src`, `srctype`, `rtype`, `dsthi`, `rsv9`) |
| `simd_reduce` | 8 (`scope`, `b0hi`, `opcls`, `cache`, `dst`, `opmarker`, `src`, `shape`) |

Hypotheses, refuters, oracles, coverage schedule, confounders and the promotion rules are
frozen in `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json`.

## Method

1. **Authored carriers** (`kernels/*.metal`, our own MSL) provoke each instruction with values
   chosen so a mix-up is numerically visible: mutually non-affine per-vertex varyings, exact
   8-bit unorm codes on the packed-colour carrier, a strongly-perspective (w = 1, 2, 4)
   triangle for the barycentric question, one 32-lane divergence-free SIMD group.
2. **Build** a binary archive for the *exact* pipeline descriptor the sweep will run
   (`frun --build-archive`), so `FailOnBinaryArchiveMiss` can never miss on a descriptor
   mismatch (sample count, depth format, MRT count).
3. **Locate** each target occurrence with `tools/agx-isa` (`isadb`), never by hand-counted
   offsets; every located offset is recorded in `00_inputs.json`.
4. **Sweep** each field over its full encodable range (≤ 8 bits dense; wider fields on the §3
   schedule), one field per case, splicing into the archive and executing on the GPU.
5. **Observe** exact RGBA32Float probe pixels (or exact 8-bit codes), the depth probe, per-lane
   u32 words, and a SHA-256 of the whole attachment.
6. **Reduce** to per-field verdicts under the promotion rules, gated on an independent
   replicate run.

### Harness

| path | role |
|---|---|
| `harness/frun.m` | **persistent render runner** — the render analogue of `agxrun_persist` (which existed only for compute), with exact float readback, the integrity sentinel, unique per-request splice paths, and `0xDEADBEEF` read-back poison. Derived from our own `tools/agxtest/agxrender.m` + `agxrun_persist.m`. |
| `harness/runner.py` | process drivers + per-request watchdog + `InnocentVictim` retry |
| `harness/casematrix.py` | the frozen case matrix: carriers, arms, value sets, controls, falsifiers |
| `run.py` | capture driver (build → locate → sweep → append) |
| `analysis/verdicts.py` | reduction to `analysis/field_verdicts.json` |

`tools/shdump` and `tools/agxtest/agxrun_persist` are used as-is for the compute arm.

## Reproduction

```sh
clang -fobjc-arc -framework Metal -framework Foundation -o work/frun harness/frun.m
python3 run.py --run-id <id>                 # full sweep  (~30k cases)
python3 run.py --run-id <id> --smoke-only    # baselines + liveness controls only
python3 analysis/verdicts.py <run01> <run02> # -> analysis/field_verdicts.json
```

## Clean-room statement

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (our own MSL) and the AGX bytes compiled from them
Apple binary introspection: NONE
Reproduction: python3 run.py --run-id <id>
Evidence: raw/<run_id>/sweep.jsonl (append-only, fsynced per case), 00_inputs.json,
          05_run_manifest.json
```

Only the compiled form of our own MSL was inspected, spliced, or executed. No Apple binary was
disassembled, decompiled, symbol-dumped, or debugged. `mesa/` and `gpu_knowledge/` were not
consulted for any value in this experiment.

## Note on the directory's prior state

An earlier dispatch of this experiment authored the carriers and harness and ran a smoke
(`work/smoke_smoke01/`) before the agent was killed by a session limit; that work is committed
at `4fe49a1c` and `raw/` was left **empty** — no capture had been taken. This dispatch keeps the
authored code (it is our own, and re-authoring it would buy nothing), freezes a **new**
pre-registration, and captures under **new** run ids. `work/smoke_smoke01/` is retained
untouched as the record of that partial attempt and is never topped up or reused.
