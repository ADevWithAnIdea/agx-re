#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o[[buffer(0)]], device const float* f[[buffer(1)]],
              device const int* n[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = float(int(f[i])) + float(uint(f[i])) + float(n[i]) + float(uint(n[i]));
}
