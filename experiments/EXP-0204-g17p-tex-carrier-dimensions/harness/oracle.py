#!/usr/bin/env python3
"""oracle.py -- EXP-0204 HOST-COMPUTED, DISCRIMINATING oracles.

`FIELD-SWEEP-PROTOCOL.md` sec.3.4 wants "a host-computed expected value per case,
independent of the GPU", and `tools/agx-isa/wave_audit.py` counts DISTINCT oracle
payloads because "a CONSTANT oracle across a varying field predicts the
instruction's effect, not the field's".  So every case here carries an oracle
whose content varies with the swept value, and every carrier's BASELINE carries
an EXACT float vector computed from arithmetic done here, on the host, from:

  * the triangle this experiment's own vertex shaders draw.  All three vertices
    have w == 1, so every varying is AFFINE in screen space and its screen-space
    partial derivatives are exact -- which is what makes the tex_deriv oracle a
    number rather than a shrug;
  * the texture content gfrun4.m itself writes:
        tex_mip   [[texture(10)]]  texel(x,y,L) = x + 100y + 10000L   (16x16, 3 levels)
        tex_depth [[texture(5)]]   depth(x,y)   = (x + 8y)/64          (8x8)
        tex_samp  [[texture(0)]]   texel(x,y)   = x + 100y            (8x8)
  * buffer(0) / buffer(1), whose contents are frozen in carriers.py.

Nothing in this module reads a GPU result.  It is imported by run.py (to stamp
`oracle` on every raw record) and by analysis/verdicts.py.

CLEAN-ROOM: pure host arithmetic over our own MSL's own constants.
"""
import math

# Screen-space triangle, identical in every carrier's vertex shader:
#   pos = ((f-1)*0.75, (f*f-f)*0.5 - 0.375, 0, 1) for f = 0,1,2
# at a 16x16 target with Metal's y-down NDC->screen mapping.
W = H = 16
VERTS = []
for f in (0.0, 1.0, 2.0):
    xn = (f - 1.0) * 0.75
    yn = (f * f - f) * 0.5 - 0.375
    VERTS.append(((xn * 0.5 + 0.5) * W, (1.0 - (yn * 0.5 + 0.5)) * H))
# -> [(2.0, 11.0), (8.0, 11.0), (14.0, 3.0)]


def covered(px, py):
    """Is the centre of pixel (px,py) inside the triangle?  Barycentric sign test."""
    x, y = px + 0.5, py + 0.5
    (x0, y0), (x1, y1), (x2, y2) = VERTS
    d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(d) < 1e-12:
        return False
    a = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / d
    b = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / d
    c = 1.0 - a - b
    return a >= 0.0 and b >= 0.0 and c >= 0.0


def affine(v0, v1, v2):
    """Coefficients (a,b,c) of the affine map a*x + b*y + c that takes the three
    screen vertices to the three given values.  w == 1 at every vertex, so
    interpolation is affine and this is exact."""
    (x0, y0), (x1, y1), (x2, y2) = VERTS
    det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    a = ((v1 - v0) * (y2 - y0) - (v2 - v0) * (y1 - y0)) / det
    b = ((x1 - x0) * (v2 - v0) - (x2 - x0) * (v1 - v0)) / det
    c = v0 - a * x0 - b * y0
    return a, b, c


def _bilinear_ramp(u_texel, v_texel, level):
    """Bilinear sample of a texture whose content is the LINEAR ramp
    x + 100y + 10000L.  Bilinear interpolation of a linear function is exact, so
    the value at texel coordinate (u,v) is simply the ramp at (u-0.5, v-0.5)."""
    return (u_texel - 0.5) + 100.0 * (v_texel - 0.5) + 10000.0 * level


# --------------------------------------------------------------------------
# Per-carrier exact baseline predictions, as float4 at a probe pixel.
# Each mirrors, line for line, the MSL in kernels/.
# --------------------------------------------------------------------------

def _msfilt(px, py):
    # uv = (pos.xy + 0.5)/16 with pos = (px+0.5, py+0.5) -> texel coord (px+1, py+1);
    # gradient 1 texel/pixel -> implicit LOD 0.
    a = _bilinear_ramp(px + 1.0, py + 1.0, 0)
    return [a, a * 2.0, a + 1.0, 7.0]


def _msfixl(px, py):
    a = _bilinear_ramp(px + 1.0, py + 1.0, 0)          # explicit level 0
    b = _bilinear_ramp((px + 1.0) / 2.0, (py + 1.0) / 2.0, 1)   # explicit level 1
    return [a, b, a + b, 7.0]


def _msgath(px, py):
    # Metal gather order is (i0j1, i1j1, i1j0, i0j0) around the coordinate;
    # the coordinate is the exact corner (px+1, py+1), so i0=px, i1=px+1,
    # j0=py, j1=py+1 on level 0 of the ramp.
    def t(x, y):
        return float(x) + 100.0 * float(y)
    return [t(px, py + 1), t(px + 1, py + 1), t(px + 1, py), t(px, py)]


def _msread(px_, py_):
    px, py = px_ & 7, py_ & 7
    a = float(px) + 100.0 * float(py)
    b = float(px >> 1) + 100.0 * float(py >> 1) + 10000.0
    c = float(px >> 2) + 100.0 * float(py >> 2) + 20000.0
    return [a, b, c, a + b + c]


def _mscmp(px_, py_):
    # 8x8 Depth32Float, depth(x,y) = (x + 8y)/64, reference r = 0.25 = 16/64.
    # coord::normalized, ((px&7)+1, (py&7)+1)/8 -> texel corner (px+1, py+1);
    # a LINEAR compare sampler averages the four 0/1 comparison results.
    px, py = px_ & 7, py_ & 7
    r = 0.25

    def dep(x, y):
        x = min(max(x, 0), 7)
        y = min(max(y, 0), 7)
        return (x + 8.0 * y) / 64.0
    taps = [dep(px, py), dep(px + 1, py), dep(px, py + 1), dep(px + 1, py + 1)]
    a = sum(1.0 if r < d else 0.0 for d in taps) / 4.0
    # The nearest-filter greater_equal tap: nearest texel to the corner is
    # implementation-chosen among the four, so `b` is NOT predicted here and the
    # oracle scores channel 0 only (recorded explicitly in `scored_channels`).
    return [a, None, None, 7.0]


def _mslodq(px, py):
    # gradient of pos.xy*k is k, in texels k*16 over a 16-wide texture, so
    # LOD = log2(k*16): k=1/4 -> 2, k=1/8 -> 1, k=1/32 -> -1 (clamped to 0).
    return [2.0, 1.0, 0.0, -1.0]


def _deriv(px, py):
    """k_deriv.metal: eight derivatives of three varyings, all affine."""
    ux = affine(0.0 * 4.0, 1.0 * 4.0, 2.0 * 4.0)              # uv.x = f*4
    uy = affine(0.0, 1.0 * 1.0 * 8.0, 2.0 * 2.0 * 8.0)        # uv.y = f*f*8
    w0 = affine(0.0, 16.0, 32.0)                              # w.x = f*16
    w1 = affine(0.0, 32.0, 64.0)                              # w.y = f*32
    w2 = affine(0.0, 64.0, 128.0)                             # w.z = f*64
    s = affine(0.0, 128.0, 256.0)                             # s   = f*128
    ax, ay = ux[0], uy[1]
    bx, by = w0[0], w1[1]
    fw = abs(uy[0]) + abs(uy[1])
    fz = abs(w2[0]) + abs(w2[1])
    sx, sy = s[0], s[1]
    uvx = ux[0] * (px + 0.5) + ux[1] * (py + 0.5) + ux[2]
    return [ax * 1000.0 + ay, bx * 1000.0 + by, fw * 1000.0 + fz,
            sx * 1000.0 + sy + uvx]


def _deriv2(px, py):
    """k_deriv2.metal: derivatives of ALU temporaries plus half-precision ones."""
    a0 = affine(0.0, 3.0, 6.0)      # a.x = f*3
    a1 = affine(0.0, 5.0, 10.0)     # a.y = f*5
    a2 = affine(0.0, 9.0, 18.0)     # a.z = f*9
    a3 = affine(0.0, 17.0, 34.0)    # a.w = f*17
    b0 = affine(0.0, 33.0, 66.0)    # b.x = f*33
    b1 = affine(0.0, 65.0, 130.0)   # b.y = f*65
    h0 = affine(0.0, 2.0, 4.0)      # h.x = f*2
    h1 = affine(0.0, 6.0, 12.0)     # h.y = f*6
    # p = a.x*2 + a.y ; q = a.z - a.w*0.5
    px_ = (a0[0] * 2.0 + a1[0], a0[1] * 2.0 + a1[1])
    qx_ = (a2[0] - a3[0] * 0.5, a2[1] - a3[1] * 0.5)
    return [px_[0] * 1000.0 + px_[1],
            qx_[0] * 1000.0 + qx_[1],
            b0[0] * 1000.0 + b1[1],
            h0[0] * 1000.0 + h1[1]]


BASELINE_PIX = {
    "msfilt": _msfilt, "msfixl": _msfixl, "msgath": _msgath,
    "msread": _msread, "mscmp": _mscmp, "mslodq": _mslodq,
    "deriv": _deriv, "deriv2": _deriv2,
}

# db.json's own enum for tex_sample.mode, and the operation class each names.
MODE_CLASS = {0x00: "gather_read_compare", 0x10: "filtered_sample",
              0x20: "lod_query"}
# The class each carrier's COMPILER-CHOSEN baseline expresses (from the
# pre-freeze census, raw/prefreeze/census_run2.json).
CARRIER_CLASS = {"msfilt": "filtered_sample", "msfixl": "filtered_sample",
                 "msgath": "gather_read_compare", "msread": "gather_read_compare",
                 "mscmp": "gather_read_compare", "mslodq": "lod_query"}

# db.json's own vocabulary for the byte+2 address/operand-source mode in the
# 0x67/0xe7 memory family, which tex_write's amode shares by position.
AMODE_MODEL = {0x44: "indexed_terminal_standalone",
               0x54: "base_rel_nonterminal_alu_data",
               0x55: "base_rel_terminal_variant(seen in our own census)",
               0x56: "direct_live_load_result_data",
               0x64: "extended_mesh"}


def mode_oracle(value, carrier, baseline_value):
    o = {"field": "tex_sample.mode",
         "class": MODE_CLASS.get(value, "unspecified"),
         "carrier_baseline_class": CARRIER_CLASS.get(carrier, "?"),
         "baseline_value": baseline_value}
    if value == baseline_value:
        o["predict"] = "baseline_exact"
    elif value in MODE_CLASS:
        o["predict"] = "class_change_to_" + MODE_CLASS[value]
    else:
        o["predict"] = "unspecified"
    return o


def deriv_oracle(value, carrier, baseline_value):
    return {"field": "tex_deriv.dstsrc",
            "model": "packed_dst_src_register_operand",
            "baseline_value": baseline_value,
            "predict": "baseline_exact" if value == baseline_value
                       else "redirected_operand"}


def write_oracle(field, value, carrier, baseline_value):
    if field == "amode":
        p = AMODE_MODEL.get(value, "unspecified")
    else:
        p = "format_tail_zero" if value == 0 else "format_tail_nonzero"
    return {"field": "tex_write." + field,
            "sibling_model": "device_store.addr_mode / st_desc_hi",
            "baseline_value": baseline_value,
            "class": p,
            "predict": "baseline_exact" if value == baseline_value
                       else ("named_model:" + p if p != "unspecified"
                             else "unspecified")}


def oracle_for(mnemonic, field, value, carrier, baseline_value):
    if mnemonic == "tex_sample" and field == "mode":
        return mode_oracle(value, carrier, baseline_value)
    if mnemonic == "tex_deriv" and field == "dstsrc":
        return deriv_oracle(value, carrier, baseline_value)
    if mnemonic == "tex_write":
        return write_oracle(field, value, carrier, baseline_value)
    return {"field": f"{mnemonic}.{field}", "predict": "unspecified",
            "baseline_value": baseline_value}


def predicted_pixels(carrier, probes):
    """Exact predicted float4 per probe pixel for the carrier's OWN baseline.
    Uncovered pixels are predicted to hold the clear colour (0,0,0,0)."""
    fn = BASELINE_PIX.get(carrier)
    if fn is None:
        return None
    out = {}
    for (x, y) in probes:
        out[f"{x},{y}"] = fn(x, y) if covered(x, y) else [0.0, 0.0, 0.0, 0.0]
    return out


def baseline_agrees(carrier, probes, observed_probe, tol=0.05):
    """Does the OBSERVED baseline match the host prediction?  Returns
    (n_checked, n_agree, detail).  Channels predicted None are not scored."""
    pred = predicted_pixels(carrier, probes)
    if pred is None or not observed_probe:
        return 0, 0, {}
    got = observed_probe.get("PIX0")
    if not got:
        return 0, 0, {}
    n = ok = 0
    detail = {}
    for k, (x, y) in enumerate(probes):
        if k >= len(got):
            break
        p = pred[f"{x},{y}"]
        g = got[k]
        for c in range(4):
            if p[c] is None:
                continue
            n += 1
            good = abs(float(g[c]) - float(p[c])) <= max(tol, abs(p[c]) * 1e-5)
            ok += 1 if good else 0
            if not good:
                detail[f"{x},{y}.{c}"] = [g[c], p[c]]
    return n, ok, detail
