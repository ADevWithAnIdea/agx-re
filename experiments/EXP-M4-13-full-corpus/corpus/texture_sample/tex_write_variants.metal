// texture_sample corpus: write to 2d / 3d / 2d_array / cube (store addressing variants).
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float4* o[[buffer(0)]],
                   texture2d<float,access::write> w2[[texture(0)]],
                   texture3d<float,access::write> w3[[texture(1)]],
                   texture2d_array<float,access::write> wa[[texture(2)]],
                   texturecube<float,access::write> wc[[texture(3)]],
                   uint3 g[[thread_position_in_grid]],
                   uint i[[thread_index_in_threadgroup]]) {
    float4 v = float4(g.x, g.y, g.z, 1.0);
    w2.write(v, g.xy);
    w3.write(v, g);
    wa.write(v, g.xy, g.z);        // array-index store
    wc.write(v, g.xy, g.z % 6);    // cube-face store
    o[i] = v;
}
