#!/usr/bin/env python3
"""EXP-0109 frozen case matrix. Imported by run.py and verify.py — the case
list here is the single source of truth for both execution and the
cross-run/self-test gates. Do not edit after CAPTURE_CONTRACT.json is frozen
(state PRE_GPU) without re-registering."""

# ---- vfetch_extract: structural VS attribute-fetch differential compile ----
VFETCH_FORMAT_CASES = [
    # (name, vertex_fn, format_raw_enum, format_label)
    ("vsfetch_format_float4",           "v_f4", 31, "Float4"),
    ("vsfetch_format_half4",            "v_h4", 27, "Half4"),
    ("vsfetch_format_uchar4norm",       "v_f4", 9,  "UChar4Normalized"),
    ("vsfetch_format_short4norm",       "v_f4", 24, "Short4Normalized"),
    ("vsfetch_format_int4",             "v_i4", 35, "Int4"),
    ("vsfetch_format_uint4",            "v_u4", 39, "UInt4"),
    ("vsfetch_format_int1010102norm",   "v_f4", 40, "Int1010102Normalized"),
]

VFETCH_LAYOUT_CASES = [
    # (name, stride, offset, step, rate)
    ("vsfetch_stride_32", 32, 0, "vertex", 1),
    ("vsfetch_stride_64", 64, 0, "vertex", 1),
    ("vsfetch_offset_0",  32, 0,  "vertex", 1),
    ("vsfetch_offset_16", 32, 16, "vertex", 1),
    ("vsfetch_step_vertex",   32, 0, "vertex",   1),
    ("vsfetch_step_instance", 32, 0, "instance", 1),
]

VFETCH_DIVISOR_CASES = [
    ("vsfetch_instance_rate1", 32, 0, "instance", 1),
    ("vsfetch_instance_rate2", 32, 0, "instance", 2),
]


def vfetch_extract_cases():
    out = []
    for name, vfn, fmt, label in VFETCH_FORMAT_CASES:
        out.append({"id": name, "family": "vsfetch_format", "backend": "vfetch_extract",
                    "params": {"vertex": vfn, "fragment": "f_pass", "format": fmt,
                               "format_label": label, "offset": 0, "stride": 32,
                               "step": "vertex", "rate": 1}})
    for name, stride, offset, step, rate in VFETCH_LAYOUT_CASES:
        out.append({"id": name, "family": "vsfetch_layout", "backend": "vfetch_extract",
                    "params": {"vertex": "v_f4", "fragment": "f_pass", "format": 31,
                               "format_label": "Float4", "offset": offset, "stride": stride,
                               "step": step, "rate": rate}})
    for name, stride, offset, step, rate in VFETCH_DIVISOR_CASES:
        out.append({"id": name, "family": "vsfetch_divisor", "backend": "vfetch_extract",
                    "params": {"vertex": "v_f4", "fragment": "f_pass", "format": 31,
                               "format_label": "Float4", "offset": offset, "stride": stride,
                               "step": step, "rate": rate}})
    return out


# ---- mrt_extract: structural fragment input/output differential compile ----
FSIN_INTERP_CASES = [
    ("fsin_interp_persp",       "v_persp",       "f_persp"),
    ("fsin_interp_nopersp",     "v_nopersp",     "f_nopersp"),
    ("fsin_interp_centroid_p",  "v_centroid_p",  "f_centroid_p"),
    ("fsin_interp_centroid_np", "v_centroid_np", "f_centroid_np"),
    ("fsin_interp_sample_p",    "v_sample_p",    "f_sample_p"),
    ("fsin_interp_sample_np",   "v_sample_np",   "f_sample_np"),
    ("fsin_interp_flat",        "v_flat",        "f_flat"),
]
FSIN_PULLMODEL_CASES = [
    ("fsin_pull_center",   "v_persp", "f_pullmodel_center"),
    ("fsin_pull_centroid", "v_persp", "f_pullmodel_centroid"),
    ("fsin_pull_sample",   "v_persp", "f_pullmodel_sample"),
    ("fsin_pull_offset",   "v_persp", "f_pullmodel_offset"),
]
FSOUT_MRT_CASES = [
    ("fsout_mrt_1", "v_common", "f_mrt1", 1),
    ("fsout_mrt_2", "v_common", "f_mrt2", 2),
    ("fsout_mrt_4", "v_common", "f_mrt4", 4),
]
FSOUT_DEPTH_CASES = [
    ("fsout_depth_any",     "f_depth_any"),
    ("fsout_depth_less",    "f_depth_less"),
    ("fsout_depth_greater", "f_depth_greater"),
]


def mrt_extract_cases():
    out = []
    for name, vfn, ffn in FSIN_INTERP_CASES:
        out.append({"id": name, "family": "fsin_interp", "backend": "mrt_extract",
                    "params": {"vertex": vfn, "fragment": ffn, "natt": 1}})
    for name, vfn, ffn in FSIN_PULLMODEL_CASES:
        out.append({"id": name, "family": "fsin_pullmodel", "backend": "mrt_extract",
                    "params": {"vertex": vfn, "fragment": ffn, "natt": 1}})
    out.append({"id": "fsin_barycentric", "family": "fsin_barycentric", "backend": "mrt_extract",
                "params": {"vertex": "v_persp", "fragment": "f_barycentric", "natt": 1}})
    out.append({"id": "fsin_primid", "family": "fsin_primid", "backend": "mrt_extract",
                "params": {"vertex": "v_common", "fragment": "f_primid", "natt": 1}})
    for name, vfn, ffn, natt in FSOUT_MRT_CASES:
        out.append({"id": name, "family": "fsout_mrt", "backend": "mrt_extract",
                    "params": {"vertex": vfn, "fragment": ffn, "natt": natt}})
    out.append({"id": "fsout_dualsource_struct", "family": "fsout_dualsource", "backend": "mrt_extract",
                "params": {"vertex": "v_common", "fragment": "f_dualsource", "natt": 1, "dualsource": True}})
    for name, ffn in FSOUT_DEPTH_CASES:
        out.append({"id": name, "family": "fsout_depth", "backend": "mrt_extract",
                    "params": {"vertex": "v_common", "fragment": ffn, "natt": 1, "depthfmt": 252}})
    out.append({"id": "fsout_stencil_struct", "family": "fsout_stencil", "backend": "mrt_extract",
                "params": {"vertex": "v_common", "fragment": "f_stencil_out", "natt": 1}})
    out.append({"id": "fsout_bogus_negative_control", "family": "fsout_stencil", "backend": "mrt_extract",
                "params": {"vertex": "v_common", "fragment": "f_bogus_negative", "natt": 1,
                           "defines": ["EXP0109_TRY_BOGUS_ATTR=1"], "expect_fail": True}})
    return out


# ---- shdump_struct: preamble / call-ABI structural compute probes ----------
def shdump_struct_cases():
    return [
        {"id": "cs_preamble_with_constant", "family": "cs_preamble", "backend": "shdump_struct",
         "params": {"function": "cs_with_constant"}},
        {"id": "cs_preamble_no_constant", "family": "cs_preamble", "backend": "shdump_struct",
         "params": {"function": "cs_no_constant"}},
        {"id": "linkage_call_abi", "family": "linkage_call_abi", "backend": "shdump_struct",
         "params": {"function": "cs_call_probe"}},
    ]


# ---- render_probe: HW-PROBE real draws + readback --------------------------
def render_probe_cases():
    out = []
    vsfetch_hw = [
        ("vsfetch_hw_inrange",          dict(nvert=6, ninst=1, basev=0, basei=0, oobidx=0)),
        ("vsfetch_hw_oob",              dict(nvert=6, ninst=1, basev=0, basei=0, oobidx=1)),
        ("vsfetch_hw_instancing_base",  dict(nvert=4, ninst=3, basev=2, basei=10, oobidx=0)),
        ("vsfetch_hw_oob_large_base",   dict(nvert=4, ninst=1, basev=1000000, basei=0, oobidx=1)),
    ]
    for name, p in vsfetch_hw:
        pp = dict(p); pp["format"] = 9
        out.append({"id": name, "family": "vsfetch_hw", "backend": "render_probe",
                    "params": {"mode": "vsfetch", **pp}})

    out.append({"id": "frontfacing_hw", "family": "fsin_frontfacing", "backend": "render_probe",
                "params": {"mode": "frontfacing"}})

    for natt in (1, 2, 4):
        out.append({"id": f"mrt_hw_{natt}", "family": "fsout_mrt_hw", "backend": "render_probe",
                    "params": {"mode": "mrt", "natt": natt}})

    out.append({"id": "dualsource_hw", "family": "fsout_dualsource_hw", "backend": "render_probe",
                "params": {"mode": "dualsource"}})

    depth_hw = [
        ("depth_hw_any_250",     dict(dfunc="f_depth_any", dval=250)),
        ("depth_hw_any_750",     dict(dfunc="f_depth_any", dval=750)),
        ("depth_hw_less_250",    dict(dfunc="f_depth_less", dval=250)),
        ("depth_hw_greater_250", dict(dfunc="f_depth_greater", dval=250)),
    ]
    for name, p in depth_hw:
        out.append({"id": name, "family": "fsout_depth_hw", "backend": "render_probe",
                    "params": {"mode": "depth", **p}})

    stencil_hw = [
        ("stencil_hw_sval5",         dict(sval=5, sfunc="f_stencil_out")),
        ("stencil_hw_sval9",         dict(sval=9, sfunc="f_stencil_out")),
        ("stencil_hw_control_mrt1",  dict(sval=5, sfunc="f_mrt1")),
    ]
    for name, p in stencil_hw:
        out.append({"id": name, "family": "fsout_stencil_hw", "backend": "render_probe",
                    "params": {"mode": "stencil", **p}})
    return out


def compute_probe_cases():
    return [
        {"id": "cstgmem_hw_sweep", "family": "cs_tgmem_dynamic", "backend": "compute_probe",
         "params": {"sizes": [1, 2, 4, 8, 16, 32, 64]}},
    ]


def full_case_list():
    return (vfetch_extract_cases() + mrt_extract_cases() + shdump_struct_cases()
            + render_probe_cases() + compute_probe_cases())


if __name__ == "__main__":
    cases = full_case_list()
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case id"
    print(f"total cases: {len(cases)}")
    from collections import Counter
    for backend, n in Counter(c["backend"] for c in cases).items():
        print(f"  backend {backend}: {n}")
    for family, n in Counter(c["family"] for c in cases).items():
        print(f"  family {family}: {n}")
