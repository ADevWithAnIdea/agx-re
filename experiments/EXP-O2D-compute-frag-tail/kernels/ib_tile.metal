#include <metal_stdlib>
using namespace metal;

// Explicit imageblock accessed from a TILE kernel (dispatchThreadsPerTile).
// Read-modify-write the tile imageblock; provokes imageblock read/write + slice
// addressing ops. Clean-room: OUR OWN MSL.
struct GB {
    half4 albedo [[color(0)]];
    half4 normal [[color(1)]];
    float depthv [[color(2)]];
};

// tile kernel: read the imageblock slot for this thread, scale it, write back.
kernel void tk_rmw(imageblock<GB> img,
                   ushort2 tpos [[thread_position_in_threadgroup]]) {
    GB v = img.read(tpos);
    v.albedo = v.albedo * 0.5h;
    v.normal = v.normal + half4(0.1h);
    v.depthv = v.depthv * 2.0f;
    img.write(v, tpos);
}

// tile kernel: write a constant into the imageblock (pure write path).
kernel void tk_write(imageblock<GB> img,
                     ushort2 tpos [[thread_position_in_threadgroup]]) {
    GB v;
    v.albedo = half4(0.5h, 0.25h, 0.125h, 1.0h);
    v.normal = half4(0.0h, 0.0h, 1.0h, 0.0h);
    v.depthv = 0.9f;
    img.write(v, tpos);
}

// tile kernel: write only ONE slice/attachment (slice addressing).
kernel void tk_write_slice(imageblock<GB> img,
                           ushort2 tpos [[thread_position_in_threadgroup]]) {
    GB v = img.read(tpos);
    v.normal = half4(0.7h, 0.6h, 0.5h, 0.4h);
    img.write(v, tpos);
}
