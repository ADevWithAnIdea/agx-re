# Unattended run — goal, plan, and resume point

**DEADLINE: 10:00 AM PST** (set 2026-08-29, ~11h30m from the setting message). A successor
session should compute remaining time against that wall-clock and prioritise accordingly: with
under ~2 hours left, **stop dispatching new sweeps** and spend the remainder auditing, merging
verdicts, and writing the honest final accounting. An unmerged result is not progress.

**Set 2026-08-29 by the user:** *"you are unattended; your goal is to have 100% of the real
instructions emittable and have closed all the RE goals in the next 12 hours."*

This file is the single resume point. A successor session should read this first, then
`work/RESUME-STATE.md`, then `experiments/NEO-TARGET-BRIEF.md`.

## Live progress (update this as results land)

| | at start | now |
|---|---|---|
| Emittable instructions | 38 / 165 | **53 / 165** |
| Emitter-grade fields | 443 / 1036 | **552 / 1057 (52.2%)** |
| Part-II questionnaire | 145/181, 21 open | **ALL resolved** except `SFU-04` (blocked by clean-room rule 5) |
| Cross-target contradictions | 1 open (`tg_addr_compute`) | **0 open** — settled as genuinely target-driven (EXP-0156) |

**Landed on G17P:** EXP-0153 (revalidation: 7 reproduced / 0 refuted), EXP-0154 (ALU),
EXP-0156 (CF+MEM+bf16), EXP-0159 (questionnaire tail). **In flight:** EXP-0155 (TEX+FRAG),
EXP-0157 (MISC), EXP-0158 (generator synthesis), EXP-0160 (one-field-from-emittable),
EXP-0161 (carry_gen/fspecial), EXP-0162 (PACK + descriptor splices).

**Concurrency: the GPU lease was REMOVED** (protocol §7). Unrestricted parallelism; contamination
is handled by a poisoned read-back buffer, an integrity sentinel, the OS fault-class string, and
majority-of-3 on faults. The deployed `gpulease.sh` on the neo is a no-op passthrough so in-flight
callers still work.

## Baseline at start of the unattended run

| | |
|---|---|
| Emittable | **38 of 171 descriptors** (denominator is wrong — see below) |
| Emitter-grade fields | **443 / 1036 (42.8%)** |
| Remaining | 195 `untested` · 203 `tokenization-only` · 182 `corpus-correlation` · 13 `single-template-inference` |
| Test target | **A18 Pro / G17P**, `users-MacBook-Neo.local` @ `192.168.10.243` (DHCP) |
| All existing evidence | **M4/G16G** — G17P revalidation in flight (EXP-0153) |

## The honest read on "100%"

Worth stating up front so nobody later mistakes a shortfall for a failure to try. **Some fields
cannot be promoted by more sweeping**, and the reasons are already documented:

- **No dispatchable carrier** — `mem_fence8` (EXP-0141).
- **No ordering observable** — the fence fields. EXP-0141 and EXP-0147 both swept them densely and
  both *declined* to promote, because a pass proves nothing without ordering-specific litmus power.
  `compute_fence_scoped.mask` breaks reproducibly at exactly 10 of 256 values and *still* was not
  promoted. That restraint is correct and must not be traded away for a percentage.
- **Deliberate clean-room boundaries** — the compression codec bitstream (EXP-0134), `SFU-04`.
- **Descriptor defects, not sweep gaps** — `tg_addr_compute` has unmodelled live operand bytes plus
  a live G16G↔G17P divergence; `vary_store` has an unresolved opcode collision. These need the
  *model* fixed before any sweep is meaningful.
- **The denominator itself is wrong.** `rtq_pred` and `sfu_marker` have **zero fields** in
  `db.json`; EXP-0148 found **six of the 23 scaffolding entries are data words** by their own
  committed semantics. A db-defect agent is computing the corrected metric — expect the real
  denominator nearer **147** than 171.

So the target is: **every real instruction that CAN be made emittable, is** — with each exception
named, evidenced, and justified. A truthful 92% with 8 documented blockers beats a claimed 100%.

## Agent concurrency budget — 6

**User directive, 2026-08-29, revised twice from observed usage: run ~6 agents at a time.**
(First set at 8, then lowered to 6.) Above the budget the account hits usage limits, which is what
killed entire waves earlier — an agent stopped by a usage limit loses whatever it had not written
to disk, so overshooting costs more than it buys.

**Never stop running agents to get under budget** — that discards work already done. Let the count
fall naturally, then **refill toward 6, never above it**.

Practical consequence for a successor session: when several agents finish at once, resist
refilling all the slots immediately. Audit and commit the returned work first — an unaudited result
is not progress, and the merge (`work/merge_verdicts.py`) is where a wave's value actually lands.

## Standing rules for this run

1. **Concurrency is free.** Run device sweeps unlocked. GPU contexts isolate ordinary work; only a
   *hang* breaks isolation, and the driver reports it (`…ErrorInnocentVictim`), so contamination is
   always detectable. Take `~/agxre/gpulease.sh` **only** for known-hang-prone sweeps and for
   re-validation runs.
2. **Never conclude `fault` from one observation** — majority-of-3 minimum. Without this, EXP-0139
   would have shipped 692 legal field values labelled `fault`.
3. **Label `target: G17P`** for anything run on the neo. Never relabel M4 evidence as G17P.
4. **Pull `raw/` back to the repo as you go.** Nothing on the neo is evidence until committed here;
   a reboot loses it.
5. **Do not promote a field to reach a number.** Every prior agent that declined a larger claim
   (EXP-0138 declined 7 fields, EXP-0144 withdrew 44→33, EXP-0147 declined six fence fields) was
   right to, and those decisions are why the corpus is trustworthy.

## Failure modes already seen, and their fixes

| Mode | Fix |
|---|---|
| Account session limit kills all agents | Work is committed incrementally; relaunch from disk |
| Host sleep | `caffeinate -dimsu` running on the M4 |
| VPN drop kills SSH | Hard-timeout every remote call; lease self-releases, no wedge |
| WindowServer/compiler-service collapse | **Solved by the pivot** — GPU work no longer runs on the session host |
| Cross-agent GPU contamination | Fault-class recording + majority-of-3 re-runs |
