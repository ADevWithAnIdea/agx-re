#include <metal_stdlib>
using namespace metal;
constant bool USE_ALT [[function_constant(0)]];
constant int MODE [[function_constant(1)]];
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int v=a[i];
    if(USE_ALT){ v = (MODE==2) ? v*v : v+MODE; }
    else { v = v ^ 0x5A5A; }
    o[i]=v;
}
