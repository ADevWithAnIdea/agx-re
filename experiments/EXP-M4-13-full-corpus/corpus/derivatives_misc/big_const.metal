#include <metal_stdlib>
using namespace metal;
// Large program-scope constant tables indexed at runtime. Probes the AGX
// constant-memory addressing mode (uniform/constant load) and how a 64-entry
// table is materialized (constant buffer vs. immediate spill).
constant float tabA[64] = {
    0.0f, 1.5f, 2.25f, 3.125f, 4.0f, 5.5f, 6.75f, 7.875f,
    8.0f, 9.5f, 10.25f, 11.125f, 12.0f, 13.5f, 14.75f, 15.875f,
    16.0f, 17.5f, 18.25f, 19.125f, 20.0f, 21.5f, 22.75f, 23.875f,
    24.0f, 25.5f, 26.25f, 27.125f, 28.0f, 29.5f, 30.75f, 31.875f,
    32.0f, 33.5f, 34.25f, 35.125f, 36.0f, 37.5f, 38.75f, 39.875f,
    40.0f, 41.5f, 42.25f, 43.125f, 44.0f, 45.5f, 46.75f, 47.875f,
    48.0f, 49.5f, 50.25f, 51.125f, 52.0f, 53.5f, 54.75f, 55.875f,
    56.0f, 57.5f, 58.25f, 59.125f, 60.0f, 61.5f, 62.75f, 63.875f
};
constant int tabB[16] = {
    -8, -7, -6, -5, -4, -3, -2, -1, 1, 2, 4, 8, 16, 32, 64, 128
};
kernel void k(device float* o [[buffer(0)]],
              device const uint* idx [[buffer(1)]],
              uint i [[thread_position_in_grid]]) {
    uint j = idx[i];
    o[i] = tabA[j & 63u] + float(tabB[j & 15u]);
}
