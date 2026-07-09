#include <metal_stdlib>
using namespace metal;
// UNSIGNED compares feeding a real divergent branch.
#define K(NM,OP) kernel void NM(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], device const uint* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ \
    uint acc=0; \
    if (a[i] OP b[i]) { for(uint k=0;k<b[i];k++) acc += a[i]*k; o[i]=acc; return; } \
    o[i]=7; }
K(u_lt,<)
K(u_gt,>)
K(u_le,<=)
K(u_ge,>=)
K(u_eq,==)
K(u_ne,!=)
