#include <metal_stdlib>
using namespace metal;
// As c_dyn8 but the callee takes TWO args and returns a 2-arg expression, to expose
// argument-register marshalling at a genuine (non-inlined) indirect call site.
[[visible]] uint g0(uint x, uint y){ return x + y + 10u; }
[[visible]] uint g1(uint x, uint y){ return x + y + 11u; }
[[visible]] uint g2(uint x, uint y){ return x + y + 12u; }
[[visible]] uint g3(uint x, uint y){ return x + y + 13u; }
[[visible]] uint g4(uint x, uint y){ return x + y + 14u; }
[[visible]] uint g5(uint x, uint y){ return x + y + 15u; }
[[visible]] uint g6(uint x, uint y){ return x + y + 16u; }
[[visible]] uint g7(uint x, uint y){ return x + y + 17u; }
kernel void k(device uint* out[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              visible_function_table<uint(uint,uint)> vft[[buffer(2)]],
              uint gid[[thread_position_in_grid]]){
    out[gid] = vft[a[gid] & 7u](a[gid], gid);
}
