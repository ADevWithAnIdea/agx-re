# EXP-0155 — emitting the TEXTURE and FRAGMENT instructions (A18 Pro / G17P)

**Target: Apple A18 Pro / G17P** — `applegpu_g17p`, `AGXAcceleratorG17P`, 5 GPU
cores, macOS 26.6, Metal family Apple9, at `192.168.10.243`. Every result here
is labelled **`target: G17P`** and is **direct** evidence for the documentation
target, not `INFERRED`.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (authored by us) and the machine code the
                  public newLibraryWithSource: / MTLBinaryArchive API produced
                  from them
Apple binary introspection: NONE
Reproduction:  # on the neo, with AGXRE_REPO=$HOME/agxre
               python3 analysis/census.py                    # pre-freeze calibration
               python3 run.py --run-id <id> --smoke-only     # baselines + liveness ladder
               python3 run.py --run-id <id> [--deadline-s N] # a gated run
               python3 analysis/verdicts.py --run01 <id> --run02 <id>
Evidence:      raw/prefreeze/** (calibration), raw/<run id>/sweep.jsonl (gated,
               append-only, one JSON object per case, flush+fsync per record)
```

## 1. The question

Texture and fragment output are mandatory for any real driver, and **none of it
was emittable**. Across the 18 instructions in scope

```
tex_deriv  imageblock_load  imageblock_store  tex_sample  tex_coord_setup  tex_write
vary_slot  frag_depth_store  frag_tile_setup  iter_flat  frag_color_store
frag_color_pack  iter_at  simd_ballot  vary_store  iter  simd_shuffle  simd_reduce
```

**110 fields** sit below emitter grade in `tools/agx-isa/validation.json`, and
under the `docs/evidence-classification.md` `emittable` rule not one of the 18
may be called emittable. `DOC-02` singles out `tex_sample`'s coordinate and
result registers: a back end currently cannot choose where a sample's
coordinates come from or where its result lands.

This experiment asks, per field, whether an emitter can choose an arbitrary
value and get documented behaviour on G17P.

## 2. Method

The binding contract is `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json`, frozen
before any gated run. In outline:

1. **Carriers** (`kernels/*.metal`, ours) are compiled on the device and every
   target occurrence is **located with `tools/agx-isa`**, never by hand-counted
   offsets; where a program does not tokenize cleanly an anchored decode scan is
   used and *every* hit is recorded in `00_inputs.json`.
2. **Liveness first.** Each arm runs a frozen **liveness ladder** before any
   sweep; an arm that cannot be shown to move the observation has its verdicts
   withheld. (§4 of the pre-registration explains why this replaced the single
   named control — the first smoke read every texture arm as dead purely because
   `tex_sample.coord` is *already* 0 in our compiled bytes.)
3. **Sweep** each field over the frozen value set — dense for width ≤ 8 —
   splicing exactly one instruction's bytes into a copy of our own archive and
   rendering/dispatching it on the real GPU.
4. **FIELD-SWEEP-PROTOCOL §7 mitigations on every case**: integrity sentinel on
   an independent path, `0xDEADBEEF` read-back poison, unique splice-archive
   path per request, majority-of-3 before any `fault`, the OS
   fault-classification string recorded per trial, `InnocentVictim` retried and
   recorded as `foreign` rather than `fault`, and periodic + end-of-arm baseline
   re-validation.
5. **Two independent gated runs**; a field is promoted only on cross-run
   agreement.

## 3. Layout

| path | what |
|---|---|
| `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` | the frozen contract (hypotheses, falsifiers, value sets, source hashes, protocol constants) |
| `kernels/*.metal` | our authored carriers |
| `harness/gfrun.m` | persistent render + splice + read-back runner with textures (derived from our own EXP-0143 `frun.m` and EXP-0142 `renderpersist`/`texpersist`) |
| `harness/casematrix.py` | the frozen case matrix: carriers, arms, value sets, falsifiers |
| `harness/runner.py` | process drivers with per-request watchdogs |
| `run.py` | the capture driver |
| `analysis/census.py` | pre-freeze carrier/occurrence census |
| `analysis/verdicts.py` | two gated runs → `analysis/field_verdicts.json` |
| `raw/prefreeze/` | calibration transcripts (never treated as evidence) |
| `raw/g17p_*/` | the gated runs, append-only |
| `RESULTS.md` | observations, interpretation, limitations, verdict |

## 4. Clean-room statement

Every byte inspected or spliced is the compiled form of MSL in `kernels/`, which
we wrote. The splice-and-reload technique uses only public Metal API
(`newLibraryWithURL:`, `MTLBinaryArchive`,
`MTLPipelineOptionFailOnBinaryArchiveMiss`). **No Apple binary was disassembled,
decompiled, symbol-dumped, strings-scanned, or otherwise introspected.**
