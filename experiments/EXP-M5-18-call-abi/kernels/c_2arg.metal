#include <metal_stdlib>
using namespace metal;
// Two-arg callee. vs c_id: reveals argument-register marshalling (how the 2nd arg is placed).
[[visible]] uint f(uint x, uint y){ return x * 3u + y; }
kernel void k(device uint* out[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              visible_function_table<uint(uint,uint)> vft[[buffer(2)]],
              uint gid[[thread_position_in_grid]]){
    out[gid] = vft[0](a[gid], gid);
}
