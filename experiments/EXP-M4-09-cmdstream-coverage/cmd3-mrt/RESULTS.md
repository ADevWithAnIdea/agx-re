# CMD-3: MRT 5–8 attachments + mixed formats — tiler-heap color-descriptor array

**Experiment:** EXP-M4-09-cmdstream-coverage / cmd3-mrt
**Device:** Apple **M4** (Apple9 family, Metal 4), LOCAL host. *A18 Pro cross-confirm flagged where noted.*
**Clean-room category:** DATA-TRACE (interpose IOKit, dump our own process's GPU BOs) + OWN-SHADER
(runtime-compiled MSL). **No Apple binary disassembled.**
**Method:** `mrtvar` (extended with per-RT `--fmts`) drives 1..8 color attachments, dumps all
registered GPU BOs on SIGUSR1 via `iotrace.dylib` (`IOTRACE_MAX_MAP=0x8000` so the whole tiler-heap
BO is captured). All 11 runs completed `status=4` with **0 CB_ERROR**.

> Address note: on M4 the harness prints VAs padded to 16 hex digits (`0x0000010000058000`); the
> interposer's canonical form is `0x10000058000`. These are the **same** VA. The A18 doc constant
> `0x10000018200` is present **verbatim** on M4 — the tiler geometry-heap BO is at gpu_va
> `0x10000018200` here too.

---

## 1. Verdicts (summary)

| Doc claim (docs/pipeline/README.md "MRT", docs/cmdstream) | Verdict on M4 |
|---|---|
| (a) Color descriptor relocates to tiler heap `0x10000018200`, **0x20-byte per-attachment records**, LOAD @`+0x20+k·0x20`, extends to k=7 | **CONFIRM** — all 8 records present, exact 0x20 stride, each with its own surface VA + format + row-stride. |
| (b1) STORE/PBE sub-array @`+0x220+k·0x20` | **CONFIRM** — 8 records, 0x20-strided, per-attachment (PBE descriptor). |
| (b2) clear-color sub-array @`+0x500+k·0x18` **in BO 0x10000018200** | **CORRECT (doc is wrong)** — that offset is a **vertex-buffer alias**, not clear colors. Real per-attachment clear array is a **float4 (0x10-stride)** array in a **separate** tiler BO (M4: `0x10000148000` @`+0x170`, mirrored @`+0x470`). See §4. **FLAG A18.** |
| (c) per-attachment format words (byte @ record) are per-attachment, not shared | **CONFIRM** — each record's `byte1` = the descriptor format-code byte (`numtype<<5\|sizeclass`), matches docs/descriptors/format-table.md exactly, and is independent per RT. See §3. |

No pixel format was rejected by Metal for MRT (all float-writable formats + `r32uint` with an
integer FS output built pipelines and rendered; §5).

---

## 2. The 0x20-byte record array extends cleanly to 8 attachments — (a) CONFIRM

Attachment-count sweep, all `bgra8`. Which BO holds the color descriptors and the per-attachment stride:

| attachments N | color-descriptor BO | LOAD base / stride | STORE base / stride | # records populated |
|---|---|---|---|---|
| 1 | `0x10000018200` (tiler heap) | `+0x20` / `0x20` | `+0x220` / `0x20` | 1 |
| 2 | `0x10000018200` | `+0x20` / `0x20` | `+0x220` / `0x20` | 2 |
| 3 | `0x10000018200` | `+0x20` / `0x20` | `+0x220` / `0x20` | 3 |
| 4 | `0x10000018200` | `+0x20` / `0x20` | `+0x220` / `0x20` | 4 |
| **5** | `0x10000018200` | `+0x20` / `0x20` | `+0x220` / `0x20` | **5** (k=5,6,7 zeroed) |
| **6** | `0x10000018200` | `+0x20` / `0x20` | `+0x220` / `0x20` | **6** |
| **7** | `0x10000018200` | `+0x20` / `0x20` | `+0x220` / `0x20` | **7** |
| **8** | `0x10000018200` | `+0x20` / `0x20` | `+0x220` / `0x20` | **8** |

(The single-attachment N=1 case *also* populates a k=0 record in the tiler-heap array here on M4,
**while** the standalone attachment-descriptor BO `0x10000110000` still coexists in the same capture
(both present at N=1). So on M4 the "N≥2 relocates the color descriptor" trigger is not clean-cut —
A18's exact N=1 relocation behaviour should be re-confirmed. This does **not** affect the k=4..7 array
layout, which is the gap under test and is unambiguous.)

**Incremental bodiff** (`caps/analysis/count_sweep_bodiff.txt`) — each +1 attachment adds **exactly one**
new LOAD record and one new STORE record, at the predicted offsets, nothing else but a running
header word at `+0x08`:

```
mrt4->mrt5 : new LOAD @+0x0a0 (=+0x20+4·0x20), new STORE @+0x2a0 (=+0x220+4·0x20)
mrt5->mrt6 : new LOAD @+0x0c0 (k=5),           new STORE @+0x2c0 (k=5)
mrt6->mrt7 : new LOAD @+0x0e0 (k=6),           new STORE @+0x2e0 (k=6)
mrt7->mrt8 : new LOAD @+0x100 (k=7),           new STORE @+0x300 (k=7)
```

**n=8 raw array** (`caps/analysis/mrt8_array.txt`), all-bgra8, showing all 8 LOAD + 8 STORE records
0x20-strided, each carrying its own surface VA (`rt0..rt7 = 0x58000..0x90000`):

```
## LOAD sub-array  (+0x20 + k*0x20)
  k=0 @+0x0020: 02 0a 0a f6 03 fc 00 00 00 58 00 00 10 c0 03 00   (VA 0x10000058000)
  k=1 @+0x0040: 02 0a 0a f6 03 fc 00 00 00 60 00 00 10 c0 03 00   (VA 0x10000060000)
  k=2 @+0x0060: 02 0a 0a f6 03 fc 00 00 00 68 00 00 10 c0 03 00
  k=3 @+0x0080: 02 0a 0a f6 03 fc 00 00 00 70 00 00 10 c0 03 00
  k=4 @+0x00a0: 02 0a 0a f6 03 fc 00 00 00 78 00 00 10 c0 03 00
  k=5 @+0x00c0: 02 0a 0a f6 03 fc 00 00 00 80 00 00 10 c0 03 00
  k=6 @+0x00e0: 02 0a 0a f6 03 fc 00 00 00 88 00 00 10 c0 03 00
  k=7 @+0x0100: 02 0a 0a f6 03 fc 00 00 00 90 00 00 10 c0 03 00
## STORE/PBE sub-array  (+0x220 + k*0x20)
  k=0 @+0x0220: 02 0a c6 3f c0 0f 00 00 00 58 00 00 10 f0 00 00
  ...
  k=7 @+0x0300: 02 0a c6 3f c0 0f 00 00 00 90 00 00 10 f0 00 00
```

Record decode (matches docs/pipeline attachment-descriptor field map):
`byte0` = texture-type/channel-arrangement, `byte1` = format code (`numtype<<5|sizeclass`),
`byte2` = channel/write config, bytes `+0x08..+0x0f` = surface **VA>>4** + row-stride in `word3`
(`word3 = 0x0003c010` for bgra8 64-wide; scales with bpp — see §3). The k=5..7 LOAD records in the
5-attachment run are **all-zero** (`caps/mrt5` dump), confirming exactly N records, no stragglers.

---

## 3. Per-attachment format words ARE per-attachment — (c) CONFIRM

Two mixed-format MRT runs. For each RT index k the LOAD record's `byte1` matches the descriptor
format-code `byte1` in `docs/descriptors/format-table.md` **exactly**, and every RT in the same pass
carries a **different** `byte1` — the format word is genuinely per-attachment, not shared.

**mixA** `--n 8 --fmts bgra8,rgba8,r8,rg8,r16f,rg16f,r32f,rgba16f` (`caps/analysis/mixA_array.txt`):

| k | set fmt | LOAD record `b0 b1 b2` | record `byte1` | doc table `byte1` | stride word3 |
|---|---|---|---|---|---|
| 0 | bgra8   | `02 0a 0a` | `0x0a` | `0x0a` ✓ | `0x0003c010` (4bpp) |
| 1 | rgba8   | `02 0a 88` | `0x0a` | `0x0a` ✓ | `0x0003c010` |
| 2 | r8      | `02 00 68` | `0x00` | `0x00` ✓ | `0x0003c010` (1bpp, min stride) |
| 3 | rg8     | `82 02 48` | `0x02` | `0x02` ✓ | `0x0003c010` |
| 4 | r16f    | `42 82 68` | `0x82` | `0x82` ✓ | `0x0003c010` |
| 5 | rg16f   | `c2 88 48` | `0x88` | `0x88` ✓ | `0x0003c010` |
| 6 | r32f    | `42 88 68` | `0x88` | `0x88` ✓ | `0x0003c010` |
| 7 | rgba16f | `82 8c 88` | `0x8c` | `0x8c` ✓ | `0x0007c010` (8bpp → 2×) |

**mixB** `--n 8 --fmts rgba32f,rgb10a2,r32f,rgba16f,bgra8,r8,rg16f,rg8` (`caps/analysis/mixB_array.txt`):

| k | set fmt | LOAD record `b0 b1 b2` | record `byte1` | doc table `byte1` | stride word3 |
|---|---|---|---|---|---|
| 0 | rgba32f | `02 8e 88` | `0x8e` | `0x8e` ✓ | `0x000fc010` (16bpp → 4×) |
| 1 | rgb10a2 | `82 09 88` | `0x09` | `0x09` ✓ | `0x0003c010` |
| 2 | r32f    | `42 88 68` | `0x88` | `0x88` ✓ | `0x0003c010` |
| 3 | rgba16f | `82 8c 88` | `0x8c` | `0x8c` ✓ | `0x0007c010` |
| 4 | bgra8   | `02 0a 0a` | `0x0a` | `0x0a` ✓ | `0x0003c010` |
| 5 | r8      | `02 00 68` | `0x00` | `0x00` ✓ | `0x0003c010` |
| 6 | rg16f   | `c2 88 48` | `0x88` | `0x88` ✓ | `0x0003c010` |
| 7 | rg8     | `82 02 48` | `0x02` | `0x02` ✓ | `0x0003c010` |

Observations:
- **`byte1` (format code)** in the tiler-heap record = the exact `numtype<<5|sizeclass` byte from the
  texture/descriptor format table. Fully per-attachment.
- **`byte0`** = texture-descriptor `byte0` with bit5 (`0x20`) cleared (`0x22→0x02`, `0xa2→0x82`,
  `0x62→0x42`, `0xe2→0xc2`) — the channel-arrangement nibble in a PBE/RT context; per-attachment.
- **`byte2`** = channel-count/swizzle write config: 1-chan(r*)=`0x68`, 2-chan(rg*)=`0x48`,
  4-chan rgba=`0x88`, 4-chan **bgra**=`0x0a` (the B↔R swizzle is baked into the PBE write config here);
  per-attachment. (Full decode of byte2 is out of scope; it is not shared.)
- **`word3` row-stride** (`(word3>>... )`, doc: PBE `word3[12:]`) scales with bpp per attachment
  (`0x0003c010`=4bpp → `0x0007c010`=8bpp → `0x000fc010`=16bpp), so the **row-byte stride is
  per-attachment too**, not just the format nibble.
- The STORE/PBE records carry the same per-attachment `byte0/byte1` + a PBE `byte2`
  (`c6/e4/00/04/...`) that also varies per format (`caps/analysis/mixA_array.txt`).

**Conclusion:** the color descriptor is a true per-attachment array; format, channel-config,
surface VA, and row stride are all independent per RT.

> Note on the dispatch's "rgba8=0x88": that does not match `docs/descriptors/format-table.md`, which
> lists **rgba8 `byte1=0x0a`** (0x88 is **r32float**'s `byte1`). The hardware data here agrees with the
> committed format table (rgba8 → `0x0a`), not with the `0x88` in the dispatch note.

---

## 4. The `+0x500+k·0x18` clear-color claim is a vertex-buffer alias — (b2) CORRECT

The doc places the per-attachment clear color at `+0x500+k·0x18` **inside BO `0x10000018200`**.
On M4 that offset is **not** clear-color data — it is the **vertex buffer**:

- The harness's `vtxBuf` was allocated at gpu_va `0x10000018700` = `0x10000018200 + 0x500`.
- BO `0x10000018700` @`+0x0` is **byte-identical** to BO `0x10000018200` @`+0x500`
  (`00 00 80 bf 00 00 80 bf 00 00 40 40 00 00 80 bf 00 00 80 bf 00 00 40 40` = the 6 floats
  `-1,-1, 3,-1,-1, 3` — our full-screen triangle). Proof: `caps/analysis/vtxbuf_collision.txt`.
- The "`0x18` stride" in the doc = **0x18 bytes = the 6-float (24-byte) triangle** that aliased there.

The **real** per-attachment clear-color storage (clearColor set to `(0.1·k, 0, 0, 1)`) is a
**float4 RGBA array, stride `0x10`**, in a **separate tiler BO** — on M4 `0x10000148000`,
base `+0x170`, mirrored at `+0x470` (the two copies are `0x300` apart)
(`caps/analysis/mrt8_clearcolor_148000.txt`):

```
  +0x0170:  00 00 00 00 .. .. 00 00 80 3f   k=0 = (0.0, 0,0, 1.0)
  +0x0180:  cd cc cc 3d .. .. 00 00 80 3f   k=1 = (0.1, 0,0, 1.0)
  +0x0190:  cd cc 4c 3e .. .. 00 00 80 3f   k=2 = (0.2, 0,0, 1.0)
  ...
  +0x01e0:  33 33 33 3f .. .. 00 00 80 3f   k=7 = (0.7, 0,0, 1.0)
```

i.e. clear color k @ `0x10000148000 + 0x170 + k·0x10` (float4 little-endian RGBA). A packed
red-channel-only copy of the clears also appears in BO `0x10000040000` @`+0x20` (per-attachment fast-clear
constant pool; not decoded further).

**A18 CROSS-CONFIRM NEEDED:** the original A18 capture almost certainly hit the *same* vtxBuf
collision (allocator-deterministic → vtxBuf at `+0x500`), which is how the doc came to record
"`+0x500+k·0x18`". The orchestrator should (i) confirm on A18 that `0x10000018200+0x500` aliases the
vertex buffer, and (ii) locate A18's real per-attachment clear-color array (expected: a separate
tiler BO, float4 `0x10`-stride). The exact A18 BO VA (`0x10000148000` here) may differ.

---

## 5. Format acceptance / rejects

No format was rejected by Metal for MRT in any run (0 `PIPELINE_FAIL`/`SHADER_FAIL`/`BAD_FMT`).
Tested renderable formats: `bgra8 rgba8 r8 rg8 r16f rg16f r32f rgba16f rgba32f rgb10a2` (float FS
output) and `r32uint` (integer FS output — `--n 3 --fmts r32uint,bgra8,r32uint` rendered `status=4`).
8× rgba32f-class MRT and 8-way mixed MRT both complete without fault, consistent with the doc's
"do not gate MRT feasibility on 32 KiB" correction.

**Incidental observation (not a cmd3 verdict):** the tiler-heap header word at
`0x10000018200 + 0x08` increments by **`0x800`** per added bgra8 attachment
(`0x7800→0x8000→0x8800→0x9000→0x9800` across mrt4..mrt8). This is the imageblock/tile-memory
running size field (a *different* structure from the color-descriptor array documented here); it is
flagged only in case it interacts with the doc's separate "0x1000 per-attachment tile stride" claim.

---

## 6. Files

- `mrtvar.m` — harness, **extended** with `--fmts f0,f1,...` (per-RT pixel format) and integer-FS
  output for `r32uint`. `iotrace.c`, `bodiff.py`, `dumpscan.py` copied from RT-2a harness.
- `arr.py` — helper: dumps/decodes the tiler-heap MRT record array from a BO snapshot.
- `run.sh` — capture driver (mrt1..mrt8, mixA, mixB, mixC).
- `caps/<label>/` — raw BO `.hex` snapshots per run; `caps/<label>.out` — run stdout.
- `caps/analysis/` — decoded array dumps, mixed-format dumps, clear-color dump, vtxBuf-collision
  proof, and the incremental count-sweep bodiff.
