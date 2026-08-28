// EXP-0142 carrier A -- eight INDEPENDENT texture samples, all live at once.
//
// Purpose: force the compiler to allocate eight distinct coordinate register
// pairs and eight distinct result register quads, so a splice into ONE sample's
// bundle is observable in exactly one of eight independently read-back slots.
// Single-sample kernels are useless for this: their bundle bytes are constant
// across every register-pressure variant we compiled (see work/gen_variants.py).
//
// LIVENESS: sample j's result reaches out[4j..4j+3] and nothing else reaches
// those four words, so any change to sample j's encoding is observed at a known
// buffer address. Cross-talk to another sample's slot is itself the observable
// used by the destination-register arm.
//
// Integrity sentinel (FIELD-SWEEP-PROTOCOL section 7): out[32] is a plain
// load->store of in[b+63] that never touches the texture unit. If it does not
// read back the expected value the dispatch is suspect as a whole and the case
// is NOT attributed to the field under test.
//
// Clean-room: our own MSL.
#include <metal_stdlib>
using namespace metal;

kernel void k_sample(texture2d<float, access::sample> t [[texture(0)]],
                     device const float *in  [[buffer(0)]],
                     device float       *out [[buffer(1)]],
                     uint tid [[thread_position_in_grid]])
{
    constexpr sampler s(coord::pixel, filter::nearest,
                        address::clamp_to_edge, mip_filter::none);
    uint b = tid * 64u;
    float4 c0 = t.sample(s, float2(in[b+ 0], in[b+ 1]), level(0.0f));
    float4 c1 = t.sample(s, float2(in[b+ 2], in[b+ 3]), level(0.0f));
    float4 c2 = t.sample(s, float2(in[b+ 4], in[b+ 5]), level(0.0f));
    float4 c3 = t.sample(s, float2(in[b+ 6], in[b+ 7]), level(0.0f));
    float4 c4 = t.sample(s, float2(in[b+ 8], in[b+ 9]), level(0.0f));
    float4 c5 = t.sample(s, float2(in[b+10], in[b+11]), level(0.0f));
    float4 c6 = t.sample(s, float2(in[b+12], in[b+13]), level(0.0f));
    float4 c7 = t.sample(s, float2(in[b+14], in[b+15]), level(0.0f));
    out[ 0]=c0.x; out[ 1]=c0.y; out[ 2]=c0.z; out[ 3]=c0.w;
    out[ 4]=c1.x; out[ 5]=c1.y; out[ 6]=c1.z; out[ 7]=c1.w;
    out[ 8]=c2.x; out[ 9]=c2.y; out[10]=c2.z; out[11]=c2.w;
    out[12]=c3.x; out[13]=c3.y; out[14]=c3.z; out[15]=c3.w;
    out[16]=c4.x; out[17]=c4.y; out[18]=c4.z; out[19]=c4.w;
    out[20]=c5.x; out[21]=c5.y; out[22]=c5.z; out[23]=c5.w;
    out[24]=c6.x; out[25]=c6.y; out[26]=c6.z; out[27]=c6.w;
    out[28]=c7.x; out[29]=c7.y; out[30]=c7.z; out[31]=c7.w;
    out[32]=in[b+63];   // integrity sentinel, texture-unit-independent path
}
