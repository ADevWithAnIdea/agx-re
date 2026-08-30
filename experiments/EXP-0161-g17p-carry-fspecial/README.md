# EXP-0161 — `carry_gen`, `mov_zext16`, `ibfe(offset,width)` re-done with a carrier that is actually live; and `fspecial` opened

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores, macOS
26.6, Metal family Apple9, `Mac17,5`), `192.168.10.243`. **Every verdict here is
`target: G17P`.** No M4 GPU work; no M5.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/probes.metal (13 authored kernels) and
  kernels/carrier_seed.metal, both authored by us for this experiment, and the AGX
  machine code the PUBLIC runtime API compiled from that source.
  tools/{shdump,agxtest,agx-isa} used READ-ONLY and unmodified.
Apple binary introspection: NONE
Reproduction: see "Reproduction" below
Evidence: raw/ (append-only), analysis/, work/
```

## 1. The two questions

### Q1 — a carrier defect, not a hardware fact
EXP-0154 swept `carry_gen` (5 blocking fields) and `mov_zext16` (4) on G17P and **promoted
nothing from either**: both failed their pre-registered falsifier — forcing byte0 of the
instruction under test to `0x00` still reproduced the whole 16-register baseline. EXP-0154
diagnosed its own cause in `RESULTS.md` §5: its integer seeds were all `<= 127`, so the
lifted 64-bit low-word add never carried and `carry_gen` was a no-op *in that carrier,
whatever its encoding*. The same defect makes `mov_zext16` the identity (`x & 0xFFFF == x`
for `x <= 127`) and leaves `ibfe.offset` / `ibfe.width` only weakly live, which is why
EXP-0154 reported its `ibfe` reproduction tests INCONCLUSIVE.

`mov_imm`'s immediate is only seven bits (EXP-0128/EXP-0140), so a seed that carries cannot
come from `mov_imm` at all. This experiment seeds r0..r14 with a **`device_load` per
register** out of an authored SEED buffer, which gives arbitrary 32-bit values.

### Q2 — `fspecial`, never opened
`fspecial` has 11 fields, all `corpus-correlation` or `tokenization-only`, and is flagged
`emit_unsafe`. EXP-0138 opened the arm, hit three reproducible GPU hangs at byte+3
192/193/194 and safety-stopped. The **safe region (byte+3 < 192) had never been swept at
all**, and neither had the other ten fields.

## 2. Method

Two carrier styles, deliberately different, so every load-bearing claim has a second method:

* **SYNTH+LIFTED** — `_agc.main` is wholly replaced by a program assembled from
  `tools/agx-isa`'s own field rules: PRE sentinel -> 15 `device_load`s seeding r0..r14 ->
  the block lifted byte-for-byte from our own compiled MSL (one field mutated) -> a
  16-register dump -> POST sentinel -> `stop`. Oracle: the full architectural state.
* **INPLACE** — our own probe kernel exactly as the compiler produced it, one instruction
  mutated in place, judged against a **host-computed** functional oracle.

and then, third and strongest:

* **GENERATION** (`harness/gen.py`) — encodings the compiler never emitted, built from the
  recovered model, with the whole 16-register result predicted **host-side before
  dispatch**.

## 3. Layout

```
PRE_REGISTRATION.md     hypotheses H1..H7, falsifiers F1/F1b/F2/F3/F4, stop rules
CAPTURE_CONTRACT.json   frozen matrix hash, authored-input hashes, anchors, stimulus, gates
harness/isa_helpers.py  instruction builders; the device_load seeding and WHY it needs two waves
harness/cases.py        the frozen case matrix, carriers, stimulus, supplementary arms
harness/anchors.py      compile our MSL -> tokenize -> locate the anchor blocks
harness/run.py          gated-run driver (majority-of-3, victim tagging, baseline refresh)
harness/gen.py          the generation proof
harness/adjudicate.py   FIELD-SWEEP-PROTOCOL 7A fault re-adjudication
harness/smoke.py        pre-freeze gate check (not evidence)
harness/pilot_seed.py   the 8-variant pilot that isolated the seeding defect
kernels/probes.metal    13 authored probe kernels
kernels/carrier_seed.metal  the SYNTH carrier (buffer0 = read-back, buffer1 = SEED vector)
analysis/verdicts.py            gates, cross-run gate, per-field verdicts, emittability
analysis/fspecial_functions.py  which FUNCTION each fspecial selector value computes
analysis/precision.py           what fspecial byte+8 bit0 actually does
raw/                    append-only: two gated runs, three generation runs, the danger arm,
                        the supplementary runs, the adjudication, and the pre-freeze pilots
```

## 4. Reproduction

```sh
export SSHPASS=...                       # the neo's password; never committed
harness/sync.sh push                     # authored harness + kernels + frozen agx-isa

# on the neo, under ~/agxre/EXP-0161, with AGX_TOOLS=$HOME/agxre/tools:
python3 harness/anchors.py                                   # anchor blocks
python3 harness/smoke.py                                     # pre-freeze gate check
python3 harness/pilot_seed.py                                # the seeding pilot
python3 harness/run.py --run g17p_20260829_run01 --order forward
python3 harness/run.py --run g17p_20260829_run02 --order reverse
python3 harness/gen.py  --run g17p_20260830_gen03            # generation proof
python3 harness/run.py --run g17p_20260830_supp02 --supp  --order forward
python3 harness/run.py --run g17p_20260830_supp03 --supp  --order reverse
python3 harness/run.py --run g17p_20260830_danger01 --danger   # DEVICE-RESETTING, see below
# --supp2 (the D4_FSPEC_FLOOR round-family arm) is BUILT BUT WAS NOT RUN; see
# RESULTS.md section 9 for why, and run it with:
#   python3 harness/run.py --run <new-id> --supp2 --order forward
python3 harness/adjudicate.py --run g17p_20260830_adj01

harness/sync.sh pull                     # bring raw/ back into the repo
python3 analysis/verdicts.py
python3 analysis/fspecial_functions.py
python3 analysis/precision.py
```

**This experiment reset the GPU 1,571 times** (`RESULTS.md` §8.1). `--danger` accounts for
65 of those by construction — every value of `fspecial` byte+3 in 192..255 returns
`kIOGPUCommandBufferCallbackErrorHang` — and the `E2_FSPEC_EST_RCP` arm inside `--supp` for
roughly 300 per run. Each reset discards other agents' in-flight command buffers. Both were
pre-announced in `PROGRESS.md` per FIELD-SWEEP-PROTOCOL §7 "Courtesy, not a rule". **Do not
re-run either casually**, and note in `PROGRESS.md` before you do.

## 5. What this experiment did NOT do

* It did not edit `tools/agx-isa/db.json`, `validation.json`, `docs/`, or `PROVENANCE.md`,
  and it did not commit. Corrected models are recorded under `db_defects` in
  `analysis/field_verdicts.json` for the orchestrator to merge.
* It did not touch the A18 documentation host, run `macvdmtool`, or probe M5.
* It did not sweep `fspecial` on a fragment/texture carrier; everything here is compute.
