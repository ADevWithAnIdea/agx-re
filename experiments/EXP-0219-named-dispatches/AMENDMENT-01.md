# EXP-0219 — AMENDMENT 01

**Frozen 2026-08-30, BEFORE the dispatch that uses it.** It adds ONE capture and
changes no hypothesis, no gate and no harness file (`harness/run_b.py` already
takes `--repeats`; its sha256 is unchanged from `CAPTURE_CONTRACT.json`).

## Why

`PRE_REGISTRATION.md` §3 posed M-B1 (race) vs M-B2 (per-process state) vs M-B3
(harness artefact). The two frozen repeat captures at N = 16 refute M-B2 and
M-B3 — but they show something the three models did not anticipate and which is
*stronger* than "race": on the four live arms the payload is a **strictly
periodic function of the dispatch index**, with period 4 or 8 over sixteen
byte-identical back-to-back dispatches, and in the interleaved run the phase
advances by exactly one step per value, i.e. the phase follows the **global
dispatch counter**, not the within-value repeat counter.

Sixteen repeats can only ever show a period that divides 16, so the periodicity
claim is partly an artefact risk of N = 16 itself. This amendment makes it an
out-of-sample prediction.

## The dispatch

One capture, `g17p_e0219_B_rep_run03`, `--phase repeat --order forward
--repeats 24`, all nine arms, adjacent repeats. 24 is chosen because it is
divisible by 4 and by 8 but **not** by 16, so a "period 16" or "first-N-differ"
explanation makes a different prediction from a genuine period-4/8.

## The prediction, stated before the run

For every (arm, value) that is unstable at N = 24:

1. the repeat sequence is periodic with period **P ∈ {4, 8}** (verified by direct
   autocorrelation over the 24-long sequence, not by counting alone);
2. therefore the payload counts are exactly `24/P` times the per-period counts,
   so the count multisets must come from
   **{18/6, 21/3, 15/6/3, 12/12, 6/6/6/6}** and specifically must **sum to 24 with
   every count divisible by `24/P`** (i.e. by 6 when P = 4, by 3 when P = 8);
3. no unstable (arm, value) produces an aperiodic sequence.

**Refuter, stated before the run:** any unstable (arm, value) at N = 24 whose
sequence has no period in {4, 8} — for example counts of 13/11, or a minority
payload confined to the first few repeats (which is what a warm-up rather than a
periodicity would produce).

**Also predicted:** the arms that were stable at N = 16 (`msfilt/0`, `mscmp/0`,
`msread/2`, `mslodq/2`, `msread1/0`) stay 0/32 unstable at N = 24, and the
bit6-CLEAR control set stays 0/33 unstable on every arm.

## Budget

Inside the frozen budgets: one capture, < 60 s measured, hang budget unchanged.
