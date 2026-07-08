#include <metal_stdlib>
using namespace metal;
kernel void u_add(device uint* o, device const uint* a, device const uint* b, uint g[[thread_position_in_grid]]){ o[g]=a[g]+b[g]; }
kernel void u_sub(device uint* o, device const uint* a, device const uint* b, uint g[[thread_position_in_grid]]){ o[g]=a[g]-b[g]; }
kernel void u_mul(device uint* o, device const uint* a, device const uint* b, uint g[[thread_position_in_grid]]){ o[g]=a[g]*b[g]; }
kernel void u_div(device uint* o, device const uint* a, device const uint* b, uint g[[thread_position_in_grid]]){ o[g]=a[g]/(b[g]|1u); }
kernel void u_mod(device uint* o, device const uint* a, device const uint* b, uint g[[thread_position_in_grid]]){ o[g]=a[g]%(b[g]|1u); }
