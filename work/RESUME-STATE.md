# Resume state — in-flight work

**Purpose:** the host is unstable and kills agents mid-run. This file is the single place a new
session (or this one after a compaction) can read to know exactly where every in-flight experiment
stands and what comes next. Update it whenever an experiment changes state.

Last updated: 2026-08-28, after commit `3efd06c6`. **The 12-agent P0/P1 wave is fully landed and
committed.** A new 10-agent **emit-everything wave** is running.

---

## In flight — 10-agent EMIT wave dispatched 2026-08-28

**Goal: make every REAL instruction emittable, not merely decodable.** Baseline at dispatch
(`tools/agx-isa/validation.json`): 1026 fields, **16.3% emitter-grade, 5 of 170 instructions
emittable**. 23 of the 170 are decode scaffolding, not real instructions; 147 are real, with 777
blocking fields. Ray tracing (8 instr / 61 fields) is **deliberately excluded** — the user scoped
P2-02 and P2-04 out.

All ten follow `experiments/FIELD-SWEEP-PROTOCOL.md`, which fixes the sweep bar, the coverage rule,
the mandatory oracle + pre-registered falsifier, and one `sweep.jsonl` record schema so their
`analysis/field_verdicts.json` files merge mechanically.

| Exp | Family | Instr | Blocking fields | Headline target |
|---|---|---|---|---|
| `EXP-0138` | FALU (float ALU) | 17 | 107 | `falu2.mod_lo` — the ONE field blocking the most-used instruction in the ISA |
| `EXP-0139` | IALU (integer ALU) | 16 | 137 | worst family; `ibfe` (16) and `ibfins` (12) are the worst two instructions |
| `EXP-0140` | MOV + CF | 23 | 51 | best yield in the wave — many are 1–2 fields from emittable |
| `EXP-0141` | MEM (load/store/atomic) | 10 | 58 | **`device_load.dst_lo`/`dst_ext9`** — the largest single synthesis blocker |
| `EXP-0142` | TEX | 7 | 46 | `tex_sample` coordinate + result registers |
| `EXP-0143` | FRAG + SIMD | 12 | 64 | `vary_slot`, the `iter` family (ties to EXP-0137's barycentric result) |
| `EXP-0144` | PACK / convert | 9 | 51 | `pack_convert`/`unpack_convert`; byte+2 newly open after the match relax |
| `EXP-0145` | bf16 / half / misc float | 15 | — | nothing in this cluster is emittable; blocks FP16/BF16 codegen entirely |
| `EXP-0146` | integer misc | 12 | — | `carry_gen` **plus answering `I64-01..06`**, the only untouched questionnaire section |
| `EXP-0147` | pipeline misc | 10 | — | `matrix_mac` is 10/12 fields done — 2 fields from emittable; `tile_read` feeds P0.4 |
| `EXP-0148` | **scaffolding + length rules** | 23 | — | modelling, not sweeping: classify the 23 pseudo-ops; derive the modifier-aware length rule for the 3 over-consumers |

**Merge procedure when they return** (orchestrator only): collect each
`analysis/field_verdicts.json`, merge into `tools/agx-isa/validation.json`, recompute the
`coverage` block **honouring `EMITTABLE VETO` notes**, then run
`python3 tools/agx-isa/validate_labels.py` (must exit 0) and
`python3 tools/agx-isa/roundtrip_test.py` (must stay 302/302). `work/merge_verdicts.py` does the
merge. Descriptor defects arrive under `"db_defects"` and are applied to `db.json` by hand, never
by the agents.


## In flight — 12-agent wave dispatched 2026-08-28

This wave covers **every** P0 and P1 row plus the three P2 rows the user approved (P2-01, P2-03,
P2-05). All are past pre-registration and into capture; a kill now costs at most one milestone
per the append+fflush / `PROGRESS.md` rule.

| Dispatched as | Directory on disk | Row | Scope | State |
|---|---|---|---|---|
| EXP-0126 | `EXP-0126-m4-uapi-field-mapping` | **P0.3** / DRV-UAPI-03 | field-by-field UAPI mapping, all 65 leaves | ✅ committed `b0a0a1b0` |
| EXP-0127 | `EXP-0127-m4-shader-selection` | **P0.2 + P0.5** / DRV-UAPI-02 | shader selection, FS selector redirect, `usc_exec_base` | ⏳ running |
| EXP-0128 | `EXP-0128-m4-generator-envelope` | **P0.6** / DRV-ISA-01 | the generator's five named cannot-generate items | ⏳ running |
| EXP-0129 | `EXP-0126-m4-lifecycle-boundary-probe` ⚠ | **Task 2** (register lifecycle) | bits 15/31, bit-17 discrimination, A18↔M4 contradiction | ⏳ running |
| EXP-0130 | `EXP-0130-m4-bg-eot-construction` | **P0.4** / DRV-UAPI-04 | *construct* BG/EOT programs (no Apple template exists) | ✅ committed `5c677b72` |
| EXP-0131 | `EXP-0131-m4-shader-container-generation` | **P0.7** / DRV-SHADER-01 | container construction, firmware-vs-archive field split | ✅ committed `ec55e03e` |
| EXP-0132 | `EXP-0132-m4-pbe-attachment-structures` | **P1.1** / DRV-PBE-01 | PBE/attachment decode + depth/stencil slot-reuse re-capture | ✅ committed `633cd06b` |
| EXP-0133 | `EXP-0133-m4-format-capability-matrix` | **P1.2** / DRV-FMT-01 | full format × capability matrix | ⏳ running |
| EXP-0134 | `EXP-0134-m4-lossless-compression` | **P2-01** | codec states, aux geometry, can-it-stay-disabled | ✅ committed `2e398db0` |
| EXP-0135 | `EXP-0135-m4-mesh-object-shading` | **P2-03** | mesh re-validation on M4 + UVB ownership | ✅ committed `661f1258` |
| EXP-0136 | `EXP-0136-m4-unreachable-encodings` | **P2-05** | Metal-unreachable encodings + capacity **promotion rule** | ⏳ running |
| EXP-0137 | `EXP-0129-m4-bary-split-abi` ⚠ | **P0.8** / DRV-ABI-01 | barycentric anomaly + prolog/epilog contract (last 2 of 9) | ⏳ running |

### ⚠ Directory-number collisions to fix at commit time (orchestrator's job, NOT the agents')

Two agents chose a directory number that does not match the number they were dispatched under.
No file conflict exists (the slugs differ), so **do not rename mid-flight** — their harnesses,
manifests, and frozen contracts embed these paths. Rename at commit, and rewrite the embedded
paths in `manifest.json` / `PRE_REGISTRATION.md` in the same commit:

- `EXP-0126-m4-lifecycle-boundary-probe` → **`EXP-0129-m4-lifecycle-boundary-probe`**
- `EXP-0129-m4-bary-split-abi` → **`EXP-0137-m4-bary-split-abi`**

Do the 0129 rename **second**, or the two will collide with each other.

---

## Completed and promoted (do not redo)

**Part-II clusters:** `EXP-0074` OPT-02 division · `EXP-0076` MEM-06..10 · `EXP-0079` format
conversion · `EXP-0082` MEM-01..05 · `EXP-0083` MEM-15..17 · `EXP-0084` MEM-20..22 bindless ·
`EXP-0085` MEM-13/14 + ATOM · `EXP-0102` INT/PACK · `EXP-0103` FP/TRIG/SFU · `EXP-0104` CF/SIMD ·
`EXP-0105` ENC · `EXP-0106` TEX · `EXP-0111` FS.

**Addendum bundles A–I:** `EXP-0091` A · `EXP-0093` B · `EXP-0092` C · `EXP-0094` D · `EXP-0095` E ·
`EXP-0100` F · `EXP-0097` G · `EXP-0098` H+I. All nine CLOSED.

**Lifecycle / synthesis chain:** `EXP-0086` liveness refutation · `EXP-0087` move synthesis ·
`EXP-0089` lifecycle model · `EXP-0090` hand-built suite · `EXP-0099` dual-model refutation ·
`EXP-0101` **load→ALU bridge solved** · `EXP-0112`+`EXP-0116` generator 140/140 · `EXP-0113`
nondeterminism · `EXP-0119` lifecycle field map.

**Row work:** `EXP-0107` scratch ceiling · `EXP-0108` BG/EOT absence · `EXP-0109` no native
prolog/epilog split · `EXP-0110` relocation/metadata · `EXP-0114` texture selector nibble ·
`EXP-0115` branch-reach checkerboard · `EXP-0117` blend epilog · `EXP-0120` TVB has no userspace
surface · `EXP-0121`/`EXP-0123` NIR contract + raster limits · `EXP-0122` 2^43 address wrap ·
`EXP-0124` query/indirect · `EXP-0125` third P0.1 negative.

---

## Resolved blockers (were open in the previous index; keep them closed)

- ~~General load-to-ALU bridging~~ — **SOLVED, EXP-0101.** The consumer route was never the
  problem: `EXP-M4-13`'s `device_load` destination formula (`dst_lo | dst_ext9<<2`) is wrong.
  The correct register is `extmode/2`; `dst_lo`/`dst_ext9` are copied verbatim. `falu2i`
  additionally needs `mods=0xC0`. Documented in `docs/isa/register-move-and-liveness.md`.
- ~~GPR-sourced `reg_move`~~ — **EXPLAINED, EXP-0087 + EXP-0101.** `reg_move` is one instruction,
  not five, and only `byte+2 = 0x01` / `op_desc = 0x08` actually moves a value; 26 other field
  values silently zero. The reproducible `0x00000100` was the silent-zero pattern, not a move.
- ~~Registers 64–95~~ — **SOLVED, EXP-0112.** Register fields alias `r(R mod 64)` for R ∈ [64,112]
  and fault at 126/127. That is why field value 67 read `r3`; there is no separate high bank.

## Open blockers (named, not hidden)

- **P0.1 / DRV-UAPI-01 helper protocol** — three independent methods have now returned negatives
  (`EXP-0107`, `EXP-0125`, and the init-time trace). Mesa's pinned UAPI says the helper is
  "internally dispatched by the hardware" out of "a static allocation shared for the whole
  device", which explains why correlation-based tracing cannot see it. Current disposition:
  **construct the protocol from first principles against the UAPI struct**, not trace it.
- **A18 ↔ M4 contradiction from EXP-0119** — unresolved; it is why `EXP-0135` is instructed to
  treat the A18-era mesh findings as *unvalidated on M4* rather than assuming transfer.

## Desk agents (no GPU; safe alongside the wave)

| Agent | Output | Purpose |
|---|---|---|
| DOC-02 labelling | `tools/agx-isa/validation.json`, `tools/agx-isa/validate_labels.py`, `work/DOC-02-LABELLING-REPORT.md` | per-field evidence label for all 170 instructions against `docs/evidence-classification.md`; yields the honest "how much can we EMIT vs merely DECODE" number |
| Gaps back-propagation | `work/GAPS-ANSWER-BLOCKS.md`, `work/GAPS-COVERAGE.md` | maps each of the 169 Part-II items to the experiment that answered it, or `UNANSWERED`; answer blocks staged for the orchestrator to splice |

## Orchestrator's own outstanding debt

- Splice `work/GAPS-ANSWER-BLOCKS.md` into `APPLE9_RE_IMPLEMENTATION_GAPS.md` once that desk
  agent reports. Bookkeeping, not evidence — the results are committed and provenanced either way.
- ~~`DOC-02` / `DOC-03` untouched~~ — **both written** (`docs/evidence-classification.md`,
  `docs/licensing-and-provenance-path.md`, commit `7fde43f0`). DOC-02's *application* to the ISA
  DB is with the labelling desk agent. `DOC-01` banners landed at `6987e19e`; the cmdstream
  open-items reconciliation at `ea1e17da`; the tiling MSAA-aux close-out at `f03b9fd1`.
- `P2-02` (tessellation) and `P2-04` (ray tracing/BVH) are deliberately **not** dispatched: the
  user approved P2-01/03/05 only.
