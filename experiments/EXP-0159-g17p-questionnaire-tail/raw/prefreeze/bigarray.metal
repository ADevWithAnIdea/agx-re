#include <metal_stdlib>
using namespace metal;
struct AB { array<texture2d<uint>, 1000001> tex [[id(0)]]; };
kernel void k(constant AB& ab [[buffer(0)]], constant uint& idx [[buffer(1)]], device uint* out [[buffer(2)]]) {
  out[0] = ab.tex[idx].read(uint2(0,0)).x;
}
