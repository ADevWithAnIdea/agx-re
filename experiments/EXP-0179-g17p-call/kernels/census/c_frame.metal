// EXP-0179 census: NON-LEAF frames (a callee that itself calls). This is the
// construct EXP-0038 used and the one the split prolog/epilog contract needs.
// Authored fresh here (same idea, our own source, different bodies), so the
// census measures THIS experiment's own inputs.
// CLEAN-ROOM: our own MSL.
#include <metal_stdlib>
using namespace metal;

__attribute__((noinline)) static float lf_add(float a, float b) { return a + b; }
__attribute__((noinline)) static float lf_mul(float a, float b) { return a * b; }

// C15 non-leaf: mid() calls two leaves -> 6f prologue + 07 link save/restore.
__attribute__((noinline))
static float nl_mid(float a, float b) { return lf_add(a, b) + lf_mul(a, b); }
kernel void k_chain(device const float* A [[buffer(0)]],
                    device const float* B [[buffer(1)]],
                    device float* O [[buffer(2)]],
                    uint i [[thread_position_in_grid]]) {
    O[i] = nl_mid(A[i], B[i]);
}

// C16 leaf only -> baseline with a call but no non-leaf frame.
__attribute__((noinline)) static float lf_only(float a, float b) { return a + b; }
kernel void k_leaf(device const float* A [[buffer(0)]],
                   device const float* B [[buffer(1)]],
                   device float* O [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    O[i] = lf_only(A[i], B[i]);
}

// C17 three levels deep -> two nested non-leaf frames.
__attribute__((noinline)) static float d_leaf(float a, float b) { return a + b; }
__attribute__((noinline)) static float d_mid(float a, float b) { return d_leaf(a, b) * 2.0f; }
__attribute__((noinline)) static float d_outer(float a, float b) { return d_mid(a, b) + 1.0f; }
kernel void k_deep(device const float* A [[buffer(0)]],
                   device const float* B [[buffer(1)]],
                   device float* O [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    O[i] = d_outer(A[i], B[i]);
}

// C18 non-leaf with heavy live state across the call -> a SPILLING frame.
__attribute__((noinline)) static float s_leaf(float a, float b) { return a + b; }
__attribute__((noinline))
static float s_big(float a, float b) {
    float t0=a*1.1f,t1=a*1.2f,t2=a*1.3f,t3=a*1.4f,t4=a*1.5f,t5=a*1.6f;
    float u0=b*2.1f,u1=b*2.2f,u2=b*2.3f,u3=b*2.4f,u4=b*2.5f,u5=b*2.6f;
    float s = s_leaf(a, b);
    return s + t0+t1+t2+t3+t4+t5 + u0+u1+u2+u3+u4+u5;
}
kernel void k_bigframe(device const float* A [[buffer(0)]],
                       device const float* B [[buffer(1)]],
                       device float* O [[buffer(2)]],
                       uint i [[thread_position_in_grid]]) {
    O[i] = s_big(A[i], B[i]);
}
