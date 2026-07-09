#include <metal_stdlib>
using namespace metal;
// Isolate the 06 02 SFU/range-reduction marker word emitted alongside sin.
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = fast::sin(a[i]);
}
