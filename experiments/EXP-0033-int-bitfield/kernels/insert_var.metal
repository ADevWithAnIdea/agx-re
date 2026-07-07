#include <metal_stdlib>
using namespace metal;

kernel void k(device const uint *a [[buffer(0)]],
              device const uint *b [[buffer(1)]],
              device const uint *off [[buffer(2)]],
              device const uint *cnt [[buffer(3)]],
              device uint *out [[buffer(4)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = insert_bits(a[gid], b[gid], off[gid], cnt[gid]);
}
