#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]],
              device const int* a [[buffer(1)]],
              device const int* b [[buffer(2)]],
              device const uint* c [[buffer(3)]],
              uint i [[thread_position_in_grid]]) {
    out[i] = select(a[i], b[i], c[i] != 0u);
}
