#!/usr/bin/env python3
"""EXP-0147 FROZEN sweep plan.

One entry per arm. An arm names the carrier (which kernel/functions to compile
and how to run it), the byte pattern that locates the target instruction inside
our own compiled program, the blocking fields to sweep, and the controls.

Nothing here reads the GPU; this module is pure data + oracles so that the
expected value of every case is computed on the HOST, independently of the
device (FIELD-SWEEP-PROTOCOL section 3.4).
"""

RENDER_KERNEL = "kernels/pipe_render.metal"
COMPUTE_KERNEL = "kernels/pipe_compute.metal"

# Fixed asymmetric inputs used by every render case (chosen so that a dropped
# term, a zeroed term and a swapped term are all distinguishable, and so that
# no component is 0 or 1).
DST0 = [0.25, 0.5, -1.0, 2.0]        # colour-attachment 0 clear colour
DST1 = [3.0, -4.0, 5.0, 6.0]         # colour-attachment 1 clear colour
SRC  = [1.0, -2.0, 3.0, 0.5]         # fragment uniform  (buffer 0)
VP   = [0.5, 0.25, 0.125, 1.0]       # vertex   uniform  (buffer 0)
DST0_ALT = [-7.0, 11.0, 0.75, -0.5]  # liveness control: a second clear colour
SRC_ALT  = [9.0, 0.125, -6.0, 4.0]   # liveness control: a second uniform

ROG_INSTANCES = 8

# ---------------------------------------------------------------- oracles ---

def bary(verts, px, py, W, H):
    """Barycentric weights of the centre of pixel (px,py) in a WxH target,
    for a clip-space triangle given as three (x,y) pairs. Metal viewport:
    ndc_x = 2*(px+0.5)/W - 1, ndc_y = 1 - 2*(py+0.5)/H."""
    nx = 2.0 * (px + 0.5) / W - 1.0
    ny = 1.0 - 2.0 * (py + 0.5) / H
    (x0, y0), (x1, y1), (x2, y2) = verts
    den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    l0 = ((y1 - y2) * (nx - x2) + (x2 - x1) * (ny - y2)) / den
    l1 = ((y2 - y0) * (nx - x2) + (x0 - x2) * (ny - y2)) / den
    return (l0, l1, 1.0 - l0 - l1)

# v_tern / v_samp use tri(vid): v0=(-1,-1) v1=(-1,3) v2=(3,-1)
TRI_TERN = [(-1.0, -1.0), (-1.0, 3.0), (3.0, -1.0)]
# v_arr uses the indexed array p[3]: v0=(-1,-1) v1=(3,-1) v2=(-1,3)
TRI_ARR = [(-1.0, -1.0), (3.0, -1.0), (-1.0, 3.0)]

VA_TERN = [[0.90, 0.10, 0.10, 1.0], [0.10, 0.90, 0.10, 1.0], [0.10, 0.10, 0.90, 1.0]]
VA_SAMP = [[0.90, 0.20, 0.30, 1.0], [0.10, 0.75, 0.30, 1.0], [0.10, 0.20, 0.60, 1.0]]


def o_tile(dst0, src, W, H, **_):
    return [[dst0[k] * 2.0 + src[k] for k in range(4)] for _ in range(W * H)]

def o_tile_zero(dst0, src, W, H, **_):
    return [[src[k] for k in range(4)] for _ in range(W * H)]

def o_mrt(dst0, dst1, src, W, H, **_):
    rt0 = [[dst0[k] * 2.0 + src[k] for k in range(4)] for _ in range(W * H)]
    rt1 = [[dst1[k] * 4.0 - src[k] for k in range(4)] for _ in range(W * H)]
    return rt0 + rt1

def o_mrt_rt1zero(dst0, dst1, src, W, H, **_):
    rt0 = [[dst0[k] * 2.0 + src[k] for k in range(4)] for _ in range(W * H)]
    rt1 = [[-src[k] for k in range(4)] for _ in range(W * H)]
    return rt0 + rt1

def _interp(verts, attrs, W, H):
    out = []
    for py in range(H):
        for px in range(W):
            l = bary(verts, px, py, W, H)
            out.append([sum(l[i] * attrs[i][k] for i in range(3)) for k in range(4)])
    return out

def o_vary_tern(W, H, **_):
    return _interp(TRI_TERN, VA_TERN, W, H)

def o_vary_arr(vp, W, H, **_):
    attrs = [[vp[k] * float(i + 1) for k in range(4)] for i in range(3)]
    return _interp(TRI_ARR, attrs, W, H)

def o_samp(src, W, H, **_):
    base = _interp(TRI_TERN, VA_SAMP, W, H)
    return [[b[k] * 2.0 + src[k] for k in range(4)] for b in base]

def o_rog(dst0, src, W, H, instances=ROG_INSTANCES, **_):
    """1x1 target: `instances` fragments each read-modify-write texel (0,0)
    under the raster_order_group, and each also returns v + dst where dst is the
    CURRENT tilebuffer value (f_rog declares [[color(0)]], i.e. programmable
    blending). If ordering held, fragment i (1-based) sees texel (i-1)*src,
    writes i*src, and adds i*src to the tile, so:
        texel = N*src              (N = instances)
        pixel = clear + src*N(N+1)/2
    Both are order-sensitive: a lost update lowers BOTH."""
    n = instances
    tex = [n * src[k] for k in range(4)]
    px = [dst0[k] + src[k] * (n * (n + 1) // 2) for k in range(4)]
    return {"pixels": [px], "tex": tex}

# ------------------------------------------------------------------ arms ----

ARMS = [
    dict(arm="matrix_mac", instr="matrix_mac", stage="compute",
         kernel=COMPUTE_KERNEL, func="k_mad_f32", pattern="cf02",
         grid=32, tg=32, oracle="mad",
         fields=[dict(name="dst_desc", byte=9, width=8, shift=0),
                 dict(name="b11hi",    byte=11, width=7, shift=1)],
         sensitivity=dict(byte=2, value=0x54,
                          why="EXP-O2C: standalone 0x56 -> tiled 0x54 zeroes the result"),
         note="10 of 12 fields were already emitter-grade (DOC-02); only "
              "dst_desc and b11hi block matrix_mac."),

    dict(arm="tile_read", instr="tile_read", stage="fragment",
         kernel=RENDER_KERNEL, vs="v_arr", fs="f_tile", nrt=1, samples=1,
         W=2, H=2, pattern="670e54", oracle="tile",
         fields=[dict(name="b2", byte=2, width=8), dict(name="dst", byte=3, width=8),
                 dict(name="b4", byte=4, width=8), dict(name="rt_index", byte=5, width=8),
                 dict(name="b6", byte=6, width=8), dict(name="b7", byte=7, width=8),
                 dict(name="tail", byte=8, width=32, nbytes=4)],
         sensitivity=dict(byte=3, value=0x02,
                          why="destination GPR relocation must change the pixel")),

    dict(arm="tile_read_mrt", instr="tile_read_mrt", stage="fragment",
         kernel=RENDER_KERNEL, vs="v_arr", fs="f_mrt", nrt=2, samples=1,
         W=1, H=1, pattern="670654", oracle="mrt",
         fields=[dict(name="dst", byte=3, width=8), dict(name="b4", byte=4, width=8),
                 dict(name="rt_index", byte=5, width=8), dict(name="b6", byte=6, width=8),
                 dict(name="fmt", byte=7, width=8),
                 dict(name="tail", byte=8, width=32, nbytes=4)],
         sensitivity=dict(byte=3, value=0x02,
                          why="destination GPR relocation must change attachment 1")),

    dict(arm="vtx_out_pos", instr="vtx_out_pos", stage="vertex",
         kernel=RENDER_KERNEL, vs="v_tern", fs="f_vary", nrt=1, samples=1,
         W=2, H=2, pattern="0b0026004000", oracle="vary_tern",
         fields=[dict(name="dst", byte=0, width=4, shift=4),
                 dict(name="slot", byte=7, width=8)],
         sensitivity=dict(byte=2, value=0x55,
                          why="byte+2 is a match constant; corrupting it must change the pixel")),

    dict(arm="vtx_coord_xform", instr="vtx_coord_xform", stage="vertex",
         kernel=RENDER_KERNEL, vs="v_arr", fs="f_varyc", nrt=1, samples=1,
         W=2, H=2, pattern="1722a2b0", oracle="vary_arr",
         fields=[dict(name="mode", byte=1, width=8), dict(name="sel", byte=4, width=8),
                 dict(name="operand", byte=5, width=40, nbytes=5)],
         sensitivity=dict(byte=1, value=0x55, why="mode changed the pixel in pilot")),

    dict(arm="pixel_order", instr="pixel_order", stage="fragment",
         kernel=RENDER_KERNEL, vs="v_arr", fs="f_rog", nrt=1, samples=1,
         W=1, H=1, pattern="071454500600", oracle="rog",
         tex=[0.0, 0.0, 0.0, 0.0], instances=ROG_INSTANCES,
         fields=[dict(name="scope", byte=3, width=8), dict(name="flags", byte=4, width=8),
                 dict(name="b5", byte=5, width=8)],
         sensitivity=dict(byte=4, value=0x55,
                          why="pilot: corrupting byte+4 loses 7 of 8 serialised updates"),
         note="sweeps the ACQUIRE member of the pair; the release member is left intact."),

    dict(arm="pixel_order_rel", instr="pixel_order", stage="fragment",
         kernel=RENDER_KERNEL, vs="v_arr", fs="f_rog", nrt=1, samples=1,
         W=1, H=1, pattern="070454d00600", oracle="rog",
         tex=[0.0, 0.0, 0.0, 0.0], instances=ROG_INSTANCES,
         fields=[dict(name="scope", byte=3, width=8), dict(name="flags", byte=4, width=8),
                 dict(name="b5", byte=5, width=8)],
         sensitivity=dict(byte=4, value=0x55, why="same, on the release member"),
         note="adversarial second method: the same three fields on the RELEASE member."),

    dict(arm="n3_sample_read", instr="n3_sample_read", stage="fragment",
         kernel=RENDER_KERNEL, vs="v_samp", fs="f_samp", nrt=1, samples=1,
         W=2, H=2, pattern="030026", oracle="samp",
         fields=[dict(name="b1", byte=1, width=8), dict(name="b3", byte=3, width=8),
                 dict(name="tail", byte=4, width=48, nbytes=6)],
         sensitivity=dict(byte=2, value=0x55,
                          why="byte+2 is the op-select match constant; pilot showed it changes the pixel")),

    dict(arm="scoreboard_fence", instr="scoreboard_fence", stage="compute",
         kernel=COMPUTE_KERNEL, func="k_atomic", pattern="07220200",
         grid=32, tg=32, oracle="atomic",
         fields=[dict(name="kind", byte=1, width=8), dict(name="scope", byte=2, width=7, shift=1),
                 dict(name="mask", byte=3, width=8)],
         sensitivity=dict(byte=0, value=0x55, why="corrupting byte0 changes the opcode itself")),

    dict(arm="compute_fence_scoped", instr="compute_fence_scoped", stage="compute",
         kernel=COMPUTE_KERNEL, func="k_tgrw", pattern="87008004",
         grid=256, tg=256, oracle="tgrw",
         fields=[dict(name="kind", byte=1, width=8), dict(name="scope", byte=2, width=8),
                 dict(name="mask", byte=3, width=8)],
         sensitivity=dict(byte=0, value=0x55, why="corrupting byte0 changes the opcode itself")),
]

# Multi-byte fields: whole-field structured values on top of the per-byte dense
# sweep (FIELD-SWEEP-PROTOCOL section 3.3 for w > 8).
def wide_values(width):
    mx = (1 << width) - 1
    vals = [0, 1, 2, mx - 1, mx]
    vals += [1 << k for k in range(width)]
    interior = [0x5A, 0xA5A5, 0x0F0F0F, 0xDEADBEEF, 0x12345678, 0x80000001,
                0x7FFFFFFE, 0xCAFEF00D, 0x00FF00FF, 0xFF00FF00, 0x33333333,
                0xCCCCCCCC, 0x01234567, 0x89ABCDEF, 0xFEDCBA98, 0x76543210]
    vals += [v & mx for v in interior]
    seen, out = set(), []
    for v in vals:
        if v not in seen:
            seen.add(v); out.append(v)
    return out
