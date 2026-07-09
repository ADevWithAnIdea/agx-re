#include <metal_stdlib>
using namespace metal;
// Nested pointers via argument buffer: a device pointer to a struct that itself
// contains a device pointer — double indirection / pointer-chasing loads.
struct Inner { device const float* data; uint len; };
struct Outer { device const Inner* nodes; uint n; };
kernel void k(device const Outer& o [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    uint k = i % o.n;
    Inner nd = o.nodes[k];
    out[i] = nd.data[i % nd.len];
}
