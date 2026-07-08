#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device atomic_uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                  uint i[[thread_position_in_grid]]) {
    atomic_fetch_add_explicit(&o[0], a[i], memory_order_relaxed);
}
