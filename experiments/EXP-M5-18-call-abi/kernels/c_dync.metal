#include <metal_stdlib>
using namespace metal;
// 8 functions returning distinct CONSTANTS (ignore the argument). Runtime index.
// Callee has no arg-derived datapath -> isolates the return-value-register move
// from the argument handling, and shows the pure ret sequence.
[[visible]] uint g0(uint x){ return 100u; }
[[visible]] uint g1(uint x){ return 101u; }
[[visible]] uint g2(uint x){ return 102u; }
[[visible]] uint g3(uint x){ return 103u; }
[[visible]] uint g4(uint x){ return 104u; }
[[visible]] uint g5(uint x){ return 105u; }
[[visible]] uint g6(uint x){ return 106u; }
[[visible]] uint g7(uint x){ return 107u; }
kernel void k(device uint* out[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              visible_function_table<uint(uint)> vft[[buffer(2)]],
              uint gid[[thread_position_in_grid]]){
    out[gid] = vft[a[gid] & 7u](a[gid]);
}
