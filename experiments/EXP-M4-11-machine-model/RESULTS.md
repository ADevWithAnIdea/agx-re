# EXP-M4-11 Results — M4 machine model vs A18 baseline

**Device:** local Apple **M4** (Mac16,10, 10-core, Metal 4, `applegpu_g16g`, Apple9). **Reboots: 0.**
Every byte inspected/spliced/executed is our own compiled MSL / our own command-stream data
(OWN-SHADER + HW-PROBE + DATA-TRACE). Splices ran the archived (spliced) code (`PIPELINE_SOURCE archive`).

## TL;DR — ALL 8 ITEMS IDENTICAL to A18 (zero machine-model deltas)
| # | Claim | M4 verdict |
|---|---|---|
| 1 | 96 GPRs, hard boundary (r96+ faults as index; no mod-64) | **IDENTICAL** |
| 2 | 16-bit halves, 2 per GPR; low-half via size bit | **IDENTICAL** |
| 3 | Uniform register file + BOTH uniform-source encodings | **IDENTICAL** |
| 4 | Spill to scratch; occupancy 2-tier bit (CMD-8) | **IDENTICAL** |
| 5 | `get_sr` SR table | **IDENTICAL** (all codes) |
| 6 | Vertex attribute fetch = in-shader software | **IDENTICAL** |
| 7 | Async completion = HW register interlock (no scoreboard) | **IDENTICAL** |
| 8 | u32 index opcode `0x61f4`; stage-boundary timestamps | **IDENTICAL** (both now HW-run on M4) |

`docs/m4-deltas.md` §2 → **✅ IDENTICAL**.

---

## 1 — 96 GPRs, hard boundary (EMPHASIS ITEM)  — IDENTICAL

**1a. Metadata caps at exactly 96** (`meta_sweep.py float`, `raw/1a_meta_float.txt`): field-0 GPR
footprint grows then **caps at exactly 96 and NEVER exceeds it** (K=62→96, and every K up to 256
stays 96 — never 97/100/128). Scratch (field 14/41) is 0 until the file overflows, then grows:
K=104→400 B, 128→576, 192→896, 256→1280 — **byte-for-byte the A18/RT-7 numbers.**

**1b. Memory-index hard fault at r95/r96** (`idx_boundary.py`, `raw/1b_idx_boundary.txt`). Kernel
`out[gid]=in[gid]`; splicing the `device_load` index register (byte+5, file off 0x09):
`r0..r95 → STATUS OK` (uninitialized regs read 0 → `a[0]`), **`r96 (0x60) → CMDBUF_ERROR`** — a
clean r95-OK / r96-FAULT edge. **Decisive no-mod-64 proof:** under mod-64, r96 would alias r32
(which reads 0 → OK); instead it **hard-faults**, so 96 is a hard silicon boundary, not a wrapped
6-bit field. IDENTICAL to A18 (RT-7).

**1c. ALU out-of-file reads 0 / no aliasing** (`alu_srcA.py`, `raw/1c_alu_srcA.txt`). Splicing a
`falu2` operand reg to r32/r63/r95/r96/r127 (uninitialized) → reads 0, STATUS OK, no fault.
⚠ **Caveat (encoding, not machine model):** the 6-byte *compact* `falu2` operand high bit
(byte+1/byte+3 bit7) is a **modifier**, not a reg bit, so the compact form cannot reach r64+ as a
distinct register (r64→aliases r0 *in the compact encoding*). This is a known compaction artifact
(the compiler uses the 8-byte extended form for high registers), **not** register-file aliasing —
the decisive no-alias evidence is the memory-index fault (1b) and the functional copy (below).

**1 functional no-alias proof** (`copy96.py`/`spill_check.py`, `raw/1_copy96_noalias.txt`,
`raw/4a_spill_check.txt`): cyclic-FMA kernels that reserve up to 96 distinct GPRs (runtime-1 trip
count → pure per-thread copy). If r64 aliased r0 the copy would corrupt; instead **all K values copy
exactly** at f0=96 (K=60..256, incl. heavy spill 256/1040 B) — 96 distinct registers, no aliasing.
Reproduces RT-7's "f0=96 runs correctly."

## 2 — 16-bit halves, 2 per GPR — IDENTICAL
`meta_sweep.py half` (`raw/2a_meta_half.txt`): **64 halves → f0=50**, **96 halves → f0=74** (exact
A18/RT-7 numbers; impossible if a half owned a full GPR). Half spills far later than float
(float K=104→spill, half K≤112 stays f0≤96).
**Low-half addressing** (`half_lowhalf.py`, `raw/2b_half_lowhalf.txt`): srcA raw bits `0x00003C00`
(float32≈0; low half `0x3C00`=half 1.0), srcB=100. 32-bit srcA → out=100; splicing the srcA size
bit (byte+1 bit0, `0x05→0x04`) → 16-bit reads the **low** halfword=1.0 → out=**101**. IDENTICAL.

## 3 — Uniform register file + both encodings (EMPHASIS ITEM) — IDENTICAL
`uniform.py` (`raw/3_uniform.txt`, `raw/3_uniA_dump.txt`, `raw/3_uniB_dump.txt`). Both forms appear
and are **byte-identical to the A18 (RT-7) examples**:
- `a+p.k` → **srcA form** `falu2_uni` `09 0d 14 01 80 c0`; select = **bit39 (byte+4 bit7)**.
- `p.k+a` → **srcB form** `falu2` `09 01 0c 0d 00 c2`; select = **byte+2 bit4 + byte+5 bit1**.

Both **read the RUNTIME uniform**: bind 7→+7, 55→+55, 1000→+1000 (out tracks it). Splicing the
select bit forces the operand to read the GPR (=0) → out=`a`: srcA clear bit39 (`0x16 0x80→0x00`),
srcB clear byte+5 bit1 (`0x17 0xc2→0xc0`) **or** set byte+2 bit4 (`0x14 0x0c→0x1c`) — all three
confirmed. Both encodings valid, one per operand position, exactly as A18.

## 4 — Spill + occupancy tier — IDENTICAL
**Spill** (`spill_check.py`, `raw/4a_spill_check.txt`): >96-live kernels spill to scratch (K=112→400
B … K=256→1040 B) and **still copy exactly** — spill computes correctly.
**Occupancy tier bit:** already M4-validated by **EXP-M4-09 / CMD-8** — the launch-descriptor cfg
word `0x100000b0000+0x00` is a **2-tier boolean** (`0x00080000`↔`0x00880000`, bit23), driven by
**peak register pressure** (not the field-0 count). That correction was measured on this same M4;
this experiment confirms the spill mechanism it sits on. IDENTICAL (per CMD-8).

## 5 — SR table (EMPHASIS ITEM) — IDENTICAL (all codes)
**Compute (HW-splice, `sr_splice.py`, `raw/5_sr_splice.txt`):** splicing `get_sr` byte1 (file off
0x01) makes the output become that SR's value, grid=128/tg=64:
`0xa0`→tpig 0..127 · `0xa4`→pos_in_tg 0..63 · `0xa7`→tidx 0..63 · `0x98`→threads_per_tg=64 ·
`0x9c`→tgroup_pos 0/1 · `0x82`→simd_lane 0..31 · `0x85`→simd_group 0/1 · `0xa8`→(bare)
threads_per_tg=64 (the RT-7 threadgroups_per_grid nuance). All match A18.
**Graphics (read-off, `raw/5_sr_dump.txt`):** compiled VS/FS `get_sr` byte1 = **vertex_id `0xdd`**,
**instance_id `0xd8`**, **front_facing `0xc5`**, **simd_is_helper `0x84`** — all IDENTICAL. vertex_id/
instance_id independently HW-re-confirmed by item 6 (step get_sr `dd`↔`d8`).

## 6 — Vertex attribute fetch = in-shader software — IDENTICAL
`attr_fetch.py` (`raw/6_attr_fetch.txt`): varying each `MTLVertexDescriptor` knob moves specific VS
bytes (fixed-function fetch would leave them invariant):
- stride 32→64: imad stride imm **@0xa** `8000→0001` (A18 exact)
- attr1 offset 16→12: 2nd-load offset **@0x27** `0402→8401` (A18 exact)
- fmt0 float3→uchar4Normalized: load width + inserted normalize/convert ALU (len 186→202)
- fmt1 float4→half4: load width + half→float converts (len 186→178)
- step perVertex→perInstance: index **get_sr @0x1 `dd→d8`** (vertex_id→instance_id) (A18 exact)

⟶ stride/offset/format/step compiled INTO the VS; attribute table supplies only the base pointer.
IDENTICAL to A18 (RT-7 / EXP-0031).

## 7 — Async completion = HW register interlock (no scoreboard) — IDENTICAL
`interlock.py` (`raw/7_interlock.txt`):
- **(A)** 8 *dependent* index loads (pointer chase) → **correct chained result** with **8
  device_load ops and 0 wait/scoreboard ops** in the compiled code. The consumer directly follows
  the load ⇒ the RAW hazard is enforced by a **HW register interlock**, not a software wait.
- **(B)** 20 *independent* loads summed **exactly** (out[0]=7030) with **0 wait ops** ⇒ >8 in flight,
  **no G13-style `AGX_MAX_PENDING=8` cap.**

No G13-style 2-byte `wait` / scoreboard-slot op exists on M4 (as on A18/G17P, EXP-0025). IDENTICAL.

## 8 — The two "inferred-identical, not re-run" cmdstream items — now HW-RUN on M4, IDENTICAL
**8a. u32 index opcode `0x61f4`** (`harness/dvar11 --idx32` under iotrace, `raw/8a_u32_index_opcode.txt`).
VDM control-stream BO (VA 0x18000). Same record, u16→u32:
`+0x6e opcode 0x61f2 → 0x61f4` · `+0x68 index-range sentinel 0x0000FFFF → 0xFFFFFFFF` ·
`+0x74 indexCount=3` · `+0x78 instanceCount=1` (unchanged). Matches A18 `docs/cmdstream/README.md` exactly.

**8b. Stage-boundary GPU timestamps** (`harness/dvar11 --ts`, `raw/8b_timestamps.txt`).
`sampleTimestamps` gives **cpu == gpu exactly** (102061486770958) ⇒ **timestampPeriod = 1.0** (same
ns clock). Stage-boundary sampling (render-pass `sampleBufferAttachments` start/endOfVertex/Fragment)
resolves **4 monotonic uint64-ns timestamps** (startVtx < endVtx < startFrag < endFrag). Format
(uint64 ns, period 1.0) and stage-boundary support IDENTICAL to A18.

---

## HW-validated vs read-off
- **HW-validated (dispatch/splice/render/capture observed):** 96 cap + copy correctness (1a,1); memory-index
  r95/r96 fault (1b); ALU out-of-file reads 0 (1c); halves 50/74 + low-half splice (2); both uniform
  encodings runtime-read + select splices (3); spill correctness (4a); all 7 compute SR splices (5);
  every attribute knob (6); interlock + no-wait (7); u32 opcode 0x61f4 + stage timestamps (8).
- **Read-off (compiler-emitted code, not per-value spliced):** graphics SR *codes* (dd/d8/c5/84) — dd/d8
  additionally HW-confirmed via the step test (6). Occupancy tier threshold = per EXP-M4-09/CMD-8 (peak
  pressure, not a fixed count) — unchanged, cited not re-measured.

## Clean-room status
Clean. Only our own MSL / our own compiled bytes / our own `__GPU_METADATA` / our own command-stream
BOs. No Apple binary disassembled. Did not edit `tools/agx-isa`, `docs/`, PROVENANCE, ROADMAP,
reviews/. Did not commit.
