# EXP-0205 — SIMD / subgroup fields on G17P

**Six fields, three instructions:** `simd_ballot.{pred,cache}`,
`simd_reduce.{op,dtype}`, `simd_shuffle.{dir,cache}` — the pairs
`docs/isa/emit-worklist.md` lists as blocking each instruction from emittable.

**Target:** Apple A18 Pro / **G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`,
macOS 26.6, Metal family Apple9), `192.168.170.254`. **Measured SIMD width 32.**

---

## The question

Can an implementer *choose* a value for each of these six fields and predict what
the hardware does? Two of them — the `cache` bits — had been withheld twice
(EXP-0163, EXP-0172) as "never observed to move an observable", and both times
the standing rule says that is a **carrier failure until proven otherwise**: a
field that never moves is promotable only if the carriers differ *in the
dimension the field controls*.

## Method

Compile our own MSL, locate the single occurrence of the target descriptor by
its `match` signature in the compiled `_agc.main`, patch **one field, directly in
the bytes**, dispatch on real hardware, and read back **32 (or 256) separate
per-lane words** so the oracle can predict a whole vector rather than "something
was written".

Two revisions, both retained:

- **Revision A** — 11 carriers, 35 arms, 3708 cases/run, two gated runs
  (`raw/g17p_20260830_run01`, `run02`).
- **Revision B** — adds the four **multi-invocation ordering litmus** carriers
  and the Gate-A actual-byte ledger required by
  `RE_EXPERIMENT_PROCESS_CORRECTIONS.md`; 16 carriers, 51 arms, 5092 cases/run,
  two gated runs in **forward and reversed** case order
  (`raw/g17p_20260830_runB01`, `runB02`).

Every target field is swept **densely over its entire encodable range**.

## What decided each field

| | |
|---|---|
| **Per-lane read-back** | 32 output words, so reduce / inclusive scan / exclusive scan and broadcast / xor are *different predicted vectors*, not different scalars. |
| **Lane divergence** | The ballot predicate is an asymmetric per-lane mask, so ballot-of-predicate and the all-active mask are different observations. A uniform predicate makes them identical **by construction**. |
| **A named semantic catalogue** | `analysis/semantics.py` predicts, from our authored inputs alone, every integer and float reduction in reduce / inclusive / exclusive shape, every broadcast lane and xor mask, both ballot masks — so an observation is *identified*, not merely seen to differ. |
| **Detection-power controls** | Every arm carries a control on the same instruction at the same occurrence (`psrc`/`src`/`lane`). An arm whose control never fires is `carrier-undecidable`. |
| **An in-dimension control for `cache`** | A dense `dst` sweep that makes the instruction overwrite the register its own source occupies, proving the carrier can see a change in the operand's *post-instruction* content. |
| **A multi-invocation litmus** | 4 threadgroups × 2 simdgroups, cross-simdgroup threadgroup-memory exchange, a cross-threadgroup device atomic checked against a host total, operand re-read after two barriers, unique per-invocation codewords, three disjoint readback plans, pre **and** post sentinels. |

## Headline results

- **`simd_reduce.op`** — live and semantically mapped: `{0,1,2,3} →
  {ior, isum, smax, umax}` reduce, 4/4 against independent host predictions.
  Only **bits [2:0]** are decoded; bits [7:3] are inert on all four carriers.
- **`simd_reduce.dtype`** — live and semantically mapped: `{3,7} → reduce,
  9 → inclusive scan, 11 → exclusive scan`, 4/4. Bits [7:4] inert on the integer
  carriers.
- **`simd_shuffle.dir`** — live and semantically mapped: `0 → every lane reads
  lane 5`, `1 → lane t reads lane t^5`, on 5 arms with **both** baseline values.
- **`simd_shuffle.cache` — LIVE. The two prior INERT verdicts were a carrier
  failure.** Clearing it on the carriers where the compiler set it makes the
  shuffle return foreign data or a silent zero.
- **`simd_ballot.cache`** — accepted-inert over 256/256 values × 6 carriers
  including the multi-invocation litmus; **global role unknown**.
- **`simd_ballot.pred`** — inert over 16/16 × 6 carriers, and the adversarial
  probe found the form selection is carried by **other bytes**. A `db.json`
  descriptor defect.

Full numbers, six-axis verdicts and every caveat: `RESULTS.md`,
`analysis/field_verdicts.json`, `analysis/report_revB.txt`.

## Reproduce

```sh
export SSHPASS='...'            # SSHPASS ONLY; never written to any file
export NEO=192.168.170.254
bash harness/sync.sh push
bash harness/sync.sh build
python3 harness/verify_remote.py                       # separate step; exit 0 required
python3 analysis/gate_selftest.py                      # offline, 13/13, no device
bash harness/sync.sh shell 'cd $HOME/agxre/EXP-0205 && python3 -B analysis/calibrate.py <tag>'
bash harness/sync.sh shell 'cd $HOME/agxre/EXP-0205 && python3 -B analysis/gen_arms.py'
bash harness/sync.sh shell 'cd $HOME/agxre/EXP-0205 && python3 -B run.py --run-id <id>'
bash harness/sync.sh shell 'cd $HOME/agxre/EXP-0205 && python3 -B run.py --run-id <id2> --reverse'
bash harness/sync.sh pull
python3 analysis/verdicts.py raw/<id> raw/<id2>
python3 analysis/report.py   raw/<id> raw/<id2>
```

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: only our own MSL in kernels/ and the machine code compiled
                  from it; the public dougallj/applegpu notes in gpu_knowledge/
                  were used as the SOURCE OF HYPOTHESIS H5 only, never of a value
Apple binary introspection: NONE
Reproduction: the commands above
Evidence: raw/prefreeze/, raw/pilot01/, raw/g17p_20260830_run01, run02,
          runB01, runB02, raw/adversarial01/, CAPTURE_CONTRACT.json
```
