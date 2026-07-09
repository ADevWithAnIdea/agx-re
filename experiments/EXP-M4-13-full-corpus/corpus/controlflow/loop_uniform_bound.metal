#include <metal_stdlib>
using namespace metal;
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], constant uint& cnt[[buffer(2)]], uint i[[thread_position_in_grid]]){
    int s=0;
    for(uint j=0;j<cnt;j++) s += a[i] + int(j);
    o[i]=s;
}
