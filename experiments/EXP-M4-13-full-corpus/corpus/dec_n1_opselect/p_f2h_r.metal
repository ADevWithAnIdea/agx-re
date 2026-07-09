#include <metal_stdlib>
using namespace metal;
// force dst register variety by chaining
kernel void p_f2h_r(device half* o[[buffer(0)]], device const float* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
  half h = half(a[i]);
  o[i] = h * half(2.0);
}
