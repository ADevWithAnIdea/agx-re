// EXP-0179 census: MUTUAL recursion, isolated in its own file so a compile
// rejection does not take the rest of the census with it.
// CLEAN-ROOM: our own MSL.
#include <metal_stdlib>
using namespace metal;

__attribute__((noinline)) static float ping(float x, int n);
__attribute__((noinline)) static float pong(float x, int n);
__attribute__((noinline)) static float ping(float x, int n) {
    if (n <= 0) return x;
    return pong(x * 1.1f, n - 1) + 1.0f;
}
__attribute__((noinline)) static float pong(float x, int n) {
    if (n <= 0) return x;
    return ping(x * 0.9f, n - 1) - 1.0f;
}

// C14 mutual recursion.
kernel void k_mutual(device const float* A [[buffer(0)]],
                     device const int* N [[buffer(1)]],
                     device float* O [[buffer(2)]],
                     uint i [[thread_position_in_grid]]) {
    O[i] = ping(A[i], N[i]);
}
