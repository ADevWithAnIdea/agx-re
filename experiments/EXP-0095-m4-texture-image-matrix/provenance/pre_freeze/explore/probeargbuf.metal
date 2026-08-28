#include <metal_stdlib>
using namespace metal;

struct AB4096 {
  array<texture2d<float>, 4096> textures [[id(0)]];
};
kernel void k_ab4096_read(constant AB4096& ab [[buffer(0)]], constant uint& idx [[buffer(1)]], device float4* o [[buffer(2)]]) {
  o[0] = ab.textures[idx].read(uint2(0,0));
}
