#include <metal_stdlib>
using namespace metal;
[[visible]] uint addk(uint x, uint gid){ return x + gid + 7u; }
kernel void k(device uint* out[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              visible_function_table<uint(uint,uint)> vft[[buffer(2)]],
              uint gid[[thread_position_in_grid]]){
    out[gid] = vft[0](a[gid], gid);
}
