#include <metal_stdlib>
using namespace metal;
[[visible]] uint f0(uint x){ return x*3u+1u; }
[[visible]] uint f1(uint x){ return x*5u+2u; }
kernel void k(device uint* out[[buffer(0)]], device const uint* a[[buffer(1)]],
              visible_function_table<uint(uint)> vft[[buffer(2)]], uint gid[[thread_position_in_grid]]){
    out[gid] = vft[gid & 1u](a[gid]);
}
