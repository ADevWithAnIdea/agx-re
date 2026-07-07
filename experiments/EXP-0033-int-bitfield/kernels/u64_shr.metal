#include <metal_stdlib>
using namespace metal;

kernel void k(device const ulong *a [[buffer(0)]],
              device const uint *n [[buffer(1)]],
              device ulong *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] >> n[gid];
}
