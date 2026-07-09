#include <metal_stdlib>
using namespace metal;
kernel void m(device int* o[[buffer(0)]],
              device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]],
              device const int* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i]= max(a[i],b[i]) + min(a[i+1],b[i+1]) + max(a[i+2],c[i+2]) + min(a[i+3],c[i+3]);
}
