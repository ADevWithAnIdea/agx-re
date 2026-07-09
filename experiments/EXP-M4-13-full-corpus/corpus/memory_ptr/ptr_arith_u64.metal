#include <metal_stdlib>
using namespace metal;
// uint64 addressing: reconstruct a device pointer from a 64-bit address held
// in a buffer, add a byte offset, and load through it (GPU-side pointers).
kernel void k(device const ulong* addrs [[buffer(0)]],
              device float* out [[buffer(1)]],
              constant ulong& byteOff [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    ulong base = addrs[i];
    device const float* p = reinterpret_cast<device const float*>(base + byteOff);
    out[i] = p[0] + p[2];
}
