// EXP-0092 numwg_probe: GLIO-A05 load_num_workgroups ABI probe.
//
// Thread (0,0,0) writes the MSL `threadgroups_per_grid` builtin (the
// compiler's num_workgroups lowering: get_sr 0xa8/a9/aa + a device_load + a
// divide per docs/isa/README.md RT-7) to out[0..2], and (for cross-checking
// against the dispatch record actually supplied) also writes the raw
// threadgroup_position_in_grid-derived thread counts is not needed here --
// grid_size (threads_per_grid, computable independently on the host from
// dispatchThreads-style calls) is intentionally NOT read; this probe isolates
// num_workgroups only.
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint3 tid  [[thread_position_in_grid]],
              uint3 tgpg [[threadgroups_per_grid]]) {
    if (tid.x == 0 && tid.y == 0 && tid.z == 0) {
        out[0] = tgpg.x;
        out[1] = tgpg.y;
        out[2] = tgpg.z;
    }
}
