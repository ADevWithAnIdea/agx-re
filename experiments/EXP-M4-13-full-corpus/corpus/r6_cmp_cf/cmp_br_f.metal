#include <metal_stdlib>
using namespace metal;
// FLOAT compares feeding a real divergent branch.
#define K(NM,OP) kernel void NM(device float* o[[buffer(0)]], device const float* a[[buffer(1)]], device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ \
    float acc=0; \
    if (a[i] OP b[i]) { for(int k=0;k<int(b[i]);k++) acc += a[i]*float(k); o[i]=acc; return; } \
    o[i]=7; }
K(f_lt,<)
K(f_gt,>)
K(f_le,<=)
K(f_ge,>=)
K(f_eq,==)
K(f_ne,!=)
