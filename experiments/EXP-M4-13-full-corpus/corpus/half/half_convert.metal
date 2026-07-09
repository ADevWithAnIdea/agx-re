// OWN-SHADER. Isolate half<->{float,int,uint,short,ushort} conversions (cvt widths).
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o[[buffer(0)]],
              device const float* f[[buffer(1)]],
              device const int* si[[buffer(2)]],
              device const uint* ui[[buffer(3)]],
              device const short* ss[[buffer(4)]],
              uint i[[thread_position_in_grid]]) {
    half hf = half(f[i]);        // f32 -> f16 (down-convert, round)
    half hi = half(si[i]);       // s32 -> f16
    half hu = half(ui[i]);       // u32 -> f16
    half hs = half(ss[i]);       // s16 -> f16
    float back = float(hf);      // f16 -> f32 (up-convert)
    int   ib   = int(hi);        // f16 -> s32
    uint  ub   = uint(hu);       // f16 -> u32
    short sb   = short(hs);      // f16 -> s16
    o[i] = hf + hi + hu + hs + half(back) + half(ib) + half(ub) + half(sb);
}
