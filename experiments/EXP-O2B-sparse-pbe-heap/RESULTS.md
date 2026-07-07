# EXP-O2B Results — sparse / PBE / 32-bit-float-filtering / bindless sampler-heap (A18 Pro / G17P)

**TL;DR.** Four objective-2 resource features decoded on A18 Pro / G17P / macOS 26.6 by
change-one-Metal-parameter DATA-TRACE of our own compute dispatches (`tools/iotrace`), plus
HW-PROBE readback. (1) **Sparse** textures carry a **sparse-tier flag** in the 32-byte texture
descriptor — `byte0` hi-nibble `bit5→bit4` **and** `word1` bits[28:29] — but **tile residency is
NOT in the descriptor** (map vs unmap byte-identical): residency lives in the GPU page table
(kernel/firmware-managed). **Placement-heap** textures are **descriptor-transparent** (only the
base/aux VA points into the heap). (2) **Render-target / PBE usability is NOT a bit in the sampled
texture descriptor** — `ShaderRead` vs `ShaderRead|RenderTarget` is byte-identical; render-target
state is expressed structurally by the attachment path (EXP-0021). (3) **32-bit float filtering is
unconditional / no special encoding** — a linear-filtered r32float sample uses the ordinary sampler
magFilter/minFilter bits and interpolates correctly (HW-validated). (4) **Bindless sampler heap** =
a tightly-packed **array of 8-byte `gpuResourceID`s** (stride 8; each ID a small integer index into
a device-global sampler table of capacity 500000); a shader-computed index selects the right
sampler (HW-validated). Every finding is **[HW]** (a dispatch confirmed it / a clean byte-diff) or
**[inf]** (inferred). Zero GPU wedges/reboots.

Word convention (EXP-0015): the 32-byte texture descriptor lives at `argBO+0x14c0`; `wordN` =
32-bit LE word at descriptor byte `4N`; `byteN` = byte at offset N. Raw: `raw/key_descriptors.txt`,
`analysis/diff_*.txt`.

---

## Capability baseline (`raw/probe.txt`, HW-PROBE)
`sparseTileSizeInBytes = 16384` (16 KiB), `maxArgumentBufferSamplerCount = 500000`,
`supports32BitFloatFiltering = 1`, `argumentBuffersSupport = Tier2`.
**Sparse tile is always 16 KiB of texels**, dims scale with bpp:
rgba8 `64×64`, r32float `64×64`, rgba32float `32×32`, r8 `128×128` (all `×bpp = 16384`).
Sparse heap `MTLHeapTypeSparse`(=2), placement(=1), automatic(=0) all create; a placement 64×64
rgba8 texture reports `heapTextureSizeAndAlign size=16512 align=128`.

---

## 1. Sparse & placement-heap texture descriptors

### 1a. Sparse-tier flag — [HW], isolated three ways
256×256 rgba8, same size/usage, standalone vs sparse (`analysis/diff_sparse_heap.txt`):

| capture | word0 | word1 | word3 | word4 (aux VA>>4) |
|---|---|---|---|---|
| `std256` (rgba8 read) | `f6880a`**`22`** | `0`**`8`**`03fc0f` | `80000010` | `0000c000` |
| `sp256` (rgba8 read, sparse) | `f6880a`**`12`** | `3`**`8`**`03fc0f` | `80000010` | `00405880` |
| `std256_rw` (rgba8 rw) | `f6880a`**`22`** | `0`**`0`**`03fc0f` | `00000010` | `0` |
| `sp256_rw` (rgba8 rw, sparse) | `f6880a`**`12`** | `3`**`0`**`03fc0f` | `00000010` | `0` |
| `std256_r32f` (r32f read) | `628868`**`f9`** *(byte0 `f9`? see note)* | `0803fc0f` | `80000010` | `0000c000` |
| `sp256_r32f` (r32f read, sparse) | `528868f9` | `3803fc0f` | `80000010` | `00405880` |

*(byte order: the raw string `220a88f6…` is `byte0=22 byte1=0a byte2=88 byte3=f6`; r32float
byte0=`0x62`, sparse r32float byte0=`0x52`.)*

Two descriptor fields flag **sparse**, independent of format and of compression:
- **`byte0` (word0 low byte) hi-nibble:** non-sparse → sparse clears bit5 (`0x20`) and sets bit4
  (`0x10`): rgba8 `0x22→0x12`, r32float `0x62→0x52` (transform `(byte0 & ~0x20) | 0x10`). This is
  the same nibble EXP-0015 called "channel arrangement" and left un-bit-split — one of its bits is
  a layout/sparse-mode selector. Placement and standalone both keep bit5 (`0x22`), so this is
  **sparse-specific, not a generic heap flag**.
- **`word1` bits[28:29]** (`0x30000000`) **set for sparse** in both the compressed-read
  (`0x38…`=bits27+28+29) and uncompressed-rw (`0x30…`=bits28+29) cases; non-sparse never sets them
  (`0x08…` read, `0x00…` rw). `word1` bit27 (`0x08000000`) remains the **compression** flag,
  orthogonal.

Interpretation [inf]: sparse must use the fixed 64×64/128×128 tile granularity (16 KiB) rather than
the whole-texture Morton of `docs/tiling`, so the descriptor selects a distinct tile/layout mode.

### 1b. Tile residency is NOT in the descriptor — [HW]
`sp256` (no tiles mapped) vs `sp256_map` (one 64×64 tile mapped at origin via
`MTLResourceStateCommandEncoder updateTextureMapping:mode:Map`) produce a **byte-identical texture
descriptor** (`analysis/diff_sparse_heap.txt`: only the arg-BO VA/pointer addresses shift, the
`+0x00/+0x10` descriptor content is unchanged). ⇒ **per-tile residency is expressed in the GPU
page table, not the userspace descriptor** — mapping/unmapping tiles is a page-table population that
the command-stream BOs we capture do not carry. **Kernel/firmware-managed** (flag for
`kernel-interface.md`): the sparse mapping-table update is a `MTLResourceStateCommandEncoder`
submission whose effect lands in GPU VM page tables, not in a descriptor pointer.

### 1c. Sparse secondary (aux) VA — [HW presence, inf meaning]
Sparse ShaderRead textures **still enable lossless compression**: `word1` bit27, `word3` bit31, and
a `word4` secondary VA are all set (cleared by ShaderWrite, exactly like non-sparse — see §2c). But
the secondary-VA **placement differs**: non-sparse aux = `base + paddedImageBytes`
(`std256`: `word4−word2 = 0xc000−0x8000 = 0x4000` → `×16 = 0x40000` = 256×256×4 ✓), whereas sparse
aux = `base + 0x80` (`sp256`: `0x405880−0x405800 = 0x80` → `×16 = 0x800` = 256×256/128 = the aux
*size*, not the image). So the sparse secondary VA points to sparse-specific auxiliary/compression
metadata whose exact placement the descriptor alone does not explain — **not fully decoded**
(consistent with tile backing being allocated per-mapped-tile, kernel-managed).

### 1d. Placement heap = descriptor-transparent — [HW]
`plc256` (placement heap) vs `std256` (standalone), same fmt/size/usage: the only differences are
`word2/word3` base VA and `word4` aux VA (both pointing into the heap region); **every format /
swizzle / dim / flag byte is identical**, and the aux still follows `base + paddedImageBytes`
(`plc256`: base `0x4000`, aux `0x8000`, Δ `0x4000×16 = 256 KiB` ✓). ⇒ a driver emits a
placement-heap texture with the **identical descriptor** as a standalone one, only substituting the
heap-relative VA (`heapTextureSizeAndAlign` gives the byte offset; align 128 B). Automatic heaps
behave the same at descriptor level (residency via `useHeap:`, not a descriptor bit).

---

## 2. PBE / render-target usage flags

### 2a. RenderTarget is NOT a bit in the sampled texture descriptor — [HW]
4×4 rgba8 (below the compression threshold, so no aux confound), one `MTLTextureUsage` bit changed
(`analysis/diff_usage.txt`):

| usage | 32-byte descriptor |
|---|---|
| `ShaderRead` | `220a8836 000c0000 1058… …` |
| `ShaderRead \| RenderTarget` | **byte-identical** |
| `ShaderRead \| ShaderWrite` | **byte-identical** |
| `ShaderRead \| PixelFormatView` | **byte-identical** |

On a small texture **all four usages produce the identical 32-byte descriptor** — texture usage
(including RenderTarget/PBE-renderability) is **not encoded** in the descriptor Metal binds for
sampling. A texture's render-target usability is expressed **structurally**, only when it is bound
as an attachment: the **3D attachment descriptor / tiler geometry heap** of EXP-0021
(`0x10000110000` / `0x10000018200`) carries the render-target state (packed pixel-format word,
sample count `+0x24`, tile-memory offset, load/store phase chain). Correlation to EXP-0021: that
"packed pixel-format word" (`0xf6880a22` rgba8, `0xf6888e02` rgba32f, …) is **exactly `word0`** of
this texture descriptor (format+swizzle) — the attachment path reuses the same texture-descriptor
`word0`; PBE-renderability adds no per-texture "is-renderable" bit, it is the surrounding
attachment record.

### 2b. PBE "renderable" ⇒ still compressible — [HW]
`ShaderRead|RenderTarget` at 256×256 is **byte-identical to `ShaderRead`** (still compressed:
`word1` bit27, `word3` bit31, `word4` aux present). So render targets get lossless compression;
render-target usage is orthogonal to (and does not disturb) the sampled descriptor.

### 2c. The only usage effect on the descriptor is compression eligibility — [HW]
At 256×256 (compressible), `ShaderWrite` **and** `PixelFormatView` each **clear** `word1` bit27,
`word3` bit31, and drop the `word4` aux VA (→ 0) — i.e. they **disable lossless compression**
(a read-write image, or a reinterpreted-format view, cannot use format-specific compression);
`RenderTarget` does not. This matches and extends `docs/tiling` §4.1 (compression needs *no
ShaderWrite*): **PixelFormatView also disqualifies compression.**

---

## 3. 32-bit float texture filtering — [HW-validated, unconditional]

`supports32BitFloatFiltering = YES`. A 2×2 r32float texture `[0,1;2,3]` sampled with a **linear**
sampler interpolates natively (`analysis/diff_floatfilter.txt`, `raw/desc_ff_r32_lin.txt`):

- **nearest** readback: `0,0,1,1 / 0,0,1,1 / 2,2,3,3 / 2,2,3,3` (quantized to texel values).
- **linear** readback: `0.000, 0.168, 0.832, 1.000 / 0.336, 0.504, … / … 2.832, 3.000` — smooth
  bilinear interpolation. **HW-proven filtering of a full 32-bit float format.**

**No special encoding.** nearest vs linear differ **only** in the ordinary sampler bits
(EXP-0015): sampler `byte2` `0x0e→0x8e` (magFilter bit23) and `byte3` `0x00→0x02` (minFilter
bit25). The **texture descriptor is byte-identical** between nearest and linear, and carries no
"filterable" flag. r32float uses format code `byte0=0x62 byte1=0x88` exactly as EXP-0015 documents.
⇒ On Apple9 a driver enables 32-bit float filtering **by doing nothing special** — the same sampler
filter bits and same texture descriptor as any other format; the hardware simply filters. (On a GPU
lacking the capability the same bits would fall back to nearest / undefined; here they filter.)

---

## 4. Bindless sampler-heap layout — [HW-validated]

`heaparg.m` builds an explicit argument buffer for MSL `struct SHeap { array<sampler,K> samps; };`
via `MTLArgumentEncoder`, with K sampler states of distinct configs, then dumps the buffer directly
(Shared) and runs `o[i] = t.sample(heap.samps[(idx+i)%K], center)` (`raw/heaparg_k{4,8,64}.txt`).

- **Each sampler slot is an 8-byte little-endian `gpuResourceID`.** `encodedLength = K×8`
  (K=4→32, K=8→64, K=64→512): **stride 8, slot k at offset k·8**. The stored value is the sampler's
  `MTLSamplerState.gpuResourceID` — a **small sequential integer** (first sampler created → `1`,
  next → `2`, …), i.e. an **index into a device-global sampler-state table** (not a VA, not a
  pointer, not an inlined descriptor). Capacity of that table = `maxArgumentBufferSamplerCount =
  500000`.
- **The argument-encoder output is byte-identical to a hand-written array of `gpuResourceID`s**
  (`ARGBUF` == `RIDBUF`), so a driver can build a bindless sampler heap by simply storing the 8-byte
  resource IDs contiguously — `setSamplerState:atIndex:` just writes the ID.
- **Shader indexing HW-validated.** A shader-computed index `j=(idx+i)%K` selects slot j: with the
  distinct samplers, nearest-mag slots return `3.000` and linear-mag slots return `1.500` at the 2×2
  center, in the exact `3,3,1.5,1.5` repeating pattern, for K=4/8/64. ⇒ the shader loads the 8-byte
  ID at `base + j·8` and uses it as the sampler-table index; dynamic (data-dependent) indices work.
- This **extends the Tier-2 argument buffer** of EXP-0011/0015. Note the two sampler encodings:
  the *Metal-auto* argument buffer (loose `sampler s [[sampler(0)]]`, EXP-0011) stores an **8-byte
  pointer** to an 8-byte sampler descriptor placed in the same BO; the *explicit bindless heap*
  (`supportArgumentBuffers` sampler in an argument-buffer array) stores the **8-byte resourceID
  index**. A bindless-capable driver uses the resourceID form.
- **Sampler states are not `MTLResource`s** — they need **no `useResource:`/residency** call (they
  live in the global table); passing one to `useResource:` faults `InvalidResource`. A driver just
  keeps the `MTLSamplerState` objects alive; their IDs stay valid.

---

## 5. HW-validated vs inferred; kernel-managed pieces

**HW-validated (dispatch or clean byte-diff):** sparse-tier flag (`byte0` nibble + `word1`[28:29]);
sparse residency absent from the descriptor (map==nomap); placement-heap descriptor transparency;
RenderTarget not a descriptor bit (usage matrix byte-identical); ShaderWrite/PixelFormatView disable
compression; 32-bit float linear filtering interpolates + its ordinary-sampler-bit encoding; bindless
sampler-heap stride-8 `gpuResourceID` layout + dynamic shader indexing; all capability values.

**Inferred / not fully decoded:** the internal bit-split of `byte0`'s hi-nibble (which exact bit is
the sparse/layout selector); the semantics of `word1` bits[28:29] beyond "sparse"; the sparse
secondary-VA (`word4`) placement/meaning (present like compression but at `base+auxSize`, not
`base+imageBytes`).

**Kernel/firmware-managed (→ `docs/kernel-interface.md`):**
- **Sparse tile residency / page-table population** — the `MTLResourceStateCommandEncoder`
  `updateTextureMapping` map/unmap changes GPU VM page tables, not any userspace descriptor
  (map==nomap descriptor). The kernel must own the sparse mapping table; userspace hands down a
  region + map/unmap intent.
- **Sparse per-tile backing allocation** (16 KiB tiles, `sparseTileSizeInBytes`) and the sparse aux
  metadata backing.
- (Corroborates EXP-0021's split: attachment/PBE store decisions, param-buffer overflow, and the
  ring/doorbell are firmware-managed.)

## 6. Recommended next
1. Decode `byte0` hi-nibble bit-split and `word1`[28:29] precisely (probe more sparse formats /
   3D & array sparse textures; try a sparse texture created on a *placement* heap if allowed).
2. Read a sparse texture's page-table / aux backing from the kernel side (kernel-team vantage) to
   pin how residency maps tile→physical (userspace can't see it).
3. Sample from a **partially-mapped** sparse texture and read back to confirm unmapped-tile behavior
   (returns 0 / `sparse_color`) — a HW-PROBE of the residency semantics.
4. Probe the bindless sampler heap at large K (thousands) and confirm resourceIDs stay a dense
   0-based(+1) index space up to 500000; check whether identical sampler descriptors dedup to one ID.

## Deliverables
`probe.m`, `rvar.m`, `heaparg.m`, `argx.py`, `run.sh` (harness); `analysis/diff_usage.txt`,
`analysis/diff_sparse_heap.txt`, `analysis/diff_floatfilter.txt`, `analysis/hex_*.txt` (byte-diffs);
`raw/key_descriptors.txt`, `raw/desc_*.txt`, `raw/heaparg_k{4,8,64}.txt`, `raw/probe.txt` (dumps).
Reused read-only: `tools/iotrace/` (`iotrace.c`, `descx.py`). No Apple binary disassembled.
Orchestrator owns `docs/` and `PROVENANCE.md`.
