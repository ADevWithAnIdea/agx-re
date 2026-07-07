# EXP-0014 Results — GRAPHICS (draw) command stream, first pass

**TL;DR.** On A18 Pro / G17P / macOS 26.6, a Metal *draw* is submitted through the **same
shared-memory + doorbell IOKit path as compute** (EXP-0009/-0011: no graphics-specific
"submit" selector), but it builds a much larger control-stream: **~20 extra registered
BOs** vs compute, split across two address regions. By change-one-Metal-parameter diffing
of the registered GPU BOs (`dvar.m` harness + `bodiff.py`/`bograph.py`), the framing and
key fields are located:

* The **tiler (TA) work** is a **VDM draw-command stream** in BO `gpu_va 0x18000`
  (firmware-context region): a header + a run of **USC bind pairs** (each = a control word
  + a GPU address into the fixed-function state pool) terminated by a **draw-primitive
  command** carrying *primitive type* (+0x65), *vertex count* (+0x68) and *instance count*
  (+0x6c); an `0xc0000000` terminator ends the record. Indexed draws switch the opcode
  `0x61c4→0x61f2` and add an index-buffer pointer + index count.
* The **fragment (3D) work** is a **render-target / attachment descriptor** in BO
  `gpu_va 0x10000110000`: chained **0x300-byte segments**, each holding the color
  attachment's **pixel-format code** (+0x22) and **clear color** (4 floats at +0x170).
* **Viewport** is a block of transform floats in BO `gpu_va 0x68000` (+0x910), pointed to
  from the VDM stream (`0x68900`).
* **Fixed-function state** (depth, raster line/point, blend) is a pool of small packets in
  BO `gpu_va 0x58000`, bound into the draw by the VDM's USC bind pairs.
* **Shaders**: unlike compute's single `shaderVA>>6` in the CDM record, the draw path
  references shaders indirectly. Vertex + fragment machine code lives in BO
  `gpu_va 0x10000000000`; Metal's auxiliary TBDR programs (tile load/store/clear/ZLS) live
  in BO `gpu_va 0x10000088000`. The **USC binding program** `gpu_va 0x10000130000` carries
  the register/config words. Changing *either* shader changes exactly
  `{0x10000000000 (code), 0x10000130000 (USC)}`.

All findings are **DATA-TRACE**: bytes crossing the userspace↔kernel boundary from our own
Metal draw. Nothing was learned from Apple code. Shader-code identification reuses the
constant-program stub validated against **our own** `shdump` output in EXP-0011 (OWN-SHADER).

Every field marked **HW-clean** below is a single-word diff produced by changing exactly one
Metal parameter with a byte-identical baseline elsewhere (noise floor is **zero** across all
37 deterministically-paired control BOs — `raw/analysis/diff_base2.txt`, see §0).

---

## 0. Method & determinism

`dvar.m` is the render analogue of EXP-0011's `cvar.m`: a minimal triangle draw (own MSL
vertex+fragment pipeline, vertex buffer, offscreen render target) whose every submission
parameter is a CLI flag. The render target is **buffer-backed** (`[MTLBuffer
newTextureWithDescriptor:offset:bytesPerRow:]`, HW-accepted for a linear RT) so its GPU VA
is printable (`rtBuf = 0x10000058000`). `run.sh` captures a change-one-parameter matrix under
the `iotrace` interposer; `cdiff.sh` restricts `bodiff` to the control-plane BOs.

**Determinism / noise floor.** The GPU-VM allocator is deterministic across runs: `base` vs a
byte-for-byte re-run `base2` differs in **0 words** across all 37 paired control BOs (the
only "diff" bodiff reports is an artifact of two distinct `gpu_va=0x0` pseudo-BOs — a sel-5
page and the low heap alias — colliding in bodiff's pair-by-VA; both are non-control). One
field, `0x10000130000 +0x534`, changed only on the very first capture (`base`) and is
identical for `base2` and every variant → a **per-first-run counter/timestamp, not a
parameter** (confirmed: `base2` vs `vp32` = 0 there). It is excluded everywhere below.

---

## 1. Draw BO set and the two address regions

A draw registers **~39 BOs** (80× resource-map sel-9) vs compute's ~13 (60× sel-9); the
IOKit mechanism is otherwise identical (`raw/analysis/selhist.txt`). The control plane lives
in **two GPU-VA regions**:

### Firmware / queue-context region (VAs < `0x10000000000`)
These low BOs are the command lists the tiler/3D engines read. They do **not** appear for
compute (compute's control lived at `0x100000b0000+`).

| gpu_va | size | role (this experiment) |
|---|---|---|
| **`0x18000`** | 0x8000 | **VDM / tiler draw-command stream** (§2) |
| `0x28000`,`0x38000`,`0x48000` | 0x8000 | mostly-zero context blocks; `0x48000` is a USC-bind target |
| **`0x58000`** | 0x8000 | **3D fixed-function state pool** (depth/raster/blend packets) (§5) |
| **`0x68000`** | 0x88e0 | **viewport / tiling context** (viewport transform @ +0x910) (§4) |

### Resource / heap region (VAs ≥ `0x10000000000`)

| gpu_va | size | role |
|---|---|---|
| **`0x10000000000`** | 0x10000 | **shader machine code** (our VS+FS) + USC data — 6 constant-program stubs (§6) |
| `0x10000018000..1a600` | 0x20000 windows | resource heap sub-allocs (our vtxBuf @ `0x18700`, idxBuf @ `0x18800`) |
| `0x10000040000` | 0x10000 | draw-count control (changes for indexed / 2-draw) |
| **`0x10000058000`** | 0x4000 | **our render target** (64×64×4, fully written = `rtBuf`) |
| **`0x10000088000`** | 0x74000 | **auxiliary TBDR shader pool** (tile load/store/clear/ZLS) — 20 constant-program stubs |
| **`0x10000100000`** | 0x8000 | **vertex-attribute / resource table** — points at vtxBuf (+0xa0) (§2) |
| **`0x10000110000`** | 0x8000 | **3D render-target / attachment descriptor** (format, clear) (§3) |
| `0x10000120000` | 0x8000 | fragment pipeline state (blend flag; receives the Z-store program under `--depth`) |
| **`0x10000130000`** | 0x8000 | **USC / shader-binding program** (register/config words) (§6) |
| `0x10000140000` | 0x100000 | tiler parameter / geometry output heap (large, sparse) |

**TA (tiler) vs 3D (fragment) split**, from which parameters land where:
* **Tiler/TA control** = VDM stream `0x18000` (primitive/vertex/instance/index) + viewport
  `0x68000` + vertex-attribute table `0x10000100000` + tiler param heap `0x10000088000/140000`.
* **Fragment/3D control** = attachment descriptor `0x10000110000` (format/clear) + FF-state
  pool `0x58000` (depth/raster/blend) + fragment state `0x10000120000`.

---

## 2. VDM / tiler draw-command stream — BO `0x18000` (HW-clean)

Raw baseline (`raw/hexdumps/base_lo_18000.hex`), one triangle, 3 verts, 1 instance:

```
+0x00: 4000002e             header (0x40000000 flag | 0x2e length-in-words)
+0x08: 00000001             (=1)
+0x0c: 00004800             state/USC alloc size  (grows to 0x4c00 under --depth and --w128; §5)
+0x10: 00000808
+0x1c..+0x60: USC BIND PAIRS  (control-word, GPU-address) — addresses into the FF-state pool:
        (0x500,0x58000)(0x700,0x5801c)(0x700,0x58030)(0x500,0x5804c)
        (0xa00,0x68900)  <-- pointer to the VIEWPORT block (0x68000+0x900, §4)
        (0x300,0x58060)(0x200,0x5806c)(0x200,0x48000)
+0x64: 61c40600            DRAW-PRIMITIVE command:  opcode 0x61c4 | primitive-type byte
+0x68: 00000003            vertexCount = 3
+0x6c: 00000001            instanceCount = 1
+0x74: c0000000            terminator
```

Change-one-parameter (`raw/hexdumps/key_diffs.txt`):

| parameter | field | evidence |
|---|---|---|
| **primitive type** | byte at **+0x65** | triangle=`0x06`, line=`0x01`, point=`0x00`, tri-strip=`0x09` |
| **vertex count** | **+0x68** (u32) | 3→6 |
| **instance count** | **+0x6c** (u32) | 1→4 |
| **indexed draw** | opcode **+0x64** `0x61c4→0x61f2`, **+0x70** = index-buffer VA low (`0x18800` = our idxBuf), **+0x74** = index count, **+0x78** = instance count | whole packet reshapes; index ptr HW-correlated |

The `--two` capture (a 2nd pipeline in one encoder) appends a second, structurally identical
record after the first's terminator (`raw/hexdumps/vdm_two_second_draw.txt`): bind pairs then
`0x61c40600` / vtxCount / instCount / `0xc0000000` — confirming the record framing.

The **vertex-attribute table** `0x10000100000` holds the fetch pointers: `+0xa0 →
0x10000018700` (= our vtxBuf VA, HW-correlated via `bograph`), plus heap pointers at
+0x30/+0x38 that track allocation shifts under `--indexed`.

---

## 3. Render-target / attachment descriptor — BO `0x10000110000` (3D) (HW-clean)

Chained **0x300-byte segments** (`raw/hexdumps/base_3d_attachment_110000.hex`); each segment
is one color-attachment phase (load/render/store), with a self-pointer at +0x00 (stored as
`(low32, 0x00000100)` 64-bit split) and the descriptor at +0x20:

| field | offset (per segment) | evidence |
|---|---|---|
| **pixel-format code** | byte at **+0x22** | BGRA8=`0x0a`, RGBA8=`0x88` (`fmt_rgba8` diff: `f60a0a02→f6880a02` at +0x20/+0x320/+0x620) |
| **clear color** (RGBA floats) | **+0x170..+0x17c** | `--cr 1` → +0x170 = `0x3f800000` (1.0f); baseline A=1.0 already at +0x17c ✓ |

The segment also references the FF-state pool (`0x00058000` at +0x8c8) and carries a `0x6f`
program id (+0x604 under `--w128`). The RT surface itself (our `0x10000058000`) is referenced
as `(low32=0x00058000, high=0x100)`.

---

## 4. Viewport / RT-size — BO `0x68000` (HW-clean)

The viewport is the **only** control change for `--vpw/--vph`; it is transform floats at
`0x68000 + 0x910` (`raw/hexdumps/base_lo_68000.hex`), pointed to from the VDM (`0x68900`):

```
+0x910: 32.0   +0x914: 32.0   +0x918: 32.0   +0x91c: -32.0   (base, viewport 0..64)
+0x920: 0.0    +0x924: 1.0                                    (depth range near/far)
```
= {scale/translate ≈ w/2, h/2, w/2, **-h/2** (Y-flip)}. HW-clean:
* `--vpw 32 --vph 32` → all four → {16, 16, 16, **-16**} (= new w/2, h/2, …).
* `--w 128 --h 128` (RT+viewport) → {64, 64, 64, **-64**}, **and** +0x904/+0x908 grow
  `0x80000001/1 → 0x80000003/3` (a tile-count that scales with RT dimensions).

RT-*dimension* change also bumps a state-size field in the VDM (`0x18000 +0x0c`:
`0x4800→0x4c00`) and in the FF-state pool (`0x58000 +0x14`: `0x4c19→0x5019`). Clear color and
pixel format do **not** touch `0x68000` (they are in the 3D descriptor, §3) — clean separation.

---

## 5. Fixed-function state pool — BO `0x58000` (HW-clean framing)

A pool of small state packets (some delimited by `0x0e` bytes), each bound into the draw by a
VDM USC-bind pair (§2). Located by one-parameter diffs (`raw/hexdumps/key_diffs.txt`):

| state | field(s) in `0x58000` | evidence |
|---|---|---|
| **raster line/point mode** | +0x54/+0x58 top nibble; +0x34/+0x50 | tri=`0x07e00000`, line=`0x17e00000`, point=`0x47e00000` (nibble 0/1/4) |
| **depth test/write** | +0x38/+0x40 (`0x07200f00→0x01000f00`), +0x34, +0x14 | `--depth` |
| **blend** | +0x08 (`0x4c0→0x500`), +0x50 (`0x200→0x20000200`); flag also at `0x10000120000 +0x45` bit 0x80 | `--blend` |

Full bit-decode of each packet is deferred (follow-up); the packet *pool location and the
per-state field offsets* are established.

---

## 6. Shader referencing (Task 1)

**Draw does NOT use compute's single `shaderVA>>6` launch word.** Instead:

* **Machine code** for our vertex + fragment shaders is in BO `0x10000000000` — it contains
  **6** copies of the AGX constant-program stub `03000700 02000000 …` validated in EXP-0011
  (our VS, FS, plus a few Metal helper programs). Metal's **auxiliary TBDR programs** (tile
  load/store, clear, ZLS) sit in the big BO `0x10000088000` (**20** stubs).
* The **USC binding program** `0x10000130000` carries the register/config words (the depth
  capture shows `0x00880000` at +0x04 — the *same* register-config encoding seen in the
  compute CDM record, EXP-0011).
* **Proof they are the shader BOs**: making the vertex shader big (`--vshader big`) *or* the
  fragment shader big (`--fshader big`) changes **exactly** `{0x10000000000, 0x10000130000}`
  and nothing else (`raw/analysis/diff_vbig.txt`, `diff_fbig.txt`).

So the two shaders are bound through the **USC bind pairs** in the VDM stream (§2) →
FF-state/USC blocks, not by a direct pointer in the draw command. The exact word that encodes
each shader's entry address (the graphics analogue of `shaderVA>>6`) is **not yet isolated**
within the USC/state blocks — flagged as the top follow-up.

---

## 7. What is opaque / recommended next

**Established (HW-clean):** BO set + TA/3D split; VDM record framing + primitive/vertex/
instance/index fields; viewport transform floats + depth range; RT pixel-format code and clear
color in the chained attachment descriptor; the state-pool location and per-state (raster/
depth/blend) field offsets; shader-code and USC-binding BO identities.

**Still opaque:**
1. The exact **shader-entry word** (graphics `shaderVA>>6` analogue) inside the USC program /
   state blocks, and how VS vs FS entries are distinguished.
2. **USC bind-pair grammar** — the meaning of the control words (`0x500/0x700/0xa00/…`) and
   the full layout of each `0x58000` state packet (depth compare func, blend factors/ops,
   raster fill/cull) at the bit level.
3. The **attachment-descriptor** remaining fields (+0x24/+0x28/+0x2c: stride/dims/tile config;
   the meaning of the 3 chained segments = load/render/store phases).
4. The **tiler parameter buffer** `0x10000088000/0x10000140000` (geometry/PPP heap) internals.
5. **ZLS / partial-render**: `--depth` restructures `0x10000110000/120000/130000` (adds a Z
   load/store program); isolate the depth-attachment descriptor and the ZLS control.

**Recommended next experiments:** (a) decode the `0x58000` state packets bit-by-bit
(depth-compare/blend-factor sweeps, one enum at a time); (b) isolate the shader-entry word via
a `--pad` VA-shift sweep like EXP-0011's shader-pointer proof; (c) decode the attachment
descriptor dims/stride by RT-size/format sweeps with allocation held constant; (d) MSAA /
depth-only / multiple-render-target probes for the TBDR follow-ups.

## Established facts → docs
- Draw command-stream framing, VDM fields, viewport/RT/clear/state field locations →
  `docs/cmdstream/` (graphics section) → add rows to `PROVENANCE.md` (DATA-TRACE, EXP-0014).

## Follow-ups
See §7. Deliverables: `dvar.m`, `run.sh`, `cdiff.sh`, `shptr.py`, `raw/` (analysis text, curated
diffs, trimmed control-BO hex dumps).
