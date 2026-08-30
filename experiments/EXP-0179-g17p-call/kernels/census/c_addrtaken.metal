// EXP-0179 census: taking the ADDRESS of a function. On a target with no
// generic function pointers this is expected to be REJECTED at compile time --
// which is itself the finding (it tells the implementation team that the only
// indirect-call surface is the visible_function_table).
// CLEAN-ROOM: our own MSL.
#include <metal_stdlib>
using namespace metal;

__attribute__((noinline)) static float fa(float a, float b) { return a + b; }
__attribute__((noinline)) static float fb(float a, float b) { return a * b; }

// C22 a local function pointer selected at runtime.
kernel void k_addrtaken(device const float* A [[buffer(0)]],
                        device const float* B [[buffer(1)]],
                        device float* O [[buffer(2)]],
                        device const uint* sel [[buffer(3)]],
                        uint i [[thread_position_in_grid]]) {
    float (*fp)(float, float) = sel[i] ? fb : fa;
    O[i] = fp(A[i], B[i]);
}
