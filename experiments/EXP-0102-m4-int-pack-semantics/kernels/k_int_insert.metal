#include <metal_stdlib>
using namespace metal;

kernel void ins(device const uint *base [[buffer(0)]],
                 device const uint *val [[buffer(1)]],
                 device const uint *off [[buffer(2)]],
                 device const uint *cnt [[buffer(3)]],
                 device uint *out [[buffer(4)]],
                 uint gid [[thread_position_in_grid]]) {
    out[gid] = insert_bits(base[gid], val[gid], off[gid], cnt[gid]);
}
