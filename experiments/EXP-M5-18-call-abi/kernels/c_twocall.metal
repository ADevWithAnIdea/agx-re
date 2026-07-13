#include <metal_stdlib>
using namespace metal;
// Two sequential calls to the table. Reveals call sequencing + whether the second
// call reuses the same call-site encoding (and any frame save/restore between).
[[visible]] uint f(uint x){ return x + 7u; }
kernel void k(device uint* out[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              visible_function_table<uint(uint)> vft[[buffer(2)]],
              uint gid[[thread_position_in_grid]]){
    uint t = vft[0](a[gid]);
    out[gid] = vft[0](t);
}
