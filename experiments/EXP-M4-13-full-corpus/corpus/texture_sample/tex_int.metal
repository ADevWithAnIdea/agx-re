// texture_sample corpus: integer texture read (int/uint) + integer gather (nearest path).
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device int4* o[[buffer(0)]],
                   texture2d<int> ti[[texture(0)]],
                   texture2d<uint> tu[[texture(1)]],
                   sampler s[[sampler(0)]],
                   device const float2* c[[buffer(1)]],
                   uint2 g[[thread_position_in_grid]],
                   uint i[[thread_index_in_threadgroup]]) {
    int4 a  = ti.read(g);
    uint4 b = tu.read(g);
    int4 gi = ti.gather(s, c[i], int2(0), component::x);
    o[i] = a + int4(b) + gi;
}
