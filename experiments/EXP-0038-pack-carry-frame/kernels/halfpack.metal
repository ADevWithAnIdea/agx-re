#include <metal_stdlib>
using namespace metal;

// ---- Task 1: half pack/unpack (0x18 / 0x30 / 0x38) ----
// All bytes inspected are the compiled form of OUR OWN MSL (OWN-SHADER).

// half2 add -> store as half2 (packed 2x fp16). EXP-0033: one 0x10 op + a 0x18 pack.
kernel void k_h2add(device const half2* a [[buffer(0)]],
                    device const half2* b [[buffer(1)]],
                    device half2* out      [[buffer(2)]],
                    uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}

// half2 mul -> store (op-select byte-diff vs k_h2add).
kernel void k_h2mul(device const half2* a [[buffer(0)]],
                    device const half2* b [[buffer(1)]],
                    device half2* out      [[buffer(2)]],
                    uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] * b[gid];
}

// half4 add -> store (two packed lanes -> two packs).
kernel void k_h4add(device const half4* a [[buffer(0)]],
                    device const half4* b [[buffer(1)]],
                    device half4* out      [[buffer(2)]],
                    uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}

// pack_half2x16 analogue: float2 -> narrow to half2 -> store as packed uint.
// Forces the fp32->fp16 narrow (0x11) + the 2-lane pack (0x18/0x30).
kernel void k_packh2(device const float2* a [[buffer(0)]],
                     device uint* out        [[buffer(1)]],
                     uint gid [[thread_position_in_grid]]) {
    half2 h = half2(a[gid]);
    out[gid] = as_type<uint>(h);
}

// unpack_half2x16 analogue: packed uint -> half2 -> widen to float2 -> store.
// Forces the unpack of two 16-bit lanes + fp16->fp32 widen (0x38?).
kernel void k_unpackh2(device const uint* a  [[buffer(0)]],
                       device float2* out     [[buffer(1)]],
                       uint gid [[thread_position_in_grid]]) {
    half2 h = as_type<half2>(a[gid]);
    out[gid] = float2(h);
}

// round-trip: pack then unpack should be identity (proves pack/unpack semantics).
kernel void k_h2roundtrip(device const float2* a [[buffer(0)]],
                          device float2* out      [[buffer(1)]],
                          uint gid [[thread_position_in_grid]]) {
    uint packed = as_type<uint>(half2(a[gid]));
    half2 h = as_type<half2>(packed);
    out[gid] = float2(h);
}

// half2 fma: exercise the 8-byte native-half form + pack.
kernel void k_h2fma(device const half2* a [[buffer(0)]],
                    device const half2* b [[buffer(1)]],
                    device const half2* c [[buffer(2)]],
                    device half2* out      [[buffer(3)]],
                    uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] * b[gid] + c[gid];
}

// scalar half add -> store as half (no packing; control for 0x10 vs 0x18).
kernel void k_h1add(device const half* a [[buffer(0)]],
                    device const half* b [[buffer(1)]],
                    device half* out      [[buffer(2)]],
                    uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}

// half4 store (4 fp16 lanes -> 2 packed 32-bit words): provoke 0x30/0x38 packs.
kernel void k_h4store(device const half4* a [[buffer(0)]],
                      device const half4* b [[buffer(1)]],
                      device half4* out      [[buffer(2)]],
                      uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] * b[gid] + a[gid];
}
// pack two independent half2 results into a uint2 (two packs).
kernel void k_pack2x(device const float4* a [[buffer(0)]],
                     device uint2* out        [[buffer(1)]],
                     uint gid [[thread_position_in_grid]]) {
    float4 v = a[gid];
    half2 lo = half2(v.xy) + half2(1.0h);
    half2 hi = half2(v.zw) * half2(2.0h);
    out[gid] = uint2(as_type<uint>(lo), as_type<uint>(hi));
}
// short4 (16-bit int vector) store -- contrast: int16 does NOT pack (EXP-0033).
kernel void k_s4store(device const short4* a [[buffer(0)]],
                      device const short4* b [[buffer(1)]],
                      device short4* out      [[buffer(2)]],
                      uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}
