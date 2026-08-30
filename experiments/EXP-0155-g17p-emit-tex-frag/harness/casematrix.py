#!/usr/bin/env python3
"""casematrix.py -- EXP-0155 FROZEN case matrix (G17P: texture + fragment + SIMD).

Defines, deterministically and without touching hardware:
  * the carriers (our own MSL + the exact pipeline descriptor each is built with),
  * which instruction OCCURRENCE each field is swept on,
  * the value set swept for each field,
  * the liveness control splice for each occurrence,
  * the pre-registered falsifiers,
  * the arm PRIORITY ORDER (the dispatch's order: vary_slot, then tex_sample,
    then the rest), which is also the order a deadline truncates.

Imported by run.py (capture) and analysis/verdicts.py (reduction) so both gated
runs and the analysis see exactly the same matrix.

Derived from OUR OWN experiments/EXP-0143-m4-emit-frag-simd/harness/casematrix.py;
the texture carriers, arms and texel probes are new here.

CLEAN-ROOM: OWN-SHADER.  Only bytes compiled from our own MSL are described.
"""

# --------------------------------------------------------------------------
# Carriers.  `kind` = render | compute.
#   tex_sample=(w,h)  -> bind an R32Float texture at [[texture(0)]],
#                        texel(x,y) = x + 100*y
#   tex_write=(w,h)   -> bind an RGBA32Float texture at [[texture(1)]], reset to
#                        (-1,-2,-3,-4) before every render and read back after
# --------------------------------------------------------------------------
CARRIERS = {
    # ---- texture ----------------------------------------------------------
    "t_sample": dict(kind="render", src="kernels/t_sample.metal", color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16,
                     tex_sample=(8, 8), buf0=True),
    "t_texops": dict(kind="render", src="kernels/t_texops.metal", color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16,
                     tex_sample=(8, 8), buf0=True),
    "t_write":  dict(kind="render", src="kernels/t_write.metal", color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16,
                     tex_write=(8, 8), buf0=True),
    "t_lodoff": dict(kind="render", src="kernels/t_lodoff.metal", color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16,
                     tex_sample=(8, 8), tex_depth=(8, 8), buf0=True),
    "t_coord":  dict(kind="render", src="kernels/t_coord.metal", color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16,
                     tex_extra=True, buf0=True),
    "t_deriv":  dict(kind="render", src="kernels/t_deriv.metal", color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16,
                     buf0=True),
    # ---- fragment / varying ----------------------------------------------
    "c_iter":   dict(kind="render", src="kernels/c_iter.metal",   color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_vary16": dict(kind="render", src="kernels/c_vary16.metal", color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_flat":   dict(kind="render", src="kernels/c_flat.metal",   color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_cent1":  dict(kind="render", src="kernels/c_cent.metal",   color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_cent4":  dict(kind="render", src="kernels/c_cent.metal",   color_format=125,
                     samples=4, depth=False, resolve=True,  width=16, height=16),
    "c_pack":   dict(kind="render", src="kernels/c_pack.metal",   color_format=80,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_depth":  dict(kind="render", src="kernels/c_depth.metal",  color_format=125,
                     samples=1, depth=True,  resolve=False, width=16, height=16),
    "c_kill":   dict(kind="render", src="kernels/c_kill.metal",   color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_mask":   dict(kind="render", src="kernels/c_mask.metal",   color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    # ---- SIMD (compute) ---------------------------------------------------
    "c_simd":   dict(kind="compute", src="kernels/c_simd.metal", function="k_simd",
                     grid=32, tg=32, out_bytes=32 * 16 * 4),
}

RENDER_VERTEX = "v_main"
RENDER_FRAGMENT = "f_main"

# Probe pixels (0-based x,y) inside the rasterized triangle at 16x16.  All three
# are covered by every render carrier's baseline; run.py asserts that.
PROBE_PIXELS = [(8, 8), (5, 10), (11, 5)]
PROBE_LANES = [0, 1, 5, 17, 31]

# Texels read back from the WRITABLE texture: the three t_write targets plus two
# controls that must keep the harness reset sentinel (-1,-2,-3,-4).
PROBE_TEXELS = [(1, 0), (3, 2), (5, 4), (0, 0), (7, 7)]
TEXW_RESET = [-1.0, -2.0, -3.0, -4.0]

# buffer(0) contents for the texture/derivative carriers (float32).
#   [0..5] : three sample coordinates / derivative coefficients
#   [6],[7]: the integrity-sentinel factors (product 6*7 = 42.0)
#   [8..19]: the three colours t_write writes
BUF0 = [1.0, 0.0, 3.0, 2.0, 5.0, 4.0,
        6.0, 7.0,
        11.0, 12.0, 13.0, 14.0,
        21.0, 22.0, 23.0, 24.0,
        31.0, 32.0, 33.0, 34.0]
# t_deriv reads in[0..3] as the four partial derivatives, in[4],[5] as W,H and
# in[7]*in[8] as its sentinel, so it gets its own buffer.
BUF0_DERIV = [2.0, 3.0, 5.0, 7.0, 16.0, 16.0, 0.0, 6.0, 7.0] + [0.0] * 11

# --------------------------------------------------------------------------
# Geometry + per-vertex varying values -> the host-side interpolation oracle.
# Every carrier uses the SAME triangle and all three vertices have w == 1, so
# perspective-correct == linear and the oracle is exact.
# --------------------------------------------------------------------------
NDC_TRI = [(-0.75, -0.375), (0.0, -0.375), (0.75, 0.625)]

ITER_SLOT_VALUES = {
    1: (1.0, 2.0, 3.0),            # v0
    2: (10.0, 11.0, 14.0),         # v1
    3: (100.0, 97.0, 94.0),        # v2
    4: (1000.0, 1003.0, 1016.0),   # v3
}


def bary(px, py, w, h, tri=NDC_TRI):
    """Screen-space barycentric of the pixel CENTRE, Metal viewport convention."""
    scr = [((x * 0.5 + 0.5) * w, (0.5 - y * 0.5) * h) for x, y in tri]
    x, y = px + 0.5, py + 0.5
    (x0, y0), (x1, y1), (x2, y2) = scr
    d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    b0 = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / d
    b1 = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / d
    return (b0, b1, 1.0 - b0 - b1)


def interp(slot, px, py, w, h):
    v = ITER_SLOT_VALUES.get(slot)
    if v is None:
        return None
    b = bary(px, py, w, h)
    return sum(bi * vi for bi, vi in zip(b, v))


def texel(x, y):
    """The R32Float source texture's content: texel(x,y) = x + 100*y."""
    return float(x) + 100.0 * float(y)


# --------------------------------------------------------------------------
# Value sets.
# --------------------------------------------------------------------------
def dense(width):
    return list(range(1 << width))


def wide(width):
    """Boundaries + every power of two + >=16 asymmetric interior samples."""
    mx = (1 << width) - 1
    vals = {0, 1, 2, mx - 1, mx}
    vals |= {1 << i for i in range(width)}
    vals |= {(1 << i) - 1 for i in range(1, width)}
    for k in (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59):
        vals.add((k * 0x9E3779B1) & mx)
    return sorted(vals)


def field_values(desc_fields, name):
    for f in desc_fields:
        if f["name"] == name:
            w = f["width"]
            return dense(w) if w <= 8 else wide(w)
    raise KeyError(name)


# --------------------------------------------------------------------------
# Arms, IN PRIORITY ORDER (the dispatch's order).  One arm == one
# (carrier, stage, mnemonic, occurrence) target.
#   fields : the fields swept on this arm
#   live   : (field, value) control splice that MUST change the observation
#   note   : why the instruction is live on the OBSERVED output path
# --------------------------------------------------------------------------
TEX_SAMPLE_FIELDS = ["kind", "chain", "comp_flags", "result_sel", "coord",
                     "extra_coord", "lod_present", "tex_type", "samp_extra"]
TEX_COORD_FIELDS = ["dst_lo", "b1", "subop", "srcA", "form", "b5", "b6", "idx",
                    "b8", "b9"]
TEX_WRITE_FIELDS = ["coord_pack", "amode", "seq_idx", "layer_reg", "coord_regs",
                    "rsv8", "coord_dim", "rsv10", "rsv11", "wop", "data_desc",
                    "data_desc_hi", "rsv15"]

ARMS = [
    # ================= PRIORITY 1 : vary_slot (2 fields) ===================
    dict(id="vary_slot@iter_v0", carrier="c_iter", stage="vertex",
         mnemonic="vary_slot", occ=0, fields=["sel", "slot"], live=("sel", 0x00),
         note="the vertex program feeds every fragment varying and the fragment "
              "program writes all four straight to the observed pixel, so any "
              "change to a varying-output descriptor must move a read-back float"),
    dict(id="vary_slot@v16_v0", carrier="c_vary16", stage="vertex",
         mnemonic="vary_slot", occ=0, fields=["sel", "slot"], live=("sel", 0x00),
         note="12-varying replicate (slots past 7) on a DIFFERENT shader -- "
              "adversarial cross-check of vary_slot@iter_v0"),
    dict(id="vary_slot@v16_v6", carrier="c_vary16", stage="vertex",
         mnemonic="vary_slot", occ=6, fields=["sel", "slot"], live=("sel", 0x00),
         note="a high-slot occurrence in the same program"),

    # ================= PRIORITY 2 : tex_sample =============================
    dict(id="tex_sample@t1_0", carrier="t_sample", stage="fragment",
         mnemonic="tex_sample", occ=0, channel=0, fields=TEX_SAMPLE_FIELDS,
         live=("coord", 0x00),
         note="sample 0's result is colour channel 0 and nothing else reaches "
              "channel 0; channel 3 is a texture-unit-independent ALU sentinel, "
              "so a dead texture unit and a dead shader are separable"),
    dict(id="tex_sample@t1_1", carrier="t_sample", stage="fragment",
         mnemonic="tex_sample", occ=1, channel=1, fields=TEX_SAMPLE_FIELDS,
         live=("coord", 0x00),
         note="sample 1 -> channel 1; adversarial replicate of the same op in "
              "the same program with a different coordinate register pair"),
    dict(id="tex_sample@t1_2", carrier="t_sample", stage="fragment",
         mnemonic="tex_sample", occ=2, channel=2, fields=TEX_SAMPLE_FIELDS,
         live=("coord", 0x00),
         note="sample 2 -> channel 2; third independent replicate"),
    dict(id="tex_sample@t2_0", carrier="t_texops", stage="fragment",
         mnemonic="tex_sample", occ=0, channel=0,
         fields=["tex_type", "samp_extra", "lod_present", "comp_flags",
                 "result_sel", "kind", "chain"],
         live=("coord", 0x00),
         note="EXPLICIT-LOD sample -> channel 0: a different `variant` value, so "
              "the tex_type/lod_present rules are tested off the implicit-LOD path"),
    dict(id="tex_sample@t2_1", carrier="t_texops", stage="fragment",
         mnemonic="tex_sample", occ=1, channel=1,
         fields=["tex_type", "samp_extra", "lod_present", "comp_flags",
                 "result_sel", "kind", "chain"],
         live=("coord", 0x00),
         note="GATHER -> channel 1: exercises result_desc's gather encoding and "
              "a third variant value"),
    dict(id="tex_sample@t2_2", carrier="t_texops", stage="fragment",
         mnemonic="tex_sample", occ=2, channel=2,
         fields=["tex_type", "samp_extra", "lod_present", "comp_flags",
                 "result_sel", "kind", "chain"],
         live=("coord", 0x00),
         note="unfiltered READ -> channel 2: no sampler is involved, so any "
              "sampler-side field that still matters here is a real finding"),

    # ================= PRIORITY 3 : tex_coord_setup ========================
    dict(id="tex_coord@lo_0", carrier="t_lodoff", stage="fragment",
         mnemonic="tex_coord_setup", occ=0, fields=TEX_COORD_FIELDS,
         live=("srcA", 0x00),
         note="THE ONLY tex_coord_setup our whole carrier set emits.  The "
              "pre-freeze census showed neither a float2 2D sample nor a "
              "3D/cube/array sample emits it -- only the const-offset gather / "
              "bias / gradient / depth-compare carrier does.  It feeds the four "
              "sample ops whose results are the four observed colour channels"),
    dict(id="tex_sample@lo_0", carrier="t_lodoff", stage="fragment",
         mnemonic="tex_sample", occ=0,
         fields=["tex_type", "samp_extra", "lod_present", "comp_flags",
                 "result_sel", "coord", "extra_coord", "kind", "chain"],
         live=("coord", 0x00),
         note="depth-compare sample (variant 0x20): the widest variant coverage "
              "in the set, and the only one with a compare reference operand"),
    dict(id="tex_sample@lo_1", carrier="t_lodoff", stage="fragment",
         mnemonic="tex_sample", occ=1,
         fields=["tex_type", "samp_extra", "lod_present", "comp_flags",
                 "result_sel", "coord", "extra_coord", "kind", "chain"],
         live=("coord", 0x00),
         note="const-offset gather (variant 0x01, samp_extra 0x0e): the only "
              "occurrence in the set with a non-zero samp_extra"),
    dict(id="tex_sample@lo_2", carrier="t_lodoff", stage="fragment",
         mnemonic="tex_sample", occ=2,
         fields=["tex_type", "samp_extra", "lod_present", "comp_flags",
                 "result_sel", "coord", "extra_coord"],
         live=("coord", 0x00),
         note="gradient sample (variant 0x04, mode 0x10 filtered)"),
    dict(id="tex_sample@tc_0", carrier="t_coord", stage="fragment",
         mnemonic="tex_sample", occ=0, channel=0,
         fields=["tex_type", "extra_coord", "samp_extra", "lod_present",
                 "comp_flags", "result_sel"],
         live=("coord", 0x00),
         note="a 3D sample: the ONLY place tex_type=2 (volumetric) and the "
              "third coordinate register (extra_coord) are live"),

    # ================= PRIORITY 4 : tex_deriv ==============================
    dict(id="tex_deriv@d0", carrier="t_deriv", stage="fragment",
         mnemonic="tex_deriv", occ=0,
         fields=["b1", "dstsrc", "src_comp", "tail"], live=("axis", 0x00),
         note="each of the four derivatives goes to its OWN colour channel and "
              "the alpha channel adds an ALU-only sentinel, so a zeroed "
              "derivative, an axis swap and a dead dispatch are three different "
              "read-back vectors"),
    dict(id="tex_deriv@d1", carrier="t_deriv", stage="fragment",
         mnemonic="tex_deriv", occ=1,
         fields=["b1", "dstsrc", "src_comp", "tail"], live=("axis", 0x00),
         note="second derivative op in the same program -- adversarial replicate"),

    # ================= PRIORITY 5 : tex_write ==============================
    dict(id="tex_write@w0", carrier="t_write", stage="fragment",
         mnemonic="tex_write", occ=0, fields=TEX_WRITE_FIELDS,
         live=("coord_pack", 0x00),
         note="write 0 lands in texel (1,0) of a texture reset to (-1,-2,-3,-4) "
              "before every render: 'wrote here', 'did not write' and 'wrote "
              "somewhere else' are three distinguishable read-backs"),
    dict(id="tex_write@w1", carrier="t_write", stage="fragment",
         mnemonic="tex_write", occ=1, fields=TEX_WRITE_FIELDS,
         live=("coord_pack", 0x00),
         note="write 1 -> texel (3,2); adversarial replicate"),
    dict(id="tex_write@w2", carrier="t_write", stage="fragment",
         mnemonic="tex_write", occ=2,
         fields=["wop", "amode", "coord_dim", "data_desc", "rsv8", "rsv15"],
         live=("coord_pack", 0x00),
         note="write 2 -> texel (5,4); third replicate on the highest-value fields"),

    # ================= PRIORITY 5b : imageblock ============================
    dict(id="ibs@t1", carrier="t_sample", stage="fragment",
         mnemonic="imageblock_store", occ=0,
         fields=["src", "b4", "b6", "fmt", "tail"], live=("src", 0x00),
         note="the pre-freeze census found the RGBA32Float colour output of the "
              "implicit-LOD sample carrier is encoded as imageblock_store, not "
              "frag_color_store: it writes the observed pixel, so the whole "
              "instruction is live on the read-back float"),
    dict(id="ibs@tc", carrier="t_coord", stage="fragment",
         mnemonic="imageblock_store", occ=0,
         fields=["src", "b4", "b6", "fmt", "tail"], live=("src", 0x00),
         note="adversarial replicate of the store on the 3D/cube/array carrier"),

    # ================= PRIORITY 6 : interpolation ==========================
    dict(id="iter@frag1", carrier="c_iter", stage="fragment",
         mnemonic="iter", occ=1,
         fields=["grp", "lead", "dst", "coeff_sel", "c7", "loc", "b9"],
         live=("src_slot", 0x08),
         note="this iter produces colour channel 0 (EXP-0143 pilot: src_slot "
              "0x02->0x08 makes channel 0 equal channel 3)"),
    dict(id="iter@frag0W", carrier="c_iter", stage="fragment",
         mnemonic="iter", occ=0,
         fields=["lead", "coeff_sel", "c7", "loc", "b9", "grp"],
         live=("mode", 0x00),
         note="the perspective-W-denominator iter; its result feeds the rcp that "
              "scales all four channels"),
    dict(id="iter@cent1", carrier="c_cent1", stage="fragment",
         mnemonic="iter", occ=1, fields=["loc", "coeff_sel", "c7", "b9", "lead"],
         live=("mode", 0x00),
         note="centroid/sample-qualified iter -- covers mode/loc values the "
              "plain-centre carrier never emits"),
    dict(id="iter@cent4", carrier="c_cent4", stage="fragment",
         mnemonic="iter", occ=1, fields=["loc", "grp"], live=("mode", 0x00),
         note="MULTISAMPLED (4x, resolved): centroid and per-sample locations "
              "are genuinely distinct from pixel centre only here"),
    dict(id="iter_at@cent1_0", carrier="c_cent1", stage="fragment",
         mnemonic="iter_at", occ=0,
         fields=["grp", "lead", "dst", "c4", "b5", "loc"], live=("lead", 0x00),
         note="interpolate-at setup for the centroid varyings; EXP-0143 pilot "
              "proved lead 0x14->0x00 changes channels 0 and 1"),
    dict(id="iter_at@cent1_1", carrier="c_cent1", stage="fragment",
         mnemonic="iter_at", occ=1,
         fields=["grp", "lead", "dst", "c4", "b5", "loc"], live=("lead", 0x00),
         note="second interpolate-at setup; pilot-proven live"),
    dict(id="iter_flat@flat1", carrier="c_flat", stage="fragment",
         mnemonic="iter_flat", occ=1, fields=["b1", "sel", "b4", "b5"],
         live=("sel", 0x00),
         note="flat varying load feeding a colour channel; the four [[flat]] "
              "values are distinct so a selector change is unambiguous"),
    dict(id="iter_flat@flat0", carrier="c_flat", stage="fragment",
         mnemonic="iter_flat", occ=0, fields=["b1", "sel", "b4", "b5"],
         live=("sel", 0x06),
         note="adversarial second occurrence of the same op in the same program"),

    # ================= PRIORITY 7 : fragment colour / depth ================
    dict(id="fcs@iter0", carrier="c_iter", stage="fragment",
         mnemonic="frag_color_store", occ=0,
         fields=["store_mode", "flags", "mask", "fmt", "slice_addr"],
         live=("rt_index", 0x02),
         note="the only colour store in the program: it writes the observed pixel"),
    dict(id="fcs@pack0", carrier="c_pack", stage="fragment",
         mnemonic="frag_color_store", occ=0,
         fields=["fmt", "mask", "flags", "store_mode"], live=("rt_index", 0x02),
         note="adversarial replicate on an 8-bit (BGRA8Unorm) attachment where "
              "fmt differs"),
    dict(id="fcp@pack0", carrier="c_pack", stage="fragment",
         mnemonic="frag_color_pack", occ=0,
         fields=["src_desc", "fmt_class", "dst", "mode", "comp_off", "val"],
         live=("val", 0x80),
         note="packs colour channels 0/1 for the 8-bit attachment store"),
    dict(id="fcp@pack1", carrier="c_pack", stage="fragment",
         mnemonic="frag_color_pack", occ=1,
         fields=["src_desc", "dst", "mode", "comp_off", "val"], live=("val", 0x80),
         note="second pack op (channels 2/3) -- adversarial replicate"),
    dict(id="fts@iter0", carrier="c_iter", stage="fragment",
         mnemonic="frag_tile_setup", occ=0,
         fields=["b1", "sel", "access", "b5"], live=("access", 0x08),
         note="store-setup bracket immediately preceding the observed colour store"),
    dict(id="fts@iter1", carrier="c_iter", stage="fragment",
         mnemonic="frag_tile_setup", occ=1,
         fields=["b1", "sel", "access", "b5"], live=("access", 0x06),
         note="second bracket around the same store"),
    dict(id="fds@depth0", carrier="c_depth", stage="fragment",
         mnemonic="frag_depth_store", occ=0, fields=["b3", "b4", "b5"],
         live=None,       # raw byte control, see LIVE_CONTROLS_RAW
         note="the only depth store; the depth attachment is read back directly "
              "and the written depth is an interpolated gradient, so 'wrote the "
              "wrong value' and 'did not write' are distinguishable"),

    # ================= PRIORITY 8 : SIMD ===================================
    dict(id="sreduce@simd0", carrier="c_simd", stage="compute",
         mnemonic="simd_reduce", occ=0,
         fields=["scope", "b0hi", "opcls", "cache", "dst", "opmarker", "src",
                 "shape"],
         live=("op", 0x02),
         note="a live SIMD-group reduction whose result every lane writes to the "
              "output buffer"),
    dict(id="sreduce@simd8", carrier="c_simd", stage="compute",
         mnemonic="simd_reduce", occ=2, fields=["scope", "shape", "b0hi", "opcls"],
         live=("op", 0x02),
         note="the opcls=0 / dtype=7 reduce (census occ 2) -- adversarial "
              "replicate exercising the other value of the op-class bit"),
    dict(id="sshuffle@simd1", carrier="c_simd", stage="compute",
         mnemonic="simd_shuffle", occ=1,
         fields=["cache", "dst", "src", "srctype", "rtype", "dsthi", "rsv9"],
         live=("lane", 0x04),
         note="simd_broadcast(u,5): the source lane is directly predictable from "
              "the input buffer, so the arm has a true predictive oracle"),
    dict(id="sshuffle@simd6", carrier="c_simd", stage="compute",
         mnemonic="simd_shuffle", occ=4, fields=["srctype", "rtype", "rsv9"],
         live=("lane", 0x08),
         note="the census's dir=1 (xor/down) occurrence -- adversarial replicate on the "
              "other direction; EXP-0115 reports THREE out-of-bounds shuffle "
              "modes, so the mode/type fields are swept densely here"),
    dict(id="sballot@simd0", carrier="c_simd", stage="compute",
         mnemonic="simd_ballot", occ=0,
         fields=["cache", "dst", "psrc", "psrctype", "form", "form_sig"],
         live=("psrc", 0x00),
         note="simd_ballot(predicate); the 32-bit mask is written by every lane"),
]

# Liveness controls expressed as a RAW byte patch inside the instruction (used
# where the control has to touch a match bit, which set_field cannot).
LIVE_CONTROLS_RAW = {
    "fds@depth0": (1, 0x00),   # byte+1 0x14 -> 0x00, the EXP-0029 control
}

# --------------------------------------------------------------------------
# Pre-registered FALSIFIERS: cases that MUST NOT match the inert oracle.  If one
# matches the baseline, the arm is reported as unable to detect a difference and
# its verdicts are WITHHELD (FIELD-SWEEP-PROTOCOL sec.3.5).
# --------------------------------------------------------------------------
# Each entry is a (arm, field, value) that the PRE-FREEZE liveness ladder
# (raw/prefreeze/smoke02_sweep.jsonl) already showed moves the observation.  The
# analysis asserts each one comes back non-`ok` in BOTH gated runs; if any of
# them silently matches the baseline, that arm could not detect a difference on
# the day and its verdicts are WITHHELD.
FALSIFIERS = [
    ("vary_slot@iter_v0", "sel", 0x00),
    ("vary_slot@v16_v0", "sel", 0x00),
    ("tex_sample@t1_0", "kind", 0x0a),
    ("tex_sample@t1_1", "kind", 0x02),
    ("tex_sample@t1_2", "kind", 0x0a),
    ("tex_sample@t2_0", "tex_type", 0xfe),
    ("tex_sample@lo_1", "tex_type", 0xfe),
    ("tex_coord@lo_0", "dst_lo", 0x09),
    ("tex_write@w0", "coord_pack", 0xef),
    ("tex_write@w1", "coord_pack", 0xdf),
    ("tex_write@w2", "wop", 0x75),
    ("ibs@t1", "src", 0xff),
    ("ibs@tc", "src", 0xff),
    ("iter_at@cent1_0", "lead", 0x00),
    ("iter_flat@flat1", "sel", 0x00),
    ("fcp@pack0", "val", 0x80),
    ("fts@iter0", "b1", 0xfd),
    ("sreduce@simd8", "scope", 0x00),
]

# NO predictive host oracle survives the pre-freeze census.  The cross-occurrence
# tex_sample.coord oracle was pre-registered but the census shows our compiled
# bytes use only coord = 0 and coord = 1 across the three samples, with two
# occurrences SHARING coord = 1, so "give occurrence 0 occurrence 1's coordinate
# register" is not a distinguishing prediction.  Every field therefore uses the
# INERT oracle -- host-computed as "identical to this arm's own unmutated
# baseline" -- and any departure from it is the observation.  The falsifiers
# above are what prove the inert oracle can still see a difference.
PREDICTIVE = set()

# --------------------------------------------------------------------------
# The 0x57 opcode-collision probe (vary_store, flagged emit_unsafe in db.json).
# Not a field sweep: a discriminator + LENGTH hypothesis tested on hardware.
# --------------------------------------------------------------------------
COLLISION_PROBE = dict(
    hypothesis=(
        "byte0==0x57 is shared by an 8-byte VERTEX varying store and a 6-byte "
        "FRAGMENT kill/target-mask op.  db.json's vary_store matches on byte0 "
        "alone and always consumes 8 bytes, so it MIS-LENGTHS the fragment "
        "form.  H1: the discriminator is byte+1 (its low nibble); H2: byte+2 "
        "co-varies with the length.  If either byte controls the hardware's "
        "instruction LENGTH, the following instruction is mis-fetched and the "
        "program's output changes in a way a mere operand change cannot explain."),
    vs_carriers=["c_iter", "c_vary16"],
    fs_carriers=["c_kill", "c_mask"],
    byte_positions=[1, 2],
    byte_values=list(range(256)),
)

# --------------------------------------------------------------------------
# imageblock_load / imageblock_store: CONDITIONAL.  EXP-0142 recorded that the
# explicit-layout fragment imageblock no longer compiles (macOS 26.6.2 /
# GPUCompiler 32023.886).  run.py attempts the carriers listed here, records
# every compile failure verbatim in raw/, and skips the arm if none compiles.
# No field of either instruction is promoted without a compiling carrier.
# --------------------------------------------------------------------------
# PRE-FREEZE NEGATIVE RESULT (raw/prefreeze/census_run2.txt): none of our
# carriers emits `imageblock_load`.  The explicit-layout fragment imageblock does
# not compile (EXP-0142) and the programmable-blending route (a [[color(0)]]
# fragment input, kernels/t_iblock.metal) compiles to `tile_read`, which EXP-0147
# already closed -- not to imageblock_load.  imageblock_load is therefore
# pre-registered as NOT ATTEMPTED and its five blocking fields stay `untested`.
IMAGEBLOCK_LOAD = "not attempted -- no carrier emits it; see RESULTS.md"
