# Resume state — in-flight work

**Purpose:** the host is unstable and kills agents mid-run. This file is the single place a new
session (or this one after a compaction) can read to know exactly where every in-flight experiment
stands and what command comes next. Update it whenever an experiment changes state.

Last updated: 2026-08-28, after commit `75eb840a` (all 9 addendum bundles closed).

## In flight — 11-agent wave dispatched 2026-08-28 (all pre-capture as of this update)

Every one of these is in the pre-registration/authoring phase: contracts not yet frozen, no
captures, no GPU processes. If the host dies now, the loss is authoring effort only — no evidence.
On resume, each agent re-orients from its own `PROGRESS.md` and frozen contract.

| Experiment | Target | Scope |
|---|---|---|
| `EXP-0101-m4-synthesis-blockers` | **The two blockers gating all synthesis** | load→ALU bridge; GPR-sourced `reg_move`; explain the reproducible `0x00000100` |
| `EXP-0102-m4-int-pack-semantics` | Part-II INT (14) + PACK (11) | integer semantics, bitfield ops, pack/unpack conversion |
| `EXP-0103-m4-fp-transcendental-semantics` | Part-II FP (14) + TRIG (10) + SFU (7) | incl. whether rcp/rsqrt/sqrt/exp2/log2 share division's DAZ+FTZ |
| `EXP-0104-m4-controlflow-simd` | Part-II CF (6) + SIMD (7) | exec-mask/reconvergence model; subgroup/quad semantics |
| `EXP-0105-m4-encoding-registers` | Part-II ENC (16) | **owns the r64–95 addressing question EXP-0099 reopened** |
| `EXP-0106-m4-texture-isa-semantics` | Part-II TEX (28, largest) | texture instruction operand map a compiler must emit |
| `EXP-0107-m4-scratch-helper-abi` | **P0.1 / DRV-UAPI-01** | scratch BO layout, helper-program ABI, exhaustion behavior |
| `EXP-0108-m4-bg-eot-programs` | **P0.4 / DRV-UAPI-04** | BG/EOT/partial program records, tilebuffer ABI, conversion split |
| `EXP-0109-m4-stage-abi` | **P0.8 / DRV-ABI-01** | VS fetch, FS in/out, CS, prolog/epilog linkage |
| `EXP-0110-m4-command-container-packing` | **P0.5 + P0.7** | relocation transforms, link grammar, container/metadata map |
| `EXP-0111-m4-fragment-semantics` | Part-II FS (12) | interpolation/derivatives/tilebuffer contract; 2 EXP-0091 anomalies |

None is evidence until its two-run sequence closes and its gates pass.

## Completed and promoted

`EXP-0074` OPT-02 division · `EXP-0076` MEM-06..10 access model · `EXP-0079` format conversion ·
`EXP-0082` MEM-01..05 · `EXP-0083` MEM-15..17 base slots · `EXP-0084` MEM-20..22 bindless ·
`EXP-0085` MEM-13/14 + ATOM-01..06 · `EXP-0086` liveness refutation · `EXP-0087` move synthesis ·
`EXP-0089` lifecycle model · `EXP-0090` hand-built program suite · `EXP-0091` addendum A ·
`EXP-0092` addendum C · `EXP-0093` addendum B · `EXP-0094` addendum D · `EXP-0095` addendum E ·
`EXP-0097` addendum G · `EXP-0098` addendum H+I (final bundle) · `EXP-0100` addendum F · `EXP-0099` dual model refutation.

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
