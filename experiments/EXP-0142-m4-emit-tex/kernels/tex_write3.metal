// EXP-0142 carrier B -- three INDEPENDENT texture writes to one RGBA32Float
// target, at three distinct coordinates with three distinct colours.
//
// LIVENESS: write N's effect is the content of exactly one texel of the
// read-back target; every other texel keeps the harness's reset sentinel
// (-1,-2,-3,-4), so "the write moved", "the write changed value" and "the
// write did not happen" are three distinguishable observations at known
// addresses. Nothing else in the kernel can write texture(1).
//
// Integrity sentinel: out[0] is a plain load->store of in[b+63] on a path that
// never touches the texture unit.
//
// Clean-room: our own MSL.
#include <metal_stdlib>
using namespace metal;

kernel void k_write(texture2d<float, access::write> w [[texture(1)]],
                    device const float *in  [[buffer(0)]],
                    device float       *out [[buffer(1)]],
                    uint tid [[thread_position_in_grid]])
{
    uint b = tid * 64u;
    float4 c0 = float4(in[b+ 0], in[b+ 1], in[b+ 2], in[b+ 3]);
    float4 c1 = float4(in[b+ 4], in[b+ 5], in[b+ 6], in[b+ 7]);
    float4 c2 = float4(in[b+ 8], in[b+ 9], in[b+10], in[b+11]);
    w.write(c0, uint2(1u, 0u));
    w.write(c1, uint2(3u, 2u));
    w.write(c2, uint2(5u, 4u));
    out[0] = in[b+63];   // integrity sentinel
}
