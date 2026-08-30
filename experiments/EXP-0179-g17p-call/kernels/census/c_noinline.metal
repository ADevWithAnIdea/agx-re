// EXP-0179 census: explicit no-inline spellings. Expect an out-of-line CALL.
// CLEAN-ROOM: our own MSL.
#include <metal_stdlib>
using namespace metal;

// C03 GNU attribute spelling (the spelling EXP-0035/EXP-0038 used).
__attribute__((noinline))
static float h_gnu(float a, float b) { return a * b + 1.0f; }
kernel void k_noinline_gnu(device const float* A [[buffer(0)]],
                           device const float* B [[buffer(1)]],
                           device float* O [[buffer(2)]],
                           uint i [[thread_position_in_grid]]) {
    O[i] = h_gnu(A[i], B[i]);
}

// C04 C++11 attribute spelling.
[[gnu::noinline]]
static float h_cxx(float a, float b) { return a * b + 3.0f; }
kernel void k_noinline_cxx(device const float* A [[buffer(0)]],
                           device const float* B [[buffer(1)]],
                           device float* O [[buffer(2)]],
                           uint i [[thread_position_in_grid]]) {
    O[i] = h_cxx(A[i], B[i]);
}

// C05 two call sites to the SAME noinline helper: pins the call/return target
// against two different return addresses.
__attribute__((noinline))
static float h_two(float a, float b) { return a + b; }
kernel void k_twocall(device const float* A [[buffer(0)]],
                      device const float* B [[buffer(1)]],
                      device float* O [[buffer(2)]],
                      uint i [[thread_position_in_grid]]) {
    float x = h_two(A[i], B[i]);
    O[i] = h_two(x, B[i]);
}

// C06 noinline VOID helper writing through a device pointer (no return value).
__attribute__((noinline))
static void h_void(device float* o, float a, float b) { *o = a - b; }
kernel void k_noinline_void(device const float* A [[buffer(0)]],
                            device const float* B [[buffer(1)]],
                            device float* O [[buffer(2)]],
                            uint i [[thread_position_in_grid]]) {
    h_void(&O[i], A[i], B[i]);
}

// C07 noinline helper returning float4 -> multi-component return (P0.8 gap G11).
__attribute__((noinline))
static float4 h_vec(float a, float b) { return float4(a + b, a - b, a * b, a / b); }
kernel void k_noinline_vec4(device const float* A [[buffer(0)]],
                            device const float* B [[buffer(1)]],
                            device float4* O [[buffer(2)]],
                            uint i [[thread_position_in_grid]]) {
    O[i] = h_vec(A[i], B[i]);
}

// C08 noinline helper returning a struct by value.
struct Pair { float u; int v; };
__attribute__((noinline))
static Pair h_pair(float a, int b) { Pair p; p.u = a * 2.0f; p.v = b + 7; return p; }
kernel void k_noinline_struct(device const float* A [[buffer(0)]],
                              device const int* B [[buffer(1)]],
                              device float* O [[buffer(2)]],
                              uint i [[thread_position_in_grid]]) {
    Pair p = h_pair(A[i], B[i]);
    O[i] = p.u + float(p.v);
}

// C09 12-argument noinline helper -> argument-register overflow probe.
__attribute__((noinline))
static float h_many(float a, float b, float c, float d, float e, float f,
                    float g, float h, float p, float q, float r, float s) {
    return a + b + c + d + e + f + g + h + p + q + r + s;
}
kernel void k_manyargs(device const float* A [[buffer(0)]],
                       device float* O [[buffer(1)]],
                       uint i [[thread_position_in_grid]]) {
    O[i] = h_many(A[12*i+0], A[12*i+1], A[12*i+2], A[12*i+3], A[12*i+4], A[12*i+5],
                  A[12*i+6], A[12*i+7], A[12*i+8], A[12*i+9], A[12*i+10], A[12*i+11]);
}
