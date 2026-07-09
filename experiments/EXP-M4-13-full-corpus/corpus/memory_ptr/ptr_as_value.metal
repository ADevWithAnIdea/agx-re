#include <metal_stdlib>
using namespace metal;
// Compute a device address (pointer arithmetic) and STORE the 64-bit address
// itself as data — surfaces address-generation without a following load.
kernel void k(device const float* base [[buffer(0)]],
              device ulong* outAddr [[buffer(1)]],
              device uint* idx [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    device const float* p = base + idx[i];
    outAddr[i] = reinterpret_cast<ulong>(p);
}
