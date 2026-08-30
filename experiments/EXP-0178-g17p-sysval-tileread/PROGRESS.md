# EXP-0178 — PROGRESS

Append-only. One entry per milestone. Assume the session can be killed at any moment;
on resume, re-orient from this file, `CAPTURE_CONTRACT.json`, and what is actually in `raw/`.

## 2026-08-30 — M0: reading and analysis (no device, no SSH)

- Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
  `experiments/FIELD-SWEEP-PROTOCOL.md` (incl. the five rules added 2026-08-30: §3a
  co-variation, §3b round-trip-is-not-a-gate, §3c contiguous-hazard mapping pass, §7
  unlocked-sweeps/quiet-confirmation, §8 safety).
- Read the two source experiments the dispatch names:
  - **EXP-0092** (`get_sr` `srsweep`, M4, exhaustive 0x00–0xFF × 2 gated runs) — carrier
    `kernels/srprobe.metal`, grid=64/tg=64, later-read discipline via a separate `iadd2`
    and a third separate `device_store`.
  - **EXP-0147** (`tile_read`/`tile_read_mrt`, M4, 25,064 cases × 2 gated runs) — carriers
    `kernels/pipe_render.metal::f_tile`/`f_mrt`, harness `rendersweep.m` + `rsdrv.py` +
    `shdump2.m`, litmus-power probe, integrity sentinel, collateral-vs-fault classification.
- Read the blocking status in `tools/agx-isa/validation.json` (as of `generated: 2026-08-28`,
  `db_sha256 a77f8cfa…`) and `experiments/EXP-0177-p08-abi-assembly/analysis/p08_gaps.md`
  (gaps **G1** and **G6**).
- **Ran `python3 tools/agx-isa/match_overlap_report.py`** on the targets, as the dispatch
  requires. RESULT: **none** of `get_sr.*`, `tile_read.*`, `tile_read_mrt.*` appears in the
  34-field overlap list. Every field under test has its full nominal encodable range;
  none is a one-legal-value pseudo-field. Recorded in `PRE_REGISTRATION.md` §3.
- Root-caused **why EXP-0169's G17P `get_sr` arm produced `untested`**: its `k_sr` probe was
  *lifted* into a synthesized program run at **grid=1 / tg=1**
  (`harness/casematrix.py:78` states the relaxation explicitly), where essentially every
  reachable SR reads 0. `L_sr_sel` therefore could not move and the ladder failed. The fix is
  a dispatch geometry and a carrier in which distinct SRs produce distinct host-computable
  patterns — which is exactly what EXP-0092 used and what this experiment restores on G17P.

## 2026-08-30 — M1: pre-registration drafted (no device, no SSH)

- `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` written and frozen (see M2).
- `kernels/`, `harness/`, `analysis/` authored. `pinned/` populated with this experiment's
  OWN copy of `isadb.py` + `db.json`, sha256 recorded in the contract; the harness resolves
  that pair by absolute path and **exits non-zero if it is absent** (no path-search fallback).
- **Courtesy notice (FIELD-SWEEP-PROTOCOL §7):** the `tile_read.dst` / `tile_read_mrt.dst`
  arms sweep byte+3 over 0..255. EXP-0147 recorded `fault` at 0xf6–0xff on M4; on G17P the
  analogous register-ceiling crossings **hang** (EXP-0155, seven fields). Hangs are possible
  in that region. `get_sr.dst_hi` is deliberately **NOT swept** for the same reason (values
  6–7 select registers ≥96).

## Status

- **BLOCKED ON GO.** EXP-0169 is running a hang-prone `device_store.base_slot` sweep and
  must not have neighbours. No SSH, no build, no dispatch has been performed by this
  experiment. Nothing has been written outside `experiments/EXP-0178-g17p-sysval-tileread/`.

## 2026-08-30 — M2: FROZEN

- `PRE_REGISTRATION.md` and `CAPTURE_CONTRACT.json` frozen over **15 authored blobs**
  (PROGRESS.md excluded — it is the append-only log the driver writes to) plus 3 pinned
  toolchain blobs. Repo revision at freeze `12e059e5aab38258c55ce490a01e146e6fae30d9`
  (tree dirty: EXP-0169 artefacts). The cross-run gate compares authored blob hashes,
  never live HEAD.
- Offline gates all pass with **no device**:
  - `python3 harness/pinned_isa.py` → pinned pair resolves, 172 instructions,
    db `a77f8cfa163f…`.
  - `python3 analysis/covary_audit.py` → **PASS**, 45 fields checked, 0 errors
    (FIELD-SWEEP-PROTOCOL §3a).
  - `python3 harness/selftest.py` → **PASS**, G1–G8, 0 failures. G3 proves offline that
    correct ≠ zero ≠ clear in every component of every pixel for every tilebuffer carrier;
    G4 proves each sysval ladder's two selectors are host-distinguishable; G6 proves the
    promotion gate is both satisfiable and refusable.
- Design changes made on the orchestrator's GO message, before any dispatch:
  - **No per-field hang budget and no per-arm abort.** Every planned value of every field
    is dispatched regardless of outcome — rule 3(c) applied at design time, following
    EXP-0169's DSTORE arm, which mapped `device_store.index_reg` ((v & 0x60) == 0x60) and
    `extmode` (v ≥ 0xFC) exactly inside its gated run because it had no budget. Only a
    global circuit breaker at 128 hangs/run remains.
  - **Tokenization column per case** (`tok_instr`, `tok_len`, `tok_same_instr`), after
    EXP-0169 withdrew `falu2_uni.uni_mode` when its swept values turned out to decode as
    different instructions. `get_sr.sr_sel` is exactly that shape of field.
  - **New `not_written` outcome**: the compute sentinel proves the dispatch ran but the
    read-back still holds `0xDEADBEEF`. Motivated by the DSTORE finding that a
    `device_store` through an unbound slot is **silently dropped** with no fault and no
    diagnostic — absence of a fault proves nothing, so the poison is what adjudicates.

## 2026-08-30 — M3: pilots (work/pilot01..05), then HELD for EXP-0179

Pushed, built (`shdump2`, `rendersweep`, `agxrun_persist` all clean) and ran five pilots.
All retained under `work/`, none reused, **zero gated dispatches — `raw/` is still empty.**

**The compute `get_sr` carrier has full detection power on G17P.** Anchor resolved by the
pinned tokenizer at offset 0, `04 82 10 06`, 58-byte program, **zero tokenization leftover**.
Baseline `1000,1001,1002,…` = `simd_lane_id + 1000`, matching the host oracle;
`exec_width = 32`. Ladder: `sr_sel` 0x82→0xa0 **moved**; `dst` relocation **moved** (collapses
to 1000, i.e. the consumer reads the vacated register). Litmus: `sr_sel`→0x9d
(`threadgroup_position_in_grid.y`, documented 0 in a one-threadgroup dispatch) drove **every
slot to exactly 1000** — the measurement can see an SR read collapse to zero.

**Root cause of EXP-0169's `untested` verdict, from its own committed files.** Its `k_sr` probe
was *lifted* into a synthesized program and run at **grid=1 / tg=1** —
`experiments/EXP-0169-g17p-rerecord/harness/casematrix.py:78` states the relaxation in so many
words — and at that geometry every reachable special register reads 0, so `L_sr_sel` could not
move and the ladder failed. Not the carrier program, not the oracle: the **dispatch geometry**
left the field unable to express anything. Goes in `RESULTS.md` as a named finding.

**The pre-registered falsifier is NOT a hang.** Clearing byte0 bit 2 runs clean on G17P —
`STATUS OK`, `GPUTIME_NS 5000`, sentinel written, read-back collapses to the silent-zero
pattern. Verified by hand against the runner, outside the harness. **This experiment has caused
no GPU reset at any point.**

**Harness defect found and fixed (amendment_01).** `tools/agxtest/persistrun.py` and the
`rsdrv.py` render driver start a fresh reader thread per line and abandon it on timeout; the
thread re-resolves `self.proc` at execution time, so after the first watchdog timeout it wakes
on the *replacement* child's stdout and races the foreground reader. Responses come back
truncated (`OUT 0 ` with the hex missing) and the shared parser raises. In the pilots one benign
case poisoned every later request including the unspliced health check, and three consecutive
cases were recorded `hang` with `restarts=99` — **all false**. Fixed in `harness/saferunner.py`
(one reader thread per child, tagged by owner; malformed response recorded as a **measurement
failure** with the raw lines kept, never as a hang), with an UPSTREAM NOTES block giving the
before/after for `tools/agxtest/persistrun.py` and marking both changes defaults-preserving.
The shared tools are deliberately **not** modified while EXP-0179 runs against them. Proven with
no device by new selftest gate **G9** driving `harness/fakerunner.py`.

Also added: a **harness/device health stop** (five consecutive failed full recovery cycles on
the *unspliced* carrier) — explicitly not a hang budget; hangs still stop nothing and the full
range is still dispatched.

Offline gates after the amendment: `selftest.py` **G1–G9 PASS, 0 failures**;
`covary_audit.py` **PASS**, 45 fields, 0 errors. Contract re-frozen,
sha `885d1d8605c3…`, 17 authored blobs + 3 pinned.

**STATUS: HELD.** Device released to EXP-0179 at its request; `pgrep` on the neo shows no
`agxrun_persist`, `rendersweep`, `shdump` or `run.py` from this experiment. Waiting for the
orchestrator's clear before the gated pair.

## 2026-08-30 — M4: split accepted; measurement-failure instrumentation added while held

- Orchestrator approved splitting the resume: **the three `get_sr` arms first** (~1,700 cases
  per run, the Q1 answer), the four tilebuffer arms second. Rationale recorded: `sr_sel` is
  P0.8's number-one blocker and that answer exists nowhere yet, whereas the tilebuffer arms are
  a target change on work that already exists and degrade gracefully.
- Read-only check of the neo at this point: **EXP-0179 is still running**
  (`MAPPING_g17p_20260830_run09N_hangtolerant`, forward then reverse). Still held; no dispatch.
- **Found and fixed a DEF-0178-1 defect one level along, in my own classifier.** A `MALFORMED`
  or `RUNNER_EXCEPTION` status fell through `classify()`'s `obs is None` branch and was recorded
  as **`fault`** — a measurement problem masquerading as an observation, which is the same class
  of error as scoring it a hang. New outcome **`measurement_failed`**, with the raw response
  lines kept on the record. The promotion gate now **removes** those values from the agreement
  computation (counting them as agreement would inflate the percentage; counting them as
  disagreement would penalise the field for a harness problem) and **refuses** any field whose
  measurement failures exceed 1 % of its dispatched values.
- `analysis/answers.py` now reports, per arm and per run: `measurement_failed` count and
  percentage, the per-field breakdown, a sample of the raw lines, plus `hang`, `invalid_run`,
  `not_written`, `no_draw`/`no_dispatch` and runner restarts, with a CLEAN / MEASUREMENT
  FAILURES PRESENT verdict. Recorded as `amendment_04`.
- Contract re-frozen, sha `6021c04247ff…`. `selftest.py` G1–G9 PASS. `raw/` still empty.

## 2026-08-30 — M5: remote-hash verification added, and it caught a stale neo immediately

- `SUBAGENT_BRIEF.md` gained the `&&`-chaining hazard (EXP-0179 ran a gated pass against a stale
  pre-amendment harness because `sync.sh push` failed inside a chain). I had been using exactly
  that pattern, so added `harness/verify_remote.py` — a **separate** step, never chained behind
  the push it checks, that hashes the pushed blobs on the neo against the contract's frozen
  `authored_sha256` + `pinned_inputs_sha256` and exits non-zero on the first mismatch.
- **It caught the exact failure on its first run: 11/18 blobs matched.** `analysis/answers.py`
  and `harness/fakerunner.py` were MISSING and `harness/{run,saferunner,selftest,sweepplan}.py`
  plus `analysis/verdicts.py` were STALE — every amendment since the first push had silently
  failed to reach the neo. A capture started at that moment would have run the pre-amendment
  harness. Re-pushed, re-verified as a separate step: **18/18**. Recorded as `amendment_05`
  along with the before-every-capture procedure.
- Applied EXP-0179's self-reported defect as a checklist to my own carriers (its layout omitted a
  `pop_reconverge` its own earlier arm had *measured* to be required, which would have produced
  the wrong hardware claim "depth-2 calls fault" looking perfectly clean). Two prior measured
  requirements bear on my carriers and both are honoured: EXP-0086's later-read discipline in
  every `get_sr` carrier, and EXP-0130/EXP-0117's pure-passthrough elision — 16 bytes containing
  neither opcode — which is why every tilebuffer carrier combines the read with non-foldable ALU
  against a runtime uniform rather than returning `dst`.
- Correction to my own earlier warning: **EXP-0179 was NOT on the unpatched driver.** It had
  already built `saferunner` in before dispatching its tail. My inference came from the process
  table (child PID advancing 19102 → 19123 → 19144), which cannot see which Python class wraps
  the child. The warning was wrong; raising it was not.
- Still held. Contract sha `92dc790e3232…`, G1–G9 PASS, `raw/` empty.

## 2026-08-30 — M6: run01 lost to a closure-shadowing defect; run03 (get_sr) capturing

**GO received; the hold was for EXP-0179 only. Concurrency is live** — I am on `saferunner`, so
a sibling's timeouts cannot manufacture a false-hang cascade in my stream; the residual risk is a
genuine device reset presenting as `kIOGPUCommandBufferCallbackErrorInnocentVictim`, which is
recorded per case and re-run rather than scored.

**`raw/g17p_20260830_run01` is DEFECTIVE and RETAINED** (`DEFECTIVE-run01.md`). Root cause: a
closure-shadowing defect in my own harness. The compute arm bound its read-back *size* as `nb`
and `raw_case` read it; the falsifier block later rebound `nb` to a `bytearray` in the same
enclosing scope, and a closure resolves a free variable at call time — so from the falsifier
onward every request asked for a read-back of *a bytearray* bytes and raised inside the request
builder. **It presented as a hang cascade — byte-for-byte the signature of the shared-driver
defect I had fixed minutes earlier — which is why four pilots did not separate the two.** The
tell was the exception *text* changing call site; the traceback I had added an hour before named
`saferunner.py:188` on the first run that hit it. Run id burned, never reused; the gated pair is
`run03`/`run04`.

Fixes and instruments added, each recorded as an amendment and each caught by a pilot before any
gated dispatch:

- **`amendment_06`** — the rename, plus selftest gate **G10**, which walks `run.py`'s AST and
  fails if any name a nested closure reads is assigned more than once in the enclosing scope.
  Found three further candidates (`mnem`, `off`, `runner`); all three are assigned in mutually
  exclusive branches of one `if`/`else`, carried as an explicit allow-list with that reason
  rather than weakening the check. Also: an `invalid_run` victim joins `measurement_failed` as a
  **non-observation** — excluded from the agreement computation *and* from `values_dispatched`,
  OS fault-class string kept.
- **`amendment_07`** — the compute sentinel is satisfied by **any** lane, not all lanes, and the
  per-lane counts become data. Requiring all 64 turned a real hardware phenomenon into
  `no_dispatch`.
- **`amendment_08`** — `moved` is `None` only for non-observations; a fault, hang or suppressed
  draw counts as movement. Relocating the destination GPR in the **vertex** stage suppresses the
  draw entirely, and the old rule would have failed that arm's ladder and left every `sr_vertex`
  field `untested` on a technicality.

**Three hardware results already in hand from the pilots and the first two arms of run03:**

1. **G17P reproduces EXP-0092's M4 bit-7-clear behaviour, and measures it more sharply.** For
   `sr_sel` 0x00–0x0B the read-back holds `1000 + sel` in **slot 0 only**, with **63 of 64 lanes
   still holding `0xDEADBEEF`** and **exactly 1 of 64 sentinel lanes written**. EXP-0092 ran
   against a zero-initialised buffer and could only report "the rest remain 0", recording the
   mechanism as UNKNOWN. Because the sentinel is written by a *separate* store containing no
   special-register read at all and it too lands on exactly one lane, the phenomenon is **the
   whole program retiring one lane**, not something specific to the SR read.
2. **The fragment pixel-centre offset is exactly 0.5, confirmed not fitted.** `f_sr`'s baseline
   is `pos.x = px + 0.5` and `pos.y = py + 0.5` across all 16 pixels, `affine_model_holds` true,
   `preregistered_c_confirmed` true — the pre-registered value, not one read off the data.
3. **The vertex carrier resolves the VS system values exactly as predicted.** Baseline pixels
   are a flat `7` = `baseInstance 5 + last instance 2`, with `.g`/`.b` at 0 and the uniform-only
   sentinel at `-2`, from an indexed draw with `baseVertex 9` / `baseInstance 5` /
   `instanceCount 3`.

`run03` in progress: 1,190 records, `sr_compute` complete (562 cases), `sr_frag` complete,
`sr_vertex` running. 16 `invalid_run` victims so far under live concurrency — recorded, not
scored.

## 2026-08-30 — M7: SELF-DISCLOSURE, and G10 made upstreamable

**Self-disclosure (SUBAGENT_BRIEF, absolute rule).** While composing a shell command I included a
stray `cat > /tmp/nothing 2>/dev/null` fragment, which created an **empty** file at a local path
outside the repository. It was removed in the same command; `ls /tmp/nothing` now reports
"No such file or directory". **No content was written to it** — the redirect created a zero-byte
file and the `cat` then blocked on stdin, which is what made the command time out. No experiment
data, no repo content and nothing about the target left the repository. Reporting it because the
rule is absolute and "a quick throwaway probe is exactly when it gets broken"; the correct
response is to disclose and relocate, which is what happened. Everything else in this experiment
has stayed inside `experiments/EXP-0178-g17p-sysval-tileread/`.

- `harness/closure_scan.py` extracted as a standalone, dependency-free, upstreamable module with
  its own `UPSTREAM NOTES`; selftest **G10** now calls it. Alongside `harness/saferunner.py` and
  `harness/verify_remote.py`, that is three checks written to be lifted into the shared brief.
- `analysis/answers.py` gained `vertex_software_offset`, which **measures** the compiler-inserted
  constant in the vertex carrier instead of assuming it: **7 independent selectors with no
  vertex-stage meaning (0x9c, 0x9d, 0x9e, 0xa0, 0xa1, 0xa4, 0xc5) all read exactly 5**, pinning
  K = 5 = `baseInstance`. It also emits the oracle-confound disclosure, so the vertex arm is
  reported differentially rather than as two clean `ok`s.
- `RESULTS.md` §6 written: the three apparatus defects and what each would have cost.
- run04 at 1,468 records and still capturing.

## 2026-08-30 — M8: BOTH gated pairs complete; both questions answered

- **Sysvals:** `g17p_20260830_run03` / `run04`, 1,710 records each.
  **`get_sr.sr_sel`, `.dp_width`, `.dp_marker` -> `hardware-run` (G17P), 100.00 % cross-run
  agreement on every value of every carrier, zero disagreements.**
- **Tilebuffer:** `g17p_20260830_run05` / `run06`, 9,460 records each (9,428 cases), four
  carriers, **zero measurement failures and zero victims in either run**. `tile_ct2` resolved to
  `tile_read`, giving the second structurally different carrier EXP-0164 required.
  **`read_en`, `rt_index`, `dst` on both instructions and `fmt` on `tile_read_mrt` ->
  `hardware-run` (G17P).** Every EXP-0147 M4 legal-value set transfers unchanged, and
  **`rt_index` produces 0 faults in 256 values on 4 carriers** — the hazard is confirmed as a
  silent zero, not a loud failure.
- Corrected an implementation bug in my own gate against my own frozen text: it computed
  `moved >= 2.0 * max(disagree, 1)` where `PRE_REGISTRATION` §8 and the contract both say
  `moved >= 2.0 * disagree, and > 0`. The stricter form refused **`read_en`** — a 1-bit field
  where at most one value can differ from its baseline — on an arithmetic artefact rather than on
  the evidence. Corrected to the frozen text; all `selftest.py` G6 cases still refuse for the
  reasons they name.
- `analysis/field_verdicts.json` restructured so recorded data cannot be mistaken for a label:
  top-level keys are verdicts, `_not_ruled_on` holds fields another experiment owns (labelled
  `NOT-A-VERDICT`, must not be merged), and `_referred_for_ruling` holds **`get_sr.form`** with
  its full per-carrier numbers and a stated recommendation.
- `RESULTS.md` complete (534 lines): the M4 vertex-fault comparison is stated as **REFINED, not
  refuted** — EXP-0092 measured a *compute* carrier and my compute arm reproduces it exactly, so
  the divergence is **stage, not target**.
- `manifest.json` generated.
