"""EXP-0117 frozen case matrix. Single source of truth for run.py/verify.py.

Every case is authored/CLI-parameterized (never re-uses a captured Apple
template). Fatal-process-abort-inducing cases (deliberately out-of-range API
values that Metal enforces via a fatal validation assertion rather than a
catchable NSError -- discovered during harness development, see PROGRESS.md)
are placed at the END of the list so a hard process abort cannot leave
collateral "innocent victim" GPU-queue noise on any case that runs after it
within the same run.py invocation.
"""

BLEND = "kernels/blend.metal"
FSORDER = "kernels/fsorder.metal"
BARY = "kernels/barycentric.metal"
MSAADIFF = "kernels/msaa_diff.metal"
SAMPLEMASK = "kernels/samplemask.metal"
STENCIL = "kernels/stencil.metal"
STENCIL_I32 = "kernels/stencil_i32_negative.metal"
CALLABI = "kernels/callabi.metal"
CALLCHAIN = "kernels/callchain.metal"

# MTLBlendFactor (public MTLRenderPipeline.h, macOS 26.5 SDK)
FACTORS = {
    "Zero": 0, "One": 1, "SourceColor": 2, "OneMinusSourceColor": 3,
    "SourceAlpha": 4, "OneMinusSourceAlpha": 5, "DestinationColor": 6,
    "OneMinusDestinationColor": 7, "DestinationAlpha": 8, "OneMinusDestinationAlpha": 9,
    "SourceAlphaSaturated": 10, "BlendColor": 11, "OneMinusBlendColor": 12,
    "BlendAlpha": 13, "OneMinusBlendAlpha": 14, "Source1Color": 15,
    "OneMinusSource1Color": 16, "Source1Alpha": 17, "OneMinusSource1Alpha": 18,
}
# MTLBlendOperation
OPS = {"Add": 0, "Subtract": 1, "ReverseSubtract": 2, "Min": 3, "Max": 4}

SRC = (0.7, 0.4, 0.2, 0.9)
DST = (0.3, 0.6, 0.8, 0.1)
CONST = (0.25, 0.75, 0.5, 0.6)


def _blendrender(case_id, family, **kw):
    p = dict(mode="blendrender", w=2, h=2, colorformat=125,
             srcr=SRC[0], srcg=SRC[1], srcb=SRC[2], srca=SRC[3],
             dstr=DST[0], dstg=DST[1], dstb=DST[2], dsta=DST[3],
             sr=1, dr=0, sa=1, da=0, rgbop=0, aop=0, mask=15,
             constr=CONST[0], constg=CONST[1], constb=CONST[2], consta=CONST[3],
             blendenabled=1)
    p.update(kw)
    return {"id": case_id, "family": family, "backend": "render", "source": BLEND, "params": p}


def _cases():
    cases = []

    # ---- blend factor sweep: factor as SOURCE (rgb+alpha slots), dst=Zero ----
    # Source1*-family factors need a DUAL-SOURCE fragment function (Metal
    # rejects the pipeline otherwise -- own-compiler diagnostic, see
    # PROGRESS.md); SRC1 is a fixed, distinct, non-neutral color.
    SRC1 = (0.5, 0.6, 0.7, 0.8)
    DUALSRC_FACTORS = {"Source1Color", "OneMinusSource1Color", "Source1Alpha", "OneMinusSource1Alpha"}
    for name, val in FACTORS.items():
        extra = {}
        if name in DUALSRC_FACTORS:
            extra = {"fragment": "f_solid_dualsrc", "src1r": SRC1[0], "src1g": SRC1[1],
                      "src1b": SRC1[2], "src1a": SRC1[3]}
        cases.append(_blendrender(f"blendfac_src_{name}", "blend_factor",
                                   case=f"src_{name}", sr=val, dr=0, sa=val, da=0, rgbop=0, aop=0, **extra))
    # ---- blend factor sweep: factor as DESTINATION (4 representative values) --
    for name in ("Zero", "One", "SourceColor", "DestinationColor"):
        val = FACTORS[name]
        cases.append(_blendrender(f"blendfac_dst_{name}", "blend_factor",
                                   case=f"dst_{name}", sr=0, dr=val, sa=0, da=val, rgbop=0, aop=0))
    # ---- hole / first-invalid: Unspecialized(19) and one past it (20) --------
    cases.append(_blendrender("blendfac_src_Unspecialized19", "blend_factor",
                               case="src_unspec19", sr=19, dr=0, sa=19, da=0, rgbop=0, aop=0))
    cases.append(_blendrender("blendfac_src_invalid20", "blend_factor",
                               case="src_invalid20", sr=20, dr=0, sa=20, da=0, rgbop=0, aop=0))
    # dst-role Unspecialized(19), isolated with src=One so the dst-factor's
    # true contribution is visible (result==src iff dst-factor behaves as Zero).
    cases.append(_blendrender("blendfac_dst_Unspecialized19", "blend_factor",
                               case="dst_unspec19", sr=1, dr=19, sa=1, da=19, rgbop=0, aop=0))

    # ---- blend operation sweep (src=One,dst=One isolates the op itself) -----
    for name, val in OPS.items():
        cases.append(_blendrender(f"blendop_{name}", "blend_op",
                                   case=f"op_{name}", sr=1, dr=1, sa=1, da=1, rgbop=val, aop=val))
    cases.append(_blendrender("blendop_Unspecialized5", "blend_op",
                               case="op_unspec5", sr=1, dr=1, sa=1, da=1, rgbop=5, aop=5))
    cases.append(_blendrender("blendop_invalid6", "blend_op",
                               case="op_invalid6", sr=1, dr=1, sa=1, da=1, rgbop=6, aop=6))
    cases.append(_blendrender("blendop_rgb_alpha_independent", "blend_op",
                               case="op_rgb_add_alpha_sub", sr=1, dr=1, sa=1, da=1, rgbop=0, aop=1))

    # ---- write mask sweep -----------------------------------------------------
    for name, val in {"None": 0x0, "Alpha": 0x1, "Blue": 0x2, "Green": 0x4, "Red": 0x8,
                       "All": 0xf, "RedAlpha": 0x9}.items():
        cases.append(_blendrender(f"writemask_{name}", "writemask",
                                   case=f"mask_{name}", blendenabled=0, sr=1, dr=0, sa=1, da=0, mask=val))
    cases.append(_blendrender("writemask_Unspecialized16", "writemask",
                               case="mask_unspec16", blendenabled=0, sr=1, dr=0, sa=1, da=0, mask=0x10))
    cases.append(_blendrender("writemask_invalid32", "writemask",
                               case="mask_invalid32", blendenabled=0, sr=1, dr=0, sa=1, da=0, mask=0x20))

    # ---- blend constant sweep (factor=BlendColor, neutral src=(1,1,1,1)) ----
    for name, cv in {"min0": (0, 0, 0, 0), "max1": (1, 1, 1, 1),
                      "below0": (-0.5, -0.5, -0.5, -0.5), "above1": (1.5, 1.5, 1.5, 1.5)}.items():
        cases.append(_blendrender(f"blendconst_{name}", "blend_constant",
                                   case=f"const_{name}", srcr=1, srcg=1, srcb=1, srca=1,
                                   sr=FACTORS["BlendColor"], dr=0, sa=FACTORS["BlendAlpha"], da=0,
                                   rgbop=0, aop=0, constr=cv[0], constg=cv[1], constb=cv[2], consta=cv[3]))

    # ---- format spot checks (RGBA16Float, RGBA8Unorm identity blend) --------
    cases.append(_blendrender("blendfmt_rgba16f", "blend_format",
                               case="fmt_rgba16f", colorformat=115, sr=1, dr=0, sa=1, da=0))
    cases.append(_blendrender("blendfmt_rgba8unorm", "blend_format",
                               case="fmt_rgba8unorm", colorformat=70, sr=1, dr=0, sa=1, da=0))
    # fmtreject: enabling blending on a non-blendable INTEGER format via struct_extract
    cases.append({"id": "fmtreject_r32uint_blend_off", "family": "blend_format", "backend": "struct_extract",
                  "source": BLEND, "params": {"vertex": "v_full", "fragment": "f_logic_copy",
                  "colorformat": 53, "blendenabled": 0}})
    cases.append({"id": "fmtreject_r32uint_blend_on", "family": "blend_format", "backend": "struct_extract",
                  "source": BLEND, "params": {"vertex": "v_full", "fragment": "f_logic_copy",
                  "colorformat": 53, "blendenabled": 1}})

    # ---- sRGB store + blend interaction --------------------------------------
    for name, fmt, blend in (("store_srgb", 71, 0), ("store_unorm", 70, 0),
                              ("blend_srgb", 71, 1), ("blend_unorm", 70, 1)):
        p = dict(mode="srgb", w=2, h=2, colorformat=fmt, blendenabled=blend,
                 srcr=0.5, srcg=0.5, srcb=0.5, srca=1.0,
                 dstr=0.2, dstg=0.2, dstb=0.2, dsta=1.0,
                 sr=1, dr=1 if blend else 0, sa=1, da=1 if blend else 0)
        cases.append({"id": f"srgb_{name}", "family": "srgb", "backend": "render", "source": BLEND,
                      "params": {**p, "case": name}})

    # ---- alpha-to-coverage sweep (N=4) + alpha-to-one (N=1) ------------------
    for a in (0.0, 0.25, 0.5, 0.75, 1.0):
        cases.append({"id": f"a2c_alpha_{a}", "family": "a2c", "backend": "render", "source": BLEND,
                      "params": {"mode": "a2c", "case": f"a2c_{a}", "w": 1, "h": 1, "samples": 4,
                                 "srcr": 1, "srcg": 1, "srcb": 1, "srca": a, "a2c": 1, "a2o": 0}})
    for a2o in (0, 1):
        cases.append({"id": f"a2o_{a2o}", "family": "a2c", "backend": "render", "source": BLEND,
                      "params": {"mode": "a2c", "case": f"a2o_{a2o}", "w": 1, "h": 1, "samples": 1,
                                 "srcr": 0.2, "srcg": 0.3, "srcb": 0.4, "srca": 0.3, "a2c": 0, "a2o": a2o}})

    # ---- NaN / Inf propagation through the blend equation --------------------
    QNAN = 0x7FC00000
    PINF = 0x7F800000
    NINF = 0xFF800000
    for name, bits, blend, dstv in (
        ("qnan_passthrough", QNAN, 1, (0, 0, 0, 0)),
        ("posinf_passthrough", PINF, 1, (0, 0, 0, 0)),
        ("neginf_passthrough", NINF, 1, (0, 0, 0, 0)),
        ("qnan_plus_finite", QNAN, 1, (2.0, 0, 0, 0)),
    ):
        p = {"mode": "nan", "case": name, "w": 2, "h": 2, "colorformat": 125,
             "uval": bits, "blendenabled": 1, "sr": 1, "dr": 1, "sa": 1, "da": 1,
             "dstr": dstv[0], "dstg": dstv[1], "dstb": dstv[2], "dsta": dstv[3]}
        cases.append({"id": f"nan_{name}", "family": "nan", "backend": "render", "source": BLEND, "params": p})

    # ---- programmable-blend epilog: logic ops (tile_read + ALU) --------------
    for name, fn, src, dst in (
        ("and_a", "f_logic_and", 0xF0F0F0F0, 0xFF00FF00),
        ("and_identity", "f_logic_and", 0x00000000, 0xFFFFFFFF),
        ("or_a", "f_logic_or", 0x0F0F0F0F, 0xF0F0F0F0),
        ("xor_a", "f_logic_xor", 0xAAAAAAAA, 0x55555555),
        ("xor_selfcancel", "f_logic_xor", 0xFFFFFFFF, 0xFFFFFFFF),
        ("inv_zero", "f_logic_inv", 0, 0x00000000),
        ("inv_allones", "f_logic_inv", 0, 0xFFFFFFFF),
        ("copy_ignores_dst", "f_logic_copy", 0x12345678, 0xAAAAAAAA),
    ):
        cases.append({"id": f"logic_{name}", "family": "logic_epilog", "backend": "render", "source": BLEND,
                      "params": {"mode": "logic", "case": name, "fragment": fn, "uval": src, "uval2": dst}})

    # ---- structural: does blendingEnabled alone add tile_read to _agc.main? -
    for name, blend, sr, dr in (
        ("off", 0, 1, 0), ("on_srconly", 1, 1, 0), ("on_dstonly", 1, 0, 1), ("on_both", 1, 2, 6),
    ):
        cases.append({"id": f"blendstruct_{name}", "family": "blend_struct", "backend": "struct_extract",
                      "source": BLEND, "params": {"vertex": "v_full", "fragment": "f_solid",
                      "colorformat": 125, "blendenabled": blend, "sr": sr, "dr": dr, "sa": sr, "da": dr}})

    # ---- MRT ceiling: 1..8 (HW-rendered), API index ceiling 1/8/9/10 --------
    for n in range(1, 9):
        cases.append({"id": f"mrtceil_{n}", "family": "mrt_ceiling", "backend": "render", "source": BLEND,
                      "params": {"mode": "mrtceil", "case": f"n{n}", "natt": n}})
    for n in (1, 8, 9, 10):
        cases.append({"id": f"mrtapiceil_{n}", "family": "mrt_ceiling", "backend": "render", "source": BLEND,
                      "params": {"mode": "mrtapiceil", "case": f"api{n}", "natt": n}})

    # ---- FS output ordering ---------------------------------------------------
    cases.append({"id": "fsorder_struct_ab", "family": "fsorder", "backend": "struct_extract", "source": FSORDER,
                  "params": {"vertex": "v_half", "fragment": "f_order_ab", "colorformat": 70,
                             "blendenabled": 0, "depthformat": 252, "stencilformat": 253}})
    cases.append({"id": "fsorder_struct_ba", "family": "fsorder", "backend": "struct_extract", "source": FSORDER,
                  "params": {"vertex": "v_half", "fragment": "f_order_ba", "colorformat": 70,
                             "blendenabled": 0, "depthformat": 252, "stencilformat": 253}})
    cases.append({"id": "fsorder_render_cmp", "family": "fsorder", "backend": "render", "source": FSORDER,
                  "params": {"mode": "fsorder_cmp", "case": "cmp1", "w": 8, "h": 8,
                             "passdepth": 0.2, "faildepth": 0.9, "stencilref": 33}})
    cases.append({"id": "fsorder_suppress_keep_replace", "family": "fsorder", "backend": "render", "source": FSORDER,
                  "params": {"mode": "fsorder_suppress", "case": "kr", "w": 8, "h": 8,
                             "passdepth": 0.2, "faildepth": 0.9, "depthfailop": 0, "depthpassop": 2,
                             "stencilref": 111}})
    cases.append({"id": "fsorder_suppress_replace_keep", "family": "fsorder", "backend": "render", "source": FSORDER,
                  "params": {"mode": "fsorder_suppress", "case": "rk", "w": 8, "h": 8,
                             "passdepth": 0.2, "faildepth": 0.9, "depthfailop": 2, "depthpassop": 0,
                             "stencilref": 111}})

    # ---- barycentric / primitive_id -------------------------------------------
    cases.append({"id": "bary_values", "family": "bary_pid", "backend": "render", "source": BARY,
                  "params": {"mode": "bary", "case": "b1", "w": 64, "h": 64}})
    cases.append({"id": "pid_nonindexed", "family": "bary_pid", "backend": "render", "source": BARY,
                  "params": {"mode": "pid", "case": "p1", "w": 64, "h": 64}})
    cases.append({"id": "pid_indexed_shuffled", "family": "bary_pid", "backend": "render", "source": BARY,
                  "params": {"mode": "pid_indexed", "case": "p2", "w": 64, "h": 64}})
    cases.append({"id": "pid_instanced", "family": "bary_pid", "backend": "render", "source": BARY,
                  "params": {"mode": "pid_instanced", "case": "p3", "w": 64, "h": 64}})

    # ---- MSAA centroid vs sample differentiation ------------------------------
    cases.append({"id": "msaadiff_n4", "family": "msaa_diff", "backend": "render", "source": MSAADIFF,
                  "params": {"mode": "msaadiff", "case": "md1", "samples": 4}})

    # ---- sample_mask finite width ---------------------------------------------
    for mv in (0x0, 0x1, 0x3, 0x7, 0xF, 0x10, 0xFFFFFFFF):
        cases.append({"id": f"samplemask_n4_{mv:#x}", "family": "sample_mask", "backend": "render",
                      "source": SAMPLEMASK, "params": {"mode": "samplemask", "case": f"n4_{mv:#x}",
                      "samples": 4, "maskval": mv}})
    for mv in (0x0, 0x1, 0x3, 0x4, 0xFFFFFFFF):
        cases.append({"id": f"samplemask_n2_{mv:#x}", "family": "sample_mask", "backend": "render",
                      "source": SAMPLEMASK, "params": {"mode": "samplemask", "case": f"n2_{mv:#x}",
                      "samples": 2, "maskval": mv}})
    for mv in (0x0, 0x1):
        cases.append({"id": f"samplemask_n1_{mv:#x}", "family": "sample_mask", "backend": "render",
                      "source": SAMPLEMASK, "params": {"mode": "samplemask", "case": f"n1_{mv:#x}",
                      "samples": 1, "maskval": mv}})

    # ---- stencil overflow -------------------------------------------------------
    for v in (0, 1, 127, 254, 255, 256, 257, 511, 65535, 4294967295):
        cases.append({"id": f"stencilover_u32_{v}", "family": "stencil_overflow", "backend": "render",
                      "source": STENCIL, "params": {"mode": "stencilover", "case": f"u32_{v}",
                      "stype": "u32", "sval": v}})
    for v in (255, 300):
        cases.append({"id": f"stencilover_u16_{v}", "family": "stencil_overflow", "backend": "render",
                      "source": STENCIL, "params": {"mode": "stencilover", "case": f"u16_{v}",
                      "stype": "u16", "sval": v}})
    cases.append({"id": "stencilover_i32_negative_control", "family": "stencil_overflow", "backend": "render",
                  "source": STENCIL_I32, "params": {"mode": "stencilover", "case": "i32_neg1",
                  "stype": "i32", "sval": -1}})

    # ---- CALL-ABI structural byte decode ---------------------------------------
    for fn in ("k_single", "k_twosame", "k_twodiff", "k_threecalls", "k_far", "k_nested"):
        cases.append({"id": f"callabi_{fn}", "family": "call_abi", "backend": "shdump_call",
                      "source": CALLABI, "params": {"function": fn}})
    cases.append({"id": "callabi_k_nested_midfn", "family": "call_abi", "backend": "shdump_call",
                  "source": CALLABI, "params": {"function": "k_nested", "symbol": "l__ZL6mid_fnf"}})

    # ---- CALL-nesting depth (real execution + readback) -------------------------
    for d in (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128):
        cases.append({"id": f"calldepth_{d}", "family": "call_depth", "backend": "compute_run",
                      "source": CALLCHAIN, "params": {"function": f"k_depth{d}", "n": 4}})

    # ---- FATAL-ABORT-INDUCING CASES: kept last, see module docstring -----------
    # (mrtapiceil 9/10 and fmtreject blend-on are already placed above by
    #  construction order in this function's early sections -- Python append
    #  order is preserved, so they are NOT actually last. Re-sort explicitly.)
    # Confirmed-by-construction (see PROGRESS.md pilot log) fatal-abort cases:
    # invalid MTLBlendFactor/MTLBlendOperation enum values are validated by a
    # FATAL assertion (SIGABRT), same as the MRT color-attachment API-index
    # ceiling and blend-on-integer-format rejection. writemask=0x20 (an
    # out-of-range NS_OPTIONS bit) was ALSO tested and does NOT abort --
    # confirmed gracefully accepted (extra bits are simply inert), so it is
    # correctly NOT in this set.
    abort_ids = {"mrtapiceil_9", "mrtapiceil_10", "fmtreject_r32uint_blend_on",
                 "blendfac_src_invalid20", "blendop_invalid6"}
    non_abort = [c for c in cases if c["id"] not in abort_ids]
    abort_last = [c for c in cases if c["id"] in abort_ids]
    return non_abort + abort_last


_CASES = _cases()


def full_case_list():
    return _CASES
