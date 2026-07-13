# EXP-M5-22 — M5 texture binding-table addressing + m5_tex typed fields + image-store form

**Device:** Apple M5 / G17g / T8142. Clean-room byte-diff of own MSL + HW splice-and-observe via a new
argument-buffer render testbed (`agxrender3`, pixel readback). No Apple binary inspected. 0 faults/reboots.

## Result: a driver can now select any bound texture/sampler slot AND emit an image store.
Census strictly non-regressing (named UP both corpora, desync DOWN both); round-trip ALL PASS (device + host).

## OBJ-1 — dense slots ≥2: the byte+4 hypothesis is HW-DISPROVEN; the real mechanism is cleaner
- **Argument buffer (Tier-2 / bindless):** `tt.tex[k].sample()` for k=0..7 produces **byte-identical `_agc.main`**
  — the sample op encodes nothing about the index. The whole-text differs at **exactly one preamble byte =
  `0xa0 + index`** (linear a0…a7), in the descriptor-address op (`0f 00 03 00 a0 4c 00 <0xa0+idx>`).
- **HW pixel proof** (`agxrender3`, 4 distinct-colored textures via a real Tier-2 arg buffer, splice the preamble
  byte): idx0→RED, idx1→GREEN, idx2→BLUE, idx3→YELLOW — observed pixels, same machine code. Image-store arg-buffer
  form identical (`k_wrab0`==`k_wrab2`, differ only at `0xa0+idx`).
- **Driver rule:** select a slot by the preamble descriptor-address immediate (`0xa0+index`) / load from
  `arg_base + index·stride`; the texture op is slot-agnostic. Direct bindings: small table → byte+6
  `tex_slot`=`0x60+0x08·slot` (now typed); dense `f_tex8` byte+4 = compiler-allocated descriptor regs (raw).

## OBJ-2 — typed m5_tex fields (leader 6→8, census-safe)
Extended `m5_tex`/`m5_tex_read` leader 6→8 (8 = the min texture-op length = the image read; sample=22/gather=14
all ≥8, never over-reads). Typed real fields the assembler sets: `samp_slot`(+5[6:0]), `samp_last`(+5[7]),
`tex_slot`(+6), `coord_ctl`(+7). Verified `agxisa.py asm m5_tex_read … tex_slot=0x68` → `0f001a0040806800`. LOD
(+12) kept in prose — typing needs len≥13 which over-reads the 8-byte image read (documented tradeoff).

## OBJ-3 — the `24 80 03` form (with a correction)
- **`24 80 03` is NOT an image store** — it's a 10-byte **constant-materialisation move** (`m5_const_move`). Proof:
  `k_wrbuf` (`texture2d.write` of a *buffer*-sourced color) stores a texture with **zero** `?4 80` ops, and
  `24 80 03` appears in a trivial passthrough vertex shader (`v_pos`). Corrects the EXP-M5-16 attribution.
- **The real M5 compute image store** is an **18-byte** `m5_image_store`
  (`<fmt>5 <data> <sf> <dim> 24 <desc> a0 02 <descHi> 80 .. 8c .. 20 .. 00 01 00`). Stable 18B across 2d/3d/2d_array;
  texture = compiler-allocated descriptor (byte+5/+8), not a raw slot. Supersedes A18 `0xd7` on the M5 compute path.

## Validation
own fully-named +12 (desync −12); tp +2 (−2); round-trip ALL PASS; DB 192→194 (`m5_const_move`, `m5_image_store`).
Previously-desynced `atomics_tex_r10_w_*` + `frag_output-*__vertex` kernels now decode.

## Resolved vs raw
- **Resolved:** arg-buffer index = preamble `0xa0+idx` (pixel-proven tex[0..3]); `tex_slot`/`samp_slot`/`coord_ctl`
  typed; image-store 18B length + slot-is-descriptor; `24 80 03`=const-move correction.
- **Raw (rule 5):** dense-direct byte+4 descriptor-register allocation; image-store data/descriptor packing; LOD (+12).

## Tooling
`kernels/agxrender3.m` — argument-buffer render testbed (candidate for `tools/agxtest/`).

## Clean-room attestation
Every byte inspected/spliced is our own on-device-compiled MSL, decoded with our own fork; every OBJ-1 splice
result is a pixel observed on real M5 HW via our own `agxrender3` (public Metal API only). No Apple binary
disassembled/introspected; unresolved fields kept raw. Validated non-regressing on both corpora before delivery.
