// EXP-0095 authored MSL kernels (OWN-SHADER). Every kernel here is our own
// source, compiled at runtime via -[MTLDevice newLibraryWithSource:options:]
// (no `metal` CLI, no Apple-authored shader). None of this is copied from
// any Apple binary or private material.
//
// Uniform convention across every kernel in this file:
//  - a 16-word (64-byte) `device uint* out [[buffer(0)]]` output array the
//    host pre-fills with the sentinel 0xEEEEEEEE before dispatch. A kernel
//    writes only the words it is documented to write; unused words must
//    stay at the sentinel so the host can detect an unexpected/overflowing
//    write downstream (the register-move-and-liveness.md rule: validate by
//    a downstream consumer read, never by the producing instruction alone).
//  - float results are written back as their raw bit pattern via
//    as_type<uint>(...) so comparisons are byte-exact, never
//    epsilon-fuzzy float comparisons.
//  - every family uses a two-dispatch structure within one command buffer:
//    a "populate" kernel writes known, distinguishable content into the
//    resource(s) under test, then a "probe" kernel exercises the operation
//    under test and/or reads back content into `out`.
#include <metal_stdlib>
using namespace metal;

// ============================================================ GLTEX-A05: 1D / 1D-array matrix
// MSL surface established by pre-freeze exploration (work/explore/probe1d.metal,
// not evidence): texture1d/texture1d_array expose only sample(sampler,coord)
// (implicit LOD only -- no bias/level/gradient/offset/gather overloads exist
// for 1D at the MSL level), read(coord[,lod]), write(color,coord[,lod]),
// get_width()/get_num_mip_levels()/get_array_size(). No depth1d type exists.

kernel void k_a05_1d_populate(texture1d<uint, access::write> t [[texture(0)]], constant uint& width [[buffer(1)]]) {
  for (uint i = 0; i < width; i++) t.write(uint4(0xA5000000u | i, 0, 0, 0), i);
}
kernel void k_a05_1d_sample(texture1d<float> t [[texture(0)]], sampler s [[sampler(0)]], constant float& u [[buffer(1)]], device uint* out [[buffer(0)]]) {
  float4 r = t.sample(s, u);
  out[0] = as_type<uint>(r.x);
}
kernel void k_a05_1d_read(texture1d<uint> t [[texture(0)]], constant uint& coord [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(coord).x;
}
kernel void k_a05_1d_write_probe(texture1d<uint, access::write> t [[texture(0)]], constant uint& coord [[buffer(1)]]) {
  t.write(uint4(0xC0FFEEu, 0, 0, 0), coord);
}
kernel void k_a05_1d_readback(texture1d<uint> t [[texture(0)]], constant uint& width [[buffer(1)]], device uint* out [[buffer(0)]]) {
  // Read back the first 8 texels (or fewer) for aliasing/hole inspection.
  for (uint i = 0; i < 8 && i < width; i++) out[i] = t.read(i).x;
}
kernel void k_a05_1d_size(texture1d<float> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  out[0] = t.get_width();
  out[1] = t.get_num_mip_levels();
}
kernel void k_a05_1darr_populate(texture1d_array<uint, access::write> t [[texture(0)]], constant uint& width [[buffer(1)]], constant uint& layers [[buffer(2)]]) {
  for (uint l = 0; l < layers; l++) for (uint i = 0; i < width; i++) t.write(uint4(0xB6000000u | (l << 8) | i, 0, 0, 0), i, l);
}
kernel void k_a05_1darr_sample(texture1d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], constant float& u [[buffer(1)]], constant uint& layer [[buffer(2)]], device uint* out [[buffer(0)]]) {
  float4 r = t.sample(s, u, layer);
  out[0] = as_type<uint>(r.x);
}
kernel void k_a05_1darr_read(texture1d_array<uint> t [[texture(0)]], constant uint& coord [[buffer(1)]], constant uint& layer [[buffer(2)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(coord, layer).x;
}
kernel void k_a05_1darr_size(texture1d_array<float> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  out[0] = t.get_width();
  out[1] = t.get_array_size();
}

// ============================================================ GLTEX-A06: shadow/cube/cube-array matrix
// depth2d_array / depthcube / depthcube_array. All of sample_compare
// (implicit/level/bias/gradient/offset-where-applicable) and gather_compare
// compiled in pre-freeze exploration (work/explore/probeshadow.metal).

kernel void k_a06_d2darr_compare_suite(depth2d_array<float> t [[texture(0)]],
    sampler s_less [[sampler(0)]], sampler s_lequal [[sampler(1)]], sampler s_greater [[sampler(2)]], sampler s_gequal [[sampler(3)]],
    sampler s_equal [[sampler(4)]], sampler s_notequal [[sampler(5)]], sampler s_always [[sampler(6)]], sampler s_never [[sampler(7)]],
    constant uint& layer [[buffer(1)]], constant float& ref [[buffer(2)]], device uint* out [[buffer(0)]]) {
  out[0] = as_type<uint>(t.sample_compare(s_less, float2(0.5, 0.5), layer, ref));
  out[1] = as_type<uint>(t.sample_compare(s_lequal, float2(0.5, 0.5), layer, ref));
  out[2] = as_type<uint>(t.sample_compare(s_greater, float2(0.5, 0.5), layer, ref));
  out[3] = as_type<uint>(t.sample_compare(s_gequal, float2(0.5, 0.5), layer, ref));
  out[4] = as_type<uint>(t.sample_compare(s_equal, float2(0.5, 0.5), layer, ref));
  out[5] = as_type<uint>(t.sample_compare(s_notequal, float2(0.5, 0.5), layer, ref));
  out[6] = as_type<uint>(t.sample_compare(s_always, float2(0.5, 0.5), layer, ref));
  out[7] = as_type<uint>(t.sample_compare(s_never, float2(0.5, 0.5), layer, ref));
}
kernel void k_a06_d2darr_layer_boundary(depth2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]],
    constant uint3& layers [[buffer(1)]], constant float& ref [[buffer(2)]], device uint* out [[buffer(0)]]) {
  out[0] = as_type<uint>(t.sample_compare(s, float2(0.5, 0.5), layers.x, ref));
  out[1] = as_type<uint>(t.sample_compare(s, float2(0.5, 0.5), layers.y, ref));
  out[2] = as_type<uint>(t.sample_compare(s, float2(0.5, 0.5), layers.z, ref));
}
kernel void k_a06_d2darr_forms(depth2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]],
    constant uint& layer [[buffer(1)]], constant float& ref [[buffer(2)]], device uint* out [[buffer(0)]]) {
  out[0] = as_type<uint>(t.sample_compare(s, float2(0.5, 0.5), layer, ref));
  out[1] = as_type<uint>(t.sample_compare(s, float2(0.5, 0.5), layer, ref, level(0.0)));
  out[2] = as_type<uint>(t.sample_compare(s, float2(0.5, 0.5), layer, ref, bias(0.0)));
  out[3] = as_type<uint>(t.sample_compare(s, float2(0.5, 0.5), layer, ref, gradient2d(float2(0.001, 0), float2(0, 0.001))));
  out[4] = as_type<uint>(t.sample_compare(s, float2(0.5, 0.5), layer, ref, level(0.0), int2(0, 0)));
  float4 g = t.gather_compare(s, float2(0.5, 0.5), layer, ref);
  out[5] = as_type<uint>(g.x);
}
kernel void k_a06_dcube_faces(depthcube<float> t [[texture(0)]], sampler s [[sampler(0)]], constant float& ref [[buffer(1)]], device uint* out [[buffer(0)]]) {
  float3 dirs[6] = { float3(1,0,0), float3(-1,0,0), float3(0,1,0), float3(0,-1,0), float3(0,0,1), float3(0,0,-1) };
  for (uint f = 0; f < 6; f++) out[f] = as_type<uint>(t.sample_compare(s, dirs[f], ref));
}
kernel void k_a06_dcube_forms(depthcube<float> t [[texture(0)]], sampler s [[sampler(0)]], constant float& ref [[buffer(1)]], device uint* out [[buffer(0)]]) {
  float3 d = float3(1, 0, 0);
  out[0] = as_type<uint>(t.sample_compare(s, d, ref));
  out[1] = as_type<uint>(t.sample_compare(s, d, ref, level(0.0)));
  out[2] = as_type<uint>(t.sample_compare(s, d, ref, bias(0.0)));
  float4 g = t.gather_compare(s, d, ref);
  out[3] = as_type<uint>(g.x);
}
kernel void k_a06_dcubearr_faces(depthcube_array<float> t [[texture(0)]], sampler s [[sampler(0)]], constant uint& layer [[buffer(1)]], constant float& ref [[buffer(2)]], device uint* out [[buffer(0)]]) {
  float3 dirs[6] = { float3(1,0,0), float3(-1,0,0), float3(0,1,0), float3(0,-1,0), float3(0,0,1), float3(0,0,-1) };
  for (uint f = 0; f < 6; f++) out[f] = as_type<uint>(t.sample_compare(s, dirs[f], layer, ref));
}
kernel void k_a06_dcubearr_layer_boundary(depthcube_array<float> t [[texture(0)]], sampler s [[sampler(0)]], constant uint3& layers [[buffer(1)]], constant float& ref [[buffer(2)]], device uint* out [[buffer(0)]]) {
  float3 d = float3(1, 0, 0);
  out[0] = as_type<uint>(t.sample_compare(s, d, layers.x, ref));
  out[1] = as_type<uint>(t.sample_compare(s, d, layers.y, ref));
  out[2] = as_type<uint>(t.sample_compare(s, d, layers.z, ref));
}
kernel void k_a06_dcubearr_forms(depthcube_array<float> t [[texture(0)]], sampler s [[sampler(0)]], constant uint& layer [[buffer(1)]], constant float& ref [[buffer(2)]], device uint* out [[buffer(0)]]) {
  float3 d = float3(1, 0, 0);
  out[0] = as_type<uint>(t.sample_compare(s, d, layer, ref));
  out[1] = as_type<uint>(t.sample_compare(s, d, layer, ref, level(0.0)));
  out[2] = as_type<uint>(t.sample_compare(s, d, layer, ref, bias(0.0)));
  float4 g = t.gather_compare(s, d, layer, ref);
  out[3] = as_type<uint>(g.x);
}

// ============================================================ GLTEX-A04: array-layer conversion + boundary
kernel void k_a04_2darr_populate(texture2d_array<uint, access::write> t [[texture(0)]], constant uint& layers [[buffer(1)]]) {
  for (uint l = 0; l < layers; l++) t.write(uint4(0xD4000000u | l, 0, 0, 0), uint2(0, 0), l);
}
// Conversion-rule sweep: MSL's array-index parameter is `uint` only (no
// float overload exists for texture2d_array::sample -- established in
// pre-freeze exploration by inspecting the public MSL header declarations,
// consistent with every compile in probeshadow.metal/probe1d.metal never
// offering a float-layer overload). A driver translating an OpenGL float
// array-layer coordinate must therefore itself choose and apply a rounding
// rule before calling the uint-typed Metal entry point; MSL's own round() is
// the public, spec-defined (round-half-away-from-zero) function we use here
// as the candidate rule, then observe the HARDWARE's response (clamping) at
// the resulting integer index. This kernel does NOT establish what a native
// Apple9 ISA sample instruction does with a raw float coordinate register
// (that needs assembler-level splicing -- out of scope here, see RESULTS).
kernel void k_a04_2darr_conversion(texture2d_array<uint> t [[texture(0)]], constant float* layers9 [[buffer(1)]], device uint* out [[buffer(0)]]) {
  for (uint i = 0; i < 9; i++) {
    float lf = layers9[i];
    uint li = uint(round(lf));
    out[i] = t.read(uint2(0, 0), li).x;
  }
}
kernel void k_a04_2darr_boundary_sample(texture2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], constant uint3& layers [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = as_type<uint>(t.sample(s, float2(0.5, 0.5), layers.x).x);
  out[1] = as_type<uint>(t.sample(s, float2(0.5, 0.5), layers.y).x);
  out[2] = as_type<uint>(t.sample(s, float2(0.5, 0.5), layers.z).x);
}
kernel void k_a04_2darr_boundary_fetch(texture2d_array<uint> t [[texture(0)]], constant uint3& layers [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(uint2(0, 0), layers.x).x;
  out[1] = t.read(uint2(0, 0), layers.y).x;
  out[2] = t.read(uint2(0, 0), layers.z).x;
}
kernel void k_a04_2darr_boundary_gather(texture2d_array<float> t [[texture(0)]], sampler s [[sampler(0)]], constant uint3& layers [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = as_type<uint>(t.gather(s, float2(0.5, 0.5), layers.x).x);
  out[1] = as_type<uint>(t.gather(s, float2(0.5, 0.5), layers.y).x);
  out[2] = as_type<uint>(t.gather(s, float2(0.5, 0.5), layers.z).x);
}
kernel void k_a04_cubearr_populate(texturecube_array<uint, access::write> t [[texture(0)]], constant uint& layers [[buffer(1)]]) {
  for (uint l = 0; l < layers; l++) for (uint f = 0; f < 6; f++) t.write(uint4(0xCA000000u | (l << 4) | f, 0, 0, 0), uint2(0, 0), f, l);
}
kernel void k_a04_cubearr_conversion(texturecube_array<uint> t [[texture(0)]], constant float* layers9 [[buffer(1)]], device uint* out [[buffer(0)]]) {
  for (uint i = 0; i < 9; i++) {
    uint li = uint(round(layers9[i]));
    out[i] = t.read(uint2(0, 0), 0u, li).x;
  }
}
kernel void k_a04_cubearr_boundary_sample(texturecube_array<float> t [[texture(0)]], sampler s [[sampler(0)]], constant uint3& layers [[buffer(1)]], device uint* out [[buffer(0)]]) {
  float3 d = float3(1, 0, 0);
  out[0] = as_type<uint>(t.sample(s, d, layers.x).x);
  out[1] = as_type<uint>(t.sample(s, d, layers.y).x);
  out[2] = as_type<uint>(t.sample(s, d, layers.z).x);
}
kernel void k_a04_cubearr_boundary_fetch(texturecube_array<uint> t [[texture(0)]], constant uint3& layers [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(uint2(0, 0), 0u, layers.x).x;
  out[1] = t.read(uint2(0, 0), 0u, layers.y).x;
  out[2] = t.read(uint2(0, 0), 0u, layers.z).x;
}
kernel void k_a04_cubearr_boundary_gather(texturecube_array<float> t [[texture(0)]], sampler s [[sampler(0)]], constant uint3& layers [[buffer(1)]], device uint* out [[buffer(0)]]) {
  float3 d = float3(1, 0, 0);
  out[0] = as_type<uint>(t.gather(s, d, layers.x).x);
  out[1] = as_type<uint>(t.gather(s, d, layers.y).x);
  out[2] = as_type<uint>(t.gather(s, d, layers.z).x);
}

// ============================================================ GLTEX-A07: texel buffer boundary
// texture_buffer<T,access> established in pre-freeze exploration
// (work/explore/probebuf.metal): read/write/get_width all compile. RGB32 is
// not an available MTLPixelFormat at all (no MTLPixelFormatRGB32* constant
// exists in the public enum) -- established by direct compile-time lookup,
// not by hardware probing; recorded as a structural (non-hardware) fact in
// RESULTS.md. Five texel sizes covered here: 1/2/4/8/16 bytes.
kernel void k_a07_tb_populate_r8(texture_buffer<uint, access::write> t [[texture(0)]], constant uint& n [[buffer(1)]]) {
  for (uint i = 0; i < n; i++) t.write(uint4(0x11000000u | i, 0, 0, 0), i);
}
kernel void k_a07_tb_read3_r8(texture_buffer<uint, access::read> t [[texture(0)]], constant uint3& idx [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(idx.x).x;
  out[1] = t.read(idx.y).x;
  out[2] = t.read(idx.z).x;
}
kernel void k_a07_tb_write3_r8(texture_buffer<uint, access::write> t [[texture(0)]], constant uint3& idx [[buffer(1)]]) {
  t.write(uint4(0xC0FFEEu, 0, 0, 0), idx.x);
  t.write(uint4(0xC0FFEEu, 0, 0, 0), idx.y);
  t.write(uint4(0xC0FFEEu, 0, 0, 0), idx.z);
}
kernel void k_a07_tb_readback8_r8(texture_buffer<uint, access::read> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  for (uint i = 0; i < 8; i++) out[i] = t.read(i).x;
}
// rg16uint (2-byte texel)
kernel void k_a07_tb_populate_rg8(texture_buffer<uint, access::write> t [[texture(0)]], constant uint& n [[buffer(1)]]) {
  for (uint i = 0; i < n; i++) t.write(uint4(0x22000000u | i, 0, 0, 0), i);
}
kernel void k_a07_tb_read3_rg8(texture_buffer<uint, access::read> t [[texture(0)]], constant uint3& idx [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(idx.x).x;
  out[1] = t.read(idx.y).x;
  out[2] = t.read(idx.z).x;
}
kernel void k_a07_tb_write3_rg8(texture_buffer<uint, access::write> t [[texture(0)]], constant uint3& idx [[buffer(1)]]) {
  t.write(uint4(0xC0FFEEu, 0, 0, 0), idx.x);
  t.write(uint4(0xC0FFEEu, 0, 0, 0), idx.y);
  t.write(uint4(0xC0FFEEu, 0, 0, 0), idx.z);
}
// rgba8uint (4-byte texel)
kernel void k_a07_tb_populate_rgba8(texture_buffer<uint, access::write> t [[texture(0)]], constant uint& n [[buffer(1)]]) {
  for (uint i = 0; i < n; i++) t.write(uint4(0x44000000u | i, i, i, i), i);
}
kernel void k_a07_tb_read3_rgba8(texture_buffer<uint, access::read> t [[texture(0)]], constant uint3& idx [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(idx.x).x;
  out[1] = t.read(idx.y).x;
  out[2] = t.read(idx.z).x;
}
kernel void k_a07_tb_write3_rgba8(texture_buffer<uint, access::write> t [[texture(0)]], constant uint3& idx [[buffer(1)]]) {
  t.write(uint4(0xC0FFEEu, 1, 2, 3), idx.x);
  t.write(uint4(0xC0FFEEu, 1, 2, 3), idx.y);
  t.write(uint4(0xC0FFEEu, 1, 2, 3), idx.z);
}
// rgba16uint (8-byte texel)
kernel void k_a07_tb_populate_rgba16(texture_buffer<uint, access::write> t [[texture(0)]], constant uint& n [[buffer(1)]]) {
  for (uint i = 0; i < n; i++) t.write(uint4(0x88000000u | i, i, i, i), i);
}
kernel void k_a07_tb_read3_rgba16(texture_buffer<uint, access::read> t [[texture(0)]], constant uint3& idx [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(idx.x).x;
  out[1] = t.read(idx.y).x;
  out[2] = t.read(idx.z).x;
}
kernel void k_a07_tb_write3_rgba16(texture_buffer<uint, access::write> t [[texture(0)]], constant uint3& idx [[buffer(1)]]) {
  t.write(uint4(0xC0FFEEu, 1, 2, 3), idx.x);
  t.write(uint4(0xC0FFEEu, 1, 2, 3), idx.y);
  t.write(uint4(0xC0FFEEu, 1, 2, 3), idx.z);
}
// rgba32uint (16-byte texel)
kernel void k_a07_tb_populate_rgba32(texture_buffer<uint, access::write> t [[texture(0)]], constant uint& n [[buffer(1)]]) {
  for (uint i = 0; i < n; i++) t.write(uint4(0xAA000000u | i, i, i, i), i);
}
kernel void k_a07_tb_read3_rgba32(texture_buffer<uint, access::read> t [[texture(0)]], constant uint3& idx [[buffer(1)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(idx.x).x;
  out[1] = t.read(idx.y).x;
  out[2] = t.read(idx.z).x;
}
kernel void k_a07_tb_write3_rgba32(texture_buffer<uint, access::write> t [[texture(0)]], constant uint3& idx [[buffer(1)]]) {
  t.write(uint4(0xC0FFEEu, 1, 2, 3), idx.x);
  t.write(uint4(0xC0FFEEu, 1, 2, 3), idx.y);
  t.write(uint4(0xC0FFEEu, 1, 2, 3), idx.z);
}
kernel void k_a07_tb_size(texture_buffer<uint, access::read> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  out[0] = t.get_width();
}

// ============================================================ GLIMG-A01: image load/store/size matrix
// One kernel per dimension form: write a distinguishable canary pattern via
// image store, then read it back via image load, and query size fields --
// all in one dispatch (this IS the round trip the addendum asks for: "for
// every advertised format... execute representative... accesses through the
// actual image instruction path"). r32uint is the primary probe format
// (native atomics + native read_write on every non-MS dimension per
// pre-freeze exploration, work/explore/probeatomic.metal).
kernel void k_a01_1d(texture1d<uint, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(uint4(0x1D000001u, 0, 0, 0), 0u);
  t.fence();
  out[0] = t.read(0u).x;
  out[1] = t.get_width();
  out[2] = t.get_num_mip_levels();
}
kernel void k_a01_1darr(texture1d_array<uint, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(uint4(0x1D000002u, 0, 0, 0), 0u, 0u);
  t.fence();
  out[0] = t.read(0u, 0u).x;
  out[1] = t.get_width();
  out[2] = t.get_array_size();
}
kernel void k_a01_2d(texture2d<uint, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(uint4(0x2D000001u, 0, 0, 0), uint2(0, 0));
  t.fence();
  out[0] = t.read(uint2(0, 0)).x;
  out[1] = t.get_width();
  out[2] = t.get_height();
}
kernel void k_a01_2darr(texture2d_array<uint, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(uint4(0x2D000002u, 0, 0, 0), uint2(0, 0), 0u);
  t.fence();
  out[0] = t.read(uint2(0, 0), 0u).x;
  out[1] = t.get_width();
  out[2] = t.get_array_size();
}
kernel void k_a01_3d(texture3d<uint, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(uint4(0x3D000001u, 0, 0, 0), uint3(0, 0, 0));
  t.fence();
  out[0] = t.read(uint3(0, 0, 0)).x;
  out[1] = t.get_width();
  out[2] = t.get_depth();
}
kernel void k_a01_cube(texturecube<uint, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(uint4(0xCB000001u, 0, 0, 0), uint2(0, 0), 0u);
  t.fence();
  out[0] = t.read(uint2(0, 0), 0u).x;
  out[1] = t.get_width();
}
kernel void k_a01_cubearr(texturecube_array<uint, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(uint4(0xCB000002u, 0, 0, 0), uint2(0, 0), 0u, 0u);
  t.fence();
  out[0] = t.read(uint2(0, 0), 0u, 0u).x;
  out[1] = t.get_width();
  out[2] = t.get_array_size();
}
kernel void k_a01_buffer(texture_buffer<uint, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(uint4(0xB0000001u, 0, 0, 0), 0u);
  t.fence();
  out[0] = t.read(0u).x;
  out[1] = t.get_width();
}
// 2D multisample / multisample-array: MSL's texture2d_ms/texture2d_ms_array
// expose no atomic support (pre-freeze exploration) and typically no
// access::write at all -- registered as a hypothesis-to-falsify; a compile
// or pipeline rejection here is itself the recorded answer for these two
// dimension forms, not a harness defect.
kernel void k_a01_2dms_read(texture2d_ms<uint, access::read> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(uint2(0, 0), 0).x;
  out[1] = t.get_width();
  out[2] = t.get_num_samples();
}
kernel void k_a01_2dmsarr_read(texture2d_ms_array<uint, access::read> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(uint2(0, 0), 0u, 0).x;
  out[1] = t.get_width();
  out[2] = t.get_num_samples();
  out[3] = t.get_array_size();
}
// Format-class sweep on 2D (does the image instruction path round-trip
// correctly for each class; DRV-FMT-01 is the conversion authority, this
// only asks "does the image path itself work", not repeat the conversion-
// rule work of EXP-0079/EXP-0064).
kernel void k_a01_fmt_r32float(texture2d<float, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(float4(0.25, 0, 0, 0), uint2(0, 0));
  t.fence();
  out[0] = as_type<uint>(t.read(uint2(0, 0)).x);
}
kernel void k_a01_fmt_r8unorm(texture2d<float, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(float4(0.5, 0, 0, 0), uint2(0, 0));
  t.fence();
  out[0] = as_type<uint>(t.read(uint2(0, 0)).x);
}
kernel void k_a01_fmt_r8snorm(texture2d<float, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(float4(-0.5, 0, 0, 0), uint2(0, 0));
  t.fence();
  out[0] = as_type<uint>(t.read(uint2(0, 0)).x);
}
kernel void k_a01_fmt_r16uint(texture2d<uint, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(uint4(4321, 0, 0, 0), uint2(0, 0));
  t.fence();
  out[0] = t.read(uint2(0, 0)).x;
}
kernel void k_a01_fmt_r16sint(texture2d<int, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(int4(-1234, 0, 0, 0), uint2(0, 0));
  t.fence();
  out[0] = as_type<uint>(t.read(uint2(0, 0)).x);
}
kernel void k_a01_fmt_rgb10a2unorm(texture2d<float, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(float4(1.0, 0.5, 0.25, 1.0), uint2(0, 0));
  t.fence();
  float4 r = t.read(uint2(0, 0));
  out[0] = as_type<uint>(r.x);
  out[1] = as_type<uint>(r.w);
}
// OOB coordinate + partial-write + unbound + aliasing robustness
kernel void k_a01_2d_oob_read(texture2d<uint, access::read_write> t [[texture(0)]], constant uint2& wh [[buffer(1)]], device uint* out [[buffer(0)]]) {
  t.write(uint4(0x0B000001u, 0, 0, 0), uint2(0, 0));
  t.fence();
  out[0] = t.read(uint2(wh.x, 0)).x;      // x == width: first invalid x
  out[1] = t.read(uint2(0, wh.y)).x;      // y == height: first invalid y
  out[2] = t.read(uint2(wh.x, wh.y)).x;   // both invalid
}
kernel void k_a01_2d_oob_write(texture2d<uint, access::read_write> t [[texture(0)]], constant uint2& wh [[buffer(1)]]) {
  t.write(uint4(0xDEAD0000u, 0, 0, 0), uint2(wh.x, 0));   // OOB store, x
  t.write(uint4(0xDEAD0001u, 0, 0, 0), uint2(0, wh.y));   // OOB store, y
}
kernel void k_a01_2d_oob_readback(texture2d<uint, access::read> t [[texture(0)]], constant uint2& wh [[buffer(1)]], device uint* out [[buffer(0)]]) {
  // Read every legal texel of a small (wh.x * wh.y) texture to detect
  // aliasing/corruption from the preceding OOB-write dispatch.
  uint k = 0;
  for (uint y = 0; y < wh.y && k < 16; y++)
    for (uint x = 0; x < wh.x && k < 16; x++)
      out[k++] = t.read(uint2(x, y)).x;
}
kernel void k_a01_cube_oob_read(texturecube<uint, access::read_write> t [[texture(0)]], constant uint& w [[buffer(1)]], device uint* out [[buffer(0)]]) {
  t.write(uint4(0x0C000001u, 0, 0, 0), uint2(0, 0), 0u);
  t.fence();
  out[0] = t.read(uint2(w, 0), 0u).x;   // OOB x within a valid face
  out[1] = t.read(uint2(0, 0), 6u).x;   // face index 6: first invalid face
}
// Partial-vector write: only channel .x is meaningful for a single-channel
// (r32uint) format; write() always takes a float4/uint4 -- does the store
// touch memory beyond the single logical channel?
kernel void k_a01_partial_write(texture2d<uint, access::read_write> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  t.write(uint4(0x99999999u, 0x11111111u, 0x22222222u, 0x33333333u), uint2(0, 0));
  t.fence();
  out[0] = t.read(uint2(0, 0)).x;
  out[1] = t.read(uint2(0, 0)).y;
  out[2] = t.read(uint2(0, 0)).z;
  out[3] = t.read(uint2(0, 0)).w;
}
// Unbound image argument: the kernel declares a texture argument that the
// case deliberately never binds at dispatch (public Metal, no debug/
// validation layer enabled).
kernel void k_a01_unbound_read(texture2d<uint, access::read> t [[texture(0)]], device uint* out [[buffer(0)]]) {
  out[0] = t.read(uint2(0, 0)).x;
}
kernel void k_a01_unbound_write(texture2d<uint, access::write> t [[texture(0)]]) {
  t.write(uint4(0xABCDEF01u, 0, 0, 0), uint2(0, 0));
}
// Read/write aliasing: two texture arguments backed by the SAME underlying
// MTLTexture, one bound read-only, one bound read_write, in the same
// dispatch, no explicit barrier between the write and the read.
kernel void k_a01_alias(texture2d<uint, access::read_write> tw [[texture(0)]], texture2d<uint, access::read> tr [[texture(1)]], device uint* out [[buffer(0)]]) {
  tw.write(uint4(0xA11A5000u, 0, 0, 0), uint2(0, 0));
  tw.fence();
  out[0] = tr.read(uint2(0, 0)).x;
}

// ============================================================ GLIMG-A02: bindless (argument-buffer) capacity
// CAP=256 array entries declared in the argument-buffer struct type (well
// beyond the 128-entry direct [[texture(N)]] ceiling established above),
// with only K=8 "canary" entries actually populated with distinguishable
// content per case. Runtime idx (from a buffer, genuinely dynamic, unlike
// the direct-binding compile-time selector) indexes into the array -- the
// direct analogue of EXP-0083's runtime base-slot sweep, applied to images.
#define CAP 256
struct AB_Read  { array<texture2d<uint>, CAP> tex [[id(0)]]; };
struct AB_Write { array<texture2d<uint, access::write>, CAP> tex [[id(0)]]; };
struct AB_Atomic{ array<texture_buffer<uint, access::read_write>, CAP> tex [[id(0)]]; };

kernel void k_a02_bindless_read(constant AB_Read& ab [[buffer(0)]], constant uint& idx [[buffer(1)]], device uint* out [[buffer(2)]]) {
  out[0] = ab.tex[idx].read(uint2(0, 0)).x;
}
kernel void k_a02_bindless_write(constant AB_Write& ab [[buffer(0)]], constant uint& idx [[buffer(1)]]) {
  ab.tex[idx].write(uint4(0xC0FFEEu, 0, 0, 0), uint2(0, 0));
}
kernel void k_a02_bindless_atomic(constant AB_Atomic& ab [[buffer(0)]], constant uint& idx [[buffer(1)]], device uint* out [[buffer(2)]]) {
  out[0] = ab.tex[idx].atomic_fetch_add(0u, uint4(1, 0, 0, 0)).x;
}
// Direct-bound readback of the K=8 canary textures (used after a bindless
// write/atomic dispatch to detect aliasing/corruption of the legitimate
// populated entries).
kernel void k_a02_canary_readback8(device uint* out [[buffer(0)]],
    texture2d<uint> c0 [[texture(0)]], texture2d<uint> c1 [[texture(1)]], texture2d<uint> c2 [[texture(2)]], texture2d<uint> c3 [[texture(3)]],
    texture2d<uint> c4 [[texture(4)]], texture2d<uint> c5 [[texture(5)]], texture2d<uint> c6 [[texture(6)]], texture2d<uint> c7 [[texture(7)]]) {
  out[0] = c0.read(uint2(0,0)).x; out[1] = c1.read(uint2(0,0)).x; out[2] = c2.read(uint2(0,0)).x; out[3] = c3.read(uint2(0,0)).x;
  out[4] = c4.read(uint2(0,0)).x; out[5] = c5.read(uint2(0,0)).x; out[6] = c6.read(uint2(0,0)).x; out[7] = c7.read(uint2(0,0)).x;
}
kernel void k_a02_canary_readback8_tb(device uint* out [[buffer(0)]],
    texture_buffer<uint, access::read> c0 [[texture(0)]], texture_buffer<uint, access::read> c1 [[texture(1)]],
    texture_buffer<uint, access::read> c2 [[texture(2)]], texture_buffer<uint, access::read> c3 [[texture(3)]],
    texture_buffer<uint, access::read> c4 [[texture(4)]], texture_buffer<uint, access::read> c5 [[texture(5)]],
    texture_buffer<uint, access::read> c6 [[texture(6)]], texture_buffer<uint, access::read> c7 [[texture(7)]]) {
  out[0] = c0.read(0u).x; out[1] = c1.read(0u).x; out[2] = c2.read(0u).x; out[3] = c3.read(0u).x;
  out[4] = c4.read(0u).x; out[5] = c5.read(0u).x; out[6] = c6.read(0u).x; out[7] = c7.read(0u).x;
}
