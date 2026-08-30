// EXP-0141 threadgroup-tile carrier. OWN MSL.
// Barrier litmus AND tg_addr_compute carrier in one.
//
// LANE 0 fills the whole tile; every OTHER lane then reads two slots. Without
// the barrier, the 224 lanes outside lane 0's own 32-lane SIMD group read
// threadgroup memory before lane 0 has written it. This shape was adopted
// after two weaker ones (`o[li]=tile[li+1]+tile[li+2]`, then
// `tile[li+128]+tile[li+37]`) FAILED to detect a neutralised barrier: with
// every lane writing its own slot, the writes retire fast enough that the
// litmus passed even with the fence spliced out, so it could not have
// falsified anything. Recorded rather than quietly swapped.
//
// o[256] is the integrity sentinel: under concurrent sibling GPU work a
// command buffer can report STATUS OK having executed nothing, and an all-zero
// readback is otherwise indistinguishable from a genuine silent zero.
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o        [[buffer(0)]],
              device const uint* a  [[buffer(1)]],
              uint tid [[thread_position_in_grid]],
              uint li  [[thread_position_in_threadgroup]])
{
    if (li == 0) o[256] = 0xA5A5A5A5u;
    threadgroup uint tile[256];
    if (li == 0) {
        for (uint i = 0; i < 256; ++i) tile[i] = a[i] + 1u;
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    o[li] = tile[(li + 128) & 255] + tile[(li + 37) & 255];
}
