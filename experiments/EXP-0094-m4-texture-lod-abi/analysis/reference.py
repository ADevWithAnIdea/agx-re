#!/usr/bin/env python3
"""EXP-0094 independently-derived sampling-math reference oracle.

Every formula here is derived BY US from public, well-known texture-sampling
mathematics (the standard OpenGL/Vulkan/D3D "rho/lambda" implicit-LOD formula,
and the standard cube-map direction-to-face-UV projection, differentiated by
us via the ordinary quotient rule). Nothing here is copied from Apple's
implementation, from Mesa, or from any other GPU driver/compiler source --
per the addendum's explicit instruction ("compute expected LOD/face selection
from the sampling math in your own Python", "do NOT copy any reference
implementation"). This module is PUBLIC-derivation, used only as an
independent oracle to compare real M4 hardware behavior against; where they
diverge, the hardware behavior is the fact and the divergence itself is the
reported result (this is an explicitly anticipated, first-class possible
outcome per the addendum's "key falsifier").

CLEAN-ROOM: pure math, no external code, no data from any Apple binary.
"""
import math

# ---------------------------------------------------------------------------
# 2D implicit LOD (rho/lambda formula)
# ---------------------------------------------------------------------------

def base_lod_2d(dudx, dvdx, dudy, dvdy, w, h):
    """Standard 'rho' scale-factor formula (OpenGL 4.6 sec 8.14.1 / D3D common
    practice): rho = max( |(dudx,dvdx)*(w,h)| , |(dudy,dvdy)*(w,h)| ),
    lambda_base = log2(rho). Returns -inf if rho == 0 (perfectly minified to a
    point -- maximum magnification, most-detailed mip)."""
    mx = math.hypot(dudx * w, dvdx * h)
    my = math.hypot(dudy * w, dvdy * h)
    rho = max(mx, my)
    if rho == 0.0:
        return float("-inf")
    if math.isnan(rho):
        return float("nan")
    return math.log2(rho)


def effective_lod(base, bias):
    return base + bias


def clamp_lod(lod, lod_min, lod_max, mip_count):
    """Order asserted by this reference (to be checked against HW, not
    assumed): bias is added first, then the result is clamped to the
    sampler's [lodMinClamp, lodMaxClamp], then clamped again to the texture's
    representable mip range [0, mipCount-1]."""
    if math.isnan(lod):
        return float("nan")
    lo = max(0.0, lod_min)
    hi = min(float(mip_count - 1), lod_max)
    if hi < lo:
        hi = lo
    return max(lo, min(hi, lod))


# ---------------------------------------------------------------------------
# Cube-map face selection (OpenGL 4.6 sec 8.13, "Cube Map Texture Selection")
# ---------------------------------------------------------------------------
# Metal/OpenGL common face-slice order (public API convention, independently
# confirmed on hardware in this experiment's cube_faceid backend):
#   0:+X 1:-X 2:+Y 3:-Y 4:+Z 5:-Z
FACE_PX, FACE_NX, FACE_PY, FACE_NY, FACE_PZ, FACE_NZ = range(6)
FACE_NAMES = ["+X", "-X", "+Y", "-Y", "+Z", "-Z"]


def select_face(rx, ry, rz):
    """Major-axis face selection. Ties are broken by a FIXED, DOCUMENTED
    left-to-right test order (X, then Y, then Z); the OpenGL spec leaves exact
    tie-break to the implementation, so an HW mismatch exactly AT a tie is
    recorded as an implementation-choice difference, not treated as a defect,
    per GLTEX-A02's own framing ("major-axis ties")."""
    ax, ay, az = abs(rx), abs(ry), abs(rz)
    if ax >= ay and ax >= az:
        return FACE_PX if rx > 0 else FACE_NX
    if ay >= ax and ay >= az:
        return FACE_PY if ry > 0 else FACE_NY
    return FACE_PZ if rz > 0 else FACE_NZ


def face_uv(face, rx, ry, rz):
    """Standard direction -> per-face (s,t) in [0,1], major-axis magnitude M.
    Table per the public OpenGL cube-map-face convention."""
    if face == FACE_PX:
        M, sc, tc = rx, -rz, -ry
    elif face == FACE_NX:
        M, sc, tc = -rx, rz, -ry
    elif face == FACE_PY:
        M, sc, tc = ry, rx, rz
    elif face == FACE_NY:
        M, sc, tc = -ry, rx, -rz
    elif face == FACE_PZ:
        M, sc, tc = rz, rx, -ry
    else:
        M, sc, tc = -rz, -rx, -ry
    s = (sc / abs(M) + 1.0) / 2.0
    t = (tc / abs(M) + 1.0) / 2.0
    return s, t, M


def _sc_tc_dsigns(face):
    """Returns (which raw component feeds sc, its sign, which feeds tc, its
    sign, which feeds M, its sign) so the derivative code below can be
    generic. sign is +1 or -1 applied to the raw component derivative."""
    table = {
        FACE_PX: (('z', -1), ('y', -1), ('x', +1)),
        FACE_NX: (('z', +1), ('y', -1), ('x', -1)),
        FACE_PY: (('x', +1), ('z', +1), ('y', +1)),
        FACE_NY: (('x', +1), ('z', -1), ('y', -1)),
        FACE_PZ: (('x', +1), ('y', -1), ('z', +1)),
        FACE_NZ: (('x', -1), ('y', -1), ('z', -1)),
    }
    return table[face]


def face_uv_gradient(face, r, dPdx, dPdy):
    """Derivative of face_uv() w.r.t. screen x/y, by the ordinary quotient
    rule applied to s = sc/(2|M|) + 1/2 (and t analogously), derived BY US
    (not copied) from the direction-to-face-UV formula above.

    d/dx [ sc / (2*|M|) ] = ( dsc/dx * |M| - sc * d|M|/dx ) / (2*M^2)
    and d|M|/dx = sign(M) * dM/dx (M is never exactly 0 for a normalized
    direction actually used as a cube coordinate).

    r = (rx,ry,rz); dPdx, dPdy = 3-component gradients of r w.r.t. screen x,y.
    Returns (ds_dx, dt_dx, ds_dy, dt_dy).
    """
    (sc_c, sc_sign), (tc_c, tc_sign), (m_c, m_sign) = _sc_tc_dsigns(face)
    comp = {'x': 0, 'y': 1, 'z': 2}
    rx, ry, rz = r
    M = m_sign * (rx, ry, rz)[comp[m_c]]
    sc = sc_sign * (rx, ry, rz)[comp[sc_c]]
    tc = tc_sign * (rx, ry, rz)[comp[tc_c]]

    def grad_of(which_c, sign, dP):
        return sign * dP[comp[which_c]]

    def duv(dP):
        dM = m_sign * dP[comp[m_c]]
        dsc = grad_of(sc_c, sc_sign, dP)
        dtc = grad_of(tc_c, tc_sign, dP)
        absM = abs(M)
        dAbsM = math.copysign(1.0, M) * dM
        ds = (dsc * absM - sc * dAbsM) / (2.0 * absM * absM)
        dt = (dtc * absM - tc * dAbsM) / (2.0 * absM * absM)
        return ds, dt

    ds_dx, dt_dx = duv(dPdx)
    ds_dy, dt_dy = duv(dPdy)
    return ds_dx, dt_dx, ds_dy, dt_dy


def cube_gradient_lod(rx, ry, rz, dPdx, dPdy, face_size):
    """Full pipeline: select face, project the 3-component direction gradient
    to face-local (s,t) partials via the quotient-rule derivative above, then
    apply the SAME 2D rho/lambda formula as base_lod_2d with w=h=face_size.
    This is OUR OWN composition of two independently-public formulas; real
    hardware is free to use a different (e.g. cheaper/approximate)
    implementation -- any divergence is the reported result, not "fixed" to
    match."""
    face = select_face(rx, ry, rz)
    ds_dx, dt_dx, ds_dy, dt_dy = face_uv_gradient(face, (rx, ry, rz), dPdx, dPdy)
    lod = base_lod_2d(ds_dx, dt_dx, ds_dy, dt_dy, face_size, face_size)
    return face, lod
