// EXP-0122 authored kernels (OWN-SHADER / clean-room): sparse-texture residency probes.
// One thread per requested coordinate; coordinates and (for the write kernel) the pattern
// are supplied as runtime buffers so the compiler cannot fold or eliminate the access.
#include <metal_stdlib>
using namespace metal;

kernel void sparse_read_rgba8(texture2d<float, access::read> tex [[texture(0)]],
                               constant uint2* coords [[buffer(0)]],
                               device float4* out [[buffer(1)]],
                               uint tid [[thread_position_in_grid]]) {
    out[tid] = tex.read(coords[tid]);
}

kernel void sparse_write_rgba8(texture2d<float, access::write> tex [[texture(0)]],
                                constant uint2* coords [[buffer(0)]],
                                constant float4& pattern [[buffer(1)]],
                                uint tid [[thread_position_in_grid]]) {
    tex.write(pattern, coords[tid]);
}
