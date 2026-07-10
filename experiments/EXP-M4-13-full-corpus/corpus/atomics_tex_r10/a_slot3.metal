#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* p0[[buffer(0)]], device uint* p1[[buffer(1)]], device uint* p2[[buffer(2)]], device atomic_uint* o[[buffer(3)]], device uint* out[[buffer(4)]], device const uint* in[[buffer(5)]], uint i[[thread_position_in_grid]]){ out[i]=atomic_fetch_add_explicit(&o[i], in[i], memory_order_relaxed); }
