#include <metal_stdlib>
using namespace metal;
struct bf2{bfloat x; bfloat y;};
kernel void p_bf2add(device bfloat2* o[[buffer(0)]], device const bfloat2* a[[buffer(1)]], device const bfloat2* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=a[i]+b[i]; }
