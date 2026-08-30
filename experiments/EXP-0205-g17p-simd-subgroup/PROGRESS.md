# EXP-0205 progress log (append-only; one entry per milestone)

## 2026-08-30 ~11:55 UTC — dirs, kernels, harness authored (PRE-FREEZE)
Created `experiments/EXP-0205-g17p-simd-subgroup/`. Pinned `db.json`, `isadb.py`,
`agxparse.py`, `shdump.m`, `agxrun_persist.m`, `persistrun.py`, `saferunner.py`
into `pinned/` so a mid-run edit to a shared tool cannot change what this
experiment measured. Authored `kernels/k_ballot.metal`, `kernels/k_reduce.metal`,
`kernels/k_shuffle.metal`.

## 2026-08-30 ~11:59 UTC — pushed + built on the neo (192.168.170.254)
`shdump` and `agxrun_persist` built from the pinned sources under
`~/agxre/EXP-0205/work/bin`. Device answers as `Apple A18 Pro`.

## 2026-08-30 ~12:02 UTC — PRE-FREEZE CALIBRATION run (raw/prefreeze/)
`analysis/calibrate.py`, 11 carriers, all `STATUS OK`, all sentinels present,
all tails still poison. Results that CHANGE the design before the freeze:

1. **MEASURED SIMD WIDTH = 32** (`threads_per_simdgroup` read back per lane;
   lane ids 0..31, one simdgroup at tg=32). Recorded, not assumed.
2. **Every carrier contains EXACTLY ONE occurrence of its target descriptor**,
   parcel-aligned, and the pinned tokenizer agrees it is that instruction. No
   occurrence-selection ambiguity anywhere.
3. **`simd_ballot.pred` is 0 on BOTH the ballot-of-predicate carrier and the
   active-mask carrier.** db.json models byte+1 high nibble as
   `0x07 = active_mask/any/all` vs `0x17 = ballot(predicate)`; our own compiler
   emits byte+1 = 0x07 for BOTH forms on G17P. What differs is byte+5
   (`psrctype`, 0x00 vs 0x02) and the byte+7..9 tail (`58 22 12` vs
   `08 02 18`). The pre-calibration oracle "pred=1 -> ballot mask" is therefore
   REFUTED before any sweep and has been replaced; the sweep now tests the
   falsifiable H1 below instead.
4. **`simd_active_threads_mask()` inside a divergent `if` returned 0xFFFFFFFF**,
   not the divergent lane mask. Either the compiler predicated the region rather
   than diverging, or the mask reports resident rather than executing lanes.
   Recorded as an open question; the frozen oracle for that carrier is the
   calibrated all-ones value with the refutation stated.
5. **`simd_shuffle.cache` already has TWO baseline values from the compiler
   itself**: byte+2 = 0x56 (cache=1) on `sh_bc`/`sh_xor` and 0x54 (cache=0) on
   `sh_reuse`, and both produce the correct broadcast.
6. `simd_shuffle.dir` model CONFIRMED at both baselines before any splice:
   `sh_bc` (0x47) gives every lane lane-5's value, `sh_xor` (0xC7) gives lane t
   lane (t^5)'s value, and both matched the host oracle exactly.
7. `simd_reduce` opcls is 1 on the three int carriers and 0 on the float
   carrier, and the db enum's pair ordering is NOT opcls order (opcls=1 gives
   `isum` and `smax`, the FIRST names of their pairs; opcls=0 gives `f32sum`,
   the SECOND name of its pair). The oracle is anchored on the measured
   baselines and a named semantic catalogue instead of on the enum text.

Consequent design change (still pre-freeze): add `sb_ballot2`, a second ballot
carrier with a different predicate mask, so that any movement under `pred` can
be attributed — a result that still tracks the predicate is ballot-like, one
that is 0xFFFFFFFF on both masks is active-mask-like.

## 2026-08-30 ~12:20 UTC — gate self-test 13/13 offline, arms frozen, contract frozen
`analysis/gate_selftest.py` passes 13/13 with **no device**: it proves the gate
can return "no" on each trap paid for elsewhere this week — a width-1 field DOES
promote (pitfall 5b), a fault is NOT movement, an arm with no detection power is
UNDERPOWERED rather than inert, inertness is still *reachable* when the control
fires, aliased encodings are refused, MALFORMED is excluded, and
moved(3) < 2*disagree(2) does not promote.

`analysis/gen_arms.py` on the neo: **35 arms, no refusals**, every arm's values
producing `distinct_encodings == len(values)` with every difference confined to
the field's own span. `CAPTURE_CONTRACT.json` frozen at repo revision
9bbc5d0b, 16 authored + 7 pinned blobs; `verify_remote.py` 22/22.

## 2026-08-30 ~12:25 UTC — pilot01 (DECLARED PILOT, retained, never gated)
77 sampled cases in 8.7 s. Three things it settled:

1. **THE IN-DIMENSION CONTROL FIRES.** On `sb_reuse`, `dst=0` left out[0..31]
   silently zero but moved out[32..63] to `0x6c8af35d + 3*v` — the ballot mask
   landed in a register the LATER read consumes. Same on `sh_reuse`. So the
   carrier demonstrably detects a change in the post-instruction content of the
   source register, which is the dimension a cache/discard operand hint is
   documented to control, and which no previous `cache` sweep had.
2. **`simd_shuffle.cache` MOVED — the field is not inert.** On `sh_bc`
   (baseline `cache=1`) and `sh_xor` (baseline `cache=1`), setting `cache=0`
   changed every lane's result to `0x00003039` = 12345. Both carriers, same
   value. Meanwhile `sh_reuse`, whose compiler-chosen baseline is `cache=0`,
   is correct at `cache=0`. Pending the gated runs, this looks like the operand
   PROVENANCE dimension EXP-0129 already found for a different field: our
   shuffle source is seeded by a `device_load`, and the prior carriers that read
   this bit INERT were not.
3. **A CONTIGUOUS HAZARD at `dst` >= 192** on both `simd_ballot.dst` and
   `simd_shuffle.dst`: 3/3 `CMDBUF_ERROR` / `ErrorHang` at dst=192, matching
   EXP-0168's `frag_color_pack.dst` wall at 0xC0. AMENDMENT 1 (recorded in
   `CAPTURE_CONTRACT.json` and `analysis/gen_arms.py`) trims the two `dst`
   CONTROL arms to 0..191. Target fields are untouched: still dense, still no
   abort path, still no hang budget.

**Courtesy note (FIELD-SWEEP-PROTOCOL section 7).** The gated runs sweep
`simd_reduce.op` and `.dtype` densely over 256 values on four carriers each, and
`simd_ballot`'s whole byte+2 over 256 values on four carriers. Those regions are
not known to be safe. Contract cases per run: 3708.

## 2026-08-30 ~12:35 UTC — REVISION A gated runs 01 + 02
3708 cases each, **zero** non-clean cases across 7630 records, 100 % cross-run
agreement on every arm, every control fired. `simd_reduce.op` and `.dtype` moved
massively and matched host predictions; `simd_shuffle.dir` matched the *other*
carrier's measured baseline vector in both directions; **`simd_shuffle.cache`
MOVED** on `sh_bc` and `sh_xor`, both to `0x00003039` = 12345, the sentinel
constant. `simd_ballot.{pred,cache}` inert.

## 2026-08-30 ~12:50 UTC — COORDINATOR STOP: RE_EXPERIMENT_PROCESS_CORRECTIONS.md
Read and applied. It overrides the dispatch's gates where they conflict. Three
of its requirements revision A does not meet, recorded honestly in
`PRE_REGISTRATION.md` → AMENDMENT 2 §B1 **before** anything was rerun:

- **Gate A NOT MET**: revision A logged the bytes it *intended* to write,
  recomputed by the same function that built the dispatched blob — exactly the
  ledger DEF-0166 defeats. No independent decode, no program hash.
- **Gate B partially met**: one readback plan on 9 of 11 carriers, and **no
  multi-invocation dimension at all**.
- **Gate C**: met for `op`/`dtype`/`dir`; **NOT met for `simd_shuffle.cache`**,
  which moved but matched no registered model — so it may not be `hardware-run`.
- **Gate E**: two runs but the same case ORDER, on a demonstrably busy machine.

## 2026-08-30 ~13:05 UTC — REVISION B authored and frozen (Amendment 2)
`kernels/k_litmus.metal`: four multi-invocation ordering-litmus carriers,
4 threadgroups × 2 simdgroups, cross-simdgroup threadgroup-memory exchange, a
cross-threadgroup device atomic read back and checked against a host total, the
operand re-read after two barriers, **three disjoint readback plans**, **pre and
post sentinels**, and **unique per-invocation codewords**, in `_ld`/`_alu` pairs
differing only in operand provenance. `run.py` gained a real Gate-A ledger
(re-read from the dispatched file, independent decode, program hash) and a
`--reverse` order mode. Calibration `calibration06_litmus`: all 16 carriers OK,
all four litmus oracles matched including the atomic total.

## 2026-08-30 ~13:20 UTC — REVISION B gated runs B01 (forward) + B02 (reversed)
5092 cases each. **5300/5300 target-arm cases ledger-verified, zero
`ledger_mismatch`.** One non-clean case in 10 184 (`sr_scan` dtype=216, seven
`InnocentVictim` classifications — sibling contamination, clean in the reversed
run; **no fault is claimed**).

**The result that mattered.** The matched litmus pair settled
`simd_shuffle.cache`: `lb_shuffle_ld` and `lb_shuffle_alu` are the same kernel
with identical `srctype` and `src` encodings, differing only in how the operand
is produced. The compiler chose `cache=1` for the device-load one and `cache=0`
for the ALU one; clearing it on the load-seeded one gave a **silent zero on
every lane and a wrong cross-threadgroup atomic total**, while the post sentinel
and the operand re-read after both barriers stayed correct. **`simd_shuffle.cache`
is LIVE and contextual — the two prior INERT verdicts were a carrier failure.**

`simd_ballot.cache` stayed inert through the multi-invocation litmus as well
(0 moved / 1536 values × 6 carriers), so the ordering dimension is now *tested*
rather than unexpressed. It is recorded as **accepted-inert in the exact tested
envelope, global role unknown** — never emitter-grade, and explicitly not
"unused": all six ballot carriers share one compiler-chosen baseline value, and
retention/occupancy has no functional observable.

## 2026-08-30 ~13:35 UTC — adversarial probe + write-up
`raw/adversarial01/` (single observations, hypothesis-grade): byte+6 `form`
alone, `0x00 → 0x14`, flips `simd_ballot` from the predicate mask to the
all-active mask; so does byte+5 + the byte+7..9 tail together. `pred` does not
participate — a `db.json` descriptor defect, recorded in
`analysis/field_verdicts.json` → `db_defects`, **not** written into `db.json`.

`README.md`, `RESULTS.md`, `manifest.json`, six-axis
`analysis/field_verdicts{,_flat,_revA,_revB}.json` and
`analysis/report_rev{A,B}.txt` written. Nothing outside this directory touched;
nothing committed.
