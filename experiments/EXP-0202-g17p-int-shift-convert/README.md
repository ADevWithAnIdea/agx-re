# EXP-0202 — integer / shift / rotate / convert: eight fields, five instructions, on G17P

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6
build 25G5043d, Metal family Apple9), `192.168.170.254`. **Nothing ran on the M4.**

## The question

Eight fields across five instructions block their families from being *emittable*. Each is one or
two fields away, and three of them already carry a **documented refusal** — three different
refusals, needing three different fixes:

| field | current label | why it is still open |
|---|---|---|
| `irotate.operands` | `untested` | EXP-0189 withheld **UNSTABLE**: 1276 values, 2365 moved, but **one arm** and cross-run instability. It moves enormously; it needs a **quiet window** and a **second arm**, not more values. |
| `shift_amt_move.src_flag` | `untested` | EXP-0189 withheld **INERT-SINGLE**: 2 values, 1 arm, **0 moved**. Domain is 2 values — nothing to sweep. The whole question is whether the one arm could express what the field selects. |
| `cvt_f2i.b9` | `single-template-inference` | EXP-0168 PROGRESS (g): **INERT-SINGLE, not UNSTABLE** — 256/256 `ok` in both runs, one distinct observed payload. Needs a second, structurally different carrier. |
| `ibitcount.cache` | `untested` | inert on the one carrier that had detection power (EXP-0169). No documented refusal — open ground. |
| `ibitcount.dst` | `untested` | swept 0..255 by EXP-0169 but **explicitly not ruled on** there (verdict deferred to another experiment). |
| `iunary.b1` | `untested` | **no raw exists at all** — never dispatched. |
| `iunary.opsel` | `untested` | **no raw exists at all** — never dispatched. |
| `cvt_f2i._instruction` | `corpus-correlation` | the instruction-level label predates the G17P pivot. |

## Method

Pure **in-place splicing**: every case is the compiled form of one of our own MSL kernels with
**exactly one field** of **one instruction occurrence** overwritten, dispatched with real inputs
against a **host-computed, per-value oracle**. No synthesized programs, no lifted anchors — the
instruction under test keeps the dataflow the compiler gave it, so a field that reaches the output
in the real program still reaches it here.

Three instruments on every case (FIELD-SWEEP-PROTOCOL §7): output buffer pre-filled with
**`0xDEADBEEF+i` poison**, an **integrity sentinel** written through a path independent of the
instruction under test, and the **OS fault-classification string** recorded on every non-`ok` case.
The **tokenized mnemonic of the mutated bytes** is recorded on every case, so "movement" that is
really a different instruction is visible in the raw.

`harness/gpuwatch.py` samples the target's process table for the duration of every gated run, so
"the machine was quiet" is a **measurement**, not a claim.

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (authored by us) and the _agc.main bytes the public Metal
                  runtime compiled from them
Apple binary introspection: NONE
Reproduction: analysis/census.py -> analysis/gen_arms.py -> run.py -> analysis/verdicts.py
Evidence: raw/g17p_20260830_run0*/sweep.jsonl (append-only), manifest.json
```

No Apple binary was disassembled, decompiled, symbol-dumped, or otherwise introspected. The only
machine code inspected is the compiled form of MSL in `kernels/`, which we wrote.
