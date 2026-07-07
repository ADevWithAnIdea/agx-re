// EXP-0022 B6 probe: Metal Performance Primitives tensor matmul2d.
// AVAILABILITY PROBE ONLY -- confirm whether this compiles on the installed
// toolchain before relying on it. CLEAN-ROOM: OUR OWN MSL.
#include <metal_stdlib>
#include <MetalPerformancePrimitives/MetalPerformancePrimitives.h>
using namespace metal;
using namespace mpp;
using namespace mpp::tensor_ops;

kernel void mpp_matmul(tensor<device half,  dextents<int, 2>> A [[buffer(0)]],
                       tensor<device half,  dextents<int, 2>> B [[buffer(1)]],
                       tensor<device float, dextents<int, 2>> C [[buffer(2)]]) {
    constexpr matmul2d_descriptor d(/*M*/32, /*N*/32, /*K*/32,
                                    /*transpose_left*/false, /*transpose_right*/false,
                                    /*relaxed_precision*/false, matmul2d_descriptor::mode::multiply);
    matmul2d<d, execution_simdgroups<1>> mm;
    mm.run(A, B, C);
}
