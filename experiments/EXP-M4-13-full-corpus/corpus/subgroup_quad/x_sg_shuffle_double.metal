#include <metal_stdlib>
using namespace metal;
kernel void k(device double* o[[buffer(0)]], device const double* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    double v=a[i];
    o[i] = simd_shuffle(v, 0);
}
