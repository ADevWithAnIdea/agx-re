// EXP-0136 H7 opcode-sweep carrier: a minimal add kernel whose compiled form
// contains exactly two device_load (0x67) instructions and one device_store
// (0xe7) instruction, used as the splice target for the reserved7/reserved13
// modifier-byte sweep (docs/isa/encoding-tables.md "device_load"/"device_store").
kernel void k(device float* a [[buffer(0)]], device float* b [[buffer(1)]], device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
  o[i] = a[i] + b[i];
}
