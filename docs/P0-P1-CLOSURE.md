# Apple9 P0/P1 Closure Matrix

This is the live status board for closing every P0 and P1 item in
`AGX_RE_INFORMATION_GAPS.md` for A18 Pro/G17P and M4/G16G.

The current execution target is the local M4. New results are marked **M4-VALIDATED** and
remain **A18-INFERRED** until the same load-bearing behavior is re-run on the A18. Existing
A18 evidence remains valid where cited. No cross-target transfer is silently promoted.

## Closure rules

A row is `CLOSED` only when:

1. the required value or behavior can be generated, not merely decoded from a captured
   template;
2. the complete authored probe, commands, raw observations, failures, and analysis are
   committed under `experiments/`;
3. the evidence chain is recorded in `PROVENANCE.md`;
4. the normative docs contain the exact fields, ranges, fallbacks, and target status;
5. an adversarial reproduction or second method passes; and
6. the result is mapped to the unchanged UAPI where that UAPI assigns responsibility to
   userspace.

Evidence strength is defined by `CODEX.md`. Tokenization or a byte-exact round trip alone
cannot close a synthesis gap.

## P0 — complete-driver and unchanged-UAPI blockers

| ID | Requirement | Current status | Closure evidence required | Active experiment |
|---|---|---|---|---|
| P0.1 | Userspace scratch allocator and VS/FS/CS helper-program ABI | **OPEN** (M4 negative boundary probe) | Helper binary/cfg/data fields; helper SR inputs; scratch BO headers, block lists, buckets, topology mapping, limits and failure behavior; generated helper runs spill and preamble scratch on M4 and A18 | `EXP-0041`: 0–576 B scratch executes, but no helper/scratch record or allocation surfaced |
| P0.2 | Graphics shader selection and code-BO handoff through existing `usc_exec_base` | **OPEN** (M4 selectors partial) | EXP-0042 proves separable live VS token and FS window-relative selector across 36 draws; still need general token/tag derivation, exact `usc_exec_base` mapping, relocatable entry/extent, HW/FW-consumer proof and A18 run | `EXP-0042-graphics-code-selection` |
| P0.3 | Apple9 value for every existing render/compute UAPI field | **OPEN** (M4 CDM end partial) | EXP-0043 locates direct-stream termination/rollover on M4; still need field-by-field values and Linux mapping for flags, ZLS, PPP/sample control, scissor/dbias/query arrays, sampler heap, arbitrary linked `cdm_ctrl_stream_end`, timestamps, dimensions and clears | `EXP-0044/0045` baseline; `EXP-0043` framing partial |
| P0.4 | BG/EOT/partial-BG/partial-EOT programs | **OPEN** (M4 behavior/negative-boundary partial) | EXP-0048 proves tested empty Clear/Store and Load/Store behavior but locates no program/tag/resource spec/ABI; still need independently generated authored programs plus tilebuffer ABI, format conversion, resolve, samples/layers and partial behavior | `EXP-0048-bg-eot-pbe` + program-ABI follow-up |
| P0.5 | Complete relocatable VDM/CDM/PPP/USC command and state packing | **OPEN** (M4 exact-shape rollover partial) | EXP-0043 locates the tested direct CDM/VDM terminals and first rollover boundaries. EXP-0049 (`84779ec8`) repeats the exact 732/733 CDM and 328/329 VDM pairs and preserves tested bytes under encoder/padding controls, but alternate indirect/stable/pass-per-draw shapes stop without the known pair. Still need hardware-consumer proof, link mutation, general capacity/relocation, barriers/calls/indirect, complete PPP/USC schemas, independent packer, Linux mapping and A18 | `EXP-0043-command-stream-framing`; `EXP-0049-command-link-structure` + mutation/packer follow-up |
| P0.6 | Compiler-ready ISA and opcode property model | **OPEN** | Every supported NIR path can generate semantic operands over legal register/immediate ranges; side-effect/control/scheduling properties; independently generated shader suite runs | `EXP-0046` synthesis audit: 92/170 descriptors lack a central fixed vector; 59 retain raw fields |
| P0.7 | Shader container, extent, metadata and resource-spec generation | **OPEN** (M4 live record partial) | EXP-0042 matches authored constant/main bytes inside 0x40-header aligned records and falsifies the old FS-size reading; still need HW-consumer proof, complete writer/replacement mapping, resource-spec derivation and independent launch | `EXP-0042-graphics-code-selection` |
| P0.8 | Complete VS/FS/CS ABI and programmable prolog/epilog linkage | **OPEN** | Inputs, outputs, sysvals, interpolation, tilebuffer, calls, scratch, linking and sideband; independently generated blend/logic/conversion epilogs across advertised formats | queued |

## P1 — API correctness and broad feature coverage

| ID | Requirement | Current status | Closure evidence required | Planned experiment cluster |
|---|---|---|---|---|
| P1.1 | Complete PBE and render-attachment structures | **OPEN** (M4 MRT structural partial) | EXP-0048 repeats six format/control variants, address/dimension invariants and bounded action/blend bytes; still need every field plus layers/mips/MSAA/resolve/memoryless/compression/D/S and Linux packing | `EXP-0048-bg-eot-pbe` + exhaustive sweep |
| P1.2 | Per-format API capability and conversion table | **OPEN** | Sample/filter/storage/atomic/render/blend/depth/linear/compressed/MSAA/resolve/sparse matrix plus pack, rounding and swizzle behavior | all-format behavior sweep |
| P1.3 | Texture/image ISA breadth and edge behavior | **OPEN** | Generated encodings and behavior for every supported dimension/mode/operand/register class plus LOD, border, seams, OOB and image ordering | texture synthesis matrix |
| P1.4 | Vulkan/GL-grade memory and synchronization model | **OPEN** (M4 Metal-path litmus partial) | EXP-0051 (`adfa33b3`) repeats correct and deliberately weak MSL/API cases: ordered encoder/queue/event/host cases pass, while unsynchronized queues expose stale data. Relaxed, `mem_none`, and wrong-scope passes are bounded non-guarantees. Still need native/cache-domain mappings, Linux `vdm_barrier`/`cdm_barrier`, flush/invalidate, broader resources, and A18 | `EXP-0051-m4-synchronization-litmus`: `analysis/summary.json`, `analysis/report.txt`, `raw/m4_20260817_run01/06_suite.json`, `raw/m4_20260817_run02/06_suite.json` |
| P1.5 | Robustness, sparse residency and VM conventions | **OPEN** | Runtime limits; USC window; OOB behavior; guard/zero/scratch mappings; sparse page/folio/miptail/alias/sync rules; BO constraints | VM/robustness/sparse suite |
| P1.6 | Complete query and timestamp semantics | **OPEN** (M4 public-timestamp partial) | EXP-0052 (`cad2132b`) establishes equal/monotonic public CPU/GPU pairs, ordered samples within each pass, and post-completion resolve on M4; H3 strict cross-pass non-overlap is falsified, and immediate post-commit/pre-wait zero resolves are not qualified as in-flight. Still need Linux frequency/`GET_TIME`, private heap/availability/reset/copy/wrap, broader stages/queues, statistics, native semantics, and A18 | `EXP-0052-m4-timestamp-semantics`: `analysis/summary.json`, `analysis/report.txt`, `raw/m4_20260817_run03/run.json`, `raw/m4_20260817_run04/run.json` |
| P1.7 | Indirect and device-generated commands | **OPEN** (M4 public-Metal partial) | EXP-0053 (`e31dfb46`) canonical full-byte runs 05/06 establish the tested indirect-argument timing, zero/nonzero work, ICB ranges, reset/re-encode and one optimization-equivalence case; downgraded runs 03/04 and failures 01/02 remain process history. Still need direct/indirect CDM modes, multi-draw/dispatch/count/restart/bounds, writable command grammar, validation/cache transitions, Linux mapping and A18 | `EXP-0053-m4-indirect-api-semantics` + native DGC/indirect suite |
| P1.8 | Conformance numerical, rasterization and limits | **OPEN** (M4 numerical source-path partial) | EXP-0047 bounds fp32/fp16 subnormal, qNaN/minmax, signed-zero and rounding behavior for ten authored M4 Metal paths; still need native-op isolation, A18 replication, full floating/integer/raster/depth/sample/helper/limit coverage | `EXP-0047-m4-numerical-behavior` + remaining conformance suite |

## Public UAPI baseline

`EXP-0044-uapi-closure-baseline` pins and hashes the exact MIT-licensed Mesa UAPI
revision used by the information-gap audit. It confirms that helpers, BG/EOT programs,
resource specifications, command-stream addresses, and render-control values are userspace
inputs. This is a requirements result, not Apple9 hardware evidence.

`EXP-0045-uapi-field-matrix` recursively expands the embedded UAPI records and checks that
all 65 queue/render/compute leaves have exactly one explicit closure row. Its baseline has
30 `OPEN`, 30 `A18-PARTIAL`, and 5 `PUBLIC-ONLY` rows; none is closed by the inventory itself.

## Completion gate

All sixteen rows must be `CLOSED`, with target-qualified evidence and intact provenance
chains. The final audit must positively reproduce the claimed generation paths and prove
that no required field or supported operation depends on captured Apple templates or on
inspection of Apple's implementation.
