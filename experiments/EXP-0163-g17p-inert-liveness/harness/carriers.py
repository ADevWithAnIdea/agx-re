#!/usr/bin/env python3
"""carriers.py -- EXP-0163 carrier definitions (frozen at pre-registration).

One entry per authored MSL program in kernels/, with the EXACT pipeline
descriptor it is built and run with.  Imported by analysis/census.py (pre-freeze
calibration) and by run.py (capture), so the census and the gated runs cannot
disagree about what was built.

Every carrier here exists to make ONE OR MORE of the 22 never-observed-to-move
fields of EXP-0155 structurally reachable; the `why` string states which field
and the structural argument.  See PRE_REGISTRATION.md sec.3.

CLEAN-ROOM: OWN-SHADER.  Only our own MSL is described.
"""

W = H = 16

# buffer(0) contents, per carrier, as float32 unless the name ends in _U32.
BUF_TEX = [1.0, 0.0, 3.0, 2.0, 5.0, 4.0,      # [0..5] coords / operands
           6.0, 7.0,                          # [6],[7] sentinel factors 6*7=42
           11.0, 12.0, 13.0, 14.0,            # [8..11]  colour 0
           21.0, 22.0, 23.0, 24.0,            # [12..15] colour 1
           31.0, 32.0, 33.0, 34.0]            # [16..19] colour 2
BUF_VSRC = [5.0, 6.0, 7.0, 900.0, 901.0, 902.0] + [0.0] * 14
BUF_FCLASS = [0.0, 0.0,          # 0/0 -> NaN
              1.0, 0.0,          # 1/0 -> Inf
              1.5, 0.25] + [0.0] * 14
BUF_BITS_U32 = [0x89ABCDEF, 0x00FF1234] + [0] * 18
# Normalised sample coordinates: 2D (8x8), 3D (4x4x4), cube face, array slice.
BUF_CUBE = [0.3125, 0.6875,          # 2D
            0.125, 0.375, 0.625,     # 3D
            0.5, -0.3,               # cube direction x,y (z = -1 -> the -Z face)
            0.0] + [0.0] * 12

CLEAR_TILE = (0.5, 0.25, 0.125, 0.0625)

CARRIERS = {
    # ---- interpolation location (iter_at.loc, iter.b9) --------------------
    "ms4cent": dict(
        kind="render", src="kernels/k_ms4cent.metal", color_format=125,
        samples=4, resolve=True, width=W, height=H,
        why="iter_at.loc was only ever swept at rasterSampleCount 1, where "
            "centroid, sample and pixel-centre are the same point"),
    "ms4out": dict(
        kind="render", src="kernels/k_ms4out.metal", color_format=125,
        samples=4, resolve=True, width=W, height=H, out_buf=(1, 16 * 16 * 4 * 16),
        why="per-sample observation of the same field, with no resolve average "
            "to hide a permutation of the four samples"),
    "atoff1": dict(
        kind="render", src="kernels/k_atoff1.metal", color_format=125,
        samples=1, width=W, height=H,
        why="interpolate_at_offset gives iter_at a live location operand with no "
            "MSAA at all -- an independent structural route to iter_at.loc"),
    "atoff4": dict(
        kind="render", src="kernels/k_atoff4.metal", color_format=125,
        samples=4, resolve=True, width=W, height=H,
        why="offset + centroid + two explicit sample indices in one program: the "
            "widest simultaneous location coverage in the set"),


    # ---- iter_at.loc: MINIMAL DELTA (same program, sample count only) -----
    "cent1": dict(
        kind="render", src="kernels/k_cent.metal", color_format=125,
        samples=1, width=W, height=H,
        why="the EXP-0155 configuration reproduced exactly: at 1 sample the "
            "centroid, the sample point and the pixel centre are one point, so "
            "iter_at.loc has nothing to select.  This arm is the CONTROL"),
    "cent4": dict(
        kind="render", src="kernels/k_cent.metal", color_format=125,
        samples=4, resolve=True, width=W, height=H,
        why="byte-for-byte the same MSL as cent1, built at 4 samples.  If "
            "iter_at.loc moves here and not on cent1, the EXP-0155 null was "
            "the sample count, not the silicon"),

    # ---- imageblock_store.b4 ---------------------------------------------
    "ibsamp": dict(
        kind="render", src="kernels/k_ibsamp.metal", color_format=125,
        samples=1, width=W, height=H, tex_sample=(8, 8), buf0=BUF_TEX,
        why="reproduces the EXP-0155 shape in which an RGBA32Float colour "
            "output compiles to imageblock_store rather than frag_color_store"),
    "ibmrt": dict(
        kind="render", src="kernels/k_ibmrt.metal", color_format=125,
        samples=1, rt_count=3, width=W, height=H, tex_sample=(8, 8),
        buf0=BUF_TEX,
        why="the same store on THREE attachments; byte+4 of the sibling "
            "frag_color_store is documented to take 0x08 only in the MRT / "
            "array-slice variant, which no EXP-0155 arm emitted"),
    "ibhalf": dict(
        kind="render", src="kernels/k_ibhalf.metal", color_format=115,
        samples=1, width=W, height=H, tex_sample=(8, 8), buf0=BUF_TEX,
        why="the same store into a 16-bit attachment: the format descriptor and "
            "any width-dependent neighbour differ with everything else held"),

    "ibms4": dict(
        kind="render", src="kernels/k_ibsamp.metal", color_format=125,
        samples=4, resolve=True, width=W, height=H, tex_sample=(8, 8),
        buf0=BUF_TEX,
        why="the imageblock store at 4 samples: byte-for-byte the same MSL as "
            "ibsamp, so a third structurally distinct context for b4 with only "
            "the sample count changed"),
    "sball": dict(
        kind="compute", src="kernels/k_sball.metal", function="k_simd",
        grid=32, tg=32, out_bytes=32 * 16 * 4,
        why="every ballot/vote form MSL offers (active mask, predicate ballot, "
            "quad ballot, any/all at both scopes) in one kernel, each result "
            "consumed several times and fed back into the SIMD network"),

    # ---- render-target selection (frag_tile_setup.*, frag_color_store.*,
    #      imageblock_store.b4) ------------------------------------------------
    "mrt3": dict(
        kind="render", src="kernels/k_mrt3.metal", color_format=125,
        samples=1, rt_count=3, width=W, height=H,
        why="frag_tile_setup.sel is documented as a per-render-target selector; "
            "both EXP-0155 carriers had exactly one target to select"),
    "tileread": dict(
        kind="render", src="kernels/k_tileread.metal", color_format=125,
        samples=1, width=W, height=H, clear=CLEAR_TILE,
        why="frag_tile_setup.access is documented 0x06 store-setup vs 0x08 "
            "tile-read; neither EXP-0155 carrier ever read the tile"),
    "tilerw2": dict(
        kind="render", src="kernels/k_tilerw2.metal", color_format=125,
        samples=1, rt_count=2, width=W, height=H, clear=CLEAR_TILE,
        why="both access modes AND more than one selector value live in one "
            "program"),
    "layer": dict(
        kind="render", src="kernels/k_layer.metal", color_format=125,
        samples=1, rt_array=4, width=W, height=H,
        why="frag_color_store.store_mode is the tile-store ADDRESSING mode and "
            "slice_addr is documented to carry a value only in array-target "
            "stores; no EXP-0155 carrier rendered to an array target"),

    # ---- varying stores (vary_store.hint2/hint6/b7, iter.b9) --------------
    "vmany": dict(
        kind="render", src="kernels/k_vmany.metal", color_format=125,
        samples=1, width=W, height=H,
        why="16 scalar varyings force output slots past 7, i.e. the byte+5 bit0 "
            "slot wrap the 4-varying EXP-0155 carrier never reached"),
    "vhalf": dict(
        kind="render", src="kernels/k_vhalf.metal", color_format=125,
        samples=1, width=W, height=H,
        why="half and vector varyings: 16- and 32-bit component widths and "
            "vector runs of 1/2/4, versus 32-bit scalars only"),
    "vflat": dict(
        kind="render", src="kernels/k_vflat.metal", color_format=125,
        samples=1, width=W, height=H,
        why="flat integer, no-perspective and perspective varyings in one "
            "program: three interpolation classes, versus one"),
    "vsrc": dict(
        kind="render", src="kernels/k_vsrc.metal", color_format=125,
        samples=1, width=W, height=H, buf0=BUF_VSRC,
        why="vary_store.hint2 is documented as the same DATA-SOURCE mode as the "
            "device_store amode; this carrier gives the varyings three distinct "
            "provenances (memory, immediate, computed)"),
    "vclip": dict(
        kind="render", src="kernels/k_vclip.metal", color_format=125,
        samples=1, width=W, height=H,
        why="[[clip_distance]] is a vertex output that is neither position nor a "
            "user varying -- a destination class not previously emitted"),

    # ---- the polymorphic 0x2f op (tex_coord_setup.b5/b6/b8/b9/idx) --------
    "fclass": dict(
        kind="render", src="kernels/k_fclass.metal", color_format=125,
        samples=1, width=W, height=H, buf0=BUF_FCLASS,
        why="db.json documents this op as polymorphic; the float-classify form "
            "(isnan/isnormal/frexp/modf) is a `form` value EXP-0155's single "
            "texture-side carrier never emitted"),
    "bits": dict(
        kind="render", src="kernels/k_bits.metal", color_format=125,
        samples=1, width=W, height=H, buf0=BUF_BITS_U32, buf0_is_u32=True,
        why="form value 16 is enumerated 'bitfield/shift-prep' and no EXP-0155 "
            "carrier emitted it"),
    "texcube": dict(
        kind="render", src="kernels/k_texcube.metal", color_format=125,
        samples=1, width=W, height=H, tex_sample=(8, 8), tex_extra=True,
        buf0=BUF_CUBE,
        why="tex_coord_setup.idx is a plausible index; four texture SHAPES (2D, "
            "3D, cube, array with a non-zero slice) give an index distinct "
            "things to select between"),

    # ---- texture writes (tex_write.amode / rsv11) -------------------------
    "twdim": dict(
        kind="render", src="kernels/k_twdim.metal", color_format=125,
        samples=1, width=W, height=H, buf0=BUF_TEX,
        tex_write=(8, 8), tex_write_arr=(8, 8, 4), tex_write_3d=(8, 8, 4),
        why="all three EXP-0155 writes went to the same plain 2D target; the "
            "array, 3D and non-zero-slice destinations an addressing mode would "
            "have to distinguish were never emitted"),
    "twtype": dict(
        kind="render", src="kernels/k_twtype.metal", color_format=125,
        samples=1, width=W, height=H, buf0=BUF_TEX,
        tex_write=(8, 8), tex_write_half=(8, 8), tex_write_uint=(8, 8),
        why="contiguous vs scattered data descriptors and 16-/32-bit, float/"
            "integer write data, versus one contiguous float4 source"),

    # ---- ADDENDUM (post-run01): a THIRD tex_write program -----------------
    "twrt": dict(
        kind="render", src="kernels/k_twrt.metal", color_format=125,
        samples=1, width=W, height=H, buf0=BUF_TEX,
        tex_sample=(8, 8), tex_write=(8, 8), tex_write_arr=(8, 8, 4),
        tex_write_3d=(8, 8, 4),
        why="ADDENDUM: twdim and twtype are two programs, one short of the "
            "pre-registered >=3-carrier bar for tex_write.amode / rsv11, and "
            "they share the property that every write uses a CONSTANT "
            "compile-time coordinate with no control flow.  This third program "
            "writes with runtime-computed coordinates, with data of texture-unit "
            "provenance, from inside a loop, and to a 3D destination with a "
            "runtime depth"),

    # ---- SIMD (simd_ballot.cache, simd_shuffle.cache/rsv9) ----------------
    "scache": dict(
        kind="compute", src="kernels/k_scache.metal", function="k_simd",
        grid=32, tg=32, out_bytes=32 * 16 * 4,
        why="if `cache` is a value-liveness hint it cannot matter when a result "
            "is produced and consumed exactly once, which is all EXP-0155's "
            "carrier did; here every SIMD result has many consumers, long reuse "
            "distance, and feeds further SIMD ops"),
    "stype": dict(
        kind="compute", src="kernels/k_stype.metal", function="k_simd",
        grid=32, tg=32, out_bytes=32 * 16 * 4,
        why="simd_shuffle.rsv9 is documented as the rotate-form tail; the "
            "rotate/fill, quad, dynamic-lane and 16-/64-bit operand forms were "
            "all absent from EXP-0155's two arms"),
    "sdiv": dict(
        kind="compute", src="kernels/k_sdiv.metal", function="k_simd",
        grid=32, tg=32, out_bytes=32 * 16 * 4,
        why="EXP-0155's SIMD carrier is deliberately divergence-free, so the "
            "active mask was always full -- the one input a ballot exists to "
            "report"),
}

# The 22 fields EXP-0163 targets (re-derived from EXP-0155 run03+run04 by
# analysis/audit_0155.py, NOT copied from the dispatch).
TARGETS = {
    "tex_coord_setup": ["b5", "b6", "b8", "b9", "idx"],
    "vary_store": ["b7", "hint2", "hint6"],
    "simd_ballot": ["cache"],
    "simd_shuffle": ["cache", "rsv9"],
    "frag_color_store": ["store_mode"],
    "frag_tile_setup": ["access", "b5", "sel"],
    "imageblock_store": ["b4"],
    "iter_at": ["loc"],
    "tex_write": ["rsv11", "amode"],
    "iter": ["b9"],
}
# Secondary byte-probe targets: the 0x57 collision arms of EXP-0155, which are
# raw byte positions rather than db.json fields.  byte+2 of the VERTEX form is
# vary_store.hint2, so these overlap the field list on purpose.
BYTE_TARGETS = {"op57_vertex": [2], "op57_fragment": [2]}

# Probes.  The colour probes are unchanged from EXP-0155 for comparability, plus
# four EDGE pixels, because centroid/sample interpolation can differ from centre
# ONLY in a partially covered pixel.  (Triangle screen vertices at 16x16 are
# (2,11), (8,11), (14,3); these four straddle its three edges.)
PROBE_PIXELS = [(8, 8), (5, 10), (11, 5),
                (5, 9), (3, 10), (11, 6), (7, 10)]
PROBE_LANES = [0, 1, 5, 17, 31]
PROBE_TEXELS = [(1, 0), (3, 2), (5, 4), (7, 6), (0, 0), (7, 7)]
