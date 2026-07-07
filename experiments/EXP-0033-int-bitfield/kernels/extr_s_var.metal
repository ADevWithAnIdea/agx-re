#include <metal_stdlib>
using namespace metal;

kernel void k(device const int *a [[buffer(0)]],
              device const uint *off [[buffer(1)]],
              device const uint *cnt [[buffer(2)]],
              device int *out [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = extract_bits(a[gid], off[gid], cnt[gid]);
}
