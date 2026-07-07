#include <metal_stdlib>
using namespace metal;

// ---- Task 3: non-leaf frame prologue (0x6f) + 0x07 link save/restore ----
// A non-leaf callee (a function that itself calls another out-of-line function)
// must preserve its return address around the inner call. EXP-0035 inferred:
// 6f.. prologue + 07.. link save/restore + 8f 12 ret. Reproduce a call chain.

// leaf callee (no frame): returns a+b. -> 8f 02 54 00 (leaf ret)
static float leaf_add(float a, float b) __attribute__((noinline));
static float leaf_add(float a, float b) { return a + b; }

// leaf callee 2: a*b
static float leaf_mul(float a, float b) __attribute__((noinline));
static float leaf_mul(float a, float b) { return a * b; }

// NON-leaf callee: calls leaf_add and leaf_mul -> must save/restore link.
// -> 6f prologue, 07 link save/restore around each call, 8f 12 ret.
static float mid(float a, float b) __attribute__((noinline));
static float mid(float a, float b) {
    float s = leaf_add(a, b);   // inner call 1
    float p = leaf_mul(a, b);   // inner call 2
    return s + p;               // (a+b) + (a*b)
}

// main calls the non-leaf mid().
kernel void k_chain(device const float* a [[buffer(0)]],
                    device const float* b [[buffer(1)]],
                    device float* out      [[buffer(2)]],
                    uint gid [[thread_position_in_grid]]) {
    out[gid] = mid(a[gid], b[gid]);
}

// baseline: main calls a single LEAF helper (no non-leaf frame).
static float leaf_only(float a, float b) __attribute__((noinline));
static float leaf_only(float a, float b) { return a + b; }
kernel void k_leaf(device const float* a [[buffer(0)]],
                   device const float* b [[buffer(1)]],
                   device float* out      [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = leaf_only(a[gid], b[gid]);
}

// deeper: main -> outer(non-leaf) -> mid2(non-leaf) -> leaf. Two nested frames.
static float leaf2(float a, float b) __attribute__((noinline));
static float leaf2(float a, float b) { return a + b; }
static float mid2(float a, float b) __attribute__((noinline));
static float mid2(float a, float b) { return leaf2(a, b) * 2.0f; }
static float outer(float a, float b) __attribute__((noinline));
static float outer(float a, float b) { return mid2(a, b) + 1.0f; }
kernel void k_deep(device const float* a [[buffer(0)]],
                   device const float* b [[buffer(1)]],
                   device float* out      [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = outer(a[gid], b[gid]);
}

// high-pressure NON-leaf: spills to scratch AND calls -> larger 0x6f frame.
static float leaf3(float a, float b) __attribute__((noinline));
static float leaf3(float a, float b) { return a + b; }
static float bigmid(float a, float b) __attribute__((noinline));
static float bigmid(float a, float b) {
    // many live temporaries to force a big scratch frame around the call
    float t0=a*1.1f, t1=a*1.2f, t2=a*1.3f, t3=a*1.4f, t4=a*1.5f, t5=a*1.6f;
    float u0=b*2.1f, u1=b*2.2f, u2=b*2.3f, u3=b*2.4f, u4=b*2.5f, u5=b*2.6f;
    float s = leaf3(a, b);   // out-of-line call in the middle of the live range
    return s + t0+t1+t2+t3+t4+t5 + u0+u1+u2+u3+u4+u5;
}
kernel void k_bigframe(device const float* a [[buffer(0)]],
                       device const float* b [[buffer(1)]],
                       device float* out      [[buffer(2)]],
                       uint gid [[thread_position_in_grid]]) {
    out[gid] = bigmid(a[gid], b[gid]);
}
