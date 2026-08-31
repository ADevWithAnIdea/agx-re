#!/usr/bin/env python3
"""carriers.py -- EXP-0204 carrier definitions (FROZEN at pre-registration).

One entry per authored MSL program in kernels/, with the EXACT pipeline
descriptor it is built and run with.  Imported by analysis/census.py (pre-freeze
calibration) and by run.py (capture), so the census and the gated runs cannot
disagree about what was built.

THE ONE RULE THIS FILE EXISTS TO ENFORCE.  `docs/isa/emit-worklist.md` line 7: a
field that never moves is promotable only if the carriers differ IN THE DIMENSION
THE FIELD CONTROLS.  Two carriers identical in that dimension are ONE carrier.
This corpus has been burned by it twice, both times on texture:
`tex_sample.samp_extra` read 256/256 INERT on nine arms and moved on 128/256 on
the tenth (the explicit-LOD arm); `iter_at.loc` read inert on every arm of
EXP-0155 and MOVED at 4 samples once EXP-0163 varied rasterSampleCount.

Every carrier below therefore states, in `why`, WHICH field it is for, WHAT
dimension that field controls, and HOW it differs in that dimension from the
carriers that already read the field inert.  `DIMENSION` names the dimension per
field so an inert verdict rests on a claim a reviewer can dispute.

CLEAN-ROOM: OWN-SHADER.  Only our own MSL is described.
"""

W = H = 16

# Probe points, kept identical to EXP-0155/0163/0172 so observations compare.
PROBE_PIXELS = [(8, 8), (5, 10), (11, 5), (5, 9), (3, 10), (11, 6), (7, 10)]
PROBE_LANES = [0, 1, 5, 17, 31]
PROBE_TEXELS = [(1, 0), (3, 2), (5, 4), (7, 6), (0, 0), (7, 7)]

# buffer(0): the EXP-0155/0163 texture-carrier buffer, unchanged so the write
# carriers stay comparable with the two arms already on record.
BUF_TEX = [1.0, 0.0, 3.0, 2.0, 5.0, 4.0,      # [0..5] normalised sample coords
           6.0, 7.0,                          # [6],[7] sentinel factors 6*7=42
           11.0, 12.0, 13.0, 14.0,            # [8..11]  colour 0
           21.0, 22.0, 23.0, 24.0,            # [12..15] colour 1
           31.0, 32.0, 33.0, 34.0]            # [16..19] colour 2
# buffer(1): float4 lanes for the contiguous-vec4 (no-ALU) store in k_twdyn.
BUF_VEC4 = [41.0, 42.0, 43.0, 44.0,
            51.0, 52.0, 53.0, 54.0,
            61.0, 62.0, 63.0, 64.0,
            71.0, 72.0, 73.0, 74.0]

_MIP = (16, 16, 3)          # sampled mip texture: 16x16, levels 0,1,2

CARRIERS = {
    # =================================================== tex_sample.mode ====
    # DIMENSION: the SAMPLE-OPERATION CLASS.  db.json's own enum for this field
    # is {0x00 gather/read/sample_compare, 0x10 filtered sample, 0x20 LOD query},
    # so the carriers must differ in which of those classes they express.  All
    # six below sample or read the SAME mipmapped texture (or, for the compare
    # class, the depth texture), so the class is the only thing that varies.
    "msfilt": dict(
        kind="render", src="kernels/k_msfilt.metal", color_format=125,
        samples=1, width=W, height=H, tex_mip=_MIP,
        why="tex_sample.mode -- the FILTERED-SAMPLE class (implicit LOD, linear "
            "magnification, coordinate on the exact corner of four level-0 "
            "texels so a filtered result is host-predictable and an unfiltered "
            "one cannot be)."),
    "msfixl": dict(
        kind="render", src="kernels/k_msfixl.metal", color_format=125,
        samples=1, width=W, height=H, tex_mip=_MIP,
        why="tex_sample.mode -- the FILTERED-SAMPLE class again but "
            "DERIVATIVE-FREE (explicit level()).  Control for msfilt: EXP-0172 "
            "showed derivative-dependent texture carriers are the unstable ones "
            "and derivative-free ones reproduce at 100 %."),
    "msgath": dict(
        kind="render", src="kernels/k_msgath.metal", color_format=125,
        samples=1, width=W, height=H, tex_mip=_MIP,
        why="tex_sample.mode -- the GATHER class (mode 0x00 per db.json), which "
            "returns four unfiltered texels; on the same coordinate as msfilt "
            "its components are integers rather than the interpolated mean."),
    "msread": dict(
        kind="render", src="kernels/k_msread.metal", color_format=125,
        samples=1, width=W, height=H, tex_mip=_MIP,
        why="tex_sample.mode -- the integer-READ class (also mode 0x00): no "
            "sampler, no filter, no LOD, no derivative.  Per-level reads make "
            "'which level was read' readable off the returned value."),
    "mscmp": dict(
        kind="render", src="kernels/k_mscmp.metal", color_format=125,
        samples=1, width=W, height=H, tex_depth=(8, 8),
        why="tex_sample.mode -- the DEPTH-COMPARE class (third member of mode "
            "0x00).  Its result is confined to [0,1], so a class change is "
            "readable as leaving that interval."),
    "mslodq": dict(
        kind="render", src="kernels/k_mslodq.metal", color_format=125,
        samples=1, width=W, height=H, tex_mip=_MIP,
        why="tex_sample.mode -- the LOD-QUERY class (mode 0x20).  NO carrier in "
            "this corpus has ever emitted one; it needs a MIPMAPPED texture, "
            "which is why the harness gained one.  This is the carrier the field "
            "has been missing."),

    # =================================================== tex_deriv.dstsrc ===
    # DIMENSION: which REGISTER the derivative reads and which it writes.
    "deriv": dict(
        kind="render", src="kernels/k_deriv.metal", color_format=125,
        samples=1, width=W, height=H,
        why="tex_deriv.dstsrc -- EXP-0172's OWN carrier, MSL unchanged, so the "
            "quiet-machine pass re-measures the same thing.  The withheld "
            "verdict is about cross-run STABILITY (5 values disagreed, all of "
            "them fault-in-one-run / InnocentVictim-in-the-other at the values "
            "that hang), not about liveness -- 198 observations moved."),
    "deriv2": dict(
        kind="render", src="kernels/k_deriv2.metal", color_format=125,
        samples=1, width=W, height=H,
        why="tex_deriv.dstsrc -- a SECOND program, so stability is measured "
            "against a different register allocation: derivatives of ALU "
            "temporaries rather than of raw varyings, plus half-precision "
            "derivatives (a different operand width)."),

    # ============================ tex_write.amode / tex_write.rsv11 =========
    # The orchestrator's refusal is explicit and numeric: "swept densely on 6
    # arms but only 2 distinct carriers with proven detection power (the
    # pre-registered bar is 3)".  Those two were EXP-0163's twdim and twtype.
    # In amode's OWN dimension they are ONE carrier: every write in both is
    # write(colour, uint2(LITERAL, LITERAL)) at implicit level 0, and both report
    # amode == 0x54 on every occurrence.  Each carrier below differs from them
    # in a NAMED address-form or data-format respect.
    "twmip": dict(
        kind="render", src="kernels/k_twmip.metal", color_format=125,
        samples=1, width=W, height=H, tex_write=(8, 8), tex_write_mip=(8, 8, 3),
        why="tex_write.amode -- ADDRESS FORM: an EXPLICIT MIP LEVEL operand in "
            "the write address.  Every tex_write ever swept wrote implicit "
            "level 0."),
    "twbuf": dict(
        kind="render", src="kernels/k_twbuf.metal", color_format=125,
        samples=1, width=W, height=H, tex_write=(8, 8), tex_write_buf=64,
        why="tex_write.amode -- ADDRESS FORM: a texture_buffer destination, i.e. "
            "LINEAR one-dimensional texel addressing with a scalar index. "
            "db.json already recognises the buffer class as a distinct texture "
            "type on the sample side (tex_type == 3); no write carrier has ever "
            "used it."),
    "twcube": dict(
        kind="render", src="kernels/k_twcube.metal", color_format=125,
        samples=1, width=W, height=H, tex_write=(8, 8), tex_write_cube=8,
        why="tex_write.amode -- ADDRESS FORM: a CUBE destination.  db.json "
            "documents coord_dim 0x0c = cube for tex_write and NOTHING in the "
            "corpus has ever emitted it, so that address form is unexercised."),
    "twdyn": dict(
        kind="render", src="kernels/k_twdyn.metal", color_format=125,
        samples=1, width=W, height=H, tex_write=(8, 8),
        tex_write_arr=(8, 8, 4),
        why="tex_write.amode -- ADDRESS SOURCE and DATA SOURCE: every write ever "
            "swept used a COMPILE-TIME-CONSTANT uint2 literal, so the compiler "
            "never had to form the address from a register; db.json's sibling "
            "enum for this byte distinguishes exactly indexed-vs-GPR-index. It "
            "also carries a contiguous float4 store with NO ALU between load and "
            "write, the 0x54-vs-0x56 data-source split EXP-0141 found."),
    "twcomp": dict(
        kind="render", src="kernels/k_twcomp.metal", color_format=125,
        samples=1, width=W, height=H, tex_write=(8, 8),
        tex_write_r32=(8, 8), tex_write_rg32=(8, 8),
        why="tex_write.rsv11 -- WRITE-DATA FORMAT: ONE- and TWO-component "
            "destinations.  byte+11's positional sibling is device_store's "
            "st_desc_hi, the store data-format descriptor tail, whose "
            "neighbouring bit is documented as set only for a NON-4-component "
            "store.  Every destination ever swept was 4-component."),
}

# buffer contents per carrier, {buffer index: [u32 words already float-encoded]}
BUFS = {
    "twmip":  {0: BUF_TEX},
    "twbuf":  {0: BUF_TEX},
    "twcube": {0: BUF_TEX},
    "twdyn":  {0: BUF_TEX, 1: BUF_VEC4},
    "twcomp": {0: BUF_TEX},
}

# The fields this experiment is chartered to sweep.
TARGETS = {
    "tex_sample": ["mode"],
    "tex_deriv":  ["dstsrc"],
    "tex_write":  ["amode", "rsv11"],
}

# The dimension each target field controls, AUTHORED here so that any inert
# verdict rests on a named claim a reviewer can dispute (EXP-0172's practice).
DIMENSION = {
    "tex_sample.mode":
        "the SAMPLE-OPERATION CLASS: filtered sample (0x10) vs "
        "gather/read/sample_compare (0x00) vs LOD query (0x20).  Carriers must "
        "differ in which class they express, not merely in texture shape.",
    "tex_deriv.dstsrc":
        "the packed DESTINATION and SOURCE REGISTER of the quad-difference "
        "derivative.  Carriers must differ in register allocation and in which "
        "values are live around the op.",
    "tex_write.amode":
        "the ADDRESS FORM / OPERAND SOURCING of the texture store -- the same "
        "byte position and the same 0x54/0x56/0x44/0x64 vocabulary as "
        "device_load.addr_mode / device_store.addr_mode.  Carriers must differ "
        "in how the destination address is formed (constant vs register, "
        "implicit vs explicit level, 2D vs cube vs linear buffer) or in how the "
        "store data reaches the op (ALU-computed vs direct live load result).",
    "tex_write.rsv11":
        "the WRITE-DATA FORMAT DESCRIPTOR TAIL, by position the sibling of "
        "device_store.st_desc_hi.  Carriers must differ in the component count "
        "and width of the data actually written.",
}

# Fields in the dispatch that get NO device sweep, each with its named reason,
# pre-registered so the decision cannot be rewritten after the runs.
DECLINED = {
    "cubearray_coord_const.b3":
        "NOT SWEEPABLE AS A FIELD, and the evidence for that is now two "
        "independent experiments.  EXP-0148: the descriptor fires 0 times in "
        "1080 corpus files under both the strict and the resync walk -- in "
        "k_tex_array_cube, the kernel it is named after, its `f0 c0 04` "
        "signature sits at offset 48, INTERIOR to the 12-byte tex_addr_setup "
        "token spanning 40..52, so it can never be reached.  EXP-0187: 31 "
        "cube/cube-array constructs authored and compiled across 12 shapes "
        "(sample, array, nearest, LOD, gradientcube, bias, both gathers, "
        "depth-cube-array compare, half, read, dynamic index) with 0 signature "
        "hits and 0 walk hits.  There is no program in which to splice b3, so a "
        "sweep cannot be built; a bigger sweep is not the missing ingredient.  "
        "EXP-0204 therefore runs the ONE probe that is still informative and is "
        "not a field sweep -- see PRE_REGISTRATION sec.7, the SYNTHESIS probe -- "
        "and reports b3 as UNRESOLVED either way.",
}
