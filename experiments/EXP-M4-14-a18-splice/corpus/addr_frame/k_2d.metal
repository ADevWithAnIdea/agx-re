#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
              uint2 g[[thread_position_in_grid]], uint2 gs[[threads_per_grid]]) {
    uint idx = g.y*gs.x + g.x;
    o[idx] = a[idx] + g.x*g.y;
}
