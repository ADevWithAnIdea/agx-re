# EXP-0184 — PROGRESS (append-only, timestamped; written after every milestone)

## 2026-08-30 M0 — reconnaissance complete, targets chosen, snapshots pinned

- Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
  `experiments/FIELD-SWEEP-PROTOCOL.md` (§3 and §7 in full),
  `docs/evidence-classification.md`.
- **Pinned snapshots taken BEFORE any other work** (EXP-0182 owns `isadb.py`,
  EXP-0183 owns `db.json`; neither is edited here):
  - `pinned/db.json`   sha256 `1ada4e7bb7879cd607829d7e7e657c8d3e5b9b000b63c5d602adfa3f7740be04`
  - `pinned/isadb.py`  sha256 `9cda47a1d4b3857c9f20423ab5d63c38050d37220da06bc5d2dc12a77d6ef1a8`
  - repo revision at pin time: `20613a44194dc48fa95cb0563b88efabf757d09c` (6 dirty paths, none mine)
- Live worklist (`tools/agx-isa/emit_worklist.py`): **55 emittable / 166**, 22 instructions one field away.
- Neo reachable: `192.168.10.243`, macOS 26.6, Apple A18 Pro, T8140. `~/agxre` already holds
  EXP-0153…EXP-0180 working dirs; mine will be `~/agxre/EXP-0184`.

### Reconciliation against the dispatch (recorded because it CHANGED the plan)

| candidate | disposition | reason |
|---|---|---|
| `rt_query_traverse.dst` | **TIER 1** | `validation.json` says `label: untested, range: "none"` — **never swept, on any target**. Sibling fields `sel`/`opB` on the SAME instruction are `hardware-run` and load-bearing (EXP-M4-14). Exact non-zero oracle available. 4 bits = 16 values. Highest prior probability of being LIVE in the whole list. |
| `if_push.scope` | **TIER 1** | 1 carrier ever (EXP-0140), 0 moved, withheld by EXP-0164. The dimension it controls is the reconvergence **mask bank / nesting parity**, and no prior arm varied nesting depth. |
| `cvt_f2i.b9` | TIER 2 | same 1-carrier withhold; carriers must span dest/src integer type. |
| `copysign.operands` | TIER 2 | same 1-carrier withhold. EXP-0138 (M4) additionally found byte+1 is a LIVE operand field that `db.json` models as a fixed match constant — swept here as the arm's own detection-power control **and** as a G17P db-defect confirmation. |
| `iadd2.b2_fmt` | DECLINED | EXP-0171 already found it dense-inert; re-litigating costs device time for no new information. |
| `n4_cf_word.b3` | DECLINED | EXP-0172 already dispatched 256 values and reported STILL-UNDERPOWERED / `untested`. |
| `cubearray_coord_const.b3`, `mesh_out_src.sel` | DECLINED | measured 0 occurrences across 24 carriers (EXP-0148/0172). Not re-attempted. |
| `n4_rt_word.dst` | DECLINED (scope) | needs the RT carrier, which TIER 1 already consumes; deferred rather than half-done. |
| half-ALU family (`half_alu.dst`, `falu2_uni.dst`, `reg_move_cb.dst`, `half_alu_fma12.ext`, `iter_at.grp`) | NOT TOUCHED | owned by EXP-0183. |
| `ret.scoreboard`, `dev_scoreboard_fence.scope_flag` | NOT TOUCHED | declined four experiments deep, EXP-0179 on a control that fired. |

Next: author kernels + harness, then freeze `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json`
BEFORE any build or device run.

## 2026-08-30 M1 — contract frozen, harness on the neo, census done

- `CAPTURE_CONTRACT.json` frozen **before any build** (v1 retained at
  `raw/prefreeze/CAPTURE_CONTRACT.v1.json`), then re-frozen as v2 after the append-only
  pre-registration amendment that added the pilot (`raw/prefreeze/CAPTURE_CONTRACT.v2.json`).
  The v1→v2 diff is exactly three blobs: `PRE_REGISTRATION.md` (amendment appended),
  `analysis/contract.py` (one filename added to its list) and the new `analysis/gen_pilot.py`.
  **No kernel, no harness file, no `run.py`, no `verdicts.py` changed.**
- Pushed; `harness/verify_remote.py` run as a **separate unchained step**: 21/21 blobs match.
- Built `work/bin/{shdump, agxrun_persist, agxrun_persist_as}` on the neo.
- **Census** (`raw/prefreeze/census.json`): 4 carriers emit `rt_query_traverse` with **14
  occurrences each**; 5 emit `cvt_f2i` (1 each); 2 of 5 emit `if_push` (`cf_if2` 3, `cf_if3` 7);
  2 of 5 emit `copysign` (`cs_load`, `cs_chain`). The three `copysign` and three `if_push`
  carriers that emit nothing are **measured negatives**, recorded, not repaired.

## 2026-08-30 M2 — calibration pilot (raw/prefreeze/pilot01, NO VERDICT CITES IT)

417 cases, 8.6 s, zero hangs, one fault. It changed the gated arm plan in two ways.

- **`rt_query_traverse.dst` looks LIVE, and only 2 of 14 occurrences are reachable.** The `opB`
  reachability control fires at occurrences #0, #6, #7 and nowhere else — reproducing EXP-0157's
  finding that most rtq ops in a ray-query program are never executed, and EXP-M4-14's "only the
  committed-path op is load-bearing". Had the arms been frozen blind at four of fourteen
  occurrences, the sweep would very likely have reported a confident, meaningless INERT.
  **This is exactly why the pilot exists.** Gated arms therefore cover **all 14 occurrences × all
  4 carriers**.
- **`copysign.operands` moved 6 of 8 sampled values** on `cs_load` — which CONTRADICTS EXP-0138's
  M4 result that all 256 values return the same result. Gated densely on both carriers.
- `if_push.scope` moved 0/18 (including 0x54 and 0x56 explicitly) at three occurrences spanning
  nesting depth, with the `scope_kind` control firing 5–6 of 7. `cvt_f2i.b9` moved 0/8 with the
  `dst` control firing 15/16. Both go to the dense gated sweep.
- **Hang density on the control-flow sweep: 0 of 54 dispatches.** The gated run has no abort path
  (protocol 3c); this is the courtesy note that a control-flow sweep is about to run.

## 2026-08-30 M3 — two gated runs complete, verdicts computed

- `raw/g17p_20260830_run01` (67.4 s) and `raw/g17p_20260830_run02` (69.1 s), **7176 cases each**,
  7516 raw lines each, byte-identical arm list (`arms_sha256 128087d8…`), pinned db/isadb hashes
  recorded in each run's `env.json`. `concurrent_gpu_procs` was **empty in both** — the machine
  being quiet is a measurement here, not a claim.
- **0 hangs, 0 watchdog timeouts, 0 malformed responses, 0 invalid runs, 0 `InnocentVictim`.**
  90 contained command-buffer faults, all inside *control* arms. The false-hang cascade the
  leak-free runner exists to prevent never had an opportunity to start, which is worth saying
  plainly rather than claiming the runner fixed something.
- **Per-value cross-run agreement: 100.000 % on every one of the 147 arms; 0 disagreements.**
- **LIVE (→ `hardware-run`): `rt_query_traverse.dst`, `copysign.operands`.**
  **INERT-ROBUST (→ `single-template-inference`, NOT promoted): `if_push.scope`, `cvt_f2i.b9`.**
- Read-only emittability simulation (`work/emitcheck/emittability_delta.json`; `validation.json`
  is **not** edited here): **60 → 62 emittable, `copysign` and `rt_query_traverse` newly emittable.**
- Three `db_defects` recorded in `analysis/field_verdicts.json`, none applied to `db.json`.

## 2026-08-30 M4 — artifacts complete; one self-inflicted defect found and fixed

- `RESULTS.md`, `manifest.json`, `analysis/{field_verdicts,partitions}.json` written; the whole
  analysis chain re-run from `raw/` after the last code edit, so nothing is carried over.
- Removed the regenerable compiled carrier archives that `sync.sh pullwork` had dragged back
  (`work/census/*.bin`): no binary archive belongs in this tree. Nothing else in `work/` is binary.
- Password scan: **CORRECTED 2026-08-30 — this line was BOTH WRONG AND ITSELF A LEAK.** It asserted the credential "appears in no file" while writing the credential verbatim. The literal password was in fact committed in 5 tracked files; all were cleaned on 2026-08-30 to use `sshpass -e` with the `SSHPASS` env var. **It remains in git history — rotating the device password is the only real remediation.**
  `SSHPASS=` in usage text.
- **A defect in my own artifact, found at the last check and fixed:** `analysis/contract.py` read
  live `git HEAD` on every re-freeze, so `CAPTURE_CONTRACT.v7` recorded
  `repo_revision_at_pre_registration = 62faa47e` — the commit in which **EXP-0183** landed —
  because the orchestrator commits continuously and swept this in-progress directory into three
  sibling commits while the runs were going. That is precisely the failure SUBAGENT_BRIEF names
  ("pin the revision at pre-registration; do not gate on live HEAD", which cost EXP-0082 a run).
  The pre-registration revision is now carried forward verbatim from the retained
  `CAPTURE_CONTRACT.v1.json` (`8b857847`, 9 dirty paths) and the live HEAD is recorded separately
  as `repo_revision_at_last_freeze`. v1..v8 are all retained under `raw/prefreeze/`.
- **Not committed** (the orchestrator owns that). No edit to `db.json`, `isadb.py`,
  `validation.json`, `docs/`, `PROVENANCE.md`, `CLAUDE.md`, `CODEX.md`, or the neo's shared
  `~/agxre/tools/`. `macvdmtool` never run. The neo answered every request; no wedge, no reboot.
