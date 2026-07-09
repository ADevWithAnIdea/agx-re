#include <metal_stdlib>
using namespace metal;
kernel void m(device int* o[[buffer(0)]],
              device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]],
              device const int* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    int x=clamp(a[i],b[i],c[i]); int y=clamp(a[i+1],b[i+1],c[i+1]); int z=clamp(a[i+2],b[i+2],c[i+2]); o[i]=x^(y<<1)^(z<<2);
}
