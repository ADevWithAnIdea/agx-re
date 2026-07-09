#include <metal_stdlib>
using namespace metal;
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]],
              uint i[[thread_position_in_grid]], uint l[[thread_index_in_simdgroup]]){
    int v=a[i];
    if((l&1u)==0u){ for(int j=0;j<3;j++) v=v*3+1; }
    else { for(int j=0;j<5;j++) v=v-2; }
    o[i]=v;
}
