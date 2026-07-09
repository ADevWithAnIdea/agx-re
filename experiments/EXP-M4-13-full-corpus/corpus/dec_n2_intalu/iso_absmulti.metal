#include <metal_stdlib>
using namespace metal;
kernel void m(device int* o[[buffer(0)]],
              device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]],
              device const int* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    int r=0; for(int k=0;k<6;k++){ r+=abs(a[i+k]-b[i+k]); } o[i]=r;
}
