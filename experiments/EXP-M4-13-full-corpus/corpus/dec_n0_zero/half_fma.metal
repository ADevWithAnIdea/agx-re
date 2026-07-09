#include <metal_stdlib>
using namespace metal;
kernel void k(device half* o [[buffer(0)]], device const half* a [[buffer(1)]], uint g [[thread_position_in_grid]]){
    half x=a[g], y=a[g+1], z=a[g+2];
    o[g] = fma(x,y,z);
}
