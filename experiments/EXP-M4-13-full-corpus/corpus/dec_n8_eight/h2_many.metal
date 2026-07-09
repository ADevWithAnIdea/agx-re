#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* o, device const half2* a, device const half2* b, uint i[[thread_position_in_grid]]){
    half2 acc=a[i];
    for(int k=0;k<8;k++){ acc = acc*b[i] + a[i]; }
    o[i]=acc;
}
