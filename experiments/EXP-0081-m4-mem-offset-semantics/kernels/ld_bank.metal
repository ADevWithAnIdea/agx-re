#include <metal_stdlib>
using namespace metal;

// EXP-0077 load probe. One scalar 32-bit device_load of a[j] whose address
// fields (immediate element offset idx_off at byte+9bit7/+10/+11, element-size
// code at byte+12, index register at byte+5) we splice; one observation store.
//
//   * a[] is filled by the harness with a[w] = 0x3CA50000 | w (4096 words),
//     so any 32-bit read at byte offset B < 16381 decodes uniquely to
//     (word, byte-residue): byte 3 of every word is the tag 0x3C, bytes 0..1
//     carry the word index.
//   * j = i0 + i1 is ALU-computed (iadd2) so the load takes the canonical
//     byte+2=0x44 indexed form with the index register at byte+5. The harness
//     always binds idxbuf[1] = 0, so at runtime j == i0 == idxbuf[0]: the
//     effective index is runtime-controlled bit-exactly (i0 + 0 never wraps).
//   * out2 keeps i2/i3 live and echoes them.
kernel void k(device uint* out        [[buffer(0)]],
              device uint* out2       [[buffer(1)]],
              const device uint* a    [[buffer(2)]],
              const device uint* idxbuf [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    uint i0 = idxbuf[gid * 4 + 0];
    uint i1 = idxbuf[gid * 4 + 1];
    uint i2 = idxbuf[gid * 4 + 2];
    uint i3 = idxbuf[gid * 4 + 3];
    uint j  = i0 + i1;
    out[0]  = a[j];
    out2[0] = i2 + (i3 << 8) + j;
}
