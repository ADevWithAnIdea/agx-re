// EXP-0220 carrier kernel -- OUR OWN MSL.
//
// Purpose: fix the compute buffer bindings (0 = out, 1 = mem, 2 = imem) and compile
// to an `_agc.main` region long enough to hold any EXP-0220 generated program.  The
// kernel's OWN arithmetic is NEVER executed: every case overwrites the whole
// `_agc.main` region from offset 0 with bytes this experiment generated, so the
// instruction stream that runs is 100% ours.  Same SHAPE as our own
// experiments/EXP-0167-g17p-synthesis-reconfirm/kernels/carrier_dag.metal (which
// compiled to >= 1536 bytes on this target), lengthened so a 16-register
// full-state dump plus seeds plus the case body always fits.
//
// base_slot is NOT read off this kernel's own compiled instructions in EXP-0220 --
// arm S0 determines the slot->buffer mapping by hardware probe instead, so no
// instruction field of any generated program comes from a compiled donor.
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* mem [[buffer(1)]],
              device int* imem [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    float acc = mem[tid + 0];
    acc = acc * 1.0000001f + mem[tid + 1u];
    acc = acc * 1.0000001f + mem[tid + 2u];
    acc = acc * 1.0000001f + mem[tid + 3u];
    acc = acc * 1.0000001f + mem[tid + 4u];
    acc = acc * 1.0000001f + mem[tid + 5u];
    acc = acc * 1.0000001f + mem[tid + 6u];
    acc = acc * 1.0000001f + mem[tid + 7u];
    acc = acc * 1.0000001f + mem[tid + 8u];
    acc = acc * 1.0000001f + mem[tid + 9u];
    acc = acc * 1.0000001f + mem[tid + 10u];
    acc = acc * 1.0000001f + mem[tid + 11u];
    acc = acc * 1.0000001f + mem[tid + 12u];
    acc = acc * 1.0000001f + mem[tid + 13u];
    acc = acc * 1.0000001f + mem[tid + 14u];
    acc = acc * 1.0000001f + mem[tid + 15u];
    acc = acc * 1.0000001f + mem[tid + 16u];
    acc = acc * 1.0000001f + mem[tid + 17u];
    acc = acc * 1.0000001f + mem[tid + 18u];
    acc = acc * 1.0000001f + mem[tid + 19u];
    acc = acc * 1.0000001f + mem[tid + 20u];
    acc = acc * 1.0000001f + mem[tid + 21u];
    acc = acc * 1.0000001f + mem[tid + 22u];
    acc = acc * 1.0000001f + mem[tid + 23u];
    acc = acc * 1.0000001f + mem[tid + 24u];
    acc = acc * 1.0000001f + mem[tid + 25u];
    acc = acc * 1.0000001f + mem[tid + 26u];
    acc = acc * 1.0000001f + mem[tid + 27u];
    acc = acc * 1.0000001f + mem[tid + 28u];
    acc = acc * 1.0000001f + mem[tid + 29u];
    acc = acc * 1.0000001f + mem[tid + 30u];
    acc = acc * 1.0000001f + mem[tid + 31u];
    acc = acc * 1.0000001f + mem[tid + 32u];
    acc = acc * 1.0000001f + mem[tid + 33u];
    acc = acc * 1.0000001f + mem[tid + 34u];
    acc = acc * 1.0000001f + mem[tid + 35u];
    acc = acc * 1.0000001f + mem[tid + 36u];
    acc = acc * 1.0000001f + mem[tid + 37u];
    acc = acc * 1.0000001f + mem[tid + 38u];
    acc = acc * 1.0000001f + mem[tid + 39u];
    acc = acc * 1.0000001f + mem[tid + 40u];
    acc = acc * 1.0000001f + mem[tid + 41u];
    acc = acc * 1.0000001f + mem[tid + 42u];
    acc = acc * 1.0000001f + mem[tid + 43u];
    acc = acc * 1.0000001f + mem[tid + 44u];
    acc = acc * 1.0000001f + mem[tid + 45u];
    acc = acc * 1.0000001f + mem[tid + 46u];
    acc = acc * 1.0000001f + mem[tid + 47u];
    acc = acc * 1.0000001f + mem[tid + 48u];
    acc = acc * 1.0000001f + mem[tid + 49u];
    acc = acc * 1.0000001f + mem[tid + 50u];
    acc = acc * 1.0000001f + mem[tid + 51u];
    acc = acc * 1.0000001f + mem[tid + 52u];
    acc = acc * 1.0000001f + mem[tid + 53u];
    acc = acc * 1.0000001f + mem[tid + 54u];
    acc = acc * 1.0000001f + mem[tid + 55u];
    acc = acc * 1.0000001f + mem[tid + 56u];
    acc = acc * 1.0000001f + mem[tid + 57u];
    acc = acc * 1.0000001f + mem[tid + 58u];
    acc = acc * 1.0000001f + mem[tid + 59u];
    acc = acc * 1.0000001f + mem[tid + 60u];
    acc = acc * 1.0000001f + mem[tid + 61u];
    acc = acc * 1.0000001f + mem[tid + 62u];
    acc = acc * 1.0000001f + mem[tid + 63u];
    acc = acc * 1.0000001f + mem[tid + 64u];
    acc = acc * 1.0000001f + mem[tid + 65u];
    acc = acc * 1.0000001f + mem[tid + 66u];
    acc = acc * 1.0000001f + mem[tid + 67u];
    acc = acc * 1.0000001f + mem[tid + 68u];
    acc = acc * 1.0000001f + mem[tid + 69u];
    acc = acc * 1.0000001f + mem[tid + 70u];
    acc = acc * 1.0000001f + mem[tid + 71u];
    acc = acc * 1.0000001f + mem[tid + 72u];
    acc = acc * 1.0000001f + mem[tid + 73u];
    acc = acc * 1.0000001f + mem[tid + 74u];
    acc = acc * 1.0000001f + mem[tid + 75u];
    acc = acc * 1.0000001f + mem[tid + 76u];
    acc = acc * 1.0000001f + mem[tid + 77u];
    acc = acc * 1.0000001f + mem[tid + 78u];
    acc = acc * 1.0000001f + mem[tid + 79u];
    acc = acc * 1.0000001f + mem[tid + 80u];
    acc = acc * 1.0000001f + mem[tid + 81u];
    acc = acc * 1.0000001f + mem[tid + 82u];
    acc = acc * 1.0000001f + mem[tid + 83u];
    acc = acc * 1.0000001f + mem[tid + 84u];
    acc = acc * 1.0000001f + mem[tid + 85u];
    acc = acc * 1.0000001f + mem[tid + 86u];
    acc = acc * 1.0000001f + mem[tid + 87u];
    acc = acc * 1.0000001f + mem[tid + 88u];
    acc = acc * 1.0000001f + mem[tid + 89u];
    acc = acc * 1.0000001f + mem[tid + 90u];
    acc = acc * 1.0000001f + mem[tid + 91u];
    acc = acc - float(imem[tid + 1u]) * 0.0000001f;
    acc = acc - float(imem[tid + 2u]) * 0.0000001f;
    acc = acc - float(imem[tid + 3u]) * 0.0000001f;
    acc = acc - float(imem[tid + 4u]) * 0.0000001f;
    acc = acc - float(imem[tid + 5u]) * 0.0000001f;
    acc = acc - float(imem[tid + 6u]) * 0.0000001f;
    acc = acc - float(imem[tid + 7u]) * 0.0000001f;
    acc = acc - float(imem[tid + 8u]) * 0.0000001f;
    acc = acc - float(imem[tid + 9u]) * 0.0000001f;
    acc = acc - float(imem[tid + 10u]) * 0.0000001f;
    acc = acc - float(imem[tid + 11u]) * 0.0000001f;
    acc = acc - float(imem[tid + 12u]) * 0.0000001f;
    acc = acc - float(imem[tid + 13u]) * 0.0000001f;
    acc = acc - float(imem[tid + 14u]) * 0.0000001f;
    out[tid + 0] = acc;
}
