#include <metal_stdlib>
using namespace metal;

// ~70 independent live values kept in registers (EXP-0020 style: data-dependent
// so the allocator cannot collapse them), forcing use of r64..r95 with no spill.
kernel void k(device const float* a [[buffer(0)]],
              device float* o        [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    float v[70];
    for (int j = 0; j < 70; ++j) v[j] = a[i] + float(j);
    // rotate/mix once so all 70 are simultaneously live at the combine point
    float s = a[i];
    for (int j = 0; j < 70; ++j) s = fma(v[j], 1.0000001f, s);
    o[i] = s;
}
