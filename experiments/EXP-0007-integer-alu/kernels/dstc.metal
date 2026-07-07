#include <metal_stdlib>
using namespace metal;

kernel void k(device const int *a [[buffer(0)]],
              device const int *b [[buffer(1)]],
              device int *out [[buffer(2)]],
              device int *o2  [[buffer(3)]],
              device int *o3  [[buffer(4)]],
              uint gid [[thread_position_in_grid]]) {
    int va = a[gid]; int vb = b[gid];
    out[gid] = va + vb; o2[gid] = va; o3[gid] = vb;
}
