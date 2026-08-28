kernel void k(device float* a [[buffer(0)]], device float* b [[buffer(1)]], device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
  o[i] = a[i] + b[i];
}
