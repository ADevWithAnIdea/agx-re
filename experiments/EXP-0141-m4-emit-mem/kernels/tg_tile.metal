// EXP-0141 threadgroup-tile carrier. OWN MSL.
// Barrier litmus AND tg_addr_compute carrier in one: every lane writes its own
// tile slot, then (after the barrier) reads two OTHER lanes' slots. Removing or
// neutralising the barrier makes some lanes read stale zeros; the exact lane
// count is the observable. a[i] = i, so o[i] = ((i+1)&255) + ((i+2)&255).
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o        [[buffer(0)]],
              device const uint* a  [[buffer(1)]],
              uint tid [[thread_position_in_grid]],
              uint li  [[thread_position_in_threadgroup]])
{
    threadgroup uint tile[256];
    tile[li] = a[li];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[li] = tile[(li + 1) & 255] + tile[(li + 2) & 255];
}
