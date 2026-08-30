// k_sr207.metal -- EXP-0207 system-value carriers for get_sr.form and
// get_sr.dst_hi.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// get_sr.form (byte0 bit 3, WIDTH 1) was declined on eight arms, promoted by the
// orchestrator, and that promotion was WITHDRAWN because every supporting record
// carried `oracle: null` and scored the UNMUTATED BASELINE as `wrong_value`.  A
// sweep with no host prediction cannot discriminate anything, so the fix is not
// more arms: it is an oracle.  These carriers put a get_sr on a path whose
// correct value the HOST can compute independently of the GPU, in each of the
// three stages, so every (form, sr_sel) cell is scored ok / silent_zero /
// wrong_value against a documented expected value rather than against "did the
// pixel change".
//
// get_sr.dst_hi (width 3, the destination-register EXTENSION) was withheld
// INERT-SINGLE on ONE arm with 8 values.  The domain is only 8 values, so the
// missing thing is a second, structurally different carrier -- and for get_sr the
// documented discriminator is STAGE, not target: EXP-0178 measured 128 of 128
// bit-7-clear selectors faulting in the VERTEX stage and none in compute.  So
// there are four arms across three stages, plus a high-register-pressure compute
// kernel whose own compiled destination may already sit above r15 (making 0 an
// OFF-baseline value rather than the baseline).
//
// Every kernel writes an INTEGRITY SENTINEL through a path the instruction under
// test cannot name, into a separate buffer the harness poisons with 0xDEADBEEF.

#include <metal_stdlib>
using namespace metal;

constant uint SENT_BASE = 0x5A5A0000u;
constant uint SR_BIAS   = 1000u;

// ------------------------------------------------------- compute carriers ----

// k_sr_c: the plain compute carrier.  out[tid] = <system value> + SR_BIAS, so a
// silent zero reads back as exactly SR_BIAS and is distinguishable from a real
// zero-valued system register.
kernel void k_sr_c(device uint *out [[buffer(0)]],
                   device uint *sent [[buffer(4)]],
                   uint tid [[thread_position_in_grid]],
                   uint lane [[thread_index_in_simdgroup]])
{
    sent[tid] = SENT_BASE + tid;
    out[tid]  = lane + SR_BIAS;
}

// k_sr_hi: the same read under HIGH REGISTER PRESSURE.  Sixteen values are kept
// live across a device load and a shuffle-free mix, so the compiler's own
// allocation for the system-value destination may land above r15 and the
// baseline dst_hi may be non-zero.  Whether it actually does is MEASURED in the
// census and recorded, not assumed.
kernel void k_sr_hi(device uint *out [[buffer(0)]],
                    device const uint *in [[buffer(1)]],
                    device uint *sent [[buffer(4)]],
                    uint tid [[thread_position_in_grid]],
                    uint lane [[thread_index_in_simdgroup]])
{
    uint v[16];
    for (uint i = 0; i < 16u; ++i) v[i] = in[tid * 16u + i] * (i + 1u) + i;
    uint s = 0u;
    for (uint i = 0; i < 16u; ++i) s ^= v[i] + (v[(i + 7u) & 15u] << 1);
    sent[tid] = SENT_BASE + tid;
    out[tid]  = s + (lane + SR_BIAS) * 65536u;
}

// ------------------------------------------------------ fragment carriers ----

struct SV { float4 pos [[position]]; };
vertex SV v_sr(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0) };
    SV o; o.pos = float4(p[vid], 0.0, 1.0); return o;
}

// f_sr: the fragment system-value read.  .r is the raw system value, .g is a
// second one, .b/.a are uniforms that no system-value read touches -- the
// fragment-stage integrity channel.
fragment float4 f_sr(SV in [[stage_in]], constant float4 &u [[buffer(0)]],
                     device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 8u + x] = SENT_BASE + y * 8u + x;
    return float4(in.pos.x, in.pos.y, u.x, u.y);
}

// f_sr2: the SAME read consumed through arithmetic before the store, so the
// destination register is read by a different instruction than in f_sr.  This is
// the second fragment-stage route for dst_hi.
fragment float4 f_sr2(SV in [[stage_in]], constant float4 &u [[buffer(0)]],
                      device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 8u + x] = SENT_BASE + y * 8u + x;
    float a = in.pos.x * 4.0 + 1.0;
    float b = in.pos.y * 16.0 + 2.0;
    return float4(a, b, a * b + u.x, u.y);
}

// -------------------------------------------------------- vertex carriers ----

// v_sv: the VERTEX-stage read.  vertex_id and instance_id are carried to the
// fragment stage as varyings and interpolate across the triangle, so the host
// can predict each pixel from the barycentric weights.
struct SVV { float4 pos [[position]]; float sv; float si; };
vertex SVV v_sv(uint vid [[vertex_id]], uint iid [[instance_id]]) {
    float2 p[3] = { float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0) };
    SVV o;
    o.pos = float4(p[vid], 0.0, 1.0);
    o.sv  = float(vid);
    o.si  = float(iid);
    return o;
}
fragment float4 f_sv(SVV in [[stage_in]], constant float4 &u [[buffer(0)]],
                     device uint *sent [[buffer(1)]]) {
    uint x = uint(in.pos.x), y = uint(in.pos.y);
    sent[y * 8u + x] = SENT_BASE + y * 8u + x;
    return float4(in.sv, in.si, 0.0, u.y);
}
