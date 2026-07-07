#include <metal_stdlib>
using namespace metal;

// Pure load -> store, no ALU. Isolates a device_load + device_store pair.
kernel void k(device const float *a [[buffer(0)]],
              device float *out [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid];
}
