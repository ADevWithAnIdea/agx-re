#include <metal_stdlib>
using namespace metal;
// 8 functions, runtime index, each returns arg XOR a distinct constant. Callee body
// derives the return value FROM the argument -> exposes arg-in / return-out registers.
[[visible]] uint g0(uint x){ return x ^ 1u; }
[[visible]] uint g1(uint x){ return x ^ 2u; }
[[visible]] uint g2(uint x){ return x ^ 3u; }
[[visible]] uint g3(uint x){ return x ^ 4u; }
[[visible]] uint g4(uint x){ return x ^ 5u; }
[[visible]] uint g5(uint x){ return x ^ 6u; }
[[visible]] uint g6(uint x){ return x ^ 7u; }
[[visible]] uint g7(uint x){ return x ^ 8u; }
kernel void k(device uint* out[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              visible_function_table<uint(uint)> vft[[buffer(2)]],
              uint gid[[thread_position_in_grid]]){
    out[gid] = vft[a[gid] & 7u](a[gid]);
}
