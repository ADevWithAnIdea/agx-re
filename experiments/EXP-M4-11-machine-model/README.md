# EXP-M4-11: Machine-model validation on the local Apple M4 (gap X-1 / m4-deltas §2)

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER + HW-PROBE + DATA-TRACE (no Apple binary disassembled)
- **Host / device:** local Apple **M4** (Mac16,10, 10-core GPU, Metal 4, `applegpu_g16g`, Apple9).
  All compile / extract / splice / run is done locally on the M4 GPU — no SSH.
- **Question:** `docs/m4-deltas.md` §2 (Machine model) is the last ⏳ subsystem. Confirm the
  A18 Pro machine model (baseline: `docs/isa/README.md` machine-model + SR/ABI sections) holds
  on the M4, or find a delta. Same ISA (EXP-M4-01), so identical is expected.

## Hypothesis
The M4 shares the A18 Pro (G17P) AGX Apple9 machine model exactly: 96-GPR hard boundary,
2-halves-per-GPR, uniform register file with both source encodings, spill-to-scratch,
the `get_sr` SR table, in-shader software vertex attribute fetch, HW register-interlock
async completion, and the two cmdstream items (u32 index opcode, stage-boundary timestamps).

## Method (all clean-room legal)
- **Splice-and-observe (OWN-SHADER + HW-PROBE):** compile our own MSL → extract `_agc.main`
  with our own parser (`harness/agxparse.py`) → splice bytes → run the archived (spliced)
  machine code on the real GPU via `tools/agxtest/agxtest.py` (proves the spliced bytes ran
  via `PIPELINE_SOURCE archive`). Disassembly is with our own DB (`tools/agx-isa`, read-only).
- **Metadata (OWN-SHADER):** read our own shader's own `__GPU_METADATA` FlatBuffer (field 0 =
  GPR footprint, 14/41 = scratch bytes) — `meta_sweep.py`.
- **Render read-off (OWN-SHADER):** compile our own VS/FS, extract stage code, tokenize.
- **DATA-TRACE:** `harness/dvar11.m` (our own draw) under `harness/iotrace.dylib` (IOKit
  interposer, reused from EXP-M4-03) dumps our own command-stream BOs (hex = non-copyrightable
  data). Used only for item 8 (u32 index opcode, timestamps).

No Apple binary (Metal/AGX*/IOGPU/kext/firmware) is ever disassembled or introspected.

## Procedure (per item; re-runnable)
| item | script | what it does |
|---|---|---|
| 1a cap=96 / 4a spill | `meta_sweep.py [float|half]` | GPR-footprint + scratch sweep from own metadata |
| 1  no-alias functional | `copy96.py`, `spill_check.py` | ~96-live copy kernels; mod-64 alias would corrupt |
| 1b mem-index boundary | `idx_boundary.py` | splice `device_load` byte+5 across r95/r96 |
| 1c ALU out-of-file | `alu_src.py`, `alu_srcA.py` | splice falu2 operand reg (compact-form caveat noted) |
| 2a halves 2/GPR | `meta_sweep.py half` | 64 halves → f0=50 |
| 2b low-half size bit | `half_lowhalf.py` | splice srcA size bit; low halfword = half 1.0 |
| 3 uniform encodings | `uniform.py` | both srcB/srcA uniform forms; runtime read; select-bit splice |
| 5 SR table | `sr_splice.py` (compute), read-off (graphics) | splice `get_sr` byte1 |
| 6 attr fetch = SW | `attr_fetch.py` | vary `MTLVertexDescriptor`, byte-diff VS |
| 7 HW interlock | `interlock.py` | dependent + independent loads; no wait op |
| 8a u32 index 0x61f4 | `harness/dvar11 --idx32` + iotrace | VDM record opcode |
| 8b timestamps | `harness/dvar11 --ts` + iotrace | stage-boundary uint64-ns / period 1.0 |

## Raw results
`raw/*.txt` (one per item). Command-stream BO dumps under `work/cmd/*.maps/` (gitignored; key
bytes copied into `raw/8a_u32_index_opcode.txt`).

## Result
**Every item IDENTICAL to A18 — zero machine-model deltas.** See `RESULTS.md` for the
per-item evidence. `docs/m4-deltas.md` §2 can flip ⏳ → ✅.

## Clean-room status
Clean. Only our own MSL compiled; only our own compiled bytes / our own `__GPU_METADATA` /
our own command-stream BOs inspected/spliced/executed. Reused OWN-SHADER tools
(`tools/agxtest`, `tools/shdump`, `tools/agx-isa` read-only) + EXP-0031 `attrdump.m` +
EXP-M4-03 `iotrace.dylib`/`dvar.m` (copied, extended). Did **not** edit `tools/agx-isa`,
`docs/`, PROVENANCE, ROADMAP, reviews/. Did not commit.
