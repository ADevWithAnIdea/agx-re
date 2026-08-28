#!/usr/bin/env python3
"""casematrix.py -- EXP-0143 FROZEN case matrix.

Defines, deterministically and without touching hardware:
  * the carriers (our own MSL + the pipeline descriptor each is built with),
  * which instruction OCCURRENCE each field is swept on,
  * the value set swept for each field,
  * the liveness control splice for each occurrence,
  * the pre-registered falsifiers.

Imported by run.py (capture) and by analysis/verdicts.py (reduction), so both
runs and the analysis see exactly the same matrix.

CLEAN-ROOM: OWN-SHADER.  Only bytes compiled from our own MSL are described.
"""

# --------------------------------------------------------------------------
# Carriers.  `kind` = render | compute.
# --------------------------------------------------------------------------
CARRIERS = {
    "c_iter":   dict(kind="render",  src="kernels/c_iter.metal",   color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_pack":   dict(kind="render",  src="kernels/c_pack.metal",   color_format=80,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_flat":   dict(kind="render",  src="kernels/c_flat.metal",   color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_cent1":  dict(kind="render",  src="kernels/c_cent.metal",   color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_cent4":  dict(kind="render",  src="kernels/c_cent.metal",   color_format=125,
                     samples=4, depth=False, resolve=True,  width=16, height=16),
    "c_depth":  dict(kind="render",  src="kernels/c_depth.metal",  color_format=125,
                     samples=1, depth=True,  resolve=False, width=16, height=16),
    "c_kill":   dict(kind="render",  src="kernels/c_kill.metal",   color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_mask":   dict(kind="render",  src="kernels/c_mask.metal",   color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_vary16": dict(kind="render",  src="kernels/c_vary16.metal", color_format=125,
                     samples=1, depth=False, resolve=False, width=16, height=16),
    "c_simd":   dict(kind="compute", src="kernels/c_simd.metal", function="k_simd",
                     grid=32, tg=32, out_bytes=32 * 16 * 4),
}

RENDER_VERTEX = "v_main"
RENDER_FRAGMENT = "f_main"

# Probe pixels (0-based x,y) inside the rasterized triangle at 16x16.  All three
# are covered in every render carrier's baseline; run.py asserts that.
PROBE_PIXELS = [(8, 8), (5, 10), (11, 5)]

# Probe lanes for the compute carrier.
PROBE_LANES = [0, 1, 5, 17, 31]

# --------------------------------------------------------------------------
# Geometry + per-vertex varying values -> the host-side interpolation oracle.
# All three vertices have w == 1, so perspective-correct == linear and the
# oracle is exact.  (Verified against the unspliced baseline: see RESULTS.md.)
# --------------------------------------------------------------------------
NDC_TRI = [(-0.75, -0.375), (0.0, -0.375), (0.75, 0.625)]

# c_iter / c_cent varying values per vertex, keyed by the FRAGMENT-side
# coefficient slot index the compiler assigned (slot = iter.src_slot >> 1).
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
    """Host-computed interpolated value of coefficient slot `slot`, or None."""
    v = ITER_SLOT_VALUES.get(slot)
    if v is None:
        return None
    b = bary(px, py, w, h)
    return sum(bi * vi for bi, vi in zip(b, v))


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
    # asymmetric interior samples, deterministic
    for k in (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59):
        vals.add((k * 0x9E3779B1) & mx)
    return sorted(vals)


# --------------------------------------------------------------------------
# Arms.  One arm == one (carrier, stage, mnemonic, occurrence) target.
#   fields  : the fields swept on this arm
#   live    : (field, value) control splice that MUST change the observation
#   note    : why the instruction is live on the observed output path
# --------------------------------------------------------------------------
ARMS = [
    # ---- priority 1: varying slot assignment -----------------------------
    dict(id="vary_slot@vert0", carrier="c_iter", stage="vertex",
         mnemonic="vary_slot", occ=0,
         fields=["sel", "slot"],
         live=("sel", 0x00),
         note="vertex program feeds every fragment varying; any change to the "
              "varying-output descriptor must show in the interpolated pixel"),
    dict(id="vary_slot@v16", carrier="c_vary16", stage="vertex",
         mnemonic="vary_slot", occ=0,
         fields=["sel", "slot"],
         live=("sel", 0x00),
         note="12-varying vertex program (slots 0..15) -- adversarial replicate "
              "of vary_slot@vert0 on a different shader"),

    # ---- priority 2: interpolation ---------------------------------------
    dict(id="iter@frag1", carrier="c_iter", stage="fragment",
         mnemonic="iter", occ=1,
         fields=["grp", "lead", "dst", "coeff_sel", "src_slot", "mode", "c7",
                 "loc", "b9"],
         live=("src_slot", 0x08),
         note="this iter produces colour channel 0 (proven: src_slot 0x02->0x08 "
              "makes channel 0 equal channel 3)"),
    dict(id="iter@frag0W", carrier="c_iter", stage="fragment",
         mnemonic="iter", occ=0,
         fields=["lead", "mode", "loc", "c7", "coeff_sel", "b9"],
         live=("mode", 0x00),
         note="the perspective-W-denominator iter; its result feeds the rcp that "
              "scales all four channels"),
    dict(id="iter@cent1", carrier="c_cent1", stage="fragment",
         mnemonic="iter", occ=1,
         fields=["mode", "loc", "coeff_sel", "c7", "b9", "lead"],
         live=("mode", 0x00),
         note="centroid/sample-qualified iter (mode 4/5, loc 8/9/32) -- covers "
              "mode/loc values the plain-centre carrier never emits"),
    dict(id="iter@cent4", carrier="c_cent4", stage="fragment",
         mnemonic="iter", occ=1,
         fields=["mode", "loc"],
         live=("mode", 0x00),
         note="same, MULTISAMPLED (4x, resolved): centroid and per-sample "
              "locations are genuinely distinct from pixel centre here"),
    dict(id="iter_at@cent1_0", carrier="c_cent1", stage="fragment",
         mnemonic="iter_at", occ=0,
         fields=["grp", "lead", "dst", "c4", "b5", "loc"],
         live=("lead", 0x00),
         note="interpolate-at setup for the centroid varyings; pilot-proven live "
              "(lead 0x14->0x00 changes channels 0 and 1)"),
    dict(id="iter_at@cent1_1", carrier="c_cent1", stage="fragment",
         mnemonic="iter_at", occ=1,
         fields=["grp", "lead", "dst", "c4", "b5", "loc"],
         live=("lead", 0x00),
         note="second interpolate-at setup; pilot-proven live (lead 0x04->0x00 "
              "zeroes all four channels)"),
    dict(id="iter_at@cent4_0", carrier="c_cent4", stage="fragment",
         mnemonic="iter_at", occ=0,
         fields=["loc", "b5", "c4"],
         live=("lead", 0x00),
         note="MULTISAMPLED replicate: the loc enum (centroid vs sample) can only "
              "differ from pixel centre when rasterSampleCount > 1"),
    dict(id="iter_flat@flat1", carrier="c_flat", stage="fragment",
         mnemonic="iter_flat", occ=1,
         fields=["b1", "sel", "b4", "b5"],
         live=("sel", 0x00),
         note="flat varying load feeding a colour channel; [[flat]] values are "
              "distinct per channel so a selector change is visible"),
    dict(id="iter_flat@flat0", carrier="c_flat", stage="fragment",
         mnemonic="iter_flat", occ=0,
         fields=["b1", "sel", "b4", "b5"],
         live=("sel", 0x06),
         note="adversarial second occurrence of the same op in the same program"),

    # ---- priority 3: fragment colour/depth output -------------------------
    dict(id="fcs@iter0", carrier="c_iter", stage="fragment",
         mnemonic="frag_color_store", occ=0,
         fields=["store_mode", "src", "flags", "rt_index", "mask", "fmt",
                 "slice_addr"],
         live=("rt_index", 0x02),
         note="the only colour store in the program: it writes the observed pixel"),
    dict(id="fcs@pack0", carrier="c_pack", stage="fragment",
         mnemonic="frag_color_store", occ=0,
         fields=["fmt", "mask", "flags", "store_mode"],
         live=("rt_index", 0x02),
         note="adversarial replicate on an 8-bit (BGRA8Unorm) attachment, where "
              "fmt differs (0x4e vs 0x2e)"),
    dict(id="fcp@pack0", carrier="c_pack", stage="fragment",
         mnemonic="frag_color_pack", occ=0,
         fields=["src_desc", "fmt_class", "dst", "mode", "comp_off", "val",
                 "src_present_mask", "src_gate_select", "conv_scale"],
         live=("val", 0x80),
         note="packs colour channels 0/1 for the 8-bit attachment store"),
    dict(id="fcp@pack1", carrier="c_pack", stage="fragment",
         mnemonic="frag_color_pack", occ=1,
         fields=["src_desc", "dst", "mode", "comp_off", "val"],
         live=("val", 0x80),
         note="second pack op (channels 2/3) -- adversarial replicate"),
    dict(id="fts@iter0", carrier="c_iter", stage="fragment",
         mnemonic="frag_tile_setup", occ=0,
         fields=["b1", "sel", "access", "b5"],
         live=("access", 0x08),
         note="store-setup bracket immediately preceding the observed colour store"),
    dict(id="fts@iter1", carrier="c_iter", stage="fragment",
         mnemonic="frag_tile_setup", occ=1,
         fields=["b1", "sel", "access", "b5"],
         live=("access", 0x06),
         note="second bracket (sel=0x0c, access=0x08) around the same store"),
    dict(id="fds@depth0", carrier="c_depth", stage="fragment",
         mnemonic="frag_depth_store", occ=0,
         fields=["b3", "b4", "b5"],
         live=None,   # see LIVE_CONTROLS_RAW below (match-bit control)
         note="the only depth store; the depth attachment is read back directly"),

    # ---- SIMD -------------------------------------------------------------
    dict(id="sreduce@simd0", carrier="c_simd", stage="compute",
         mnemonic="simd_reduce", occ=0,
         fields=["scope", "b0hi", "opcls", "cache", "op", "dst", "opmarker",
                 "src", "shape", "dtype"],
         live=("op", 0x02),
         note="a live SIMD-group reduction whose result is written to the output "
              "buffer by every lane"),
    dict(id="sreduce@simd8", carrier="c_simd", stage="compute",
         mnemonic="simd_reduce", occ=8,
         fields=["scope", "dtype", "op", "shape"],
         live=("op", 0x02),
         note="the QUAD-scope reduce (scope=0) -- adversarial replicate that "
              "exercises the other value of the scope bit"),
    dict(id="sshuffle@simd1", carrier="c_simd", stage="compute",
         mnemonic="simd_shuffle", occ=1,
         fields=["dir", "mode", "cache", "dst", "src", "srctype", "lane",
                 "rtype", "dsthi", "rsv9"],
         live=("lane", 0x04),
         note="simd_broadcast(u,5): lane index 5 == lane field 0x0a, so a lane "
              "change is directly predictable from the input buffer"),
    dict(id="sshuffle@simd6", carrier="c_simd", stage="compute",
         mnemonic="simd_shuffle", occ=6,
         fields=["dir", "mode", "lane", "srctype", "rtype"],
         live=("lane", 0x08),
         note="a dir=1 (xor/down) occurrence -- adversarial replicate on the "
              "other direction"),
    dict(id="sballot@simd0", carrier="c_simd", stage="compute",
         mnemonic="simd_ballot", occ=0,
         fields=["pred", "cache", "dst", "psrc", "psrctype", "form", "form_sig"],
         live=("psrc", 0x00),
         note="simd_ballot(predicate); the 32-bit mask is written by every lane"),
]

# Liveness controls expressed as a RAW byte patch inside the instruction
# (used where the control has to touch a match bit, which set_field cannot).
LIVE_CONTROLS_RAW = {
    "fds@depth0": (1, 0x00),   # byte+1 0x14 -> 0x00 : neutralize the depth-store
                               # variant selector, the same control EXP-0029 used
                               # on frag_color_store's byte+1.
}

# --------------------------------------------------------------------------
# Pre-registered FALSIFIERS: cases that MUST NOT match the inert/null oracle.
# If any of these matches the baseline, the corresponding arm is reported as
# unable to detect a difference and its verdicts are withheld.
# --------------------------------------------------------------------------
FALSIFIERS = [
    ("iter@frag1", "src_slot", 0x08),
    ("iter@frag1", "src_slot", 0x06),
    ("fcs@iter0", "rt_index", 0x02),
    ("fcp@pack0", "val", 0x80),
    ("iter_at@cent1_0", "lead", 0x00),
    ("iter_at@cent1_1", "lead", 0x00),
    ("sshuffle@simd1", "lane", 0x04),
    ("sreduce@simd0", "op", 0x02),
    ("iter_flat@flat1", "sel", 0x00),
]

# --------------------------------------------------------------------------
# Fields with a PREDICTIVE host oracle (everything else uses the null/inert
# oracle: "observation == baseline", and a mismatch is the result).
# --------------------------------------------------------------------------
PREDICTIVE = {
    ("iter@frag1", "src_slot"),      # value>>1 selects the coefficient slot
    ("fcs@iter0", "rt_index"),       # nonzero -> writes an absent RT -> clear colour
    ("sshuffle@simd1", "lane"),      # value>>1 is the broadcast source lane
}

# --------------------------------------------------------------------------
# The 0x57 opcode-collision probe (vary_store, flagged emit_unsafe in db.json).
# Not a field sweep: a discriminator/length hypothesis tested on hardware.
# --------------------------------------------------------------------------
COLLISION_PROBE = dict(
    hypothesis=(
        "byte0==0x57 is shared by an 8-byte VERTEX varying store and a 6-byte "
        "FRAGMENT kill/target-mask op.  db.json currently discriminates on "
        "byte+2==0x54, but our own corpus shows byte+2==0x54 in BOTH.  "
        "H: the discriminator is byte+1's LOW NIBBLE -- 0x?6 = 8-byte vertex "
        "varying store, 0x?4 = 6-byte fragment kill/mask op."),
    vs_carriers=["c_iter", "c_vary16"],
    fs_carriers=["c_kill", "c_mask"],
    # hardware test: rewrite the FS op's byte+1 low nibble 4 -> 6 and the VS
    # op's 6 -> 4.  If byte+1 controls the hardware's instruction LENGTH, the
    # following instruction is mis-fetched and the program's output changes in
    # a way a mere operand change cannot explain.
    fs_byte1_values=list(range(256)),
    vs_byte1_values=list(range(256)),
)


def field_values(desc_fields, name):
    """The pre-registered value set for one field, from its declared width."""
    for f in desc_fields:
        if f["name"] == name:
            w = f["width"]
            return dense(w) if w <= 8 else wide(w)
    raise KeyError(name)
