# EXP-0200 — the control-flow / ray-query compact-word family, at `_instruction`

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`,
5 cores, macOS 26.6, Metal family Apple9). **Nothing ran on the M4.**

## The question

Six descriptors — `n1_word`, `n2_compact2`, `n3_word`, `rtq_pred`, `n4_cf_word`,
`n4_rt_word` — are blocked at `_instruction: tokenization-only`. That label
means we can **decode** the encoding and have never shown the hardware does what
the descriptor claims. `_instruction` alone blocks 79 descriptors corpus-wide,
more than any named field.

Read what those descriptors actually claim about the silicon and it is a
**length**: *"length 2 / 4; +N lands on the next op leader in every corpus
occurrence"*. Corpus framing is our tokenizer agreeing with itself, and a round
trip cannot help — it is symmetric across encode and decode, and EXP-0170 showed
the repo's own suite passes 173 cases with **zero** failures against an
assembler that could not clear a bit.

So this experiment asks the hardware, by **generating** the encodings ourselves
at program points the compiler never chose.

## The instrument, in one picture

Three instructions already carry `_instruction: hardware-run` with known
lengths: `stop` (`0e 00 00 00`, 4, and its 24-bit body is HW-proven free
filler), `mov_imm` (`0c 20`, 2), `icmp_pred` (`0a ..`, 6).

Take an 8-byte **hole** — a run of whole instructions on the executed path,
after the sentinel store and before the result store — and overwrite it with
`<candidate word> ++ stop ++ padding`. Then read back the **poisoned** buffer.

```
   consumed exactly len(W)      ->  the planted stop is decoded  ->  out[0] still 0xDEADBEEF
   consumed more than len(W)    ->  the stop is swallowed        ->  out[0] written
```

`out[1] = 7.5` (the integrity sentinel, stored through an independent path
before the hole) separates *the program ran and stopped where we told it* from
*it never ran at all*. That distinction is the whole measurement, and it exists
only because the buffer is poisoned rather than zeroed.

Four fills calibrate every hole, and two of them must fail in **opposite**
directions before any candidate is read:

| fill | stop at | prediction | role |
|---|---|---|---|
| `C_reach` — `stop` alone | +0 | `not_written` | the hole is executed, before the result store |
| `A_icmp6` — `0a 00` ++ stop | +2 | **`written`** | a 6-byte word hides the terminator: over-read is visible here |
| `A_mov2` — `0c 20` ++ stop | +2 | `not_written` | known-2-byte yardstick at the 2-byte candidates' offset |
| `A_ifpush4` — `0f 05 00 54` ++ stop | +4 | `not_written` | known-4-byte yardstick at the 4-byte candidates' offset |

A hole that fails any of these supports **no** verdict — confirming or refuting
— and is counted as barred.

A second arm asks the complementary question: substituted for a *different*
same-length word at a natural occurrence, does a generated candidate leave the
carrier's non-zero oracle intact?

## Layout

```
PRE_REGISTRATION.md     frozen before any build; §8 is the gate
CAPTURE_CONTRACT.json   every authored + pinned blob hash, timeouts, revision
kernels/k_w200.metal    six compute carriers authored here
harness/words200.py     the fill catalogue and the HOST prediction for each fill
harness/carriers200.py  dispatch shape, authored inputs, non-zero host oracles
harness/locate200.py    pinned tokenizer, walk boundaries, hole finding
run200.py               the sweep driver (runs on the neo)
analysis/census200.py   pre-freeze census (where to look)
analysis/gen_arms200.py freezes harness/arms200.json; its docstring IS the rule
analysis/verdicts200.py THE GATE; writes analysis/t2_verdicts.json
analysis/contract200.py freeze/check + re-derivation of every byte constant
t1/                     EXP-0187's apparatus, VERBATIM (27 blobs, hash-checked)
raw/                    append-only evidence
```

## Target 1: EXP-0187's contract, honoured unchanged

EXP-0187 froze a 25-arm contract for `n4_rt_word.dst`, completed **one** run,
and recorded that the field is *"one clean gated pair away from a verdict"*.
`t1/` is that apparatus carried in byte-for-byte. `harness/verify_remote200.py`
re-hashes all 27 blobs against EXP-0187's own `CAPTURE_CONTRACT.json` and
**refuses to run** on any difference, so "honoured unchanged" is a check rather
than a claim. Its verdict is computed by its own frozen gate,
`t1/analysis/verdicts.py`, which this experiment does not touch.

**The hazard wall is entered deliberately, not avoided.** EXP-0187 mapped
`fault ⟺ (dst & 0b110) == 0b100` — 64 of 256 values, two carriers, zero
exceptions. `DST_VALUES` here contains four values that satisfy the predicate
and twelve that do not, dispatched at **synthesized** sites, to test whether the
wall belongs to the encoding or to the occurrence. There is no hang budget:
protocol §3(c) is explicit that a budget cannot characterise a contiguous hazard
— it guarantees the region is never mapped.

## Reproduction

```sh
export SSHPASS='...'                       # SSHPASS ONLY; never written to a file
export NEO=192.168.170.254

python3 analysis/contract200.py encodings  # re-derive every byte constant
python3 analysis/contract200.py freeze
bash    harness/sync200.sh push
python3 harness/verify_remote200.py        # SEPARATE step; exit 0 required
bash    harness/sync200.sh build

# pre-freeze calibration (no verdict may cite it)
bash harness/sync200.sh shell 'cd ~/agxre/EXP-0200 && python3 analysis/census200.py'
bash harness/sync200.sh shell 'cd ~/agxre/EXP-0200 && python3 run200.py --run-id prefreeze/holeprobe01 --probe-holes'
bash harness/sync200.sh shell 'cd ~/agxre/EXP-0200 && python3 analysis/gen_arms200.py raw/prefreeze/holeprobe01'
bash harness/sync200.sh pullarms
python3 analysis/contract200.py freeze     # re-freeze with arms200.json hashed
bash    harness/sync200.sh push
python3 harness/verify_remote200.py

# gated pairs (target 1 and target 2), nohup'd so the driving session's timeout
# cannot kill them -- EXP-0187 lost a whole run exactly that way
bash harness/sync200.sh shell 'cd ~/agxre/EXP-0200/t1 && nohup python3 run.py --run-id g17p_YYYYMMDD_t1run01 > ../work/t1run01.log 2>&1 &'
bash harness/sync200.sh shell 'cd ~/agxre/EXP-0200    && nohup python3 run200.py --run-id g17p_YYYYMMDD_t2run01 > work/t2run01.log 2>&1 &'
#   ... and again for run02 ...
bash harness/sync200.sh pull

python3 t1/analysis/verdicts.py t1/raw/<t1run01> t1/raw/<t1run02>
python3 analysis/verdicts200.py raw/<t2run01> raw/<t2run02>
python3 ../../tools/agx-isa/wave_audit.py .
```

## Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected:      kernels/k_w200.metal and t1/kernels/*.metal -- authored by
                       us -- and the `_agc.main` bytes the public Metal runtime
                       compiled from them, overwritten with byte values we chose.
                       Encodings are re-derived from the PINNED db.json, which
                       this project built from its own compiled shaders.
Apple binary introspection: NONE
Reproduction:          the commands above
Evidence:              raw/ (target 2), t1/raw/ (target 1), append-only
```
