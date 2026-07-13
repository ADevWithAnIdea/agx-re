#include <metal_stdlib>
using namespace metal;
static uint __attribute__((noinline)) helper(device const uint* a, uint i){ return a[i]*3u + 7u; }
kernel void k(device const uint* a [[buffer(0)]], device uint* out [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = helper(a, gid);
}
