#include <metal_stdlib>
using namespace metal;
// OPT-05/06: can ONE compare/select instruction choose between two ARBITRARY register values
// (not merely materialize a Boolean 0/1), for FP32, signed I32, and unsigned I32, across every
// equality/relational condition NIR needs (eq, ne, lt, le, gt, ge)? Each (type, condition) pair
// is its own kernel function so the compiled body for that exact condition can be inspected in
// isolation (no runtime branch/switch on the condition itself -- that would test something
// different: a runtime-selected condition, not a fixed compare op). `A`/`B` are runtime,
// non-Boolean, mutually distant sentinel values (never 0/1) so a correct readback of A-or-B
// proves genuine arbitrary-value selection, not accidental boolean-shaped output.
//
// select(falseValue, trueValue, predicate) is MSL's ternary-select builtin.

#define MAKE_F32(NAME, OP) \
kernel void k_sel_f32_##NAME(device float* A [[buffer(0)]], device float* B [[buffer(1)]], \
                              device float* ca [[buffer(2)]], device float* cb [[buffer(3)]], \
                              device float* out [[buffer(4)]], uint gid [[thread_position_in_grid]]) { \
    out[gid] = select(B[gid], A[gid], (bool)(ca[gid] OP cb[gid])); \
}

#define MAKE_I32(NAME, OP) \
kernel void k_sel_i32_##NAME(device int* A [[buffer(0)]], device int* B [[buffer(1)]], \
                              device int* ca [[buffer(2)]], device int* cb [[buffer(3)]], \
                              device int* out [[buffer(4)]], uint gid [[thread_position_in_grid]]) { \
    out[gid] = select(B[gid], A[gid], (bool)(ca[gid] OP cb[gid])); \
}

#define MAKE_U32(NAME, OP) \
kernel void k_sel_u32_##NAME(device uint* A [[buffer(0)]], device uint* B [[buffer(1)]], \
                              device uint* ca [[buffer(2)]], device uint* cb [[buffer(3)]], \
                              device uint* out [[buffer(4)]], uint gid [[thread_position_in_grid]]) { \
    out[gid] = select(B[gid], A[gid], (bool)(ca[gid] OP cb[gid])); \
}

MAKE_F32(eq, ==) MAKE_F32(ne, !=) MAKE_F32(lt, <) MAKE_F32(le, <=) MAKE_F32(gt, >) MAKE_F32(ge, >=)
MAKE_I32(eq, ==) MAKE_I32(ne, !=) MAKE_I32(lt, <) MAKE_I32(le, <=) MAKE_I32(gt, >) MAKE_I32(ge, >=)
MAKE_U32(eq, ==) MAKE_U32(ne, !=) MAKE_U32(lt, <) MAKE_U32(le, <=) MAKE_U32(gt, >) MAKE_U32(ge, >=)
