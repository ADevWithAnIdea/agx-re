#include <metal_stdlib>
using namespace metal;
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]],
              constant int& flag[[buffer(2)]], constant int& mode[[buffer(3)]],
              uint i[[thread_position_in_grid]]){
    int v=a[i];
    if(flag>0){ v = (mode==1) ? v*3 : v+mode; } else { v = v - 5; }
    o[i]=v;
}
