#include <metal_stdlib>
using namespace metal;

// EXP-0082 store probe (successor of EXP-0077/0080/0081; kernel BODY below is
// BYTE-IDENTICAL to all three -- not tuned from any prior run). Exactly ONE
// device_store (tgt[j] = constant) whose address fields we splice. tgt is a
// 2048-word (8 KiB) zero-filled buffer; the harness reads the whole buffer
// back and the changed byte positions identify the effective store byte
// address. The data is a compile-time constant so the store's data path never
// moves when address fields are spliced.
//   * j = i0 + i1 is ALU-computed so the store takes the canonical indexed
//     form with the index register at byte+5. The harness always binds
//     idxbuf[1] = 0, so at runtime j == i0 == idxbuf[0] bit-exactly.
kernel void k(device uint* tgt        [[buffer(1)]],
              device uint* echo       [[buffer(0)]],
              const device uint* idxbuf [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    uint i0 = idxbuf[gid * 4 + 0];
    uint i1 = idxbuf[gid * 4 + 1];
    uint i2 = idxbuf[gid * 4 + 2];
    uint i3 = idxbuf[gid * 4 + 3];
    uint j  = i0 + i1;
    tgt[j]  = 0x5A17C0DEu;
    echo[0] = i2 + (i3 << 8) + j;   // keep i2/i3 live, echo j
}
