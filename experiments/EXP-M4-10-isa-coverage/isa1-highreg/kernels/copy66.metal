#include <metal_stdlib>
using namespace metal;
// K live ints copied in via loads, out via stores. n=1 => out[k]==in[k].
// Forces r0..r~85 allocation; each store reads a distinct live register.
kernel void k(device int* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              constant uint& n [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
  int a[66];
  for (int k=0;k<66;k++) a[k]=in[k];
  for (uint i=1;i<n;i++){ int t=in[i]; for(int k=0;k<66;k++) a[k]=a[k]*t+a[(k+1)%66]; }
  for (int k=0;k<66;k++) out[k]=a[k];
}
