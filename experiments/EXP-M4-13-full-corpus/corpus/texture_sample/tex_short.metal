// texture_sample corpus: 16-bit integer texture read (short/ushort) — narrow integer path.
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device int4* o[[buffer(0)]],
                   texture2d<short> ts[[texture(0)]],
                   texture2d<ushort> tus[[texture(1)]],
                   uint2 g[[thread_position_in_grid]],
                   uint i[[thread_index_in_threadgroup]]) {
    short4 a  = ts.read(g);
    ushort4 b = tus.read(g);
    o[i] = int4(a) + int4(b);
}
