// EXP-0023 CONTROL: hand-written software ray/triangle intersection loop.
// CLEAN-ROOM: OUR OWN MSL. This is what a SOFTWARE BVH-traversal lowering of a
// ray query would look like -- an explicit Moller-Trumbore loop over a device
// buffer of triangles, using only ordinary ALU / load ops. If the raytracing::
// intersector (kernels/rt.metal) contains opcodes this control does NOT, those
// opcodes are the dedicated ray-tracing hardware instructions.
#include <metal_stdlib>
using namespace metal;

struct Tri { float3 v0, v1, v2; };

// Moller-Trumbore single-triangle intersection.
static float tri_hit(float3 o, float3 d, float3 v0, float3 v1, float3 v2) {
    float3 e1 = v1 - v0;
    float3 e2 = v2 - v0;
    float3 p  = cross(d, e2);
    float det = dot(e1, p);
    if (fabs(det) < 1e-8f) return -1.0f;
    float inv = 1.0f / det;
    float3 t  = o - v0;
    float u   = dot(t, p) * inv;
    if (u < 0.0f || u > 1.0f) return -1.0f;
    float3 q  = cross(t, e1);
    float v   = dot(d, q) * inv;
    if (v < 0.0f || u + v > 1.0f) return -1.0f;
    float dist = dot(e2, q) * inv;
    return (dist > 0.0f) ? dist : -1.0f;
}

// Software "traversal": brute-force loop over N triangles, keep the closest.
kernel void hand_trace(device const Tri *tris [[buffer(0)]],
                       device const uint *ntri [[buffer(1)]],
                       device float *o [[buffer(2)]],
                       device float3 *dir [[buffer(3)]],
                       uint i [[thread_position_in_grid]]) {
    float3 org = float3(0.0f, 0.0f, 0.0f);
    float3 d   = dir[i];
    float best = INFINITY;
    uint n = ntri[0];
    for (uint k = 0; k < n; ++k) {
        float t = tri_hit(org, d, tris[k].v0, tris[k].v1, tris[k].v2);
        if (t > 0.0f && t < best) best = t;
    }
    o[i] = isinf(best) ? -1.0f : best;
}

// Single-triangle version (matches a 1-triangle AS): closest of exactly one tri.
kernel void hand_one(device const Tri *tris [[buffer(0)]],
                     device float *o [[buffer(1)]],
                     device float3 *dir [[buffer(2)]],
                     uint i [[thread_position_in_grid]]) {
    float3 org = float3(0.0f, 0.0f, 0.0f);
    float3 d   = dir[i];
    float t = tri_hit(org, d, tris[0].v0, tris[0].v1, tris[0].v2);
    o[i] = t;
}
