#include <metal_stdlib>
using namespace metal;
// Eight distinct functions, FULLY runtime index (a[gid] % 8). The compiler cannot
// devirtualize/inline a runtime selection over 8 candidates -> forces a real
// out-of-line INDIRECT call through the visible_function_table.
[[visible]] uint g0(uint x){ return x + 10u; }
[[visible]] uint g1(uint x){ return x + 11u; }
[[visible]] uint g2(uint x){ return x + 12u; }
[[visible]] uint g3(uint x){ return x + 13u; }
[[visible]] uint g4(uint x){ return x + 14u; }
[[visible]] uint g5(uint x){ return x + 15u; }
[[visible]] uint g6(uint x){ return x + 16u; }
[[visible]] uint g7(uint x){ return x + 17u; }
kernel void k(device uint* out[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              visible_function_table<uint(uint)> vft[[buffer(2)]],
              uint gid[[thread_position_in_grid]]){
    out[gid] = vft[a[gid] & 7u](a[gid]);
}
