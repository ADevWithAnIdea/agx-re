#include <metal_stdlib>
using namespace metal;
// isolate: rsqrt (half), one-arg SFU
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = rsqrt(a[i]);
}
