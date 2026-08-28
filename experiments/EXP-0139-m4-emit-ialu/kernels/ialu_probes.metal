// EXP-0139 authored MSL probes: one kernel per integer-ALU shape we need a
// live, compiler-natural anchor for. Every kernel is written by us; the only
// machine code this experiment inspects is the compiled form of THIS file and
// of kernels/carrier_dag.metal. Buffer signature is identical in every kernel
// so one harness can drive them all: a[] in, b[] in, o[] out.
#include <metal_stdlib>
using namespace metal;

// --- ibfe: compile-time-constant extract (EXP-0033's single-op shape) ------
kernel void k_bfe_const(device const uint* a [[buffer(0)]],
                        device const uint* b [[buffer(1)]],
                        device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = extract_bits(a[i], 4u, 8u);
}
kernel void k_bfe_const_s(device const int* a [[buffer(0)]],
                          device const int* b [[buffer(1)]],
                          device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = extract_bits(a[i], 4, 8);
}
// --- ibfins: compile-time-constant insert ---------------------------------
kernel void k_bfi_const(device const uint* a [[buffer(0)]],
                        device const uint* b [[buffer(1)]],
                        device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = insert_bits(a[i], b[i], 4u, 8u);
}
// --- ishift ---------------------------------------------------------------
kernel void k_shl(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                  device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] << b[i];
}
kernel void k_shr(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                  device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] >> b[i];
}
kernel void k_shl_const(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                        device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] << 5u;
}
// --- imad -----------------------------------------------------------------
kernel void k_imad(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                   device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] * b[i] + 7u;
}
kernel void k_imul(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                   device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] * b[i];
}
// --- iminmax --------------------------------------------------------------
kernel void k_umax(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                   device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = max(a[i], b[i]);
}
kernel void k_imin(device const int* a [[buffer(0)]], device const int* b [[buffer(1)]],
                   device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = min(a[i], b[i]);
}
// --- icmpsel / isel* ------------------------------------------------------
kernel void k_sel(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                  device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = (a[i] > b[i]) ? a[i] : b[i];
}
kernel void k_sel_const(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                        device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = (a[i] > 100u) ? 11u : 22u;
}
kernel void k_sel_mixed(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                        device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = (a[i] == b[i]) ? (a[i] + 3u) : (b[i] + 5u);
}
// --- iunary convert -------------------------------------------------------
kernel void k_cvt_i2f(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                      device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = float(a[i]);
}
kernel void k_cvt_f2i(device const float* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                      device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = uint(a[i]);
}
kernel void k_cvt_i2h(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                      device half* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = half(a[i]);
}

// --- second wave: anchors located by work/pilot/p4_recon2.py --------------
// abs(int) lowers to iadd2(negate) + isel8 -> a clean 8-byte isel8 anchor.
kernel void k_abs(device const int* a [[buffer(0)]], device const int* b [[buffer(1)]],
                  device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = abs(a[i]);
}
// clz lowers to ibitcount + iadd2 + isel10 -> a clean 10-byte isel10 anchor.
kernel void k_clz(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                  device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = clz(a[i]);
}
// popcount -> the tight 8-byte ibitcount form (NATURAL counterpart of the
// SYNTH ibitcount carrier).
kernel void k_pop(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                  device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = popcount(a[i]);
}
// rotate by an immediate -> the 12-byte irotate sibling of ibfins.
kernel void k_rot(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                  device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = rotate(a[i], 7u);
}
// mulhi -> a second, structurally different imad anchor (no addend).
kernel void k_mulhi(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                    device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = uint(mulhi(a[i], 12345u));
}
// arithmetic shift-right by an immediate -> the ishift member db.json names
// as its HW-validated one (byte0 0xa7, byte+1 bit0 == 1).
kernel void k_ashr(device const int* a [[buffer(0)]], device const int* b [[buffer(1)]],
                   device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] >> 4;
}
kernel void k_ashr2(device const int* a [[buffer(0)]], device const int* b [[buffer(1)]],
                    device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = (a[i] >> 1) + (a[i] >> 8);
}
// unsigned divide by a non-power-of-two -> the isel_reg / isel10_c correction
// selects db.json attributes to the division lowering.
kernel void k_div(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                  device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] / b[i];
}
kernel void k_mod(device const int* a [[buffer(0)]], device const int* b [[buffer(1)]],
                  device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = a[i] % b[i];
}
// a compare feeding a 14-byte compare-select (icmpsel candidate).
kernel void k_cmpsel(device const uint* a [[buffer(0)]], device const uint* b [[buffer(1)]],
                     device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = (a[i] < b[i]) ? 0xAAu : 0x55u;
}
kernel void k_cmpsel2(device const float* a [[buffer(0)]], device const float* b [[buffer(1)]],
                      device uint* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = (a[i] < b[i]) ? 1u : 0u;
}
kernel void k_cmpsel3(device const int* a [[buffer(0)]], device const int* b [[buffer(1)]],
                      device int* o [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    o[i] = select(a[i] * 2, b[i] + 9, a[i] > b[i]);
}
