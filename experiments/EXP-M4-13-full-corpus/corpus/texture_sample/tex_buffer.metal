// texture_sample corpus: texture_buffer read/write (float) + texture_buffer read (uint) + width.
#include <metal_stdlib>
using namespace metal;
kernel void k_main(device float4* o[[buffer(0)]],
                   texture_buffer<float> tbr[[texture(0)]],
                   texture_buffer<float,access::write> tbw[[texture(1)]],
                   texture_buffer<uint> tbu[[texture(2)]],
                   uint i[[thread_position_in_grid]]) {
    float4 v = tbr.read(i);
    tbw.write(v * 2.0, i);
    uint4 u = tbu.read(i);
    uint dim = tbr.get_width();
    o[i] = v + float4(u) + float4(dim);
}
