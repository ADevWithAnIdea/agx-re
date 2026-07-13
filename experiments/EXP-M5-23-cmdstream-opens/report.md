# EXP-M5-23 — remaining OBJ-1 cmdstream/tiling opens (M5 / Apple10 / G17g)

**Device:** Apple M5 (T8142, macOS 27.0, 8 GPU cores, `AGXAcceleratorG17G`). **Method:** own-process IOKit
DATA-TRACE (`tools/iotrace`, arm64e) + change-one-Metal-parameter BO diffing + own-MSL HW-probe + own-process
self-VM scan of our own texture data. Every probe hard-timeout-wrapped. No Apple binary introspected.
Evidence: `captures/decoded-evidence.txt` + `captures/analysis.txt`. Bulk BO snapshots on device (gitignored).

## Headline
**3 of 4 resolved; 1 characterised-blocked.** Rate-map layout, mesh amplification/ICB, and USC>2 all closed;
intra-tile Morton byte-order is **not CPU-observable on M5** (root cause pinned; allocation model already
byte-for-byte confirmed). No new missing HW functionality; the one transient GPU fault was contained (no reboot).

## 1. Rasterization rate map (foveated rendering) — RESOLVED
`ratemap.m --rate 0|1`. Metal: screen 256x256 -> **physicalSizeForLayer = 224x224** (real foveation);
`parameterBufferSizeAndAlign = {0xc030, 4}`; `copyParameterDataToBuffer` fills the screen<->physical rate table.
- **Tile-count follows PHYSICAL size** (decisive): `0x68000+0x9c4 = 0x80000000|(ceil(physW/32)-1)` = `0x80000006`
  (rate) vs `0x80000007` (screen); `+0x9c8` = 6 vs 7. So with a rate map the tiler rasterises at the physical
  resolution and the M5 tile-count words (docs `0x68000+0x9c4/+0x9c8`) carry the physical dims.
- **Bound-rate-map field:** tiler stream `0x18000+0x38` = `0x40`->`0xc180`; `+0x24` (UVS/size) `0x5800`->`0x5e00`.
- **Parameter data** (client BO): per-axis fixed-point rate-factor zone pairs (`ffffff00`/`00ebff00`) + scale
  header, 0xc030 B. Rate-map data BOs (zone/rate arrays) appear only with `--rate 1`.

## 2. Vertex amplification + payload-heavy mesh + full ICB — RESOLVED
**Amplification** (`amp.m`, count 1->2, 2-layer array RT in both, VS `[[amplification_id]]`->layer):
- `0x18000+0x30` = `0`->`1` and `0x58000+0x160` = `0`->`1` (amplification-active / factor-1, mirrored).
- **PPP** `0x58000+0x158` gains **bits[27:24]=0xd** (`0x00190000`->`0x0d190000`); store-class `+0x128`
  `0x4c0`->`0x7c0` (extra RT view outputs). Per-view routing reuses the documented layer machinery
  (`render_target_array_index`, PPP bit20). M5 caps at count 2 (3 = `supportsVertexAmplificationCount:` NO).

**Payload-heavy multi-object mesh** (`meshpayload.m`, min vs heavy=payload48/obj4x2/V64P32/TPT32):
- **Object-grid dims inline in the mesh-grid-dispatch record:** `0x18000+0xac` = objGridX (1->4),
  `+0xb0` = objGridY (1->2). Mesh threads/tg at `+0x44` low byte (3->32); `maxPrim-1` at `+0x40` (`0x1f`=31);
  packed config `+0x4c` (9->0x81).
- **The A18 `0x100000f8000` BO has NO M5 equivalent** — absent for min AND heavy mesh; grid dims + config are
  inlined in `0x18000`, UVB stays in the tiler heap. No CDM BO (single graphics submit). Both STATUS=4.
  (Resolves EXP-M5-13/EXP-M5-10 open: "0x100000f8000's M5 role for complex meshes" = none.)

**Full ICB** (`icb.m`, `executeCommandsInBuffer`, draw N=1 vs 4):
- **Command count** `0x18000+0x04` = N (1->4) (mirror at `+0x58`). N inline draw records each carrying the
  **direct** draw opcode **`0x69c4`** (not indirect `0x6c04`) at file-off `0x1aa/0x1ee/0x232/0x276` (stride 0x44).
  Structurally identical to A18 (A18 uses `0x61c4`). Clean isolated re-run STATUS=4.

## 3. Intra-tile Morton byte order — BLOCKED on M5 (root cause characterised)
`mortondraw.m` / `texscan.m` write texel(x,y)=`(y<<16)|x` and try to read the raw twiddled backing. On M5 the
raw backing is **not CPU-observable** by any route:
- **iotrace sel-9:** a standalone uncompressed (ShaderWrite) StorageModeShared texture backing is not registered
  via resource-map selector 9 (unlike A18/EXP-0017) — the raw value `0x00020003` appears in **zero** captured
  BOs (draw-store and compute-store).
- **heap-placed texture:** heap backing IS captured, but M5 stores heap textures lossless-**compressed** even
  with ShaderWrite (0x800 aux; content is the HW codec, not raw Morton).
- **self-VM scan** (reading our own texture's data): the full 36864 distinct texel values never appear
  contiguously in any CPU-readable region (best window RW 383, incl. RO 3688, of 36864). `getBytes` de-twiddles
  on a GPU/driver path; the twiddled bytes never materialise in CPU-visible linear memory.

The **allocation** model (tile edge T per bpp, page-granule G, mult-of-T padding, aux=numTexels/32) is already
byte-for-byte confirmed (EXP-M5-10) — a direct consequence of the tiled-Morton layout — so the Morton structure
is strongly corroborated; the exact within-tile permutation stays **inherited from A18** (`docs/tiling/README.md`
section 1.1), now with the read-back blocker's root cause pinned (supersedes EXP-M5-10's "interposer didn't snapshot").

## 4. USC graphics buffer slots > 2 — RESOLVED
`usc.m` (1 tex + 1 samp + K buf). FS Tier-2 arg buffer `0x10000250000`: buffer VAs are **inline 8-byte slots at
`+0x610 + k*8`** (high32 `0x00000100`), confirmed **k=0..3** (buf[0]`..cd00`, buf[1]`..ce00`, buf[2]`..cf00`,
buf[3]`..d500`). The texture/sampler-array pointers (`+0x600/+0x608`) shift forward as buffers are added; **no
switch to an indirect form beyond 2** — the inline-VA list simply extends. All STATUS=4.

## Fault behaviour
One transient GPU fault (first combined sweep, mesh_heavy/ICB region) discarded 3 submits as innocent victims +
errored one; **GPU recovery contained it, no host reboot** (`macvdmtool` not needed); all isolated re-runs
STATUS=4. M5 fault recovery is contained — a first-class data point.

## Deliverables
`docs/cmdstream/README-M5-deltas.md` (+section Rasterization rate map, +section Vertex amplification, +section
Full ICB; resolved mesh object-grid + `0x100000f8000`=none + USC buffer-slot >2). `docs/tiling/README-M5-deltas.md`
(Morton open item updated with root cause). Scripts in `scripts/`; evidence in `captures/`.

## Clean-room attestation
Own-process DATA-TRACE only; the interposer wraps the public IOKit C API from our own arm64e dylib and logs
non-copyrightable command-buffer/descriptor bytes our own Metal process registered. The self-VM scan reads OUR
OWN process memory holding OUR OWN texture's data (the same non-copyrightable layout bytes a data-trace logs).
All MSL is ours, runtime-compiled. No Apple binary disassembled/introspected. Every decoded field traces to
observed bytes; unresolved items listed as open with the mechanism that blocks them.
