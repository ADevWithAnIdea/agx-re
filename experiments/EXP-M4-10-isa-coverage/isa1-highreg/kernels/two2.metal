#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], device const int* in [[buffer(1)]],
              uint gid [[thread_position_in_grid]]){
  int x = in[0]*3;      // reg(x)
  int y = in[1]*5;      // reg(y), distinct
  out[0]=x; out[9]=y;
}
