#include <metal_stdlib>
using namespace metal;
// Same signature as c_id, different body (x+7). Byte-diff isolates callee body vs call site.
[[visible]] uint f(uint x){ return x + 7u; }
kernel void k(device uint* out[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              visible_function_table<uint(uint)> vft[[buffer(2)]],
              uint gid[[thread_position_in_grid]]){
    out[gid] = vft[0](a[gid]);
}
