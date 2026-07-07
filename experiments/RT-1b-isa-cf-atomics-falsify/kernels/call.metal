// RT-1b function-call kernels (OUR OWN MSL). Falsify CALL 0f 05 (target=call+4+
// off40) / RETURN 8f (link) / calling convention (args r10+, return r10).
#include <metal_stdlib>
using namespace metal;

// --- one noinline call, distinct math so folding cannot hide it.
__attribute__((noinline)) static float helper2(float a, float b) { return a * b + 1.0f; }
kernel void one(device const float* A [[buffer(0)]], device const float* B [[buffer(1)]],
                device float* O [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    O[i] = helper2(A[i], B[i]);
}

// --- two call sites to the SAME target: off40 must differ by the call distance.
__attribute__((noinline)) static float hadd(float a, float b) { return a + b; }
kernel void twocall(device const float* A [[buffer(0)]], device const float* B [[buffer(1)]],
                    device float* O [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    float x = hadd(A[i], B[i]);
    float y = hadd(x, B[i]);
    O[i] = y;
}

// --- 3-level nested calls (return address must survive across inner calls).
__attribute__((noinline)) static float leaf(float x) { return x * 2.0f + 1.0f; }
__attribute__((noinline)) static float mid(float x)  { return leaf(x) + leaf(x * 3.0f); }
kernel void chain(device const float* A [[buffer(0)]], device float* O [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) { O[i] = mid(A[i]); }

// --- recursion -> loop lowering (statically bounded).
__attribute__((noinline)) static float rec(float x, int n) {
    if (n <= 0) return x; return rec(x * 1.1f, n - 1);
}
kernel void recur(device const float* A [[buffer(0)]], device const int* N [[buffer(1)]],
                  device float* O [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    O[i] = rec(A[i], N[i]);
}

// --- many-arg call (spill past the arg registers).
__attribute__((noinline)) static float many(float a,float b,float c,float d,float e,float f,
                                             float g,float h,float p,float q,float r,float s){
    return a+b+c+d+e+f+g+h+p+q+r+s;
}
kernel void spill(device const float* A [[buffer(0)]], device float* O [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    O[i] = many(A[12*i+0],A[12*i+1],A[12*i+2],A[12*i+3],A[12*i+4],A[12*i+5],
                A[12*i+6],A[12*i+7],A[12*i+8],A[12*i+9],A[12*i+10],A[12*i+11]);
}
