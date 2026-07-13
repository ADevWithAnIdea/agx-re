# EXP-M5-22 HW splice-and-observe (Apple M5 / G17g, agxrender3 argument-buffer render)

## OBJ-1: argument-buffer texture index = preamble byte `0xa0 + index` (main op index-agnostic)
Bind a Tier-2 argument buffer of 4 distinct-colored 1x1 textures at indices 0..3
(RED/GREEN/BLUE/YELLOW). Shader f_ab0 (`return tt.tex[0].sample(s,uv)`) -- the SAME
machine code for every index (f_ab0..f_ab7 _agc.main byte-identical). Splice the single
preamble index byte and read back the pixel:

  idx0 (byte=0xa0) -> rgba 1.000,0.000,0.000  RED     *** tt.tex[0] ***
  idx1 (byte=0xa1) -> rgba 0.000,1.000,0.000  GREEN   *** tt.tex[1] ***
  idx2 (byte=0xa2) -> rgba 0.000,0.000,1.000  BLUE    *** tt.tex[2] ***
  idx3 (byte=0xa3) -> rgba 1.000,1.000,0.000  YELLOW  *** tt.tex[3] ***

=> the arg-buffer texture slot is selected ENTIRELY by the preamble `0xa0+index`
   immediate; the main-body m5_tex sample op encodes NOTHING about the index. A driver
   emits a sample of ANY bound slot by setting this preamble immediate (equivalently:
   loading the descriptor from arg_base + index*stride). HW-observed pixel per index.
   Faults: none. Device healthy throughout.

## OBJ-1 direct-binding cross-check (compile-only byte-diff)
f_tex2 (2 direct [[texture(N)]]): t0 sample byte+6=0x60, t1 byte+6=0x68 -> the EXP-M5-17
`tex_slot = 0x60 + 0x08*slot` holds for the small implicit binding table (slots 0/1).
f_tex8 (8 direct): byte+4 (descriptor selector) pairs 0xc9/0x51/0xd9/0x41 -- NON-linear
in slot -> dense direct bindings load descriptors into compiler-allocated registers.
