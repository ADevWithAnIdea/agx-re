#include <metal_stdlib>
using namespace metal;
kernel void k(device half2* o[[buffer(0)]], device const half2* a[[buffer(1)]],
              device const half2* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    half2 x=a[i], y=b[i];
    o[i] = half2(x.x + y.x, x.y * y.y);
}
