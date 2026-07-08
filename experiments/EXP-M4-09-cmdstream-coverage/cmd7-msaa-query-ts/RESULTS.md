# CMD-7 — MSAA / occlusion / timestamp parameter breadth (LOCAL Apple M4)

**Device:** Apple M4 (10 GPU cores, Metal 4), this host. **NOT the A18 Pro.** All findings
below are M4 observations; where they match the A18-derived doc claims (from EXP-0021 / RT-4 /
EXP-0027) that is a **cross-confirmation**, and any divergence is flagged **A18-CROSS-CONFIRM**.

**Method / clean-room category:** OWN-SHADER (our own runtime-compiled MSL) + HW-PROBE
(readback, capability queries) + DATA-TRACE (`iotrace.dylib` read-only BO snapshots, byte-diff
with `bodiff.py`). No Apple binary was disassembled or inspected. Harnesses: `sctest.m`,
`pipe8.m`, `ovar.m`, `qvar.m` (locally enlarged visibility buffer + offset-aware readback),
`tvar.m`. Reproduce with `./run.sh`; raw under `caps/`.

Zero GPU wedges / reboots. Every render/compute submit returned `status=4` (Completed).

---

## (a) MSAA sample count — 8× is Metal-REJECTED; +0x24 encoding for 1×/2×/4× confirmed

### supportsTextureSampleCount (HW-PROBE, `caps/sctest.out`)
| N | `[dev supportsTextureSampleCount:N]` |
|---|---|
| 1 | **1 (YES)** |
| 2 | **1 (YES)** |
| 4 | **1 (YES)** |
| 8 | **0 (NO)** |
| 16 | 0 (NO) |
| 32 | 0 (NO) |

### How 8× fails (two independent rejection paths, HW-PROBE)
- **Texture:** creating a `MTLTextureType2DMultisample` texture with `sampleCount=8` triggers a
  **hard Metal validation assertion** and aborts the process:
  `-[MTLTextureDescriptorInternal validateWithDevice:] MTLTextureDescriptor sampleCount (8) is not
  supported by device.` (2× and 4× textures create fine → `sc=2` / `sc=4`.)
- **Pipeline:** `newRenderPipelineStateWithDescriptor:error:` with `rasterSampleCount=8` returns
  **nil** with `NSError` = `rasterSampleCount (8) is not supported by device.` (graceful, no abort;
  `caps/pipe8.out`). 1×/2×/4× build OK.

⇒ **8× MSAA cannot be expressed at all** on M4 — no command stream is producible, so there is no
`+0x24` encoding for it to capture. **CONFIRMS** the doc's "8× unsupported" and upgrades it from
"not shown to be Metal-rejected" to **Metal-rejected at both the texture and pipeline layer**.

### `+0x24` sample-count / MSAA-store encoding for the accepted counts (DATA-TRACE)
The color-attachment descriptor is a 0x20-byte **header** followed by 0x20-byte **segments**:
a **LOAD segment** (byte0 `0x02`) and, when MSAA/MultisampleResolve is used, a **RENDER/STORE
segment** (byte0 `0x24`). Within a segment: format byte at seg+0x02 (`0x0a`=BGRA8Unorm), and the
**config/sample word at seg+0x04** — this is the doc's "`+0x24`" (the doc numbers a segment's
word0 as `+0x20`, so its config word = `+0x24`). The **sample-count / MSAA-store bits live in the
RENDER/STORE segment's config word.**

Non-MSAA (1×) keeps the descriptor at `0x10000110000`; **2×/4× relocate it into the tiler heap
`0x10000018200`** (confirms doc "relocates on MRT≥2 OR MSAA OR memoryless"). Config/sample word:

| count | descriptor location | STORE-seg config word | high byte | bit27 (MSAA-store) | bit24 (count LSB) |
|---|---|---|---|---|---|
| **1×** | `0x10000110000` (LOAD seg only) | `0x0000fc03` | `0x00` | 0 | 0 |
| **2×** | `0x10000018200` STORE seg @+0x40 → word @+0x44 | `0x0800fc03` | `0x08` | **1** | 0 |
| **4×** | `0x10000018200` STORE seg @+0x40 → word @+0x44 | `0x0900fc03` | `0x09` | **1** | **1** |

`bodiff caps/msaa2 caps/msaa4` isolates a **single word** flip at `0x10000018200+0x44`
(`0x0800fc03 → 0x0900fc03`, Δ = bit24). **CONFIRMS** doc exactly: msaa2 `0x08…`, msaa4 `0x09…`,
**bit24 = sample-count LSB, bit27 = MSAA-store**.

- **Nuance to fold into docs:** the MSAA bits are in the **STORE segment** config word, *not* the
  LOAD segment's `+0x24` (the LOAD segment config stays `0x0000fc03` for all of 1×/2×/4×). A driver
  emitting the descriptor must place `0x08/0x09` in the resolve/store segment.
- **Extrapolation (untestable — Metal-rejected):** the count field is `bits[25:24]` reading
  1×→0, 2×→0? No — 1× has no STORE seg; the *field* observed is 2×→0, 4×→1 in bit24, i.e. the
  count code = `log2(N)-1`. A hypothetical 8× would be count-code 2 → **bit25 set → `0x0a00fc03`**.
  This CANNOT be verified: 8× resources are rejected before any stream is built. Recorded as an
  inferred extrapolation only.
- **A18-CROSS-CONFIRM:** M4 matches the A18 doc values (`0x08`/`0x09`, bit24/bit27). Worth a
  one-line A18 re-check that `supportsTextureSampleCount:8` is likewise `NO` (Apple-GPU-wide cap
  at 4×, but not independently re-measured on A18 here).

---

## (b) Occlusion query — offset = byteOffset<<14 confirmed across 7 offsets; mode bit14 confirmed

Harness writes a full-screen triangle over 64×64 → **4096** passing samples; visibility buffer
poisoned with `0xdeadbeef000000xx` so any write is unmistakable. `qvar` reads back the u64 at the
exact `offset/8` slot (my local edit; upstream qvar only read slots 0-3 / a 256-byte buffer).

### Field encoding in the FF/tiler pool BO `0x10000058000` (DATA-TRACE)
| capture | `+0x8c` | bit14 (mode) | `+0xa0` (observed) | `byteOffset<<14` (expected) | match |
|---|---|---|---|---|---|
| count off=0    | `0x00048200` | 0 | `0x00000000` | `0x00000000` | ✅ |
| count off=8    | `0x00048200` | 0 | `0x00020000` | `0x00020000` | ✅ |
| count off=16   | `0x00048200` | 0 | `0x00040000` | `0x00040000` | ✅ |
| count off=64   | `0x00048200` | 0 | `0x00100000` | `0x00100000` | ✅ |
| count off=256  | `0x00048200` | 0 | `0x00400000` | `0x00400000` | ✅ |
| count off=1024 | `0x00048200` | 0 | `0x01000000` | `0x01000000` | ✅ |
| count off=4096 | `0x00048200` | 0 | `0x04000000` | `0x04000000` | ✅ |
| **bool** off=0 | `0x0004c200` | **1** | `0x00000000` | `0x00000000` | ✅ |
| **bool** off=8 | `0x0004c200` | **1** | `0x00020000` | `0x00020000` | ✅ |

- **Offset field:** `0x10000058000+0xa0 = byteOffset<<14`, verified exactly for **all 7 counting
  offsets (0 → 4096)**. It is a **standalone 32-bit word** — the neighbor `+0xa4` is constant
  `0x02000048` across every offset (no high-word spill). Implication for drivers: a 32-bit
  `byteOffset<<14` field ⇒ representable byteOffset up to ~`2^18` before overflow (Metal requires
  byteOffset 8-aligned). **CONFIRMS** doc.
- **Mode bit:** `0x10000058000+0x8c` **bit14 (0x00004000)**: Boolean → word `0x0004c200` (bit14=1),
  Counting → `0x00048200` (bit14=0). Single-bit difference. **CONFIRMS** doc (Boolean=1 / Counting=0).
- **Tiler visibility-ctx mirror** `0x10000258000+0x00` tracks the offset as **`byteOffset>>2`**
  (off=8→`0x2`, off=4096→`0x400`). (Doc says "also mirrored in the tiler visibility-ctx"; the
  mirror scale is `>>2`, i.e. a 32-bit-word index, not the `<<14` of the `+0xa0` field.)
- **HW accumulation proof (readback):** at *every* offset, COUNTING wrote **4096** to slot
  `off/8` and left slot 0 untouched (`0`); BOOLEAN wrote **1**; upper 32 poison bits cleared ⇒
  64-bit writes. So the HW genuinely accumulates the passed-sample count at the user-chosen offset.

**A18-CROSS-CONFIRM:** M4 mode words (`0x0004c200`/`0x00048200`) and `<<14` offset law are
**identical** to the A18 EXP-0027 values — strong cross-confirmation; no divergence found.

---

## (c) GPU timestamps — uint64 ns, period 1.0; stage-boundary works, dispatch/draw read zero

(HW-PROBE via public `MTLCounterSampleBuffer` / `sampleTimestamps:`; `caps/tv_*.out`.)

- **Counter set:** exactly one — name `timestamp`, single counter `GPUTimestamp`.
- **Period / format:** `[dev sampleTimestamps:cpu gpuTimestamp:gpu]` returns **cpu == gpu on every
  call** (e.g. `95278779053500 == 95278779053500`); across a ~55 ms sleep, `dCPU == dGPU` →
  **`gpu_ticks_per_cpu_ns = 1.000000`, `ns_per_gpu_tick = 1.000000`**. ⇒ **GPU timestamp = uint64
  nanoseconds, timestampPeriod = 1.0 ns/tick**, in the same mach-ns domain as the CPU clock.
  **CONFIRMS** doc.
- **Supported sampling points** (`supportsCounterSampling:`): **dispatchBoundary=0, drawBoundary=0,
  stageBoundary=1**. Only render-pass **stage-boundary** sampling is available. **CONFIRMS** doc.
- **Compute dispatch-boundary (csample):** unsupported (`CSAMPLE_UNSUPPORTED`); resolved
  `TS[0..3]` all **0**. This is the known limitation — **compute/blit/per-draw timestamp queries
  read zero and must be emulated** by a Vulkan/GL driver (`vkCmdWriteTimestamp` in compute).
- **Render stage-boundary (rsample):** **works.** Resolved (start/end vertex, start/end fragment):
  `TS[0]=95279079970208`, `TS[1]=…974666` (Δvtx **4458 ns**), `TS[2]=…978875`,
  `TS[3]=…985416` (Δ0→3 **15208 ns**). Monotone, physically sane for a 64×64 triangle, same ns
  domain as `sampleTimestamps`. u64, 8-byte stride, one per sample index.

**A18-CROSS-CONFIRM:** M4 matches the A18 doc on every point (ns/period, sampling-point support,
dispatch/draw-zero limitation). No divergence.

---

## Verdict per doc claim
| doc claim | result |
|---|---|
| (a) MSAA 2×/4× only; `+0x24` msaa2 `0x08…` / msaa4 `0x09…`; bit24=count LSB, bit27=MSAA-store | **CONFIRMED** (M4). Encoding word exact. |
| (a) "8× unsupported" (not shown Metal-rejected) | **CONFIRMED + STRENGTHENED**: `supportsTextureSampleCount:8=NO`; texture=hard assert, pipeline=nil+error. |
| (a) config/sample word location | **REFINED**: MSAA bits are in the **STORE segment** config word (seg+0x04), not the LOAD segment; descriptor relocates to `0x10000018200` under MSAA. |
| (b) mode = bit14 of `0x58000+0x8c` (Bool=1/Count=0) | **CONFIRMED** (`0x0004c200`/`0x00048200`). |
| (b) offset = `0x58000+0xa0 = byteOffset<<14` | **CONFIRMED across 7 offsets 0→4096**; standalone 32-bit field. |
| (c) uint64 ns, period 1.0 (cpu==gpu) | **CONFIRMED**. |
| (c) stage-boundary only; dispatch/draw read zero | **CONFIRMED**. |

**No contradictions with the A18 doc were found on M4.** The only new work items are doc-precision
refinements (STORE-segment location of the MSAA bits; tiler mirror scale `>>2`) and the flagged
A18 one-line re-check that `supportsTextureSampleCount:8` is also NO there.

## Deliverables
`sctest.m` `pipe8.m` `ovar.m` `qvar.m` (edited) `tvar.m` `iotrace.c` `bodiff.py`; `run.sh`;
`caps/` (per-run `*.out` + per-BO `*.hex` DATA-TRACE snapshots, text only); this `RESULTS.md`.
