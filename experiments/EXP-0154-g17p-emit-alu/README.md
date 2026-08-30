# EXP-0154 — making the float and integer ALU *emittable* on G17P

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, Metal family Apple9). Every claim here is a **G17P** claim, measured directly
on the documentation target — not promoted from M4.

## Question

`tools/agx-isa/validation.json` reports **38 of 171 instructions emittable** and 443 of
1036 fields at emitter grade. An instruction is emittable only when *every* field in its
`db.json` descriptor is `hardware-run` or `isolated-byte-diff`
(`docs/evidence-classification.md` section 2). **133 fields across 32 float/integer ALU
instructions** are below that bar. Which of them can be closed on G17P, and what exact
per-field rule must an emitter apply?

## Method

The load-bearing idea is a **synthesized program around a lifted anchor block**:

```
mov_imm seeds r0..r15 (16 distinct values)      <- WE choose every operand the
PRE  sentinel  -> stored to memory                  instruction can name
[ BLOCK lifted BYTE-FOR-BYTE out of the compiled form of our own MSL,
  with exactly ONE db.json field mutated ]
dump all 16 registers -> 16 output words
POST sentinel  (its register written AFTER the block) -> stored
stop
```

Three things fall out of that shape:

1. **The operand map becomes decodable.** EXP-0139 could not map 44 operand/condition
   selectors because a wrong selector value pointed at a register its carrier never
   seeded, so every wrong value looked alike. Here every register holds a distinct value,
   so the result *identifies* which register was read.
2. **EXP-0138's sentinel trap is closed.** EXP-0138 lost six sweeps because reading r11 as
   a source **zeroes it** (release-on-read) and that destroyed its own witness. Here the
   PRE sentinel is already in memory before the block runs and the POST sentinel's
   register is written after it, so neither can be reached by the instruction under test.
3. **Release-on-read becomes an instrument.** Dumping all 16 registers means the register
   that went to zero *is* the register the swept descriptor named — an operand oracle that
   does not depend on the instruction's arithmetic at all.

The oracle for `ok` is the **full 16-register architectural state** matching the unmutated
anchor's, read out of a buffer poisoned with `0xDEADBEEF` before every dispatch. That is
strictly stronger than a single output word.

## Reproduction

```sh
export SSHPASS='...'                       # never committed
harness/sync.sh push                       # -> ~/agxre/EXP-0154 on the neo
# on the neo:
python3 harness/anchors.py                 # compile our MSL, tokenize, locate anchors
python3 harness/smoke.py                   # pilot: scaffold + sentinels + sensitivity
python3 harness/run.py --run g17p_20260829_run02 --order forward
python3 harness/run.py --run g17p_20260829_run03 --order reverse
# back in the repo:
harness/sync.sh pull g17p_20260829_run02
harness/sync.sh pull g17p_20260829_run03
python3 analysis/verdicts.py raw/g17p_20260829_run02 raw/g17p_20260829_run03
python3 analysis/emittable.py              # instructions this experiment unblocks
```

## Files

| path | what |
|---|---|
| `PRE_REGISTRATION.md` | frozen hypotheses, coverage rule, oracle, falsifiers, promotion rule |
| `CAPTURE_CONTRACT.json` | frozen source hashes, matrix hash, raw schema, timeouts, `amendments` |
| `kernels/probes.metal` | 27 authored probe kernels, one per instruction family |
| `kernels/carrier_dag.metal` | authored SYNTH host (binding shape + a long `_agc.main`) |
| `harness/isa_helpers.py` | seeds, stores, sentinels, program builder |
| `harness/anchors.py` | compile + tokenize + locate the anchor blocks |
| `harness/casematrix.py` | the frozen case matrix |
| `harness/run.py` | gated-run driver (majority-of-3, victim flags, baseline revalidation) |
| `analysis/verdicts.py` | raw -> `analysis/field_verdicts.json` |
| `raw/` | append-only per-case evidence, including every failure |

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/probes.metal and kernels/carrier_dag.metal (authored by us for
  this experiment) and the AGX machine code the PUBLIC runtime API compiled from that
  source; tools/{shdump,agxtest,agx-isa} used READ-ONLY and unmodified.
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled,
  symbol-dumped, strings-scanned or debugged. The only machine code inspected or spliced
  is the compiled form of our own MSL.
Reproduction: see above.
Evidence: raw/g17p_20260829_run01 (retained partial, matrix v1),
          raw/g17p_20260829_run02, raw/g17p_20260829_run03 (gated pair, matrix v2),
          work/smoke/smoke.json, work/anchor_report.json
```
