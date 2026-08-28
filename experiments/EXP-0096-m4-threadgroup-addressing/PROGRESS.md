# EXP-0096 progress log

All timestamps local (US, host clock), append-only, newest entry last.

## 2026-08-28T00:00 (approx) -- authoring stage started
Read CLAUDE.md, CODEX.md, experiments/SUBAGENT_BRIEF.md,
work/ADDENDUM-TRIAGE-20260828.md (Bundle F), APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md
(GLCS-A01/GLCS-A02 exact wording), docs/isa/register-move-and-liveness.md
(silent-zero pattern), EXP-0082-m4-mem-offset-semantics (full methodology:
README/PRE_REGISTRATION/casematrix.py/baseline.py/run.py/verify.py/analysis.py/
make_manifest.py), EXP-0024-usc-ppp-config RESULTS.md (threadgroup-memory-size
BO field `(bytes<<2)|0x80`, static+dynamic tested 256..32768B individually, NOT
combined -- the exact gap GLCS-A02 names), docs/pipeline/README.md.

tools/agx-isa/db.json's `tg_addr_compute` entry inspected: only b3/b4/b5 are
real "mod" fields; byte0 (whole byte, match-pinned 0x1c) and byte+1
(match-pinned 0x02) are described in prose as LIVE dst/operand selectors that
the assembler's field mechanism cannot vary -- first-class tooling-gap finding
per the dispatch's own instruction.

Built read-only tools/shdump and tools/agxtest binaries in scratch (not
committed). Authoring-stage (compile-only, no GPU dispatch) design iteration:
tried 4 draft kernel shapes before landing the final 3 (kernels/tga.metal,
kernels/tg_ld.metal, kernels/tg_st.metal); confirmed by direct disassembly
with tools/agx-isa/isadb.py that:
  * tg_addr_compute is emitted ONLY by the compile-time-constant-offset
    masked-index shape (matches prior A18 evidence, own-MSL k_thr.metal /
    EXP-M4-14) -- three independent attempts to make its offset
    idxbuf/device-sourced instead of compile-time-constant all failed to
    emit it. Negative result, recorded for PRE_REGISTRATION.md.
  * kernels/tg_ld.metal / tg_st.metal each contain exactly ONE
    threadgroup-space device_load / device_store reachable by a clean
    structural locator (unique threadgroup-space load; unique
    threadgroup-space store occurring after the first threadgroup_barrier),
    confirmed by isadb.assemble round trip on the located probe bytes.
  * Ran the SAME two authorized-pre-capture-style checks EXP-0082 used (never
    promoted, compile+dispatch shape checks only, in scratch, not `raw/`):
    unspliced tg_ld.metal baseline dispatch matched the hand-computed
    expectation exactly (tile[64]=a[64]=0x3CA50040); one scratch idx_off=1
    splice via isadb.assemble moved the read to element 65 exactly (H-ELEM
    confirmed); unspliced tga.metal baseline dispatch matched the known A18
    formula o[i]=2i+3 (wrap 255,1) EXACTLY on this M4 host; one scratch
    byte0-hi splice (0x1c->0x2c) reproduced the known A18 corruption pattern
    o[i]=(i+2)&255 EXACTLY. All four checks used ONLY our own compiled shader
    bytes through tools/shdump + tools/agxtest; no Apple binary was
    introspected.

Wrote casematrix.py (frozen matrix, 2900 cases across 3 kernels/15 families;
TGA tg_addr_compute decode + TGLS-LD/TGLS-ST threadgroup device_load/store
decode) and kernels/tga.metal, kernels/tg_ld.metal, kernels/tg_st.metal.

## Coordinator steering message received mid-authoring (before PRE_REGISTRATION freeze)
Relaunch/continuity notice: prior session ended on a host/terminal problem
(not a self-inflicted stop); this directory had only the scaffolding above
(casematrix.py + kernels; no PRE_REGISTRATION.md, no CAPTURE_CONTRACT.json, no
raw/ captures) -- nothing was lost, resuming from this file per policy.

New required input BEFORE freezing the contract: apple9_isa_explainer.md
(repo root) and work/COMPILER-EXPLAINER-INTERACTION-20260828.md. Read both in
full. Summary of what changes for THIS experiment:
  * A CONFIRMED bug exists in tools/agx-isa/db.json's falu2 (6-byte compact
    float) field layout: the nominal top bit of the 7-bit srcA_reg/srcB_reg
    fields (bit15/bit31) is actually a per-source RETENTION flag, not part of
    the register index -- decoding the same instruction with only retention
    state changed produces "register numbers" 64 apart under our old layout.
  * This is a DIFFERENT instruction family from tg_addr_compute (no direct
    bit-position transfer), but the METHODOLOGICAL lesson is directly
    relevant: do not assume a db.json field described as an "N-bit
    register/operand selector" is a clean linear index without a
    downstream-consumer-read check. EXP-0099 is settling the general
    question on hardware in parallel; this experiment cross-references it,
    does not duplicate it, and does not import its unverified specifics.
  * Action taken: added an explicit caution + tga_dstreg_bit3_pairs() helper
    to casematrix.py (pairs hi/hi|0x8 for the TGA-DSTREG byte0-hi sweep) so
    analysis.py can test retention-vs-index discrimination on the ALREADY-
    PLANNED 16-value byte0-hi sweep and the 256-value byte+1 sweep, without
    adding new GPU cases and without asserting a width claim the data cannot
    support. This will be carried into PRE_REGISTRATION.md's hypotheses and
    into RESULTS.md's interpretation section explicitly.
  * No change to the matrix's case count/shape was needed elsewhere: the
    dense/exhaustive sweeps already planned (byte0-hi full 16, byte+1 full
    256, TGLS-LD-01 elem_size full 256, TGLS-LD-03 dense 0..2047) already
    constitute the "verify by downstream consumer readback" discipline the
    steering message asks for, because every case's OBSERVATION is the full
    downstream array (tga: 256-value o[]; tg_ld/tg_st: the decoded
    tile-read/tile-write location), never the spliced instruction's own
    "result" in isolation.

Continuing to baseline.py / run.py / verify.py / analysis.py /
make_manifest.py / harness/build.sh / PRE_REGISTRATION.md /
CAPTURE_CONTRACT.json / README.md.

## Harness build-out complete; gates green (pre-capture)
Wrote baseline.py (locates + freezes anchors for all 3 kernels via structural
rules: unique tg_addr_compute; unique threadgroup-space device_load; unique
threadgroup-space device_store after the first barrier -- all confirmed by
isadb round trip on this M4 host), run.py (dual splice mechanism: raw byte
patch for tga byte0/byte1/byte2 which the DB's match clause pins, isadb.assemble
for tga b3/b4/b5 and all tg_ld/tg_st fields; a SEPARATE non-splicing BUDGET
family via harness/tgbudget.m), verify.py, analysis.py, make_manifest.py,
harness/build.sh, harness/tgbudget.m, PRE_REGISTRATION.md, README.md,
RESULTS.md (placeholder), CAPTURE_CONTRACT.json (generated programmatically
from the frozen schema constants, never hand-typed).

Two real bugs found and fixed while freezing the matrix (both pre-capture,
both now fixed, both recorded in PRE_REGISTRATION.md as authoring-stage
findings):
1. `tools/agx-isa`'s `idx_off` field is width-checked at 11 bits by
   `isadb.assemble` (raises `ValueError` above 2047) -- the TGLS-LD-03/
   TGLS-ST-03 "beyond the dense sweep" cases originally tried to construct
   idx_off=2048+ through the normal field mechanism and crashed `run.py`'s
   internal splice builder at IMPORT-TIME sanity (caught before any capture
   via `verify.py --selftest`, never during a real run). Fixed by adding
   `idx_off_wide_raw` (a direct raw-byte-patch mechanism, `run.py::
   raw_write_idx_off_wide`) for exactly those cases, documented as
   necessarily also overwriting the adjacent tail field (ldform_hi11 /
   st_desc_hi).
2. `tgbudget.m` v1's canary kernel touched only compile-time-constant array
   indices; LLVM's SROA proved those were the array's only live elements and
   discarded the rest of the allocation, and a linear per-byte fill pattern
   was independently blind to a real periodicity/aliasing effect at exactly
   65536 bytes. v2 (committed) uses a runtime-thread-id-strided fill/verify
   loop and a bit-mixing multiplicative hash; recalibrated with v2 before
   freezing the BUDGET-* case ranges. Full account in PRE_REGISTRATION.md
   point 5-6.

Authoring-stage calibration (v2 tool, unpromoted, in scratch) located the two
real boundaries the frozen BUDGET-* ranges bracket: STATIC threadgroup memory
hard-rejects (pipeline-creation time) above 32768 B; DYNAMIC and COMBINED
(static+dynamic in the same kernel) are NOT validated by the API at all and
silently corrupt data once the TOTAL exceeds 65536 B (64 KiB), independent of
the static/dynamic split (verified at 4 different splits).

Gates green on the real PRE_GPU tree (all commands from this directory):
`python3 -B verify.py --selftest` -> SELFTEST PASS (16 checks, 11 mutators
each correctly rejected, cross_run_timing_only_diff_passes confirmed,
timing_isolation_checks confirmed); `python3 -B verify.py --seqtest` ->
SEQTEST PASS (10 checks, full PRE_GPU/RUN01_PRESENT/RUN02_PRESENT walk);
`python3 -B make_manifest.py --check` -> OK; `python3 -B verify.py
--preflight` -> PREFLIGHT PASS. One real bug caught and fixed by seqtest
itself during development: `seqtest()`'s own synthetic-tree cleanup only
removed `selftest/seq/`, leaving an empty `selftest/` directory that then
failed the NEXT `--preflight`'s closed-root check -- fixed to remove the
whole `selftest/` tree.

Matrix frozen at **2900 splice cases + 145 budget cases** (3045 total).
Estimated runtime (informal, from interactive per-case timings during
authoring): splice cases ~0.05-0.25 s each, budget cases ~0.1-0.3 s each
(fresh Metal compile) -> low-single-digit minutes per run.

Next: `run.py --execute --run-id m4-20260828-run01`, then `--between-runs`,
then run02, then analysis + final manifest + `--captured`, then RESULTS.md.

## run01 captured cleanly; QUARANTINED before run02 (verify.py fixture bug)
`run01` (raw/m4-20260828-run01/) completed: 2900/2900 splice cases STATUS OK, 145/145
budget cases (109 OK, 36 PIPELINE_FAIL, all BUDGET-STATIC-CAP as expected), 153.6s wall
time, zero faults/hangs/timeouts. Re-running the mandatory pre-run02 `verify.py --selftest`
then failed (`FAIL manifest` inside the `clean_pregpu` synthetic fixture): a real bug in
`verify.py::_build_tree`'s `pre_gpu=True` early-return path (it never regenerates
manifest.json for the synthetic root, unlike EXP-0082's verify.py which does so
unconditionally for both branches) that only activates once the REAL tree itself moves to
CAPTURED state (i.e. after run01 -- it was invisible throughout the entire authoring stage
and both pre-run01 --selftest/--seqtest passes).

Fixing verify.py now would change its SHA-256, which run.py's own run02 gate compares
against run01's recorded `authored_code_sha256` -- an unresolvable conflict between "fix
the gate so run02 can proceed" and "never repair a hash-frozen authored file after
capture." Per the standing rule, quarantined here rather than either violated. verify.py
REVERTED to its exact run01-frozen bytes (sha256 173e0a35...); make_manifest.py --check
passes; raw/m4-20260828-run01/ untouched. Full account: QUARANTINE.md.

Successor `../EXP-0100-m4-threadgroup-addressing` created: identical kernels/matrix/
baseline/runner, verify.py fixed BEFORE any capture, fresh PRE_REGISTRATION.md +
CAPTURE_CONTRACT.json. EXP-0096's run01 cited there only as authoring-stage corroboration
(status-count summary matches expectation), never as promoted evidence.
