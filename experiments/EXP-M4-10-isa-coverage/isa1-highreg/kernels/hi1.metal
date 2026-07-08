#include <metal_stdlib>
using namespace metal;
// K live values forced by a data-dependent loop (EXP-0020 pattern), but only ONE
// value is stored. With n=1 => out[0]=in[K-1]. The single store reads whatever
// (high) register the compiler parked a[K-1] in. Large footprint, no elimination.
kernel void k(device int* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              constant uint& n [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
  int a[70];
  for (int k=0;k<70;k++) a[k]=in[k];
  for (uint i=1;i<n;i++){ int t=in[i]; for(int k=0;k<70;k++) a[k]=a[k]*t+a[(k+1)%70]; }
  out[0]=a[69];
}
