// EXP-0179 census: recursion. EXP-0035 found tail recursion lowered to a LOOP
// with no self-call; mutual recursion has never been tried on this target.
// A COMPILE REJECTION is itself the finding and is recorded as one.
// CLEAN-ROOM: our own MSL.
#include <metal_stdlib>
using namespace metal;

// C12 tail self-recursion (EXP-0035 saw a loop, no call).
__attribute__((noinline))
static float rec_tail(float x, int n) {
    if (n <= 0) return x;
    return rec_tail(x * 1.1f, n - 1);
}
kernel void k_rec_tail(device const float* A [[buffer(0)]],
                       device const int* N [[buffer(1)]],
                       device float* O [[buffer(2)]],
                       uint i [[thread_position_in_grid]]) {
    O[i] = rec_tail(A[i], N[i]);
}

// C13 NON-tail self-recursion: the recursive result is used in an expression,
// so it cannot be rewritten as a simple loop without an accumulator.
__attribute__((noinline))
static float rec_nontail(float x, int n) {
    if (n <= 0) return x;
    return rec_nontail(x * 1.1f, n - 1) * 0.5f + x;
}
kernel void k_rec_nontail(device const float* A [[buffer(0)]],
                          device const int* N [[buffer(1)]],
                          device float* O [[buffer(2)]],
                          uint i [[thread_position_in_grid]]) {
    O[i] = rec_nontail(A[i], N[i]);
}
