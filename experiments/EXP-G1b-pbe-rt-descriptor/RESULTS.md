# EXP-G1b Results — PBE / render-target (storage-image) descriptor (A18 Pro / G17P)

**TL;DR.** (1) A texture bound `access::write` in a compute/fragment shader is described by a
**distinct 32-byte "PBE" descriptor** in the Tier-2 argument buffer — *not* the sampled texture
descriptor. It shares the format code (byte0/byte1) and base-VA field (`VA>>4`) with the sampled
descriptor but **re-packs width/height, replaces the swizzle field with a format-derived component
field, and carries NO lossless-compression aux**. `access::read_write` binds **two** descriptors —
a (read) texture descriptor *and* a PBE descriptor — plus two 8-byte control words. `access::read`
uses the ordinary sampled descriptor + an 8-byte read-control word (in place of a sampler).
(2) The 3D **render-target attachment descriptor** (`0x10000110000`) is a chain of three 0x300-byte
segments — **LOAD / RENDER / STORE**. The **STORE segment is itself a PBE descriptor** carrying the
RT **surface VA (`VA>>4`), width−1, height−1, and linear stride/rowBytes**; the LOAD/RENDER segments
carry the same surface as a *texture-style* descriptor plus clear-enable + clear color. All fields
HW-validated by a surface-VA correlation and a 6-size × 6-format sweep. (3) **MRT** relocates the
color attachment into the tiler geometry heap (`0x10000018200`) and arrays the N attachments at a
fixed **0x20-byte per-attachment stride** (LOAD block at +0x20, STORE/PBE block at +0x220).
Every finding is **[HW]** (a dispatch/draw confirmed it + a clean byte-diff) or **[inf]** (inferred).
Zero GPU wedges/reboots; all 36 dispatches/draws `status=completed`.

Word convention: `wordN` = 32-bit LE word at byte `4N` of a descriptor block; `byteN` = byte at
offset N. Storage descriptors live in the compute Tier-2 auto argument buffer (slot table at
`+0x14a0`, appended descriptors at `+0x14c0`, EXP-0011/0015). RT attachment segments live in
`0x10000110000` (single RT) or `0x10000018200` (MRT/MSAA). Raw: `raw/`, diffs: `analysis/DIFFS.txt`.

---

## 1. Storage-image (PBE write) descriptor — argument-buffer binding [HW]

### 1a. Per-access-qualifier argument layout (rgba8 64×64, `raw/storage_descriptors.txt`)
The auto argument buffer allocates, per texture, a **descriptor slot + an 8-byte control-word slot**
(exactly as a sampled texture allocates a texture-descriptor slot + a sampler slot). What lands in
each depends on the MSL access qualifier:

| access | slot0 (+0x14c0) | slot1 (+0x14e0) | notes |
|---|---|---|---|
| `sample`     | 32B **sampled** texture descriptor (compressed) | 8B **sampler** `000e0000 00000780` | EXP-0015 baseline |
| `read`       | 32B **sampled** texture descriptor (compressed, **byte-identical** to `sample`) | 8B **read-control** `680e0000 0000031b` | read w/o sampler still uses the sampled descriptor |
| `write`      | 32B **PBE descriptor** `3fe40a22 00000fc0 00008000 00000010 00000000 00000000` | 8B **write-control** `080e0000 00000300` | **compression aux dropped** (word4/5 = 0) |
| `read_write` | 32B (read) texture descriptor, **compression disabled** `f6880a22 0000fc03 00008000 00000010 …` | 32B **PBE descriptor** `3fe40a22 00000fc0 …` | slot2→ read-control + write-control words; obuf at slot3 |

Key structural facts:
- **`access::write` ⇒ a PBE descriptor, not the sampled descriptor.** word0 `0x3fe40a22` vs sampled
  `0xf6880a22`; word1, word3 differ; the compression aux (sampled word4/5 = `0x8400`/`0x10`) is
  **zeroed** (ShaderWrite disables lossless compression — matches EXP-O2B / `docs/tiling` §4.1).
- **`access::read_write` binds BOTH** a texture (read) descriptor *and* a PBE (write) descriptor,
  consuming two descriptor slots; the read descriptor has compression **disabled** (ShaderWrite
  present) — so it is *not* byte-identical to the pure `sample` descriptor (word1 `0000fc03` vs
  `0800fc03`, word3 `00000010` vs `80000010`, word4 = 0).
- **`access::read` uses the ordinary sampled descriptor** (compression preserved) + an 8-byte
  read-control word in the sampler slot.
- **HW-validated:** the `write` r32f dispatch wrote `gid.x` into the texture; readback =
  `0.00 1.00 2.00 3.00` (`caps_out/s_write_bb_r32f.out`).

### 1b. PBE (write / storage-image) descriptor — 32-byte field map [HW]
Base = rgba8 64×64: `3fe40a22 00000fc0 00008000 00000010 00000000 00000000 …`

| field | location | encoding | evidence (`analysis/DIFFS.txt`) |
|---|---|---|---|
| texture type | word0 bits[0:3] (byte0 low nibble) | 2D=2 — **same codes as sampled** (`format-table` §1) | — |
| channel arrangement | word0 bits[4:7] (byte0 hi nibble) | format-derived | fmt sweep |
| format numtype+sizeclass | word0 byte1 | `(numtype<<5)\|sizeclass` — **identical to the sampled format-table** | r32f `62/88`, rgba32f `22/8e`, r32u `62/48`, rg16f `e2/88`, r16f `62/82`, rgba16f `a2/8c` |
| component/write field | word0 bits[16:23] (byte2) | **format-derived** (rgba=`0xe4`, rg=`0x04`, r=`0x00`) — not an independent knob | fmt sweep |
| **width−1** (low 8) | word0 bits[24:31] (byte3) | `(width−1) & 0xff` | 33→`0x20`, 129→`0x80`, 256→`0xff`, 65→`0x40` |
| width−1 (high) | word1 bits[0:5] | `(width−1) >> 8` | **[inf]** — all tested ≤256 |
| **height−1** | word1 bits[6:19] | `value = height−1` | 17→16, 63→62, 256→255, 65→64 |
| **base VA** | word2 ‖ word3 bits[0:11] | **`VA>>4`** (16-byte units) — same field as sampled | word2=`0x8000` unchanged sample↔write |
| **linear stride** (buffer-backed) | word3 bits[12:] | `((word3>>12)+1) × 16` = bytesPerRow | bb r32f 64→`f010`→256; RT store desc 64/128/256→256/512/1024 |
| aux / compression | word3 bit31 + word4/word5 | **always 0** for write (never compressed) | write word4/5=0 vs sampled `0x8400`/`0x10` |

**Difference from the sampled 32B descriptor** (`docs/descriptors/format-table.md` §5): PBE shares
byte0/byte1 (type+format) and word2‖word3[0:11] (base `VA>>4`) but (a) packs **width−1 in
word0[24:31]‖word1[0:5]** and **height−1 in word1[6:19]** — a *different* split than sampled
(width−1 in word0[28:31]‖word1[0:7], height−1 in word1[10:]); (b) word0[16:27] is **not** the 4×3-bit
swizzle — it is a format-derived component/write field; (c) **no compression aux** (word3 bit31 clear,
word4/5 zero). The 8-byte write-control word (`080e0000 00000300`) reuses the 8-byte **sampler**
descriptor byte layout (EXP-0015 §4); its exact bits are **[inf]** (a default non-filtered state).

---

## 2. Render-target attachment descriptor (`0x10000110000`) — full field map [HW]

Single-RT, non-MSAA. A chain of **three 0x300-byte segments: seg0=LOAD (+0x000), seg1=RENDER
(+0x300), seg2=STORE (+0x600).** Each segment starts with two self-referential 8-byte pointers
(+0x00 → seg+0x20 body, +0x08 → seg+0x120 sub-block; store seg fills `0xffffffff` where load
pointers would be). Base = bgra8 64×64 clear/store, buffer-backed **surface VA `0x10000058000`**
(`raw/rt_base.hex`).

### 2a. Surface VA — HW-correlated
`surface_VA = ((word3 & 0xfff) << 32 | word2) << 4`. For rt_base:
`((0x010<<32) | 0x5800) << 4 = 0x10000058000` = the printed `rtBuf0` VA. Validated across all sizes
(e.g. 33×17 → `0x18200` = its `rtBuf0`). This is the **same `VA>>4` (16-byte-unit) encoding** as the
texture-descriptor base VA.

### 2b. LOAD / RENDER segment body (seg+0x20) — texture-style
| offset | field | value (64×64 bgra8) | meaning / evidence |
|---|---|---|---|
| seg+0x20 | packed format word | `0xf60a0a02` | byte+0x22 = format (bgra8=`0x0a`); = sampled word0 with byte0 hi-nibble 0. fmt sweep: rgba8 `f6880a02`, r8 `f9680002`, r32f `f9688842` |
| seg+0x24 | config / sample word | `0x0000fc03` | non-MSAA; MSAA → `0x0800fc03`(2×)/`0x0900fc03`(4×) [EXP-0021] |
| seg+0x28 | surface `VA>>4` low32 | `0x00005800` | =(0x10000058000>>4)&0xffffffff |
| seg+0x2c | VA-hi + stride | `0x0003c010` | bits[0:7]=`0x10`(VA>>4[32:39]); bits[14:]=stride `0xf`→256=bpr |
| seg+0x2d0 | format-class byte | `0x00100083` | bgra8=`0x83`, r8=`0x23`, r32f=`0x31` (format-derived) **[inf meaning]** |
| **seg1+0x168** (=+0x468) | **clear-enable** bit24 + flags | `0x01000002` | Clear on; DontCare → `0x00000002` (bit24 cleared) **[HW]** |
| seg1+0x17c / +0x1f0 / +0x1fc | clear color floats | `0x3f800000`(=1.0) | RGBA clear color |

### 2c. STORE segment body (seg2+0x20 = +0x620) — a PBE descriptor
The store phase describes the surface with the **same PBE descriptor** as a compute storage-image
write (§1b):
| offset | field | value | meaning |
|---|---|---|---|
| +0x620 | PBE word0 | `0x3fc60a02` | byte1=store format; byte2=`0xc6`(bgra order); **byte3=`0x3f`=width−1** |
| +0x624 | PBE word1 | `0x00000fc0` | **`>>6`=`0x3f`=height−1** |
| +0x628 | surface `VA>>4` low | `0x00005800` | |
| +0x62c | VA-hi + stride | `0x0000f010` | bits[0:11]=`0x010`(VA-hi); **bits[12:]=`0xf`→stride 256** |
| +0x8c4 | **store program id** | `0x0000006f` | [EXP-0021] |
| +0x8c8 / +0x8cc / +0x8d8 | store surface addr | `0x00058000` | store target VA (raw 32-bit) — **DontCare → `0xffffffff`** (store disabled) **[HW]** |

### 2d. Dims / stride sweep — store PBE descriptor (`raw/rt_store_sweep.txt`) [HW]
| RT (W×H) | word0 byte3 = W−1 | word1>>6 = H−1 | stride `((word3>>12)+1)×16` |
|---|---|---|---|
| 64×64   | `0x3f`=63  | 63  | 16×16 = **256** (bpr) |
| 128×128 | `0x7f`=127 | 127 | 32×16 = **512** |
| 256×256 | `0xff`=255 | 255 | 64×16 = **1024** |
| 33×17   | `0x20`=32  | 16  | **256** (33×4=132→align 256) |
| 128×64  | `0x7f`=127 | 63  | **512** — **asymmetric: W≠H separated ✓** |
| 65×65   | `0x40`=64  | 64  | **512** (65×4=260→align 512) |

### 2e. Load / store action & resolve [HW]
- **Load = Clear:** clear-enable bit24 at seg1+0x168 (=+0x468) set; clear color at +0x17c…
- **Load = DontCare:** *only* +0x468 bit24 cleared (`0x01000002`→`0x00000002`).
- **Load = Load:** adds a surface-read (PBE-style) descriptor into the RENDER segment (+0x320 gains a
  `0x3f..0a02` word + surface `0x00005800` + store-id `0x6f`) → reads existing tile contents.
- **Store = Store:** store PBE descriptor + surface addr `0x00058000` present in seg2.
- **Store = DontCare:** the store surface addresses become `0xffffffff` (no store); the store PBE
  descriptor shifts within the segment.
- **MSAA resolve:** under MSAA the color relocates (§3); byte0 low-nibble becomes **`4`
  (2DMultisample)** and seg+0x24 encodes the sample count (`0x0800fc03`=2×, `0x0900fc03`=4×); the
  MultisampleResolve store adds a per-sample resolve descriptor. Programmable sample **positions** do
  not appear in any BO (firmware-managed, EXP-0021 — corroborated).

### 2f. Tile / compression flags
The buffer-backed RTs here are **linear** — the descriptor carries an explicit stride (§2c-d) and no
compression aux. A **Private (twiddled) RT** would carry stride=0 (Morton implicit) and, per EXP-O2B
("RenderTarget stays compressed"), the lossless-compression aux VA + word3 bit31 like the sampled
path — **[inf]**: `rt_priv`'s attachment relocated to an unlabeled BO and was not cleanly isolated
here (recommended next).

---

## 3. Multi-RT (MRT) array layout [HW]

For **N ≥ 2 color attachments (or any MSAA)** the color attachment descriptor **relocates from
`0x10000110000` into the tiler geometry heap `0x10000018200`** (confirmed EXP-0021). There the N
attachments are arrayed as fixed **0x20-byte per-attachment records**, one array per phase
(`analysis/DIFFS.txt` mrt3-vs-mrt2, mrt4-vs-mrt2):

| block | offset | per-attachment record (0x20 B) |
|---|---|---|
| LOAD/format | `0x20 + k·0x20` | [format word, config `0xfc03`, surface `VA>>4`, VA-hi+stride] |
| STORE (PBE) | `0x220 + k·0x20` | [PBE word0, height<<6, surface `VA>>4`, VA-hi+stride] |
| clear color | `0x500 + k·0x18` | 6 floats per attachment |

Evidence: attachment k LOAD record at `+0x20+k*0x20` with surfaces `0x58000 / 0x60000 / 0x68000 /
0x70000` (k=0..3; 0x8000-byte VA stride between the four RT surfaces); attachment k STORE/PBE record
at `+0x220+k*0x20` (`0x3fc60a02 …`). **Per-attachment descriptor stride = 0x20 bytes** within each
phase block. (Distinct from EXP-0021's per-attachment **imageblock tile-memory** record — stride
`0x1000` for bgra8 — which is a *separate* tiler-heap structure.)

---

## 4. HW-validated vs inferred; kernel-managed

**HW-validated (dispatch/draw + clean byte-diff):**
- PBE (write) descriptor full field map (format codes, width−1/height−1, base `VA>>4`, stride, no
  aux); write dispatch readback `0,1,2,3`.
- `read_write` = texture(read) + PBE dual-descriptor; `read` = sampled descriptor + control word.
- RT attachment 3-segment LOAD/RENDER/STORE; STORE = PBE descriptor; surface VA correlated to
  `rtBuf0`; width/height/stride over 6 sizes; format word over 6 formats.
- Clear-enable bit24 @ seg1+0x168; store-DontCare surface poison `0xffffffff`; Load adds a read desc.
- MRT 0x20-stride per-attachment array + per-attachment surface VAs; all renders produced correct
  pixels (bgra8 `bf8040ff`, rgba8 `4080bfff`, mrt2 `30201040`).

**Inferred / not fully isolated:**
- width−1 high bits (word1[0:5]) — all tested widths ≤256; 8-byte read/write control-word bit decode;
  byte2 component-field exact bit meaning; seg+0x2d0 format-class byte + the store-program config word
  (+0x82c: bgra8 `10020300`, r8 `04020300`, r32f `04021100`).
- Private (twiddled) RT compression aux (relocation prevented clean isolation).
- MSAA per-sample resolve descriptor internals (sample-count field itself confirmed).

**Kernel/firmware-managed (unchanged; corroborated):** programmable sample **positions** (no BO);
depth/ZLS store; store-program id `0x6f` semantics + bg/eot programs; partial-render / param-buffer
overflow trigger; ring/doorbell submission.

## 5. Established facts → docs
- Storage-image (PBE) descriptor field map + per-access-qualifier arg-buffer layout → `docs/descriptors/`
  (new "storage-image / PBE descriptor" section alongside the sampled 32B descriptor).
- RT attachment descriptor full field map (surface `VA>>4`, width−1/height−1/stride, LOAD/RENDER/STORE
  segments, clear-enable bit24, store poison) + MRT 0x20-stride array → `docs/pipeline/` (extends
  EXP-0021) and `docs/cmdstream/` (attachment `0x10000110000`). Orchestrator owns `docs/` + PROVENANCE.

## 6. Recommended next
1. Probe width **>256** (e.g. 512×512) to confirm the width-high field (word1[0:5]).
2. Decode the 8-byte read/write **control word** with a mipmapped storage image (LOD/base-level bits).
3. Force a **Private compressed RT** to not relocate (fixed size/order) and capture its compression aux.
4. Decode the seg+0x2d0 format-class byte and the store-program config word (+0x82c).

## 7. Deliverables
`svar.m` (storage-image compute harness), `rtvar.m` (render-target draw harness), `argx2.py`
(arg-buffer descriptor locator/dumper), `attloc.py` (attachment-BO locator + surface-VA finder),
`run.sh` (matrix driver). `raw/` — curated descriptor/attachment hex, `rt_store_sweep.txt`,
`storage_descriptors.txt`. `analysis/DIFFS.txt` — all byte-diffs. `caps_out/*.out` — per-run stdout.
Reused read-only: `tools/iotrace/{iotrace.c,bodiff.py,dumpscan.py,bograph.py}`,
`experiments/EXP-O2B/descx.py`. No Apple binary disassembled.
