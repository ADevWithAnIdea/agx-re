#!/usr/bin/env python3
"""EXP-0094 shared case matrix -- single source of truth imported by run.py
and verify.py (never restated). Six backends, one unified gated record shape.

  bias_sweep     -- kernels/bias_probe.metal via harness/texrender (public
                     Metal source compile, no splice). GLTEX-A01.
  grad_sweep     -- kernels/grad_probe.metal via harness/texcompute (public
                     Metal, no splice). GLTEX-A02.
  lodquery       -- kernels/lodquery_probe.metal via harness/texrender
                     (public Metal, no splice). GLTEX-A03.
  cube_faceid    -- kernels/cube_faceid.metal via harness/texcompute (public
                     Metal, no splice). GLTEX-A02 (face selection half).
  cube_grad      -- kernels/cube_grad.metal via harness/texcompute (public
                     Metal, no splice). GLTEX-A02 (cube-gradient LOD half).
  regsplice_bias -- kernels/regpair_bias_{A,B}.metal, compiled to F32-color
                     archives (harness/bin/shdump --color-format 55) and
                     spliced at a FROZEN absolute file offset (found by
                     differential compilation, see PROGRESS.md/RESULTS.md),
                     run via harness/texrender --archive. HW-VALIDATED
                     downstream-consumer proof for GLTEX-A02's
                     bias-operand-register claim.

Every numeric field a case can carry (bias/gradient/direction/lodclamp
components) may be a finite float OR the strings "inf"/"-inf"/"nan"
(JSON-safe; converted to argv floats by run.py's harness invocation).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reference as REF  # noqa: E402

EXP = HERE.parent
KERNELS_DIR = EXP / "kernels"

# ---------------------------------------------------------------------------
# shared texture geometry for the LOD-recovery probes
# ---------------------------------------------------------------------------
TEX_W = TEX_H = 256
TEX_LEVELS = 9          # levels 0..8, sizes 256..1
FACE_SIZE = 256
CUBE_LEVELS = 9

SPECIAL = {"inf": float("inf"), "-inf": float("-inf"), "nan": float("nan")}


def _f(v):
    """string-or-float -> float, for computing expected values (JSON-safe in;
    real float out, used only for the host-side oracle, never re-serialized)."""
    if isinstance(v, str):
        return SPECIAL[v]
    return float(v)


# ---------------------------------------------------------------------------
# bias_sweep -- GLTEX-A01. Fixed uvScale gives base_lod=0 exactly (uvScale.x
# = 1/TEX_W, uvScale.y = 0) so effective LOD = bias() alone (before sampler
# clamp). Finite-resource sweep: zero, signed zero, ordinary +/-, the
# in-range endpoints [0, TEX_LEVELS-1]=[0,8], the first value outside each
# endpoint, very large magnitude, subnormal, +-Inf, NaN. A second block
# varies the SAMPLER lodMinClamp/lodMaxClamp with a fixed bias to test
# clamp-order; a third block restricts the texture to a MIP VIEW (levels
# 2..6) to test base/max-level interaction.
# ---------------------------------------------------------------------------
BIAS_CORE = [
    ("zero", 0.0), ("neg_zero", -0.0),
    ("small_pos", 0.5), ("small_neg", -0.5),
    ("one", 1.0), ("neg_one", -1.0),
    ("mid", 4.0), ("neg_mid", -4.0),
    ("max_valid", 8.0),            # last mip index
    ("above_max", 8.5),            # first value past the last mip
    ("below_min", -1.0),           # first value below mip 0
    ("far_below_min", -20.0),
    ("huge_pos", 1.0e6),
    ("huge_neg", -1.0e6),
    ("fmax", 3.0e38),
    ("subnormal", 1.0e-40),
    ("inf", "inf"), ("neg_inf", "-inf"), ("nan", "nan"),
]

BIAS_CLAMP_CASES = [
    # (name, bias, lod_min, lod_max)
    ("clamp_max3_bias6", 6.0, 0.0, 3.0),     # bias alone would give LOD 6; sampler max clamps to 3
    ("clamp_min5_bias1", 1.0, 5.0, 8.0),     # bias alone would give LOD 1; sampler min clamps to 5
    ("clamp_tight_bias4", 4.0, 3.5, 4.5),    # bias inside a tight window
    ("clamp_inverted_ignored", 4.0, 6.0, 2.0),  # min>max: observe raw HW behavior, no a-priori oracle
]

BIAS_VIEW_CASES = [
    # (name, bias, view_lo, view_hi) -- texture VIEW restricted to levels [lo,hi]
    ("view_2_6_bias0", 0.0, 2, 6),
    ("view_2_6_bias8", 8.0, 2, 6),   # bias alone would ask for level 8; view only has 5 levels (0..4 local)
    ("view_2_6_biasneg", -3.0, 2, 6),
]


def bias_sweep_cases():
    out = []
    uvsx, uvsy = 1.0 / TEX_W, 0.0
    for name, bias in BIAS_CORE:
        b = _f(bias)
        base = REF.base_lod_2d(uvsx, 0.0, 0.0, uvsy, TEX_W, TEX_H)
        if isinstance(bias, str) or (isinstance(bias, float) and (bias != bias)):
            expected = None
        else:
            eff = REF.effective_lod(base, b)
            expected = {"lod": REF.clamp_lod(eff, 0.0, 1000.0, TEX_LEVELS)}
        out.append({"case_name": f"core_{name}", "bias": bias, "lod_min": None, "lod_max": None,
                     "view": None, "expected": expected})
    for name, bias, lmin, lmax in BIAS_CLAMP_CASES:
        base = REF.base_lod_2d(uvsx, 0.0, 0.0, uvsy, TEX_W, TEX_H)
        eff = REF.effective_lod(base, bias)
        if lmin <= lmax:
            expected = {"lod": REF.clamp_lod(eff, lmin, lmax, TEX_LEVELS)}
        else:
            expected = None  # inverted clamp range: no a-priori oracle, observe raw behavior
        out.append({"case_name": f"clamp_{name}", "bias": bias, "lod_min": lmin, "lod_max": lmax,
                     "view": None, "expected": expected})
    for name, bias, vlo, vhi in BIAS_VIEW_CASES:
        # view semantics (does level 0 of the view == texture level vlo?) are
        # exactly what this sub-probe tests; no a-priori oracle for the
        # readback VALUE, but we record the naive full-texture prediction for
        # comparison.
        base = REF.base_lod_2d(uvsx, 0.0, 0.0, uvsy, TEX_W, TEX_H)
        eff = REF.effective_lod(base, bias)
        naive_full = REF.clamp_lod(eff, 0.0, 1000.0, TEX_LEVELS)
        out.append({"case_name": f"view_{name}", "bias": bias, "lod_min": None, "lod_max": None,
                     "view": [vlo, vhi], "expected": None,
                     "naive_full_texture_lod": naive_full})
    return out


# ---------------------------------------------------------------------------
# grad_sweep -- GLTEX-A02. Independent (asymmetric) dx/dy pairs.
# ---------------------------------------------------------------------------
GRAD_CASES = [
    ("zero", (0.0, 0.0), (0.0, 0.0)),
    ("x_small", (1.0 / TEX_W, 0.0), (0.0, 0.0)),
    ("x_large", (16.0 / TEX_W, 0.0), (0.0, 0.0)),
    ("y_small", (0.0, 0.0), (0.0, 1.0 / TEX_H)),
    ("y_large", (0.0, 0.0), (0.0, 16.0 / TEX_H)),
    ("asym_x_lt_y", (0.5 / TEX_W, 0.0), (0.0, 32.0 / TEX_H)),
    ("asym_x_gt_y", (32.0 / TEX_W, 0.0), (0.0, 0.5 / TEX_H)),
    ("neg_sign_x", (-16.0 / TEX_W, 0.0), (0.0, 0.0)),
    ("neg_sign_y", (0.0, 0.0), (0.0, -16.0 / TEX_H)),
    ("subnormal", (1.0e-40, 0.0), (0.0, 1.0e-40)),
    ("huge", (1.0e6, 0.0), (0.0, 1.0e6)),
    ("inf_dx_x", ("inf", 0.0), (0.0, 0.0)),
    ("inf_dy_y", (0.0, 0.0), (0.0, "inf")),
    ("nan_dx_x", ("nan", 0.0), (0.0, 0.0)),
    ("nan_dy_y", (0.0, 0.0), (0.0, "nan")),
    ("both_inf", ("inf", "inf"), ("inf", "inf")),
    ("both_nan", ("nan", "nan"), ("nan", "nan")),
    ("mixed_inf_nan", ("inf", 0.0), (0.0, "nan")),
]


def grad_sweep_cases():
    out = []
    for name, dx, dy in GRAD_CASES:
        dxf = (_f(dx[0]), _f(dx[1]))
        dyf = (_f(dy[0]), _f(dy[1]))
        has_special = any(isinstance(v, str) for v in (dx[0], dx[1], dy[0], dy[1]))
        if has_special:
            expected = None
        else:
            base = REF.base_lod_2d(dxf[0], dxf[1], dyf[0], dyf[1], TEX_W, TEX_H)
            expected = {"lod": REF.clamp_lod(base, 0.0, 1000.0, TEX_LEVELS)}
        out.append({"case_name": name, "dx": list(dx), "dy": list(dy), "expected": expected})
    return out


# ---------------------------------------------------------------------------
# lodquery -- GLTEX-A03. Sweep base LOD via uvScale; a few sampler
# lodMin/lodMax clamp combinations to separate clamped vs unclamped.
# ---------------------------------------------------------------------------
LODQUERY_CASES = [
    # (name, target_base_lod, lod_min, lod_max)
    ("lod0_noclamp", 0, None, None),
    ("lod2_noclamp", 2, None, None),
    ("lod4_noclamp", 4, None, None),
    ("lod6_noclamp", 6, None, None),
    ("lod8_noclamp", 8, None, None),
    ("lod6_max3", 6, 0.0, 3.0),
    ("lod2_min5", 2, 5.0, 8.0),
    ("lod4_tight", 4, 3.5, 4.5),
    ("lod0_min2", 0, 2.0, 8.0),
    ("lod8_max6", 8, 0.0, 6.0),
]


def lodquery_cases():
    out = []
    for name, target_lod, lmin, lmax in LODQUERY_CASES:
        uvsx = (2.0 ** target_lod) / TEX_W
        uvsy = 0.0
        base = REF.base_lod_2d(uvsx, 0.0, 0.0, uvsy, TEX_W, TEX_H)
        unclamped = base
        clamped = REF.clamp_lod(base, lmin if lmin is not None else 0.0,
                                 lmax if lmax is not None else 1000.0, TEX_LEVELS)
        out.append({"case_name": name, "uvsx": uvsx, "uvsy": uvsy,
                     "lod_min": lmin, "lod_max": lmax,
                     "expected": {"sampled_lod": clamped, "clamped_lod": clamped,
                                  "unclamped_lod": unclamped}})
    return out


# ---------------------------------------------------------------------------
# cube_faceid -- GLTEX-A02 (face selection). Face centers, edge midpoints,
# corners (major-axis ties).
# ---------------------------------------------------------------------------
def _norm(v):
    import math
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


CUBE_FACE_COLORS = [
    (255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255),
    (255, 255, 0, 255), (0, 255, 255, 255), (255, 0, 255, 255),
]


def cube_faceid_cases():
    dirs = []
    # 6 face centers
    for v in [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]:
        dirs.append(("center_%+d%+d%+d" % v, v))
    # 12 edge midpoints (two nonzero components equal magnitude)
    axes = [0, 1, 2]
    signs = [1, -1]
    seen = set()
    for a in axes:
        for b in axes:
            if b <= a:
                continue
            for sa in signs:
                for sb in signs:
                    v = [0, 0, 0]
                    v[a] = sa
                    v[b] = sb
                    key = tuple(v)
                    if key in seen:
                        continue
                    seen.add(key)
                    dirs.append(("edge_%+d%+d%+d" % tuple(v), tuple(v)))
    # 8 corners (major-axis ties across all three axes)
    for sx in signs:
        for sy in signs:
            for sz in signs:
                v = (sx, sy, sz)
                dirs.append(("corner_%+d%+d%+d" % v, v))
    out = []
    for name, v in dirs:
        nv = _norm(v)
        face = REF.select_face(*v)
        out.append({"case_name": name, "dir": list(nv), "expected": {"face": face,
                    "face_name": REF.FACE_NAMES[face], "color": list(CUBE_FACE_COLORS[face])}})
    return out


# ---------------------------------------------------------------------------
# cube_grad -- GLTEX-A02 (cube gradient LOD). A few representative directions
# (face center / near-edge / at-edge / at-corner) x a few gradient
# magnitudes.
# ---------------------------------------------------------------------------
CUBE_GRAD_DIRS = [
    ("face_center", (1.0, 0.0, 0.0)),
    ("near_edge", (1.0, 0.9, 0.0)),
    ("at_edge", (1.0, 1.0, 0.0)),
    ("at_corner", (1.0, 1.0, 1.0)),
]
CUBE_GRAD_MAGS = [
    ("small", 0.001), ("medium", 0.01), ("large", 0.05),
]


def cube_grad_cases():
    out = []
    for dname, d in CUBE_GRAD_DIRS:
        nd = _norm(d)
        for mname, mag in CUBE_GRAD_MAGS:
            dPdx = (0.0, mag, 0.0)
            dPdy = (0.0, 0.0, mag)
            face, lod = REF.cube_gradient_lod(nd[0], nd[1], nd[2], dPdx, dPdy, FACE_SIZE)
            out.append({"case_name": f"{dname}_{mname}", "dir": list(nd),
                         "dPdx": list(dPdx), "dPdy": list(dPdy),
                         "expected": {"face": face, "lod": REF.clamp_lod(lod, 0.0, 1000.0, CUBE_LEVELS)}})
    return out


# ---------------------------------------------------------------------------
# regsplice_bias -- GLTEX-A02 splice validation (HW-VALIDATED). FROZEN
# archive-byte offset found by differential compilation (PROGRESS.md
# 2026-08-28 T2): absolute file offset 15653 == `_agc.main` base (15584) + 69,
# in the F32-color (--color-format 55) archives of
# kernels/regpair_bias_A.metal / regpair_bias_B.metal. Splice values: A's
# native byte 0x06, B's native byte 0x08, plus one control value 0x00 (an
# unclaimed byte value -- observe raw behavior, no a-priori oracle).
# ---------------------------------------------------------------------------
REGSPLICE_MAIN_OFFSET = 15584  # `_agc.main` absolute file offset in the frozen archives
REGSPLICE_BYTE_OFFSET = 69      # offset WITHIN `_agc.main`
REGSPLICE_ABS_OFFSET = REGSPLICE_MAIN_OFFSET + REGSPLICE_BYTE_OFFSET
REGSPLICE_A_NATIVE = 0x06
REGSPLICE_B_NATIVE = 0x08
BIAS_A_VALUE = 2.0
BIAS_B_VALUE = 6.0

REGSPLICE_CASES = [
    # (name, base_archive, splice_byte, expect_reads_as)
    ("A_unspliced", "A", None, "A"),
    ("B_unspliced", "B", None, "B"),
    ("A_spliced_to_B", "A", REGSPLICE_B_NATIVE, "B"),
    ("B_spliced_to_A", "B", REGSPLICE_A_NATIVE, "A"),
    ("A_spliced_control0", "A", 0x00, None),   # no a-priori oracle -- observe raw value
]


def regsplice_bias_cases():
    out = []
    for name, base, splice_byte, expect_reads_as in REGSPLICE_CASES:
        expected = None
        if expect_reads_as == "A":
            expected = {"lod": BIAS_A_VALUE}
        elif expect_reads_as == "B":
            expected = {"lod": BIAS_B_VALUE}
        out.append({"case_name": name, "base_archive": base, "splice_byte": splice_byte,
                     "expected": expected})
    return out


BACKENDS = ("bias_sweep", "grad_sweep", "lodquery", "cube_faceid", "cube_grad", "regsplice_bias")


def full_case_list():
    cases = []
    i = 0
    for c in bias_sweep_cases():
        cases.append({"i": i, "backend": "bias_sweep", **c}); i += 1
    for c in grad_sweep_cases():
        cases.append({"i": i, "backend": "grad_sweep", **c}); i += 1
    for c in lodquery_cases():
        cases.append({"i": i, "backend": "lodquery", **c}); i += 1
    for c in cube_faceid_cases():
        cases.append({"i": i, "backend": "cube_faceid", **c}); i += 1
    for c in cube_grad_cases():
        cases.append({"i": i, "backend": "cube_grad", **c}); i += 1
    for c in regsplice_bias_cases():
        cases.append({"i": i, "backend": "regsplice_bias", **c}); i += 1
    return cases


if __name__ == "__main__":
    cs = full_case_list()
    from collections import Counter
    counts = Counter(c["backend"] for c in cs)
    print(f"total cases: {len(cs)}")
    for b in BACKENDS:
        print(f"  {b}: {counts[b]}")
