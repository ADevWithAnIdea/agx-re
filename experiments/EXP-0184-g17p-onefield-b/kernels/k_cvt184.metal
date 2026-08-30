// EXP-0184 float->integer convert carriers (AUTHORED BY US; OWN-SHADER).
//
// TARGET FIELD: `cvt_f2i.b9` = byte+9 of the 10-byte `27 07 ...` convert,
// modelled in db.json as "reserved 0x00" and constant across 136 corpus
// instances. EXP-0144 dispatched 256 values on ONE carrier and nothing moved;
// EXP-0164 withheld it for exactly that reason.
//
// WHY FIVE KERNELS. db.json places the DEST format/width descriptor at byte+8
// and the SOURCE format/class descriptor at byte+4. If byte+9 carries anything,
// the plausible dimension is the same one -- destination width/sign, or source
// width. So the carriers below span BOTH: four destination types and two source
// types. Two carriers that convert float->int32 are one carrier for this field.
//
//   k_cvt_s32  float -> int          (signed 32)
//   k_cvt_u32  float -> uint         (unsigned 32)
//   k_cvt_s16  float -> short        (signed 16, widened for read-back)
//   k_cvt_u16  float -> ushort       (unsigned 16, widened for read-back)
//   k_cvt_h32  half  -> int          (16-bit SOURCE)
//
// A SECOND, INDEPENDENT PURPOSE. byte+9 is the LAST byte of the modelled
// 10-byte length. If the length model is wrong and the real instruction is 9
// bytes, then "sweeping b9" is sweeping the NEXT instruction's leader, and the
// sweep will not be quietly inert -- it will fault, hang, or corrupt the
// following op. Either outcome is a first-class result (protocol section 6).
//
// ORACLE: truncation toward zero, computed on the host from these exact inputs.
//   a = [ 3.9, -3.9,  2.5, -2.5, 100.75,  7.0,  0.5,  63.25]  (signed / half src)
//   b = [ 3.9, 12.25, 2.5, 250.5, 100.75, 7.0,  0.5,  63.25]  (unsigned src)
// No lane's expected value is 0 except lane 6 (0.5 -> 0), which is deliberate:
// it is the one lane where a silent zero is indistinguishable from a pass, and
// the verdict never rests on it (`analysis/verdicts.py` excludes lane 6 from the
// match test and records it separately).
#include <metal_stdlib>
using namespace metal;

#define SENTI outi[8] = 12345;

kernel void k_cvt_s32(device int *outi [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENTI
    outi[t] = int(a[t]);
}

kernel void k_cvt_u32(device int *outi [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENTI
    outi[t] = int(uint(b[t]));
}

kernel void k_cvt_s16(device int *outi [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENTI
    outi[t] = int(short(a[t]));
}

kernel void k_cvt_u16(device int *outi [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENTI
    outi[t] = int(ushort(b[t]));
}

kernel void k_cvt_h32(device int *outi [[buffer(0)]],
                      device const float *a [[buffer(1)]],
                      device const float *b [[buffer(2)]],
                      uint t [[thread_position_in_grid]]) {
    SENTI
    half h = half(a[t]);
    outi[t] = int(h);
}
