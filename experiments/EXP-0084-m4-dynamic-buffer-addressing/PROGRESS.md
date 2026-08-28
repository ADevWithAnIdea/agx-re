# EXP-0084 progress log

Append-only; one entry per milestone (mandatory per dispatch instructions).

## 2026-08-27 — pre-registration frozen

- Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`.
- Studied `EXP-0076-m4-buffer-robustness-matrix` (promoted exemplar: gates,
  two-run structure, RESULTS.md shape) and
  `EXP-0081-m4-mem-offset-semantics/QUARANTINE.md` (the four fenced
  contract-defect classes: EXP-0073 receipt-schema contradiction, EXP-0072
  payload truncation, EXP-0075 gate-order contradiction, EXP-0081
  nondeterministic-field-in-byte-compared-record) plus its lineage
  (`EXP-0072`, `EXP-0073`, `EXP-0075` QUARANTINE.md for the exact fenced
  text) and `EXP-0077`/`EXP-0078`/`EXP-0080`/`EXP-0081` for the `--seqtest`
  pattern (present in `EXP-0077`/`EXP-0080`/`EXP-0081`, absent from
  `EXP-0076` — adopted from the later lineage).
- Read `APPLE9_RE_IMPLEMENTATION_GAPS.md` MEM-15..MEM-22 (this experiment's
  assigned scope is MEM-20/21/22; MEM-15..19 are adjacent, separately
  tracked, not answered here) and `tools/agx-isa/db.json`'s
  `device_load`/`device_store`/`atomic_rmw`/`atomic_mem` descriptors
  (HW-VALIDATED: `base_slot` is an 8-bit IMMEDIATE, `index_reg` is a
  register-select field — the structural basis for H3's uniform-vs-
  divergent hypothesis).
- Read `docs/cmdstream/README.md` / `docs/descriptors/README.md` (Tier-2
  argument buffer = inline 8-byte VA per slot, DATA-TRACE evidence) and
  `EXP-0078-m4-base-slot-census` (QUARANTINED; its 31-buffer-capacity
  hypothesis is cited as unpromoted context only, independently
  re-registered here as H5/`mem22_direct_cap_31`).
- Read `tools/shdump/README.md`, `tools/agx-isa/README.md`,
  `tools/agxtest/README.md`; confirmed `tools/agxtest/agxtest.py`'s
  `--buf IDX=FILE` cannot express "a buffer holding another buffer's own
  `.gpuAddress`" (the address only exists inside the process that
  allocates the buffer), which is why `harness/splice_run.m` combines
  `agxrun.m`'s archive-forcing technique with `probe.m`'s custom buffer
  setup instead of driving `agxtest.py` directly for the splice case.
- Designed and authored: `kernels/probes.metal` (7 entry points),
  `kernels/gen_cap_kernels.py` + generated `kernels/cap_kernels.metal`
  (`cap31`/`cap32`), `harness/probe.m` (12 dispatch-kind case modes,
  compile-rejection as a first-class recorded outcome, never prints a raw
  GPU address), `harness/splice_run.m`, `harness/build.sh`,
  `casematrix.py` (14 frozen cases, one shared key set across all three
  kinds), `procutil.py` (one shared subprocess-receipt builder), `run.py`,
  `verify.py` (`--selftest`/`--seqtest`/`--preflight`/`--between-runs`/
  `--captured`), `analysis/decode_lib.py` (shared identification
  algorithm), `analysis/decode_case.py`, `analysis/splice_case.py`,
  `make_manifest.py`.
- Pre-GPU sanity: `xcrun clang` built `harness/probe.m` and
  `harness/splice_run.m` in a throwaway scratch dir (deleted); each run
  with no arguments exits 2 (`ARGS_FAIL`) before any Metal call — matches
  the `EXP-0076` "prove it links" precedent, no GPU/compiler touched.
  `kernels/gen_cap_kernels.py` was run once to produce the committed
  `kernels/cap_kernels.metal` (pure Python text generation, no compiler).
- Wrote `PRE_REGISTRATION.md` (hypotheses H1-H8 with refuters, the frozen
  14-case matrix, the frozen splice identification algorithm, the frozen
  splice case procedure, the cross-run byte-identity gate rationale, the
  four standing-gate-set classes mapped explicitly to their originating
  quarantine), `README.md`, then `CAPTURE_CONTRACT.json` (generated from
  `run.py`/`verify.py`/`casematrix.py` constants, never hand-transcribed).
- **Bug caught by `verify.py --selftest` before any GPU work** (exactly the
  point of the gate): `casematrix.py`'s decode/splice-kind case dicts
  omitted the `mode` key that dispatch-kind cases carry, so
  `MATRIX_CASE_KEYS` (derived from case 0) rejected cases 12/13 as a
  key-set mismatch — fixed by adding a frozen `"mode": None` placeholder to
  every non-dispatch case, keeping ONE shared key set across all 14 cases
  (gate (a)). Regenerated `CAPTURE_CONTRACT.json` after the fix.
- `verify.py --selftest`: **PASS 20/20**. `verify.py --seqtest`: **PASS
  7/7**. Both pre-GPU, both operate only on synthetic scratch trees (or,
  for the two PRE_GPU-state checks, the real root's actual current PRE_GPU
  state) — no device, no `shdump`, no dispatch has occurred.
- `make_manifest.py --write`/`--check`: PASS (state=PRE_GPU). Added
  `RESULTS.md`/`PROGRESS.md` pre-GPU stub content (required by the frozen
  `PRE_GPU_ARTIFACTS` list). `verify.py --preflight`: **PREFLIGHT OK.**

## 2026-08-27 — run01 captured

- `run.py --execute --run-id m4-20260827-run01`: selftest 20/20, seqtest
  7/7, preflight OK, then a clean capture: 14/14 cases recorded, 0
  watchdog/proc_fail/proc_timeout/cb_error. Status breakdown: `ok` 10,
  `compile_reject` 2 (`mem22_direct_cap_31`/`_32`, both from the SAME
  `cap32`-out-of-range diagnostic — see "Limitation" in `RESULTS.md`),
  `identification_failed` 2 (`decode_dynamic_addressing_mechanism`/
  `splice_swap_indirect_pointer` — H7's refuter fired: `l1.index_reg ==
  l2.index_reg`, but `l1.base_slot != l2.base_slot`, an honest negative
  result for the AS-STATED hypothesis, handled by the pre-registered hedge
  — no crash, no coercion).
- Wrote `analysis.py` (post-capture correctness verification; NOT part of
  the frozen `AUTH_CODE`/provenance hash set — a completeness gap against
  the EXP-0076 precedent, acknowledged in `RESULTS.md`). Ran it against
  run01: **all 10 dispatch-kind cases with an expectation match byte-for-
  byte** (`analysis/analysis_run01.json`, `all_dispatch_match: true`).

## 2026-08-27 — run02 captured, cross-run gate passed

- `verify.py --selftest`/`--seqtest`/`--between-runs`: all PASS. `run.py
  --execute --run-id m4-20260827-run02`: clean capture, 14/14 cases.
  `verify.py --selftest`/`--seqtest`/`--captured`: all PASS —
  `raw/*/04_results.jsonl` is **byte-identical in full** between run01 and
  run02 (manually re-confirmed with `diff`, in addition to the gate).
  `analysis.py` against run02: identical result to run01
  (`all_dispatch_match: true`, same per-case values).

## 2026-08-27 — supplementary exploratory splice (base_slot)

- The `identification_failed` result (H7 refuted: `base_slot` differs, not
  `index_reg`) was investigated further with a **manual, ungated,
  single-observation exploration** (not run through `run.py`/`verify.py`,
  no `raw/` record, ROOT files never touched): rebuilt `shdump` +
  `splice_run` into a scratch dir, compiled `splice_target` with
  `--no-fast-math` (needed to match `splice_run.m`'s identity-recompile
  options — the frozen `analysis/decode_lib.py`/`splice_case.py` path does
  NOT pass `--no-fast-math` to `shdump`, a **second latent bug** this
  exploration surfaced, not corrected in this already-captured
  experiment), confirmed the same `_agc.main` bytes byte-for-byte, ran the
  unmodified archive (`out`=`TAG_A`, `outb`=`TAG_B`), spliced ONE byte
  (`l1`'s `base_slot` field, absolute offset 7560, `0x03`→`0x04`), and
  re-ran: `out` flipped to `TAG_B`, `outb` unchanged — **the exact
  predicted outcome, HW-VALIDATED for this one compiled binary.** Recorded
  verbatim in `analysis/supplementary/README.json` +
  `splice_target_main.hex`; full caveats on its (non-frozen, non-promoted)
  evidentiary standing are in `RESULTS.md`'s "Supplementary exploratory
  finding" section. Recommended as a successor experiment's H1.
- Wrote the full `RESULTS.md` (OBSERVED/INTERPRETED, MEM-20/21/22 verdict
  blocks, the compiler-emitted-vs-hardware-validated separation table, the
  `mem22_direct_cap_31` confound limitation, exact tested range, remaining
  unknowns + safe driver fallback, clean-room attestation).
- Final `make_manifest.py --write && --check` and a last
  `verify.py --selftest && --seqtest && --captured` pass, all green (see
  below).

## 2026-08-27T18:20:00Z — coordinator re-orientation / address-exclusion audit confirmed

Two coordinator messages arrived describing a hypothetical interrupted-session
state (RUN02_PRESENT, `analysis.json` missing) that did not match reality:
both runs, `analysis/analysis_run01.json`/`analysis_run02.json`,
`manifest.json` (state=CAPTURED), and `RESULTS.md` were already complete
from earlier in this same session (see the three entries above). No
interruption occurred in this session; nothing was redone; `raw/
m4-20260827-run01` and `raw/m4-20260827-run02` were not touched, overwritten,
or reused.

Performed the explicit re-audit the coordinator asked for anyway, since it
is the correct and load-bearing check regardless of session continuity:
**GPU virtual addresses are excluded from the byte-compared payload by
construction, not merely by coincidence or post-hoc normalization.**
Evidence, re-verified fresh (commands and output in this session's tool
log): (1) `grep -ic gpuaddress raw/*/04_results.jsonl` → `0` in both files;
(2) a VA-shaped-hex scan (`1000[0-9a-f]{7,9}`, the pattern this repo's own
`docs/cmdstream/README.md` uses for real Apple GPU VAs, e.g.
`0x10000030000`) → zero matches in either gated file; (3) manual inspection
of sample records (dispatch case `mem20_uniform_single`: `out_hex` is 32
repeats of the compile-time TAG constant `5a000000`, never an address;
decode case `decode_dynamic_addressing_mechanism`: only small
instruction-encoding integers — `base_slot 3/4`, `index_reg 1`, byte
offsets `4/18` — deterministic given the frozen compiled binary, not
addresses; splice case fields are `null`, correctly, since
`confirmation_ok=false` stopped it before any archive/address ever entered
the picture); (4) `raw/m4-20260827-run01/04_results.jsonl` and
`raw/m4-20260827-run02/04_results.jsonl` are SHA-256 identical
(`e0a037c1e9676f491fe963e305d88595d8bcb2793be2f984a1b353f06c0646cf`, both
files) — the empirical proof: had a raw address leaked into the payload,
two independent process launches allocating fresh buffers would essentially
never produce byte-identical files. `verify.py --selftest`'s
`no_address_fields_check()` (grep-based, checks every frozen key set name
and every `harness/*.m` source line touching `gpuAddress`) passed 20/20
both before either capture and again now. **No defect found; no
`QUARANTINE.md` needed; both runs remain fully promotable evidence.**

Re-ran the complete gate sequence end-to-end as a final consistency check:
`verify.py --selftest` (20/20), `--seqtest` (7/7), `analysis.py` against
both runs (re-written, byte-identical to each other and to the prior
content), `make_manifest.py --write && --check` (state=CAPTURED),
`verify.py --captured` (CAPTURED OK). All green. `RESULTS.md` (written
earlier this session) stands as the final MEM-20/21/22 writeup; no changes
required.

**EXP-0083 cross-reference (per coordinator note):** `RESULTS.md`'s MEM-22
section already cites the base-slot-selector/31-slot context consistently
with EXP-0083/EXP-0078's non-promoted 7-bit-selector and 31-slot findings
(this experiment's OWN, independently and cleanly established 31-argument
MSL compile-time ceiling — case 9's diagnostic, reproduced identically in
both runs — corroborates that edge from the compiler side; this experiment
draws no unearned inference about the underlying architectural selector
width from EXP-0083, which remains a separate, adjacent open item).

Status: **DONE.** MEM-20/21/22 answered; two-run gate closed; no quarantine.
