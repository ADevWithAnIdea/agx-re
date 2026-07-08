#include <metal_stdlib>
using namespace metal;
kernel void k(device half* out [[buffer(0)]],
              device const half* in [[buffer(1)]],
              constant uint& n [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
  half a0 = in[gid*2+0];
  half a1 = in[gid*2+1];
  for (uint i=1;i<n;i++) {
    half t = in[i];
    a0 = fma(a0, t, a1);
    a1 = fma(a1, t, a0);
  }
  out[gid*2+0] = a0;
  out[gid*2+1] = a1;
}
