#include <metal_stdlib>
using namespace metal;
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int s=0;
    for(int j=0;j<8;j++) s+=a[i]*j;
    o[i]=s;
}
