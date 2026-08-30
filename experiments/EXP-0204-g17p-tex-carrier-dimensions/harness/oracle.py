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


# ---- the texture-write carriers -----------------------------------------
# buffer(0) = carriers.BUF_TEX, so colour0 = (11,12,13,14), colour1 =
# (21,22,23,24), colour2 = (31,32,33,34) and in[6]*in[7] = 42.  Every write
# carrier returns float4(c0.x, c1.x, c2.x, 42) except twdyn.
C0 = [11.0, 12.0, 13.0, 14.0]
C1 = [21.0, 22.0, 23.0, 24.0]
C2 = [31.0, 32.0, 33.0, 34.0]
DRAW = [51.0, 52.0, 53.0, 54.0]        # buffer(1) lane 1, the contiguous vec4
TEXW_RESET = [-1.0, -2.0, -3.0, -4.0]  # gfrun4.m resets every writable 2D texel


def _tw_pix(px, py):
    return [C0[0], C1[0], C2[0], 42.0]


def _twdyn_pix(px, py):
    uv = affine(0.0, 2.0, 4.0)          # o.uv.x = f*2
    uvx = uv[0] * (px + 0.5) + uv[1] * (py + 0.5) + uv[2]
    return [DRAW[0], C0[0] + uvx, float(px & 7), 42.0]


BASELINE_PIX = {
    "msfilt": _msfilt, "msfixl": _msfixl, "msgath": _msgath,
    "msread": _msread, "mscmp": _mscmp, "mslodq": _mslodq,
    "deriv": _deriv, "deriv2": _deriv2,
    "twmip": _tw_pix, "twbuf": _tw_pix, "twcube": _tw_pix, "twcomp": _tw_pix,
    "twdyn": _twdyn_pix,
}

# Exact predicted contents of the plain 2D writable texture [[texture(1)]],
# read back by the harness as surface TEXW, at the probe texels.  Each entry is
# {(x,y): expected float4}; every OTHER probe texel must still hold the reset
# sentinel, which is what makes "wrote elsewhere" and "did not write" separable.
# twdyn is deliberately absent: its coordinates are per-fragment dynamic, so the
# final texel content depends on rasterisation order and is NOT predicted here.
BASELINE_TEXW = {
    "twmip":  {(3, 2): C0},     # w2.write(c0, uint2(3,2))
    "twbuf":  {(1, 0): C0},     # w2.write(c0, uint2(1,0))
    "twcube": {(7, 6): C0},     # w2.write(c0, uint2(7,6))
    "twcomp": {(5, 4): C2},     # w2.write(c2, uint2(5,4))
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


def predicted_texw(carrier, texels):
    """Exact predicted TEXW contents at the probe texels, or None."""
    m = BASELINE_TEXW.get(carrier)
    if m is None:
        return None
    return {f"{x},{y}": list(m.get((x, y), TEXW_RESET)) for (x, y) in texels}


def baseline_agrees(carrier, probes, observed_probe, tol=0.05, texels=None):
    """Does the OBSERVED baseline match the host prediction?  Returns
    (n_checked, n_agree, detail).  Channels predicted None are not scored.

    Checks the colour attachment (PIX0) and, for the write carriers whose
    destination texels are compile-time constants, the written texture (TEXW)."""
    if not observed_probe:
        return 0, 0, {}
    n = ok = 0
    detail = {}
    pred = predicted_pixels(carrier, probes)
    got = observed_probe.get("PIX0")
    if pred is not None and got:
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
                    detail[f"PIX0:{x},{y}.{c}"] = [g[c], p[c]]
    tpred = predicted_texw(carrier, texels or [])
    tgot = observed_probe.get("TEXW")
    if tpred is not None and tgot:
        for k, (x, y) in enumerate(texels or []):
            if k >= len(tgot):
                break
            p = tpred[f"{x},{y}"]
            g = tgot[k]
            for c in range(4):
                n += 1
                good = abs(float(g[c]) - float(p[c])) <= max(tol, abs(p[c]) * 1e-5)
                ok += 1 if good else 0
                if not good:
                    detail[f"TEXW:{x},{y}.{c}"] = [g[c], p[c]]
    return n, ok, detail


# ==========================================================================
# GATE C -- an INDEPENDENT SEMANTIC PREDICTOR.
#
# RE_EXPERIMENT_PROCESS_CORRECTIONS sec.3 Gate C: "A difference from baseline is
# not a semantic oracle."  The predictor below is independent of the GPU result
# and distinguishes the five buckets the gate names:
#     correct  |  coherent_other  |  silent_zero / no_write  |  fault/hang  |
#     measurement_failure / contaminated
# plus `unchanged` (the observation is exactly the baseline, a legitimate and
# distinct outcome for a value that turns out inert) and `unmodelled` (status OK
# but the observation matches nothing the model can name -- which is a REFUTATION
# of the model, not a pass).
#
# `sem_checked` counts only cases where the model made a DEFINITE prediction.
# sec.2: `sem_checked == 0` can never produce `hardware-run`.
# ==========================================================================

SAMPLE_CANDIDATES = {
    # carrier -> {class name: f(px,py) -> predicted channel-0 value, or None}
    # `filtered`  : bilinear level-0 value at the carrier's own coordinate
    # `nearest`   : an unfiltered level-0 texel at that coordinate (either of the
    #               two texels the corner sits between -- the tie is not ours to
    #               break, so both are accepted as the same class)
    # `lod`       : the implicit LOD for the carrier's own coordinate gradient
    "msfilt": {"filtered": lambda x, y: [_bilinear_ramp(x + 1.0, y + 1.0, 0)],
               "nearest":  lambda x, y: [float(x) + 100.0 * y,
                                         float(x + 1) + 100.0 * y,
                                         float(x) + 100.0 * (y + 1),
                                         float(x + 1) + 100.0 * (y + 1)],
               "lod":      lambda x, y: [0.0]},
    "msfixl": {"filtered": lambda x, y: [_bilinear_ramp(x + 1.0, y + 1.0, 0)],
               "nearest":  lambda x, y: [float(x) + 100.0 * y,
                                         float(x + 1) + 100.0 * y,
                                         float(x) + 100.0 * (y + 1),
                                         float(x + 1) + 100.0 * (y + 1)],
               "lod":      lambda x, y: [0.0]},
    "msgath": {"gather":   lambda x, y: [float(x) + 100.0 * (y + 1)],
               "filtered": lambda x, y: [_bilinear_ramp(x + 1.0, y + 1.0, 0)],
               "lod":      lambda x, y: [0.0]},
    "msread": {"read":     lambda x, y: [float(x & 7) + 100.0 * float(y & 7)],
               "lod":      lambda x, y: [0.0]},
    "mscmp":  {"compare":  lambda x, y: [0.0, 0.25, 0.5, 0.75, 1.0],
               "lod":      lambda x, y: [0.0]},
    "mslodq": {"lod":      lambda x, y: [2.0],
               "filtered": lambda x, y: None},   # texel-shaped, not pinned
}
# db.json's mode enum -> the class name this model expects the occurrence to take.
MODE_TO_CLASS = {0x00: ("gather", "read", "compare"), 0x10: ("filtered",),
                 0x20: ("lod",)}


def _near(a, b, tol=0.05):
    return abs(float(a) - float(b)) <= max(tol, abs(float(b)) * 1e-5)


def semantic_sample(carrier, probes, obs, base_obs, value, baseline_value):
    """Classify ONE spliced tex_sample.mode case into a Gate-C bucket."""
    st = obs.get("status")
    if st == "MALFORMED":
        return {"bucket": "measurement_failure", "checked": False}
    if st == "HANG":
        return {"bucket": "hang", "checked": True}
    if st in ("FOREIGN_FAULT",) or obs.get("os_class") == "InnocentVictim":
        return {"bucket": "contaminated", "checked": False}
    if st != "OK":
        return {"bucket": "fault", "checked": True}
    if obs.get("status") == "POISON":
        return {"bucket": "no_execution_poison", "checked": True}
    if obs.get("hh") == base_obs.get("hh"):
        return {"bucket": "unchanged", "checked": value in MODE_TO_CLASS,
                "note": "identical to the arm's own baseline observation"}
    got = (obs.get("probe") or {}).get("PIX0")
    cand = SAMPLE_CANDIDATES.get(carrier, {})
    if not got or not cand:
        return {"bucket": "unmodelled", "checked": False}
    want = MODE_TO_CLASS.get(value)
    matched = set()
    allzero = True
    n = 0
    for k, (x, y) in enumerate(probes):
        if k >= len(got) or not covered(x, y):
            continue
        v = float(got[k][0])
        n += 1
        if abs(v) > 1e-6:
            allzero = False
        for cname, fn in cand.items():
            vals = fn(x, y)
            if vals is None:
                continue
            if any(_near(v, t) for t in vals):
                matched.add(cname)
    if n == 0:
        return {"bucket": "unmodelled", "checked": False}
    if allzero:
        return {"bucket": "silent_zero", "checked": value in MODE_TO_CLASS}
    if want and matched & set(want):
        return {"bucket": "correct", "checked": True,
                "matched_class": sorted(matched)}
    if matched:
        return {"bucket": "coherent_other", "checked": bool(want),
                "matched_class": sorted(matched)}
    return {"bucket": "unmodelled", "checked": bool(want)}


# ---- tex_write: the semantic question is WHERE the write landed ------------
# gfrun4.m's reset sentinels, by surface prefix.
WRITE_RESET = {
    "TEXW":  [-1.0, -2.0, -3.0, -4.0],
    "TEXWA": [-1.0, -2.0, -3.0, -4.0],
    "TEXWM": None,       # level-distinct: (-1-L, -2-L, -3-L, -4-L)
    "TEXWC": None,       # face-distinct:  (-1-f, -2-f, -3-f, -4-f)
    "TEXWB": [-11.0, -12.0, -13.0, -14.0],
    "TEXWR": [-21.0],
    "TEXWG": [-31.0, -32.0],
}
WRITE_DATA = {"C0": C0, "C1": C1, "C2": C2, "DRAW": DRAW}


def _surface_reset(tag):
    if tag.startswith("TEXWM"):
        L = int(tag[5:] or 0)
        return [-1.0 - L, -2.0 - L, -3.0 - L, -4.0 - L]
    if tag.startswith("TEXWC"):
        f = int(tag[5:] or 0)
        return [-1.0 - f, -2.0 - f, -3.0 - f, -4.0 - f]
    for k in ("TEXWA", "TEXWB", "TEXWR", "TEXWG", "TEXW"):
        if tag.startswith(k):
            return WRITE_RESET[k]
    return None


def _write_state(probe):
    """Compact, host-computed description of every probed write surface:
    per texel, one of `reset` / `C0` / `C1` / `C2` / `DRAW` / `other`."""
    out = {}
    for tag, vals in sorted((probe or {}).items()):
        if not tag.startswith("TEXW"):
            continue
        rst = _surface_reset(tag)
        row = []
        for v in vals:
            vv = v if isinstance(v, list) else [v]
            name = "other"
            if rst is not None and len(vv) <= len(rst) and \
                    all(_near(vv[i], rst[i]) for i in range(len(vv))):
                name = "reset"
            else:
                for dn, dv in WRITE_DATA.items():
                    if all(_near(vv[i], dv[i]) for i in range(len(vv))):
                        name = dn
                        break
            row.append(name)
        out[tag] = row
    return out


def semantic_write(carrier, obs, base_obs, value, baseline_value, field):
    """Classify ONE spliced tex_write.{amode,rsv11} case into a Gate-C bucket.

    The question a texture store's address/format descriptor answers is WHERE the
    write landed and WITH WHAT, so the predictor is the per-surface, per-texel
    state map above, compared against the arm's own host-VALIDATED baseline map."""
    st = obs.get("status")
    if st == "MALFORMED":
        return {"bucket": "measurement_failure", "checked": False}
    if st == "HANG":
        return {"bucket": "hang", "checked": True}
    if st in ("FOREIGN_FAULT",) or obs.get("os_class") == "InnocentVictim":
        return {"bucket": "contaminated", "checked": False}
    if st != "OK":
        return {"bucket": "fault", "checked": True}
    now = _write_state(obs.get("probe"))
    was = _write_state(base_obs.get("probe"))
    if not now or not was:
        return {"bucket": "unmodelled", "checked": False}
    if now == was:
        return {"bucket": "correct_all_writes_landed", "checked": True,
                "state": now}
    lost, moved, wrong = [], [], []
    for tag in sorted(set(was) | set(now)):
        a, b = was.get(tag, []), now.get(tag, [])
        for i in range(max(len(a), len(b))):
            x = a[i] if i < len(a) else "?"
            y = b[i] if i < len(b) else "?"
            if x == y:
                continue
            if x != "reset" and y == "reset":
                lost.append(f"{tag}[{i}]:{x}->reset")
            elif x == "reset" and y != "reset":
                moved.append(f"{tag}[{i}]:reset->{y}")
            else:
                wrong.append(f"{tag}[{i}]:{x}->{y}")
    if lost and not moved and not wrong:
        return {"bucket": "write_suppressed", "checked": True, "detail": lost}
    if moved and not lost and not wrong:
        return {"bucket": "write_relocated", "checked": True, "detail": moved}
    return {"bucket": "write_data_changed", "checked": True,
            "detail": (lost + moved + wrong)[:8]}


def semantic_check(mnemonic, field, carrier, probes, obs, base_obs, value,
                   baseline_value):
    if mnemonic == "tex_sample" and field == "mode":
        return semantic_sample(carrier, probes, obs, base_obs, value, baseline_value)
    if mnemonic == "tex_write":
        return semantic_write(carrier, obs, base_obs, value, baseline_value, field)
    # tex_deriv.dstsrc: NO semantic model is pre-registered.  Gate C therefore
    # caps it at `live; role unknown` and `sem_checked` stays 0 for it, which by
    # sec.2 makes `hardware-run` unreachable.  Stated here rather than faked.
    return {"bucket": "no_model", "checked": False}
