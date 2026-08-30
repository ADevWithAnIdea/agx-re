# EXP-0163 — is any AGX encoding field genuinely a don't-care? (A18 Pro / G17P)

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
Reproduction:  # on the neo, with AGXRE_REPO=$HOME/agxre/EXP-0163
               python3 analysis/audit_0155.py                       # re-derive the target list
               python3 analysis/census.py                           # pre-freeze calibration
               python3 analysis/gen_arms.py                         # census -> frozen arms
               python3 run.py --run-id <id> --smoke-only             # detection profile only
               python3 run.py --run-id <id> [--deadline-s N]         # a gated run
               python3 analysis/verdicts.py --runs raw/*/sweep.jsonl
               python3 analysis/rules.py    --runs raw/*/sweep.jsonl
Evidence:      raw/prefreeze/** (calibration, never evidence)
               raw/<run id>/sweep.jsonl (gated, append-only, one JSON object per
               case, flush+fsync per record)
```

## 1. The question

`EXP-0155` swept 109 fields over two gated runs and **22 of them moved nothing,
on any carrier, in either run**. The tempting reading is that those are
don't-cares.

The prior this experiment tests is the opposite, and it is a hardware-economics
argument: **encoding space is expensive, so a field that shows no effect is more
likely UNEXERCISED than meaningless.** EXP-0155's own data already supports it —
three fields it first read as inert turned out live once a different carrier was
picked.

**Per field: does a compilable MSL carrier exist under which some value in the
field's dense range changes an observable?**

## 2. What makes a null mean anything

The method's load-bearing part is not the sweep, it is the **detection profile**
(`PRE_REGISTRATION.md` §4). Before sweeping, every arm splices the bitwise
complement and then zero of **every field the DB defines on that instruction**,
and records all of it. Unlike EXP-0155's ladder it does not stop at the first
success: the whole profile is the evidence, and it says which bytes of the
instruction are live on this carrier.

An arm whose profile shows no **status-OK, same-mnemonic** control that moves
the observation has **no detection power**, and contributes nothing to an inert
verdict. `analysis/verdicts.py` recomputes that gate from the raw records rather
than trusting the in-run summary, because run.py's in-run predicate scores a
**faulted** control as "moved" — and a fault is an effect, but not a proof that
the arm can see a value difference.

## 3. Layout

| path | what |
|---|---|
| `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` | the frozen contract (hypotheses, falsifiers, arms, value sets, source hashes, protocol constants) |
| `kernels/k_*.metal` | our authored carriers (27 MSL programs, 29 carrier configurations), one `why` per file |
| `harness/gfrun2.m` | render + splice + read-back runner, forked from our own EXP-0155 `gfrun.m`; adds a layered `texture2d_array` colour attachment, array/3D/half/uint writable textures, and OUTBUF reporting |
| `harness/runner2.py` | process drivers with per-request watchdogs and the new surfaces |
| `harness/carriers.py` | frozen carrier table (pipeline descriptor + `why` per carrier) and the target field list |
| `harness/arms.py` | the frozen arm list, GENERATED from the census by `analysis/gen_arms.py`, carrying each arm's expected bytes |
| `run.py` | the capture driver (baseline → detection profile → dense sweep) |
| `analysis/audit_0155.py` | re-derives the 22-field target list from EXP-0155's raw |
| `analysis/census.py` | pre-freeze carrier/occurrence census |
| `analysis/verdicts.py` | gated runs → `analysis/field_verdicts.json` (the three buckets) |
| `analysis/rules.py` | gated runs → `analysis/bit_rules.json` (exact per-bit liveness) |
| `raw/prefreeze/` | calibration transcripts, including the carriers that did not compile |
| `raw/g17p_*/` | the gated runs, append-only |
| `RESULTS.md` | observations, interpretation, limitations, verdict |

## 4. Clean-room statement

Every byte inspected or spliced is the compiled form of MSL in `kernels/`, which
we wrote. The splice-and-reload technique uses only public Metal API
(`newLibraryWithURL:`, `MTLBinaryArchive`,
`MTLPipelineOptionFailOnBinaryArchiveMiss`). **No Apple binary was disassembled,
decompiled, symbol-dumped, strings-scanned, or otherwise introspected.**
