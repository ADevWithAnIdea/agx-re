// EXP-0174 authored probe kernels.
//
// Purpose: provoke the compiler into emitting members of the low-nibble-3
// compact family (`n3_mov` / `mov_zext16` / `frame_marker`), so that this
// experiment has REAL compiled instances to use as POSITIVE CONTROLS beside its
// fully generated encodings. The generated arms do not depend on these; they
// exist so that "the form we generated behaves like the form the compiler
// emits" is a checkable statement rather than an assumption.
//
// CLEAN-ROOM: every line here is our own MSL. The only machine code inspected is
// what the public `newLibraryWithSource:` API compiles FROM THIS FILE.
#include <metal_stdlib>
using namespace metal;

// 16-bit zero-extend: the HW-validated `X3 00 00 01` member (EXP-0013/0161).
kernel void k_zext(device uint* out [[buffer(0)]],
                   device uint* in  [[buffer(1)]],
                   uint tid [[thread_position_in_grid]]) {
    ushort s = (ushort)in[tid];
    out[tid] = (uint)s;
}

// Four independent zero-extends: the "parallel-extend diff" shape EXP-M4-13
// used to prove byte0's high nibble is the destination register.
kernel void k_zext4(device uint4* out [[buffer(0)]],
                    device uint4* in  [[buffer(1)]],
                    uint tid [[thread_position_in_grid]]) {
    uint4 v = in[tid];
    out[tid] = uint4((uint)(ushort)v.x, (uint)(ushort)v.y,
                     (uint)(ushort)v.z, (uint)(ushort)v.w);
}

// Half <-> float packing: the "half-pack" role the descriptor names.
kernel void k_halfpack(device uint* out [[buffer(0)]],
                       device float* in [[buffer(1)]],
                       uint tid [[thread_position_in_grid]]) {
    half2 h = half2((half)in[tid], (half)in[tid + 1]);
    out[tid] = as_type<uint>(h);
}

// A value that must survive an out-of-line call: provokes the frame marker and,
// around it, ordinary compact moves.
static float noinline_helper(float a, float b) [[noinline]] { return a * b + a; }
kernel void k_call(device float* out [[buffer(0)]],
                   device float* in  [[buffer(1)]],
                   uint tid [[thread_position_in_grid]]) {
    float a = in[tid];
    float b = in[tid + 1];
    out[tid] = noinline_helper(a, b) + noinline_helper(b, a);
}

// A long-lived value crossing a divergent region -- the classic place a compiler
// needs a register-to-register copy.
kernel void k_livecopy(device uint* out [[buffer(0)]],
                       device uint* in  [[buffer(1)]],
                       uint tid [[thread_position_in_grid]]) {
    uint a = in[tid];
    uint b = a;
    if (in[tid + 1] > 100u) { b = a + 7u; }
    out[tid] = a + b;
}

// A bitcast, which is a pure move at the machine level.
kernel void k_bitcast(device uint* out [[buffer(0)]],
                      device float* in [[buffer(1)]],
                      uint tid [[thread_position_in_grid]]) {
    out[tid] = as_type<uint>(in[tid]);
}
