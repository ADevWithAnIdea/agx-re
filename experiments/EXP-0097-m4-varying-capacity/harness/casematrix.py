"""EXP-0097 frozen case matrix (GLIO-A01 varying/clip-cull capacity + GLPRE-A03
pre-raster special-output boundary behavior). Imported by run.py (executor)
and verify.py (selftest/seqtest). Pure data construction -- no device or
filesystem access -- safe in any tree state (selftest requirement).

Frozen boundary values below (124-component varying cap, 8-plane clip cap,
511px point-size clamp, clamp-to-layer/viewport-0 on OOB array index,
first-vertex provoking convention) were located during build-time interactive
probing recorded in PRE_REGISTRATION.md "Build-time findings" BEFORE this
matrix was frozen -- the matrix exists to independently re-confirm those
exact points across two full official capture runs, not to (re)discover them.
"""

WCOMP = {"float": 1, "float2": 2, "float3": 3, "float4": 4, "half": 1}

# ---------------------------------------------------------------------------
# Family: vary_scalar -- GLIO-A01 primary capacity boundary, per width.
# (width, N declared==used) -- total_scalars = N * WCOMP[width].
# Boundary-focused: well-under, mid, and the 122..127 tight window per width,
# expressed in each width's own N so widths that can't hit 124 exactly
# (float2/float3) show where their own granularity actually lands.
# ---------------------------------------------------------------------------
VARY_SCALAR_POINTS = {
    "float":  [1, 8, 60, 100, 116, 120, 122, 123, 124, 125, 126, 127, 128, 132, 200],
    "half":   [1, 60, 116, 120, 123, 124, 125, 126, 127, 132],
    "float2": [1, 30, 50, 60, 61, 62, 63, 64, 66],
    "float3": [1, 20, 39, 40, 41, 42, 43, 44],
    "float4": [1, 4, 8, 28, 29, 30, 31, 32, 33, 40],
}

# expect_ok(total_scalars): the frozen hypothesis, established at build time:
# legal iff total user-varying scalar components (post-link "used" count) <= 124.
def expect_vary_ok(total_scalars):
    return total_scalars <= 124


# ---------------------------------------------------------------------------
# Family: vary_dce -- declared-vs-used (dead-code-elimination sensitivity).
# (declared, used)
# ---------------------------------------------------------------------------
VARY_DCE_POINTS = [
    (10, 10),      # trivial control
    (124, 124),    # exact boundary control, declared==used
    (150, 124),    # declared > limit, used == limit -> expect OK (DCE saves it)
    (150, 125),    # declared > limit, used 1-over -> expect FAIL
    (200, 200),    # declared == used, both over -> expect FAIL
    (500, 10),     # declared wildly over, used tiny -> expect OK
]


# ---------------------------------------------------------------------------
# Family: clip_sweep -- GLIO-A01 clip-distance capacity, 1-unit granularity
# through and past the boundary, plus coarse high points.
# ---------------------------------------------------------------------------
CLIP_SWEEP_POINTS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 16, 64, 256]


def expect_clip_ok(n):
    return n <= 8


# ---------------------------------------------------------------------------
# Family: vary_clip_combo -- independent-budget test (GLIO-A01).
# (used_varyings, clip_n)
# ---------------------------------------------------------------------------
VARY_CLIP_COMBO_POINTS = [
    (0, 8),      # clip alone at its max
    (116, 8),    # both comfortably under
    (124, 8),    # BOTH simultaneously at their individual max -> tests independence
    (124, 9),    # varying at max, clip 1-over -> expect FAIL (clip's own limit)
    (125, 0),    # varying 1-over, no clip -> expect FAIL (varying's own limit)
]


# ---------------------------------------------------------------------------
# Family: position_special -- GLPRE-A03 NaN/Inf/signed-zero clip-space tests.
# (name, component, expr, expect_full_fill)  -- expect_full_fill is the frozen
# build-time-probed hypothesis (True=16/16 px filled, False=discarded/partial,
# recorded exactly either way -- verdict is PASS iff the observed fill state
# matches the *category* [full/none/partial] recorded at build time, see
# POSITION_EXPECT_CATEGORY below).
# ---------------------------------------------------------------------------
POSITION_SPECIAL_CASES = [
    ("baseline", None, None, "full"),
    ("x_nan", "x", "0.0/0.0", "none"),
    ("x_posinf", "x", "1.0/0.0", "none"),
    ("x_neginf", "x", "-1.0/0.0", "full"),
    ("y_nan", "y", "0.0/0.0", "none"),
    ("y_posinf", "y", "1.0/0.0", "none"),
    ("y_neginf", "y", "-1.0/0.0", "full"),
    ("z_nan", "z", "0.0/0.0", "none"),
    ("w_nan", "w", "0.0/0.0", "none"),
    ("w_poszero", "w", "0.0", "full"),
    ("w_negzero", "w", "-0.0", "full"),
    ("w_posinf", "w", "1.0/0.0", "partial"),
    ("w_neginf", "w", "-1.0/0.0", "none"),
    ("w_negone", "w", "-1.0", "partial"),
]


# ---------------------------------------------------------------------------
# Family: point_size -- GLPRE-A03 (name, expr, expect_category).
# expect_category in {"discard","clamp511","scale","anomalous"}: the frozen
# build-time-probed classification. "scale" cases additionally freeze the
# exact expected footprint side length (size==sqrt(count)) for the PASS check.
# ---------------------------------------------------------------------------
POINT_SIZE_CASES = [
    ("zero", "0.0", "discard", None),
    ("neg_tiny", "-0.001", "discard", None),
    ("neg_huge", "-1.0e8", "discard", None),
    ("neg1", "-1.0", "anomalous", None),
    ("neg5", "-5.0", "anomalous", None),
    ("neg50", "-50.0", "anomalous", None),
    ("ctrl4", "4.0", "scale", 4),
    ("ctrl16", "16.0", "scale", 16),
    ("ctrl64", "64.0", "scale", 64),
    ("ctrl128", "128.0", "scale", 128),
    ("ctrl256", "256.0", "scale", 256),
    ("b510", "510.0", "scale", 510),
    ("b511", "511.0", "scale", 511),
    ("b512", "512.0", "clamp511", None),
    ("b513", "513.0", "clamp511", None),
    ("big1000", "1000.0", "clamp511", None),
    ("huge1e8", "1.0e8", "clamp511", None),
    ("nan", "0.0/0.0", "clamp511", None),
    ("posinf", "1.0/0.0", "clamp511", None),
    ("neginf", "-1.0/0.0", "discard", None),
]
POINT_TARGET_WH = 600  # px, matches build-time probing (headroom past the 511 clamp)


# ---------------------------------------------------------------------------
# Family: layer_oob -- GLPRE-A03 render_target_array_index OOB (layer_count, requested).
# expect_landing: which layer index actually receives the fragment (frozen
# build-time finding: clamp-to-ZERO on any out-of-range index).
# ---------------------------------------------------------------------------
LAYER_OOB_POINTS = [
    (4, 0, 0), (4, 1, 1), (4, 2, 2), (4, 3, 3),          # in-range controls
    (4, 4, 0), (4, 5, 0), (4, 8, 0), (4, 255, 0), (4, 4294967295, 0),
    (8, 7, 7),                                            # in-range control at a different N
    (8, 8, 0), (8, 9, 0), (8, 255, 0),
]

# ---------------------------------------------------------------------------
# Family: viewport_oob -- GLPRE-A03 viewport_array_index OOB, same clamp model.
# ---------------------------------------------------------------------------
VIEWPORT_OOB_POINTS = [
    (4, 0, 0), (4, 1, 1), (4, 2, 2), (4, 3, 3),
    (4, 4, 0), (4, 5, 0), (4, 255, 0), (4, 4294967295, 0),
]

# ---------------------------------------------------------------------------
# Family: provoking -- GLPRE-A03 provoking-vertex convention.
# ---------------------------------------------------------------------------
# (name, gen_topology, probe_topology, vcount, icount, width, height,
#  samples=[(x,y,expect_color_name)]) -- expect_color_name is the frozen
# build-time-probed hypothesis (first-vertex-of-primitive provoking convention).
PROVOKING_CASES = [
    ("list_direct", "list", "triangle", 3, 0, 4, 4, [(2, 2, "red")]),
    ("list_reversed_index", "list", "triangle", 3, 3, 4, 4, [(2, 2, "blue")]),
    ("strip_two_tri", "strip", "strip", 4, 0, 8, 4, [(1, 2, "red"), (5, 2, "green")]),
]


def build_matrix():
    cases = []

    def add(cid, family, kind, params):
        cases.append({"id": cid, "family": family, "kind": kind, "params": params})

    for width, ns in VARY_SCALAR_POINTS.items():
        wc = WCOMP[width]
        for n in ns:
            total = n * wc
            add(f"vary_{width}_n{n}", "vary_scalar", "capacity_compile",
                {"width": width, "n": n, "total_scalars": total,
                 "expect_ok": expect_vary_ok(total)})

    for declared, used in VARY_DCE_POINTS:
        total = used
        add(f"varydce_d{declared}_u{used}", "vary_dce", "capacity_compile",
            {"width": "float", "declared": declared, "used": used,
             "expect_ok": expect_vary_ok(total)})

    for n in CLIP_SWEEP_POINTS:
        add(f"clip_n{n}", "clip_sweep", "capacity_compile",
            {"n": n, "expect_ok": expect_clip_ok(n)})

    add("cull_distance_attr", "cull_negative", "capacity_compile", {"expect_ok": False})

    for used, clip_n in VARY_CLIP_COMBO_POINTS:
        add(f"combo_v{used}_c{clip_n}", "vary_clip_combo", "capacity_compile",
            {"used": used, "clip_n": clip_n,
             "expect_ok": expect_vary_ok(used) and expect_clip_ok(clip_n)})

    for name, comp, expr, cat in POSITION_SPECIAL_CASES:
        add(f"pos_{name}", "position_special", "render_fill",
            {"component": comp, "expr": expr, "expect_category": cat})

    for name, expr, cat, side in POINT_SIZE_CASES:
        add(f"point_{name}", "point_size", "render_point",
            {"expr": expr, "expect_category": cat, "expect_side": side,
             "wh": POINT_TARGET_WH})

    for layers, req, expect_landing in LAYER_OOB_POINTS:
        add(f"layer_L{layers}_v{req}", "layer_oob", "render_layer",
            {"layers": layers, "requested": req, "expect_landing": expect_landing})

    for vps, req, expect_landing in VIEWPORT_OOB_POINTS:
        add(f"viewport_V{vps}_v{req}", "viewport_oob", "render_viewport",
            {"viewports": vps, "requested": req, "expect_landing": expect_landing})

    for name, topo_gen, topo_probe, vcount, icount, width, height, samples in PROVOKING_CASES:
        add(f"prov_{name}", "provoking", "render_provoking",
            {"gen_topology": topo_gen, "probe_topology": topo_probe,
             "vcount": vcount, "icount": icount, "width": width, "height": height,
             "samples": samples})

    # vary_render_confirm: a small subset of in-budget capacity cases that go
    # all the way to a real draw + checksum readback, not just pipeline
    # creation -- proves the max-legal pipeline EXECUTES correctly (no silent
    # aliasing), not merely that it compiles.
    for width, n in [("float", 124), ("float4", 31), ("float", 8), ("float2", 62)]:
        wc = WCOMP[width]
        add(f"varyconfirm_{width}_n{n}", "vary_render_confirm", "render_checksum",
            {"width": width, "n": n, "total_scalars": n * wc})

    return cases


MATRIX = build_matrix()
TOTAL = len(MATRIX)
IDS = [c["id"] for c in MATRIX]


def case_order_sensitive_keys(case):
    """No family in this experiment has a legitimately racy/nondeterministic
    'observed' field: every case is a single-draw, single-readback,
    deterministic pipeline-creation-or-render test (standing gate (d) --
    nothing here is scheduling-order-sensitive). Returns the empty set for
    every case; kept as a function (not a constant) to match the shared
    cross-run-gate call signature used by verify.py."""
    return set()
