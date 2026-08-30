# EXP-0169 — re-recording the 144 unauditable emitter-grade fields, on G17P

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, Metal family Apple9). Every claim here is a **G17P** claim, measured on the
documentation target.

## Question

EXP-0164 (commit `459bb8bd`) re-derived every emitter-grade field in
`tools/agx-isa/validation.json` from committed `raw/` and found **144 fields — 21.7% of
everything labelled emitter-grade — with no per-value raw record attributable to them**
(47 `no-raw`, 60 `no-field-records`, 24 `field-named-but-unstructured`, 13
`raw-present-but-unattributable`). Their promotions cannot be reproduced from committed
evidence, which fails `CLAUDE.md`'s Definition of Done by construction. Enforced strictly
the headline drops from 41/166 emittable instructions to 24/166.

**Which of them can be made auditable, and do their original promotions still reproduce?**

This is an **auditability** gap, not a refutation. The remedy is a **fresh sweep**, never a
re-labelling: translating an old narrative summary into the per-case schema would launder
unauditable evidence into auditable-looking form, which would be worse than leaving the
debt visible.

## Method, in one paragraph

Three structurally different carriers (ALU-sourced narrow operands; **load**-sourced
operands with **non-zero low halves**; a **uniform-preloaded** carrier with a different
buffer signature), each running a synthesized program that seeds all 16 GPRs with distinct
values, writes a PRE sentinel to memory, executes the instruction under test with **exactly
one db.json field mutated**, dumps **all 16 registers**, then writes a POST sentinel from a
register the instruction could not have named. The read-back buffer is poisoned with
`0xDEADBEEF` first. The oracle is the full architectural state — and, for `falu2`/`falu2i`,
a **host-computed** expected value, so the published semantics are checked value by value
rather than assumed. Every (arm, carrier) first has to pass a **liveness ladder** of
mutations pre-registered to move; a carrier that cannot demonstrate detection power is not
allowed to support an inert conclusion.

Full contract: **`PRE_REGISTRATION.md`** (frozen before any device dispatch) and
**`CAPTURE_CONTRACT.json`**.

## Scope

* **12 of the 144 need a citation fix, not a device.** `analysis/recitation.py` re-runs
  EXP-0164's own gate over the *whole* raw index rather than only the experiments a field's
  `evidence` array cites (which is all `audit.py::gather()` consults). Twelve fields already
  have attributable per-value records under an **uncited** experiment, and four of those are
  recoverable from **EXP-0153, which ran on G17P** — better evidence than the M4/A18 the
  field currently cites. Result: `analysis/recitation_recovery.json`.
* **57 fields are in device scope**, `falu2` first: `falu2` 8, `falu2i` 8, `falu2_uni` 1,
  then the EXP-M4-14 ALU citations (`half_alu` 4, `half_alu_ext8` 7, `half_alu_fma12` 2,
  `iunary` 2), then the `reg_move` family (18), then `bf_alu`/`icmp_pred`/`get_sr`/
  `device_store` (7).
* **`dst` on every descriptor is EXP-0168's verdict** (coordinator directive 2026-08-30).
  It is swept here — *which register slot changed* is this experiment's detection
  instrument — but **no verdict is emitted for it**.
* **64 fields are explicitly out of scope** and named in `PRE_REGISTRATION.md` §1b: they
  need a graphics / texture / RT / control-flow / spill-frame harness this experiment does
  not build. An honest bound beats a half-swept arm.

## Reproduction

```sh
# ---- offline, no device -------------------------------------------------
python3 analysis/collect_raw.py          # EXP-0164's indexer, byte-identical
python3 analysis/recitation.py           # -> analysis/recitation_recovery.json
python3 harness/selftest.py              # offline CODE test; NOT evidence

# ---- on the neo (A18 Pro / G17P) ---------------------------------------
export SSHPASS='...'                     # never committed
harness/sync.sh push                     # -> ~/agxre/EXP-0169
ssh user@$NEO 'cd agxre/EXP-0169 && python3 harness/anchors.py'
ssh user@$NEO 'cd agxre/EXP-0169 && python3 harness/smoke.py --run pilot01'
harness/sync.sh pullwork; harness/sync.sh pull pilot01
#   -- inspect the ladder in raw/pilot01/smoke.json BEFORE the gated pair --
ssh user@$NEO 'cd agxre/EXP-0169 && nohup python3 harness/procsample.py --run g17p_20260830_run01 &'
ssh user@$NEO 'cd agxre/EXP-0169 && python3 harness/run.py --run g17p_20260830_run01 --order forward'
ssh user@$NEO 'cd agxre/EXP-0169 && python3 harness/run.py --run g17p_20260830_run02 --order reverse'

# ---- back in the repo ---------------------------------------------------
harness/sync.sh pull g17p_20260830_run01
harness/sync.sh pull g17p_20260830_run02
harness/sync.sh frozen                   # the exact db.json/isadb.py the HW ran
python3 analysis/verdicts.py raw/g17p_20260830_run01 raw/g17p_20260830_run02
python3 analysis/reindex_check.py        # THE ACCEPTANCE TEST
```

## Files

| path | what |
|---|---|
| `PRE_REGISTRATION.md` | frozen hypotheses, carriers, coverage rule, oracles, falsifiers, ladder, promotion gate |
| `CAPTURE_CONTRACT.json` | frozen source hashes, raw schema, timeouts, gated run ids, amendments |
| `kernels/probes.metal` | 28 authored probe kernels, one family per anchor |
| `kernels/carrier_dag.metal` | authored SYNTH host (binding shape + a long `_agc.main`) |
| `kernels/carrier_uni.metal` | authored uniform-preloaded host (our own EXP-0138 carrier, verbatim) |
| `harness/isa_helpers.py` | seeds (three provenances), stores, loads, sentinels, program builder, the inline-minifloat oracle |
| `harness/anchors.py` | compile our MSL + tokenize + resolve every arm's anchor |
| `harness/casematrix.py` | the frozen matrix rule: arms, carriers, coverage, ladder, `falu2` crossings |
| `harness/run.py` | gated-run driver (majority-of-3, victim flags, baseline revalidation, semantic oracle) |
| `harness/smoke.py` | pilot: carriers, baseline, `idx_off` calibration, **liveness ladder**, store shape |
| `harness/procsample.py` | samples concurrent GPU activity so "quiet window" is a measurement |
| `harness/selftest.py` | offline CODE test (no device, not evidence) |
| `analysis/collect_raw.py` | **byte-identical copy of EXP-0164's indexer** — the acceptance test's engine |
| `analysis/recitation.py` | the 12 citation-recoverable fields |
| `analysis/verdicts.py` | raw → `field_verdicts.json` + `reproduction.json` |
| `analysis/reindex_check.py` | **the acceptance test**: does EXP-0164's indexer attribute our raw? |
| `raw/` | append-only per-case evidence, including every failure |

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/probes.metal, kernels/carrier_dag.metal and
  kernels/carrier_uni.metal (authored by us in this project; carrier_uni's body is a
  verbatim copy of our own EXP-0138 carrier), and the AGX machine code the PUBLIC
  runtime API (`newLibraryWithSource:` via tools/shdump) compiled from that source.
  tools/{shdump,agxtest,agx-isa} used READ-ONLY and unmodified.
  analysis/collect_raw.py is a byte-identical copy of EXP-0164's.
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled,
  symbol-dumped, strings-scanned or debugged. The only machine code inspected or
  spliced is the compiled form of our own MSL.
Reproduction: see above.
Evidence: raw/pilot01, raw/g17p_20260830_run01, raw/g17p_20260830_run02,
          analysis/recitation_recovery.json, analysis/reindex_report.json
```
