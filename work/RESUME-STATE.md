# Resume state — in-flight work

**Purpose:** the host is unstable and kills agents mid-run. This file is the single place a new
session (or this one after a compaction) can read to know exactly where every in-flight experiment
stands and what command comes next. Update it whenever an experiment changes state.

Last updated: 2026-08-28, after commit `d94b2ce8`.

## In flight

| Experiment | Bundle / items | State on disk | Next action |
|---|---|---|---|
| `EXP-0096-m4-threadgroup-addressing` | Addendum F — GLCS-A01/A02 | Contract frozen; `raw/m4-20260828-run01` COMPLETE (6090 records); run02 not started; RESULTS not final | between-runs gate → run02 under a **new** id → analysis → manifest → `--captured` → RESULTS |
| `EXP-0098-m4-gpu-driven-draws` | Addendum H+I — GLPRE-A01/A02, GLXFB-A01 | Contract frozen (pinned rev `39af7f93`); `raw/m4_20260828_run01` is an INTERRUPTED PARTIAL (7 records only) | retain the partial untouched, note it, then run both official captures under **fresh** ids |

Neither is evidence yet. Nothing in either may be cited until its two-run sequence closes and its
gates pass.

## Completed this wave (promoted, committed, provenance rows in place)

`EXP-0074` OPT-02 division · `EXP-0076` MEM-06..10 access model · `EXP-0079` format conversion ·
`EXP-0082` MEM-01..05 · `EXP-0083` MEM-15..17 base slots · `EXP-0084` MEM-20..22 bindless ·
`EXP-0085` MEM-13/14 + ATOM-01..06 · `EXP-0086` liveness refutation · `EXP-0087` move synthesis ·
`EXP-0089` lifecycle model · `EXP-0090` hand-built program suite · `EXP-0091` addendum A ·
`EXP-0092` addendum C · `EXP-0093` addendum B · `EXP-0094` addendum D · `EXP-0095` addendum E ·
`EXP-0097` addendum G · `EXP-0099` dual model refutation.

## Deferred tool changes (blocked, do not apply while agents run)

`tools/agx-isa/db.json` needs, once EXP-0096 stops decoding against it:
1. Retype the `falu2`/`falu2i` register-field top bit — **not** a 7-bit index (EXP-0099 H1) and
   **not** a retention flag (EXP-0099 H2). Correct label: 6 bits load-bearing, top bit HW-tested
   inert, role `UNKNOWN`.
2. Collapse the five `reg_move_*` descriptors into ONE instruction with an 8-bit `byte+2` field
   (EXP-0087).
3. Fix the mis-tokenized fragment kill/mask op currently read as an 8-byte vertex `vary_store`
   (EXP-0091), noting EXP-0093's correction that the `07 02 54 01` bracket is the ordinary
   fragment epilog, not a kill/mask companion.
4. Correct the `threadgroup_barrier(mem_texture)` provenance note: it is a genuine acquire
   (`sub=0x14`) / release (`sub=0x04`) pair, not `sub=0x04` for both (EXP-0093).
5. Record the `b_alu10` length-rule coverage gap: the explainer's 10-byte XOR example does not
   decode under any current family (EXP-0099).

Every one of these changes requires a full assembler/disassembler round-trip + corpus re-validation
before commit, because they alter how existing instructions decode.

## Open blockers (named, not hidden)

- **General load-to-ALU bridging** — `device_load` → `falu2` fails at all 8 consumer-route values
  while the ALU-sourced control passes at all 8 (EXP-0099 H4). Real, unexplained.
- **GPR-sourced `reg_move`** — fails for both ALU-written and `device_load`-written GPRs; returns
  an exact reproducible `0x00000100` (EXP-0099 H5).
- **Registers 64–95** — no validated addressing path in the `falu2` family once the literal-index
  model is refuted, despite EXP-0092's re-confirmed 96-GPR boundary (EXP-0099 H3).
