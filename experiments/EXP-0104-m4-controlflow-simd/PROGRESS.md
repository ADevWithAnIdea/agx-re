# PROGRESS — EXP-0104

- **M0 (pre-registration, frozen)**: PRE_REGISTRATION.md + CAPTURE_CONTRACT.json
  written; pinned revision `0f1af7fa1d3e21a9996c3b49d7d91f6377427225`; 92-case
  matrix (`harness/matrix.py`) covers all 13 items + branch-reach. Standing
  gates implemented (`harness/verify.py`): `--selftest` 103/103 PASS,
  `--seqtest` 5/5 PASS at PRE_GPU state. Pilot dispatches during design
  (ifnest_004/ifnest_128/loopnest1_064/predalias-splice/sgbar-structural/
  width-partial48/frag-quad-xor/frag-ballot) captured real M4 output, some
  promoted into `harness/fixtures.py` as RECORDED-REALITY selftest fixtures.
  Kernel redesign note: an initial `predalias` shape (nested if/else with
  inner loops, no return/break/continue) tokenized to ZERO `icmp_pred`
  instances -- fully predicated, no real branch -- so the splice target for
  CF-05/06 was moved to `ifnest_004` (proven to emit real `icmp_pred`); this
  negative finding is retained as CF-01 evidence, not discarded.

  **Self-disclosed clean-room boundary slip (remediated).** During early pilot
  compile-checks (before `work/bin` scratch conventions were fully settled in
  this session), a handful of scratch files were written to `/tmp` instead of
  this experiment's `work/` directory: `/tmp/test_{ifnest_128,loopnest1_064,
  loopnestD_012}.bin` (our own compiled Metal binary archives -- own-MSL, not
  Apple proprietary blobs) and ten `/tmp/shdump_*.log` compile-log text files.
  All thirteen files were located and deleted as soon as noticed (see
  `experiments/SUBAGENT_BRIEF.md`'s explicit "do not write to /tmp, not even
  briefly" rule, added concurrently by the orchestrator during this
  session). No raw evidence, `RESULTS.md` claim, or committed artifact in
  this experiment depends on those files -- every result they informally
  previewed was re-derived from the frozen `raw/m4_20260827_run0{1,2}.jsonl`
  captures under `harness/matrix.py`'s pre-registered cases, run entirely
  inside `work/`. Disclosed here per the brief's own guidance.

- **M1 (captures complete)**: `harness/verify.py --smoke` PASS (non-recorded,
  before any `raw/` file existed). `run01`/`run02` (92 cases each) both
  completed with 0 host wedges: 71 OK/MATCH, 0 mismatch, 4 contained
  `CMDBUF_ERROR`, 1 contained HANG (8s timeout, recovered), 16 structural/
  no-oracle cases (all `STATUS OK`) -- identical case-by-case between runs.
  `--captured` cross-run gate: 0 gated-field issues, `gputime_ns` differs in
  81/92 cases (nondeterminism-split proof CONFIRMED). `analysis/report.py`
  regenerates `analysis/summary.json` from the raw capture. `RESULTS.md`
  written with a response block per all 13 items + the branch-reach
  addendum, a finite-resource table, and an explicit Deferred section (7
  items, none silently dropped).
