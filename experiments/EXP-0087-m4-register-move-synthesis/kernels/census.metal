// EXP-0087 compiler-emitted-move census kernels (OWN-SHADER). Four minimal,
// per-thread-varying (tid-indexed, so nothing collapses to the uniform data
// path) kernels, each intended to force the compiler to emit a genuine
// GPR-to-GPR register move in a different source context:
//
//   k_passthrough  -- a value simply passed through a local variable.
//   k_swap         -- a classic two-variable register swap.
//   k_loop_phi     -- a data-dependent (non-unrollable) loop whose
//                     loop-carried value is reassigned from a second buffer
//                     value on some iterations: a genuine control-flow-join
//                     (phi) merge, not an if/else (which this ISA lowers to
//                     predication/select, not a branch -- confirmed
//                     separately not to emit the move family under test).
//   k_call_marshal -- a noinline function call, to observe whether
//                     call-argument marshaling uses this move family.
//
// All four are compiled and disassembled with our own tools/shdump +
// tools/agx-isa; census.py records the full instruction stream of each and
// classifies which reg_move_* variant (if any) appears and in what role.
#include <metal_stdlib>
using namespace metal;

kernel void k_passthrough(device float* out [[buffer(0)]],
                           device const float* in [[buffer(1)]],
                           uint tid [[thread_position_in_grid]]) {
    float a = in[tid * 2u + 0u];
    float t = a;
    out[tid] = t;
}

kernel void k_swap(device float* out [[buffer(0)]],
                    device const float* in [[buffer(1)]],
                    uint tid [[thread_position_in_grid]]) {
    float a = in[tid * 2u + 0u];
    float b = in[tid * 2u + 1u];
    float tmp = a;
    a = b;
    b = tmp;
    out[tid * 2u + 0u] = a;
    out[tid * 2u + 1u] = b;
}

kernel void k_loop_phi(device float* out [[buffer(0)]],
                        device const float* in [[buffer(1)]],
                        uint tid [[thread_position_in_grid]]) {
    float a = in[tid * 3u + 0u];
    float b = in[tid * 3u + 1u];
    float r = a;
    uint n = tid & 3u;
    for (uint k = 0; k < n; k++) {
        r = b;
        b = r + in[tid * 3u + 2u];
    }
    out[tid] = r;
}

static float __attribute__((noinline)) helper_pick(float x, float y, uint sel) {
    return (sel != 0u) ? y : x;
}
kernel void k_call_marshal(device float* out [[buffer(0)]],
                            device const float* in [[buffer(1)]],
                            uint tid [[thread_position_in_grid]]) {
    float a = in[tid * 2u + 0u];
    float b = in[tid * 2u + 1u];
    out[tid] = helper_pick(a, b, tid & 1u);
}
