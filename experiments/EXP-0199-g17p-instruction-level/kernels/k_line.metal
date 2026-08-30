// k_line.metal -- EXP-0199 straight-line compute carrier for the MARKER
// framing / independent-emission probes.  OUR OWN MSL.  Clean-room: OWN-SHADER.
//
// Design constraints, each for a stated reason:
//
//  * NO control flow, NO SFU op, NO threadgroup memory, and no 0x60 or 0x06
//    leader of its own, so an inserted marker is the ONLY thing of its kind in
//    the stream and cannot be confused with a compiler-placed one.
//  * The computed output is a DIFFERENT value in every lane and a strict
//    function of the host-supplied input buffer, so the host oracle is a
//    32-element VARYING vector.  "The program still ran correctly" therefore
//    cannot be satisfied by a constant, and a desynchronised instruction stream
//    cannot accidentally reproduce it.
//  * The INTEGRITY SENTINEL (FIELD-SWEEP-PROTOCOL sec.7.2) is written FIRST,
//    through its own store, into a disjoint region of the output buffer, from a
//    value no instruction after the insertion point contributes to.  So:
//      sentinel present + value correct  -> the insertion was benign
//      sentinel present + value wrong    -> the insertion broke the tail
//      sentinel absent  (still poison)   -> the program never got that far
//  * o[32..63] and o[96..127] are never written by any lane, so they must come
//    back holding the harness's 0xDEADBEEF poison.  A read-back that silently
//    did not happen is therefore visible as poison in the WRITTEN regions too.
//
//   o[i]      = a[i]*3 + i*7 + 11        (grid = 32)
//   o[64 + i] = 0xA5A50000 + i           (sentinel, stored before the rest)

#include <metal_stdlib>
using namespace metal;

kernel void k_line(device const uint *a  [[buffer(1)]],
                   device uint       *o  [[buffer(0)]],
                   uint               i  [[thread_position_in_grid]])
{
    o[i + 64u] = 0xA5A50000u + i;   // integrity sentinel, independent store
    uint v = a[i] * 3u;
    v += i * 7u;
    v += 11u;
    o[i] = v;
}
