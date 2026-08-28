#include <metal_stdlib>
using namespace metal;

kernel void k(device const uint *in [[buffer(0)]],
              device const uint *mb [[buffer(1)]],
              device const uint *mc [[buffer(2)]],
              device uint *out [[buffer(3)]],
              uint gid [[thread_position_in_grid]]) {
    uint t0 = in[0] ^ (in[0] << 1) + gid;
    uint t1 = in[1] ^ (in[1] << 2) + gid;
    uint t2 = in[2] ^ (in[2] << 3) + gid;
    uint t3 = in[3] ^ (in[3] << 4) + gid;
    uint t4 = in[4] ^ (in[4] << 5) + gid;
    uint t5 = in[5] ^ (in[5] << 6) + gid;
    uint t6 = in[6] ^ (in[6] << 7) + gid;
    uint t7 = in[7] ^ (in[7] << 8) + gid;
    uint t8 = in[8] ^ (in[8] << 9) + gid;
    uint t9 = in[9] ^ (in[9] << 10) + gid;
    uint t10 = in[10] ^ (in[10] << 11) + gid;
    uint t11 = in[11] ^ (in[11] << 12) + gid;
    uint t12 = in[12] ^ (in[12] << 13) + gid;
    uint t13 = in[13] ^ (in[13] << 1) + gid;
    uint t14 = in[14] ^ (in[14] << 2) + gid;
    uint t15 = in[15] ^ (in[15] << 3) + gid;
    uint t16 = in[16] ^ (in[16] << 4) + gid;
    uint t17 = in[17] ^ (in[17] << 5) + gid;
    uint t18 = in[18] ^ (in[18] << 6) + gid;
    uint t19 = in[19] ^ (in[19] << 7) + gid;
    uint t20 = in[20] ^ (in[20] << 8) + gid;
    uint t21 = in[21] ^ (in[21] << 9) + gid;
    uint t22 = in[22] ^ (in[22] << 10) + gid;
    uint t23 = in[23] ^ (in[23] << 11) + gid;
    uint t24 = in[24] ^ (in[24] << 12) + gid;
    uint t25 = in[25] ^ (in[25] << 13) + gid;
    uint t26 = in[26] ^ (in[26] << 1) + gid;
    uint t27 = in[27] ^ (in[27] << 2) + gid;
    uint t28 = in[28] ^ (in[28] << 3) + gid;
    uint t29 = in[29] ^ (in[29] << 4) + gid;
    uint t30 = in[30] ^ (in[30] << 5) + gid;
    uint t31 = in[31] ^ (in[31] << 6) + gid;
    uint t32 = in[32] ^ (in[32] << 7) + gid;
    uint t33 = in[33] ^ (in[33] << 8) + gid;
    uint t34 = in[34] ^ (in[34] << 9) + gid;
    uint t35 = in[35] ^ (in[35] << 10) + gid;
    uint t36 = in[36] ^ (in[36] << 11) + gid;
    uint t37 = in[37] ^ (in[37] << 12) + gid;
    uint t38 = in[38] ^ (in[38] << 13) + gid;
    uint t39 = in[39] ^ (in[39] << 1) + gid;
    uint acc = (t0 + t1 + t2 + t3 + t4 + t5 + t6 + t7 + t8 + t9 + t10 + t11 + t12 + t13 + t14 + t15 + t16 + t17 + t18 + t19 + t20 + t21 + t22 + t23 + t24 + t25 + t26 + t27 + t28 + t29 + t30 + t31 + t32 + t33 + t34 + t35 + t36 + t37 + t38 + t39);
    out[gid] = acc * mb[gid] + mc[gid];
}
