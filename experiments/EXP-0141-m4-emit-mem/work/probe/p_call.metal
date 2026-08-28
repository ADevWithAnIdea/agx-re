#include <metal_stdlib>
using namespace metal;
[[visible]] uint helper(uint x, device uint* p);
kernel void k(device uint* o [[buffer(0)]], device const uint* a [[buffer(1)]],
              device uint* s [[buffer(2)]], uint tid [[thread_position_in_grid]]) {
    uint v = a[tid];
    uint r = 0;
    while (v > 0) { r = helper(r + v, s); v >>= 1; }
    o[tid] = r;
}
