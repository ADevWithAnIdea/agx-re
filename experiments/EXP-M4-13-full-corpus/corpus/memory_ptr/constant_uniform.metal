#include <metal_stdlib>
using namespace metal;
// constant-space load with a UNIFORM (threadgroup-invariant) index — candidate
// for promotion to uniform registers / a distinct uniform-load path.
struct P { uint sel; float m[16]; };
kernel void k(constant P& p [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    float u = p.m[p.sel & 15u];   // index is uniform across the grid
    out[i] = u + float(i);
}
