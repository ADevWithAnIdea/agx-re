// EXP-0168 anchor-probe kernels — ALL AUTHORED BY US for this experiment.
//
// Each kernel is the smallest MSL we could write that makes the public Metal
// runtime compiler emit ONE instruction of a family whose `dst` (or other
// withheld) field EXP-0164 sent back to `untested`. We never inspect Apple's
// compiler or any Apple binary; we compile OUR OWN source through the public
// `newLibraryWithSource:` API (via tools/shdump) and read the AGX bytes that
// were produced FROM OUR SOURCE. The bytes of the target instruction are then
// lifted verbatim into a synthesized program (harness/isa_helpers.py) so that
// every operand the instruction names is a register WE seeded.
//
// Shapes are deliberately close to EXP-0154/EXP-0139 probe kernels (same
// project, same rules) so anchors are comparable across experiments; the file
// is authored fresh here.
//
// PAIRED CARRIERS. Several kernels come in twos or threes that differ ONLY in
// the dimension the field under test is hypothesised to control. That pairing
// is the whole point of this experiment: EXP-0164 showed that two carriers
// identical in the controlled dimension are ONE carrier, and every field we are
// repairing was withheld on exactly that failure.
//
// CLEAN-ROOM: OWN-SHADER. No Apple binary is disassembled or introspected.
#include <metal_stdlib>
using namespace metal;

// ============================================================== dst anchors ==
// The compact-move family (byte0 low nibble 0xb): reg_move_c0 / c1 / c2var /
// c9 / cb and uniform_mov are ONE 4-byte instruction (EXP-0087/EXP-0140) whose
// byte0 HIGH nibble is `dst`. We need an anchor of the `Xb YY 01 08` shape.

kernel void k_uni_each(device uint* out       [[buffer(0)]],
                       constant uint& u0      [[buffer(1)]],
                       constant uint& u1      [[buffer(2)]],
                       constant uint& u2      [[buffer(3)]],
                       constant uint& u3      [[buffer(4)]],
                       uint g [[thread_position_in_grid]]) {
    // one thread-invariant scalar per output slot: the shape EXP-0020 recorded
    // as emitting a run of `Xb YY 01 08` uniform moves with byte0-hi = 0,1,2,..
    out[g * 4u + 0u] = u0;
    out[g * 4u + 1u] = u1;
    out[g * 4u + 2u] = u2;
    out[g * 4u + 3u] = u3;
}

kernel void k_uni_sum(device uint* out    [[buffer(0)]],
                      constant uint& u0   [[buffer(1)]],
                      constant uint& u1   [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    // uniform-datapath result left in a uniform register, then ONE move out
    out[g] = u0 * 3u + u1;
}

kernel void k_bitcast(device const uint* a [[buffer(0)]],
                      device float* out    [[buffer(1)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = as_type<float>(a[g]);          // reg_move_cb family (bitcast)
}

kernel void k_packnorm2(device const float2* a [[buffer(0)]],
                        device uint* out       [[buffer(1)]],
                        uint g [[thread_position_in_grid]]) {
    out[g] = pack_float_to_unorm2x16(a[g]);  // pack_convert + reg_move_cb
}

// ------------------------------------------------------------- float ALU ----

kernel void k_fadd(device const float* a [[buffer(0)]],
                   device const float* b [[buffer(1)]],
                   device float* out     [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + b[g];                    // falu2, both sources GPR
}

kernel void k_faddi(device const float* a [[buffer(0)]],
                    device float* out     [[buffer(1)]],
                    uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + 3.0f;                    // falu2i, packed minifloat srcB
}

kernel void k_sum(device const float* a [[buffer(0)]],
                  device float* out     [[buffer(1)]],
                  uint g [[thread_position_in_grid]]) {
    // a plain reduction: the compiler lowers the tail adds to the COMPACT
    // 4-byte falu_acc (byte+2 in {0x18,0x38}) rather than the 6-byte fadd.
    float s = 0.0f;
    for (uint i = 0u; i < 10u; ++i) s += a[g * 10u + i];
    out[g] = s;
}

// falu_acc.cache PAIR — the dimension the hint is hypothesised to control is
// "is this the LAST read of the source, i.e. may the source be released?".
// k_sum_lastuse never reads its accumulator sources again; k_sum_reuse reads
// every source a SECOND time after the accumulate. A carrier that only ever
// reads a source once cannot express a last-use hint at all.
kernel void k_sum_reuse(device const float* a [[buffer(0)]],
                        device float* out     [[buffer(1)]],
                        uint g [[thread_position_in_grid]]) {
    float s = 0.0f;
    float keep = 0.0f;
    for (uint i = 0u; i < 10u; ++i) { float v = a[g * 10u + i]; s += v; keep = fma(keep, 1.5f, v); }
    out[g * 2u + 0u] = s;
    out[g * 2u + 1u] = keep;                 // every source is read TWICE
}

kernel void k_copysign(device const float* a [[buffer(0)]],
                       device const float* b [[buffer(1)]],
                       device float* out     [[buffer(2)]],
                       uint g [[thread_position_in_grid]]) {
    out[g] = copysign(a[g], b[g]);           // copysign, low register pressure
}

// copysign.operands PAIR — byte+3 is claimed to be the src/dst REGISTER
// descriptor, so the dimension it controls is "which registers". This second
// kernel computes the same op under enough live values that the compiler must
// allocate different registers for it. If byte+3 really is a register
// descriptor, the two anchors MUST differ in byte+3; that is an OWN-SHADER-DIFF
// answer available before a single splice.
kernel void k_copysign_rp(device const float* a [[buffer(0)]],
                          device const float* b [[buffer(1)]],
                          device float* out     [[buffer(2)]],
                          uint g [[thread_position_in_grid]]) {
    float v0 = a[g * 8u + 0u], v1 = a[g * 8u + 1u], v2 = a[g * 8u + 2u], v3 = a[g * 8u + 3u];
    float v4 = a[g * 8u + 4u], v5 = a[g * 8u + 5u], v6 = a[g * 8u + 6u], v7 = a[g * 8u + 7u];
    float s0 = b[g * 4u + 0u], s1 = b[g * 4u + 1u], s2 = b[g * 4u + 2u], s3 = b[g * 4u + 3u];
    float c = copysign(v0 + v1 + v2 + v3, s0 + s1);
    out[g * 2u + 0u] = c + v4 + v5 + v6 + v7 + s2 + s3;
    out[g * 2u + 1u] = v0 * v1 + v2 * v3 + v4 * v5 + v6 * v7;
}

// ---------------------------------------------------------- conversions -----
// cvt_f2h.op is byte+2, and the sibling cvt_i2f_src/cvt_f2i descriptor records
// byte+2 as "result-consumed-by-following-ALU (0x54) vs standalone (0x56)".
// So the dimension is CONSUMPTION, and these two kernels differ in exactly it.

kernel void k_f2h_standalone(device const float* a [[buffer(0)]],
                             device half* out      [[buffer(1)]],
                             uint g [[thread_position_in_grid]]) {
    out[g] = half(a[g]);                     // convert -> store, nothing between
}

kernel void k_f2h_consumed(device const float* a [[buffer(0)]],
                           device const float* b [[buffer(1)]],
                           device half* out      [[buffer(2)]],
                           uint g [[thread_position_in_grid]]) {
    half x = half(a[g]);
    half y = half(b[g]);
    out[g] = x * y + x;                      // convert -> consumed by half ALU
}

kernel void k_f2i(device const float* a [[buffer(0)]],
                  device int* out       [[buffer(1)]],
                  uint g [[thread_position_in_grid]]) {
    out[g] = int(a[g]);                      // cvt_f2i, standalone
}

kernel void k_f2i_consumed(device const float* a [[buffer(0)]],
                           device const int* b   [[buffer(1)]],
                           device int* out       [[buffer(2)]],
                           uint g [[thread_position_in_grid]]) {
    int x = int(a[g]);
    out[g] = x * b[g] + x;                   // cvt_f2i, result consumed by ALU
}

kernel void k_f2u(device const float* a [[buffer(0)]],
                  device uint* out      [[buffer(1)]],
                  uint g [[thread_position_in_grid]]) {
    out[g] = uint(a[g]);                     // cvt_f2i, unsigned variant
}

// pack_convert.b7 lives inside the format-conversion descriptor, so the
// dimension it most plausibly interacts with is the FORMAT. Three carriers,
// one per format class (byte+9 0x4x snorm / 0x8x unorm / 0xcx unorm-8).
kernel void k_pack_unorm2(device const float2* a [[buffer(0)]],
                          device uint* out       [[buffer(1)]],
                          uint g [[thread_position_in_grid]]) {
    out[g] = pack_float_to_unorm2x16(a[g]);
}

kernel void k_pack_snorm2(device const float2* a [[buffer(0)]],
                          device uint* out       [[buffer(1)]],
                          uint g [[thread_position_in_grid]]) {
    out[g] = pack_float_to_snorm2x16(a[g]);
}

kernel void k_pack_unorm4(device const float4* a [[buffer(0)]],
                          device uint* out       [[buffer(1)]],
                          uint g [[thread_position_in_grid]]) {
    out[g] = pack_float_to_unorm4x8(a[g]);
}

kernel void k_unpack_unorm2(device const uint* a  [[buffer(0)]],
                            device float2* out    [[buffer(1)]],
                            uint g [[thread_position_in_grid]]) {
    out[g] = unpack_unorm2x16_to_float(a[g]);
}

kernel void k_unpack_snorm2(device const uint* a  [[buffer(0)]],
                            device float2* out    [[buffer(1)]],
                            uint g [[thread_position_in_grid]]) {
    out[g] = unpack_snorm2x16_to_float(a[g]);
}

kernel void k_unpack_consumed(device const uint* a [[buffer(0)]],
                              device const float* b [[buffer(1)]],
                              device float* out    [[buffer(2)]],
                              uint g [[thread_position_in_grid]]) {
    float2 v = unpack_unorm2x16_to_float(a[g]);
    out[g] = v.x * b[g] + v.y;               // unpack result consumed by ALU
}

// -------------------------------------------------------- special regs ------

kernel void k_getsr(device uint* out [[buffer(0)]],
                    uint lane [[thread_index_in_simdgroup]],
                    uint tg   [[threads_per_threadgroup]],
                    uint g    [[thread_position_in_grid]]) {
    out[g * 2u + 0u] = lane;                 // get_sr sr_sel = lane index
    out[g * 2u + 1u] = tg;                   // get_sr sr_sel = threads/tg
}

// ------------------------------------------------------- shift staging ------

kernel void k_rot_var(device const uint* a [[buffer(0)]],
                      device const uint* b [[buffer(1)]],
                      device uint* out     [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = rotate(a[g], b[g]);             // shift_amt_move + irotate
}

// shift_amt_move.src_flag PAIR — bit7 of byte+1 selects which FILE the staged
// shift amount comes from (EXP-0140: "bit7 selects immediate-vs-uniform-file").
// A carrier whose amount is a compile-time constant lives entirely in the
// immediate file and can never show the GPR side; a carrier whose amount is a
// per-thread loaded value lives in the GPR file. Both are needed.
kernel void k_rot_uni(device const uint* a [[buffer(0)]],
                      constant uint& sh    [[buffer(1)]],
                      device uint* out     [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = rotate(a[g], sh);               // amount is THREAD-INVARIANT
}

kernel void k_shl_var(device const uint* a [[buffer(0)]],
                      device const uint* b [[buffer(1)]],
                      device uint* out     [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = a[g] << (b[g] & 31u);           // shift_amt_move + ishift
}

// ============================================ in-place-splice carriers =======
// These are NOT lifted. Control-flow and memory instructions reference the
// kernel's own branch displacements and buffer bindings, so their fields are
// swept by mutating ONE field IN PLACE inside the compiled form of the kernel
// below and dispatching THAT kernel with real inputs. The observable is the
// kernel's own POISONED output buffer.
//
// WHY THE STORES ARE INSIDE THE BRANCHES. EXP-0140's if_push carrier is the
// cautionary case: its MSL `if/else` assigned a value, so the compiler lowered
// it to `isel10` -- a SELECT, which exercises no execution-mask stack at all --
// and its whole mask-stack liveness argument rested on the loop instead. A
// divergent STORE cannot be if-converted away; it has to be predicated by the
// execution mask. So every region below writes its own output slot, and against
// a 0xDEADBEEF-poisoned buffer the read-back IS the per-lane execution mask:
// a slot still holding poison is a region that lane did not execute. That makes
// the observable exactly the thing `if_push.scope` is claimed to control.

kernel void k_if_flat(device const uint* a [[buffer(0)]],
                      device uint* out     [[buffer(1)]],
                      uint g [[thread_position_in_grid]]) {
    // ONE non-nested scope. Kept ONLY as the blind negative control: with a
    // single live scope there is no second mask bank for a wrong bank to
    // collide with, so this carrier cannot express `scope` even in principle.
    out[g * 8u + 0u] = 0xA0u + g;
    if (a[g] > 100u) { out[g * 8u + 1u] = 0xA1u + g; }
    out[g * 8u + 6u] = 0xA6u + g;               // reconvergence witness
}

kernel void k_if_nest2(device const uint* a [[buffer(0)]],
                       device uint* out     [[buffer(1)]],
                       uint g [[thread_position_in_grid]]) {
    out[g * 8u + 0u] = 0xA0u + g;               // every lane
    if (a[g] > 100u) {                          // outer scope (even parity)
        out[g * 8u + 1u] = 0xA1u + g;
        if (a[g] > 200u) {                      // inner scope (odd parity)
            out[g * 8u + 2u] = 0xA2u + g;
        }
        out[g * 8u + 5u] = 0xA5u + g;           // post-inner, still in outer
    }
    out[g * 8u + 6u] = 0xA6u + g;               // every lane: a broken
                                                // reconvergence shows HERE
}

kernel void k_if_nest3(device const uint* a [[buffer(0)]],
                       device uint* out     [[buffer(1)]],
                       uint g [[thread_position_in_grid]]) {
    // THREE genuine nesting levels, so the 0x54 / 0x56 nesting-parity model
    // db.json describes is actually instantiated: an inner push forced to the
    // outer's bank has an outer mask to destroy.
    out[g * 8u + 0u] = 0xA0u + g;
    if (a[g] > 50u) {
        out[g * 8u + 1u] = 0xA1u + g;
        if (a[g] > 100u) {
            out[g * 8u + 2u] = 0xA2u + g;
            if (a[g] > 200u) {
                out[g * 8u + 3u] = 0xA3u + g;
            }
            out[g * 8u + 4u] = 0xA4u + g;       // back in level 2
        }
        out[g * 8u + 5u] = 0xA5u + g;           // back in level 1
    }
    out[g * 8u + 6u] = 0xA6u + g;               // back at level 0, EVERY lane
}

kernel void k_if_loop(device const uint* a [[buffer(0)]],
                      device uint* out     [[buffer(1)]],
                      uint g [[thread_position_in_grid]]) {
    // scope_kind 0x01 (conditional-skip guard) wrapping scope_kind 0x1a
    // (loop-iteration scope): the two KINDS nested, which the flat and the
    // pure-nest carriers do not produce.
    out[g * 8u + 0u] = 0xA0u + g;
    if (a[g] > 100u) {
        for (uint i = 0u; i < 3u; ++i) {
            out[g * 8u + 1u + i] = 0xB0u + g + i * 0x10u;
        }
        out[g * 8u + 5u] = 0xA5u + g;
    }
    out[g * 8u + 6u] = 0xA6u + g;
}

// atomic_mem.addr_desc_hi is byte+6 bits 6..7, sitting immediately above the
// 7-bit operand-register field (`oper_reg_lo` at bit47 + `oper_reg_hi` at bits
// 48..53). The obvious hypothesis is that those two bits extend the operand
// register number -- which is UNTESTABLE at a low register index, and EXP-0141
// tested exactly one (index 3, its own range note says "0x01/0x41/0x81/0xC1 all
// select index 3"). So the dimension is the OPERAND REGISTER NUMBER, and the
// pair below differs in exactly it: k_atomic_lo keeps the operand in a low
// register, k_atomic_hi keeps enough scalars simultaneously live that the
// operand must be allocated high. The scalars are named, not an array, because
// a dynamically indexed array goes to scratch memory instead of registers.

kernel void k_atomic_lo(device atomic_uint* at [[buffer(0)]],
                        device const uint* b   [[buffer(1)]],
                        device uint* out       [[buffer(2)]],
                        uint g [[thread_position_in_grid]]) {
    out[g] = atomic_fetch_add_explicit(&at[g], b[g], memory_order_relaxed);
}

kernel void k_atomic_hi(device atomic_uint* at [[buffer(0)]],
                        device const uint* b   [[buffer(1)]],
                        device uint* out       [[buffer(2)]],
                        uint g [[thread_position_in_grid]]) {
    uint k00 = b[g * 24u +  0u], k01 = b[g * 24u +  1u], k02 = b[g * 24u +  2u];
    uint k03 = b[g * 24u +  3u], k04 = b[g * 24u +  4u], k05 = b[g * 24u +  5u];
    uint k06 = b[g * 24u +  6u], k07 = b[g * 24u +  7u], k08 = b[g * 24u +  8u];
    uint k09 = b[g * 24u +  9u], k10 = b[g * 24u + 10u], k11 = b[g * 24u + 11u];
    uint k12 = b[g * 24u + 12u], k13 = b[g * 24u + 13u], k14 = b[g * 24u + 14u];
    uint k15 = b[g * 24u + 15u], k16 = b[g * 24u + 16u], k17 = b[g * 24u + 17u];
    uint k18 = b[g * 24u + 18u], k19 = b[g * 24u + 19u], k20 = b[g * 24u + 20u];
    uint k21 = b[g * 24u + 21u], k22 = b[g * 24u + 22u], k23 = b[g * 24u + 23u];
    // the atomic operand is one of the late-defined scalars, and every other
    // scalar is still live afterwards, so it cannot be allocated low
    uint prev = atomic_fetch_add_explicit(&at[g], k21, memory_order_relaxed);
    uint mix = k00;
    mix = mix * 3u + k01; mix = mix * 3u + k02; mix = mix * 3u + k03;
    mix = mix * 3u + k04; mix = mix * 3u + k05; mix = mix * 3u + k06;
    mix = mix * 3u + k07; mix = mix * 3u + k08; mix = mix * 3u + k09;
    mix = mix * 3u + k10; mix = mix * 3u + k11; mix = mix * 3u + k12;
    mix = mix * 3u + k13; mix = mix * 3u + k14; mix = mix * 3u + k15;
    mix = mix * 3u + k16; mix = mix * 3u + k17; mix = mix * 3u + k18;
    mix = mix * 3u + k19; mix = mix * 3u + k20; mix = mix * 3u + k22;
    mix = mix * 3u + k23;
    out[g * 2u + 0u] = prev;
    out[g * 2u + 1u] = mix;
}

kernel void k_atomic_min(device atomic_uint* at [[buffer(0)]],
                         device const uint* b   [[buffer(1)]],
                         device uint* out       [[buffer(2)]],
                         uint g [[thread_position_in_grid]]) {
    // a different atomic OP in the same 5-bit `op` selector, so the arm has a
    // second carrier that differs in the operation as well as the register
    out[g] = atomic_fetch_min_explicit(&at[g], b[g], memory_order_relaxed);
}

// -------------------------------------------------------- matrix (stretch) --

kernel void k_matmac(device const float* a [[buffer(0)]],
                     device const float* b [[buffer(1)]],
                     device float* out     [[buffer(2)]],
                     uint g   [[thread_position_in_grid]],
                     uint sgi [[simdgroup_index_in_threadgroup]]) {
    simdgroup_float8x8 A, B, C;
    simdgroup_load(A, a, 8);
    simdgroup_load(B, b, 8);
    C = simdgroup_float8x8(0.0f);
    simdgroup_multiply_accumulate(C, A, B, C);
    simdgroup_store(C, out, 8);
}
