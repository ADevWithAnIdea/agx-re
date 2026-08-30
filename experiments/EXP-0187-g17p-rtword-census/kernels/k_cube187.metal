// EXP-0187 CUBE / CUBE-ARRAY census candidates (AUTHORED BY US; OWN-SHADER).
//
// CENSUS QUESTION (target 2): can ANY MSL we author make the G17P compiler emit
// `cubearray_coord_const` -- the 4-byte word `f0 c0 04 <b3>` that `db.json` says
// feeds the cube/cube-array face-select coordinate math?
//
// This field has been DECLINED on a measured basis before (EXP-0184: 0
// occurrences across 24 carriers; EXP-0148: 0 firings in 1080 corpus files under
// the committed tokenizer, because in `k_tex_array_cube.hex` -- the kernel it is
// NAMED after -- the `f0 c0 04` signature sits at byte 48, INTERIOR to the
// 12-byte `tex_addr_setup` token spanning 40..52, so it cannot fire). So the
// question is not "sweep it" but "can we build a carrier at all". These 12
// constructs are the attempt. A bounded negative -- "12 constructs tried, none
// emitted it" -- is the deliverable if they all fail.
//
// The census records BOTH numbers, because they answer different questions:
//   signature hits  : the raw `f0 c0 04` byte pattern anywhere in our own code
//                     (an upper bound; a hit may be another op's operand tail)
//   tokenizer hits  : the mnemonic actually emitted by a resync walk from 0
//                     (the number that decides whether a carrier is buildable)
//
// CLEAN-ROOM: our own MSL only; compiled with the public Metal API; scanned with
// our own tools. No Apple binary is disassembled.
#include <metal_stdlib>
using namespace metal;

constexpr sampler smp(coord::normalized, filter::linear, mip_filter::linear,
                      address::clamp_to_edge);
constexpr sampler smpn(coord::normalized, filter::nearest, mip_filter::nearest,
                       address::clamp_to_edge);
constexpr sampler smpc(coord::normalized, filter::linear, mip_filter::linear,
                       address::clamp_to_edge, compare_func::less);

// 1. plain cube sample
kernel void k_cu_sample(device float4 *out [[buffer(0)]],
                        texturecube<float> t [[texture(0)]],
                        device const float3 *dir [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    out[gid] = t.sample(smp, dir[gid]);
}
// 2. cube ARRAY sample (the named construct)
kernel void k_cu_arr(device float4 *out [[buffer(0)]],
                     texturecube_array<float> t [[texture(0)]],
                     device const float4 *dir [[buffer(1)]],
                     uint gid [[thread_position_in_grid]]) {
    out[gid] = t.sample(smp, dir[gid].xyz, uint(dir[gid].w));
}
// 3. cube array, NEAREST filtering (no LOD math)
kernel void k_cu_arr_n(device float4 *out [[buffer(0)]],
                       texturecube_array<float> t [[texture(0)]],
                       device const float4 *dir [[buffer(1)]],
                       uint gid [[thread_position_in_grid]]) {
    out[gid] = t.sample(smpn, dir[gid].xyz, uint(dir[gid].w));
}
// 4. cube array, explicit LOD
kernel void k_cu_arr_lod(device float4 *out [[buffer(0)]],
                         texturecube_array<float> t [[texture(0)]],
                         device const float4 *dir [[buffer(1)]],
                         uint gid [[thread_position_in_grid]]) {
    out[gid] = t.sample(smp, dir[gid].xyz, uint(dir[gid].w), level(1.5f));
}
// 5. cube array, explicit GRADIENT (gradientcube)
kernel void k_cu_arr_grad(device float4 *out [[buffer(0)]],
                          texturecube_array<float> t [[texture(0)]],
                          device const float4 *dir [[buffer(1)]],
                          device const float3 *dd [[buffer(2)]],
                          uint gid [[thread_position_in_grid]]) {
    out[gid] = t.sample(smp, dir[gid].xyz, uint(dir[gid].w),
                        gradientcube(dd[gid], dd[gid + 1]));
}
// 6. cube array, bias
kernel void k_cu_arr_bias(device float4 *out [[buffer(0)]],
                          texturecube_array<float> t [[texture(0)]],
                          device const float4 *dir [[buffer(1)]],
                          uint gid [[thread_position_in_grid]]) {
    out[gid] = t.sample(smp, dir[gid].xyz, uint(dir[gid].w), bias(0.75f));
}
// 7. cube array GATHER
kernel void k_cu_arr_gather(device float4 *out [[buffer(0)]],
                            texturecube_array<float> t [[texture(0)]],
                            device const float4 *dir [[buffer(1)]],
                            uint gid [[thread_position_in_grid]]) {
    out[gid] = t.gather(smp, dir[gid].xyz, uint(dir[gid].w));
}
// 8. cube gather
kernel void k_cu_gather(device float4 *out [[buffer(0)]],
                        texturecube<float> t [[texture(0)]],
                        device const float3 *dir [[buffer(1)]],
                        uint gid [[thread_position_in_grid]]) {
    out[gid] = t.gather(smp, dir[gid]);
}
// 9. DEPTH cube array, sample_compare
kernel void k_cu_depth(device float *out [[buffer(0)]],
                       depthcube_array<float> t [[texture(0)]],
                       device const float4 *dir [[buffer(1)]],
                       uint gid [[thread_position_in_grid]]) {
    out[gid] = t.sample_compare(smpc, dir[gid].xyz, uint(dir[gid].w), 0.5f);
}
// 10. HALF cube array
kernel void k_cu_half(device half4 *out [[buffer(0)]],
                      texturecube_array<half> t [[texture(0)]],
                      device const float4 *dir [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    out[gid] = t.sample(smp, dir[gid].xyz, uint(dir[gid].w));
}
// 11. cube array READ (integer face + coordinate, no face-select math expected)
kernel void k_cu_read(device float4 *out [[buffer(0)]],
                      texturecube_array<float, access::read> t [[texture(0)]],
                      device const uint4 *c [[buffer(1)]],
                      uint gid [[thread_position_in_grid]]) {
    out[gid] = t.read(c[gid].xy, c[gid].z, c[gid].w, 0);
}
// 12. cube array sample with a RUNTIME array index and a dependent direction --
//     the shape most likely to force the full face-select + reciprocal chain.
kernel void k_cu_dyn(device float4 *out [[buffer(0)]],
                     texturecube_array<float> t [[texture(0)]],
                     device const float4 *dir [[buffer(1)]],
                     uint gid [[thread_position_in_grid]]) {
    float3 d = normalize(dir[gid].xyz * (1.0f + float(gid)));
    uint  ai = uint(dir[gid].w) + (gid & 3u);
    float4 a = t.sample(smp, d, ai);
    float4 b = t.sample(smp, d.zyx, ai + 1u, level(0.0f));
    out[gid] = a * 3.0f + b;
}
