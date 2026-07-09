// OWN-SHADER. Isolate half bitcasts / pack-unpack (as_type between half and int bits).
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]],
              device const uint* u[[buffer(1)]],
              device const half2* hv[[buffer(2)]],
              uint i[[thread_position_in_grid]]) {
    // bit reinterpretation across the fp16 lane boundary
    half2  h2 = as_type<half2>(u[i]);        // u32 bits -> 2x f16
    uint   p  = as_type<uint>(hv[i]);        // 2x f16 -> u32 bits
    ushort s  = as_type<ushort>(hv[i].x);    // f16 -> u16 bits
    half   hb = as_type<half>(ushort(u[i])); // u16 bits -> f16
    o[i] = p ^ as_type<uint>(h2) ^ uint(s) ^ as_type<ushort>(hb);
}
