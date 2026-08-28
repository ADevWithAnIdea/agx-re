// EXP-0113 LOADFWD carrier kernel. OWN MSL. Compiles to a real
// device_load(a) -> device_load(b) -> iminmax(max) -> device_store chain
// (a genuine int max(a,b) computation, functionally verified unspliced,
// see PROGRESS.md Milestone 2) with enough spare body (extra min/add/sub
// arithmetic, all dead to the H1_LOADFWD group's own splices) that the
// compiled _agc.main region is long enough to hold a hand-built program
// with a SECOND, later consumer instruction (needed by the
// loadfwd_r*_persistence cases). Every H1_LOADFWD case replaces the
// entire _agc.main body via splice at offset 0; this kernel's own extra
// arithmetic is never executed by any such case.
#include <metal_stdlib>
using namespace metal;
kernel void k(device const int *a [[buffer(0)]],
              device const int *b [[buffer(1)]],
              device int *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    int m = max(a[gid], b[gid]);
    int n = min(a[gid], b[gid]);
    int p = m + n;
    int q = m - n;
    out[gid] = m;
    out[gid+4] = n;
    out[gid+8] = p;
    out[gid+12] = q;
}
