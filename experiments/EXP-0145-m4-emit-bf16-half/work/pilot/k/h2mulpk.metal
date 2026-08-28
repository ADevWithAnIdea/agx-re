#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]], device const half2* a [[buffer(1)]], device const half2* b [[buffer(2)]], uint g [[thread_position_in_grid]]){ half2 s=a[g]*b[g]; out[g]=as_type<uint>(s); }
