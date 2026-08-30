// EXP-0145 carrier -- AUTHORED BY US (clean-room OWN-SHADER).
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device const float* a [[buffer(1)]],
              device uint* sent [[buffer(4)]], uint g [[thread_position_in_grid]]) {
    out[g] = precise::tan(a[g]) + precise::exp2(a[g]) + precise::log2(a[g]);
    sent[g] = 0xA5A5A5A5u;
}
