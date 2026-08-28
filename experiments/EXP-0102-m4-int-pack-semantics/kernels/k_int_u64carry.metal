#include <metal_stdlib>
using namespace metal;

kernel void u64add(device const ulong *a [[buffer(0)]],
                    device const ulong *b [[buffer(1)]],
                    device ulong *out [[buffer(2)]],
                    uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}

kernel void u64add_expr(device const ulong *a [[buffer(0)]],
                         device const ulong *b [[buffer(1)]],
                         device const ulong *c [[buffer(2)]],
                         device ulong *out [[buffer(3)]],
                         uint gid [[thread_position_in_grid]]) {
    out[gid] = (a[gid] + b[gid]) + c[gid];
}
