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
| P0.2 | Graphics shader selection and code-BO handoff through existing `usc_exec_base` | **OPEN** | Multiple coexisting pipelines selected without a new UAPI field; relative-address/tag derivation; complete relocatable block/entry/extent mapping; distinguish HW/FW ABI from Metal bookkeeping | `EXP-0042-graphics-code-selection` |
| P0.3 | Apple9 value for every existing render/compute UAPI field | **OPEN** | Field-by-field generation table and live tests for flags, ZLS, PPP/sample control, scissor/dbias/query arrays, sampler heap, stream end, timestamps, dimensions and clears | `EXP-0044` baseline; exhaustive 65-leaf manifest in `EXP-0045`; probes queued |
| P0.4 | BG/EOT/partial-BG/partial-EOT programs | **OPEN** | Independently generated authored programs plus tilebuffer ABI, resource spec, tags, format conversion, load/clear/store/resolve, samples/layers, partial and empty-tile behavior | queued |
| P0.5 | Complete relocatable VDM/CDM/PPP/USC command and state packing | **OPEN** | Machine-readable packet schema; type/length/order/alignment/reserved rules; links/calls/termination/barriers; relocations; multi-command and rollover tests | `EXP-0043-command-stream-framing` |
| P0.6 | Compiler-ready ISA and opcode property model | **OPEN** | Every supported NIR path can generate semantic operands over legal register/immediate ranges; side-effect/control/scheduling properties; independently generated shader suite runs | `EXP-0046` synthesis audit: 92/170 descriptors lack a central fixed vector; 59 retain raw fields |
| P0.7 | Shader container, extent, metadata and resource-spec generation | **OPEN** | Separate HW-consumed fields from archive bookkeeping; complete writer or UAPI replacement mapping; resource-spec derivation and multi-pipeline launch | `EXP-0042-graphics-code-selection` |
| P0.8 | Complete VS/FS/CS ABI and programmable prolog/epilog linkage | **OPEN** | Inputs, outputs, sysvals, interpolation, tilebuffer, calls, scratch, linking and sideband; independently generated blend/logic/conversion epilogs across advertised formats | queued |

## P1 — API correctness and broad feature coverage

| ID | Requirement | Current status | Closure evidence required | Planned experiment cluster |
|---|---|---|---|---|
| P1.1 | Complete PBE and render-attachment structures | **OPEN** | Every field and invariant in the PBE and load/render/store records; layers/mips/MSAA/resolve/memoryless/compression/D/S combinations | PBE/attachment exhaustive sweep |
| P1.2 | Per-format API capability and conversion table | **OPEN** | Sample/filter/storage/atomic/render/blend/depth/linear/compressed/MSAA/resolve/sparse matrix plus pack, rounding and swizzle behavior | all-format behavior sweep |
| P1.3 | Texture/image ISA breadth and edge behavior | **OPEN** | Generated encodings and behavior for every supported dimension/mode/operand/register class plus LOD, border, seams, OOB and image ordering | texture synthesis matrix |
| P1.4 | Vulkan/GL-grade memory and synchronization model | **OPEN** | Producer/consumer cache-domain tests; scope/order mappings; flush/invalidate and barrier encodings; cross-queue/host visibility | synchronization litmus suite |
| P1.5 | Robustness, sparse residency and VM conventions | **OPEN** | Runtime limits; USC window; OOB behavior; guard/zero/scratch mappings; sparse page/folio/miptail/alias/sync rules; BO constraints | VM/robustness/sparse suite |
| P1.6 | Complete query and timestamp semantics | **OPEN** | Heap layout, allocation/reset/availability/copy; stage ordering; frequency/wrap/calibration; statistics fallback | query/timestamp suite |
| P1.7 | Indirect and device-generated commands | **OPEN** | Direct/indirect CDM modes; multi-draw/dispatch/count/restart/bounds; writable command grammar, validation and cache transitions | DGC/indirect suite |
| P1.8 | Conformance numerical, rasterization and limits | **OPEN** | Floating/integer corner cases, interpolation, raster/depth/sample rules, side effects/helper interaction, and driver-facing hard limits | conformance behavior suite |

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
