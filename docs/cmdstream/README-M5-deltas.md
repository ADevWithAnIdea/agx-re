# M5 (Apple10 / G17g) command-stream deltas vs A18 (G17P)

Delta-form spec: "same as `cmdstream/README.md` (A18/G17P) except as noted." Source: EXP-M5-06
(own-process iotrace DATA-TRACE on M5 / T8142 / macOS 27.0, 8 GPU cores). HW-validated unless marked ⏳.
Clean-room: own-process IOKit data-trace only; no Apple binary introspected.

## Submission model — SAME
Two user clients: `IOSurfaceRoot` + **`AGXAcceleratorG17G`** (A18: `…G17P`). Shared-memory + doorbell,
no per-submit ioctl (IOKit call count invariant; compute 49 / draw 58, same as A18). Resource-map
selector 9 (in@0x38 CPU base, in@0x48 size, out@0x00 GPU VA) unchanged.

## Compute launch (CDM) descriptor `…b0000` — 0x2c-byte record, `0x40000000` terminator (SAME)
- **SAME:** shader ptr `+0x08 = shaderVA>>6`; grid(threads) `+0x10/+0x14/+0x18`; threadgroup
  `+0x1c/+0x20/+0x24` (incl. the barrier-free Metal occupancy repack, e.g. 48→64).
- **DELTA — config word `+0x00`:** the A18 always-set **bit19 base (`0x00080000`) is GONE** on M5.
  The word is `0x00000000` (clear) / **`0x00800000`** (set) — **bit23 = the same 2-tier occupancy/register
  class** as A18 (driver sets it from its register allocator's peak-GPR occupancy decision, not a `≥N` test).
- Constant undecoded words: `+0x04=0x1`, `+0x0c=0x40000001`, `+0x28=0x60000160` ⏳.

## Threadgroup-memory size — MOVED to shader BO `…90000+0x38`
A18 used `(tgmem<<2)|0x80` at shader-BO **+0x40**; on M5 +0x40 keeps only a 1-bit has-tgmem flag
(`0x40`→`0x48`). The **size is at +0x38**:

    word(+0x38) = 0x0c00000f | (fine<<11) | (coarse<<19)
      fine   = round_up(tgmem & 0x7FF, 64) / 64     (bits [11:15])
      coarse = tgmem >> 11                           (bits [19:...], bits[16:18] reserved)

HW-validated 16 B…32 KiB (sub-64 B rounds up to 64).

## Argument buffer (Tier-2) — SAME
Resource table `+0x14a0`, 8-byte slots: buffers = inline GPU VA; textures/samplers = ptr-to-descriptor
in same BO. Byte-identical to A18.

## Graphics VDM draw record — same layout, OPCODES SHIFTED +0x0800
- **DELTA:** non-indexed opcode **`0x61c4`→`0x69c4`**; indexed **`0x61f2`→`0x69f2`** (`| strip | (u32<<1)`,
  u16=`0x69f2` / u32=`0x69f4`).
- **SAME:** primitive-type byte (point`00`/line`01`/lineStrip`03`/tri`06`/triStrip`09`) at rec+0x01;
  vertexCount rec+0x04 / instanceCount rec+0x08; indexed config word `0x40000001`; restart comparand
  tracks index width (`0xffff`/`0xffffffff`).

## Viewport transform — MOVED to `0x68000+0x9d0` (A18 +0x910)
4 floats `{tx, sx, ty, sy}` with Y-flip in sy (`tx=x+w/2, sx=w/2, ty=y+h/2, sy=-h/2`). Default full-target
`{w/2,h/2,w/2,-h/2}`. Same structure, offset +0xc0.

## Fixed-function state pool `0x58000` — same fields, REORGANIZED offsets ⏳
Depth/stencil block ~`+0x134`(flags)/`+0x16c–0x174`(depth); rasterizer cull+winding at **`+0x1a8`**
(cull[1:0] none/front/back, winding bit16 CW/CCW). Not a uniform shift vs A18 (`+0x34/+0x38/+0x3c/+0x70`);
full per-bit compare-op / stencil-op / blend-flag decode is a follow-up.

## Open (next cmdstream experiments)
FF-pool per-bit decode (depth/stencil/blend enums, USC bind-pair grammar); attachment/PBE/storage-image
records + packed format word; CDM `+0x04/+0x0c/+0x28` words; sel-2 device-info struct; indirect/mesh/
tessellation records; tiling/compression per format.
