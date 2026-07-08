# EXP-M4-08 Results — Descriptor coverage (DESC-1..DESC-7)

**Devices:** primary **Apple M4** (Mac16,10, macOS 26.4.1); cross-confirm **A18 Pro** (G17P, macOS
26.6). **Clean-room:** OWN-SHADER + DATA-TRACE + HW-PROBE; no Apple binary disassembled. All values
below are **HW-validated** (a dispatch/draw + a clean single-parameter byte-diff) unless marked
*inferred*. **A18 == M4 byte-for-byte** on every cross-confirmed point (`raw/a18_xconfirm.txt`,
0 mismatches over 33 formats). Zero GPU wedges/reboots.

Word/byte convention: `wordN` = 32-bit LE word at byte `4N` of a descriptor block; `byteN` = byte at
offset N. Sampled `byte0 = word0 & 0xff`, `byte1 = (word0>>8) & 0xff`, `swizzle = word0[16:27]`.

---

## DESC-1 [HIGH] — RT attachment format word: **CORRECTED** + full coverage

Swept **all 46 renderable formats** (`rtfmt.m`, `raw/rt_format_capture.txt`). Single buffer-backed
color RT → the 3-segment attachment chain at `0x10000110000` (LOAD seg0 / RENDER seg1 / STORE seg2).

**The LOAD/RENDER format word (seg+0x20) is exactly:**
```
word = (0xf << 28) | (swizzle[11:0] << 16) | (byte1 << 8) | (byte0 & ~0x20)
```
where `byte0`, `byte1`, `swizzle` are the **sampled texture-descriptor** fields (DESC-5 table). This
formula matched **43/43** narrow/mid formats with **0 mismatch** (`analysis/rt_format_decode.txt`); the
3 128-bit formats relocate (below) but carry the identical value.

**CORRECTION to the doc's "byte+0x22 = format":**
| attachment byte | content |
|---|---|
| byte+0x20 | `byte0 & ~0x20` (texture-type + arrangement, **bit5 cleared**) |
| **byte+0x21** | **`byte1` = the format code** (`numtype<<5 \| sizeclass`) ← the real format byte |
| byte+0x22 | `swizzle[0:7]` (low byte of the 12-bit swizzle) |
| byte+0x23 | `0xf0 \| swizzle[8:11]` |

The old claim "byte+0x22 = format" only *coincided* for **bgra8**, whose swizzle-low byte (`0x0a`)
happens to equal its format code (`0x0a`). For rgba8 byte+0x22 = `0x88` (swizzle-low), not the format.
Verified false across rgba8/r8/r32f/integer/packed. **The format identity is byte+0x21.**

**STORE segment (seg2+0x20) — a PBE descriptor** (`raw/rt_format_capture.txt` `store=` column):
```
store_word0 = ((width-1)&0xff)<<24 | component_field<<16 | byte1<<8 | (byte0 & ~0x20)
store_word1 = (height-1) << 6
```
Format code again at **byte+0x21 = byte1** (checked 34/34). `component_field` (byte+0x22 of the store)
is the format-derived PBE component byte (r=`0x00`, rg=`0x04`, rgba=`0xe4`, bgra=`0xc6`, bgr=`0x06`) —
the same field EXP-G1b §1b documents.

**Wide-format relocation** (placement only, not encoding): ≥64bpp RTs move the STORE/RENDER descriptors
out of `0x10000110000` (LOAD word stays); 128bpp RTs (rgba32*) relocate the whole attachment to the
tiler geometry heap `0x10000018200` / `0x10000120000`. The format-word **values are identical** to the
formula (e.g. rgba32float LOAD = `0xf6888e02` at the relocated BO). So the format word is derivable for
**every** renderable format; only the BO it lands in changes with imageblock size.

**A18:** seg0 words identical for r8/rgba8/bgra8/r32f/rgba8uint/rg11b10/rgb9e5/bgr10_xr/rgba16f.

---

## DESC-5 [emphasized] — byte0 channel-arrangement nibble: **DECODED**

Captured **all 96 formats** (`raw/format_capture.txt`; decode `analysis/format_decode.txt`). Structure:
```
byte0 = arrangement[4:7] | texture_type[0:2]      (byte0 bit4 (0x10) = 0 in every capture)
byte1 = numtype[5:7] | sizeclass[0:4]
```
The **arrangement sub-index** is observed entirely in `byte0 bits[5:7]` (a 3-bit value; bit4 unused).
Values seen: `{1,3,5,7}` for color/compressed (bit5 always set), `{0,2}` for YUV. **It is a
per-sizeclass sub-index** that disambiguates the channel arrangements sharing one sizeclass — it is
*not* an independent channel-count field. With all 96 standard formats now captured, no format needs
guessing; the sub-index makes families derivable:

**ASTC block-shape grid (all 14 LDR shapes decoded — was 8/14 untested).** sizeclass × arr enumerates
the shapes in Metal's canonical order:
| sizeclass | arr=1 | arr=3 | arr=5 | arr=7 |
|---|---|---|---|---|
| `0x18` | 4×4 | 5×4 | 5×5 | 6×5 |
| `0x19` | 6×6 | 8×5 | 8×6 | 8×8 |
| `0x1a` | 10×5 | 10×6 | 10×8 | 10×10 |
| `0x1b` | 12×10 | 12×12 | (unused) | (unused) |

HDR-ASTC = same sizeclass + **numtype float** (astc_4x4_hdr byte1 `0x98`). sRGB-ASTC = same code +
word3 bit12.

**New sizeclasses discovered:**
- `0x03` = 16bpp **4-channel packed** (abgr4 arr1, a1bgr5 arr3, bgr5a1 arr5).
- `0x10` = **YUV 4:2:2** (gbgr422 arr0, bgrg422 arr2 — the only formats with byte0 bit5 = 0).
- (Confirms EXP-0028's `0x14`/`0x16`/`0x17`/`0x18`–`0x1b`/`0x1d`/`0x1e` for PVRTC/ETC2/EAC/ASTC/BC.)

**depth32float_stencil8 aspects** (was untested): depth aspect = **r32float** code (`0x62`/`0x88`);
stencil aspect = **X32_Stencil8** = **r8uint** code (`0x22`/`0x40`). (stencil8 also = r8uint code.)

**A18:** all 24 cross-confirmed word0 values (incl. all ASTC shapes, packed, BC6H, XR, stencil) identical.

---

## DESC-6 [confirmed] — numtype orthogonality on packed / wide / compressed

`code = numtype<<5 | sizeclass` is **fully orthogonal**, HW-validated across **18** `(sizeclass,arr)`
families spanning every width and packing (`analysis/format_decode.txt` "numtype orthogonality"):
- packed **rgb10a2**: unorm `0x09` / uint `0x49` / **xr `0xa9`** (numtype 5 = extended-range) — all arr5.
- 64-bit **rg32** (uint/sint/float) and **rgba16** (unorm/snorm/uint/sint/float); 128-bit **rgba32**
  (uint/sint/float).
- compressed: **BC4/BC5/EAC** unorm↔snorm (numtype 0↔1), **BC6H/ASTC** float (numtype 4).
So numtype is independent of arrangement/sizeclass for the full format set, not just the 4 base families.

---

## DESC-2 [confirmed + refined] — 14-bit dims on non-2D; depth/arrayLen field; PBE split

**14-bit width/height generalize to all texture types** (`raw/dims_capture.txt`), same encoding as 2D:
2DArray reached **16384** (width and height, independently); 3D reached **2048** (the Metal 3D axis
limit, 11-bit); Cube reached **8192**; 5000×5000 on 2DArray (both axes >4096).

**depth (3D) / arrayLength (array) − 1 = word3 bits[14:24]** (11-bit, max 2048; Metal's array/depth
limit). Shared, type-dependent field. Confirmed: arrayLen 2048 → `0x7ff`, arrayLen 64 → `0x3f`, depth
2048 → `0x7ff`. word3 **bits[30:31]** are separate layout flags (bit31 = aux/mip metadata). For
buffer-backed linear textures the *same* word3[14:] field instead carries the stride (DESC-7 /
format-table §7) — context-dependent as documented.

**PBE (storage-image) alternate split HW-validated to the full 14 bits** (`raw/pbe_dims_capture.txt`) —
previously *inferred* (all tested ≤256):
- **width−1 = word0[24:31] ‖ word1[0:5]** — reached **16384** (16384×4 → `0xff`+`0x3f`).
- **height−1 = word1[6:19]** — reached **16384** (4×16384).
- Asymmetric 8192×256 / 256×8192 / 300×100 separate W/H cleanly.

**A18:** 2DArray 16384 width + arrayLen 2048 identical.

---

## DESC-3 [confirmed + refined] — sampler LOD / anisotropy

`raw/sampler_capture.txt`. Sampler descriptor `word0`/`word1` (8-byte descriptor, LE).
- **lodMin** = bits[0:12], **×64** (6 frac): 0.25→`0x10`, 0.5→`0x20`, 1.5→`0x60`, 13.9→`0x379`.
  **Saturates at 14.0** (`0x380`) — lodMin is clamped to the (default 14.0) lodMax.
- **lodMax** = bits[13:19], **×8** (3 frac): 0.25→2, 1.5→12, 3.0→24, 13.9→111. **Saturates at 14.0**
  (`112`). The field is 7-bit (could hold 15.875) but **Metal clamps to 14.0**; >14.0 is
  Metal-unreachable (a splice candidate; the HW field has room).
- **maxAnisotropy** = bits[20:22], **log2**: 1/2/4/**8**/16 → 0/1/2/**3**/4 (**aniso 8× now confirmed**).
  **aniso >16 clamps to field 0 (= 1×), NOT 16×** — the Metal setter rejects >16 to 1×. The 3-bit field
  *can* encode up to 128× (log2 7) but Metal won't emit >4; >16× requires descriptor injection.

**A18:** lodMax 14.1/15.875 → saturate 14.0; aniso 8 → `0x3`, aniso 32 → `0x0`. Identical.

---

## DESC-4 [reachable codes confirmed] — sampler address / border / swizzle

Metal-reachable codes (`raw/sampler_capture.txt`), all HW-validated:
- **Address S/T/R** bits[29:31]/[32:34]/[35:37]: edge=0, repeat=1, mirror=2, **clampToZero = clampToBorder = 3** (single HW mode), mirrorClampToEdge=5.
- **Border** bits[61:62]: transparent-black=0, opaque-black=1, opaque-white=2.

**Codes 4/6/7 (address), 6/7 (swizzle), 3 (border), aniso>16, lodMax>14 are not expressible via
Metal.** Attempted raw injection via an **explicit argument buffer** (`splice.m`): on Apple9 the
explicit arg buffer holds **8-byte gpuResourceIDs** (bindless indices into device-global texture/sampler
tables — `id 0x1`, `0x2`), **not** inline descriptor bytes, so the raw code cannot be patched there; the
*auto* arg buffer's appended 8-byte sampler descriptor is Metal-internal memory. Injecting these codes
needs a write-capable interposer or a device-global-table patch — **beyond this read-only pass**. So the
gap codes' HW behavior remains **uncharacterized** (unchanged from the doc). *Vulkan implication:* map
`VK_SAMPLER_ADDRESS_MODE_*` only onto the confirmed codes {0,1,2,3,5}; treat 4/6/7 as unknown.

---

## DESC-7 [confirmed] — buffer bounds behavior; texture-buffer descriptor

`desc7.m` (HW-PROBE).
- **Plain `device T*` buffer** = bare inline 8-byte GPU VA, **no length word** (EXP-0015 reconfirmed).
  Out-of-bounds reads (16-element buffer, indices 16 / 100 / 4096 / 1e6 / **268435456 (≈1 GiB past)**)
  all return **`0.0` with `status=completed` — no fault** in the entire tested range. ⇒ **no
  descriptor-level bounds check**; OOB device-buffer reads yield 0 by VM behavior, not by a bound. A
  Vulkan driver wanting strict `robustBufferAccess` semantics cannot rely on a descriptor bound (there
  is none) but *does* get non-faulting zero-return for free.
- **texture_buffer (typed/texel buffer)** = a **full 32-byte texture descriptor**, **not** a bare VA:
  `f9688842 0000000f 00001c50 000fc010` (r32float, 256 elems). type field 2, format code byte1=`0x88`,
  **width−1 = word0[28:31]‖word1[0:9]** = 255, base **VA>>4**, **linear stride word3[14:] = 63 →
  (63+1)×16 = 1024 = bytesPerRow**. word0 top nibble `0xf` + byte0 bit5 cleared (the PBE/attachment
  component-explicit form). So typed buffers ride the texture-descriptor path (1D linear), not the
  plain-buffer path.

---

## Established facts → docs (orchestrator owns `docs/`; these two files are mine)
- `docs/descriptors/format-table.md`: decode the byte0 arrangement field + ASTC grid (§2b), add the
  new sizeclasses (`0x03`, `0x10`) + the full captured format set, resolve depth32float_stencil8 aspects
  and the DESC-6 orthogonality note.
- `docs/descriptors/README.md`: add the **RT attachment format-word derivation** (+ the byte+0x21
  correction), refine depth/arrayLen to word3[14:24], the PBE 14-bit split (now HW-validated), the
  sampler LOD/aniso saturation + Metal-reachable limits, and the buffer OOB / texture_buffer facts.
- **Cross-doc flag for the orchestrator:** `docs/pipeline/README.md` §"LOAD/RENDER: format word …
  byte+0x22 = format" and `docs/cmdstream/` carry the **wrong** byte offset — the format code is
  **byte+0x21**; byte+0x22 is swizzle-low. (I do not own those files; flagging for propagation.)
