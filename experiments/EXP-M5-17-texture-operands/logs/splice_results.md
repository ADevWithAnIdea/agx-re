# EXP-M5-17 splice-and-observe raw results (agxrender2 fragment->pixel, Apple M5 / G17g)

All pixels read back from a 1x1 BGRA8Unorm target. `rgba_unorm` = R,G,B,A.
Each field was isolated by byte-diffing two live sample ops (select(a,b,opaque-false)
keeps both ops, defeats DCE) then spliced in the OUTPUT op ('a').

## COORD REGISTER = byte+3   (kernel f_coord, 2x2 tex: row0=RED=uvA(0.25), row1=BLUE=uvB(0.75))
op0 @110 (output 'a', samples uvA), op1 @132 (samples uvB). abs splice off = fragment _agc.main + 110 + n.
  baseline                         : rgba 1.000,0.000,0.000  RED   (a = uvA -> row0)
  op0 +3 (113) 0x00->0x04          : rgba 0.000,0.000,1.000  BLUE  *** coord switched uvA->uvB ***
  op0 +7 (117) 0x29->0x49  alone   : rgba 1.000,0.000,0.000  RED   (byte+7 INERT = scoreboard token)
  op0 +3 AND +7                    : rgba 0.000,0.000,1.000  BLUE  (byte+3 drives it)

## TEXTURE SLOT = byte+6   (kernel f_texslot, tex0=RED@slot0, tex1=GREEN@slot1, same coord)
op0 @66 (output 'a', tex0), op1 @88 (tex1).
  baseline                         : rgba 1.000,0.000,0.000  RED    (a = tex0/slot0)
  op0 +6 (72) 0x60->0x68           : rgba 0.000,1.000,0.000  GREEN  *** texture switched slot0->slot1 ***
  op1 +6 (94) 0x68->0x60           : rgba 1.000,0.000,0.000  RED    (op1 discarded -> no effect; proves op0=output)

## SAMPLER SLOT = byte+5[6:0]   (kernel f_sampaddr, uvR=1.25 out-of-range; s0=clamp->row1=BLUE, s1=repeat->row0=RED)
op0 @62 (output 'a', s0), op1 @84 (s1).
  baseline                         : rgba 0.000,0.000,1.000  BLUE   (a = s0 clamp -> row1)
  op0 +5 (67) 0x00->0x01           : rgba 1.000,0.000,0.000  RED    *** sampler switched slot0->slot1(repeat)->row0 ***
  op0 +6 (68) 0x60->0x68 (control) : STATUS CMDBUF_ERROR (contained) -- texture slot 1 UNBOUND faults;
                                     confirms byte+6 is the TEXTURE slot, distinct from byte+5 (sampler).

## LOD / BIAS IMMEDIATE = byte+12   (kernel f_lodsel, mipmapped tex: level0=RED, level1=BLUE)
op0 @66 (output 'a', level(0.0)), op1 @88 (level(1.0)).
  baseline                         : rgba 1.000,0.000,0.000  RED    (a = level 0)
  op0 +12 (78) 0x00->0x40          : rgba 0.000,0.000,1.000  BLUE   *** LOD switched level0->level1 ***
  op0 +12 (78) 0x00->0x80 (level2) : rgba 0.000,0.000,1.000  BLUE   (clamped to max level 1)
  => encoding: byte+12 = round(level * 0x40)  (Q?.6 fixed point; level 0/1/2 -> 0x00/0x40/0x80)

## SCALE confirmations (byte-diff of freshly compiled multi-resource kernels; compile-only)
  coord reg   f_coordABC 3 live coords -> byte+3 in {0x00,0x04,0x08}  (adjacent float2 -> +0x04 = reg32<<1)
  samp slot   f_samp4    4 live samplers -> byte+5[6:0] = 0,1,2,3      (dense linear index)
  tex slot    f_tex3     3 live textures -> slot0/1 = byte+6 0x60/0x68; slot>=2 also bumps byte+4 desc-bank
  LOD imm     f_lod0/1/2 level 0/1/2   -> byte+12 = 0x00/0x40/0x80

## OP SUBCLASS (byte+1) / CLASS (byte+2) from single-op kernels (rtex.metal) + compute (EXP-M5-16)
  byte+1: 0x04 explicit-LOD sample | 0x05 bias / sample_compare | 0x06 implicit-LOD sample|gather|lod_query | 0x07 register-LOD
  byte+2: 0x12 compute sample | 0x16 FRAGMENT implicit-derivative sample | 0x1a image read
  byte+9: 0x18 implicit-LOD (derivative) | 0x00 explicit-LOD / bias

## FULL LENGTHS (own-MSL, HW-observed, next-op boundary)
  fragment sample (implicit/explicit LOD/bias/reg-LOD) = 22 B
  gather                                                = 14 B
  image read                                            =  8 B
  DB tokenizes the 6-byte EMITTABLE LEADER; coord/LOD/gradient operand words fall through raw (rule 5).

## DEVICE / FAULT behaviour
  Faults CONTAINED throughout. The one intentional bad splice (unbound texture slot 1) raised a
  contained CMDBUF_ERROR; the very next dispatch succeeded (device healthy, fresh render RED/OK).
  One transient SSH auth-throttle and one transient PIPELINE_MISS, both self-cleared -- no reboot needed.
