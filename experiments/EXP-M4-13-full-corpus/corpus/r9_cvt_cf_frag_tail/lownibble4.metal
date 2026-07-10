#include <metal_stdlib>
using namespace metal;

// subgroup product reduction -> the low-nibble-4 datapath residue (frag_pos_read catch)
kernel void sg_prod_u32(device uint* out, device const uint* a, uint i [[thread_position_in_grid]]) {
    uint v = a[i];
    uint p = simd_product(v);
    out[i] = p;
}
kernel void sg_prod_s32(device int* out, device const int* a, uint i [[thread_position_in_grid]]) {
    int v = a[i];
    int p = simd_product(v);
    out[i] = p;
}
kernel void sg_reduce_mul(device uint* out, device const uint* a, uint i [[thread_position_in_grid]]) {
    uint v = a[i];
    uint p = simd_prefix_exclusive_product(v);
    out[i] = p;
}
kernel void k_powr(device float* out, device const float* a, device const float* b, uint i [[thread_position_in_grid]]) {
    out[i] = powr(a[i], b[i]);
}
kernel void k_cospi(device float* out, device const float* a, uint i [[thread_position_in_grid]]) {
    out[i] = cospi(a[i]);
}
