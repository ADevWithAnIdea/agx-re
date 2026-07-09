#include <metal_stdlib>
using namespace metal;
// isolate: metal::fast::rsqrt (float) — explicit precision namespace
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = fast::rsqrt(a[i]);
}
