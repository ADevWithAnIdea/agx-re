#include <metal_stdlib>
using namespace metal;
// Three-arg callee. vs c_2arg: reveals the 3rd argument register slot.
[[visible]] uint f(uint x, uint y, uint z){ return x + y + z; }
kernel void k(device uint* out[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              device const uint* b[[buffer(3)]],
              visible_function_table<uint(uint,uint,uint)> vft[[buffer(2)]],
              uint gid[[thread_position_in_grid]]){
    out[gid] = vft[0](a[gid], gid, b[gid]);
}
