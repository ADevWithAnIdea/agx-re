// out = a + 1.0f : packed-immediate base kernel for splice validation.
kernel void k(device float* a [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + 1.0f;
}
