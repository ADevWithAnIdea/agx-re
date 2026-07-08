#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], device const int* in [[buffer(1)]],
              uint gid [[thread_position_in_grid]]){
  int x = in[0];        // distinct value 111
  int y = in[1];        // distinct value 222
  out[0]=x; out[1]=y;   // store#0 reads reg(x); store#1 reads reg(y)
}
