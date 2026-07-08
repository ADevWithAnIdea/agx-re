#include <metal_stdlib>
using namespace metal;
kernel void k_umul(device uint* o, device const uint* a, device const uint* b, uint g[[thread_position_in_grid]]){ o[g]=a[g]*b[g]; }
kernel void k_umad(device uint* o, device const uint* a, device const uint* b, device const uint* c, uint g[[thread_position_in_grid]]){ o[g]=a[g]*b[g]+c[g]; }
kernel void k_imul(device int* o, device const int* a, device const int* b, uint g[[thread_position_in_grid]]){ o[g]=a[g]*b[g]; }
