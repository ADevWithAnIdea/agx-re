// several independent fp32->fp16 converts to force distinct destination registers
#include <metal_stdlib>
using namespace metal;
kernel void p_f2h_multi(device half* o [[buffer(0)]],
                        device const float* a [[buffer(1)]],
                        uint i [[thread_position_in_grid]]) {
    half h0 = half(a[i*4+0]);
    half h1 = half(a[i*4+1]);
    half h2 = half(a[i*4+2]);
    half h3 = half(a[i*4+3]);
    // keep all four live so they land in different registers
    o[i*4+0] = h0; o[i*4+1] = h1; o[i*4+2] = h2; o[i*4+3] = h3;
}
