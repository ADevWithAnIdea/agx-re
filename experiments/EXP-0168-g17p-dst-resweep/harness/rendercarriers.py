#!/usr/bin/env python3
"""rendercarriers.py -- EXP-0168 RENDER-arm carrier table and HOST oracles.

One entry per (authored MSL, pipeline descriptor) pair, with the exact command
line it is built and run with, so the census and the gated runs cannot disagree
about what was built.  Imported by harness/renderrun.py and by
analysis/render_verdicts.py.

NOTHING IN THIS FILE CONSULTS THE GPU.  Every expected value is computed here
from the MSL we wrote plus IEEE-754 binary32/binary16 arithmetic in Python, and
every quantity is a dyadic rational chosen to be exactly representable, so the
oracle is exact rather than tolerant.  "It looked right" is not an oracle; these
are closed-form predictions made before the run.

Structure derived from OUR OWN experiments/EXP-0163-.../harness/carriers.py and
experiments/EXP-0162-.../harness/renderplan.py.

CLEAN-ROOM: OWN-SHADER.  Only our own MSL is described.
"""
import math
import struct

# ---------------------------------------------------------------------------
# bit helpers
# ---------------------------------------------------------------------------


def f32(x):
    """Round a Python float to binary32, the way the GPU stores it."""
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def words(vals):
    """float list -> the u32 word list --buf-u32 wants."""
    return [f32_bits(v) for v in vals]


def f16_bits(x):
    """binary32 -> binary16 bits, IEEE round-to-nearest-even, exact integer
    arithmetic (struct.pack('<e') raises on overflow instead of producing inf,
    which is useless for a boundary oracle)."""
    u = f32_bits(x)
    s = (u >> 16) & 0x8000
    e = (u >> 23) & 0xFF
    m = u & 0x7FFFFF
    if e == 0xFF:
        return s | (0x7E00 if m else 0x7C00)
    ne = e - 127 + 15
    if ne >= 0x1F:
        return s | 0x7C00
    if ne > 0:
        r = (ne << 10) | (m >> 13)
        rem = m & 0x1FFF
        if rem > 0x1000 or (rem == 0x1000 and (r & 1)):
            r += 1
        return (s | r) & 0xFFFF
    shift = 14 - ne
    if shift > 31:
        return s
    mm = m | 0x800000
    r = mm >> shift
    rem = mm & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    if rem > half or (rem == half and (r & 1)):
        r += 1
    return (s | r) & 0xFFFF


def bits_f16(u):
    return struct.unpack("<e", struct.pack("<H", u & 0xFFFF))[0]


def unorm8(x):
    """binary32 -> 8-bit unorm code, round-to-nearest of clamp(x,0,1)*255.

    Every value this experiment feeds through it is at least 1e-4 away from a
    .5 tie, so the tie rule is never exercised and the oracle does not depend on
    which way the hardware breaks ties.  `analysis/render_verdicts.py` asserts
    that margin rather than assuming it.
    """
    v = min(1.0, max(0.0, float(x)))
    return int(v * 255.0 + 0.5)


def unorm8_margin(x):
    """Distance of v*255 from the nearest .5 TIE POINT, in [0, 0.5].

    0.5 means "exactly on an integer, maximally far from a tie"; 0.0 means "on a
    tie, and the observed byte then depends on the hardware's rounding mode".
    The selftest requires > 0.4 for every value this experiment uses, so no
    oracle here depends on a tie rule we have not established."""
    v = min(1.0, max(0.0, float(x)))
    s = v * 255.0
    return abs((s - math.floor(s)) - 0.5)


BYTES_PER_PIXEL = {125: 16, 115: 8, 80: 4, 70: 4, 71: 4, 81: 4, 55: 4, 10: 1}

# ---------------------------------------------------------------------------
# shared constants
# ---------------------------------------------------------------------------

W = H = 16
PROBE_PIXELS = [(0, 0), (3, 5), (8, 8), (15, 15)]
PROBE_PIXELS_1X1 = [(0, 0)]

OUT_STRIDE_FLOATS = 32          # every vertex carrier that writes --out-buf
OUT_VERTS = 3
OUT_BYTES = OUT_STRIDE_FLOATS * OUT_VERTS * 4       # 384

# The uniform every vertex carrier reads, and its DATA-LADDER replacement.  Both
# are dyadic, so every derived value below is exact in binary32.
VTX_U = [1.0, 2.0, 4.0, 8.0]
VTX_U_ALT = [3.0, 5.0, 9.0, 17.0]

# The ordered-RMW parameters.  ROG_SRC / ROG_CLEAR reproduce EXP-0162's exactly,
# so r_rog8 is a direct cross-experiment replication of its `pixel_order` result.
ROG_SRC = [0.0625, 0.125, 0.25, 0.5]
ROG_SRC_ALT = [0.125, 0.25, 0.5, 1.0]
ROG_CLEAR = [0.125, 0.25, 0.375, 0.5]
ROG_N = 8
ROG_RESET_ZERO = [0.0, 0.0, 0.0, 0.0]           # r_rog8: EXP-0162 replication
ROG_RESET_NZ = [0.0625, 0.125, 0.25, 0.5]       # r_rogx / r_rog2
ROG_URESET = [1000, 2000, 3000, 4000]           # r_rog2 integer accumulator

# frag_color_pack colour values.
FCP1_LIT = [0.2, 0.4, 0.6, 0.8]                 # literals inside r_fcp1.metal
FCP16_K = [16 * j - 1 for j in range(1, 17)]    # 15,31,...,255 -- all distinct
FCP16 = [f32(k / 255.0) for k in FCP16_K]
FCP16_K_ALT = [16 * j - 9 for j in range(1, 17)]  # 7,23,...,247
FCP16_ALT = [f32(k / 255.0) for k in FCP16_K_ALT]
FCP32 = [f32(2.0 ** j) for j in range(16)]      # r_fcpf, RGBA32Float
FCP32_ALT = [f32(3.0 * 2.0 ** j) for j in range(16)]
FCPH = [1.5, 3.25, 7.125, 15.0625]              # exact in binary16
FCPH_ALT = [2.5, 4.25, 8.125, 16.0625]


def vtx_values_pow2(u):
    """r_v1 / r_v8 / r_v8f: v[k] = u[k&3] * (1 if k<4 else 16).

    Distinct powers of two for the default uniform, so any subset-sum of the
    eight decodes uniquely: a read-back channel names exactly which slot(s)
    reached it, and 0.0 (lost) is unmistakable.
    """
    return [f32(u[k & 3] * (1.0 if k < 4 else 16.0)) for k in range(8)]


def vtx_values_vec(u):
    """r_v4v: sixteen components as four float4s, scaled 1/16/256/4096."""
    out = []
    for s in (1.0, 16.0, 256.0, 4096.0):
        out += [f32(x * s) for x in u]
    return out


def vtx_values_mix(u):
    """r_vmix: twelve observables from MIXED-WIDTH varyings, in RT/channel order.

        c0 = (h0, h1.x, h1.y, f0)                   = ( 1,  2,   4,    8)
        c1 = (f1.x, f1.y, f2.x, f2.y)               = (16, 32,  64,  128)
        c2 = (f2.z, f2.w, h0*1024, f0*1024)         = (256,512,1024, 8192)

    The half-typed values are small integers, exact in binary16, so the oracle
    does not depend on half rounding.  This is the ONLY carrier whose
    ordinal -> byte-offset map is non-linear, which is what makes it the
    discriminator for how `vtx_out_pos.slot` is indexed.
    """
    h0, h1x, h1y, f0 = f32(u[0]), f32(u[1]), f32(u[2]), f32(u[3])
    return [h0, h1x, h1y, f0,
            f32(u[0] * 16.0), f32(u[1] * 16.0), f32(u[0] * 64.0), f32(u[1] * 64.0),
            f32(u[2] * 64.0), f32(u[3] * 64.0), f32(h0 * 1024.0), f32(f0 * 1024.0)]


def vtx_values_chain(u):
    """r_vsrc: t0 = u.x ; t(k+1) = t(k)*1.5 + u.y.

    Every intermediate is dyadic, so the result is exact whether or not the
    compiler contracts the multiply-add into an FMA.
    """
    v = [f32(u[0])]
    for _ in range(7):
        v.append(f32(f32(v[-1] * 1.5) + u[1]))
    return v


def rog_ordered(reset, src, clear, n=ROG_N):
    """r_rog8: additive, commutative.  Ordering intact ->
           texel = R + n*src
           pixel = C + n*R + (n(n+1)/2)*src
    """
    tri = n * (n + 1) // 2
    return {"tex": [f32(reset[i] + n * src[i]) for i in range(4)],
            "pixel": [f32(clear[i] + n * reset[i] + tri * src[i]) for i in range(4)]}


def rog_lost(reset, src, clear, kept, n=ROG_N):
    """Total-serialization-failure model: every fragment reads the same stale
    accumulator, so `kept` distinct updates survive.
           texel = R + kept*src
           pixel = C + n*(R + kept*src)
    With reset = 0 this is exactly EXP-0162's `rog_oracle_lost`."""
    return {"tex": [f32(reset[i] + kept * src[i]) for i in range(4)],
            "pixel": [f32(clear[i] + n * (reset[i] + kept * src[i])) for i in range(4)]}


def rogx_ordered(reset, src, clear, n=ROG_N):
    """r_rogx: affine, NON-commutative.  v <- v*2 + src, so after k applications
           v_k    = 2^k * R + (2^k - 1) * src
           texel  = v_n
           pixel  = C + sum_{i=1..n} v_i
                  = C + (2^(n+1)-2)*R + (2^(n+1)-2-n)*src
    """
    p = 2 ** n
    sp = 2 ** (n + 1) - 2
    return {"tex": [f32(p * reset[i] + (p - 1) * src[i]) for i in range(4)],
            "pixel": [f32(clear[i] + sp * reset[i] + (sp - n) * src[i]) for i in range(4)]}


def rogx_k(reset, src, k):
    """The texel after exactly k applications of the affine update."""
    p = 2 ** k
    return [f32(p * reset[i] + (p - 1) * src[i]) for i in range(4)]


def rog2_ordered(reset, ureset, src, clear, n=ROG_N):
    """r_rog2: float group 0 accumulates additively; uint group 1 accumulates
    uint(16*av.x + 0.5) which, with reset.x == src.x == 0.0625, is exactly i for
    the i-th fragment.  Both are exact integers; nothing depends on rounding."""
    base = rog_ordered(reset, src, clear, n)
    inc = [sum(int(16.0 * f32(reset[0] + i * src[0]) + 0.5) for i in range(1, n + 1)),
           n * 1, n * 2, n * 3]
    base["texu"] = [(ureset[i] + inc[i]) & 0xFFFFFFFF for i in range(4)]
    return base


# ---------------------------------------------------------------------------
# carriers
# ---------------------------------------------------------------------------
#
# `family`      vtx | rog | fcp        -- selects the oracle and the arm rules
# `carrier_dim` the DIMENSION THE FIELD CONTROLS in which this carrier differs
#               from its siblings.  Two carriers with the same carrier_dim value
#               are ONE carrier for verdict purposes; renderrun.py enforces that.
# `priority`    1 = must run, 2 = run if the window allows, 3 = opportunistic
#
CARRIERS = {
    # ================= vtx_out_pos.dst / .slot =============================
    "r_v1": dict(
        family="vtx", kind="render", src="kernels/r_v1.metal",
        color_format=125, rt_count=1, samples=1, width=W, height=H,
        buf0=VTX_U, buf0_alt=VTX_U_ALT, priority=1,
        carrier_dim="varying-slot-count=1 (single-varying CONTROL)",
        why="Reproduces EXP-0147's blind shape on purpose: ONE user varying, so "
            "`slot` -- which selects WHICH output slot -- has nothing to select. "
            "If slot moves nothing here and something on r_v8/r_v4v/r_vsrc, the "
            "EXP-0147 null is a carrier limitation, not a hardware don't-care.",
        vtx_values="pow2_1", n_channels=4),
    "r_v8": dict(
        family="vtx", kind="render", src="kernels/r_v8.metal",
        color_format=125, rt_count=2, samples=1, width=W, height=H,
        buf0=VTX_U, buf0_alt=VTX_U_ALT, out_buf=(1, OUT_BYTES), priority=1,
        carrier_dim="varying-slot-count=8 scalar + vertex-stage device out-buf",
        why="Eight scalar varyings carrying eight distinct powers of two, so a "
            "redirected slot is DECODABLE rather than merely different; plus the "
            "direct per-vertex device-buffer observable, which separates 'the "
            "value was computed' from 'the value was routed to slot k' from 'the "
            "program never ran'.",
        vtx_values="pow2", n_channels=8),
    "r_v8f": dict(
        family="vtx", kind="render", src="kernels/r_v8flat.metal",
        color_format=125, rt_count=2, samples=1, width=W, height=H,
        buf0=VTX_U, buf0_alt=VTX_U_ALT, priority=3,
        carrier_dim="varying-slot-count=8 scalar, FLAT interpolation, no out-buf",
        why="Two controls in one: flat vs smooth changes how the vertex-side "
            "store is lowered (EXP-0163's vflat is one of five carriers that "
            "moved vary_store.hint6), and the absence of the device write "
            "identifies the write itself as a confound if the writing carriers "
            "behave differently.",
        vtx_values="pow2", n_channels=8),
    "r_vmix": dict(
        family="vtx", kind="render", src="kernels/r_vmix.metal",
        color_format=125, rt_count=3, samples=1, width=W, height=H,
        buf0=VTX_U, buf0_alt=VTX_U_ALT, priority=1,
        carrier_dim="MIXED-WIDTH varyings (half/half2/float/float2/float4)",
        why="THE DISCRIMINATOR for how `slot` is indexed. Every other carrier "
            "has uniform-width varyings, and for uniform widths "
            "'ordinal scaled by 4' and 'byte offset into the output block' are "
            "indistinguishable. Mixed widths make the ordinal->offset map "
            "non-linear, so a dense slot sweep here separates the two readings "
            "-- which no number of additional uniform-width carriers can do.",
        vtx_values="mix", n_channels=12),
    "r_v4v": dict(
        family="vtx", kind="render", src="kernels/r_v4vec.metal",
        color_format=125, rt_count=4, samples=1, width=W, height=H,
        buf0=VTX_U, buf0_alt=VTX_U_ALT, out_buf=(1, OUT_BYTES), priority=2,
        carrier_dim="varying-slot-count=4 VECTOR (16 components)",
        why="Same component count as r_v8 doubled, but carried as four float4s "
            "rather than eight floats. If slot's stride-4 corpus values are a "
            "BYTE OFFSET into an output block rather than a slot ordinal, the "
            "slot->offset map differs between scalar and vector programs and "
            "only a set containing both can tell the readings apart.",
        vtx_values="vec", n_channels=16),
    "r_vsrc": dict(
        family="vtx", kind="render", src="kernels/r_vsrc.metal",
        color_format=125, rt_count=2, samples=1, width=W, height=H,
        buf0=VTX_U, buf0_alt=VTX_U_ALT, out_buf=(1, OUT_BYTES), priority=2,
        carrier_dim="8 varyings from a SERIAL CHAIN (8 distinct live registers)",
        why="`dst` is a 4-bit register selector; the only dimension it controls "
            "is which register feeds the output. A serial dependency chain "
            "forces eight simultaneously live distinct values, which is the "
            "register-space condition EXP-0138's copysign.operands sweep lacked "
            "(two live float registers -> a register selector has nothing to "
            "select).",
        vtx_values="chain", n_channels=8),

    # ================= pixel_order.kind ====================================
    "r_rog8": dict(
        family="rog", kind="render", src="kernels/r_rog8.metal",
        color_format=125, rt_count=1, samples=1, width=1, height=1,
        instances=ROG_N, tex_write=(1, 1), texw_reset=ROG_RESET_ZERO,
        clear=ROG_CLEAR, buf0=ROG_SRC, buf0_alt=ROG_SRC_ALT, priority=1,
        carrier_dim="COMMUTATIVE additive RMW, one ordered resource",
        why="Direct replication of EXP-0162's `pixel_order` carrier (same src, "
            "clear, reset, instance count), so its committed per-value partition "
            "is a PRE-REGISTERED PREDICTION this run is scored against rather "
            "than an inert 'differs from baseline' oracle. Ordering failure "
            "presents as a LOST-UPDATE COUNT; being commutative, this carrier is "
            "blind to a pure permutation.",
        rog_model="add", reset=ROG_RESET_ZERO),
    "r_rogx": dict(
        family="rog", kind="render", src="kernels/r_rogx.metal",
        color_format=125, rt_count=1, samples=1, width=1, height=1,
        instances=ROG_N, tex_write=(1, 1), texw_reset=ROG_RESET_NZ,
        clear=ROG_CLEAR, buf0=ROG_SRC, buf0_alt=ROG_SRC_ALT, priority=2,
        carrier_dim="NON-COMMUTATIVE affine RMW (order-sensitive, not only loss)",
        why="v <- v*2 + src is not permutation-invariant and not idempotent, so "
            "ordering failure presents as a WRONG VALUE that names how many "
            "updates were applied -- a different failure signature from r_rog8, "
            "which is the dimension `kind` (acquire vs release) controls.",
        rog_model="affine", reset=ROG_RESET_NZ),
    "r_rog2": dict(
        family="rog", kind="render", src="kernels/r_rog2.metal",
        color_format=125, rt_count=1, samples=1, width=1, height=1,
        instances=ROG_N, tex_write=(1, 1), tex_write_uint=(1, 1),
        texw_reset=ROG_RESET_NZ, texwu_reset=ROG_URESET,
        clear=ROG_CLEAR, buf0=ROG_SRC, buf0_alt=ROG_SRC_ALT, priority=3,
        carrier_dim="TWO ordered resources of different type, data-dependent",
        why="Two raster order groups (float group 0, uint group 1) where group "
            "1's increment derives from group 0's post-update value. Ordering "
            "failure can present as an INCONSISTENCY BETWEEN the two resources, "
            "a third distinct signature, and it puts two independent pixel_order "
            "brackets with different scope in one program.",
        rog_model="two", reset=ROG_RESET_NZ, ureset=ROG_URESET),

    # ================= frag_color_pack.dst =================================
    "r_fcp1": dict(
        family="fcp", kind="render", src="kernels/r_fcp1.metal",
        color_format=80, rt_count=1, samples=1, width=W, height=H, priority=1,
        carrier_dim="1 RT, 8-bit unorm, IMMEDIATE-source packs (EXP-0155 replica)",
        why="EXP-0155's configuration re-authored (BGRA8Unorm, 1 RT, 1 sample, "
            "four scalar varyings written as literals so the compiler may fold "
            "them into the pack's own `val` immediate). This is the CONTROL that "
            "reproduces the prior unstable result; its two pack occurrences are "
            "ONE carrier, which is exactly what EXP-0164 mis-counted as two.",
        fcp_values=FCP1_LIT, fcp_kind="lit"),
    "r_fcp1s": dict(
        family="fcp", kind="render", src="kernels/r_fcp1.metal",
        color_format=80, rt_count=1, samples=4, resolve=True,
        width=W, height=H, priority=3,
        carrier_dim="1 RT, 8-bit unorm, 4x MSAA tile path",
        why="Same source as r_fcp1 with rasterSampleCount 4 -- a controlled "
            "comparison under one changed pipeline parameter (NOT a byte-for-"
            "byte pair: Metal lowers the multisampled fragment build "
            "differently, per EXP-0163's corrected sec.2). Four constant-per-"
            "sample channels resolve to exactly their own value, so the oracle "
            "is unchanged.",
        fcp_values=FCP1_LIT, fcp_kind="lit"),
    "r_fcp4": dict(
        family="fcp", kind="render", src="kernels/r_fcpmrt.metal",
        color_format=80, rt_count=4, samples=1, width=W, height=H,
        buf0=FCP16, buf0_alt=FCP16_ALT, priority=1,
        carrier_dim="4 RTs, 8-bit unorm, REGISTER-source packs (16 live colours)",
        why="Sixteen distinct live colour values in sixteen registers, so "
            "redirecting one pack's destination onto another's register produces "
            "a DECODABLE cross-contamination naming the register it came from. "
            "The set of live colour registers genuinely differs from r_fcp1's, "
            "which is what makes this a second carrier and not a second "
            "occurrence. Runtime-sourced, so the packs must read registers "
            "(db.json's `src_present_mask` 0xd0 register vs 0x50 immediate).",
        fcp_values=FCP16, fcp_kind="reg"),
    "r_fcpf": dict(
        family="fcp", kind="render", src="kernels/r_fcpmrt.metal",
        color_format=125, rt_count=4, samples=1, width=W, height=H,
        buf0=FCP32, buf0_alt=FCP32_ALT, priority=2,
        carrier_dim="4 RTs, 32-bit FLOAT attachment (pack may be absent)",
        why="Same source and same 4-RT shape as r_fcp4 with the attachment "
            "format changed to RGBA32Float, which needs no conversion. If the "
            "census finds ZERO frag_color_pack occurrences here that is a "
            "first-class structural result about when the instruction exists, "
            "recorded rather than treated as a failed build.",
        fcp_values=FCP32, fcp_kind="reg"),
    "r_fcph": dict(
        family="fcp", kind="render", src="kernels/r_fcph.metal",
        color_format=115, rt_count=1, samples=1, width=W, height=H,
        buf0=FCPH, buf0_alt=FCPH_ALT, priority=2,
        carrier_dim="1 RT, 16-bit FLOAT attachment (different conversion class)",
        why="r_fcp1 and r_fcp4 both convert float -> 8-bit normalised integer. "
            "RGBA16Float is a different conversion class (no normalisation, two "
            "halves per word). If the pack's destination assignment depends on "
            "how many components share a word, an 8-bit-only set cannot see it.",
        fcp_values=FCPH, fcp_kind="reg"),
}

VERTEX_FN = "v_main"
FRAGMENT_FN = "f_main"


def probe_pixels(cfg):
    return PROBE_PIXELS_1X1 if cfg["width"] * cfg["height"] == 1 else PROBE_PIXELS


def buf0_words(cfg, alt=False):
    b = cfg.get("buf0_alt" if alt else "buf0")
    if not b:
        return None
    return words(b)


def buf0_override_bytes(cfg):
    """The `@buf0=` payload for the zero-hazard DATA LADDER, or None when the
    carrier has no runtime-sourced input (r_fcp1 / r_fcp1s use literals)."""
    w = buf0_words(cfg, alt=True)
    if not w:
        return None
    return b"".join(struct.pack("<I", x) for x in w)


# ---------------------------------------------------------------------------
# decoding a read-back surface
# ---------------------------------------------------------------------------


def decode_pixel(buf, fmt, x, y, width):
    bpp = BYTES_PER_PIXEL[fmt]
    base = (y * width + x) * bpp
    if base + bpp > len(buf):
        return None
    if fmt == 125:
        return [f32(v) for v in struct.unpack_from("<4f", buf, base)]
    if fmt == 115:
        return list(struct.unpack_from("<4H", buf, base))          # raw half bits
    return list(buf[base:base + 4])                                # BGRA bytes


def decode_texw(buf, x=0, y=0, width=1):
    base = (y * width + x) * 16
    if base + 16 > len(buf):
        return None
    return [f32(v) for v in struct.unpack_from("<4f", buf, base)]


def decode_texwu(buf, x=0, y=0, width=1):
    base = (y * width + x) * 16
    if base + 16 > len(buf):
        return None
    return list(struct.unpack_from("<4I", buf, base))


def decode_outbuf(buf):
    n = len(buf) // 4
    return [f32(v) for v in struct.unpack_from("<%df" % n, buf, 0)]


# ---------------------------------------------------------------------------
# host oracles, per family
# ---------------------------------------------------------------------------

POISON_F = struct.unpack("<f", bytes.fromhex("efbeadde"))[0]


def oracle(name, alt=False):
    """The complete host-computed expected observation for a carrier, as a dict
    of surface tag -> expected decoded values.  Computed here, never read back
    from the device."""
    cfg = CARRIERS[name]
    fam = cfg["family"]
    if fam == "vtx":
        u = cfg["buf0_alt"] if alt else cfg["buf0"]
        kind = cfg["vtx_values"]
        if kind == "pow2_1":
            vals = [f32(v) for v in u]
        elif kind == "pow2":
            vals = vtx_values_pow2(u)
        elif kind == "vec":
            vals = vtx_values_vec(u)
        elif kind == "mix":
            vals = vtx_values_mix(u)
        else:
            vals = vtx_values_chain(u)
        o = {}
        for rt in range(cfg["rt_count"]):
            o["PIX%d" % rt] = vals[rt * 4:rt * 4 + 4]
        if cfg.get("out_buf"):
            # Post-transform vertex positions of the full-screen triangle.
            pos = [(-1.0, -1.0), (3.0, -1.0), (-1.0, 3.0)]
            ob = [None] * (OUT_STRIDE_FLOATS * OUT_VERTS)
            for v in range(OUT_VERTS):
                b = v * OUT_STRIDE_FLOATS
                ob[b + 0], ob[b + 1] = f32(pos[v][0]), f32(pos[v][1])
                ob[b + 2], ob[b + 3] = 0.0, 1.0
                for k, val in enumerate(vals):
                    ob[b + 4 + k] = val
                m = b + 4 + len(vals)
                ob[m + 0] = float(v)
                ob[m + 1], ob[m + 2], ob[m + 3] = -1.0, -2.0, -3.0
            o["OUTBUF"] = ob            # None == "written by nothing: stay poison"
        return o
    if fam == "rog":
        src = cfg["buf0_alt"] if alt else cfg["buf0"]
        R, C = cfg["reset"], cfg["clear"]
        if cfg["rog_model"] == "add":
            g = rog_ordered(R, src, C)
        elif cfg["rog_model"] == "affine":
            g = rogx_ordered(R, src, C)
        else:
            g = rog2_ordered(R, cfg["ureset"], src, C)
        o = {"PIX0": g["pixel"], "TEXW": g["tex"]}
        if "texu" in g:
            o["TEXWU"] = g["texu"]
        return o
    # fcp
    vals = cfg["fcp_values"]
    if alt:
        vals = {"r_fcp4": FCP16_ALT, "r_fcpf": FCP32_ALT,
                "r_fcph": FCPH_ALT}.get(name, vals)
    fmt = cfg["color_format"]
    o = {}
    for rt in range(cfg["rt_count"]):
        ch = vals[rt * 4:rt * 4 + 4]
        if fmt == 80:
            # BGRA8Unorm: the read-back byte order is B,G,R,A.
            o["PIX%d" % rt] = [unorm8(ch[2]), unorm8(ch[1]),
                               unorm8(ch[0]), unorm8(ch[3])]
        elif fmt == 115:
            o["PIX%d" % rt] = [f16_bits(v) for v in ch]
        else:
            o["PIX%d" % rt] = [f32(v) for v in ch]
    return o


def classify_rog(name, observed, alt=False):
    """Name what happened to an ordered RMW, in EXP-0162's outcome vocabulary.

    `observed` is {tag: decoded values}.  Returns one of
        ok | lost_<k>_of_<n> | applied_<k> | inconsistent | no_draw |
        silent_zero | wrong_value
    """
    cfg = CARRIERS[name]
    src = cfg["buf0_alt"] if alt else cfg["buf0"]
    R, C = cfg["reset"], cfg["clear"]
    px, tx = observed.get("PIX0"), observed.get("TEXW")
    if px is None or tx is None:
        return "wrong_value"
    good = oracle(name, alt)
    if _eq(px, good["PIX0"]) and _eq(tx, good["TEXW"]):
        if "TEXWU" in good:
            if not _eq(observed.get("TEXWU"), good["TEXWU"]):
                return "inconsistent"
        return "ok"
    if "TEXWU" in good and _eq(observed.get("TEXWU"), good["TEXWU"]) \
            and not _eq(tx, good["TEXW"]):
        return "inconsistent"
    if _eq(px, [f32(c) for c in C]) and _eq(tx, [f32(r) for r in R]):
        return "no_draw"
    if cfg["rog_model"] in ("add", "two"):
        for kept in range(0, ROG_N):
            m = rog_lost(R, src, C, kept)
            if _eq(tx, m["tex"]) and _eq(px, m["pixel"]):
                return "lost_%d_of_%d" % (ROG_N - kept, ROG_N)
    else:
        for k in range(0, ROG_N):
            if _eq(tx, rogx_k(R, src, k)):
                return "applied_%d" % k
    if all(abs(v) < 1e-9 for v in tx):
        return "silent_zero"
    return "wrong_value"


def _eq(a, b, tol=0.0):
    if a is None or b is None:
        return False
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if isinstance(x, float) or isinstance(y, float):
            if abs(float(x) - float(y)) > tol * max(1.0, abs(float(y))):
                return False
        elif x != y:
            return False
    return True


def selftest():
    """Every claim this module makes about exactness, checked in Python."""
    bad = []

    def chk(tag, got, want):
        if got != want:
            bad.append("%s: got %r want %r" % (tag, got, want))

    chk("pow2", vtx_values_pow2(VTX_U), [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0])
    chk("pow2_alt", vtx_values_pow2(VTX_U_ALT), [3.0, 5.0, 9.0, 17.0, 48.0, 80.0, 144.0, 272.0])
    chk("vec", vtx_values_vec(VTX_U)[:8], [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0])
    chk("vec_hi", vtx_values_vec(VTX_U)[12:], [4096.0, 8192.0, 16384.0, 32768.0])
    chk("mix", vtx_values_mix(VTX_U),
        [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0, 512.0, 1024.0, 8192.0])
    chk("mix_alt", vtx_values_mix(VTX_U_ALT),
        [3.0, 5.0, 9.0, 17.0, 48.0, 80.0, 192.0, 320.0, 576.0, 1088.0,
         3072.0, 17408.0])
    chk("chain", vtx_values_chain(VTX_U),
        [1.0, 3.5, 7.25, 12.875, 21.3125, 33.96875, 52.953125, 81.4296875])
    # every vertex value must be distinct: that is what makes a subset-sum decodable
    for nm, vv in (("pow2", vtx_values_pow2(VTX_U)), ("vec", vtx_values_vec(VTX_U)),
                   ("mix", vtx_values_mix(VTX_U)),
                   ("mix_alt", vtx_values_mix(VTX_U_ALT)),
                   ("chain", vtx_values_chain(VTX_U))):
        if len(set(vv)) != len(vv):
            bad.append("%s: values not distinct" % nm)
        if 0.0 in vv:
            bad.append("%s: contains 0.0, colliding with 'lost'" % nm)
    # EXP-0162 replication: r_rog8's ordered oracle must equal EXP-0162's numbers
    g = rog_ordered(ROG_RESET_ZERO, ROG_SRC, ROG_CLEAR)
    chk("rog8 tex", g["tex"], [0.5, 1.0, 2.0, 4.0])
    chk("rog8 pixel", g["pixel"], [2.375, 4.75, 9.375, 18.5])
    l1 = rog_lost(ROG_RESET_ZERO, ROG_SRC, ROG_CLEAR, 1)
    chk("rog8 lost7 tex", l1["tex"], [0.0625, 0.125, 0.25, 0.5])
    chk("rog8 lost7 pixel", l1["pixel"], [0.625, 1.25, 2.375, 4.5])
    gx = rogx_ordered(ROG_RESET_NZ, ROG_SRC, ROG_CLEAR)
    chk("rogx tex", gx["tex"], [31.9375, 63.875, 127.75, 255.5])
    chk("rogx pixel", gx["pixel"], [63.375, 126.75, 253.375, 506.5])
    # every affine step must land on its own value
    ks = [tuple(rogx_k(ROG_RESET_NZ, ROG_SRC, k)) for k in range(ROG_N + 1)]
    if len(set(ks)) != len(ks):
        bad.append("rogx: affine steps not distinct")
    g2 = rog2_ordered(ROG_RESET_NZ, ROG_URESET, ROG_SRC, ROG_CLEAR)
    chk("rog2 texu", g2["texu"], [1044, 2008, 3016, 4024])
    # unorm oracle: r_fcp1's four literals land on exact codes with a real margin
    chk("fcp1 codes", [unorm8(v) for v in FCP1_LIT], [51, 102, 153, 204])
    for v in FCP1_LIT + FCP16 + FCP16_ALT:
        if unorm8_margin(v) < 0.4:
            bad.append("unorm tie too close: %r (margin %r)" % (v, unorm8_margin(v)))
    chk("fcp16 codes", [unorm8(v) for v in FCP16], FCP16_K)
    chk("fcp16alt codes", [unorm8(v) for v in FCP16_ALT], FCP16_K_ALT)
    if len(set(FCP16_K)) != 16 or len(set(FCP16_K_ALT)) != 16:
        bad.append("fcp16: codes not distinct")
    if set(FCP16_K) & set(FCP16_K_ALT):
        bad.append("fcp16: ladder codes overlap the baseline codes")
    # half oracle: exact round-trip, so no rounding ambiguity in r_fcph
    for v in FCPH + FCPH_ALT:
        if bits_f16(f16_bits(v)) != v:
            bad.append("half not exact: %r" % v)
    if len(set(FCPH)) != 4 or set(FCPH) & set(FCPH_ALT):
        bad.append("fcph: values not distinct / ladder overlaps baseline")
    # r_vmix's half-typed lanes must be EXACT in binary16, or its oracle is not
    # exact.  Asserted for both the baseline and the ladder uniform.
    for u in (VTX_U, VTX_U_ALT):
        for x in (u[0], u[1], u[2]):
            if bits_f16(f16_bits(x)) != f32(x):
                bad.append("r_vmix half lane not exact in binary16: %r" % x)
    # the carrier_dim contract: no two carriers in a family may share a dimension
    seen = {}
    for k, c in CARRIERS.items():
        key = (c["family"], c["carrier_dim"])
        if key in seen:
            bad.append("carrier_dim collision: %s and %s" % (seen[key], k))
        seen[key] = k
    # every oracle must be computable
    for k in CARRIERS:
        oracle(k)
        oracle(k, alt=True)
    return bad


if __name__ == "__main__":
    f = selftest()
    print("rendercarriers selftest: %s" % ("PASS" if not f else "FAIL\n  " + "\n  ".join(f)))
    if f:
        raise SystemExit(1)
