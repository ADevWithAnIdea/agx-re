"""EXP-0123 frozen case matrix -- the single source of truth for cases.

Every case is {id, family, kind, params}. `family` groups cases for the
RESULTS/limit table; `kind` selects which run.py handler builds & executes
the case; `params` are the exact, deterministic inputs. This module is
imported (never re-derived) by genkernels.py, run.py, and verify.py, so the
matrix a given commit executes is always the matrix that gets graded.

Values here were chosen from real exploratory hardware probing performed
before freezing this matrix (see PRE_REGISTRATION.md and RESULTS.md section
0) -- boundaries are exact numbers observed on this M4, not textbook
constants.
"""

MATRIX = []


def _add(case_id, family, kind, params):
    MATRIX.append({"id": case_id, "family": family, "kind": kind, "params": params})


# ---------------------------------------------------------------- line_rule
for cid, x0, y0, x1, y1, w, h in [
    ("line_horiz", 1.0, 4.5, 7.0, 4.5, 8, 8),
    ("line_vert", 4.5, 1.0, 4.5, 7.0, 8, 8),
    ("line_diag45", 1.0, 1.0, 7.0, 7.0, 8, 8),
    ("line_shallow", 0.5, 0.5, 7.5, 3.5, 8, 8),
    ("line_tie_exact", 1.0, 4.0, 7.0, 4.0, 8, 8),
    ("line_tie_below", 1.0, 3.99, 7.0, 3.99, 8, 8),
    ("line_tie_above", 1.0, 4.01, 7.0, 4.01, 8, 8),
    ("line_degenerate", 4.0, 4.0, 4.0, 4.0, 8, 8),
]:
    _add(cid, "line_rule", "render_grid", {"x0": x0, "y0": y0, "x1": x1, "y1": y1,
                                            "width": w, "height": h, "topology": "line"})

# ------------------------------------------------------------- point_rounding
for sz in [0.5, 0.9, 1.0, 1.1, 1.4, 1.5, 1.6, 1.9, 2.0, 2.1, 2.4, 2.5, 2.6, 2.9, 3.0, 3.5]:
    _add(f"point_sz_{sz}", "point_rounding", "render_point_centered",
         {"size": sz, "width": 32, "height": 32, "cx": 16.5, "cy": 16.5})

# ------------------------------------------------------------ polygon_fillmode
_add("fillmode_fill", "polygon_fillmode", "render_fillmode",
     {"fill_mode": "fill", "topology": "triangle", "width": 16, "height": 16})
_add("fillmode_lines", "polygon_fillmode", "render_fillmode",
     {"fill_mode": "lines", "topology": "triangle", "width": 16, "height": 16})
_add("fillmode_lines_on_lines", "polygon_fillmode", "render_fillmode",
     {"fill_mode": "lines", "topology": "line", "width": 16, "height": 16})

# --------------------------------------------------------- wide_line_negative
_add("wideline_horiz_baseline", "wide_line_negative", "render_grid",
     {"x0": 1.0, "y0": 8.5, "x1": 15.0, "y1": 8.5, "width": 16, "height": 16, "topology": "line"})
_add("wideline_diag_baseline", "wide_line_negative", "render_grid",
     {"x0": 1.0, "y0": 1.0, "x1": 15.0, "y1": 15.0, "width": 16, "height": 16, "topology": "line"})

# ---------------------------------------------------------- depth_clip_clamp
for mode in ["clip", "clamp"]:
    for label, z in [("far", 1.5), ("near", -0.5), ("atone", 1.0), ("atzero", 0.0)]:
        _add(f"depthclip_{mode}_{label}", "depth_clip_clamp", "render_depthclip",
             {"depth_clip_mode": mode, "z": z, "width": 8, "height": 8})

# --------------------------------------------------------- conservative_raster
for corner, (x0, y0, x1, y1, x2, y2) in [
    ("tl", (4.0, 4.0, 4.2, 4.0, 4.0, 4.2)),
    ("tr", (5.0, 4.0, 5.0, 4.2, 4.8, 4.0)),
    ("bl", (4.0, 5.0, 4.2, 5.0, 4.0, 4.8)),
    ("br", (5.0, 5.0, 4.8, 5.0, 5.0, 4.8)),
]:
    _add(f"consv_{corner}", "conservative_raster", "render_subpixel_tri",
         {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "width": 8, "height": 8})

# ---------------------------------------------------------- coverage_earlylate
for a2c in [True, False]:
    for alpha in [0, 1]:
        for samples in ([4] if (a2c and alpha == 0) else [1]):
            _add(f"cov_a2c{int(a2c)}_alpha{alpha}_ms{samples}", "coverage_earlylate", "render_coverage",
                 {"alpha_to_coverage": a2c, "alpha": alpha, "sample_count": samples,
                  "width": 4, "height": 4})

# ------------------------------------------------------------ limit_attachments
_add("attach_n8", "limit_attachments", "multiattach", {"n": 8, "width": 4, "height": 4})
_add("attach_n9", "limit_attachments", "multiattach", {"n": 9, "width": 4, "height": 4})

# -------------------------------------------------------------- limit_viewports
for n in [1, 16, 17, 20, 21]:
    _add(f"vp_n{n}", "limit_viewports", "viewport_functional", {"n": n})

# ------------------------------------------------------------------- limit_tex
_add("tex2d_16384", "limit_tex", "texcreate", {"type": "2d", "width": 16384, "height": 4})
_add("tex2d_16385", "limit_tex", "texcreate", {"type": "2d", "width": 16385, "height": 4})
_add("texcube_16384", "limit_tex", "texcreate", {"type": "cube", "width": 16384, "height": 16384})
_add("texcube_16385", "limit_tex", "texcreate", {"type": "cube", "width": 16385, "height": 16385})
_add("tex3d_2048", "limit_tex", "texcreate", {"type": "3d", "width": 2048, "height": 4, "depth": 4})
_add("tex3d_2049", "limit_tex", "texcreate", {"type": "3d", "width": 2049, "height": 4, "depth": 4})
_add("texarr_2048", "limit_tex", "texcreate", {"type": "2d_array", "width": 4, "height": 4, "depth": 2048})
_add("texarr_2049", "limit_tex", "texcreate", {"type": "2d_array", "width": 4, "height": 4, "depth": 2049})
_add("mip_16384_15", "limit_tex", "texcreate", {"type": "2d", "width": 16384, "height": 16384, "mips": 15})
_add("mip_16384_16", "limit_tex", "texcreate", {"type": "2d", "width": 16384, "height": 16384, "mips": 16})
_add("mip_64_7", "limit_tex", "texcreate", {"type": "2d", "width": 64, "height": 64, "mips": 7})
_add("mip_64_8", "limit_tex", "texcreate", {"type": "2d", "width": 64, "height": 64, "mips": 8})

# ---------------------------------------------------------- limit_bufferindex
for idx in [0, 30, 31]:
    _add(f"bufidx_{idx}", "limit_bufferindex", "bufferindex_compile", {"index": idx})

# ----------------------------------------------------------- limit_textureindex
for idx in [0, 127, 128]:
    _add(f"texidx_{idx}", "limit_textureindex", "texindex_compile", {"index": idx})

# ------------------------------------------------------------ limit_bytesconst
for length in [4095, 4096, 4097, 32752, 32753, 65536]:
    _add(f"bytesconst_{length}", "limit_bytesconst", "bytesconst", {"length": length})

# ------------------------------------------------------------ limit_bufferalign
for off in [0, 1, 2, 3, 4, 15, 17]:
    _add(f"bufalign_{off}", "limit_bufferalign", "bufferalign", {"offset": off})

# ---------------------------------------------------------- limit_threadgroup
for tg in [1024, 1025, 2048]:
    _add(f"tgsize_{tg}", "limit_threadgroup", "compute_threadgroup", {"tg": tg})

# --------------------------------------------------------- limit_tgmem_dynamic
for m in [32768, 65536, 131072]:
    _add(f"tgmem_{m}", "limit_tgmem_dynamic", "compute_tgmem", {"bytes": m})

# --------------------------------------------------------------- simd_width
for tg in [32, 64]:
    _add(f"simdwidth_tg{tg}", "simd_width", "compute_simdwidth", {"tg": tg})

# ----------------------------------------------------------- simd_shuffle_oob
for src in [0, 31, 32, 40, 63, 64, 100]:
    _add(f"shuffle_src{src}", "simd_shuffle_oob", "compute_simdshuffle", {"src": src})

TOTAL = len(MATRIX)
IDS = [c["id"] for c in MATRIX]


def case_order_sensitive_keys(case):
    """No family in this experiment relies on cross-case ordering or hidden
    global state; every case is a fresh, independent process. Kept for
    schema/verify symmetry with sibling experiments' standing-gate shape."""
    return set()


if __name__ == "__main__":
    print(f"TOTAL={TOTAL}")
    from collections import Counter
    for fam, n in Counter(c["family"] for c in MATRIX).most_common():
        print(f"  {fam}: {n}")
