#include <metal_stdlib>
using namespace metal;
// Large footprint; output is the SUM of two high-register values -> forces a
// falu2/fadd (or iadd) reading r64+. With n=1 => out[0]=in[68]+in[69].
kernel void k(device float* out [[buffer(0)]],
              device const float* in [[buffer(1)]],
              constant uint& n [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
  float a[70];
  for (int k=0;k<70;k++) a[k]=in[k];
  for (uint i=1;i<n;i++){ float t=in[i]; for(int k=0;k<70;k++) a[k]=a[k]*t+a[(k+1)%70]; }
  out[0]=a[68]+a[69];
}
