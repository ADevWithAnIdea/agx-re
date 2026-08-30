// EXP-0169 anchor-probe kernels (ALL authored by us for this experiment).
//
// Each kernel is the smallest MSL we could write that should make the Apple
// compiler emit ONE instruction of a family whose db.json fields EXP-0164
// withheld as UNVERIFIABLE. We never inspect Apple's compiler; we compile our
// own source through the PUBLIC runtime API (`newLibraryWithSource:` via
// tools/shdump) and read the AGX bytes it produced FROM OUR SOURCE. The bytes
// of the target instruction are then lifted verbatim into a synthesized
// program (harness/isa_helpers.py) in which every operand it can name is a
// register WE seeded.
//
// Which kernel supplies which anchor is NOT hard-coded here: harness/anchors.py
// tokenizes every kernel with tools/agx-isa and harness/casematrix.py resolves
// each arm to the first liftable occurrence of its target mnemonic, in the
// frozen kernel order below. That keeps the frozen contract robust against the
// compiler choosing a different length/form than we guessed.
//
// Shapes are deliberately similar to the EXP-0139/EXP-0145/EXP-0154 probe
// kernels (same project, same rules); the file is authored fresh here.
//
// CLEAN-ROOM: OWN-SHADER. No Apple binary is disassembled or introspected.
#include <metal_stdlib>
using namespace metal;

// ------------------------------------------------------------------ float ---
// falu2: the plain 6-byte two-source float ALU (byte0 0x09, byte+2 0x1c/0x1d).

kernel void k_fadd(device const float* a [[buffer(0)]],
                   device const float* b [[buffer(1)]],
                   device float* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + b[g];                      // falu2 fadd
}

kernel void k_fmul(device const float* a [[buffer(0)]],
                   device const float* b [[buffer(1)]],
                   device float* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = a[g] * b[g];                      // falu2 fmul
}

kernel void k_fchain(device const float* a [[buffer(0)]],
                     device const float* b [[buffer(1)]],
                     device float* out [[buffer(2)]],
                     uint g [[thread_position_in_grid]]) {
    // A run of dependent adds/muls: gives several falu2 occurrences whose
    // neighbourhood contains no memory op, so a widened lift window is legal.
    float x = a[g];
    float y = b[g];
    x = x + y; x = x * y; x = x + y; x = x * y;
    x = x + y; x = x * y; x = x + y; x = x * y;
    out[g] = x;
}

// falu2i: two-source float ALU with the packed minifloat immediate.

kernel void k_faddi(device const float* a [[buffer(0)]],
                    device float* out [[buffer(1)]],
                    uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + 3.0f;                      // falu2i fadd imm
}

kernel void k_fimmchain(device const float* a [[buffer(0)]],
                        device float* out [[buffer(1)]],
                        uint g [[thread_position_in_grid]]) {
    float x = a[g];
    x = x + 3.0f; x = x * 1.5f; x = x + 0.5f; x = x * 30.0f;
    x = x + 7.0f; x = x * 0.25f; x = x + 18.0f; x = x * 2.0f;
    out[g] = x;
}

// falu2_uni: srcB is a UNIFORM register (thread-invariant), not a GPR and not
// an immediate. Needs the `constant` buffer so the shader container preloads
// the uniform file (EXP-0020 / RT-1a-FIX).

kernel void k_funi(device const float* a [[buffer(0)]],
                   device float* out [[buffer(1)]],
                   constant float4& u [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + u.x;                       // falu2_uni
}

kernel void k_funichain(device const float* a [[buffer(0)]],
                        device float* out [[buffer(1)]],
                        constant float4& u [[buffer(2)]],
                        uint g [[thread_position_in_grid]]) {
    float x = a[g];
    x = x + u.x; x = x * u.y; x = x + u.z; x = x * u.w;
    out[g] = x;
}

// ------------------------------------------------------------------- half ---
// half_alu (6B), half_alu_ext8 (8B fma / add+saturate), half_alu_fma12 (12B).

kernel void k_hadd(device const half* a [[buffer(0)]],
                   device const half* b [[buffer(1)]],
                   device half* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + b[g];                      // half_alu hadd
}

kernel void k_hmul(device const half* a [[buffer(0)]],
                   device const half* b [[buffer(1)]],
                   device half* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = a[g] * b[g];                      // half_alu hmul
}

kernel void k_hchain(device const half* a [[buffer(0)]],
                     device const half* b [[buffer(1)]],
                     device half* out [[buffer(2)]],
                     uint g [[thread_position_in_grid]]) {
    half x = a[g], y = b[g];
    x = x + y; x = x * y; x = x + y; x = x * y;
    x = x + y; x = x * y; x = x + y; x = x * y;
    out[g] = x;
}

kernel void k_hsat(device const half* a [[buffer(0)]],
                   device const half* b [[buffer(1)]],
                   device half* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = saturate(a[g] + b[g]);            // half_alu_ext8 (add + saturate)
}

kernel void k_hfma(device const half* a [[buffer(0)]],
                   device const half* b [[buffer(1)]],
                   device const half* c [[buffer(2)]],
                   device half* out [[buffer(3)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = fma(a[g], b[g], c[g]);            // half_alu_ext8 (hfma, 8B)
}

kernel void k_hfma_abs(device const half* a [[buffer(0)]],
                       device const half* b [[buffer(1)]],
                       device const half* c [[buffer(2)]],
                       device half* out [[buffer(3)]],
                       uint g [[thread_position_in_grid]]) {
    out[g] = fma(abs(a[g]), b[g], c[g]);       // half_alu_fma12 (12B abs form)
}

kernel void k_hfma_satabs(device const half* a [[buffer(0)]],
                          device const half* b [[buffer(1)]],
                          device const half* c [[buffer(2)]],
                          device half* out [[buffer(3)]],
                          uint g [[thread_position_in_grid]]) {
    out[g] = saturate(fma(abs(a[g]), b[g], c[g]));
}

// ---------------------------------------------------------------- bfloat ---

kernel void k_bfadd(device const bfloat* a [[buffer(0)]],
                    device const bfloat* b [[buffer(1)]],
                    device bfloat* out [[buffer(2)]],
                    uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + b[g];                      // bf_alu add
}

kernel void k_bfmul(device const bfloat* a [[buffer(0)]],
                    device const bfloat* b [[buffer(1)]],
                    device bfloat* out [[buffer(2)]],
                    uint g [[thread_position_in_grid]]) {
    out[g] = a[g] * b[g];                      // bf_alu mul
}

kernel void k_bfchain(device const bfloat* a [[buffer(0)]],
                      device const bfloat* b [[buffer(1)]],
                      device bfloat* out [[buffer(2)]],
                      uint g [[thread_position_in_grid]]) {
    bfloat x = a[g], y = b[g];
    x = x + y; x = x * y; x = x + y; x = x * y;
    out[g] = x;
}

// ------------------------------------------------- integer unary / bitcount --
// ibitcount is the tightly-matched 0x27 sub-family (popcount / find_msb /
// reverse_bits); iunary is the looser 0x27 descriptor (convert / SFU / interp
// datapaths). Both anchors are wanted, and which kernel yields which is
// resolved from the anchor report, not assumed.

kernel void k_popcount(device const uint* a [[buffer(0)]],
                       device uint* out [[buffer(1)]],
                       uint g [[thread_position_in_grid]]) {
    out[g] = popcount(a[g]);
}

kernel void k_clz(device const uint* a [[buffer(0)]],
                  device uint* out [[buffer(1)]],
                  uint g [[thread_position_in_grid]]) {
    out[g] = clz(a[g]);
}

kernel void k_reverse(device const uint* a [[buffer(0)]],
                      device uint* out [[buffer(1)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = reverse_bits(a[g]);
}

kernel void k_ctz(device const uint* a [[buffer(0)]],
                  device uint* out [[buffer(1)]],
                  uint g [[thread_position_in_grid]]) {
    out[g] = ctz(a[g]);
}

kernel void k_bitchain(device const uint* a [[buffer(0)]],
                       device uint* out [[buffer(1)]],
                       uint g [[thread_position_in_grid]]) {
    uint x = a[g];
    x = popcount(x); x = clz(x); x = reverse_bits(x); x = popcount(x);
    out[g] = x;
}

kernel void k_cvt_f2i(device const float* a [[buffer(0)]],
                      device int* out [[buffer(1)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = int(a[g]);                        // convert datapath (iunary form)
}

kernel void k_cvt_i2f(device const int* a [[buffer(0)]],
                      device float* out [[buffer(1)]],
                      uint g [[thread_position_in_grid]]) {
    out[g] = float(a[g]);
}

kernel void k_cvt_chain(device const float* a [[buffer(0)]],
                        device float* out [[buffer(1)]],
                        uint g [[thread_position_in_grid]]) {
    float x = a[g];
    int i = int(x); x = float(i); i = int(x * 3.0f); x = float(i);
    out[g] = x;
}

// ------------------------------------------------------ compare / predicate --
// icmp_pred sets a per-lane predicate feeding a divergent block. Its effect is
// only observable through that block, so this arm runs in NATIVE-carrier mode
// (splice in place, read the kernel's own output) rather than being lifted.

kernel void k_cmp(device const uint* a [[buffer(0)]],
                  device const uint* b [[buffer(1)]],
                  device uint* out [[buffer(2)]],
                  uint g [[thread_position_in_grid]]) {
    uint r = 0x11111111u;
    if (a[g] > b[g]) {
        r = 0x22222222u;
    } else {
        r = 0x33333333u;
    }
    out[g] = r;
}

kernel void k_cmp_chain(device const uint* a [[buffer(0)]],
                        device const uint* b [[buffer(1)]],
                        device uint* out [[buffer(2)]],
                        uint g [[thread_position_in_grid]]) {
    uint r = 0u;
    if (a[g] > b[g])  r += 1u;
    if (a[g] < b[g])  r += 2u;
    if (a[g] == b[g]) r += 4u;
    if (a[g] != b[g]) r += 8u;
    out[g] = r;
}

// -------------------------------------------------------- special registers --

kernel void k_sr(device uint* out [[buffer(0)]],
                 uint g [[thread_position_in_grid]],
                 uint l [[thread_position_in_threadgroup]],
                 uint sg [[simdgroup_index_in_threadgroup]]) {
    out[g] = g + 1000u * l + 1000000u * sg;    // get_sr
}
