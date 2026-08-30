#!/usr/bin/env python3
"""carriers.py -- EXP-0172 carrier definitions (FROZEN at pre-registration).

One entry per authored MSL program in kernels/, with the EXACT pipeline
descriptor it is built and run with.  Imported by analysis/census.py (pre-freeze
calibration) and by run.py (capture), so the census and the gated runs cannot
disagree about what was built.

Every carrier states, in `why`, WHICH of this experiment's fields it makes
reachable and -- for the fields that never moved before -- WHICH DIMENSION it
differs in from the carrier that already read them inert.  A carrier that does
not differ in that dimension is not a second carrier (EXP-0164 / iter_at.loc).

Carriers marked `[from EXP-0163]` are that experiment's authored MSL, copied
into kernels/ unchanged so this experiment is self-contained.

CLEAN-ROOM: OWN-SHADER.  Only our own MSL is described.
"""

W = H = 16

# Probe points, shared with EXP-0155/EXP-0163 so observations are comparable.
PROBE_PIXELS = [(8, 8), (5, 10), (11, 5), (5, 9), (3, 10), (11, 6), (7, 10)]
PROBE_LANES = [0, 1, 5, 17, 31]
PROBE_TEXELS = [(1, 0), (3, 2), (5, 4), (7, 6), (0, 0), (7, 7)]

# buffer(0) contents, per carrier.
BUF_TEX = [1.0, 0.0, 3.0, 2.0, 5.0, 4.0,      # [0..5] normalised sample coords
           6.0, 7.0,                          # [6],[7] sentinel factors 6*7=42
           11.0, 12.0, 13.0, 14.0,            # [8..11]  colour 0
           21.0, 22.0, 23.0, 24.0,            # [12..15] colour 1
           31.0, 32.0, 33.0, 34.0]            # [16..19] colour 2
BUF_VSRC = [5.0, 6.0, 7.0, 900.0, 901.0, 902.0] + [0.0] * 14
# Integer texel coordinates into the 8x8 R32Float source texture whose content is
# texel(x,y) = x + 100*y, so each read names its own texel: 201, 605, 7, 700.
BUF_TEXREAD_U32 = [1, 2, 5, 6, 7, 0, 0, 7,
                   17, 34, 51, 68] + [0] * 8

CARRIERS = {
    # ---------------------------------------------------------------- get_sr
    "srwide": dict(
        kind="compute", src="kernels/k_srwide.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="get_sr.form -- db.json calls form a datapath/WIDTH modifier 'set for "
            "the position-in-grid SR family'. This carrier reads ONLY the "
            "multi-component (uint3) SR family, so form is natively 1 on its "
            "occurrences. Its controlled sibling srnarrow reads only scalar SRs. "
            "EXP-0140 swept form on one carrier; EXP-0164 withheld it as "
            "never-moved-on-one-carrier."),
    "srnarrow": dict(
        kind="compute", src="kernels/k_srnarrow.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="get_sr.form -- the SCALAR-SR control for srwide. Same kernel shape, "
            "same output surface, only the SR WIDTH differs, which is the "
            "dimension db.json says form controls."),

    # ---------------------------------------------------------------- falu2i
    "fimm": dict(
        kind="compute", src="kernels/k_fimm.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="falu2i.imm_flag -- bit8 sits INSIDE db.json's own imm_decode(). The "
            "dimension it controls is the decoded immediate, so this carrier "
            "spans the minifloat domain (1/32 .. 30) under fadd and fmul rather "
            "than using one constant as EXP-0138's single carrier did."),
    "fimm2": dict(
        kind="compute", src="kernels/k_fimm2.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="falu2i.imm_flag -- structurally different arm: negative immediates "
            "(imm_sign=1), fma-shaped uses, and immediates applied to a freshly "
            "LOADED operand (the mods==0xC0 form of EXP-0101)."),

    # --------------------------------------------- irotate / the 0x54 byte+2
    "rot": dict(
        kind="compute", src="kernels/k_rot.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="irotate.b2 -- EXP-0166 recommendation 4. EXP-0146's arm reached 32 "
            "of 256 encodings through assemble()'s OR defect; this sweep patches "
            "bytes directly and the raw is checked for 256 DISTINCT byte strings. "
            "Sources are reused after the rotate (live-source side of the "
            "last-use dimension)."),
    "rot2": dict(
        kind="compute", src="kernels/k_rot2.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="irotate.b2 -- second structurally different rotate carrier: results "
            "feed the SIMD network and a threadgroup round-trip, sources are "
            "16-bit and lane-derived."),
    "deadsrc": dict(
        kind="compute", src="kernels/k_deadsrc.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="irotate.b2 + simd_ballot.cache + simd_shuffle.cache -- all three are "
            "the same 0x54 operand byte at byte+2, and db.json's vocabulary for a "
            "byte in that role (falu_acc, RT-1a-FIX) is 'a source cache / LAST-USE "
            "hint'. Every carrier ever swept for these reuses its sources, so they "
            "are ONE carrier in that dimension. Here every operand is loaded, used "
            "once, and dead immediately after."),

    # ------------------------------------------------- simd (from EXP-0163)
    "sball": dict(
        kind="compute", src="kernels/k_sball.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="[from EXP-0163] simd_ballot.cache / simd_shuffle.cache live-source "
            "reference arm; every ballot form the language offers, each result "
            "consumed several times."),
    "scache": dict(
        kind="compute", src="kernels/k_scache.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="[from EXP-0163] simd cache/last-use reference arm."),
    "stype": dict(
        kind="compute", src="kernels/k_stype.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="[from EXP-0163] the mode==0x06 rotate / shuffle-and-fill form and the "
            "16/64-bit operand widths; the only carrier on which simd_shuffle.rsv9 "
            "ever moved."),
    "sdiv": dict(
        kind="compute", src="kernels/k_sdiv.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="[from EXP-0163] SIMD ops under a partially active mask."),

    # ------------------------------------------------ tex_sample.coord
    "texread": dict(
        kind="render", src="kernels/k_texread.metal", color_format=125,
        samples=1, width=W, height=H, tex_sample=(8, 8),
        why="tex_sample.coord -- EXP-0155's movement did not reproduce (73-93% "
            "cross-run agreement). coord is a REGISTER INDEX, so a swept value "
            "points the coordinate operand at an arbitrary register; on a filtered "
            "sample that feeds garbage derivatives, an arbitrary LOD and an "
            "arbitrary wrap. read(uint2) has no sampler, derivative, LOD or "
            "filter, so the per-value outcome should be run-invariant."),
    "texmix": dict(
        kind="render", src="kernels/k_texmix.metal", color_format=125,
        samples=1, width=W, height=H, tex_sample=(8, 8),
        why="tex_sample.coord -- the same descriptor reached through three "
            "operation kinds (explicit-LOD sample, gather, integer read) in one "
            "program, so a coord verdict is not a property of one kind. Every "
            "operation is derivative-free."),

    # ---------------------------------------- imageblock_store (from EXP-0163)
    "ibsamp": dict(
        kind="render", src="kernels/k_ibsamp.metal", color_format=125,
        samples=1, width=W, height=H, tex_sample=(8, 8), buf0=BUF_TEX,
        why="[from EXP-0163] imageblock_store.src baseline shape (single "
            "RGBA32Float attachment, texture-sampling fragment program)."),
    "ibhalf": dict(
        kind="render", src="kernels/k_ibhalf.metal", color_format=115,
        samples=1, width=W, height=H, tex_sample=(8, 8), buf0=BUF_TEX,
        why="[from EXP-0163] imageblock_store.src with a HALF attachment format."),
    "ibmrt": dict(
        kind="render", src="kernels/k_ibmrt.metal", color_format=125,
        samples=1, rt_count=3, width=W, height=H, tex_sample=(8, 8), buf0=BUF_TEX,
        why="[from EXP-0163] imageblock_store.src with THREE render targets."),
    "ibms4": dict(
        kind="render", src="kernels/k_ibsamp.metal", color_format=125,
        samples=4, resolve=True, width=W, height=H, tex_sample=(8, 8),
        buf0=BUF_TEX,
        why="[from EXP-0163] imageblock_store.src at 4 samples."),

    # ------------------------------------------- vary_slot.slot (from EXP-0163)
    "vmany": dict(
        kind="render", src="kernels/k_vmany.metal", color_format=125,
        samples=1, width=W, height=H,
        why="vary_slot.slot -- 16 scalar varyings force slots past 7, where the "
            "slot descriptor has something to say. EXP-0155 saw slot move 3 of 256 "
            "in one run and 0 in the other (noise) on a 4-varying carrier."),
    "vhalf": dict(
        kind="render", src="kernels/k_vhalf.metal", color_format=125,
        samples=1, width=W, height=H,
        why="vary_slot.slot -- half / vector varying widths."),
    "vflat": dict(
        kind="render", src="kernels/k_vflat.metal", color_format=125,
        samples=1, width=W, height=H,
        why="vary_slot.slot -- flat / no-perspective interpolation class."),
    "vsrc": dict(
        kind="render", src="kernels/k_vsrc.metal", color_format=125,
        samples=1, width=W, height=H, buf0=BUF_VSRC,
        why="vary_slot.slot -- varyings sourced from memory / immediates / "
            "computed values rather than one class."),

    # -------------------------------------------------- tex_deriv.dstsrc
    "deriv": dict(
        kind="render", src="kernels/k_deriv.metal", color_format=125,
        samples=1, width=W, height=H,
        why="tex_deriv.dstsrc -- the ONLY field left blocking tex_deriv, and the "
            "ISA database has never had a carrier authored for it: every previous "
            "0x37 in the corpus was incidental to implicit-LOD sampling. Eight "
            "independent derivatives of three varyings with different gradients, "
            "each in its own output channel, across BOTH axis values (0x92 dfdx / "
            "0x90 dfdy) and the fwidth abs+add form -- so the arm list spans the "
            "axis dimension inside one program and a dst- or src-register "
            "redirect is an exact numeric change, not noise."),

    # ------------------------------------------------------ TIER 2 carriers
    "tgat": dict(
        kind="compute", src="kernels/k_tgat.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="frame_marker_compact.b1 -- the 2-byte 60 <b1> word was length-anchored "
            "in a threadgroup-atomics kernel and has never been swept on hardware."),
    "cfdiv": dict(
        kind="compute", src="kernels/k_cfdiv.metal", function="k_simd",
        grid=32, tg=32, out_bytes=2048,
        why="n4_cf_word.b3 -- the 04 01 00 <b3> control word was located before "
            "pop_reconverge / threadgroup_barrier in divergent-CF kernels; this is "
            "nested data-dependent divergence with reconvergence points."),
}


# ---------------------------------------------------------------------------
# The fields this experiment is chartered to sweep, and the mnemonics the
# pre-freeze census must therefore look for.  TIER is the pre-registered
# priority; DECLINED fields are listed with their named reason and get NO device
# time (FIELD-SWEEP-PROTOCOL: "a field declined with a named reason is a real
# deliverable").
TARGETS = {
    # ---- TIER 1: a real chance of promotion, strongest oracle first ----
    "falu2i":               ["imm_flag"],
    "get_sr":               ["form"],
    "tex_sample":           ["coord"],
    "vary_slot":            ["slot"],
    "tex_deriv":            ["dstsrc"],
    # ---- TIER 2: swept for the record; promoted only if genuinely LIVE ----
    "imageblock_store":     ["src"],
    "irotate":              ["b2"],
    "simd_ballot":          ["cache"],
    "simd_shuffle":         ["cache"],
    "frame_marker_compact": ["b1"],
    "n4_cf_word":           ["b3"],
    # ---- TIER 3: swept for the record, promotion DECLINED IN ADVANCE ----
    "ret":                  ["scoreboard"],
    "dev_scoreboard_fence": ["scope_flag"],
}

# Fields in this experiment's charter that get NO device time, each with the
# reason.  Pre-registered so the decision cannot be rewritten after the runs.
DECLINED = {
    "cubearray_coord_const.b3":
        "UNSWEEPABLE, not merely untested. EXP-0148 found the descriptor fires "
        "0 times in 1080 corpus files under both the strict and the resync walk: "
        "its `f0 c0 04` signature in k_tex_array_cube sits at offset 48, INTERIOR "
        "to the 12-byte tex_addr_setup token spanning 40..52, so it can never be "
        "reached. Its only exercise is the literal 4-byte string in "
        "roundtrip_test.py -- and a round trip is not an emitter gate "
        "(FIELD-SWEEP-PROTOCOL sec.3b). There is no program in which to splice "
        "b3. RECOMMENDATION: this is a descriptor-existence question for the "
        "orchestrator (delete or re-anchor), not a sweep.",
    "half_alu_fma12.ext":
        "BLOCKED BY A DESCRIPTOR DEFECT. half_alu_fma12 is flagged `emit_unsafe` "
        "in db.json because its modelled length OVER-CONSUMES the following "
        "instruction's leader (FIELD-SWEEP-PROTOCOL sec.6 known list), and `ext` "
        "is the 64-bit unmodelled remainder -- i.e. exactly the bytes the length "
        "defect puts in doubt. Sweeping it would sweep the NEXT instruction. The "
        "length must be fixed before the field means anything.",
    "mesh_out_src.sel":
        "NO CARRIER. mesh_out_src is MESH-stage-only and harness/gfrun2.m has no "
        "mesh pipeline (MTLMeshRenderPipelineDescriptor) at all. Authoring one is "
        "a harness project with its own pre-registration, not a field sweep; "
        "attempting it inside this experiment would mean building an unvalidated "
        "render path and a frozen contract at the same time.",
    "imageblock_store.src (as an INSTRUCTION closure)":
        "SWEPT (tier 2) but it does NOT close the instruction: the live worklist "
        "now shows imageblock_store TWO fields away (`src` + `b4`), and `b4` is "
        "EXP-0163's INERT-ROBUST result, which rule 8 caps at "
        "single-template-inference. Promoting `src` is a field win only.",
    "ret.scoreboard / dev_scoreboard_fence.scope_flag":
        "PROMOTION DECLINED IN ADVANCE (they are still swept, for the record). "
        "Both are ORDERING controls -- an execution/scoreboard-wait mask and a "
        "memory-fence scope. This harness has no ordering observable: it reads "
        "back after command-buffer completion, which flushes. A carrier that "
        "moves therefore proves GENERAL sensitivity to the byte, not "
        "ordering-specific power, which is why three prior experiments declined "
        "to promote this family. We decline for the same reason and say so, "
        "rather than promoting on a general-sensitivity result.",
}
