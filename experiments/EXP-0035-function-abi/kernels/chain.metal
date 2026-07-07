// EXP-0035 D: nested calls, recursion, return-address preservation.
// CLEAN-ROOM: OUR OWN MSL.
#include <metal_stdlib>
using namespace metal;

__attribute__((noinline)) static float leaf(float x){ return x*2.0f + 1.0f; }

// mid() calls leaf TWICE -> its own return address must survive across the inner
// calls (tests whether the link/return-address is saved to scratch across nested calls).
__attribute__((noinline)) static float mid(float x){ return leaf(x) + leaf(x*3.0f); }

kernel void k_chain(device const float*A[[buffer(0)]],device float*O[[buffer(1)]],
                    uint i[[thread_position_in_grid]]){ O[i]=mid(A[i]); }

// Recursion probe (MSL is expected to REJECT recursion; a compile error is itself
// the finding that recursion is not supported / depth is statically bounded).
__attribute__((noinline)) static float rec(float x, int n){
    if (n <= 0) return x;
    return rec(x*1.1f, n-1);
}
kernel void k_rec(device const float*A[[buffer(0)]],device const int*N[[buffer(1)]],
                  device float*O[[buffer(2)]],uint i[[thread_position_in_grid]]){
    O[i]=rec(A[i], N[i]);
}
