#include <metal_stdlib>
using namespace metal;
kernel void probe(device atomic_uint *flag [[buffer(0)]], device uint *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) {
    if(gid==0) atomic_store_explicit(flag,0x13579bdfu,memory_order_release);
    else out[gid]=atomic_load_explicit(flag,memory_order_acquire);
}
