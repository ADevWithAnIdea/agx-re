// EXP-0106 authored MSL kernels (OWN-SHADER). Every kernel here is our own
// source, compiled at runtime via -[MTLDevice newLibraryWithSource:options:]
// (no `metal` CLI, no Apple-authored shader). None of this is copied from
// any Apple binary or private material. Convention (matches EXP-0095, our
// own prior work): a 16-word `device uint* out [[buffer(0)]]` output array
// the host pre-fills with sentinel 0xEEEEEEEE; a kernel writes only the
// words it documents; float results go back as raw bits via as_type<uint>.
#include <metal_stdlib>
using namespace metal;

// ============================================================ b02: mip-count ceiling + explicit-level() edge values (TEX-24)

// 16384-wide, 15-mip-level 2D texture. Level L populated with byte (0xC0+L).
// get_num_mip_levels() must read 15; read() at level 14 (last legal) must
// read 0xCE; read() at level 15 (first illegal) is OOB per the public MSL
// spec's OOB-read rule and must read 0.
kernel void k_b02_mip15(texture2d<uint> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  out[0] = t.get_num_mip_levels();
  out[1] = t.read(uint2(0, 0), 14).x;
  out[2] = t.read(uint2(0, 0), 15).x;
}

// 16x16, 4-mip-level 2D texture, level L populated with byte (0xD0+L).
// Explicit level() operand supplied dynamically (from a buffer, not a
// compile-time literal) so NaN/Inf bit patterns can be injected exactly.
// mip_filter=nearest sampler selects one discrete level (no blend).
kernel void k_b02_levelsweep(texture2d<uint> t [[texture(0)]], sampler s [[sampler(0)]],
    constant float& lod [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.sample(s, float2(0.5, 0.5), level(lod)).x;
}

// ============================================================ b04: dynamic min_lod_clamp() operand across sample forms (TEX-05)

// 16x16, 4-mip-level 2D texture, level L populated with byte (0xE0+L).
// Implicit-LOD sample in a compute kernel has base LOD 0 (no derivatives);
// min_lod_clamp(minlod) must raise the effective LOD to minlod (clamped to
// [0, mipCount-1]) even though it is a genuinely dynamic (buffer-loaded)
// value, not a compile-time constant.
kernel void k_b04_implicit_minlod(texture2d<uint> t [[texture(0)]], sampler s [[sampler(0)]],
    constant float& minlod [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.sample(s, float2(0.5, 0.5), min_lod_clamp(minlod)).x;
}
// bias(0) + min_lod_clamp(minlod): base LOD 0 + bias 0 = 0, then raised to
// minlod by the clamp -- the combined 2-parameter overload MSL exposes for
// bias (spec 6.12.3: bias_options + min_lod_clamp_options + offset).
kernel void k_b04_bias_minlod(texture2d<uint> t [[texture(0)]], sampler s [[sampler(0)]],
    constant float& minlod [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.sample(s, float2(0.5, 0.5), bias(0.0), min_lod_clamp(minlod)).x;
}
// gradient2d(0,0) + min_lod_clamp(minlod): a zero gradient alone would
// select LOD 0 by this project's established rho/lambda formula
// (EXP-0094); min_lod_clamp must still raise it to minlod.
kernel void k_b04_grad_minlod(texture2d<uint> t [[texture(0)]], sampler s [[sampler(0)]],
    constant float& minlod [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.sample(s, float2(0.5, 0.5), gradient2d(float2(0, 0), float2(0, 0)), min_lod_clamp(minlod)).x;
}
// sample_compare + min_lod_clamp: depth2d, level L stores depth L/3.0
// (0, .333, .667, 1.0). compareFunc=less, ref=0.5: less<0.333->pass only at
// L>=2. mip_filter=nearest selects one discrete level.
kernel void k_b04_compare_minlod(depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]],
    constant float& minlod [[buffer(1)]], device uint* out [[buffer(0)]]) {
  float r = t.sample_compare(s, float2(0.5, 0.5), 0.5, min_lod_clamp(minlod));
  out[0] = as_type<uint>(r);
}

// ============================================================ b05: dynamic bindless texture query, per-lane non-uniform (TEX-06)
#define B05_CAP 8
struct AB_Query { array<texture2d<uint>, B05_CAP> tex [[id(0)]]; };
kernel void k_b05_bindless_query(constant AB_Query& ab [[buffer(0)]], device uint* out [[buffer(1)]],
    uint tid [[thread_position_in_grid]]) {
  // Each of 4 dispatched lanes indexes its OWN, distinct array entry (a
  // genuinely non-uniform per-lane bindless index, unlike a uniform
  // shader-wide selection), and reports what get_width/get_num_mip_levels
  // returns for THAT lane's texture.
  out[tid] = ab.tex[tid].get_width();
  out[4 + tid] = ab.tex[tid].get_num_mip_levels();
}

// ============================================================ b06: OOB remainder -- 3D depth-axis (TEX-13)
// 4x4x4 r8uint 3D texture, texel value = z (0..3) uniformly over x,y.
// read(coord) at z=3 (last legal) must read 3; z=4 (first illegal) is an
// OOB coordinate per the public spec's OOB-read rule and must read 0.
kernel void k_b06_3d_depth_oob(texture3d<uint> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(uint3(0, 0, 3)).x;
  out[1] = t.read(uint3(0, 0, 4)).x;
}

// ============================================================ b08: 16 simultaneously distinguishable direct samplers (TEX-17)
// One 2x2 r32float texture; texel content distinguishes edge vs. non-edge.
// 16 samplers alternate address mode clampToZero (even index) vs.
// clampToEdge (odd index); all 16 sample the SAME out-of-range coordinate
// (u=-0.25, left of [0,1)) so the address-mode divergence is the only
// thing that can distinguish them (EXP-0063 established filter mode does
// NOT discriminate at texel-center UVs; address mode at an OOB coordinate
// DOES). Even slots must read 0 (clampToZero border); odd slots must read
// the left-edge texel's nonzero value (clampToEdge).
kernel void k_b08_sampler16(texture2d<float> t [[texture(0)]],
    sampler s0 [[sampler(0)]], sampler s1 [[sampler(1)]], sampler s2 [[sampler(2)]], sampler s3 [[sampler(3)]],
    sampler s4 [[sampler(4)]], sampler s5 [[sampler(5)]], sampler s6 [[sampler(6)]], sampler s7 [[sampler(7)]],
    sampler s8 [[sampler(8)]], sampler s9 [[sampler(9)]], sampler s10 [[sampler(10)]], sampler s11 [[sampler(11)]],
    sampler s12 [[sampler(12)]], sampler s13 [[sampler(13)]], sampler s14 [[sampler(14)]], sampler s15 [[sampler(15)]],
    device uint* out [[buffer(0)]]) {
  float2 c = float2(-0.25, 0.5);
  out[0] = as_type<uint>(t.sample(s0, c).x);   out[1] = as_type<uint>(t.sample(s1, c).x);
  out[2] = as_type<uint>(t.sample(s2, c).x);   out[3] = as_type<uint>(t.sample(s3, c).x);
  out[4] = as_type<uint>(t.sample(s4, c).x);   out[5] = as_type<uint>(t.sample(s5, c).x);
  out[6] = as_type<uint>(t.sample(s6, c).x);   out[7] = as_type<uint>(t.sample(s7, c).x);
  out[8] = as_type<uint>(t.sample(s8, c).x);   out[9] = as_type<uint>(t.sample(s9, c).x);
  out[10] = as_type<uint>(t.sample(s10, c).x); out[11] = as_type<uint>(t.sample(s11, c).x);
  out[12] = as_type<uint>(t.sample(s12, c).x); out[13] = as_type<uint>(t.sample(s13, c).x);
  out[14] = as_type<uint>(t.sample(s14, c).x); out[15] = as_type<uint>(t.sample(s15, c).x);
}

// ============================================================ b09: offset-pair boundary sweep + dynamic (non-constant) offset (TEX-03/04)
// 32x32 r32uint texture, texel(row,col) = row*32+col (0..1023), so any two
// distinct texels read back distinct values -- footprint identity is
// directly legible from the returned number. Base coordinate sits exactly
// on a grid intersection (16,16) far from every edge, so every offset in
// [-8,7]^2 stays fully in-bounds and no address-mode clamp/wrap can
// confound the reading (address mode is irrelevant here by construction).
kernel void k_b09_gather_offset(texture2d<uint> t [[texture(0)]], sampler s [[sampler(0)]],
    constant int2& off [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.gather(s, float2(16.0 / 32.0, 16.0 / 32.0), off, component::x).x;
}
// Dynamic (per-lane, runtime-loaded, non-constant) offset: 4 lanes, each
// with its own int2 offset value loaded from a buffer -- structurally
// impossible to express as a single compile-time literal, the direct
// TEX-04 test.
kernel void k_b09_gather_offset_dynamic(texture2d<uint> t [[texture(0)]], sampler s [[sampler(0)]],
    constant int2* offs [[buffer(1)]], device uint* out [[buffer(0)]], uint tid [[thread_position_in_grid]]) {
  out[tid] = t.gather(s, float2(16.0 / 32.0, 16.0 / 32.0), offs[tid], component::x).x;
}
