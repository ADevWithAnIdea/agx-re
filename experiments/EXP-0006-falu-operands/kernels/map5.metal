// Register-map probe kernel: one fadd (va+vb) feeds `out`; extra distinct
// values vc,vd,ve are loaded and kept live via direct stores (no extra fadd),
// so splicing the target fadd's src/dst index bits and observing `out` maps the
// encoding bits to physical registers. CLEAN-ROOM: our own MSL.
kernel void k(device float* a   [[buffer(0)]],
              device float* b   [[buffer(1)]],
              device float* c   [[buffer(2)]],
              device float* d   [[buffer(3)]],
              device float* e   [[buffer(4)]],
              device float* out [[buffer(5)]],
              device float* s1  [[buffer(6)]],
              device float* s2  [[buffer(7)]],
              device float* s3  [[buffer(8)]],
              uint gid [[thread_position_in_grid]]) {
    float va = a[gid], vb = b[gid], vc = c[gid], vd = d[gid], ve = e[gid];
    out[gid] = va + vb;   // THE single fadd feeding out
    s1[gid] = vc;
    s2[gid] = vd;
    s3[gid] = ve;
}
