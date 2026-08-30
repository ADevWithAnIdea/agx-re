# EXP-0171 — close `ilogic` on G17P, and pull the `srcA` / `tail` levers

**Target: A18 Pro / G17P** (`users-MacBook-Neo.local`). Status board:
`../../docs/P0-P1-CLOSURE.md`. Rows served: **P0.6 / P0.8 / P1.3** (shader ISA — prove the
*encoder* can synthesise arbitrary legal field values, not merely tokenize them).

## The question

1. **`ilogic`.** `EXP-0166` §2.1 left a live M4↔G17P contradiction it withheld by rule.
   On **M4** `ilogic.outmod` is dense-live over 0..255 from a **store-consumed** carrier —
   128 values move the observable and every value with bit 7 clear silently zeroes. On
   **G17P** the same field read inert from a **16-register-dump** carrier (EXP-0154), and
   EXP-0164 withdrew that verdict for single-carrier inertness. EXP-0166's prescription:
   *one G17P `ilogic` arm with a store-consumed observable settles it.*
2. **The `srcA` / `tail` levers.** After `dst` (35 descriptors, EXP-0168's),
   `emit_worklist.py` ranks `srcA` (17) and `tail` (15) as the most load-bearing field
   NAMES. Six further arms, ranked by distance-to-emittable.

## Method

Three carrier styles, chosen so that the pairs differ **in the dimension the field under
test controls** — the EXP-0164 rule that two carriers identical in that dimension are one
carrier:

| style | observable | operands | consumer |
|---|---|---|---|
| **NAT** | `out[]` in device memory | LOADED from device buffers | the **compiler's own `device_store`** |
| **SYNTH** | the 16 GPRs, dumped | `mov_imm`-seeded | a later dump instruction |
| **FRAME** | the 16 GPRs + two framing markers | `mov_imm`-seeded | a later dump, with a 6B+2B instruction pair immediately after the block |

Every case mutates exactly **one byte**, densely over 0..255, spliced as **raw bytes**;
`isadb.assemble()` is never on the sweep path (DEF-0166-1: an OR cannot clear a bit, and 53
fields were silently under-swept through it). `db.json` FIELDS are recovered offline by the
EXP-0166 A5 decomposition. Fields wider than a byte also get the FIELD-SWEEP-PROTOCOL §3.3
set. Read-back buffers are poisoned `0xDEADBEEF`; NAT carries its integrity sentinels in a
**separate device buffer**. For every NAT integer kernel the comparator is a **host-computed
oracle** with no GPU involvement.

Full frozen design, hypotheses, refuters, falsifiers and promotion rule:
**`PRE_REGISTRATION.md`** + **`CAPTURE_CONTRACT.json`** (frozen before any dispatch).

## Commands

```bash
export SSHPASS='...'                      # never written to a file
harness/sync.sh push                      # authored harness/kernels/frozen-db -> the neo
ssh user@$NEO 'cd ~/agxre/EXP-0171 && python3 harness/anchors.py'        # step 0, COMPILE-ONLY
harness/sync.sh pullwork
ssh user@$NEO 'cd ~/agxre/EXP-0171 && python3 harness/run.py --run g17p_20260830_run01 --order forward'
ssh user@$NEO 'cd ~/agxre/EXP-0171 && python3 harness/run.py --run g17p_20260830_run02 --order reverse'
harness/sync.sh pull g17p_20260830_run01 ; harness/sync.sh pull g17p_20260830_run02
python3 analysis/coverage.py     raw/g17p_20260830_run01 raw/g17p_20260830_run02
python3 analysis/emit_verdicts.py raw/g17p_20260830_run01 raw/g17p_20260830_run02
```

## Clean-room category

```text
OWN-SHADER + HW-PROBE
Inputs: kernels/probes.metal + kernels/carrier_dag.metal (authored by us) and the AGX
        machine code the PUBLIC Metal runtime API compiled FROM THEM.
Apple binary introspection: NONE. The only machine code inspected or spliced is the
        compiled form of our own MSL.
```

Results, with observation separated from interpretation: **`RESULTS.md`**.
