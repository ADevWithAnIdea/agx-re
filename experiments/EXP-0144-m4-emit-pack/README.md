# EXP-0144 — M4 pack/convert family: are the operand fields EMITTABLE?

**Row:** `P0.6` / `DRV-ISA-01` (shader ISA synthesis) via the emit-everything wave.
**Status:** see `RESULTS.md`. **Target: local Apple M4 / G16G only.**

## Question

Nine instructions carry every format conversion an Apple9 driver performs:

```
cvt_bf16  cvt_f2h  cvt_f2h_dst  cvt_f2i  cvt_i2f  cvt_i2f_src
pack_convert  packed_half2_hi  unpack_convert
```

Across them **51 fields** sit below emitter grade in `tools/agx-isa/validation.json`
(`untested`, `tokenization-only`, `corpus-correlation`, `single-template-inference`).
Round-tripping those bytes proves we can *decode* them. This experiment asks the
different, harder question the Definition of Done actually requires:

> Can an emitter put an **arbitrary value** in each field and get documented
> behaviour — and where it cannot, what does the hardware do instead?

## Hypotheses and method

Pre-registered in `PRE_REGISTRATION.md` (frozen before any recorded capture, with
`CAPTURE_CONTRACT.json` pinning source hashes, the 22,237-case matrix hash, the raw
schema, the gate, the timeouts and the stopping rules). Five arms: semantics (`S`),
dense per-byte field sweep (`F`), whole-field values for the two wide raw fields
(`W`), format-code × semantic-vector cross (`X`), and controls/falsifiers (`C`).

Each carrier in `kernels/carriers.metal` is our own MSL holding **six distinct
host-known values live in distinct registers across the instruction**, so an
operand-field sweep can identify *which register* a field value selects, and storing
several registers afterwards, so a destination-field sweep can be seen redirecting
the result. Oracles (`harness/oracle.py`) are host-computed with exact `Fraction`
arithmetic at every tie and never consult the GPU.

`packed_half2_hi` could **not be provoked from any MSL shape tried**, so it is tested
MODE A: a synthesised encoding replaces the carrier's own `half_alu`.

## Contamination guards

This sweep ran in a three-experiment GPU batch and implements all of
`FIELD-SWEEP-PROTOCOL.md` §7 plus EXP-0141's finding: a per-carrier **integrity
sentinel** on an independent path (three-way `clean`/`perturbed`/`absent`, because a
length-desync is a *result* and only "nothing executed" is invalid), a **unique
splice-archive path per request**, **no fault or hang concluded from one
observation**, verbatim OS fault-classification strings, and periodic baseline
re-validation that stops the run on a genuine cascade. Two partial captures
(`raw/m4_20260828_run01`, `raw/m4_20260828_run02`) are retained unmodified with their
own `PARTIAL.md`; neither is used for any verdict.

## Reproduction

```sh
cd experiments/EXP-0144-m4-emit-pack
./harness/build.sh work/bin                     # build the READ-ONLY repo tools
python3 harness/oracle.py                       # host oracle self-test (must PASS)
python3 harness/casematrix.py                   # case count + frozen matrix hash
python3 harness/run.py --run-id m4_YYYYMMDD_runNN
python3 analysis/verdicts.py --runs m4_20260828_run03 m4_20260828_run04
```

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE (+ PUBLIC for IEEE-754 / MSL
  format-conversion definitions, used only to write the host oracle, never to
  source an Apple9 encoding fact)
Inputs inspected: kernels/*.metal (authored here) and the machine code compiled
  from them; tools/agx-isa/db.json (this project's own, read-only)
Apple binary introspection: NONE
Reproduction: see above
Evidence: raw/m4_20260828_run03/, raw/m4_20260828_run04/ (append-only JSONL),
  analysis/field_verdicts.json
```
