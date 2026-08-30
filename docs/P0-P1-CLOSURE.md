# Apple9 P0/P1 Closure Matrix

This is the live status board for closing every P0 and P1 item in
`APPLE9_RE_IMPLEMENTATION_GAPS.md` (the authoritative task list, superseding the removed
`AGX_RE_INFORMATION_GAPS.md` audit) using the local M4/G16G as the **sole test target**.

> ### ⚠ SUPERSEDED 2026-08-28 — read this before the paragraph below it
>
> **The A18 Pro / G17P is now THE test target and closure is measured against full G17P**
> (`CLAUDE.md`, user directive 2026-08-28). The 2026-08-27 hands-off directive quoted below was
> **lifted**; the local M4 is **retired from GPU testing** because local GPU work destabilized
> the host running this session. The paragraph is retained rather than deleted because the rows
> in this table were written under both regimes and each records the target it actually ran on —
> which is the point. **Committed M4/G16G evidence stays valid on its own target and is not
> retracted, but it is supporting evidence, not closure evidence, and must never be relabelled.**
>
> That distinction stopped being bureaucratic on 2026-08-30. `get_sr.sr_sel` was measured on M4
> to fault at no value anywhere in `0x00`–`0xFF`; on **G17P in a vertex shader every bit-7-clear
> selector faults, 128 of 128**. The M4 result was *correct for the stage it was measured on* —
> a compute carrier — and the G17P compute arm reproduces it exactly. **The divergence is stage,
> not target.** An experiment can be exhaustively swept, cross-run agreed, and still blind,
> which is precisely why a single-target, single-carrier claim cannot close a row.

**Historical, superseded — the 2026-08-27 regime:** the A18 Pro/G17P is hands-off (never SSH,
probe, or reboot it; `macvdmtool` is never used), and all testing runs locally on the M4, which is
Apple9-equal to the A18 Pro for every driver-emittable subsystem (`EXP-M4-*` byte-identity).
A18-specific replication is suspended, not a closure gate; every result still records its actual
M4 target and must not be relabeled as directly observed on A18.

**Priority directive (user, 2026-08-27): the load/store/SSBO gaps are the compiler critical
path and jump the queue.** Concretely: Part-II `MEM-01…MEM-22` + `ATOM-*` (element scaling,
immediate-offset units/range/signedness, stride addressing, unaligned + out-of-allocation
behavior, base-slot capacity/aliasing, dynamic 64-bit / descriptor-array addressing,
atomics) and the memory subset of DRV-ISA-01. Everything else yields device slots to this
cluster until the compiler can lower NIR buffer access end-to-end.

Row-ID mapping (this board's legacy row IDs ↔ the task list's current IDs — same sixteen
items, restated; the task list adds the P2/DOC rows and the Part-II compiler questionnaire,
which this board does not track):

| Board row | Task-list ID |
|---|---|
| P0.1 | DRV-UAPI-01 (scratch/helper protocol) |
| P0.2 | DRV-UAPI-02 (shader selection / code-BO handoff) |
| P0.3 | DRV-UAPI-03 (field-by-field UAPI mapping) |
| P0.4 | DRV-UAPI-04 (BG/EOT + partial-render programs) |
| P0.5 | DRV-CMD-01 (relocatable command/state schemas) |
| P0.6 | DRV-ISA-01 (compiler-ready ISA specification) |
| P0.7 | DRV-SHADER-01 (shader container / metadata / resource specs) |
| P0.8 | DRV-ABI-01 (stage ABI, linking, programmable epilogs) |
| P1.1 | DRV-PBE-01 |
| P1.2 | DRV-FMT-01 |
| P1.3 | DRV-TEX-01 (+ Part II `TEX-*`) |
| P1.4 | DRV-MEM-01 (+ Part II `MEM-*`/`ATOM-*`) |
| P1.5 | DRV-ROBUST-01 |
| P1.6 | DRV-QUERY-01 |
| P1.7 | DRV-INDIRECT-01 |
| P1.8 | DRV-RASTER-01 (+ Part II `FP-*`/`PACK-*`/`INT-*`/`TRIG-*`/`SFU-*`) |

## Closure rules

A row is `CLOSED` only when:

1. the required value or behavior can be generated, not merely decoded from a captured
   template;
2. the complete authored probe, commands, raw observations, failures, and analysis are
   committed under `experiments/`;
3. the evidence chain is recorded in `PROVENANCE.md`;
4. the normative docs contain the exact fields, ranges, fallbacks, and target status;
5. an adversarial reproduction or second method passes; and
6. the relevant userspace object can be independently generated and consumed without a
   captured Apple template: shader/container/metadata records, command/state streams,
   render/attachment objects, or other object type required by the row.

The pinned Mesa/Asahi UAPI is retained only as a compatibility inventory. It is
not a reconstruction target and does not gate closure: this project targets the
Apple userspace objects, ISA, command streams, and object-generation paths
needed to drive the hardware independently.

Evidence strength is defined by `CODEX.md`. Tokenization or a byte-exact round trip alone
cannot close a synthesis gap.

> [!IMPORTANT]
> **Target scope for closure — CURRENT RULE (user directive, 2026-08-28, superseding the G16G-only
> amendment made earlier the same day): these rows are measured against FULL G17P** — the A18 Pro at
> `users-MacBook-Neo.local`, now the sole test target and verified working end-to-end. Local M4 GPU
> testing is **retired**; it destabilized the machine hosting this repo.
>
> Committed G16G evidence is **NOT retracted** and stays valid on its own target, but it no longer
> satisfies a row by itself. The upside is large: G17P is the documentation target, so new evidence
> is **direct rather than `INFERRED`**, retiring a standing inference debt across the whole corpus.
>
> *(Audit trail: the superseded note read "these rows are measured against G16G — the local Apple
> M4 — only.")*

## P0 — complete-driver and unchanged-UAPI blockers

| ID | Requirement | Current status | Closure evidence required | Active experiment |
|---|---|---|---|---|
| P0.1 | Userspace scratch allocator and VS/FS/CS helper-program ABI | **OPEN** (M4 negative boundary probe) | Helper binary/cfg/data fields; helper SR inputs; scratch BO headers, block lists, buckets, topology mapping, limits and failure behavior; generated helper runs spill and preamble scratch on M4 and A18 | `EXP-0041`: 0–576 B scratch executes, but no helper/scratch record or allocation surfaced |
| P0.2 | Graphics shader selection and code-BO handoff through existing `usc_exec_base` | **OPEN** (M4 selectors partial) | EXP-0042 proves separable live VS token and FS window-relative selector across 36 draws; still need general token/tag derivation, exact `usc_exec_base` mapping, relocatable entry/extent, HW/FW-consumer proof and A18 run | `EXP-0042-graphics-code-selection` |
| P0.3 | Apple9 value for every existing render/compute UAPI field | **OPEN** (all 65 leaves chained: 7 MAPPED / 58 PARTIAL) | EXP-0126 now chains all 65 leaves (userspace derivation -> UAPI value -> firmware marshaling -> observed behaviour): 7 MAPPED, 58 PARTIAL, 0 undeterminable within the 65. `ppp_multisamplectl` is SETTLED (it IS the packed value; rounding is round-half-up, bisected at 1/32 and 3/32; no ceiling clamp -- 0.99 -> 1.0); `render.samples` is exactly {1,2,4}. The 58 PARTIALs now carry full PUBLIC bit layouts and are blocked by the ABSENCE OF A MACOS OBSERVATION POINT for firmware-marshaled registers, not by missing effort. EXP-0043 locates direct-stream termination/rollover. EXP-0054 (`6c342a06`) retains four M4 public-Metal runs: exact tested single/two-scissor coverage and bounded Depth32Float `2^-24` constant and `-0.01875` slope correlations; runs01/02 preserve the inactive magnitude-100 H4 clamp negative, while separately preregistered runs03/04 support sign-matched magnitude-100000 clamps. EXP-0055 (`83e29abe`) adds a clean exact-two-VA M4 DATA-TRACE boundary: every tested nonzero constant/slope input changes only `0x58000+0x36` `00->02` as an enable candidate, while tested scissor/multi/clamp readbacks change without a semantic pair delta in either allowed mapping and `0x68000` remains unchanged. Still need private `isp_scissor_base`/`isp_dbias_base` layout, integer mode, every other field, hardware-consumer proof, Linux mapping and A18 | `EXP-0044/0045` baseline; `EXP-0043` framing; `EXP-0054-m4-scissor-depth-bias` public behavior; `experiments/EXP-0055-m4-scissor-depth-bias-state/analysis/summary.json`; `experiments/EXP-0055-m4-scissor-depth-bias-state/analysis/report.txt`; `experiments/EXP-0055-m4-scissor-depth-bias-state/raw/m4_20260817_run01/04_boundary_preflight.json`; `experiments/EXP-0055-m4-scissor-depth-bias-state/raw/m4_20260817_run02/04_boundary_preflight.json` |
| P0.4 | BG/EOT/partial-BG/partial-EOT programs | **OPEN** (program side ADVANCED; UAPI side blocked) | EXP-0130 CONSTRUCTED and executed a real tilebuffer-read/attachment-write program on M4 (`f_eot_combine`, behaviourally exact on 4/4 boundary cases, structurally carrying both `tile_read` and `frag_color_store`), with a paired falsifier proving tile-independence; EXP-0120 separately showed TVB overflow has NO userspace surface. Still blocked: `drm_asahi_bg_eot` cannot be populated on macOS (no `/dev/dri`, P0.5 still OPEN), so `usc`/`rsrc_spec` field values remain PUBLIC-only inference from the pinned MIT header, not Apple9 facts. Also open: the `usc` low-bit tag, BG_LOAD construction as such, and the `imageblock` tile-shading route | `EXP-0130-m4-bg-eot-construction`, `EXP-0120`, `EXP-0117`, `EXP-0048-bg-eot-pbe` |
| P0.5 | Complete relocatable VDM/CDM/PPP/USC command and state packing | **OPEN** (M4 exact-shape rollover partial) | EXP-0043 locates the tested direct CDM/VDM terminals and first rollover boundaries. EXP-0049 (`84779ec8`) repeats the exact 732/733 CDM and 328/329 VDM pairs and preserves tested bytes under encoder/padding controls, but alternate indirect/stable/pass-per-draw shapes stop without the known pair. Still need hardware-consumer proof, link mutation, general capacity/relocation, barriers/calls/indirect, complete PPP/USC schemas, independent packer, Linux mapping and A18 | `EXP-0043-command-stream-framing`; `EXP-0049-command-link-structure` + mutation/packer follow-up |
| P0.6 | Compiler-ready ISA and opcode property model | **OPEN** (emitter-grade **544/1040 fields = 52.3%**; **32 of 166 emitter-relevant instructions emittable**; 24 are ONE field away) | **Measured directly by the G17P emit wave; closure is measured against full G17P.** `tools/agx-isa/validation.json` labels every field by the evidence backing it (`docs/evidence-classification.md`): **544/1040 emitter-grade, 32 of 166 emitter-relevant instructions emittable**. `docs/isa/emit-worklist.md` (regenerate: `python3 tools/agx-isa/emit_worklist.py`) ranks what blocks the remaining 134 closest-first - **24 are ONE field away, 18 are two**, and the instruction-level label `_instruction` alone blocks 79 descriptors, `dst` 38, `srcA` 14, `tail` 13. **THE NUMBER WENT DOWN EIGHT TIMES ON 2026-08-30 AND EVERY WITHDRAWAL WAS CORRECT** — the arc is 79 → 41 → 55 → 38 → 37 → 34 → 33 → 32, and each fall came from an audit that reproduced the published figure before disputing it. Do not hand-edit this cell: `python3 tools/agx-isa/check_doc_numbers.py` fails the build if it goes stale again. EXP-0164 re-derived every emitter-grade field from committed `raw/` (728,387 records, 53 experiments) and found the headline inflated; 81 INERT-SINGLE and 41 UNSTABLE fields were downgraded. EXP-0163 then confirmed the driving hypothesis on hardware - a user challenge that encoding space is too expensive for Apple to waste - with a controlled experiment: `k_cent.metal` built twice differing ONLY in `rasterSampleCount` shows **`iter_at.loc` is 0/256 at 1 sample and 128/256 at 4**, because at one sample centroid and sample are the same point. Of 20 corpus-declared-inert fields, **7 are LIVE**. **This refuted the orchestrator's own >=2-carrier rule, which is now: two carriers identical in the dimension the field controls are ONE carrier.** A further label overrule (proven-inert-but-unknown-role is `single-template-inference`, not emitter-grade, because emitter-grade asserts the implementer may CHOOSE the value) cost 4 more instructions. **EXP-0170 then audited the audit** and confirmed it: of 266 withheld rows **253 AGREE**, and not one of the 144 UNVERIFIABLE or 81 INERT-SINGLE rows moves a bucket. It corrected two published figures (`cvt_f2i.dst` is 98.14%, not 99.56%; `cvt_f2h.op` unaffected) and restored 2 fields withdrawn on a pairing against a run the source experiment disowns. **FOUR TOOLING DEFECTS FOUND AND FIXED, each silently inflating confidence:** (1) `isadb.assemble()` OR-ed `match` then fields, so any overlapping bit was **stuck at 1** - 59 fields overlap and **25 have ZERO free bits**, i.e. one legal value, so they are part of the match rather than fields (16 carry a vacuous emitter-grade label); `assemble()` now REFUSES the conflict (DEF-0166-1, DEF-0170-1). (2) **`roundtrip_test.py` is NOT an emitter gate** - proved by re-implementing the broken assembler and re-running the suite: 173 cases, 0 failures. 28 files define the same symmetric `assert_round_trip`; `rt_ok` means only that our tokenizer agrees with itself. (3) **The observable must not co-vary with the field under test** - EXP-0140 swept `uniform_mov.dst` with a read-back of `device_store(data_reg=D)` where D *was* the swept dst, so zero-moved was the PASSING outcome of a test that could return nothing else. (4) **Coverage was unenforceable** - `range` is free prose, 358 of 617 rows unparseable, and no gate had a coverage term, so a field could pass on two dispatched values; `values_dispatched` / `distinct_bytes` / `encodable_range` now flow through and the validator reports THIN and UNDER-COVERED. **Descriptor defects remain first-order**, all silent-wrong-register: `fspecial`'s operands SWAPPED, `imad` with NO `srcA` modelled, `cvt_bf16.src` fully match-pinned so it cannot be the source it names, and `op04_len8`'s declared length refuted on hardware (12 bytes, not 8 - carries an EMITTABLE VETO). **The countervailing positive is strong: EXP-0167 re-confirmed under MEASURED isolation that 233 of 237 generated programs containing ZERO copied fields produce their exact host oracle on G17P** - `verify.py --captured` PASSES, results byte-identical across runs, 740 witness observations with 0 MIXED (against 102 of 174 contended), and a ledger check over 204,044 `assemble()` calls with 0 mismatches. That is closure rules 1 and 6 met directly. Un-sweepable and named: `mem_fence8`, the fence fields (no ordering observable - four experiments have declined them), the compression codec and SFU-04 (clean-room), `rtq_pred`/`rtq_dualsrc` (UNREACHED, proved by a 256-byte erase leaving the oracle correct). | `EXP-0046` synthesis audit; `experiments/EXP-0060-isa-falu2i-bound-vectors/{RESULTS.md,raw/run01/result.json}` |
| P0.7 | Shader container, extent, metadata and resource-spec generation | **OPEN** (HW-consumer proof OBTAINED; synthesis + selection still open) | EXP-0131 supplies the missing HW-consumer proof: a one-byte edit to the LIVE post-creation code BO flips the rendered pixel (`4080ffff`->`4040ffff`), with the adjacent-byte control unchanged. Own-record `record_size` is NOT re-consulted at code-fetch time (0x0 and 0xFFFFFFFF both render clean) but IS read by macOS userspace at teardown; EXP-0042's "opaque following record" is reclassified as the next record's own header. Still need: a from-scratch instruction sequence rather than a field edit, the live selector mechanism (EXP-0127), `constant_program` mutation, resource-bearing variants, A18 replication | `EXP-0131-m4-shader-container-generation`, `EXP-0042-graphics-code-selection` |
| P0.8 | Complete VS/FS/CS ABI and programmable prolog/epilog linkage | **OPEN** (12 of 28 stage-ABI instructions emittable = 42.9%; **only 5 clear both the field and instruction bars, and none is an input/output/sysval/interpolation/tilebuffer op**) | **NOT 'queued' — assembled by EXP-0177, and the honest reading is worse than a padded survey would give.** **Computed, not asserted** (`analysis/isa_status.py`, from `validation.json`): of the **28 instructions a VS/FS/CS stage ABI and prolog/epilog linkage must emit, 12 are emittable (42.9%)** — but **seven of those twelve carry an `_instruction` label weaker than emitter-grade**, and EXP-0173 proved the emittability rule never reads that label. **Only FIVE of 28 clear both bars: `frame_prologue`, `link_save_restore`, `pixel_order`, `pop_reconverge`, `spill_frame_marker` — and NOT ONE is an input, output, sysval, interpolation or tilebuffer instruction.** All five are frame/ordering plumbing, and two are compromised in their own right (`spill_frame_marker`'s role is UNRESOLVED, with EXP-0041 finding its byte pattern absent from every proven-spilling main; `link_save_restore` carries three zero-free-bit pseudo-fields per DEF-0170-1). In one line: **the semantics are largely known, almost entirely on the wrong target, and mostly not emittable.** **WHY THIS CELL SAID 'queued' — a structural finding, not an oversight: the two experiments named for this row are BOTH QUARANTINED.** `EXP-0050-fragment-output-abi` carries a false clean-room attestation (its own text reads 'ALL VERDICTS BELOW ARE NON-EVIDENCE') and `EXP-0071-m4-vertex-fragment-abi-contract` is pre-GPU with no capture ever run; `EXP-0118` claims a G17P result with no gate, no `raw/` and no target line. **Anyone searching the tree for P0.8 evidence hits three dead ends first.** Compounding it, **the two largest P0.8 experiments are outside the paper trail** — EXP-0109 (57x2) and EXP-0117 (148x2) have no `PROVENANCE.md` row of their own, appearing only inside other experiments' rows. **RANKED BLOCKERS** (`analysis/p08_gaps.md`, 19 gaps naming instruction and field): (1) **`get_sr.sr_sel` is `untested` on G17P on one carrier, so NO SYSTEM VALUE CAN BE EMITTED AT ALL** — EXP-0092's exhaustive 0x00-0xFF sweep exists, but on M4. (2) **`call.{b3,b5,b6,tail}` are `tokenization-only` ('framing only, no value semantics') and `ret.scoreboard` was declined in advance, so NO CALL CAN BE EMITTED** — precisely the instruction EXP-0137's split-epilog contract depends on. (3) `vary_store.{hint1,b5_tag}` are `untested` and the descriptor still carries a mis-tokenization flag EXP-0155 already solved. (4) `iter.b9` / `iter_at.grp` block all non-flat interpolation. (5) **`tile_read`/`tile_read_mrt` are measured only on M4 — the cheapest big win available, since harness, carriers and oracle all exist and only the target changes.** **Closure rules 1, 3, 4 and 6 all FAIL; rule 2 is partial** (the four experiments carrying G17P *semantics* predate the two-run gate entirely); rule 5 is mixed. **Five declared clean-room BOUNDARIES, not gaps:** Apple's own BG/EOT programs; the scratch/helper protocol (three independent lawful methods negative, EXP-0125 concluding it must be constructed from first principles rather than traced); a hidden second mode Metal never emits (EXP-0111 FS-05); Apple's inlining heuristic; and the fused EOT store op. | EXP-0177 assembly; EXP-0092/0109/0111/0117/0130/0137/0155/0163/0168/0172; quarantined: EXP-0050, EXP-0071 |

## P1 — API correctness and broad feature coverage

| ID | Requirement | Current status | Closure evidence required | Planned experiment cluster |
|---|---|---|---|---|
| P1.1 | Complete PBE and render-attachment structures | **OPEN** (depth/stencil slot reuse CONFIRMED; layer/mip location still unknown) | EXP-0132 CONFIRMS depth/stencil reuse the color MRT k-array at k=ncolor / k=ncolor+1 (generalized to ncolor=2), finds slice/mip are NOT in the per-attachment record, maps `mipCount>1` to word1 bit26, and constructs two distinct silent-failure modes (invalid slice destructively zeroes slice 0; invalid level is a no-op). `attachment-slot-b` NOT reproduced. Still needed: where layer/mip selection actually lives, the access/control word, coherency, and the 3-segment chain on M4. EXP-0048 repeats six format/control variants, address/dimension invariants and bounded action/blend bytes; still need every field plus layers/mips/MSAA/resolve/memoryless/compression/D/S and Linux packing | `EXP-0048-bg-eot-pbe` + exhaustive sweep |
| P1.2 | Per-format API capability and conversion table | **OPEN** (full 138-format x 11-axis matrix captured; compressed decode + sparse still open) | EXP-0133 captures the FULL public `MTLPixelFormat` enum (138 formats x 11 axes = 1518 cells) byte-exact across two runs, plus conversion/layout/sparse cases. Key driver-facing results: **`unorm16` ties round DOWN, opposite `unorm8`**; eligibility is an unconditional `abort()` not a soft query (static allowlist required); `Depth24Unorm_Stencil8`/`X24_Stencil8` are header-available but device-rejected; 21/22 integer formats support `texture2d` atomics. Still open: bit-exact decode for the 76 compressed formats beyond BC1, sparse semantics for 133/138, content verification on render/blend/storage axes, mips/arrays/cube/3D, A18 replication. EXP-0070 (`63a468f7`) repeats six exact in-bounds 1×1 public-Metal store/read cases with full owned backing: RGBA8 `0080ff80`, BGRA8 `ff800080`, sRGB `0a0abc80`, R16 `0080`, RGBA16F `0080003cff7b5535`, and R32Uint `efbeadde`. EXP-0079 (`84851b4f`) adds a two-run 37-case/14-format batch: snorm8 encode uses the SYMMETRIC `round(c*127)` scale (-1.0 -> `0x81`, refuting the asymmetric mapping); reduced-float store narrowing (fp16/fp11/fp10/RGB9E5) TRUNCATES TOWARD ZERO (refuting round-to-nearest-even, and a positive-direction probe refutes round-away-from-zero); R8Unorm ties round HALF-UP, not half-even (2.5/255 -> `0x03`). Normalized-integer and reduced-float stores therefore use different rounding rules on the same path. The full sample/filter/storage/atomic/render/blend/depth/linear/compressed/MSAA/resolve/sparse matrix plus general pack and swizzle behavior remain required. No PBE descriptor, native, Linux, or A18 inference. | `experiments/EXP-0070-m4-typed-format-conversion-contract/{RESULTS.md,analysis.json,raw/m4-TODO-run01,raw/m4-TODO-run02}` |
| P1.3 | Texture/image ISA breadth and edge behavior | **OPEN** (M4 public sampler partial) | EXP-0063 (`211d8a90`) records the original address-mode boundary; EXP-0066 (`5ea41e62`) separately repeats an off-center explicit-LOD-0 public-Metal matrix where tested zero/edge/repeat nearest reads green and linear reads the red/green blend. Generated encodings and every dimension/mode/operand/register class plus LOD, border, seams, OOB and image ordering remain required. No descriptor, ISA, Linux, native, or A18 inference. | `experiments/EXP-0066-m4-sampler-filter-provenance/{RESULTS.md,raw/m4-20260820-run01/02_run.json,raw/m4-20260820-run02/02_run.json}` |
| P1.4 | Vulkan/GL-grade memory and synchronization model | **OPEN** (M4 litmus + interlock/atomics + dynamic addressing bounded) | EXP-0051 (`adfa33b3`) repeats correct and deliberately weak MSL/API cases: ordered encoder/queue/event/host cases pass, while unsynchronized queues expose stale data. Relaxed, `mem_none`, and wrong-scope passes are bounded non-guarantees. EXP-0093 (`d3e7d1ba`) decodes the `0x07` fence/barrier family (incl. `threadgroup_barrier(mem_texture)` as a genuine acquire `sub=0x14` / release `sub=0x04` pair, correcting a db.json note) and establishes with concurrent litmus tests that **asymmetric fencing is NOT safe**: at >=4 producer/consumer pairs, relaxed messaging corrupts up to 100% and only fully symmetric fencing gives 0 mismatches (EXP-0051 saw none only because it ran at 1-2 pairs). `byte+3` bit0 (`0x85` vs `0x84`) is the execution-convergence enable, independent of the memory-fence class. EXP-0085 (`2e693a58`) re-validates the hardware register interlock on M4 (load/dependent-load/texture-read/atomic-result all feed a consuming ALU with zero slack and no software wait, corroborated by structural tokenization showing no wait ops) and establishes the atomics op-table (subtract selector `0x1b` distinct from add `0x10`), native single-transaction compare-exchange, and the SIMD pre-combine boundary (reducible ops only, and only at a compile-time-provably uniform address). EXP-0084 (`783fe693`) adds hardware-validated dynamic 64-bit addressing and proven per-lane divergent buffer selection. Still need the fence/barrier `0x07` family (ATOM-07..11), native/cache-domain mappings, Linux `vdm_barrier`/`cdm_barrier`, flush/invalidate, broader resources, and A18 | `EXP-0051-m4-synchronization-litmus`: `analysis/summary.json`, `analysis/report.txt`, `raw/m4_20260817_run01/06_suite.json`, `raw/m4_20260817_run02/06_suite.json` |
| P1.5 | Robustness, sparse residency and VM conventions | **OPEN** (M4 OOB/alignment behavior + base-slot census bounded) | EXP-0076 (`446a5f28`) establishes the owned-buffer robustness model on M4: accesses execute as independent naturally-aligned units with per-unit align-down addressing; OOB units read zero / stores discarded (guards intact); unaligned loads are not byte-exact; OOB atomic exchange reads 0. EXP-0083 (`8d47a271`) adds the base-slot census: selector effectively 7-bit (128..255 mirror 0..127 on load/store/atomic), no aliasing/holes among populated slots 1..30, 31 slots usable via direct binding (a binding-population edge, not a proven architectural ceiling), out-of-range slots fault-contained but silently wrong. Still need allocation-size/distance bounding of the zero-fill region, vertex/fragment stages, USC window, the uniform/constant-program slot-population path (MEM-18/19), sparse/VM conventions, kernel-side mechanism. [PRIORITY CLUSTER: load/store/SSBO] | `EXP-0076-m4-buffer-robustness-matrix` + follow-ups; supersedes never-captured EXP-0068 |
| P1.6 | Complete query and timestamp semantics | **OPEN** (M4 public-timestamp partial) | EXP-0052 (`cad2132b`) establishes equal/monotonic public CPU/GPU pairs, ordered samples within each pass, and post-completion resolve on M4; H3 strict cross-pass non-overlap is falsified, and immediate post-commit/pre-wait zero resolves are not qualified as in-flight. Still need Linux frequency/`GET_TIME`, private heap/availability/reset/copy/wrap, broader stages/queues, statistics, native semantics, and A18 | `EXP-0052-m4-timestamp-semantics`: `analysis/summary.json`, `analysis/report.txt`, `raw/m4_20260817_run03/run.json`, `raw/m4_20260817_run04/run.json` |
| P1.7 | Indirect and device-generated commands | **OPEN** (M4 public-Metal partial) | EXP-0053 (`e31dfb46`) canonical full-byte runs 05/06 establish the tested indirect-argument timing, zero/nonzero work, ICB ranges, reset/re-encode and one optimization-equivalence case; downgraded runs 03/04 and failures 01/02 remain process history. Still need direct/indirect CDM modes, multi-draw/dispatch/count/restart/bounds, writable command grammar, validation/cache transitions, Linux mapping and A18 | `EXP-0053-m4-indirect-api-semantics` + native DGC/indirect suite |
| P1.8 | Conformance numerical, rasterization and limits | **OPEN** (M4 numerical source-path partial; FP32 division answered) | EXP-0074 (`ae63b41f`) answers Part-II OPT-02 for the tested config: precise FP32 division is bit-exact vs a correctly-rounded binary32 reference except DAZ+FTZ (subnormal operands read as zero, subnormal results flush to zero); a single DAZ+FTZ model predicts 4171/4171 cases, FTZ proven independently of DAZ, NaNs always canonical `0x7FC00000`. EXP-0047 bounds fp32/fp16 subnormal, qNaN/minmax, signed-zero and rounding behavior for ten authored M4 Metal paths; still need native-op isolation, A18 replication, full floating/integer/raster/depth/sample/helper/limit coverage | `EXP-0047-m4-numerical-behavior` + remaining conformance suite |

## Compatibility inventory (non-gating)

`EXP-0044-uapi-closure-baseline` pins and hashes a Mesa/Asahi UAPI revision used
as a compatibility inventory. It neither defines the desired objects nor proves
Apple9 behavior; reconstruction closure is driven by independently generated
Apple userspace objects and hardware validation.

`EXP-0045-uapi-field-matrix` recursively expands the embedded UAPI records and checks that
all 65 queue/render/compute leaves have exactly one explicit closure row. Its baseline has
30 `OPEN`, 30 `A18-PARTIAL`, and 5 `PUBLIC-ONLY` rows; none is closed by the inventory itself.

## OpenGL addendum tracker (goal task 1, second half)

**STATUS: all 9 bundles CLOSED (2026-08-28).** All 29 addendum items have been
answered or explicitly scoped, each with committed raw evidence and a PROVENANCE row.
Several bundles are "closed for tested scope" with not-exercised cells named in their
RESULTS; those are recorded as successor work, not as silent gaps.

`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md` adds 29 OpenGL 4.6 / WineD3D-class compiler items.
Triage and dedup: `work/ADDENDUM-TRIAGE-20260828.md` (0 already-answered, 17 partial, 12 open;
20 of 29 collapse onto an existing OPEN primary-list row, so they are answered by ONE experiment
each rather than duplicated). Seven items are new hardware surface with no primary-list
counterpart. No item is blocked by the A18 hands-off directive.

| Bundle | Items | Status | Experiment |
|---|---|---|---|
| A — fragment sample/coverage/discard/demote/helper | GLFS-A01/02/03/05/06/07 (+ `OPT-09`) | **A01/A02/A05/A06 + OPT-09 CLOSED; A03/A07 PARTIAL** (`4c2df727`) | `EXP-0091-m4-fragment-sample-discard` |
| B — pixel/sample interlock + device-fence family | GLFS-A08 + `ATOM-07..11` | **CLOSED for tested scope** (`d3e7d1ba`): ROG proven causally by splice-neutering; ATOM-11 negative (buffer- vs texture-tagged ROG use different mechanisms); asymmetric fencing UNSAFE at >=4 pairs. MSAA/multi-RT/nesting scope named for a successor | `EXP-0093-m4-fence-barrier-interlock` |
| C — vertex/instance/base/draw-ID + general sysval ABI | GLIO-A02/A03/A05/A06 | **A03 CLOSED; A02/A05 CLOSED-PARTIAL; A06 table populated** (`96f9dade`); draw-ID UNKNOWN (no Metal multidraw) | `EXP-0092-m4-sysval-abi` |
| D — texture bias/gradient/implicit-LOD ABI | GLTEX-A01/02/03 | **A01/A03 CLOSED; A02 PARTIAL** (`6d3ad2ef`): exact LOD clamp formula; `calculate_clamped_lod` bit-exact; bias-operand register splice-validated, gradient-operand register OPEN; bias(NaN)→mip 0 vs gradient(NaN/Inf)→mip 8 | `EXP-0094-m4-texture-lod-abi` |
| E — texture/image dimension-format operation matrix | GLTEX-A04/05/06/07 + GLIMG-A01/02 | **CLOSED for tested scope** (`47954e44`): texel-buffer ceiling 2^28 texel-size-INDEPENDENT (falsifies the addendum's own formula); fetch/read zero vs sample/gather CLAMP at illegal layer; image table 128 entries (8 for read_write/atomic); bindless has NO mirroring, unlike EXP-0083 buffer slots | `EXP-0095-m4-texture-image-matrix` |
| F — threadgroup addressing / compute launch | GLCS-A02 (A01 out of scope) | **CLOSED for 2884/2900 splice + 145/145 budget** (`f5c321c4`); PARTIAL on 16 racy byte+1 values `(v&0x17)==0x04`. Store `idx_off` x16B vs load x4 element asymmetry; **combined tgmem 65536 B ceiling is NOT API-validated — silently corrupts** | `EXP-0100-m4-threadgroup-addressing` (successor to quarantined `EXP-0096`) |
| G — varying/UVS capacity + pre-raster outputs | GLIO-A01, GLPRE-A03 | **CLOSED** (`eef37ca8`): 124 varying scalar components (per-component, consumed-only), clip-distance 8 independent, provoking vertex FIXED to first vertex (must emulate for GL) | `EXP-0097-m4-varying-capacity` |
| H — GPU-driven compute-generated draws | GLPRE-A01/A02 | **CLOSED** (`fc804669`): encoder-order and symmetric fence safe (0/48 raced); untracked+asymmetric UNSAFE — indexed raced 8/8 every mode, to 99.997% stale. `[[instance_id]]` is ABSOLUTE; ICB `location>maxCommandCount` faults; `maxCommandCount` SIGSEGVs at 8388608 | `EXP-0098-m4-gpu-driven-draws` |
| I — compute-emulated transform feedback | GLXFB-A01 | **CLOSED** (`fc804669`): capacity/no-partial-primitive/multistream/interleaved/discard match a closed-form model 32/32; unsafe-mode signature is a ~400x latency penalty with zero corruption, mechanism UNKNOWN | `EXP-0098-m4-gpu-driven-draws` |

Highest-value new surface flagged by triage: GLFS-A01 (the actual kill/target-mask/live-mask
instruction — undecoded anywhere in the repo; a negative result is a legitimate outcome),
GLFS-A04 (shader sample-mask semantics), GLIO-A01 (UVS/coefficient capacity), GLIO-A02 (general
`get_sr` encoding), GLIO-A04 (MSAA sysval ABI incl. the unresolved `0x97` sample-ID path),
GLIO-A05 (`load_num_workgroups`), and the operand-decode half of GLCS-A02 (`tg_addr_compute`).

## Synthesis acceptance test (goal task 3)

`EXP-0090-m4-handbuilt-program-suite` (IN FLIGHT) is the direct test of the project's central
claim: four or more **hand-built non-trivial programs** — authored instruction sequences, not
splices into compiler output — each checked against an independent host-computed oracle, with a
systematic operand-field matrix across register indices, immediates, offset boundaries,
element-size codes and base slots. Per-family verdicts will be CONFIRMED / REFINED / REFUTED.
Until it passes, DRV-ISA-01 cannot be closed regardless of decode coverage.

## Register-lifecycle model (goal task 2)

`EXP-0086` REFUTED the "inert scheduling hint" reading of the source-cache/last-use bits: a
producer-side bit in the float-ALU family makes a **later** separate instruction's read return
zero, deterministically and without a fault (`docs/isa/register-move-and-liveness.md`).
`EXP-0087` found that only `byte+2=0x01`/`op_desc=0x08` actually moves a value while most other
encodings are silent zeroing no-ops. `EXP-0089-m4-register-lifecycle-model` (IN FLIGHT) completes
the two-run gate, tests the literal bit 17 in a family where it is free, sweeps the corrupting
bit across distance/pressure/control-flow, characterises the non-inert `ctrl`/`ctrl_lo` field,
and discriminates between last-use-hint and register-cache-residency models.

## Completion gate

All sixteen rows must be `CLOSED`, with target-qualified evidence and intact provenance
chains. The final audit must positively reproduce the claimed generation paths and prove
that no required field or supported operation depends on captured Apple templates or on
inspection of Apple's implementation.


---

## 2026-08-30 G17P wave — facts added from the emit/closure experiments

> Drafted by EXP-0186, which audited which results had reached this deliverable and found
> **20 of 22 emitter-facing facts missing or refuted-but-still-stated**. Every block below is
> traced to a committed experiment artifact, carries its evidence label and the **target it was
> measured on**, and keeps the bounds the measuring experiment stated. Where a result is
> deliberately bounded it says so; a doc that drops the bound is worse than no doc.

**RANKED BLOCKERS — three of the five original blockers CLOSED on 2026-08-30, all on G17P.**
(1) ~~`get_sr.sr_sel` untested on G17P~~ **CLOSED:** `sr_sel`, `dp_width` and `dp_marker` are
`hardware-run` on G17P over three stage carriers (`EXP-0178`), and `get_sr` is EMITTABLE — with
the new stage rule that a bit-7-clear selector faults in vertex. (2) ~~no call can be emitted~~
**CLOSED:** `EXP-0179` generated 192 distinct calls with 384/384 correct and moved
`call.{b3,b5,b6,tail}` from `tokenization-only` to `hardware-run`; the emitter contract adds a
constraint nobody had — **`pop_reconverge` after a call is REQUIRED, the frame marker is
OPTIONAL**. `ret.scoreboard` remains declined, now on a control that **fired**. (3)
`vary_store.{hint1,b5_tag}` — **partly answered**: `hint6` is `hardware-run` (`EXP-0163`).
(4) `iter.b9` / `iter_at.grp` — **partly answered**: `iter_at.loc` is `hardware-run` and is bit 1
alone (`EXP-0163`); `grp` was deliberately not promoted. (5) ~~`tile_read`/`tile_read_mrt`
measured only on M4~~ **CLOSED as a measurement:** re-measured on G17P over four carriers with
every M4 value set transferring unchanged (`EXP-0178` §5) — though **neither instruction is
emittable**, `tile_read` still blocked by `b2`/`b4`/`b6_hi`/`b7`/`tail` and `tile_read_mrt` by
`b4`/`b6_hi`/`tail`.
