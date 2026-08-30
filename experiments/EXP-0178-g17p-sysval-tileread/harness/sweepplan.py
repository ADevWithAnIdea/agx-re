#!/usr/bin/env python3
"""EXP-0178 FROZEN sweep plan.

Pure data + HOST-COMPUTED oracles. Nothing in this module touches the GPU, so
every expected value exists before any dispatch (FIELD-SWEEP-PROTOCOL section 3.4).
Field geometry is read from the PINNED db only (harness/pinned_isa.py); nothing
here hand-computes a bit offset.

CO-VARIATION AUDIT (section 3a) is machine-checked by analysis/covary_audit.py
against the `observable` / `never_spliced` keys each arm declares below.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinned_isa                                              # noqa: E402

SYSVAL_KERNEL = "kernels/sysval.metal"
TILEBUF_KERNEL = "kernels/tilebuf.metal"

# ---------------------------------------------------------------- constants --
# Asymmetric, none equal to 0 or 1, chosen so that for every carrier the CORRECT
# value, the SILENT-ZERO value and the CLEAR value differ in every component.
DST0 = [0.25, 0.5, -1.0, 2.0]
DST1 = [3.0, -4.0, 5.0, 6.0]
DST2 = [-0.75, 7.0, 1.5, -2.5]
SRC = [1.0, -2.0, 3.0, 0.5]
VP = [0.5, 0.25, 0.125, 1.0]
DST0_ALT = [-7.0, 11.0, 0.75, -0.5]      # liveness control: second clear colour
SRC_ALT = [9.0, 0.125, -6.0, 4.0]        # liveness control: second uniform

# Compute-carrier dispatch. EXP-0169's G17P get_sr arm died at grid=1/tg=1,
# where every reachable SR reads 0.
CGRID = CTG = 64
SR_BIAS = 1000                            # k_sr_c adds this after the SR read
POISON_U32 = 0xDEADBEEF
SENTINEL_U32 = 0xA5A5A5A5

# Vertex-carrier draw parameters (indexed draw; the only form that gives
# [[base_vertex]] / [[base_instance]] non-zero values).
BASE_VERTEX = 9
BASE_INSTANCE = 5
VS_INSTANCES = 3

# Pre-registered pixel-centre offset for the fragment [[position]] carrier.
# C is CONFIRMED (not fitted) against the baseline case before any swept case is
# classified; see run.py::calibrate_frag. If the baseline refutes the affine
# model the fragment arm's SEMANTIC oracle is withdrawn and only the movement
# oracle stands. The offset itself is a documented open question
# (EXP-0177 section 4: "the instruction supplying the +0.5 pixel-centre offset").
FRAG_CENTRE_C = 0.5


# ------------------------------------------------------------- SR semantics --
# The ONLY sysval oracle table in this experiment. Values come from the PINNED
# db.json enum for `get_sr.sr_sel` plus the dispatch geometry -- they are what
# db.json CLAIMS, so a mismatch is a falsification of the documented meaning and
# is recorded as such, never quietly re-fitted. Selectors absent from a table
# have NO semantic oracle in that stage; those cases carry oracle=None and are
# classified by the analysis (KNOWN_MATCH / ALIAS / CONSTANT / STRUCTURED /
# IDENTITY_MATERIALIZE), which is how EXP-0092 reported the same sweep on M4.

def sr_oracle_compute(sel, exec_width, grid=CGRID, tg=CTG):
    """Expected 64-thread raw SR pattern, or None if undocumented in this stage."""
    t = list(range(grid))
    if sel == 0x82: return [i % exec_width for i in t]           # simd_lane_id
    if sel == 0x85: return [i // exec_width for i in t]          # simd_group_id
    if sel == 0x98: return [tg] * grid                           # threads_per_tg.x
    if sel in (0x99, 0x9a): return [1] * grid                    # threads_per_tg.y/z
    if sel in (0x9c, 0x9d, 0x9e): return [0] * grid              # tg_position_in_grid
    if sel == 0xa0: return list(t)                               # thread_pos_in_grid.x
    if sel in (0xa1, 0xa2): return [0] * grid
    if sel == 0xa4: return list(t)                               # thread_pos_in_tg.x
    if sel in (0xa5, 0xa6): return [0] * grid
    if sel == 0xa7: return list(t)                               # thread_index_in_tg
    if sel in (0xa8, 0xa9, 0xaa): return [1] * grid              # threadgroups_per_grid
    return None


def sr_oracle_frag(sel, W, H):
    """Expected raw SR value per pixel (row-major, W*H), or None."""
    if sel == 0xa0: return [px for py in range(H) for px in range(W)]
    if sel == 0xa1: return [py for py in range(H) for px in range(W)]
    if sel == 0xc5: return [0] * (W * H)   # our triangle is CW in NDC; default
                                           # frontFacingWinding is CCW -> back
    return None


def sr_oracle_vertex(sel):
    """Expected raw SR value at the THREE triangle corners, or None.
    Corner i is the vertex with k = vid % 3 == i (see kernels/sysval.metal)."""
    if sel == 0xdd: return [BASE_VERTEX + i for i in range(3)]        # vertex_id
    if sel == 0xd8: return [BASE_INSTANCE + VS_INSTANCES - 1] * 3     # last instance wins
    if sel == 0x88: return [BASE_VERTEX] * 3                          # base_vertex
    if sel == 0x8a: return [BASE_INSTANCE] * 3                        # base_instance
    return None


# ------------------------------------------------- barycentric interpolation --

def bary(verts, px, py, W, H):
    """Weights of the centre of pixel (px,py) in a WxH target, for a clip-space
    triangle. Metal viewport: ndc_x = 2*(px+0.5)/W - 1, ndc_y = 1 - 2*(py+0.5)/H.
    All our vertices have w == 1, so perspective-correct == linear here."""
    nx = 2.0 * (px + 0.5) / W - 1.0
    ny = 1.0 - 2.0 * (py + 0.5) / H
    (x0, y0), (x1, y1), (x2, y2) = verts
    den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    l0 = ((y1 - y2) * (nx - x2) + (x2 - x1) * (ny - y2)) / den
    l1 = ((y2 - y0) * (nx - x2) + (x0 - x2) * (ny - y2)) / den
    return (l0, l1, 1.0 - l0 - l1)


# v_sr / v_full: k=0 -> (-1,-1), k=1 -> (-1,3), k=2 -> (3,-1)
TRI_SR = [(-1.0, -1.0), (-1.0, 3.0), (3.0, -1.0)]
# v_arr: p[0]=(-1,-1) p[1]=(3,-1) p[2]=(-1,3)
TRI_ARR = [(-1.0, -1.0), (3.0, -1.0), (-1.0, 3.0)]


# ------------------------------------------------------------ tile  oracles --

def o_tile(dst0, src, W, H, **_):
    return [[dst0[k] * 2.0 + src[k] for k in range(4)] for _ in range(W * H)]

def o_tile_zero(dst0, src, W, H, **_):
    return [[src[k] for k in range(4)] for _ in range(W * H)]

def o_tile2(dst0, src, W, H, **_):
    a = [[dst0[k] * -3.0 + src[k] * 0.5 for k in range(4)] for _ in range(W * H)]
    b = [[src[k] * 7.0 - [0.125, 0.25, 0.5, 1.0][k] for k in range(4)] for _ in range(W * H)]
    return a + b

def o_tile2_zero(dst0, src, W, H, **_):
    a = [[src[k] * 0.5 for k in range(4)] for _ in range(W * H)]
    b = [[src[k] * 7.0 - [0.125, 0.25, 0.5, 1.0][k] for k in range(4)] for _ in range(W * H)]
    return a + b

def o_mrt(dst0, dst1, src, W, H, **_):
    r0 = [[dst0[k] * 2.0 + src[k] for k in range(4)] for _ in range(W * H)]
    r1 = [[dst1[k] * 4.0 - src[k] for k in range(4)] for _ in range(W * H)]
    return r0 + r1

def o_mrt_zero(dst0, dst1, src, W, H, **_):
    """The tile_read_mrt under test feeds attachment 1 only (byte+5 baseline
    0x08), so a zeroed READ collapses attachment 1 and leaves attachment 0."""
    r0 = [[dst0[k] * 2.0 + src[k] for k in range(4)] for _ in range(W * H)]
    r1 = [[-src[k] for k in range(4)] for _ in range(W * H)]
    return r0 + r1

def o_mrt3(dst0, dst1, dst2, src, W, H, **_):
    r0 = [[dst0[k] * 2.0 + src[k] for k in range(4)] for _ in range(W * H)]
    r1 = [[dst1[k] * 4.0 - src[k] for k in range(4)] for _ in range(W * H)]
    r2 = [[dst2[k] * -0.5 + src[k] * 3.0 for k in range(4)] for _ in range(W * H)]
    return r0 + r1 + r2


# ------------------------------------------------------------- coverage rule --

def dense(width):
    return list(range(1 << width))

def wide_values(width):
    """FIELD-SWEEP-PROTOCOL 3.3 for w > 8: boundaries, every power of two, and
    >=16 asymmetric interior samples. Applied ON TOP OF the per-constituent-byte
    dense sweep, exactly as our own EXP-0147 did."""
    mx = (1 << width) - 1
    vals = [0, 1, 2, mx - 1, mx] + [1 << k for k in range(width)]
    vals += [v & mx for v in (0x5A, 0xA5A5, 0x0F0F0F, 0xDEADBEEF, 0x12345678,
                              0x80000001, 0x7FFFFFFE, 0xCAFEF00D, 0x00FF00FF,
                              0xFF00FF00, 0x33333333, 0xCCCCCCCC, 0x01234567,
                              0x89ABCDEF, 0xFEDCBA98, 0x76543210)]
    seen, out = set(), []
    for v in vals:
        if v not in seen:
            seen.add(v); out.append(v)
    return out


# ------------------------------------------------------------------- arms ----
# `fields`      -- ruled on; a verdict is emitted for each.
# `foreign`     -- swept and recorded, NO verdict (another experiment owns the
#                  field name): get_sr.dst -> EXP-0168, get_sr.form -> EXP-0172.
# `not_swept`   -- deliberately excluded, with the reason, so the omission is
#                  auditable rather than silent.
# `ladder`      -- pre-registered to MOVE. A carrier that fails any step has no
#                  demonstrated detection power and ALL its verdicts stay
#                  `untested` (the iter_at.loc / EXP-0169 failure mode).
# `power_probe` -- pre-registered to land on a SPECIFIC host-computed value,
#                  proving the measurement can see the instruction's
#                  contribution change.
# `sensitivity` -- pre-registered to FAIL (observation must NOT equal baseline).

ARMS = [
    # ------------------------------------------------------------- get_sr ----
    dict(arm="sr_compute", instr="get_sr", stage="compute",
         kernel=SYSVAL_KERNEL, func="k_sr_c", grid=CGRID, tg=CTG,
         anchor_sr=0x82, oracle="sr_compute",
         observable="out[gid] written by a SEPARATE device_store whose index "
                    "register comes from a DIFFERENT, unspliced get_sr (0xa0); "
                    "the value passes through a SEPARATE later add (+1000)",
         never_spliced=["the gid get_sr (0xa0)", "the iadd2", "the device_store",
                        "the sentinel store"],
         fields=["sr_sel", "dp_width", "dp_marker"],
         foreign={"dst": "EXP-0168 owns the field name `dst`",
                  "form": "EXP-0172 owns get_sr.form"},
         not_swept={"dst_hi": "values 6-7 select registers >= 96; EXP-0155 "
                              "measured that crossing on G17P as a HANG across "
                              "seven fields. Already hardware-run/G17P via "
                              "EXP-0168. Excluded on safety, not convenience."},
         ladder=[("L_sr_sel", "sr_sel", 0xa0,
                  "0x82 (lane = t%%W) -> 0xa0 (t) must move: two DIFFERENT "
                  "host-computable 64-thread patterns"),
                 ("L_dst", "dst", None,
                  "relocating the destination GPR must break the +1000 chain "
                  "the store reads, so the observation must move")],
         power_probe=("sr_sel", 0x9d,
                      "threadgroup_position_in_grid.y is 0 in a single-threadgroup "
                      "dispatch, so every slot must read exactly SR_BIAS: proves "
                      "the measurement can see the SR read collapse to zero"),
         sensitivity=("byte0_bit2", 0,
                      "clear byte0 bit 2 and the 4 bytes are no longer a get_sr; "
                      "the observation MUST NOT equal the baseline")),

    dict(arm="sr_frag", instr="get_sr", stage="fragment",
         kernel=SYSVAL_KERNEL, vs="v_full", fs="f_sr", nrt=1, samples=1,
         W=4, H=4, anchor_sr=0xa0, oracle="sr_frag",
         observable="colour channel .r of a 4x4 attachment. .g is fed by a "
                    "DIFFERENT unspliced get_sr (0xa1) and .a by the uniform "
                    "alone; both are integrity sentinels on paths the "
                    "instruction under test cannot name",
         never_spliced=["the pos.y get_sr (0xa1)", "frag_color_store",
                        "the vertex program"],
         fields=["sr_sel", "dp_width", "dp_marker"],
         foreign={"dst": "EXP-0168", "form": "EXP-0172"},
         not_swept={"dst_hi": "same G17P register-ceiling hang region"},
         ladder=[("L_sr_sel", "sr_sel", 0xa1,
                  "pixel X -> pixel Y: a clean mutual swap, both patterns "
                  "host-computable and different at 4x4 (EXP-M4-14's method)"),
                 ("L_dst", "dst", None, "relocating the destination GPR must move .r")],
         power_probe=("sr_sel", 0x9c,
                      "threadgroup_position_in_grid.x has no fragment meaning; "
                      "pre-registered expectation is a CONSTANT across all 16 "
                      "pixels, i.e. the spatial structure of .r disappears while "
                      ".g and .a stay correct"),
         sensitivity=("byte0_bit2", 0, "must not equal the baseline")),

    dict(arm="sr_vertex", instr="get_sr", stage="vertex",
         kernel=SYSVAL_KERNEL, vs="v_sr", fs="f_sv", nrt=1, samples=1,
         W=4, H=4, anchor_sr=0xd8, oracle="sr_vertex",
         draw="indexed", basevertex=BASE_VERTEX, baseinstance=BASE_INSTANCE,
         instances=VS_INSTANCES,
         observable="colour channel .r, the interpolated varying the vertex "
                    "stage wrote. The triangle's GEOMETRY is driven by a "
                    "DIFFERENT, unspliced get_sr (vertex_id 0xdd), so a spliced "
                    "selector can never move the coverage the observation is "
                    "read from. .a is a uniform-only integrity sentinel",
         never_spliced=["the vertex_id get_sr (0xdd) that drives position",
                        "vary_store", "the fragment program"],
         fields=["sr_sel", "dp_width", "dp_marker"],
         foreign={"dst": "EXP-0168", "form": "EXP-0172"},
         not_swept={"dst_hi": "same G17P register-ceiling hang region"},
         ladder=[("L_sr_sel", "sr_sel", 0xdd,
                  "instance_id (FLAT 7) -> vertex_id (RAMP 9,10,11): two "
                  "different host-computable 16-pixel patterns"),
                 ("L_dst", "dst", None, "relocating the destination GPR must move .r")],
         power_probe=("sr_sel", 0x9c,
                      "no documented vertex meaning; pre-registered expectation "
                      "is a FLAT field, i.e. the varying loses the value under "
                      "test while .a stays correct"),
         sensitivity=("byte0_bit2", 0, "must not equal the baseline")),

    # ---------------------------------------------------------- tilebuffer ----
    dict(arm="tile_ct1", instr="tile_read", stage="fragment",
         kernel=TILEBUF_KERNEL, vs="v_arr", fs="f_tile", nrt=1, samples=1,
         W=2, H=2, pattern=["670e54"], oracle="tile",
         observable="the 2x2 colour attachment, written by frag_color_store -- "
                    "an instruction no arm here splices",
         never_spliced=["frag_color_store", "the ALU consuming the read",
                        "the vertex program"],
         fields=["b2", "dst", "b4", "rt_index", "read_en", "b6_hi", "b7", "tail"],
         foreign={}, not_swept={},
         ladder=[("L_dst", "dst", 0x02,
                  "relocating the read's destination GPR while the consuming ALU "
                  "still reads the ORIGINAL register must change the pixel"),
                 ("L_rt", "rt_index", 0x02,
                  "an unbound render-target index must change the pixel")],
         power_probe=("b7", 0x00,
                      "EXP-0147's litmus: byte+7 -> 0x00 makes the tile read "
                      "return ZERO, so the pixel must collapse from dst*2+src to "
                      "src alone on every pixel and every component"),
         sensitivity=("byte1", 0x55,
                      "byte+1 is part of the descriptor match; the observation "
                      "MUST NOT equal the baseline")),

    dict(arm="tile_ct2", instr=None, stage="fragment",
         kernel=TILEBUF_KERNEL, vs="v_arr", fs="f_tile2", nrt=2, samples=1,
         W=4, H=4, pattern=["670e54", "670654"], oracle="tile2",
         observable="attachment 0 of a 4x4 2-attachment pass; attachment 1 is "
                    "written WITHOUT a tilebuffer read and is an integrity "
                    "sentinel on an independent path",
         never_spliced=["both frag colour stores", "the vertex program"],
         fields=["b2", "dst", "b4", "rt_index", "read_en", "b6_hi", "b7", "fmt", "tail"],
         foreign={}, not_swept={},
         ladder=[("L_dst", "dst", 0x02, "must change attachment 0"),
                 ("L_rt", "rt_index", 0x02, "must change attachment 0")],
         power_probe=[("b7", 0x00,
                       "byte+7 -> 0x00 must collapse attachment 0 to src*0.5 while "
                       "attachment 1 stays exactly correct"),
                      ("fmt", 0x00,
                       "same litmus if this carrier resolves to tile_read_mrt, "
                       "where byte+7 is `fmt` rather than `b7`")],
         sensitivity=("byte1", 0x55, "must not equal the baseline"),
         note="SECOND, structurally different carrier for the tile_read family: "
              "attachment COUNT, spatial extent, arithmetic and a second "
              "non-reading store all differ from CT1. Which anchor it compiles "
              "to is resolved from the compiled bytes BEFORE the first gated "
              "dispatch and recorded in 00_arm_resolution.json; the arm is "
              "attributed to the instruction actually found, and its field list "
              "is intersected with that descriptor's real field names."),

    dict(arm="mrt_cm1", instr="tile_read_mrt", stage="fragment",
         kernel=TILEBUF_KERNEL, vs="v_arr", fs="f_mrt", nrt=2, samples=1,
         W=1, H=1, pattern=["670654"], oracle="mrt",
         observable="attachment 1 of a 1x1 2-attachment pass; attachment 0 is "
                    "produced by the OTHER tilebuffer read and is never spliced",
         never_spliced=["the attachment-0 tile read", "both colour stores",
                        "the vertex program"],
         fields=["dst", "b4", "rt_index", "read_en", "b6_hi", "fmt", "tail"],
         foreign={}, not_swept={},
         ladder=[("L_dst", "dst", 0x0a, "must change attachment 1"),
                 ("L_rt", "rt_index", 0x0a, "an unbound index must change attachment 1")],
         power_probe=("fmt", 0x00,
                      "byte+7 -> 0x00 must collapse attachment 1 to -src "
                      "(the tile read returns zero) while attachment 0 stays correct"),
         sensitivity=("byte1", 0x55, "must not equal the baseline")),

    dict(arm="mrt_cm2", instr="tile_read_mrt", stage="fragment",
         kernel=TILEBUF_KERNEL, vs="v_arr", fs="f_mrt3", nrt=3, samples=1,
         W=2, H=2, pattern=["670654"], oracle="mrt3",
         observable="the attachment selected by the spliced instruction's "
                    "baseline rt_index in a THREE-attachment 2x2 pass; the other "
                    "two attachments are integrity sentinels",
         never_spliced=["the other two tile reads", "all three colour stores",
                        "the vertex program"],
         fields=["dst", "b4", "rt_index", "read_en", "b6_hi", "fmt", "tail"],
         foreign={}, not_swept={},
         ladder=[("L_dst", "dst", 0x0a, "must change the observed attachment"),
                 ("L_rt", "rt_index", 0x0a, "must change the observed attachment")],
         power_probe=("fmt", 0x00,
                      "byte+7 -> 0x00 must collapse the observed attachment to "
                      "its no-read form while the other two stay correct"),
         sensitivity=("byte1", 0x55, "must not equal the baseline"),
         note="SECOND, structurally different carrier for tile_read_mrt: THREE "
              "bound attachments instead of two widens exactly the dimension "
              "`rt_index` selects, and 2x2 instead of 1x1 adds spatial extent."),
]

# ------------------------------------------------------ per-field coverage ----

def field_values(mnemonic, field):
    """The frozen value list for a field, from the PINNED geometry.
    w <= 8  -> every value.
    w >  8  -> every value of each constituent BYTE (holding the others at their
               baseline) PLUS the structured whole-field set of wide_values()."""
    start, width, rng = pinned_isa.field_geometry(mnemonic, field)
    if width <= 8:
        return ("dense", dense(width), rng, start, width)
    return ("perbyte+structured", wide_values(width), rng, start, width)


def hang_policy():
    """FIELD-SWEEP-PROTOCOL section 8 and rule 3(c), resolved at DESIGN time.

    There is deliberately **no per-field hang budget and no per-arm abort**.
    Rule 3(c) exists because a budget cannot characterise a CONTIGUOUS hazard --
    it guarantees the region is never mapped, since a budget of 2 discovers
    exactly two more bad values per run (`frag_color_pack.dst`'s wall at 0xC0
    was walked into by three experiments and seen by none). The counter-example
    is EXP-0169's DSTORE arm, whose harness had no budget and no abort path: it
    dispatched all 256 values of every field regardless of outcome and mapped
    two contiguous fault walls EXACTLY inside the gated run --
    `device_store.index_reg` faults iff (v & 0x60) == 0x60 (64 values, zero
    counterexamples, both carriers, both runs) and `extmode` faults iff
    v >= 0xFC. EXP-0168's own mapping pass showed the device survives such a
    region: 64 hangs, no reset, no wedge, no macvdmtool.

    So: FULL RANGE ALWAYS, and the contiguity of any hazard is a RESULT of the
    gated run rather than something a later pass has to go back for. The only
    stop is a global circuit breaker against a runaway.
    """
    return dict(
        per_field_budget=None,
        per_arm_abort=False,
        global_circuit_breaker=128,
        rationale=(
            "rule 3(c): a per-field budget guarantees a contiguous region is "
            "never mapped. Full-range dispatch maps it in the gated run."),
        known_risk=[
            "tile_read.dst / tile_read_mrt.dst byte+3 top of range: EXP-0147 "
            "recorded `fault` at 0xf6-0xff on M4; the analogous register-ceiling "
            "crossing HANGS on G17P (EXP-0155, seven fields). This range is "
            "dispatched deliberately, and PROGRESS.md carries the courtesy "
            "notice FIELD-SWEEP-PROTOCOL section 7 asks for.",
            "get_sr.dst_hi is NOT swept at all: values 6-7 select registers "
            ">= 96, EXP-0168 already has it hardware-run on G17P, and nothing "
            "here needs it.",
        ])


# --------------------------------------------- tilebuffer oracle assembly ----

def tile_oracles(arm):
    """(good, [(label, zero_candidate), ...]) for a tilebuffer arm.

    All host-computed. `good` is the fully correct read-back. Each zero
    candidate is "attachment j's tilebuffer read returned 0, everything else
    correct" -- ONE per attachment that performs a read, because which
    attachment the resolved anchor feeds is resolved from the compiled bytes and
    must not be assumed by the oracle. The matching candidate's label is
    recorded, so `SILENT_ZERO:rt1` is itself evidence about rt_index routing.
    """
    o = arm["oracle"]
    if not o.startswith(("tile", "mrt")):
        return None, []
    W, H = arm["W"], arm["H"]
    n = W * H
    if o == "tile":
        good = o_tile(DST0, SRC, W, H)
        return good, [("rt0", o_tile_zero(DST0, SRC, W, H))]
    if o == "tile2":
        good = o_tile2(DST0, SRC, W, H)
        return good, [("rt0", o_tile2_zero(DST0, SRC, W, H))]
    if o == "mrt":
        good = o_mrt(DST0, DST1, SRC, W, H)
        z0 = [[SRC[k] for k in range(4)] for _ in range(n)] + good[n:]
        z1 = good[:n] + [[-SRC[k] for k in range(4)] for _ in range(n)]
        return good, [("rt0", z0), ("rt1", z1)]
    if o == "mrt3":
        good = o_mrt3(DST0, DST1, DST2, SRC, W, H)
        z0 = [[SRC[k] for k in range(4)] for _ in range(n)] + good[n:]
        z1 = good[:n] + [[-SRC[k] for k in range(4)] for _ in range(n)] + good[2 * n:]
        z2 = good[:2 * n] + [[SRC[k] * 3.0 for k in range(4)] for _ in range(n)]
        return good, [("rt0", z0), ("rt1", z1), ("rt2", z2)]
    return None, []
