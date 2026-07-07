# RT-11 RESULTS — 2nd independent red-team pass on cmdstream + pipeline

Device A18 Pro / G17P, macOS 26.6 (25G5043d). **67 dispatches/draws, all `status=4`, no
faults, no reboots.** Every fact re-derived with programs **different** from RT-2a/RT-4.
**[HW]** = a real dispatch/draw ran and a byte-diff on captured control BOs is the evidence.

## Verdict summary — every corrected fact UPHELD; one new hole decoded

| # | Claim under test (post-correction doc) | Verdict |
|---|---|---|
| 1 | USC sampler stride **0x20**; `num_samplers=(term−samp)/0x20` | **CONFIRMED** |
| 2 | Indexed VDM shift: instanceCount **@+0x78**, u32 opcode **0x61f4**, idxVA@+0x70, indexCount@+0x74, baseVertex@+0x7c | **CONFIRMED** |
| 3 | Sample positions **userspace @+0x40** (N (x,y) f32, 1/16 grid); NOT kernel-managed | **CONFIRMED — no kernel route exists** |
| 4 | 32 KiB is **not** a MRT/MSAA cap; it is the explicit-threadgroup/imageblock budget; rgba32f stride **0x1800** | **CONFIRMED** |
| 5 | No regression: state packets / programmable blend / tile 32×32 / memoryless / occlusion / timestamp | **CONFIRMED** |
| 6 | NEW hole: CDM effective-vs-API threadgroup mapping | **DECODED** (see §6) |

**No discrepancy found. cmdstream + pipeline pass their 2nd independent clean pass.**

---

## Claim 1 — USC sampler stride is 0x20 — CONFIRMED [HW]
Evidence: `raw/evidence/sampler_stride.txt`, `raw/hex/argbuf_s_*.hex`, `raw/bohex/s_t8s8_va10000248000.hex`.

Graphics draw (`smp11`), arg buffer `0x10000248000`, 2-pointer header `[tex-array VA][samp-array VA]`,
terminator `0x60000000`. Independent sweep — **wider than RT-2a's 1/2/3/4**:

| samplers | `term − samp_ptr` | `/0x20` (doc) | `/8` (old, wrong) |
|---|---|---|---|
| 1 | 0x20 | **1** ✓ | 4 ✗ |
| 2 | 0x40 | **2** ✓ | 8 ✗ |
| 5 | 0xa0 | **5** ✓ | 20 ✗ |
| 8 | 0x100 | **8** ✓ | 32 ✗ |

Also mixed (t2s5, t8s8, t3s2) and the texture sweep (t1/2/3/5/8 → `num_tex=(samp−tex)/0x20` exact).
**No count breaks it.** Both textures and samplers are 0x20-stride; `/8` overcounts 4×. Matches doc.

## Claim 2 — Indexed VDM record shift — CONFIRMED [HW]
Evidence: `raw/evidence/vdm_records.txt`, `raw/analysis/vdm_*.txt`, `raw/bohex/i_*.hex`.

Raw VDM records (`0x18000`), decoded:

**Non-indexed (`i_ni`, opcode `0x61c4`, verts6 inst1):**
`+0x65` prim=`0x06` (tri) · `+0x68`=6 vertexCount · `+0x6c`=1 instanceCount · `+0x70`=0 vertexStart.

**u16 indexed (`i_u16`):** `+0x64`=`0x40000001` · `+0x68`=`0x0000ffff` cut-index · `+0x6e`=`0x61f2` opcode,
`+0x6d` prim · `+0x70`=idxVA · `+0x74`=6 indexCount · **`+0x78`=1 instanceCount** · `+0x7c`=0 baseVertex.

**u32 indexed (`i_u32`):** `+0x68`=`0xffffffff` cut · `+0x6e`=**`0x61f4`** opcode (u32).

**Combo (`i_combo`: u32, icount9, inst4, basevert3):** `+0x74`=**9** · **`+0x78`=4** (instanceCount) ·
**`+0x7c`=3** (baseVertex) — decisively shows the shift.

Clean single-parameter isolations: `idxoff 4` (u16) → `+0x70` +8 bytes (idxVA carries the byte offset;
idxBuf VA `0x10000018800` → `+0x70`=`0x00018800` low32); `basevert 9` → `+0x7c` 0→9. **baseInstance is
NOT in the VDM record** (non-indexed baseinst change touched only `+0x6c` instanceCount; indexed
baseinst touched no real BO — my harness reads buffer(0) by `vertex_id` so it doesn't populate the
attr-table path where RT-2a located baseInstance at `0x10000100000+0x8c`; that field is unchanged here
but not independently re-tested — a documented, non-core detail). **Record shift = exactly as documented.**

## Claim 3 — Sample positions are userspace @+0x40 — CONFIRMED; NO kernel route [HW]
Evidence: `raw/evidence/sample_positions.txt`, `raw/analysis/allbo_sp*.txt`, `raw/analysis/tracediff_sp*.txt`,
`raw/hex/sp4_*_e8.hex`, `raw/bohex/sp4_*_va100000e8000.hex`.

**DIFFERENT custom positions than RT-4**, chosen as exact 1/16-grid values so decode is unambiguous:

| | default (no `setSamplePositions`) | custom (my input) |
|---|---|---|
| 4× @`0x100000e8000`+0x40 | (6/16,2/16)(14/16,6/16)(2/16,10/16)(10/16,14/16) = std D3D 4× | **(1/16,15/16)(8/16,1/16)(15/16,8/16)(4/16,12/16)** = my input exactly |
| 2× @`0x100000e0000`+0x40 | (12/16,12/16)(4/16,4/16) = std 2× | **(3/16,13/16)(13/16,3/16)** = my input exactly |

Each sample n at `+0x40 + n·8` as an (x,y) f32 pair, each coord on a 1/16 grid.

**Falsification of the "userspace" claim — no kernel route found:**
- Full-BO diff (default vs custom): the **only** BO that differs (past the `gpu_va=0x0` scratch
  artifact) is the **client sel-9 resource-map BO** (`0x100000e8000` / `0x100000e0000`), 8 words, all in
  `+0x40..+0x5c`. No firmware/register page carries them.
- IOKit CALL-structure diff (default vs custom): **4× = byte-identical call sequence**; 2× differs by a
  single `IOSurfaceRoot sel=0x20` call with **`inStructCnt=0`** (zero input payload → carries no position
  data). `IN.struct` count identical (43=43). ⇒ custom positions push **no extra data through any ioctl.**
- Even the **default** pattern is materialized in the client BO — the field is always userspace-populated,
  never a kernel route. Matches the RT-4 correction; `areProgrammableSamplePositionsSupported = YES`.

## Claim 4 — 32 KiB is not a MRT cap; it is the threadgroup/imageblock budget — CONFIRMED [HW]
Evidence: `raw/evidence/mrt_strides.txt`, `raw/evidence/tgcap_static_gate.txt`, `raw/evidence/tgmem_field.txt`,
`raw/hex/heap_mrt8_*.hex`, `raw/bohex/m_8_32f_va10000018200.hex`.

- **8× rgba32f MRT** (`Σ = 8·1024·16 = 131072 B = 128 KiB`, 4× the 32 KiB `maxThreadgroupMemoryLength`):
  pipeline **accepted**, draw **`status=4`**, attachment-0 pixel **correct** (`rgba=0.0625` = shader value).
  Tile-mem offsets climb to `0x12800` (>73 KiB). **Not gated by 32 KiB.**
- **Per-attachment tiler-heap stride (record `+0x08`):** bgra8 = **0x1000**, rgba16f = **0x1000**,
  rgba32f = **0x1800** — does *not* scale as `tile_area×bpp` (would be 0x4000 for rgba32f). Matches the
  RT-4 correction exactly; each record carries its own format word.
- **32 KiB IS the explicit-threadgroup gate (different budget):** static `[[threadgroup]]` pipeline
  creation — 4096/16384/32768 → **OK** (`staticThreadgroupMemoryLength` = requested); **32800 →
  REJECTED** *"Threadgroup memory size (32800) exceeds the maximum threadgroup memory allowed (32768)"*;
  49152/65536 also rejected. The dynamic tgmem field (shader BO `+0x4c[31:16]` with carry into `+0x50`)
  = `(bytes<<2)|0x80` (256→`0x480`; 32768→`0x20080`), a field distinct from the color tiler-heap records.
  **⇒ MRT color storage and the 32 KiB threadgroup/imageblock budget are two separate resources.**

## Claim 5 — regression re-check: CONFIRMED (no fix disturbed a prior fact) [HW]
Evidence: `raw/analysis/st_*.txt`, `raw/evidence/tile_grid.txt`, `raw/stdout/st_*.out`.

- **State packets (`0x58000`):** depth compare `+0x38` bits[26:24] less(1)→greater(4) (`+0x40` back mirrors);
  stencil enable at `+0x34` bit19 + `+0x3c` write/read masks; cull `+0x70`[1:0] none(0)→back(2);
  depth clip-vs-clamp `+0x70`[11:10] (01→10). **PPP length** grows **+0x400** on both VDM `0x18000+0x0c`
  and pool `0x58000+0x14` when the depth block is appended. All exactly as documented.
- **Programmable blend:** enabling blend rewrites **231 words** of the FS-code BO `0x10000000000` and only
  **2 words** of `0x58000` — blend is compiled into the fragment shader, not a fixed-function LUT. ✓
- **Tile 32×32 fixed:** `0x68000 +0x904 = 0x80000000|(ceil(W/32)−1)`, `+0x908 = ceil(H/32)−1` across
  64²/1024²/777×333/31²/33²/**2048×64** (X=63,Y=1 independent). bit31 always on `+0x904`, never `+0x908`. ✓
- **Memoryless color:** single-sample memoryless relocates (no `0x10000110000` BO); tiler-heap record
  `+0x28 = 0x0eeee000` poison, `+0x24` bit27 clear. ✓
- **Occlusion query:** Counting mode wrote **4096** = 64×64 exact passed-sample count (u64). ✓
- **GPU timestamp:** stage-boundary samples nonzero+monotonic; `sampleTimestamps` cpu/gpu deltas **equal**
  (ratio **1.00000**) ⇒ timestampPeriod = 1.0, uint64 ns, cpu==gpu clock. ✓

## Claim 6 — NEW hole decoded: CDM effective-vs-API threadgroup mapping [HW]
Evidence: `raw/evidence/cdm_efftg_summary.txt`, `raw/bohex/c_tg64_va100001b8000.hex`.

RT-2a flagged the CDM `+0x1c/+0x20/+0x24` field as "effective/driver-chosen, not verbatim API tg" but
left the mapping open. Decoded (CDM launch descriptor, trivial kernel, `dispatchThreads`):

- **grid `+0x10/+0x14/+0x18` = verbatim threads** (256, 512, 64×64, 64×64×8) — re-confirmed.
- **effTG `+0x1c/+0x20/+0x24` = driver-chosen: each axis rounded UP to a power of two, product ≥ 32
  (one 32-lane SIMD), capped by `maxTotalThreadsPerThreadgroup=1024`:**
  - 1-D reqTG 1..32 → **32**; 48,64 → **64**; 100 → **128** (round up to next pow2 ≥ max(req,32)).
  - 2-D req (3,5) → **(4,8)** = 32; 3-D grid tg(1,1,1) → **(32,1,1)**.
- This value is **occupancy/shader-dependent** (RT-2a's register-heavier kernel saw tg8→16; my trivial
  kernel sees tg8→32), which is exactly *why* it must be treated as effective, not a copy of the API arg.

**Driver takeaway (already implied by the doc, now quantified):** emit the launch threadgroup you actually
use; do not expect `+0x1c` to echo `threadsPerThreadgroup`. The offset is correct; the value is the HW
partition (per-axis pow2, ≥ 32-lane SIMD).

---

## Bottom line
Sampler-stride 0x20 ✓ · indexed instanceCount@+0x78 (u32 opcode 0x61f4) ✓ · sample positions genuinely
userspace @+0x40 with **no kernel-route case** ✓ · 32 KiB really not a MRT cap (static threadgroup gate is
the real 32 KiB limit) ✓ · rgba32f stride 0x1800 ✓ · all prior state/blend/tile/memoryless/occlusion/
timestamp facts intact ✓. **One new hole (CDM effective-tg mapping) decoded, no discrepancy.**
cmdstream + pipeline pass their 2nd clean pass.
