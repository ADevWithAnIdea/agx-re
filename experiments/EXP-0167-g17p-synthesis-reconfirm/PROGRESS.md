# PROGRESS — EXP-0167

## 2026-08-30T07:45Z — dispatch, governing docs read
Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md`, and EXP-0158's `README.md` / `RESULTS.md` /
`run.py` / `verify.py` / `harness/*`.

## 2026-08-30T07:46Z — MILESTONE: the lease does not exist
`~/agxre/gpulease.sh` on the target is a **neutralised pass-through shim** (mtime Aug 30
00:02): `shift 2; [ "$1" = "--" ] && shift; exec "$@"`. It takes no lock; no lock directory
exists on the machine. The dispatch's instruction to "take the lease" is therefore
unexecutable. **EXP-0158's own run03/run04 went through this same shim**, so those runs were
never locked either — which fits its contamination symptoms exactly. Reported to the
orchestrator, who confirmed the instruction was stale, declined a replacement lock, and
instead quiesced the other device agents by hand. Isolation is verified by measurement.

## 2026-08-30T07:50Z — MILESTONE: EXP-0158's numbers recomputed from its committed raw/
Not taken from its prose. Over its 289 cases, 265 zero-copied, **237** zero-copied and
predicted to match:
- matched in BOTH gated runs (M1 strict-pair): **96**
- `summarize.py` matched-everywhere (M2, its published strict figure): **149**
- attributable (M3): **233**; attributably wrong: exactly the 4 `IADD_SYNTH` cases
- matched in at least one gated run: 218 → **19** cases got no `ok` in either gated run
- victim retries: 328 (run03) / 636 (run04); 59 / 179 cases affected
The 19, plus `dag_040_n20` (ok / victim / fault-5-of-5), are the named watch list.

## 2026-08-30T07:52Z — MILESTONE: experiment tree built and FROZEN
`synth.py`, `generator.py`, `families.py`, `cf.py`, `casematrix.py`, `frozen_pilot.py`,
`baseline.py`, `make_manifest.py`, `verify.py`, `harness/*`, `kernels/*`,
`work/isadb_pinned/*`, `analysis/summarize.py` copied from EXP-0158 and verified
byte-identical. Only `run.py` differs, and only in its two run-id strings.
**Corpus identity proven:** both trees build 289 programs with
`sha256(concat hex) = f08d5988…59e4e87`. `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json`
frozen with the committed predictions M1 ≥ 225, M2 ≥ 229, M3 ∈ [229,237], M4 PASS, and the
pre-committed honest-lower branch (M3 < 225 ⇒ EXP-0158's 233 was contamination-inflated).

## 2026-08-30T07:51Z — sampler started on the target (pre-window baseline)
`harness/gpuwatch.py` running at 2 s into `raw/isolation/00_prewindow.jsonl`. First samples:
`n_foreign = 0`, 3 idle `MTLCompilerService` (normal on this host, not contention).

## 2026-08-30T07:56Z — MILESTONE: isolation precondition MET, tree deployed
Pre-window sampler: **126 samples over 261.8 s, `n_foreign` == 0 in every one**, max
concurrent foreign harness processes **0**, zero busy `MTLCompilerService`, load average
falling 3.99 → 1.70 as the other agents stopped. The §6 precondition is satisfied on
measurement, not on assurance.
Tree deployed to `~/agxre/EXP-0167/experiments/EXP-0167-g17p-synthesis-reconfirm/` with
`tools/` at `~/agxre/EXP-0167/tools/`; on-target hashes of `synth.py`, `casematrix.py`,
`run.py`, `work/isadb_pinned/db.json` match the frozen contract.
No-GPU gates on the target: `--selftest` 2887 checks PASS, `--seqtest` PASS (state=PRE_GPU),
`--preflight` PASS.

## 2026-08-30T07:57Z — MILESTONE: iso01 capture started
Second sampler started (`raw/isolation/01_gated.jsonl`, phase `gated`) so the whole capture
window is covered. `baseline.py` re-derived both carriers FRESH on the target:
`carrier_dag.metal` → **1590** bytes, `carrier_cf.metal` → **152** bytes, same `base_slot`
order including `carrier_cf`'s buffer(1)/buffer(2) reversal — identical to EXP-0158's and to
the M4's. Pre-capture smoke gate passed; `raw/g17p-20260830-iso01/` created.

## 2026-08-30T08:05Z — MILESTONE: sampler v1 false-positive root-caused, v2 added
`gpuwatch.py` (v1) logged **4** samples with `n_foreign == 1` during `iso01`, naming
`(agxrun)` / `(shdump)`, `etime 00:00`. Root cause verified on the target: **macOS `ps`
truncates `comm` to 16 characters** (a Python process reports `comm = "/Applications/Xc"`),
and a process whose `argv` is momentarily unreadable — the fork/exec transition — is rendered
`(agxrun)` in BOTH `comm` and `args`. v1 matched the harness regex on `comm` (which
`(agxrun)` satisfies) and then looked for the marker in `args` (which `(agxrun)` lacks), so it
filed **its own child, caught mid-`exec`**, as foreign. The same truncation is why v1's
`n_mine` was 0 throughout, including for the sampler itself.
`harness/gpuwatch2.py` added: matches the FULL `args`, resolves every candidate by **ppid
ancestry** against this experiment's own process tree, and reports an unreadable-argv process
in its own bucket rather than asserting it belongs to someone else. First v2 samples:
`n_mine` 5–6, `n_foreign` **0**, `n_unresolved_unreadable` **0**, 3 idle `MTLCompilerService`.
**v1 is left running and UNMODIFIED for the whole experiment** so both records cover the same
window and can be compared; its file is append-only and is not edited.

## 2026-08-30T08:15Z — MILESTONE: iso01 complete, and it alone reproduces the 233
289 cases, **257 matched, 285 as-predicted, `zero_copied_and_matched` = 233 in a SINGLE run**.
`outcome_counts`: ok 257, silent_zero 15, wrong_value 12, no_write 2, **fault 3**.
**Zero `InnocentVictim`, zero victim retries.** Only 3 cases needed revalidation and they are
exactly the three deliberate fault arms (`regb_R126_faultarm`, `regb_R127_faultarm`,
`adv_iadd_dst_reg96`), each 3/3 fault. **7 of 7 cascade witnesses OK.**
For contrast, EXP-0158 run03: 51 victims / 30 faults / 328 retries; run04: 70 / 44 / 636.
Raw pulled back to the repo.

## 2026-08-30T08:22Z — MILESTONE: DEF-0166-1 ledger check — CLEAN, both ways
`analysis/assemble_defect_check.py` (no GPU). Wrapped the PINNED pre-fix `assemble()`,
recorded all **204,044** calls made while building the corpus (**2,396** distinct
`(mnemonic, field-values)` pairs over 18 mnemonics), and:
1. re-assembled each with the **corrected** algorithm over the same pinned descriptors —
   **0 differences**. DEF-0166-1 altered no emitted field in this corpus.
2. the stronger test `assert_round_trip()` cannot do: **disassembled** each emitted
   instruction and compared the decoded value against the value the generator **requested** —
   **0 mismatches**. Every field carries the value the ledger says was computed.
Also measured: the 289 cases contain **277 distinct programs** — 11 `CF` cases share one
program (they vary only their input buffers) and `dag_002_n4`/`dagi_002_n4`,
`dag_003_n5`/`dagi_003_n5` coincide. Reported as a corpus qualification.

## 2026-08-30T08:30Z — MILESTONE: iso02 complete, CROSS-RUN GATE PASSES
iso02: identical dispatch summary to iso01. **`verify.py --captured` PASSES** —
`01_results.jsonl` **byte-identical** across iso01 and iso02,
sha256 `434f00b5ff8912efb21f9651829faf2976b12ed59fac09f0ad93c468de9dea73`.
The 4 unexpected mismatches are exactly EXP-0158's 4 known `IADD_SYNTH` failures, with
identical observed values in both runs (44 / poison / 22 / 120).

## 2026-08-30T08:36Z — MILESTONE: witness-gated 5-repeat pass — ZERO nondeterminism
48 cases (the 20 named watch cases ∪ every non-`ok` case) × 5 reps = **240 witness-gated
observations**. **0 MIXED outcomes. 0 discarded attempts — the witness never failed once.**
EXP-0158's equivalent pass: **102 of 174 MIXED**, and its first attempt produced 427
`ErrorHang` observations in streaks.
**All 15 fragile watch cases, and `dag_040_n20`, are `ok` 5/5.** `dag_040_n20` — `ok`/`victim`
in EXP-0158's gated pair and **`fault` 5/5** in its witness-gated pass — is `ok` 5/5 here.
Every failure is deterministic 5/5 in its own class.
Stratified top-up launched: 100 further cases × 5 reps.
