#include <metal_stdlib>
using namespace metal;
// Baseline: one visible function, identity. Forces one out-of-line indirect call.
[[visible]] uint f(uint x){ return x; }
kernel void k(device uint* out[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              visible_function_table<uint(uint)> vft[[buffer(2)]],
              uint gid[[thread_position_in_grid]]){
    out[gid] = vft[0](a[gid]);
}
