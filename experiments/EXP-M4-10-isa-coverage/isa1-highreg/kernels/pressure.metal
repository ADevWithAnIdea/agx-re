#include <metal_stdlib>
using namespace metal;

// Force high register pressure so the compiler must allocate r64..r95.
// A data-dependent chain of independent live values that cannot be collapsed.
kernel void k(device const float* a [[buffer(0)]],
              device float* o        [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    float acc[40];
    for (int j = 0; j < 40; ++j) acc[j] = a[i + j] * float(j + 1);
    // keep them all live across a barrier-ish reduction that references each once
    float s = 0.0f;
    for (int j = 0; j < 40; ++j) s += acc[j] * acc[(j*7+3) % 40];
    o[i] = s;
}
