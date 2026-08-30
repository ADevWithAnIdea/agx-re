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

## 2026-08-30 — M6: `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` landed mid-run — AMENDMENT v3 frozen
The document is normative and wins over this experiment's own §6 gate. `run02` was in flight; it
is **retained in full as the discovery run** and its harness files are NOT edited, so its chain
stays byte-reproducible. The amendment adds beside them: `run2.py` (actual-byte ledger, predicted
outcome bucket, `--order reverse`), `harness/oracles202b.py`, `harness/carriers202b.py`,
`kernels/k_sam2_202.metal` (five operand-PROVENANCE carriers: ALU / thread-position system value /
SIMD lane / overwrite+intervening ALU / control-flow merge), `kernels/k_pc2_202.metal` (a second
disjoint readback plan for `ibitcount.dst`), `analysis/census_b.py`, `analysis/gen_arms_b.py`.
`analysis/verdicts.py` is rewritten onto the six axes (analysis programs may change; raw may not).
`PRE_REGISTRATION.md` gains AMENDMENT v3, frozen **before** its first dispatch.

## 2026-08-30 — M6a: the machine stopped being quiet DURING run02
`ps` on the neo shows `EXP-0201/work/bin/agxrun_persist` and `EXP-0200/t1/work/bin/agxrun_persist_as`
running alongside ours. `raw/g17p_20260830_run02/gpuwatch.jsonl` records it sample by sample. This
is exactly why the quiet window is measured rather than claimed, and it is another reason run02 is
scored as discovery only.

## 2026-08-30 — M6b: a movement-scoring defect caught in our OWN discovery run
The outcome-partition key included the `outcome` label, and `ok` / `unexpected_ok` are the SAME
hardware observation (the carrier's vector was reproduced) differing only in what the oracle
PREDICTED. Without collapsing them, `shift_amt_move.src_flag` scores as MOVED at the compiled
source index on four carriers **purely because the prediction differs at the compiled value** —
the observed word vectors are byte-identical. Fixed in `analysis/verdicts.py` (`OUTCOME_NORM`).
This is the corrections document's "a difference from baseline is not a semantic oracle" in its
sharpest form, and it was found by re-deriving from raw rather than reading a summary.

## 2026-08-30 — M7: run03 (confirmation A, forward) complete — and Gate A caught its first thing
10162 cases in 405 s, 0 hangs, 0 malformed responses, 706 contained faults, 2 invalid runs.
**Gate A reported 3232 failures — and every one of them is a defect in the CHECK, not the
dispatch.** The driver compared the requested value against the pinned tokenizer's decode of the
WHOLE db field; the arms that sweep a SUB-SPAN of a wider field (`irotate.operands` is 40 bits and
its byte-wise arms request 8 of them, `irotate.tail` is 32 bits) therefore compared 8 bits against
40. `requested_bytes == actual_bytes` is **TRUE in all 3232**. §9 of the corrections document is
explicit that this is reclassified from raw, not re-run: `analysis/verdicts.py` now re-derives
Gate A offline from `actual_bytes` + `start` + `width` with a THIRD independent bit extractor, and
additionally records how many cases the tokenizer's own decode independently confirms.

## 2026-08-30 — M7a: the confirmation window is NOT quiet, and it is MEASURED
`raw/g17p_20260830_run03/gpuwatch.jsonl`: **201 of 201 samples** carry a foreign GPU process
(`EXP-0206`, `EXP-0200`). Under `PRE_REGISTRATION.md` §6 rule 8 and Gate E the cross-run figure is
reported **CONTAMINATED**; the EXP-0160 validity filter is applied instead (two agreeing
sentinel-valid dumps stand, because contamination can destroy an observation but never fabricate a
coherent one). No promotion rests on a clean-window claim that was not measured.
