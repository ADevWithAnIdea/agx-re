// EXP-0035 B2: constant-index indirect calls (isolate the table-slot load + call).
// CLEAN-ROOM: OUR OWN MSL.
#include <metal_stdlib>
using namespace metal;

[[visible]] float vadd(float a, float b) { return a + b; }
[[visible]] float vmul(float a, float b) { return a * b; }

// Constant table index 0 -> simplest indirect call; diff vs index 1 to find the
// slot-index encoding in the function-table load.
kernel void fp_i0(device const float*A[[buffer(0)]],device const float*B[[buffer(1)]],
                  device float*O[[buffer(2)]],
                  visible_function_table<float(float,float)> ftab [[buffer(3)]],
                  uint i[[thread_position_in_grid]]){ O[i]=ftab[0](A[i],B[i]); }

kernel void fp_i1(device const float*A[[buffer(0)]],device const float*B[[buffer(1)]],
                  device float*O[[buffer(2)]],
                  visible_function_table<float(float,float)> ftab [[buffer(3)]],
                  uint i[[thread_position_in_grid]]){ O[i]=ftab[1](A[i],B[i]); }
