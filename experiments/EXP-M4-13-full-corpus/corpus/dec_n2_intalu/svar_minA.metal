#include <metal_stdlib>
using namespace metal;
// srcA varies: min(a,b) vs min(c,b)  (change first operand source)
kernel void m(device int* o[[buffer(0)]], device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]], device const int* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) { o[i]=min(a[i],b[i]); }
