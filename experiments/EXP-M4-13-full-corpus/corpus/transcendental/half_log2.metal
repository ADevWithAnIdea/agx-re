#include <metal_stdlib>
using namespace metal;
// isolate: log2 (half), one-arg SFU
kernel void k(device half* o[[buffer(0)]], device const half* a[[buffer(1)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = log2(a[i]);
}
