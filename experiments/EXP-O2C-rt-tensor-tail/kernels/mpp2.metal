// EXP-O2C MPP tensor-ops probes BEYOND matmul2d (extends EXP-0022 B6).
// Availability + lowering probe: do these lower to more 0xcf, or new opcodes?
// CLEAN-ROOM: OUR OWN MSL. Each kernel is compiled in isolation; a compile
// failure is a first-class negative result.
#include <metal_stdlib>
#include <MetalPerformancePrimitives/MetalPerformancePrimitives.h>
using namespace metal;
using namespace mpp;
using namespace mpp::tensor_ops;

// Baseline matmul2d (multiply) 32x32x32 -- reference from EXP-0022.
kernel void mm_mul(tensor<device half,  dextents<int, 2>> A [[buffer(0)]],
                   tensor<device half,  dextents<int, 2>> B [[buffer(1)]],
                   tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(32,32,32,false,false,false,
                                    matmul2d_descriptor::mode::multiply);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}

// matmul2d multiply_accumulate (C += A*B) -- does accumulate change the op mix?
kernel void mm_mac(tensor<device half,  dextents<int, 2>> A [[buffer(0)]],
                   tensor<device half,  dextents<int, 2>> B [[buffer(1)]],
                   tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(32,32,32,false,false,false,
                                    matmul2d_descriptor::mode::multiply_accumulate);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}

// transpose_left: A^T * B -- transposed operand tiling.
kernel void mm_tl(tensor<device half,  dextents<int, 2>> A [[buffer(0)]],
                  tensor<device half,  dextents<int, 2>> B [[buffer(1)]],
                  tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(32,32,32,true,false,false,
                                    matmul2d_descriptor::mode::multiply);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}

// transpose_right: A * B^T.
kernel void mm_tr(tensor<device half,  dextents<int, 2>> A [[buffer(0)]],
                  tensor<device half,  dextents<int, 2>> B [[buffer(1)]],
                  tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(32,32,32,false,true,false,
                                    matmul2d_descriptor::mode::multiply);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}

// small 16x16x16 matmul2d -- smallest legal tile (M/N must be mult of 16);
// compare 0xcf count (expect 2*2*2 = 8 tile-MACs) to the 32x32x32 case.
kernel void mm_16(tensor<device half,  dextents<int, 2>> A [[buffer(0)]],
                  tensor<device half,  dextents<int, 2>> B [[buffer(1)]],
                  tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(16,16,16,false,false,false,
                                    matmul2d_descriptor::mode::multiply);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}

// float x float -> float matmul2d (dtype variant).
kernel void mm_f32(tensor<device float, dextents<int, 2>> A [[buffer(0)]],
                   tensor<device float, dextents<int, 2>> B [[buffer(1)]],
                   tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(32,32,32,false,false,false,
                                    matmul2d_descriptor::mode::multiply);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}

// 2 simdgroups of execution -- does the scope change the op or just the tiling?
kernel void mm_2sg(tensor<device half,  dextents<int, 2>> A [[buffer(0)]],
                   tensor<device half,  dextents<int, 2>> B [[buffer(1)]],
                   tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(32,32,32,false,false,false,
                                    matmul2d_descriptor::mode::multiply);
    matmul2d<d, execution_simdgroups<2>> mm;
    mm.run(A, B, C);
}
