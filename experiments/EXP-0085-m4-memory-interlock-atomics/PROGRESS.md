# EXP-0085 progress log

## Milestone 1 — scope and prior-evidence review
Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`. Studied
`EXP-0076` (promoted exemplar: guard-checked matrix + fail-closed
verify/selftest/smoke pattern) and `EXP-0081/QUARANTINE.md` (the four
fenced contract-defect classes this experiment is required to avoid:
receipt-schema contradiction, payload truncation, gate-order contradiction,
byte-exactness-vs-nondeterministic-field). Read `EXP-0025-scoreboard`
(A18 HW-register-interlock claim, no explicit wait op), `EXP-0018-atomics-
subgroup` (A18 atomic op-field table, SIMD pre-combine), `EXP-0051-m4-
synchronization-litmus` (M4 API-level relaxed/seq_cst exposure). Enumerated
every ATOM-* item (ATOM-01..11) and MEM-13/14 from
`APPLE9_RE_IMPLEMENTATION_GAPS.md`; decided scope: MEM-13/14 + ATOM-01..06
covered this increment, ATOM-07..11 explicitly deferred to a successor
(fence/barrier instruction family), recorded in `PRE_REGISTRATION.md`.

## Milestone 2 — harness build-time probing (pre-registration methodology)
Built `harness/atomics_probe.m` (generic 6-shape atomic-op runner) and
`harness/interlock_probe.m` / `harness/interlock_tex_probe.m`, and iterated
the kernel set against the REAL MSL compiler before freezing the matrix
(CODEX §3). Findings folded into `PRE_REGISTRATION.md`:
- `atomic_fetch_add/min/max_explicit` and `atomic_load_explicit` on
  `atomic_ulong` are all rejected; only the void `atomic_min/max_explicit`
  (no return) compile for 64-bit — sharper than EXP-0018.
- `memory_order_seq_cst` on a device atomic RMW **call** is rejected
  ("`order` argument must be `metal::memory_order_relaxed`");
  `memory_order_acq_rel` is an undeclared identifier — matches EXP-0051's
  fence-level finding, now confirmed at the RMW-call surface.
- A **literal** uniform atomic address triggers Apple's SIMD-reduce/
  lane-election optimization; an address that is merely **runtime**-uniform
  (loaded through an `idx[]` buffer whose contents happen to be all zero)
  does **not** — a new structural finding, added the `*_static0` kernel
  family to test it directly (ATOM-05/06).

## Milestone 3 — structural (tokenization) pass
Compiled the interlock and exchange-family kernels with `tools/shdump`
(read-only) and tokenized with `tools/agx-isa/agxisa.py` (read-only).
14/14 kernels tokenize CLEAN (0 leftover bytes). Confirmed on M4:
- `il_load_alu`/`il_gather`/`il_store_src`: producer instruction directly
  adjacent (0 intervening bytes) to consumer, no wait/scoreboard opcode.
- `il_atomic_alu`/`il_atomic_src`: atomic RMW is immediately followed by the
  compiler's SIMD-reduce broadcast/rebuild machinery
  (`simd_shuffle`/`iadd2`) and then the consuming ALU — still zero wait
  instructions anywhere in the chain. Observed an unexplained
  `scoreboard_fence kind=0x22` op around the lane-election machinery
  (before the atomic, not between it and its consumer) — recorded as new
  raw evidence for a successor (ATOM-09/10), not interpreted here.
- `da_add_static0`/`da_xor_static0`/`da_umin_static0` (literal uniform
  address): full `simd_reduce → elect → atomic_rmw → reconverge → broadcast`
  sequence present.
- `da_exch_static0`/`da_cmpxchg_static0` (literal uniform address): **no**
  `simd_reduce`/election sequence — straight to `atomic_mem[xchg/cmpxchg]`,
  even at a statically-provable-uniform address. Confirms the pre-combine
  is disabled for non-reducible (distinct-per-lane-result) ops
  unconditionally, not just for non-uniform addresses.
- `da_add`/`da_exch`/`da_exch_noret`/`da_store` (idx[]-buffer-driven
  address, "runtime uniform"): **no** `simd_reduce` even for `da_add` —
  confirms the runtime-vs-static-uniform boundary finding from Milestone 2.
Saved as `analysis/tokenize_evidence.txt` via `analysis/tokenize_structural.sh`
(repeatable, read-only tool use only).

## Milestone 4 — matrix freeze, contract, first capture attempt
Froze `casematrix.py` (56 cases), `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`,
`README.md`. `verify.py --selftest`/`--seqtest` both pass (10 / 11 checks).
`verify.py --preflight` PASS. Ran `run.py --execute --run-id
m4-20260827-run01` then `run02`: all 56 cases completed (55 `ok`, 1 expected
`compile_fail`), no faults, no watchdog fires, no host issues.

## Milestone 5 — analysis found 3 bugs; fixed; RECAPTURED before promotion
`analysis.py --run-a run01 --run-b run02 --write` on the first capture pair
surfaced real problems, exactly as the falsification step is supposed to:

1. **`--init` byte-order bug** (harness/run.py boundary): `casematrix.py`
   stores atomic init values as little-endian byte-hex strings (matching
   every `*_hex` field's convention). `harness/atomics_probe.m`'s `--init`
   parsing used `strtoull` (a big-endian NUMBER read) instead. This
   silently wrote the WRONG bit pattern into the target buffer for
   `da_smin`/`da_smax`/`da_exch`*/`da_store` (e.g. `da_smin`'s intended
   `INT32_MAX` init arrived as `-129`). Root-caused via the raw
   `target_final_hex` values (`7fffffff` unchanged from a corrupted init,
   proving `min` never moved) — not guessed. **Fix:** added
   `parse_le_hex()` to the harness so `--init` uses the SAME LE-byte
   convention as every other field. This changes what was written to the
   GPU buffer, so it is a **capture-affecting** fix.
2. **`case_order_sensitive_keys` field-name bug** (analysis-only):
   excluded `target_final_hex` for `tg_exch`/`tg_cmpxchg`, but those
   shapes report their final value in `tg_result_hex` (a different field);
   `target_final_hex` doesn't even exist for threadgroup-scope cases. Fixed
   to exclude `tg_result_hex` instead.
3. **Ordering-probe substring-match bug** (analysis-only): searched for
   `"order argument must be"` but the real clang diagnostic reads `` 'order'
   argument must be `` (quoted) — fixed to match on `"argument must be"` +
   `"memory_order_relaxed"`.
4. **`da_exch_noret`/`da_store` invariant bug** (analysis-only): these
   kernels deliberately set `old_out[tid] = deltas[tid]` (a placeholder,
   documented in the kernel source) since they discard the atomic's real
   return value; `analysis.py` incorrectly applied the same
   old-value/tag permutation invariant used for `da_exch`. Fixed with a
   dedicated no-return-form check (`final` is some lane's tag; `old_out`
   is exactly `deltas`, proving the return path was truly unused).

All four fixes are mechanical and objectively forced by the kernel/harness
source already on disk — none involved choosing a different expected value
after seeing GPU output. **Nothing had been promoted or cited** at the time
these were found (still inside the same pre-promotion analysis pass), so
per CODEX discipline the first (flawed, `--init`-bug-affected) `run01`/
`run02` pair was discarded rather than laundered, `verify.py --selftest`/
`--seqtest` re-run (still PASS), and the full 56-case matrix was
**recaptured from scratch** under the same run-ids from byte-identical
(post-fix) authored source (`00_inputs.json` `authored_sha256` matches
exactly between the promoted `run01` and `run02`). `CAPTURE_CONTRACT.json`
was amended with a signed note describing exactly this (see its
`amendment_2026-08-27` key) rather than silently re-frozen.

## Milestone 6 — clean recapture, full green
Recaptured `run01`/`run02` (56/56 `ok`+`compile_fail` as expected, no
faults). `analysis.py --write`: **cross-run gate PASS (0 issues)**,
**provenance gate PASS**, **56/56 per-case verdicts PASS**, **MEM-13 PASS**,
**MEM-14 PASS**, all six covered ATOM-item groups PASS.
`verify.py --captured` PASS. Proceeding to `RESULTS.md`.

## Milestone 7 — documentation finalization
Wrote `RESULTS.md`, `manifest.json`. Discovered via `git status` that
`EXP-0086` was independently claimed by a concurrent session for an
unrelated topic (`register-liveness-bits`) while this experiment was in
progress; retargeted every "recommended successor" reference in
`README.md`/`PRE_REGISTRATION.md`/`RESULTS.md` from a hard-coded `EXP-0086`
to "the next available EXP-NNNN number" (prose-only change, zero effect on
the frozen matrix, gates, hypotheses, or evidence — made after the
promoted capture runs, so `CAPTURE_CONTRACT.json`'s `authored_sha256` and
the runs' own `00_inputs.json` reflect the pre-tweak text; this is noted
here rather than re-churning the frozen-hash machinery for a wording fix).
Cleaned build-artifact clutter (`work/*.bin`, `work/shdump`, compiled
harness binaries in `harness/` and `work/*/`) before handoff — all are
regenerable from committed source via the documented build command and are
not evidence; `raw/`, `analysis/`, and the `work/*/00_inputs.json`/
`02_build.json`/`smoke_receipt.json` provenance records are untouched.

**Note for the orchestrator on raw size:** the two `raw/*/04_results.jsonl`
files are ~46 MB each (92 MB total), 15-200x larger than comparable prior
M4 experiments (EXP-0076: 220 KB/run; EXP-0081: 3.3 MB/run), because the
full per-lane arrays (`old_out_hex`, `idx`, `deltas_hex`, `tag_hex`) are
captured at their full N=65536 width for every device-scope contention
case, not just the fields each invariant check actually inspects. This is
genuine, honest, complete raw observation (nothing fabricated or
selectively excerpted) and every byte is plain JSON text (no binaries), but
it is bulkier than this repo's norm. Left as-is rather than re-capturing a
third time under a tight timeline; flagging for a decision (accept,
gzip-on-commit, or a follow-up capture with trimmed per-lane arrays for the
cases whose invariant never reads them) rather than silently shipping it.
