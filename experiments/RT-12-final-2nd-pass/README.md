# RT-12 — 2nd overlapping red-team pass: cmdstream-2, machine-model/SR-ABI, tiling re-confirm

**Role:** independent 2nd-overlapping-pass verifier. Goal: give the single-pass clusters their
overlapping confirmation by **running falsification tests on real hardware** with **different
programs** than RT-6 (cmdstream-2), RT-7 (machine model), and RT-9 (tiling). Report CONFIRMED or
DISCREPANCY per section. Finding nothing = those clusters pass two clean passes.

Device: Apple A18 Pro / G17P, macOS 26.6 (25G5043d). **Reboots: 0. Faults: only the expected,
contained `CMDBUF_ERROR` from the deliberate r96 memory-index splice.**

**Clean-room:** DATA-TRACE (our own BOs via read-only `tools/iotrace`, arm64e) + OWN-SHADER (our
own MSL, compiled at runtime; our own compiled bytes spliced/run) + HW-PROBE. No Apple binary was
disassembled or introspected. See `../../CLAUDE.md`.

## Scope (as dispatched)
- **(A) cmdstream-2** (`docs/cmdstream/README.md`): indirect opcodes `0x6404`/`0x6432` + args-ptr
  @+0x68/+0x6c (hi-then-lo); ICB cmd-count @+0x04 + mesh-in-ICB `0x70000600`; occlusion mode bit14
  @0x58000+0x8c + offset<<14 @+0xa0; timestamp stage-boundary-only; viewport-count
  `((n−1)<<12)|0x0C00` + clip-mask bits[7:0] + restart cut-index.
- **(B) machine-model + SR/ABI** (`docs/isa/README.md`): 96-GPR hard boundary (r96+ faults as
  index / reads 0 as source); halves 2-per-GPR; SR table (byte1 splice for thread_position `0xa0`,
  simd_lane `0x82`, vertex_id `0xdd`, instance_id `0xd8`, front_facing `0xc5`); BOTH uniform-source
  encodings (srcB byte+2bit4+byte+5bit1 AND srcA bit39); vertex fetch = in-shader software.
- **(C) tiling** (`docs/tiling/README.md` §1.1/§1.4 — RT-9's fix): 2 NEW non-pow2-tile widths
  (448×448 bpp4, 704×256 bpp8): `cols=ceil(W/T)` + allocation padded to multiple-of-T
  (BO size = padW·padH·bpp, NOT nextpow2).

## Method (change-one-parameter / splice-and-observe / known-pattern-in)
- **(A)** Own Metal draws in single-feature modes → captured registered GPU BOs under read-only
  `iotrace` → byte-diff / field-read at the documented fw-context offsets (VDM `0x18000`, 3D-state
  pool `0x58000`, viewport/tiling ctx `0x68000`, attachment `0x10000100000`). Occlusion counters
  and timestamps additionally read back from Shared buffers.
- **(B)** Own MSL → `shdump` extract `_agc.main` bytes → `agx-isa` tokenize to locate fields →
  `agxtest.py` splice-and-run on the real GPU, reading back outputs. `__GPU_METADATA` GPR footprint
  read from our own archive (OWN-SHADER).
- **(C)** GPU-write a coordinate-marker pattern into a texture in the optimal (twiddled, writable→
  uncompressed) layout; `heapTextureSizeAndAlignWithDescriptor:` for the driver's own allocation
  size (API, no iotrace); read the raw backing bytes via `iotrace` and reconstruct every sampled
  texel under BOTH `cols=ceil(W/T)` (tile-multiple) and `cols=nextpow2(W)/T` models → 0-mismatch is
  the confirmed model.

## Harness inventory (all our own; different programs than RT-6/7/9)
| file | part | role |
|---|---|---|
| `c_tiling.m` / `c_analyze.py` | C | marker-write texture + heap-size + GF(2)-style layout reconstruction (448²/704×256, new sizes) |
| `a_draw.m` | A | direct/indirect/idx(in)direct draw (6-vtx quad, RGBA8) → indirect opcodes + args ptr |
| `a_icb.m` | A | ICB of N draws / N mesh cmds (N∈{4,5,3}) → cmd-count @+0x04, mesh `0x70000600` |
| `a_occ.m` | A | occlusion bool/count @ byte offsets 24/40 → mode bit14, offset<<14, counter readback |
| `a_ts.m` | A | timestamp period + sampling-point support + dispatch-vs-stage sample |
| `a_geo.m` | A | viewports (2/8/16) / clip (5) / point / vpidx / restart(u16/u32 list+strip) |
| `a_reg.py` | A | read a byte region / scan opcodes in a captured fw-context BO |
| `b1_load.metal` / `b1_add.metal` | B | memory-index & ALU-source register-boundary splices |
| `b2_half.py` | B | half-vs-float `__GPU_METADATA` GPR-footprint comparison |
| `b3_sr.metal` | B | compute `get_sr` byte1 splice (SR table) |
| `b4a.metal` / `b4b.metal` | B | uniform-as-srcA (`falu2_uni`) and uniform-as-srcB forms |
| `b5_attr.m` | B | `[[stage_in]]` VS compiled against a configurable `MTLVertexDescriptor` |
| `b5_vs.metal` | B | vertex_id / instance_id / front_facing `get_sr` read-off |

## Result
**All three sections CONFIRMED — no discrepancies.** See `RESULTS.md`. Raw:
`raw/RT12_RAW_EVIDENCE_AC.txt`, `raw/RT12_RAW_EVIDENCE_B.txt`, `raw/bk/` (our MSL + extracted hex).

## Clean-room statement
Only our own MSL was compiled; only our own compiled bytes / our own archive metadata were
inspected/spliced/executed; `iotrace` logged only DATA (BO bytes) at the userspace↔kernel boundary.
No Apple binary disassembled/introspected (the indirect-dispatch grid-setup helper and blend
microprograms are located-but-never-disassembled per CLAUDE.md rule 5). All work under
`~/cleanroom_work/rt12/`; text-only artifacts pulled back. Did **not** edit `docs/`,
`tools/agx-isa/`, `tools/iotrace/`, PROVENANCE, or reviews. Did **not** commit.
