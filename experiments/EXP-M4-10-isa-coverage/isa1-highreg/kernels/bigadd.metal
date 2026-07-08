#include <metal_stdlib>
using namespace metal;
// Large declared register footprint (pad[80] kept live via runtime n), PLUS a
// clean spliceable fadd of two loaded values. With n=1, s=0 so o[i]=a[i]+b[i].
kernel void k(device const float* a [[buffer(0)]],
              device const float* b [[buffer(1)]],
              device float* o        [[buffer(2)]],
              constant uint& n       [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
  float pad[80];
  for (int k=0;k<80;k++) pad[k] = a[gid] + float(k*7 + 1);
  float s = 0.0f;
  for (uint j=1;j<n;j++){ for (int k=0;k<80;k++) s += pad[k]*float(j); }
  float x = a[gid];
  float y = b[gid];
  o[gid] = x + y + s;
}
