#include <metal_stdlib>
using namespace metal;
kernel void k(device int4* o[[buffer(0)]], device const int4* a[[buffer(1)]], device const int4* b[[buffer(2)]], uint i[[thread_position_in_grid]]){
    int4 va=a[i], vb=b[i];
    o[i]=select(va, vb, va>vb);
}
