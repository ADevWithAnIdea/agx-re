// RT-1b control-flow kernels (OUR OWN MSL). Falsify predication (icmp 0x0a/0x02,
// imm byte+3), select (0x05/0x16), backward jump 0f 00 54 <off>, exec-mask sub-ops.
#include <metal_stdlib>
using namespace metal;

// --- gid-threshold predication/select: out[gid] = gid<4 ? 100 : 200.
// The compare tests gid against an immediate (byte+3). Sweeping grid shows the
// active-lane boundary; splicing the immediate must MOVE the boundary; flipping
// the compare op must INVERT it.
kernel void thresh(device int* out [[buffer(0)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = (gid < 4) ? 100 : 200;
}

// --- data-dependent branch: out = a[gid] > 5 ? 100 : 200 (immediate 5 at byte+3).
kernel void ifdata(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    out[gid] = (a[gid] > 5) ? 100 : 200;
}

// --- dynamic loop -> real backward jump (0f 00 54 <off>): sum 1..N.
kernel void loopsum(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
                    uint gid [[thread_position_in_grid]]) {
    int s = 0; int i = a[gid]; while (i > 0) { s += i; i--; } out[gid] = s;
}

// --- LARGE-body dynamic loop (big backward offset): forces a long back-edge.
kernel void loopbig(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
                    uint gid [[thread_position_in_grid]]) {
    int s = 0; int n = a[gid];
    for (int i = 0; i < n; i++) {
        s += i;            s ^= (i << 3);  s += (i * 7 + 1);
        s -= (i & 3);      s += (i | 5);   s ^= (i * 3);
        s += (s >> 2);     s -= (i << 1);  s += (i ^ 0x55);
        s += (i % 5);      s ^= (i + 9);   s += (i & 0x0f);
    }
    out[gid] = s;
}

// --- deeply nested if/else (data-dependent divergence).
kernel void nested(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {
    int x = a[gid]; int r;
    if (x < 10) { if (x < 5) { r = (x < 2) ? 1 : 2; } else { r = (x < 8) ? 3 : 4; } }
    else        { if (x < 20){ r = (x < 15)? 5 : 6; } else { r = (x < 30)? 7 : 8; } }
    out[gid] = r;
}

// --- break, continue, early-return.
kernel void brk(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
                uint gid [[thread_position_in_grid]]) {
    int s = 0; for (uint i = 0; i < 100u; i++) { if (i >= uint(a[gid])) break; s += int(i); } out[gid] = s;
}
kernel void cont(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
                 uint gid [[thread_position_in_grid]]) {
    int s = 0; for (uint i = 0; i < uint(a[gid]); i++) { if (i & 1u) continue; s += int(i); } out[gid] = s;
}
kernel void eret(device int* out [[buffer(0)]], device const int* a [[buffer(1)]],
                 uint gid [[thread_position_in_grid]]) {
    out[gid] = 0; if (gid >= 4) return; out[gid] = 7;
}
