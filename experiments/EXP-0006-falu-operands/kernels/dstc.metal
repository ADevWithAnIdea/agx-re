// Force the fadd's dst onto a fresh register by keeping both sources live past
// the add (they are stored afterwards), so dst cannot reuse a's/b's register.
// Diffing this fadd vs simple add localizes the dst field bits.
kernel void k(device float* a   [[buffer(0)]],
              device float* b   [[buffer(1)]],
              device float* out [[buffer(2)]],
              device float* o2  [[buffer(3)]],
              device float* o3  [[buffer(4)]],
              uint gid [[thread_position_in_grid]]) {
    float va = a[gid], vb = b[gid];
    out[gid] = va + vb;
    o2[gid] = va;
    o3[gid] = vb;
}
