#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]],
              uint v [[thread_index_in_quadgroup]]) {
    out[0] = v;
}
