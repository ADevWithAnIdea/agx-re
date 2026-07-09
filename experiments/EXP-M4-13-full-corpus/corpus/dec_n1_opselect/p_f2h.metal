// isolated fp32->fp16 narrowing convert, single op, bracketed by load/store
#include <metal_stdlib>
using namespace metal;
kernel void p_f2h(device half* o [[buffer(0)]],
                  device const float* a [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    o[i] = half(a[i]);
}
