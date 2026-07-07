#include <metal_stdlib>
using namespace metal;

// Texture WRITE: write two distinct known values into a writable image at
// (0,0) and (1,0). Read back the image to confirm where the data landed.
// v[0] -> texel(0,0); v[1] -> texel(1,0).
kernel void k(texture2d<float, access::write> img [[texture(0)]],
              device const float4* v [[buffer(0)]]) {
    img.write(v[0], uint2(0,0));
    img.write(v[1], uint2(1,0));
}
