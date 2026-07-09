// texture_sample corpus: texture metadata queries across 2d/3d/array/ms/cube (incl. LOD-arg width).
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device uint* o[[buffer(0)]],
                   texture2d<float> t2[[texture(0)]],
                   texture3d<float> t3[[texture(1)]],
                   texture2d_array<float> ta[[texture(2)]],
                   texture2d_ms<float> tm[[texture(3)]],
                   texturecube<float> tc[[texture(4)]],
                   uint i[[thread_position_in_grid]]) {
    uint w  = t2.get_width(2);          // width at mip level 2
    uint h  = t2.get_height();
    uint d  = t3.get_depth();
    uint n  = t2.get_num_mip_levels();
    uint as = ta.get_array_size();
    uint ns = tm.get_num_samples();
    uint cw = tc.get_width();
    o[i] = w + h + d + n + as + ns + cw;
}
