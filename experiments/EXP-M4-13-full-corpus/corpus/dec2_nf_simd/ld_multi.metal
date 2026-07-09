#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
              device const int* n[[buffer(2)]], uint i[[thread_position_in_grid]]){
    float v0=a[i], v1=a[i+1u], v2=a[i+2u];
    int e0=n[i], e1=n[i+1u], e2=n[i+2u];
    o[i]   = ldexp(v0,e0);
    o[i+1u]= ldexp(v1,e1);
    o[i+2u]= ldexp(v2,e2);
}
