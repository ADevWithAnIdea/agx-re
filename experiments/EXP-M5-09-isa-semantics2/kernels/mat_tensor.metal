// EXP-M5-09 MARQUEE: MPP tensor_ops::matmul2d provocations on M5 (Metal-4 tensor path).
// The KEY question: does M5 keep A18's all-to-0xcf lowering or emit a NEW dedicated
// neural/tensor instruction? Diff these vs mat_simd.metal.
// CLEAN-ROOM: OUR OWN MSL. Reused/extended from EXP-O2C (A18). No Apple binary inspected.
#include <metal_stdlib>
#include <MetalPerformancePrimitives/MetalPerformancePrimitives.h>
using namespace metal;
using namespace mpp;
using namespace mpp::tensor_ops;

// half*half->float matmul2d 32x32x32, multiply only
kernel void mm_mul(tensor<device half,  dextents<int, 2>> A [[buffer(0)]],
                   tensor<device half,  dextents<int, 2>> B [[buffer(1)]],
                   tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(32,32,32,false,false,false,
                                    matmul2d_descriptor::mode::multiply);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}

// multiply_accumulate (C += A*B)
kernel void mm_mac(tensor<device half,  dextents<int, 2>> A [[buffer(0)]],
                   tensor<device half,  dextents<int, 2>> B [[buffer(1)]],
                   tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(32,32,32,false,false,false,
                                    matmul2d_descriptor::mode::multiply_accumulate);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}

// smallest legal tile 16x16x16 (M/N mult of 16)
kernel void mm_16(tensor<device half,  dextents<int, 2>> A [[buffer(0)]],
                  tensor<device half,  dextents<int, 2>> B [[buffer(1)]],
                  tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(16,16,16,false,false,false,
                                    matmul2d_descriptor::mode::multiply);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}

// float*float->float matmul2d (dtype variant)
kernel void mm_f32(tensor<device float, dextents<int, 2>> A [[buffer(0)]],
                   tensor<device float, dextents<int, 2>> B [[buffer(1)]],
                   tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(32,32,32,false,false,false,
                                    matmul2d_descriptor::mode::multiply);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}

// bf16*bf16->float matmul2d (bfloat neural dtype)
kernel void mm_bf16(tensor<device bfloat, dextents<int, 2>> A [[buffer(0)]],
                    tensor<device bfloat, dextents<int, 2>> B [[buffer(1)]],
                    tensor<device float,  dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(32,32,32,false,false,false,
                                    matmul2d_descriptor::mode::multiply);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}
