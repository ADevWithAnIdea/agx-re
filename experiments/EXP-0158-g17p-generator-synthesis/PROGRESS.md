# EXP-0158 progress log (G17P generator synthesis)

Append-only. One entry per milestone, so a kill costs at most one milestone.

## 2026-08-30T05:20Z — M0: scope read, prior art located
Read `CLAUDE.md`, `CODEX.md`, `SUBAGENT_BRIEF.md`, `NEO-TARGET-BRIEF.md`,
`FIELD-SWEEP-PROTOCOL.md`, `work/UNATTENDED-RUN.md`,
`docs/evidence-classification.md`.  Located the two direct ancestors:
`EXP-0112-m4-program-generator` (committed evidence, NOT modified) and
`EXP-0149-m4-generator-synthesis` (committed but never run — killed by
local-M4 host instability before its first capture; its `synth.py` is the
provenance-ledger design this experiment builds on).  Created
`experiments/EXP-0158-g17p-generator-synthesis/`.

## 2026-08-30T05:25Z — M1: ISA database PINNED
`tools/agx-isa/db.json` changed **under this agent mid-read**: `falu2.mod_lo`
was split into `srcA_class` (bit 40) + `srcB_class` (bits 41-42), landing
EXP-0138's operand-source-class model.  The orchestrator owns that file and
edits it while this experiment runs, so a two-run byte-identity gate cannot
depend on it.  Snapshotted `db.json` + `isadb.py` into
`work/isadb_pinned/`, verified the snapshot passes `roundtrip_test.py`
standalone, and recorded both hashes.  `synth.py` asserts at import that it
loaded the pinned copy.
  db.json  sha256 418d780ca2920a7235deb55878b4e5e82563f2370c6ce6f9fea7d05643e7c91f
  isadb.py sha256 1d60d36d2da7b681028c201013a510603d8fb7909bb59186e7534296e3b6e0d1

## 2026-08-30T05:30Z — M2: deployed to the neo, first pilot signal
Deployed to `~/agxre/experiments/EXP-0158-g17p-generator-synthesis/` on
`192.168.10.243` (G17P).  Integrity sentinel and poisoned read-back both
CONFIRMED working on the first try: a sentinel-only program leaves out[0] at
the poison word `-6.259853398707798e+18` and sets out[252] to `1.19e-43`
(bits 0x55).  Unmutated carrier returns its own value, -591.84.

**First substantive finding (pilot arm P6):** `falu2` with `srcB_class=1` and
srcB index 112 returned **-5.0** where EXP-0138's magnitude model predicts
`3.0 + 8.0 = 11.0`.  -5.0 is `3.0 - 8.0`: the MAGNITUDE is exactly EXP-0138's
but the SIGN is inverted in this shape.  `srcB_class=2` produced a real GPU
**hang**; class 3 behaved like class 1.

## 2026-08-30T05:35Z — M3: first pilot sweep destroyed by a sibling cascade
Ran arms P1-P5 unleased.  **~96 of 109 cases came back
`Discarded (victim of GPU error/recovery)`** — the neo is running ~11 other
GPU experiments and is in an error cascade.  Per FIELD-SWEEP-PROTOCOL section
7.3 the run is NOT data; retained as `work/pilot/pilot_main.jsonl` and
superseded, never overwritten.

The 13 surviving `wrong_value` rows are nevertheless decisive about the inline
immediate, because all 13 agree exactly:
    k= 2 -> 3.0 - 0.0625     k= 4 -> 3.0 - 0.125      k= 5 -> 3.0 - 0.15625
    k= 6 -> 3.0 - 0.1875     k= 7 -> 3.0 - 0.21875    k= 8 -> 3.0 - 0.25
    k= 9 -> 3.0 - 0.28125    k=12 -> 3.0 - 0.375      k=13 -> 3.0 - 0.40625
    k=14 -> 3.0 - 0.4375     k=17 -> 3.0 - 0.5625     k=18 -> 3.0 - 0.625
    k=24 -> 3.0 - 1.0        k=25 -> 3.0 - 1.125      k=33 -> 3.0 - 2.25
Every magnitude is EXACTLY EXP-0138's `m*2^-5 / (8+m)*2^(e-6)` model.  The
sign is uniformly negative.  Re-running under the GPU lease to get a clean,
complete sweep before freezing.

## 2026-08-30T05:35Z — M4: leased pilot queued
`gpulease.sh EXP-0158-pilot 900` is waiting behind EXP-0156.  Harness code
written while waiting: `synth.py` (inline-immediate codec, integrity
sentinel, PILOT provenance class), `families.py`, `casematrix.py`,
`harness/case_exec.py` (poison + sentinel + fault-class capture),
`run.py` (cascade witness + majority-of-3 revalidation pass), `verify.py`,
`baseline.py`, `analysis/freeze_from_pilot.py`.
