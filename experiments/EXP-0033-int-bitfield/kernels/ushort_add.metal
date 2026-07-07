#include <metal_stdlib>
using namespace metal;

kernel void k(device const ushort *a [[buffer(0)]],
              device const ushort *b [[buffer(1)]],
              device ushort *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}
