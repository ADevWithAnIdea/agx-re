kernel void k(device float* a [[buffer(0)]],
              device float* b [[buffer(1)]],
              device float* out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}
