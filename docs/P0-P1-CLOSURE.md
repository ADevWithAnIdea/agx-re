# Apple9 P0/P1 Closure Matrix

This is the live status board for closing every P0 and P1 item in
`APPLE9_RE_IMPLEMENTATION_GAPS.md` (the authoritative task list, superseding the removed
`AGX_RE_INFORMATION_GAPS.md` audit) using the local M4/G16G as the **sole test target**.
**User directive (2026-08-27): the A18 Pro/G17P is hands-off (never SSH, probe, or reboot
it; `macvdmtool` is never used), and all testing runs locally on the M4, which is
Apple9-equal to the A18 Pro for every driver-emittable subsystem (`EXP-M4-*`
byte-identity).** A18-specific replication is suspended, not a closure gate; every result
still records its actual M4 target and must not be relabeled as directly observed on A18.

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

## P0 — complete-driver and unchanged-UAPI blockers

| ID | Requirement | Current status | Closure evidence required | Active experiment |
|---|---|---|---|---|
| P0.1 | Userspace scratch allocator and VS/FS/CS helper-program ABI | **OPEN** (M4 negative boundary probe) | Helper binary/cfg/data fields; helper SR inputs; scratch BO headers, block lists, buckets, topology mapping, limits and failure behavior; generated helper runs spill and preamble scratch on M4 and A18 | `EXP-0041`: 0–576 B scratch executes, but no helper/scratch record or allocation surfaced |
| P0.2 | Graphics shader selection and code-BO handoff through existing `usc_exec_base` | **OPEN** (M4 selectors partial) | EXP-0042 proves separable live VS token and FS window-relative selector across 36 draws; still need general token/tag derivation, exact `usc_exec_base` mapping, relocatable entry/extent, HW/FW-consumer proof and A18 run | `EXP-0042-graphics-code-selection` |
| P0.3 | Apple9 value for every existing render/compute UAPI field | **OPEN** (M4 stream/public-state behavior partial) | EXP-0043 locates direct-stream termination/rollover. EXP-0054 (`6c342a06`) retains four M4 public-Metal runs: exact tested single/two-scissor coverage and bounded Depth32Float `2^-24` constant and `-0.01875` slope correlations; runs01/02 preserve the inactive magnitude-100 H4 clamp negative, while separately preregistered runs03/04 support sign-matched magnitude-100000 clamps. EXP-0055 (`83e29abe`) adds a clean exact-two-VA M4 DATA-TRACE boundary: every tested nonzero constant/slope input changes only `0x58000+0x36` `00->02` as an enable candidate, while tested scissor/multi/clamp readbacks change without a semantic pair delta in either allowed mapping and `0x68000` remains unchanged. Still need private `isp_scissor_base`/`isp_dbias_base` layout, integer mode, every other field, hardware-consumer proof, Linux mapping and A18 | `EXP-0044/0045` baseline; `EXP-0043` framing; `EXP-0054-m4-scissor-depth-bias` public behavior; `experiments/EXP-0055-m4-scissor-depth-bias-state/analysis/summary.json`; `experiments/EXP-0055-m4-scissor-depth-bias-state/analysis/report.txt`; `experiments/EXP-0055-m4-scissor-depth-bias-state/raw/m4_20260817_run01/04_boundary_preflight.json`; `experiments/EXP-0055-m4-scissor-depth-bias-state/raw/m4_20260817_run02/04_boundary_preflight.json` |
| P0.4 | BG/EOT/partial-BG/partial-EOT programs | **OPEN** (M4 behavior/negative-boundary partial) | EXP-0048 proves tested empty Clear/Store and Load/Store behavior but locates no program/tag/resource spec/ABI; still need independently generated authored programs plus tilebuffer ABI, format conversion, resolve, samples/layers and partial behavior | `EXP-0048-bg-eot-pbe` + program-ABI follow-up |
| P0.5 | Complete relocatable VDM/CDM/PPP/USC command and state packing | **OPEN** (M4 exact-shape rollover partial) | EXP-0043 locates the tested direct CDM/VDM terminals and first rollover boundaries. EXP-0049 (`84779ec8`) repeats the exact 732/733 CDM and 328/329 VDM pairs and preserves tested bytes under encoder/padding controls, but alternate indirect/stable/pass-per-draw shapes stop without the known pair. Still need hardware-consumer proof, link mutation, general capacity/relocation, barriers/calls/indirect, complete PPP/USC schemas, independent packer, Linux mapping and A18 | `EXP-0043-command-stream-framing`; `EXP-0049-command-link-structure` + mutation/packer follow-up |
| P0.6 | Compiler-ready ISA and opcode property model | **OPEN** (one structural subset increment) | EXP-0060 (`911b253f`) binds 1,440 repository-only `falu2i` semantic-subset codec round trips. It excludes `opflags`/`ctrl_lo`/`mods` and proves neither hardware execution, general emission, NIR completeness, native semantics, nor A18 behavior. Every supported NIR path still needs legal semantic construction, properties, and independently generated runs. | `EXP-0046` synthesis audit; `experiments/EXP-0060-isa-falu2i-bound-vectors/{RESULTS.md,raw/run01/result.json}` |
| P0.7 | Shader container, extent, metadata and resource-spec generation | **OPEN** (M4 live record partial) | EXP-0042 matches authored constant/main bytes inside 0x40-header aligned records and falsifies the old FS-size reading; still need HW-consumer proof, complete writer/replacement mapping, resource-spec derivation and independent launch | `EXP-0042-graphics-code-selection` |
| P0.8 | Complete VS/FS/CS ABI and programmable prolog/epilog linkage | **OPEN** | Inputs, outputs, sysvals, interpolation, tilebuffer, calls, scratch, linking and sideband; independently generated blend/logic/conversion epilogs across advertised formats | queued |

## P1 — API correctness and broad feature coverage

| ID | Requirement | Current status | Closure evidence required | Planned experiment cluster |
|---|---|---|---|---|
| P1.1 | Complete PBE and render-attachment structures | **OPEN** (M4 MRT structural partial) | EXP-0048 repeats six format/control variants, address/dimension invariants and bounded action/blend bytes; still need every field plus layers/mips/MSAA/resolve/memoryless/compression/D/S and Linux packing | `EXP-0048-bg-eot-pbe` + exhaustive sweep |
| P1.2 | Per-format API capability and conversion table | **OPEN** (M4 conversion rules for 14 formats bounded) | EXP-0070 (`63a468f7`) repeats six exact in-bounds 1×1 public-Metal store/read cases with full owned backing: RGBA8 `0080ff80`, BGRA8 `ff800080`, sRGB `0a0abc80`, R16 `0080`, RGBA16F `0080003cff7b5535`, and R32Uint `efbeadde`. EXP-0079 (`84851b4f`) adds a two-run 37-case/14-format batch: snorm8 encode uses the SYMMETRIC `round(c*127)` scale (-1.0 -> `0x81`, refuting the asymmetric mapping); reduced-float store narrowing (fp16/fp11/fp10/RGB9E5) TRUNCATES TOWARD ZERO (refuting round-to-nearest-even, and a positive-direction probe refutes round-away-from-zero); R8Unorm ties round HALF-UP, not half-even (2.5/255 -> `0x03`). Normalized-integer and reduced-float stores therefore use different rounding rules on the same path. The full sample/filter/storage/atomic/render/blend/depth/linear/compressed/MSAA/resolve/sparse matrix plus general pack and swizzle behavior remain required. No PBE descriptor, native, Linux, or A18 inference. | `experiments/EXP-0070-m4-typed-format-conversion-contract/{RESULTS.md,analysis.json,raw/m4-TODO-run01,raw/m4-TODO-run02}` |
| P1.3 | Texture/image ISA breadth and edge behavior | **OPEN** (M4 public sampler partial) | EXP-0063 (`211d8a90`) records the original address-mode boundary; EXP-0066 (`5ea41e62`) separately repeats an off-center explicit-LOD-0 public-Metal matrix where tested zero/edge/repeat nearest reads green and linear reads the red/green blend. Generated encodings and every dimension/mode/operand/register class plus LOD, border, seams, OOB and image ordering remain required. No descriptor, ISA, Linux, native, or A18 inference. | `experiments/EXP-0066-m4-sampler-filter-provenance/{RESULTS.md,raw/m4-20260820-run01/02_run.json,raw/m4-20260820-run02/02_run.json}` |
| P1.4 | Vulkan/GL-grade memory and synchronization model | **OPEN** (M4 Metal-path litmus partial) | EXP-0051 (`adfa33b3`) repeats correct and deliberately weak MSL/API cases: ordered encoder/queue/event/host cases pass, while unsynchronized queues expose stale data. Relaxed, `mem_none`, and wrong-scope passes are bounded non-guarantees. Still need native/cache-domain mappings, Linux `vdm_barrier`/`cdm_barrier`, flush/invalidate, broader resources, and A18 | `EXP-0051-m4-synchronization-litmus`: `analysis/summary.json`, `analysis/report.txt`, `raw/m4_20260817_run01/06_suite.json`, `raw/m4_20260817_run02/06_suite.json` |
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

## Completion gate

All sixteen rows must be `CLOSED`, with target-qualified evidence and intact provenance
chains. The final audit must positively reproduce the claimed generation paths and prove
that no required field or supported operation depends on captured Apple templates or on
inspection of Apple's implementation.
