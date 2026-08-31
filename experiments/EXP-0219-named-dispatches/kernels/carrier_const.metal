// EXP-0219 SYNTH carrier "C-CONST" (AUTHORED BY US for this experiment).
//
// PURPOSE.  EXP-0218 could not decide whether `imad`'s external-fetch index is
// 5 bits (K alone) or 8 bits (K | (byte+8 & 7) << 5), because the only carrier
// on record -- EXP-0160's carrier_dag -- has a constant file that reads ZERO at
// every half-index >= 32, so "index >= 32" and "addend suppressed" are the same
// observation.  0 of 4086 committed cases separate them.
//
// This carrier exists to break that tie and nothing else.  It uses 48 DISTINCT
// 32-bit float constants, built with as_type<float>() so that BOTH 16-bit
// halves of every constant are chosen by us and are unique across the whole
// set: constant i has high half 0x3F80+i (a normal, finite float in [1,2), so
// nothing is a NaN/Inf the compiler might fold away) and low half 0x1000+i.
// The two ranges are disjoint, so all 96 halves are distinct and every half we
// observe in the file identifies exactly which constant it came from and which
// half of it.
//
// The body is never executed in a sweep case -- every case replaces the WHOLE
// `_agc.main` with a synthesized program.  Only the region LENGTH, the buffer
// bindings (buffer 0 = out float, buffer 1 = float in, buffer 2 = int in, the
// shape tools/agxtest/agxrun_persist binds) and the CONSTANT FILE the driver
// preloads for this pipeline matter.  Binding shape reused (not values) from
// EXP-0160's carrier_dag.metal, same project, same rules.
//
// CLEAN-ROOM: our own MSL.  No Apple source consulted.
#include <metal_stdlib>
using namespace metal;

kernel void k(device float* out  [[buffer(0)]],
              device float* mem  [[buffer(1)]],
              device int*   imem [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    float acc = mem[tid + 0];
#define ST(BITS, I) acc = acc * as_type<float>(BITS) + mem[tid + I##u];
    ST(0x3f801000u,  1)
    ST(0x3f811001u,  2)
    ST(0x3f821002u,  3)
    ST(0x3f831003u,  4)
    ST(0x3f841004u,  5)
    ST(0x3f851005u,  6)
    ST(0x3f861006u,  7)
    ST(0x3f871007u,  8)
    ST(0x3f881008u,  9)
    ST(0x3f891009u, 10)
    ST(0x3f8a100au, 11)
    ST(0x3f8b100bu, 12)
    ST(0x3f8c100cu, 13)
    ST(0x3f8d100du, 14)
    ST(0x3f8e100eu, 15)
    ST(0x3f8f100fu, 16)
    ST(0x3f901010u, 17)
    ST(0x3f911011u, 18)
    ST(0x3f921012u, 19)
    ST(0x3f931013u, 20)
    ST(0x3f941014u, 21)
    ST(0x3f951015u, 22)
    ST(0x3f961016u, 23)
    ST(0x3f971017u, 24)
    ST(0x3f981018u, 25)
    ST(0x3f991019u, 26)
    ST(0x3f9a101au, 27)
    ST(0x3f9b101bu, 28)
    ST(0x3f9c101cu, 29)
    ST(0x3f9d101du, 30)
    ST(0x3f9e101eu, 31)
    ST(0x3f9f101fu, 32)
    ST(0x3fa01020u, 33)
    ST(0x3fa11021u, 34)
    ST(0x3fa21022u, 35)
    ST(0x3fa31023u, 36)
    ST(0x3fa41024u, 37)
    ST(0x3fa51025u, 38)
    ST(0x3fa61026u, 39)
    ST(0x3fa71027u, 40)
    ST(0x3fa81028u, 41)
    ST(0x3fa91029u, 42)
    ST(0x3faa102au, 43)
    ST(0x3fab102bu, 44)
    ST(0x3fac102cu, 45)
    ST(0x3fad102du, 46)
    ST(0x3fae102eu, 47)
    ST(0x3faf102fu, 48)
#undef ST
#define ISTEP(i) acc = acc - float(imem[tid + i##u]) * 0.0000001f;
    ISTEP(1) ISTEP(2) ISTEP(3) ISTEP(4) ISTEP(5) ISTEP(6) ISTEP(7) ISTEP(8)
#undef ISTEP
    out[tid + 0] = acc;
}
