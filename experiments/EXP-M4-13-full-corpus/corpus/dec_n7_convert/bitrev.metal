#include <metal_stdlib>
using namespace metal;
kernel void cvt(device uint* o [[buffer(0)]], device const uint* ib [[buffer(1)]], uint i [[thread_position_in_grid]]) {
    uint a = ib[i];
    o[i] = reverse_bits(a);
}
