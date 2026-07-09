#include <metal_stdlib>
using namespace metal;
// Tier-2 argument buffer / bindless: struct holding an array of device
// pointers + a texture array, indexed non-uniformly per lane.
struct Bindless {
    device const float* bufs[8];
    texture2d<float>    texs[8];
    uint count;
};
kernel void k(device const Bindless& args [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    uint sel = i % args.count;
    float fromBuf = args.bufs[sel][i];
    float fromTex = args.texs[sel].read(uint2(i & 7u, 0u)).x;
    out[i] = fromBuf + fromTex;
}
