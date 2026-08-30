#!/usr/bin/env python3
"""EXP-0207 frozen sweep plan: arms, value sets, oracles.

Frozen at pre-registration.  `harness/run207.py` reads this and nothing else for
what to dispatch; `analysis/verdicts.py` reads `raw/` and nothing else for what
it means.

An ARM is (carrier program, pipeline state, stage, the located instruction
occurrence, the fields ruled on, the controls).  Every arm carries three kinds of
control record, and FIELD-SWEEP-PROTOCOL section 5a makes the first of them a
GATE rather than a decoration: an arm whose observable never moves for a
known-live control cannot establish that anything else is inert.

  ladder      -- neighbouring fields of the SAME instruction, known live
  power_probe -- a field in the DIMENSION the target field would control
  sensitivity -- a splice pre-registered to FAIL (the falsifier)
"""

POISON_U32 = 0xDEADBEEF
SENT_BASE = 0x5A5A0000
SR_BIAS = 1000
CGRID = 64
CTG = 64

# Fragment/vertex uniform (fragment buffer 0) and vertex uniform (vertex buffer 0).
SRC = [0.125, 0.375, 0.625, 0.875]
VP = [1.5, 2.5, 3.0, 0.0]

CLEAR_F = [[-1.0, -2.0, -3.0, -4.0]]
CLEAR_U = [[4000000000.0, 4000000001.0, 4000000002.0, 4000000003.0]]
CLEAR_8 = [[0.0, 0.25, 0.5, 0.75]]
CLEAR_M = [[-7.0, -8.0, -9.0, -10.0]]

FRAG_KERNEL = "kernels/k_frag207.metal"
VTX_KERNEL = "kernels/k_vtx207.metal"
SR_KERNEL = "kernels/k_sr207.metal"
FEN_KERNEL = "kernels/k_fence207.metal"
MESH_KERNEL = "kernels/k_mesh207.metal"

# --------------------------------------------------------------- selectors ---
# `get_sr.sr_sel` values whose meaning this project has already documented in
# tools/agx-isa/db.json.  The host oracle below computes each one WITHOUT the
# GPU.  Selectors outside a stage's documented set are still dispatched (they are
# part of the joint form x sr_sel map) but record `oracle: null` and are scored
# only as moved / not-moved -- never as `wrong_value` against a guess.
SR_SET = [130, 133, 152, 153, 154, 156, 157, 158,
          160, 161, 162, 164, 165, 166, 167, 168, 169, 170]
SR_SET_VERTEX = [221, 216, 136, 138]

BASE_VERTEX = 9
BASE_INSTANCE = 5
INSTANCES = 3


def sr_oracle_compute(sel, exec_width, grid=CGRID, tg=CTG):
    """Expected per-lane read-back for a documented compute selector, or None.

    Derived from db.json's own sr_sel enum plus the dispatch geometry this plan
    fixes (grid 64, threadgroup 64 -> exactly one threadgroup).  Nothing here is
    read off the GPU.
    """
    n = grid
    if sel == 130:                       # thread_index_in_simdgroup
        return [i % exec_width for i in range(n)]
    if sel == 133:                       # simdgroup_index_in_threadgroup
        return [i // exec_width for i in range(n)]
    if sel == 152:
        return [tg] * n
    if sel in (153, 154):
        return [1] * n
    if sel in (156, 157, 158):           # threadgroup_position_in_grid.xyz
        return [0] * n
    if sel == 160:                       # thread_position_in_grid.x
        return list(range(n))
    if sel in (161, 162):
        return [0] * n
    if sel == 164:                       # thread_position_in_threadgroup.x
        return [i % tg for i in range(n)]
    if sel in (165, 166):
        return [0] * n
    if sel == 167:                       # thread_index_in_threadgroup
        return [i % tg for i in range(n)]
    if sel == 168:
        return [max(1, grid // tg)] * n
    if sel in (169, 170):
        return [1] * n
    return None


def sr_oracle_frag(sel, W, H):
    """Expected .r channel (before the pixel-centre offset) per pixel, or None."""
    if sel == 160:
        return [float(px) for _ in range(H) for px in range(W)]
    if sel == 161:
        return [float(py) for py in range(H) for _ in range(W)]
    if sel == 162:
        return [0.0] * (W * H)
    return None


def sr_oracle_vertex(sel):
    """Expected value at each of the three triangle corners, or None."""
    if sel == 221:                       # vertex_id
        return [0.0 + BASE_VERTEX, 1.0 + BASE_VERTEX, 2.0 + BASE_VERTEX]
    if sel == 216:                       # instance_id
        return [float(BASE_INSTANCE)] * 3
    if sel == 136:                       # base_vertex
        return [float(BASE_VERTEX)] * 3
    if sel == 138:                       # base_instance
        return [float(BASE_INSTANCE)] * 3
    return None


def bary(tri, px, py, W, H):
    """Barycentric weights of the pixel centre in the clip-space triangle."""
    x = (px + 0.5) / W * 2.0 - 1.0
    y = 1.0 - (py + 0.5) / H * 2.0
    (x0, y0), (x1, y1), (x2, y2) = tri
    d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    l0 = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / d
    l1 = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / d
    return [l0, l1, 1.0 - l0 - l1]


TRI_FULL = [(-1.0, -1.0), (3.0, -1.0), (-1.0, 3.0)]

# ------------------------------------------------------------ value plans ----
# H1: byte+2 of the memory family is the ADDRESS / STORE MODE, whose documented
# values across device_load / device_store are these five.  Pre-registered, and
# used as the per-value oracle for frag_color_store.store_mode.
ADDR_MODE_VALUES = (0x04, 0x24, 0x54, 0x56, 0x64)

# Structured whole-field values for the 40-bit vtx_coord_xform.operand, on top of
# the per-byte dense plan.  Boundaries, all powers of two, and asymmetric
# interiors -- FIELD-SWEEP-PROTOCOL section 3 for w > 8.
def operand_structured():
    m = (1 << 40) - 1
    vals = [0, 1, 2, m - 1, m]
    vals += [1 << k for k in range(40)]
    vals += [0x0123456789, 0xFEDCBA9876, 0x5555555555, 0xAAAAAAAAAA,
             0x00000000FF, 0xFF00000000, 0x0102030405, 0x8000000001,
             0x000000FFFF, 0xFFFF000000, 0x0F0F0F0F0F, 0xF0F0F0F0F0,
             0x1234500000, 0x0000012345, 0x7FFFFFFFFF, 0x8000000000]
    seen, out = set(), []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


# ------------------------------------------------------------------ arms -----
# `anchor` says how run207.py locates the instruction occurrence:
#   ("sr", sr_sel)      -- the get_sr whose sr_sel byte equals this
#   ("pat", [hexpat..]) -- the first occurrence matching one of these byte
#                          patterns that ALSO decodes to `instr` under the
#                          pinned tokenizer
#   ("occ", k)          -- the k-th tokenized occurrence of `instr`
R = "render"
C = "compute"
M = "mesh"

ARMS = [
    # ---------------- frag_color_store.store_mode: destination kind / data path
    dict(arm="sm_dual", stage=R, kind=R, kernel=FRAG_KERNEL, vs="v_plain", fs="f_dual",
         W=8, H=8, nrt=1, samples=1, fmt=125, blend="dual", depth=0, outbuf=256,
         clear=CLEAR_F, instr="frag_color_store", anchor=("occ", 0),
         fields=["store_mode"], oracle="store_mode",
         why="DUAL-SOURCE blend: a second colour output to the SAME render target at "
             "index(1).  That is not an rt_index change, so if the second source is "
             "encoded at all it is encoded elsewhere in the store descriptor.  No "
             "carrier in EXP-0155/0163 had more than one source per target."),
    dict(arm="sm_dual1", stage=R, kind=R, kernel=FRAG_KERNEL, vs="v_plain", fs="f_dual",
         W=8, H=8, nrt=1, samples=1, fmt=125, blend="dual", depth=0, outbuf=256,
         clear=CLEAR_F, instr="frag_color_store", anchor=("occ", 1),
         fields=["store_mode"], oracle="store_mode",
         why="the SECOND store of the dual-source pair -- the index(1) source itself"),
    dict(arm="sm_blend", stage=R, kind=R, kernel=FRAG_KERNEL, vs="v_plain", fs="f_blend",
         W=8, H=8, nrt=1, samples=1, fmt=125, blend="alpha", depth=0, outbuf=256,
         clear=CLEAR_F, instr="frag_color_store", anchor=("occ", 0),
         fields=["store_mode"], oracle="store_mode",
         why="fixed-function blending on: the store feeds the blender rather than "
             "overwriting the tile.  Never varied in any prior arm."),
    dict(arm="sm_samp", stage=R, kind=R, kernel=FRAG_KERNEL, vs="v_plain", fs="f_samp",
         W=8, H=8, nrt=1, samples=4, fmt=125, blend="none", depth=0, outbuf=256,
         clear=CLEAR_F, instr="frag_color_store", anchor=("occ", 0),
         fields=["store_mode"], oracle="store_mode",
         why="PER-SAMPLE invocation ([[sample_id]]) at 4 samples: a per-sample store. "
             "EXP-0163's cent4 was 4 samples with PER-PIXEL shading."),
    dict(arm="sm_mask", stage=R, kind=R, kernel=FRAG_KERNEL, vs="v_plain", fs="f_mask",
         W=8, H=8, nrt=1, samples=4, fmt=125, blend="none", depth=0, outbuf=256,
         clear=CLEAR_F, instr="frag_color_store", anchor=("occ", 0),
         fields=["store_mode"], oracle="store_mode",
         why="a [[sample_mask]] output alongside the colour: a second, non-colour "
             "destination in the same store sequence"),
    dict(arm="sm_u32", stage=R, kind=R, kernel=FRAG_KERNEL, vs="v_plain", fs="f_u32",
         W=8, H=8, nrt=1, samples=1, fmt=123, blend="none", depth=0, outbuf=256,
         clear=CLEAR_U, instr="frag_color_store", anchor=("occ", 0),
         fields=["store_mode"], oracle="store_mode",
         why="an INTEGER (RGBA32Uint) attachment: a different store data path.  Every "
             "prior arm stored float or half."),
    dict(arm="sm_depth", stage=R, kind=R, kernel=FRAG_KERNEL, vs="v_plain", fs="f_depth",
         W=8, H=8, nrt=1, samples=1, fmt=125, blend="none", depth=1, outbuf=256,
         clear=CLEAR_F, instr="frag_color_store", anchor=("occ", 0),
         fields=["store_mode"], oracle="store_mode",
         why="the fragment also writes [[depth(any)]]: a second destination kind in "
             "the same epilogue"),
    dict(arm="sm_r8", stage=R, kind=R, kernel=FRAG_KERNEL, vs="v_plain", fs="f_r8",
         W=8, H=8, nrt=1, samples=1, fmt=70, blend="none", depth=0, outbuf=256,
         clear=CLEAR_8, instr="frag_color_store", anchor=("occ", 0),
         fields=["store_mode"], oracle="store_mode",
         why="a packed 8-bit attachment: the narrowest store data path Metal offers"),

    # ---------------------------------- iter.b9: INVOCATION FREQUENCY ---------
    dict(arm="it_ps4", stage=R, kind=R, kernel=FRAG_KERNEL, vs="v_loc", fs="f_ps",
         W=8, H=8, nrt=1, samples=4, fmt=125, blend="none", depth=0, outbuf=8 * 8 * 4 * 16,
         clear=CLEAR_F, instr="iter", anchor=("occ", 0),
         fields=["b9"], oracle="iter_b9",
         why="PER-SAMPLE invocation at 4 samples, with every sample's own interpolated "
             "values written to a device buffer so no resolve average can hide a "
             "permutation.  iter.b9 has only ever been swept under PER-PIXEL shading."),
    dict(arm="it_ps4b", stage=R, kind=R, kernel=FRAG_KERNEL, vs="v_loc", fs="f_ps",
         W=8, H=8, nrt=1, samples=4, fmt=125, blend="none", depth=0, outbuf=8 * 8 * 4 * 16,
         clear=CLEAR_F, instr="iter", anchor=("occ", 2),
         fields=["b9"], oracle="iter_b9",
         why="a second iter occurrence in the same per-sample program (a different "
             "varying, hence a different location class)"),
    dict(arm="it_ps1", stage=R, kind=R, kernel=FRAG_KERNEL, vs="v_loc", fs="f_ps",
         W=8, H=8, nrt=1, samples=1, fmt=125, blend="none", depth=0, outbuf=8 * 8 * 4 * 16,
         clear=CLEAR_F, instr="iter", anchor=("occ", 0),
         fields=["b9"], oracle="iter_b9",
         why="THE CONTROL: byte-for-byte the same MSL at ONE sample, where every "
             "sample location collapses to the pixel centre.  If b9 moves at 4 and "
             "not at 1, the dimension is the sample count; if it moves at neither "
             "while `loc` does, the null is much stronger than today's."),
    dict(arm="it_atsamp", stage=R, kind=R, kernel=FRAG_KERNEL, vs="v_pull", fs="f_atsamp",
         W=8, H=8, nrt=1, samples=4, fmt=125, blend="none", depth=0, outbuf=8 * 8 * 4 * 16,
         clear=CLEAR_F, instr="iter", anchor=("occ", 0),
         fields=["b9"], oracle="iter_b9",
         why="pull-model interpolate_at_sample with a DYNAMIC index at 4 samples: the "
             "location is a runtime operand, not a qualifier"),

    # ------------------------- vtx_coord_xform.operand: SEVERAL SOURCES -------
    dict(arm="vx_multi", stage="vertex", kind=R, kernel=VTX_KERNEL, vs="v_multi", fs="f_multi",
         W=16, H=16, nrt=1, samples=1, fmt=125, blend="none", depth=0, outbuf=16 * 16 * 4,
         clear=CLEAR_F, instr="vtx_coord_xform", anchor=("pat", ["17", None]),
         fields=["operand"], oracle="baseline_equality",
         why="THREE indexed constant arrays with disjoint value ranges.  EXP-0147's "
             "carrier had ONE, so every legal alternative selection had nothing to "
             "select and V=1 was structural, not a property of the field."),
    dict(arm="vx_wide", stage="vertex", kind=R, kernel=VTX_KERNEL, vs="v_wide", fs="f_wide",
         W=16, H=16, nrt=1, samples=1, fmt=125, blend="none", depth=0, outbuf=16 * 16 * 4,
         clear=CLEAR_F, instr="vtx_coord_xform", anchor=("pat", ["17", None]),
         fields=["operand"], oracle="baseline_equality",
         why="ONE array with EIGHT distinct entries and a runtime index: eight "
             "selectable slots instead of three"),
    dict(arm="vx_pos2", stage="vertex", kind=R, kernel=VTX_KERNEL, vs="v_pos2", fs="f_pos2",
         W=16, H=16, nrt=1, samples=1, fmt=125, blend="none", depth=0, outbuf=16 * 16 * 4,
         clear=CLEAR_F, instr="vtx_coord_xform", anchor=("pat", ["17", None]),
         fields=["operand"], oracle="baseline_equality",
         why="two candidate POSITION arrays: a re-selected coordinate changes the "
             "geometry, and at 16x16 with a per-pixel coverage sentinel that is a "
             "large distinct pattern rather than an all-or-nothing draw"),

    # --------------------------------- get_sr: form and dst_hi, by STAGE ------
    dict(arm="sr_c", stage=C, kind=C, kernel=SR_KERNEL, func="k_sr_c",
         grid=CGRID, tg=CTG, ins={}, instr="get_sr", anchor=("sr", 130),
         fields=["form", "dst_hi"], oracle="sr_compute", sr_set=SR_SET,
         why="the compute stage: the richest documented selector set, so the "
             "form x sr_sel map is scored against a HOST-COMPUTED value in every cell"),
    dict(arm="sr_hi", stage=C, kind=C, kernel=SR_KERNEL, func="k_sr_hi",
         grid=CGRID, tg=CTG, ins={1: "hipress"}, instr="get_sr", anchor=("sr", 130),
         fields=["form", "dst_hi"], oracle="sr_compute_hi", sr_set=SR_SET,
         why="HIGH REGISTER PRESSURE: sixteen values live across a device load, so the "
             "compiler's own destination for the system-value read may already sit "
             "above r15 and 0 becomes an OFF-baseline dst_hi.  Measured in the census."),
    dict(arm="sr_f", stage=R, kind=R, kernel=SR_KERNEL, vs="v_sr", fs="f_sr",
         W=8, H=8, nrt=1, samples=1, fmt=125, blend="none", depth=0, outbuf=256,
         clear=CLEAR_F, instr="get_sr", anchor=("sr", 160),
         fields=["form", "dst_hi"], oracle="sr_frag", sr_set=SR_SET,
         why="the fragment stage: pixel x and pixel y are host-computable per pixel"),
    dict(arm="sr_f2", stage=R, kind=R, kernel=SR_KERNEL, vs="v_sr", fs="f_sr2",
         W=8, H=8, nrt=1, samples=1, fmt=125, blend="none", depth=0, outbuf=256,
         clear=CLEAR_F, instr="get_sr", anchor=("sr", 160),
         fields=["form", "dst_hi"], oracle="sr_frag2", sr_set=SR_SET,
         why="the same fragment read CONSUMED THROUGH ARITHMETIC before the store, so "
             "the destination register is read by a different instruction"),
    dict(arm="sr_v", stage="vertex", kind=R, kernel=SR_KERNEL, vs="v_sv", fs="f_sv",
         W=8, H=8, nrt=1, samples=1, fmt=125, blend="none", depth=0, outbuf=256,
         clear=CLEAR_F, draw="indexed", basevertex=BASE_VERTEX, baseinstance=BASE_INSTANCE,
         instances=INSTANCES, instr="get_sr", anchor=("sr", 221),
         fields=["form", "dst_hi"], oracle="sr_vertex", sr_set=SR_SET_VERTEX,
         why="the VERTEX stage -- the documented discriminator for get_sr (EXP-0178 "
             "measured 128/128 bit-7-clear selectors faulting here and none in "
             "compute).  An indexed draw with baseVertex/baseInstance makes "
             "vertex_id, instance_id, base_vertex and base_instance mutually "
             "distinguishable."),

    # ------------------------------ dev_scoreboard_fence.scope_flag -----------
    dict(arm="fen_at", stage=C, kind=C, kernel=FEN_KERNEL, func="k_fence_at",
         grid=CGRID, tg=CTG, ins={1: "zeros"}, instr="dev_scoreboard_fence",
         anchor=("occ", 0), fields=["scope_flag"], oracle="fence",
         why="divergent device atomics then a device-scope barrier: the post-barrier "
             "counters are (32,64) for every lane, so the correct answer is a host "
             "constant and a lost ordering is a smaller number, not noise"),
    dict(arm="fen_rel", stage=C, kind=C, kernel=FEN_KERNEL, func="k_fence_rel",
         grid=CGRID, tg=CTG, ins={1: "zeros", 2: "zeros"}, instr="dev_scoreboard_fence",
         anchor=("occ", 0), fields=["scope_flag"], oracle="fence_rel",
         why="a release/acquire handoff: a broken release makes the readers see the "
             "pre-publication payload, which is a different host-computable constant"),

    # ------------------------------------------- mesh_out_src.sel -------------
    dict(arm="me_w2", stage=M, kind=M, kernel=MESH_KERNEL, obj="obj_main",
         mesh="mesh_wide2", frag="frag_wide", W=8, H=8, clear=CLEAR_M,
         tgobj=1, tgmesh=12, grid=1,
         instr="mesh_out_src", anchor=("occ", 0), fields=["sel"], oracle="mesh_sel",
         why="the EXP-0187 mesh_wide payload structure with NON-DEGENERATE, "
             "viewport-covering geometry, so the mesh output path is observable in "
             "the frame at all.  This field has never been dispatched."),
    dict(arm="me_w3", stage=M, kind=M, kernel=MESH_KERNEL, obj="obj_main",
         mesh="mesh_wide3", frag="frag_wide", W=8, H=8, clear=CLEAR_M,
         tgobj=1, tgmesh=12, grid=1,
         instr="mesh_out_src", anchor=("occ", 0), fields=["sel"], oracle="mesh_sel",
         why="the same geometry with per-vertex and per-primitive payload slots that "
             "differ by two orders of magnitude, so a re-selected source is an "
             "unmistakable colour change"),
    dict(arm="me_w1", stage=M, kind=M, kernel=MESH_KERNEL, obj="obj_main",
         mesh="mesh_wide", frag="frag_wide", W=8, H=8, clear=CLEAR_M,
         tgobj=1, tgmesh=12, grid=1,
         instr="mesh_out_src", anchor=("occ", 0), fields=["sel"], oracle="mesh_sel",
         why="THE CENSUS CONTROL: the exact shape EXP-0187 walk-confirmed.  Its "
             "geometry is degenerate (every vertex on y = 2x), so it is expected to "
             "draw nothing -- which is recorded as a measured no-detection-power "
             "result, not as inertness."),
]

# ------------------------------------------------------------- controls ------
# ladder: (name, field, alternative value or None for +1, why)
# power_probe: [(field, value, why)] -- tried in order, the first that exists on
#              the resolved descriptor is used
# sensitivity: the pre-registered FALSIFIER, expected to break the program
CONTROLS = {
    "frag_color_store": dict(
        ladder=[("rt", "rt_index", 0x02, "route the store to an absent RT: the tile must keep the clear colour"),
                ("fmt", "fmt", 0x22, "the attachment format descriptor, hardware-run"),
                ("src", "src", None, "the source colour GPR")],
        power_probe=[("rt_index", 0x06, "IN-DIMENSION POWER: rt_index is the store's own "
                                        "destination selector.  If moving it cannot move the "
                                        "observable, this arm cannot see a store-mode change "
                                        "either and no inert verdict may rest on it.")],
        sensitivity=("byte1", 0x00, "byte+1==0x06 is the FRAGMENT tile-store variant; 0x00 is the "
                                    "compute device store.  Documented to neutralise the store.")),
    "iter": dict(
        ladder=[("loc", "loc", 0x08, "the documented interpolation LOCATION field, hardware-run"),
                ("loc2", "loc", 0x20, "a second location value"),
                ("mode", "mode", 0x04, "the interpolation mode"),
                ("slot", "src_slot", 0x02, "the varying coefficient slot")],
        power_probe=[("loc", 0x09, "IN-DIMENSION POWER: `loc` is the documented location field and "
                                   "b9 is the adjacent byte of the same descriptor tail.  An arm on "
                                   "which `loc` cannot move has not built the location dimension.")],
        sensitivity=("byte1", 0x00, "byte+1 is the leading/subsequent marker; 0x00 is neither")),
    "vtx_coord_xform": dict(
        ladder=[("sel", "sel", 0x04, "the operand selector: 91 of 256 correct on M4"),
                ("mode", "mode", 0xE2, "the mode: correct iff (mode & 0xf3) in {0x22,0xe2}")],
        power_probe=[("sel", 0x08, "IN-DIMENSION POWER: `sel` is the neighbouring operand SELECTOR "
                                   "on the same instruction")],
        sensitivity=("byte2", 0x00, "byte+2==0xa2 is a match constant that statically separates this "
                                    "op from simd_ballot; corrupting it must break the draw")),
    "get_sr": dict(
        ladder=[("sel", "sr_sel", 0x98, "the selector byte, hardware-run at full range"),
                ("dp", "dp_width", 0x50, "the datapath width / destination bank descriptor"),
                ("dst", "dst", None, "the destination GPR low nibble, hardware-run")],
        power_probe=[("dst", 0x0A, "IN-DIMENSION POWER: `dst` is the LOW half of the very register "
                                   "number `dst_hi` extends.  Two carriers that cannot both express "
                                   "'which register the value lands in' are one carrier.")],
        sensitivity=("byte0_bit2", 0, "clearing byte0 bit 2 leaves the low 3 bits != 0b100")),
    "dev_scoreboard_fence": dict(
        ladder=[("b2", "scope_flag", 0x04, "the documented rare variant value")],
        power_probe=[("scope_flag", 0xFF, "an out-of-range scope value")],
        sensitivity=("byte0", 0x00, "NEUTRALISE THE FENCE ITSELF.  This is the arm's whole point: if "
                                    "removing the fence does not change the observable, the carrier "
                                    "has no ordering sensitivity and NO verdict may be filed.")),
    "mesh_out_src": dict(
        ladder=[("sel1", "sel", 0x01, "the selector byte itself at an adjacent value")],
        power_probe=[("sel", 0x40, "IN-DIMENSION POWER: the only field this 2-byte op has")],
        sensitivity=("byte0", 0x00, "byte0==0x04 is the op leader; 0x00 is not this instruction")),
}


def field_values(mnem, field, start, width):
    """The frozen value plan for one field."""
    if width <= 8:
        return "dense", list(range(1 << width))
    if mnem == "vtx_coord_xform" and field == "operand":
        return "byte-dense+structured", operand_structured()
    raise KeyError("no frozen plan for %s.%s" % (mnem, field))


def hang_policy():
    """No per-field hang budget (FIELD-SWEEP-PROTOCOL rule 3c): a budget cannot
    characterise a contiguous hazard, it guarantees the region is never mapped.
    The only stop is a global circuit breaker against a runaway."""
    return {"per_field_budget": None, "global_circuit_breaker": 400}
