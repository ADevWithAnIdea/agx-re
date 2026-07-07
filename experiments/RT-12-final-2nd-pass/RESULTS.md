# RT-12 RESULTS — 2nd overlapping pass (cmdstream-2 · machine-model/SR-ABI · tiling re-confirm)

Device: A18 Pro / G17P, macOS 26.6 (25G5043d). **0 reboots.** Only fault = the intended contained
`CMDBUF_ERROR` from the r96 memory-index splice. Different programs/sizes than RT-6/RT-7/RT-9.
`le32` = little-endian u32 at the stated fw-context offset. All draws/dispatches `status=4`.

## TL;DR verdicts
| section | claim | verdict |
|---|---|---|
| **A** | indirect opcodes `0x6404`/`0x6432` + args-ptr hi@+0x68/lo@+0x6c (idx: +0x74/+0x78) | **CONFIRMED** |
| **A** | ICB cmd-count @0x18000+0x04 + mesh-in-ICB `0x70000600` | **CONFIRMED** |
| **A** | occlusion mode bit14 @0x58000+0x8c + per-draw offset<<14 @+0xa0 | **CONFIRMED** |
| **A** | timestamp = uint64 ns / period 1.0 / stage-boundary-only | **CONFIRMED** |
| **A** | viewport-count `((n−1)<<12)\|0x0C00` + clip-mask bits[7:0] + restart cut-index | **CONFIRMED** |
| **B** | 96-GPR hard boundary (r96+ faults as index / reads 0 as source; no mod-64 alias) | **CONFIRMED** |
| **B** | 16-bit halves packed 2-per-GPR | **CONFIRMED** |
| **B** | SR table (`0xa0`/`0x82`/`0xdd`/`0xd8`/`0xc5`) | **CONFIRMED** |
| **B** | BOTH uniform-source encodings (srcB byte+2bit4+byte+5bit1; srcA bit39) | **CONFIRMED** |
| **B** | vertex attribute fetch = in-shader software | **CONFIRMED** |
| **C** | `cols=ceil(W/T)` + tile-multiple padding (BO size = padW·padH·bpp, NOT nextpow2) | **CONFIRMED** |

**No discrepancies found.** The two clusters (cmdstream-2, machine-model) now pass two clean
independent passes, and RT-9's driver-breaking tiling correction is independently re-upheld.

---

## Section A — cmdstream-2

### A1. Indirect draw opcodes + args pointer — CONFIRMED
6-vertex quad, RGBA8; my argBuf VA=`0x1000001b900`, idxArgBuf=`0x1000001ba00`, idxBuf=`0x1000001b800`.
VDM `0x18000`:
- **direct**: `+0x64`=`0x61c40600`, `+0x68`=vtxCount **6** (my quad; RT-6 used 3 — the count field tracks), `+0x6c`=instCount 1.
- **indirect**: opcode **`0x64040600`** (`0x61c4→0x6404`); `+0x68`=**argHi 0x100**, `+0x6c`=**argLo 0x1b900** (=my argBuf) — stored **high32-then-low32**. Opcode scan: `0x6404` present, `0x61c4` absent.
- **idxdirect**: shifted record `0x40000001`@+0x64, cut `0x0000ffff`@+0x68, opcode `0x61f2`@+0x6c, idxVA `0x1b800`@+0x70, idxCnt 6@+0x74, instCnt 1@+0x78.
- **idxindirect**: opcode **`0x64320600`** (`0x61f2→0x6432`); idxVA `0x1b800` inline@+0x70; **argHi 0x100@+0x74, argLo 0x1ba00@+0x78** (=my idxArgBuf). Opcode scan: `0x6432` present.

### A2. Full ICB command-count + mesh-in-ICB — CONFIRMED
- draw N=4 → `0x18000+0x04`=**4**, exactly **4** `0x61c4` records (0x1aa/0x1ea/0x22a/0x26a, 0x40 stride).
- draw N=5 → `+0x04`=**5**, exactly **5** `0x61c4` records.
- **mesh N=3** → `+0x04`=**3**, exactly **3** `0x70000600` mesh-grid-dispatch records (0x1c4/0x22c/0x294). Mesh-in-ICB lowers to `0x70000600` as documented.

### A3. Occlusion query — CONFIRMED
- **mode @0x58000+0x8c**: none=`0x00040200`, bool=`0x0004c200`, count=`0x00048200`. bool⊕count = `0x00004000` = **bit14** ⇒ Boolean=1 / Counting=0 (exact).
- **offset @0x58000+0xa0 = byteOffset<<14**: off 24→`0x00060000` (=24<<14), off 40→`0x000a0000` (=40<<14). New offsets vs RT-6's 0/8/16/4096.
- **counter readback**: bool→visBuf[off/8]=**1**; count→**4096** (=64×64 passed samples), exact, at both offsets; none→0.
- result-buffer base ptr @`0x10000100000+0x00` = LE u64 visBuf VA (lo `0x18800`, hi `0x100`).

### A4. GPU timestamps — CONFIRMED
- `sampleTimestamps:gpuTimestamp:` returns cpu==gpu; over ~70 ms dCPU==dGPU ⇒ **ratio 1.000000** ⇒ uint64 **nanoseconds, timestampPeriod 1.0**.
- `supportsCounterSampling`: **stageBoundary=1, drawBoundary=0, dispatchBoundary=0, blitBoundary=0**.
- compute **dispatch-boundary** sample → resolves **all-zero** `TS[0..3]=0` (unsupported).
- render **stage-boundary** sample → real ns (`TS[0]=…892875, TS[1]=…899916`, **vtxDelta=7041 ns**).
  *(Minor observation, not a doc conflict: the fragment-stage indices `TS[2..3]` read 0 in this
  single-encoder config; the documented claim — stage-boundary supported vs dispatch/draw
  unsupported — is confirmed by the nonzero vertex-stage delta and the all-zero dispatch sample.)*

### A5. Geometry-output — CONFIRMED (new counts vs RT-6)
- **viewport count @0x68000+0x900 = ((n−1)<<12)|0x0C00**: base `0x0C00`, vp2 `0x1C00`, vp8 `0x7C00`, vp16 `0xFC00` (max 16). Exact.
- **PPP output-select @0x58000+0x20**: clip5 → `0x0001001f` (**bits[7:0]=0x1f** = 5 clip planes); point → `0x00050000` (**bit18**); vpidx → `0x00090000` (**bit19**).
- **restart cut @0x18000+0x68 = all-ones of index width** + opcode @+0x6c:
  u16 list `0x0000ffff` / `0x61f2`; **u32 list `0xffffffff` / `0x61f4`**; u16 strip `0x0000ffff` / `0x61f3` (strip bit0); u32 strip `0xffffffff` / `0x61f5` (u32 bit1|strip bit0). Cut written for **both list and strip**; no separate enable bit.

> **Method note (transparency):** an early geometry run showed vp8/clip5/restart *not* moving —
> traced to (1) unquoted `$args` word-splitting under the device's zsh, and (2) stale BO files left
> in reused iotrace dump dirs (the fw-context BO's CPU addr varies per run → both old and new
> `.hex` coexist; the extractor loaded the alphabetically-first, stale one). Re-running with
> explicit args into fresh dump dirs reproduced every documented value exactly. **Not a doc issue.**

---

## Section B — machine model + SR/ABI

### B1. 96-GPR hard boundary — CONFIRMED
Kernel `o[i]=a[i]` — the `device_load` index register is byte+5 (file offset 0x09).
- **memory-index splice**: r94/r95 → **STATUS OK** (uninitialised in-file reg reads 0 ⇒ `a[0]=100`); **r96/r97 → hard `CMDBUF_ERROR`**. Clean r95/r96 boundary. This also **disproves a 64-entry mod-64-aliased file**: if r96 aliased r32 it would not fault as an index.
- **ALU-source splice** (fadd srcA, kernel `o[i]=a[i]+b[i]`, srcB=r0=a=[10..80]): r95/r96/r127 → read **0** (o=a, no fault). r0/r2 read the live loaded values.
- **no mod-64 aliasing**: srcA=r64/r66 read physical copies of a/b, **but srcA=r65 read `[10,0,0,…]` — NOT r1's thread-index `[0..7]`**, and r67/r33/r63 read 0. A genuine mod-64 alias would make r65≡r1 (returning the thread index); it does not ⇒ no logical mod-64 aliasing (the r64/r66 hits are physical-slot coincidence, consistent with RT-7's "r64/r66 read live values").

### B2. Halves packed 2-per-GPR — CONFIRMED
Independent bank-of-K-madd kernel, `half` vs `float`, comparing `__GPU_METADATA` field-0 GPR count:
K=24/32/48/64 → float f0 33/43/63/83, half f0 20/26/38/**50**, ratio ≈**0.60**. **64 halves → f0=50**
(exactly RT-7/EXP-0020's number) — impossible if a half owned a full GPR (would need ≥64).

### B3. SR table — CONFIRMED
- **compute HW splice** (`get_sr` byte1, grid 64 / tg 32): baseline `0xa0` → `[0,1,…,63]` (**thread_position_in_grid**); splice `0x82` → lane ids `[0..31]` in the first simdgroup (**simd_lane_id**). *(A second simdgroup overwrites o[0..31] because `o[i]=i` reuses the SR value as the store index — the value 0..31 in o[0..31] is nonetheless decisive.)*
- **graphics read-off** (compiler's own `get_sr` byte1): vertex_id → **`0xdd`**, instance_id → **`0xd8`**, front_facing (FS) → **`0xc5`**. All match the doc table exactly; the step-function test in B5 independently re-confirms `0xdd`↔`0xd8`.

### B4. BOTH uniform-source encodings — CONFIRMED
The compiler emits both forms (my two kernels reproduce the doc's exact example bytes):
- **`a[i]+p.k`** (fast-math) → **srcA form `falu2_uni` `09 0d 14 01 80 c0`**. Runtime uniform read (p.k 17→+17, 100→+100). Splice **bit39** (byte+4 bit7 `0x80→0x00`) → GPR read (0), o=a. ⇒ select = bit39.
- **`p.k+a[i]`** → **srcB form `falu2` `09 01 0c 0d 00 c2`**. Runtime uniform read. Splice **byte+2 bit4** (`0x0c→0x1c`) → o=a; splice **byte+5 bit1** (`0xc2→0xc0`) → o=a. ⇒ select = byte+2 bit4 + byte+5 bit1 (toggling either).

Both forms HW-read the runtime uniform; both select-bit accounts hold. (Confirms the RT-7 correction
that the byte+2-bit4/byte+5-bit1 form is the valid **uniform-srcB** encoding, not "wrong/superseded".)

### B5. Vertex attribute fetch = in-shader software — CONFIRMED
Fixed `[[stage_in]]` VS compiled against a varied `MTLVertexDescriptor`; each knob moves specific
VS bytes (impossible if fetch were fixed-function):
| knob | VS delta |
|---|---|
| stride 32→64 | imad stride immediate `…8000`→`…0001` (len 372→372) |
| attr1 offset 16→12 | 2nd-load offset `1704024022`→`1784014022` |
| a0 float3→uchar4Normalized | +normalize/convert ALU, len 372→**404** |
| a1 float4→half4 | half loads/converts, len 372→**356** |
| step perVertex→perInstance | leading `get_sr` **`0cdd`→`0cd8`** (vertex_id→instance_id) |

⇒ stride/offset/format/step are compiled **into** the VS; the attribute table supplies only the base pointer.

---

## Section C — tiling (RT-9 fix re-confirm)

Two NEW non-pow2-tile widths; both independent evidences agree with the **tile-multiple** model and
reject **nextpow2**:

| case | bpp | T | cols=ceil(W/T) | `heapTextureSizeAndAlign` | tilemult | nextpow2 | GF(2) reconstruction |
|---|---|---|---|---|---|---|---|
| **448×448 r32uint** | 4 | 64 | **7** | **0xc4000** | 0xc4000 ✓ | 0x100000 ✗ | cols=7: **676/676 match, 0 mismatch**; cols=8: 484 mismatch |
| **704×256 rg32uint** | 8 | 32 | **22** | **0x160000** | 0x160000 ✓ | 0x200000 ✗ | cols=22: **702/702 match, 0 mismatch**; cols=32: 384 mismatch |

- `heapTextureSizeAndAlignWithDescriptor:` returns exactly `padW·padH·bpp` (448·448·4=`0xc4000`;
  704·256·8=`0x160000`), **not** the nextpow2 size (`0x100000` / `0x200000`).
- The registered backing BO size (via iotrace) matches tile-multiple; every sampled texel
  reconstructs at `element=(ty·ceil(W/T)+tx)·T² + morton_D(xl,yl)` with **0 mismatch**, while the
  retracted `cols=nextpow2(W)/T` model mismatches hundreds of texels.

⇒ RT-9's correction (`cols=ceil(W/T)`, padding to a multiple of T, `allocationBytes=padW·padH·bpp`)
**holds on both new NPOT-tile sizes.**

---

## HW-validated vs read-off
- **HW-validated** (dispatch/splice/render/known-pattern observed): all of A (BO captures + counter/
  timestamp readback), B1/B2/B4/B5, C (heap-size API + raw-layout reconstruction), and the B3
  compute splices (`0xa0`,`0x82`).
- **Read-off from our own compiler output** (not per-value splice-in-render): B3 graphics SR codes
  `0xdd`/`0xd8`/`0xc5` (the `0xdd`↔`0xd8` pair is additionally splice-confirmed by B5's step test).

## Clean-room status
Clean. OWN-SHADER + DATA-TRACE + HW-PROBE only; no Apple binary disassembled/introspected. Reused
existing tools (`iotrace` read-only arm64e, `shdump`/`agxparse`/`agxrun`/`agxtest`/`agxisa`). Did not
edit `docs/`, `tools/agx-isa/`, `tools/iotrace/`, PROVENANCE, or reviews. Did not commit. `raw/` is
text only (our MSL + extracted hex + evidence logs); `.bin` archives stayed on-device.
