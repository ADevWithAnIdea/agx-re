# EXP-0219 — the five dispatches EXP-0218 and EXP-0213 named

**Question.** Two careful experiments ended by naming, exactly, the dispatch that would
settle what they could not decide. This experiment does those dispatches and **opens no new
question**.

| # | question | named by | verdict |
|---|---|---|---|
| A1 | is `imad`'s addend-source selector byte+9 **bit 3** on G17P, or bit 1? | EXP-0218 §6.1 | **SETTLED — bit 3**, G17P-direct |
| A2 | is the fetch index **5 bits** or **8**? | EXP-0218 §6.2 | **the 5-bit reading is REFUTED**; the index is **at least 7 bits**; bit 2 of the high field is **still undecidable** |
| A3 | does a 32-bit fetch pair `(K, K+1)` or read word `K>>1`? | EXP-0218 §6.3 | **SETTLED — word**, on two carriers |
| A4 | is the immediate branch true across all 32 K **on G17P**? | EXP-0218 §6.4 | **SETTLED — yes**, and over all 256 immediate values |
| B | what does `tex_sample.mode` **bit 6** do, and why only on `msread`/`mslodq`? | EXP-0213 §2.5 | **it is not nondeterminism.** It makes the result a **strictly periodic function of the dispatch index** (period 4 or 8). Live on 4 of 9 arms, inert on 5. Its *semantics* remain unmapped |

**Target: Apple A18 Pro / G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6,
Metal family Apple9), `192.168.170.254`. **Nothing ran on the M4.**

**Clean-room category: OWN-SHADER + HW-PROBE.** Every byte compiled, spliced, decoded or
inspected is the compiled form of MSL in `kernels/`, which we wrote. **No Apple binary was
disassembled, decompiled, symbol-dumped, strings-scanned or introspected at any point.**

## Method in one paragraph

Part A splices a 12-byte `imad` lifted verbatim from our own compiled `k_imad` into a
program we assemble instruction by instruction (seeds → PRE sentinel → the mutated block →
16-register dump → POST sentinel → `stop`) over the whole `_agc.main` of a compute carrier,
and reads back all sixteen architectural registers against a poisoned buffer. Part B splices
one 14-byte `tex_sample` into the compiled fragment stage of our own render carriers and
reads back the rendered surface at seven fixed probe pixels. Both re-read the spliced window
back **from the file handed to Metal** and decode it with a pinned database before any
number is used (Gate A).

## Layout

| path | what |
|---|---|
| `PRE_REGISTRATION.md` | the frozen contract: hypotheses, competing models, refuters, gates, budgets. Frozen before any build |
| `AMENDMENT-01.md`, `AMENDMENT-02.md` | each frozen **before** the dispatch that used it |
| `CAPTURE_CONTRACT.json` | authored-blob hashes, anchor, carrier geometry, matrix hashes, the single declared fit, the designated Gate E pairs |
| `kernels/` | our own MSL. New here: `probes_imad.metal`, `carrier_const.metal`, `k_msread1.metal`. Copied byte-identical: `carrier_dag.metal` (EXP-0160), `k_*.metal` (EXP-0204) |
| `harness/` | new: `casematrix_a.py`, `oracle_a.py`, `run_a.py`, `imad_carrier.py`, `run_b.py`, `calib_a.py`, `capture_*.sh`, `push*.sh`. Copied byte-identical: `imad_helpers.py` (EXP-0160 `isa_helpers.py`, only `_find_isadb` retargeted), `gfrun4.m`/`runner4.py`/`carriers.py`/`oracle.py`/`arms.py`/`shdump.m` (EXP-0204), `quietsample.py`/`gpusnap.py`/`neo.sh`/`pull_run.sh` (EXP-0213) |
| `pinned_b/`, `work/frozen/` | pinned ISA database copies (part B uses EXP-0204's pinned DB so the frozen arm bytes still check; part A uses the current repo DB) |
| `raw/` | 12 capture directories, append-only, pulled back **one at a time** |
| `analysis/` | repeatable scorers; `field_verdicts.json` carries the six axes |
| `RESULTS.md` | observations vs interpretation, exact numerators, limitations, verdicts |

## Commands

```sh
# part A (compute) -- per capture, on the neo
sh harness/capture_a.sh <run_id> dag|const forward|reverse <cap_s>
python3 analysis/score_a.py ; python3 analysis/score_a_final.py
python3 analysis/score_a2_index.py

# part B (render) -- per capture, on the neo
sh harness/capture_b.sh <run_id> ruler|repeat|sweep forward|reverse "<extra>" <cap_s>
python3 analysis/score_b_repeat.py ; python3 analysis/score_b_period.py
python3 analysis/score_b_sweep.py  ; python3 analysis/score_b_partition.py
python3 analysis/quiet_table.py
```

**Nothing was committed by this experiment, and no label, `tools/agx-isa/` file, `docs/`
page or `PROVENANCE.md` row was changed.**
