#include <metal_stdlib>
using namespace metal;
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], device const int* n[[buffer(2)]], uint i[[thread_position_in_grid]]){
    int s=0; int cnt=n[i];
    for(int j=0;j<cnt;j++) s+=a[j];
    o[i]=s;
}
