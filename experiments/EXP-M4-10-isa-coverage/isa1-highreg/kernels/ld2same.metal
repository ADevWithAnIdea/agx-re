#include <metal_stdlib>
using namespace metal;

// Two loads from the SAME buffer into two different registers, then combine
// so neither load is eliminated. Isolates the device_load destination register
// field (base_slot identical for both loads => no buffer-address confound).
kernel void k(device const float* a [[buffer(0)]],
              device float* o        [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    float x = a[2*i];
    float y = a[2*i + 1];
    o[i] = x - y*1000.0f;   // asymmetric so we can tell x from y
}
