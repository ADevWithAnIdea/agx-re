#include <metal_stdlib>
using namespace metal;

constexpr sampler smp(coord::normalized, address::clamp_to_edge, filter::nearest, mip_filter::nearest);
constexpr sampler smpc(coord::normalized, address::clamp_to_edge, filter::nearest, mip_filter::nearest, compare_func::less);

// --- plain 2D (baseline: likely NO tex_addr_setup) ---
kernel void k_plain(texture2d<float> tex [[texture(0)]],
                    device const float *cin [[buffer(0)]],
                    device float *out [[buffer(2)]],
                    uint tid [[thread_position_in_grid]]) {
    out[tid] = tex.sample(smp, float2(cin[2*tid+0], cin[2*tid+1])).x;
}

// --- 2D with constant integer offset ---
kernel void k_off(texture2d<float> tex [[texture(0)]],
                  device const float *cin [[buffer(0)]],
                  device float *out [[buffer(2)]],
                  uint tid [[thread_position_in_grid]]) {
    out[tid] = tex.sample(smp, float2(cin[2*tid+0], cin[2*tid+1]), int2(3, 1)).x;
}

// --- 2D with explicit LOD level ---
kernel void k_lod(texture2d<float> tex [[texture(0)]],
                  device const float *cin [[buffer(0)]],
                  device float *out [[buffer(2)]],
                  uint tid [[thread_position_in_grid]]) {
    out[tid] = tex.sample(smp, float2(cin[2*tid+0], cin[2*tid+1]), level(cin[2*tid+2])).x;
}

// --- 2D with explicit gradient ---
kernel void k_grad(texture2d<float> tex [[texture(0)]],
                   device const float *cin [[buffer(0)]],
                   device float *out [[buffer(2)]],
                   uint tid [[thread_position_in_grid]]) {
    float2 uv = float2(cin[4*tid+0], cin[4*tid+1]);
    float2 dx = float2(cin[4*tid+2], 0.0);
    float2 dy = float2(0.0, cin[4*tid+3]);
    out[tid] = tex.sample(smp, uv, gradient2d(dx, dy)).x;
}

// --- cube sample (coord projection) ---
kernel void k_cube(texturecube<float> tex [[texture(0)]],
                   device const float *cin [[buffer(0)]],
                   device float *out [[buffer(2)]],
                   uint tid [[thread_position_in_grid]]) {
    out[tid] = tex.sample(smp, float3(cin[3*tid+0], cin[3*tid+1], cin[3*tid+2])).x;
}

// --- 3D sample ---
kernel void k_3d(texture3d<float> tex [[texture(0)]],
                 device const float *cin [[buffer(0)]],
                 device float *out [[buffer(2)]],
                 uint tid [[thread_position_in_grid]]) {
    out[tid] = tex.sample(smp, float3(cin[3*tid+0], cin[3*tid+1], cin[3*tid+2])).x;
}

// --- 2D array sample (array index) ---
kernel void k_arr(texture2d_array<float> tex [[texture(0)]],
                  device const float *cin [[buffer(0)]],
                  device float *out [[buffer(2)]],
                  uint tid [[thread_position_in_grid]]) {
    out[tid] = tex.sample(smp, float2(cin[3*tid+0], cin[3*tid+1]), uint(cin[3*tid+2])).x;
}

// --- depth compare sample ---
kernel void k_cmp(depth2d<float> tex [[texture(0)]],
                  device const float *cin [[buffer(0)]],
                  device float *out [[buffer(2)]],
                  uint tid [[thread_position_in_grid]]) {
    out[tid] = tex.sample_compare(smpc, float2(cin[3*tid+0], cin[3*tid+1]), cin[3*tid+2]);
}

// --- read (integer coords, no sampler) ---
kernel void k_read(texture2d<float, access::read> tex [[texture(0)]],
                   device const float *cin [[buffer(0)]],
                   device float *out [[buffer(2)]],
                   uint tid [[thread_position_in_grid]]) {
    out[tid] = tex.read(uint2(uint(cin[2*tid+0]), uint(cin[2*tid+1]))).x;
}
