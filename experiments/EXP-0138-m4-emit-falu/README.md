# EXP-0138 — M4 float-ALU emission closure (`DRV-ISA-01` / `P0.6`)

## Question

`tools/agx-isa/validation.json` leaves **98 fields across 16 float-ALU
instructions** below emitter grade. The float-ALU family is the most-used in the
ISA and **none of it** qualified as emittable. Can a compiler *choose* an
arbitrary legal value for these fields and get the documented behaviour — as
opposed to merely *decoding* values Apple's compiler happened to emit?

The single highest-value field is **`falu2.mod_lo`**: 3 bits, and the only thing
keeping `falu2` — the most-used instruction in the ISA — off emitter grade.

## Hypotheses

See `PRE_REGISTRATION.md` section 1 (frozen before the gated runs):
**H-MODLO** (`mod_lo` is an operand-SOURCE selector), **H-FALU3-LAYOUT** and
**H-HALF-LAYOUT** (`db.json`'s field names for `falu3`/`falu3_ext`/`half_alu*`
are off by one slot), **H-REGDESC** (`(reg<<1)|is32` with an inert top bit), and
**H-NULL** (the explicit default: an unlabelled field is inert). Each carries a
pre-registered refuter.

## Method

Two modes, both proven in the pilot (`PROGRESS.md` Milestone 1):

* **MODE A** — a hand-built program replaces the whole `_agc.main` of
  `kernels/carrier.metal` / `kernels/carrier_uni.metal`, seeds r0..r12 with 13
  distinct exact minifloat constants, runs ONE instruction under test, and
  stores the destination, an integrity-sentinel register, and a source register.
* **MODE B** — ONE instruction is spliced in place inside a compiled carrier
  from `kernels/probes.metal` (fp16, `copysign`, SFU forms).

**16,202 cases**, every field of width ≤ 8 swept densely over its whole
encodable range, wide tails swept byte-by-byte. Two independent gated runs.

Contamination controls (FIELD-SWEEP-PROTOCOL section 7, binding): unique
splice-archive path per request; **poisoned (0xDEADBEEF) output buffer** so
"nothing written" ≠ "zero written"; majority-of-3 before any `fault` verdict;
OS fault-classification string recorded and `InnocentVictim`/`Discarded`
segregated; baseline re-validation every 200 cases; per-case integrity sentinel.

## Commands

```sh
sh harness/build.sh work/bin                                  # our own tools only
python3 harness/run.py --run m4_20260828_run01                # gated run 1
python3 harness/run.py --run m4_20260828_run02                # gated run 2
python3 analysis/verdicts.py raw/m4_20260828_run01 raw/m4_20260828_run02
```

## Clean-room statement

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own MSL (kernels/*.metal, work/pilot/anchors*.metal -- 42
  authored kernels), the AGX bytes those compile to, and the outputs the GPU
  produced from them. tools/shdump, tools/agxtest and tools/agx-isa are used
  READ-ONLY and unmodified (SHA-256 recorded in CAPTURE_CONTRACT.json).
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled,
  or otherwise introspected. Every instruction byte examined here is the
  compiled form of MSL we wrote, or a value this experiment synthesised itself.
Reproduction: the four commands above.
Evidence: raw/m4_20260828_run01/, raw/m4_20260828_run02/ (sweep.jsonl,
  00_env.json, 01_summary.json, cascades.json each); raw/smoke01/ (retained
  pre-gate smoke of the priority-1 group, never promoted); work/pilot/ (the
  non-gated anchor-discovery phase).
```

## Layout

| path | what |
|---|---|
| `PRE_REGISTRATION.md` | frozen hypotheses, coverage rule, contamination controls, promotion rule |
| `CAPTURE_CONTRACT.json` | frozen revision, authored + tool SHA-256, carriers, anchors, schema |
| `kernels/` | our own MSL: two MODE-A carriers + the MODE-B probe carriers |
| `harness/isa_helpers.py` | instruction builders (all via `isadb.assemble`, never hand-spliced bytes) |
| `harness/bench.py` | persistent-runner wrapper + every contamination mitigation |
| `harness/families.py` | the 16,202-case matrix with a per-case oracle |
| `harness/run.py` | gated runner; appends + flushes one JSON object per case |
| `analysis/verdicts.py` | applies the frozen promotion rule to both runs |
| `analysis/field_verdicts.json` | the deliverable, in FIELD-SWEEP-PROTOCOL section 5 schema |
| `raw/` | append-only evidence |
| `work/pilot/` | non-gated anchor discovery (disclosed, never promoted) |
