#include <metal_stdlib>
using namespace metal;
// HIGH-NIBBLE TEST for the 0x?b float-unary (fmov/fneg/fabs) group.
// Force several fneg/fabs results to be simultaneously live so the compiler must
// place them in DIFFERENT destination registers -> the byte0 high nibble should
// track the dst reg if the family shape is (hi=dst, lo=opcode).
kernel void k_neg1(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                   uint i[[thread_position_in_grid]]) {
    o[i] = -a[i];
}
kernel void k_neg_fan(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                      uint i[[thread_position_in_grid]]) {
    // eight independent negations kept live and summed -> eight distinct dst regs.
    float s = 0.0f;
    float acc[8];
    for (int k=0;k<8;k++) acc[k] = -a[i+k];
    // read them back in a data-dependent order so they cannot be coalesced
    s = acc[0]*1.0f + acc[1]*2.0f + acc[2]*3.0f + acc[3]*4.0f
      + acc[4]*5.0f + acc[5]*6.0f + acc[6]*7.0f + acc[7]*8.0f;
    o[i] = s;
}
kernel void k_abs_fan(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                      uint i[[thread_position_in_grid]]) {
    float acc[6];
    for (int k=0;k<6;k++) acc[k] = fabs(a[i+k]);
    o[i] = acc[0]+acc[1]*2+acc[2]*3+acc[3]*4+acc[4]*5+acc[5]*6;
}
