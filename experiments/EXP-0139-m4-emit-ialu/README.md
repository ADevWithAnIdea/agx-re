# EXP-0139 — M4 integer-ALU: from *decodable* to *emittable*

**Date:** 2026-08-28 · **Target:** local **Apple M4 (G16G)**, macOS 26.6.2 (25G82), Metal 4.
No A18 Pro claim (A18 hands-off per `CLAUDE.md`); no M5 evidence used or produced.
**Clean-room category:** HW-PROBE + OWN-SHADER.

## Question

`docs/evidence-classification.md` §2: a family may be called **emittable** only if every
field an emitter must fill is `hardware-run` or `isolated-byte-diff`. Only **5 of 170**
instructions cleared that bar. **Integer ALU was the single largest blocked family — 16
instructions, 137 blocking fields**, the worst in the ISA:

`iadd2 ibfe ibfe_mesh_attr ibfins ibitcount icmp_pred icmpsel imad iminmax isel10 isel10_c
isel8 isel_reg isel_reg8 ishift iunary`

For how many of those 137 can an emitter choose an arbitrary value and get documented
behaviour — proven by running values the compiler would never choose, against a
host-computed oracle?

## Method (full detail: `PRE_REGISTRATION.md`; process contract: `../FIELD-SWEEP-PROTOCOL.md`)

Two carrier styles, both built from our own MSL:

- **SYNTH** (`kernels/carrier_dag.metal`) — `_agc.main` entirely replaced by a program we
  assembled from `tools/agx-isa` field rules: 16 `mov_imm` seeds (every immediate in the
  HW-validated 0..127 range) → the instruction under test → `device_store` → `stop`. Used
  for `iadd2`, `ibitcount`, `iunary`. **Generation, not replay.**
- **NATURAL** (`kernels/ialu_probes.metal`, 30 authored kernels) — our own compiled kernel
  left intact, exactly ONE instruction overwritten at an offset resolved at run time by
  tokenizing the carrier. Used where the operand map is still `corpus-correlation`, so that
  "field is inert" is never conflated with "I guessed the operand map wrong".

Fields of width ≤ 8 swept **densely over all 2^w values**; wider fields per
FIELD-SWEEP-PROTOCOL §3.3. Every case dispatched **twice inside one process**, and the whole
capture repeated in a **second process launch**. Every non-OK and every unstable case then
re-run **in a fresh process** (5× and 7×) with a baseline check before and after, recording
the OS's own fault-classification string.

## Commands

```sh
sh harness/build.sh work/bin
python3 harness/verify.py --selftest
python3 harness/run.py --run m4_20260828_run01
python3 harness/run.py --run m4_20260828_run02
python3 harness/revalidate.py --runs m4_20260828_run01,m4_20260828_run02 \
        --out raw/m4_20260828_reval01 --repeats 5
python3 harness/revalidate.py --runs m4_20260828_run01,m4_20260828_run02 \
        --indices work/unstable_indices.json --out raw/m4_20260828_reval02 --repeats 7
python3 analysis/emit_verdicts.py
```

## Result

`RESULTS.md`; machine-readable verdicts in `analysis/field_verdicts.json`.

**73 of the 137 blocking fields reached emitter grade** (39 `hardware-run`,
34 `isolated-byte-diff`); 64 remain blocked, 44 of them operand/condition selectors that need
a seeded-register carrier per family. **`ibitcount` and `iunary` became emittable** — the two
single-field blockers. 129,839 GPU dispatches, **0 hangs**, 0 reboots.

Highlights: `ibitcount.tail` is a **bit-2-only** gate, not a `0x04` marker; `iunary.operand`
is **not** a 40-bit blob but five one-byte sub-fields identical to `ibitcount`'s;
`ibfe.offset` is **literal** (≥32 → 0, refuting NIR's mod-32 assumption at the raw-instruction
level, EXP-0102's own open follow-up) while `ibfe.width` is **mod 32** — refuting this
experiment's own pre-registered model; EXP-0112's `r(R mod 64)` aliasing rule does **not**
hold for `iadd2.dst`, whose reproducible fault boundary is `reg ≥ 96`.

**Process finding:** 44 % of the faults seen in the gated runs **did not reproduce**;
1,552 revalidation attempts carried `kIOGPUCommandBufferCallbackErrorInnocentVictim`. Without
`FIELD-SWEEP-PROTOCOL` §7's re-validation rule, 692 legal field values would have been
labelled `fault`. This experiment ran concurrently with **EXP-0141 (MEM)** and
**EXP-0146 (integer misc)**.

## Clean-room provenance

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: kernels/*.metal (authored by us) and the AGX machine code the public
  runtime API compiled from them; tools/agx-isa/db.json; tools/{shdump,agxtest} read-only.
Apple binary introspection: NONE
Reproduction: see Commands above
Evidence: raw/m4_20260828_{run01,run02,reval01,reval02}/, analysis/field_verdicts.json
```
