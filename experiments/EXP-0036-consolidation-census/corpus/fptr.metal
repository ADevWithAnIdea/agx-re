// EXP-0036 census corpus — visible_function_table indirect call (OWN-SHADER).
// A compute kernel that indirect-calls through a visible_function_table.
#include <metal_stdlib>
using namespace metal;

[[visible]] int vadd(int a, int b) { return a + b; }
[[visible]] int vmul(int a, int b) { return a * b; }

kernel void k_fptr(device int* o [[buffer(0)]],
                   device const int* a [[buffer(1)]],
                   device const int* b [[buffer(2)]],
                   device const uint* sel [[buffer(3)]],
                   visible_function_table<int(int,int)> fns [[buffer(4)]],
                   uint i [[thread_position_in_grid]]) {
    o[i] = fns[sel[i]](a[i], b[i]);
}
