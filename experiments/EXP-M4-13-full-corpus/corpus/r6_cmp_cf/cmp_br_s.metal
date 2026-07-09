#include <metal_stdlib>
using namespace metal;
// signed compares feeding a REAL divergent branch (loop body defeats predication).
// operands a[i],b[i] identical across variants; only the operator changes.
#define K(NM,OP) kernel void NM(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], device const int* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ \
    int acc=0; \
    if (a[i] OP b[i]) { for(int k=0;k<b[i];k++) acc += a[i]*k; o[i]=acc; return; } \
    o[i]=7; }
K(s_lt,<)
K(s_gt,>)
K(s_le,<=)
K(s_ge,>=)
K(s_eq,==)
K(s_ne,!=)
