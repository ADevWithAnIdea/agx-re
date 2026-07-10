#include <metal_stdlib>
using namespace metal;
kernel void k(texture2d<float,access::write> w[[texture(0)]], device const float4* c[[buffer(0)]], uint2 g[[thread_position_in_grid]]){
  float4 v = c[g.x+1];
  w.write(v, g);
}
