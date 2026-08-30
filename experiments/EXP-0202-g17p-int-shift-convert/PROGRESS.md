# EXP-0202 — PROGRESS (append-only)

## 2026-08-30 — M0: pre-registration v1 written BEFORE any kernel was authored
`PRE_REGISTRATION.md` frozen as `raw/prefreeze/PRE_REGISTRATION.v1.md`. Repo revision pinned at
`f59821fe5e896b09a1bd33b41e7a9f1b7df6b4b4`. Eight fields, five instructions, the dimension each
field is believed to select named FIRST and the carrier set designed to span it.

## 2026-08-30 — M1: 50 carriers authored, pushed, built on the neo
`kernels/k_sam202.metal` (14 kernels), `k_pc202.metal` (7), `k_iu202.metal` (22),
`k_cvt202.metal` (7). Toolchain rebuilt on the neo from the pinned sources.

## 2026-08-30 — M2: census pass 1 — and it was WRONG, in exactly the documented way
Signature scan + `token_at` cross-check reported `iunary` emitted by 3 carriers. **It is not.**
Adding a sequential tokenizer walk and requiring instruction-BOUNDARY alignment removed all of
them: the hits were interiors of longer instructions (`b_alu10_lo7` at `cvt_i64@46` contains
`27 11 00 02 ..`). Pass 1 is retained as `raw/prefreeze/census_v1.json`; pass 2 is
`raw/prefreeze/census.json`. This is the "movement that is really a different instruction"
failure one step earlier, and it would have manufactured two field verdicts out of nothing.

## 2026-08-30 — M3: the census answers three design questions before any sweep
* `shift_amt_move.src_flag` is **0 in all 6 occurrences** across 50 carriers — the compiler never
  chooses the other value, and the two thread-invariant-amount carriers compile to bytes
  IDENTICAL to the GPR-sourced one. The same-dimension positive control therefore moves to
  **`b_alu10_lo7.src_flag`** — same bit, same 7+1 split, same enum, same 0x?b family — where the
  compiler **does** emit both values.
* `ibitcount.cache` is compiled **0 twice and 1 seven times**: the routing dimension is spanned by
  demonstration, and both splice directions are available.
* `irotate`: byte+6 is the ONLY byte that moves with the rotate amount, at **byte+6 = 4·(32−K)**.
  That converts the `operands` sweep from "did it move" into an EXACT per-value host oracle.

## 2026-08-30 — M4: pilot (`raw/prefreeze/pilot01`, 369 cases, 39.5 s) — CALIBRATION, NO VERDICT CITES IT
Harness end-to-end OK: poison, sentinel, per-value oracle, tokenized mnemonic, majority-of-3.
0 hangs, 0 malformed responses. Three defects found and fixed **before the freeze**:
1. the `iunary` arms' prepatch set only one of the two synthesized bytes, so each arm's own
   baseline was not the synthesized form — now both bytes are prepatched on both arms;
2. `rot_two#1` was in the amount-oracle set but its carrier's expression XORs two rotates, so the
   rotate-by-K oracle could never match — replaced by `rot_k19#0`;
3. prepatched arms' baselines are by design not `ok`, so gate rule 4 is amended (pre-freeze) to
   require **stability** rather than `ok` for those arms.
The amount model already reproduced **5 of 5** modelled values exactly in the pilot.

## 2026-08-30 — M5: contract frozen, gated pair
See `CAPTURE_CONTRACT.json`. `harness/gpuwatch.py` samples the neo's process table every 2 s for
the duration of both gated runs, so the quiet-window claim is a measurement.

## 2026-08-30 — M5a: run id `g17p_20260830_run01` BURNED and RETAINED, not reused
The first launch chained `cd ... && mkdir ... && nohup gpuwatch &`, which backgrounded the whole
chain: `run.py` then executed from `$HOME` and failed, while the `mkdir` had already created
`raw/g17p_20260830_run01` — and `run.py` refuses an existing run id. The directory is retained
with the 63 kB of gpuwatch samples it collected and **is never topped up or reused**
(`SUBAGENT_BRIEF.md`: a partial capture is retained, never reused). The gated pair is
**run02 / run03**. `harness/gated.sh` now starts the sweep first and attaches gpuwatch to the
directory `run.py` created — the only correct order. `CAPTURE_CONTRACT.json` v2 records it.
This is the third instance this week of a state-changing step behind `&&`/`&` not doing what it
looked like it did.
