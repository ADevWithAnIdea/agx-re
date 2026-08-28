// EXP-0140 carrier for the MOV family (get_sr / mov_imm / uniform_mov /
// reg_move_*).  Authored by us (clean-room OWN-SHADER).
//
// Why this shape:
//  * four `constant int&` arguments force the compiler to emit a
//    `_agc.main.constant_program` that preloads the UNIFORM register file
//    with values WE bind and therefore know exactly (EXP-0020 established
//    that pure-uniform expressions are hoisted into the constant program and
//    land in uniform registers).  Splicing `_agc.main` does NOT touch the
//    constant program, so the uniform file still holds our magic values --
//    that is the ground-truth oracle for `uniform_mov.usrc`.
//  * one `device int*` input plus the `device int*` output fix the
//    device_load / device_store base_slot bindings (re-derived fresh by
//    harness/baseline.py, never assumed -- EXP-0112's documented trap).
//  * the body is long enough that `_agc.main` comfortably exceeds every
//    generated probe program (the whole region is replaced per case).
#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out  [[buffer(0)]],
              device const int* mem [[buffer(1)]],
              constant int& u0 [[buffer(2)]],
              constant int& u1 [[buffer(3)]],
              constant int& u2 [[buffer(4)]],
              constant int& u3 [[buffer(5)]],
              uint gid [[thread_position_in_grid]]) {
    int acc = mem[gid];
    acc = acc * 3 + u0;
    acc = acc * 5 + u1;
    acc = acc * 7 + u2;
    acc = acc * 11 + u3;
    acc = acc * 13 + u0;
    acc = acc * 17 + u1;
    acc = acc * 19 + u2;
    acc = acc * 23 + u3;
    acc = acc * 29 + u0;
    acc = acc * 31 + u1;
    acc = acc * 37 + u2;
    acc = acc * 41 + u3;
    acc = acc * 43 + u0;
    acc = acc * 47 + u1;
    acc = acc * 53 + u2;
    acc = acc * 59 + u3;
    acc = acc * 61 + u0;
    acc = acc * 67 + u1;
    acc = acc * 71 + u2;
    acc = acc * 73 + u3;
    out[gid] = acc;
}
