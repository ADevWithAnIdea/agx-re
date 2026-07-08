#include <metal_stdlib>
using namespace metal;
kernel void s_div(device int* o, device const int* a, device const int* b, uint g[[thread_position_in_grid]]){ o[g]=a[g]/(b[g]|1); }
kernel void s_mod(device int* o, device const int* a, device const int* b, uint g[[thread_position_in_grid]]){ o[g]=a[g]%(b[g]|1); }
