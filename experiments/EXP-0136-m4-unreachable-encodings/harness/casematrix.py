"""EXP-0136 frozen case matrix (see PRE_REGISTRATION.md #4). Every case is a
plain dict: {id, family, mechanism, kind, params}. `mechanism` routes run.py to
the right probe binary/tool: "descpatch" (harness/descpatch.m), "gfxprobe"
(harness/gfxprobe.m), or "agxtest" (tools/agxtest, read-only, wrapped).

Each family carries at least one internal positive control (see per-family
comment) satisfying "every null needs a positive control proving
detectability".
"""

MATRIX = []


def _add(cid, family, mechanism, kind, params):
    MATRIX.append({"id": cid, "family": family, "mechanism": mechanism, "kind": kind, "params": params})


# ---------------------------------------------------------------- H1: aniso
# ystripe texture, 32x32, 6 mips (32,16,8,4,2,1); box-filter-authored so every
# mip>=1 is uniformly 127 (0.498) -- crisp readback (r near 1.0) proves the
# sampler resolved detail at mip0-for-the-minor-axis; blurred (r near 0.5)
# proves it fell back to a higher/blended mip. v=1.5/32 lands on a "255" row.
# dPdy is fixed (=1/32, i.e. LOD_y=0, never minified in Y). dPdx = ratio/32.
def _aniso_uvg(ratio):
    return [0.5, 1.5 / 32.0, ratio / 32.0, 1.0 / 32.0]


for a in (1, 2, 4, 8, 16):  # REAL API, ratio==16==cap: positive control, monotonic-with-aniso curve
    _add(f"aniso_ratio16_real{a}", "aniso", "descpatch", "aniso_real",
         {"ratio": 16, "aniso": a, "patched": False})
for a in (32, 64, 128):  # patched, ratio==16 (already <= cap): "over-provisioning" check
    _add(f"aniso_ratio16_patch{a}", "aniso", "descpatch", "aniso_patch",
         {"ratio": 16, "aniso": a, "patched": True})
for ratio in (64, 128):
    _add(f"aniso_ratio{ratio}_real16", "aniso", "descpatch", "aniso_real",
         {"ratio": ratio, "aniso": 16, "patched": False})  # real cap, ratio > cap: expect blur
    for a in (32, 64, 128):
        _add(f"aniso_ratio{ratio}_patch{a}", "aniso", "descpatch", "aniso_patch",
             {"ratio": ratio, "aniso": a, "patched": True})

# -------------------------------------------------------------- H2: addrmode
# codes 0,1,2,3,5 documented (EXP-0015); 4,6,7 Metal-unreachable. 4 UV points
# per code builds a signature; codes 0/1/2/3/5 ALSO serve as the family's
# positive control (their signatures must reproduce known clampToEdge/repeat/
# mirrorRepeat/clampToBorder/mirrorClampToEdge behavior).
for code in range(8):
    for ui, u in enumerate((1.2, 1.7, 2.6, -0.4)):
        _add(f"addrmode_code{code}_u{ui}", "addrmode", "descpatch", "addrmode",
             {"code": code, "u": u})

# ----------------------------------------------------------------- H3: border
# code0/1/2 are the positive control (must match the real preset's exact
# pixel regardless of which preset the sampler was actually CREATED with --
# proving the patch, not the creation value, determines the result). code3 is
# the unreachable 4th value.
_BORDER_EXPECT = {0: (0.0, 0.0, 0.0, 0.0), 1: (0.0, 0.0, 0.0, 1.0), 2: (1.0, 1.0, 1.0, 1.0)}
for creation in ("transparentBlack", "opaqueBlack", "opaqueWhite"):
    for code in (0, 1, 2, 3):
        _add(f"border_create{creation}_code{code}", "border", "descpatch", "border",
             {"creation_border": creation, "code": code})

# ---------------------------------------------------------------- H4: swizzle
# component0 (R-dst, byte2 bits0:2): codes 0..5 documented+positive-control
# (R,G,B,A,One,Zero each has an exact predicted value); 6,7 unreachable.
# component1 (G-dst, byte2 bits3:5) cross-check with a representative subset.
_SWZ_EXPECT_COMP0 = {0: "r", 1: "g", 2: "b", 3: "a", 4: "one", 5: "zero"}
for code in range(8):
    _add(f"swizzle_comp0_code{code}", "swizzle", "descpatch", "swizzle",
         {"component": 0, "code": code})
for code in (0, 4, 6):
    _add(f"swizzle_comp1_code{code}", "swizzle", "descpatch", "swizzle",
         {"component": 1, "code": code})

# ----------------------------------------------------------------- H5: restart
for idxtype in ("u16", "u32"):
    for kind, sentinel in (("allones", None), ("allones_minus1", "MINUS1"), ("small_oob", 8)):
        _add(f"restart_{idxtype}_{kind}", "restart", "gfxprobe", "restart",
             {"index_type": idxtype, "sentinel_kind": kind, "sentinel": sentinel})

# ---------------------------------------------------------------- H6: norender
for raster in (True, False):
    _add(f"norender_raster{raster}", "norender", "gfxprobe", "norender", {"raster_enabled": raster})

# ----------------------------------------------------------------- H7: opcode
# device_load#1 @4..17 (r7@off11, r13@off17); device_load#2 @18..31 (r7@off25,
# r13@off31); device_store @38..51 (r7@off45, r13@off51), in the compiled form
# of the fixed "o[i]=a[i]+b[i]" kernel (harness/kernels/add.metal). Offsets are
# fixed facts of that exact compiled program (recorded in
# harness/kernels/add_offsets.json, generated once and frozen -- see README).
_RESERVED_LOCS = {
    "load1_r7": 11, "load1_r13": 17, "load2_r7": 25, "load2_r13": 31,
    "store_r7": 45, "store_r13": 51,
}
for locname, off in _RESERVED_LOCS.items():
    for val in ("ff", "55"):
        _add(f"opcode_{locname}_{val}", "opcode", "agxtest", "reserved_byte",
             {"offset": off, "value": val})
for val in ("3f", "99", "d3", "5a", "c1", "ff"):
    _add(f"opcode_terminal_{val}", "opcode", "agxtest", "terminal_byte0",
         {"offset": 52, "value": val})

IDS = [c["id"] for c in MATRIX]
TOTAL = len(MATRIX)

FAMILIES = sorted(set(c["family"] for c in MATRIX))


def case_order_sensitive_keys(case):
    """No family in this experiment declares an order-sensitive observed key
    (unlike some prior EXPs with fence/hazard timing races) -- every probe
    here is a single isolated process/dispatch with no cross-case shared
    mutable state. Kept as a hook for verify.py's shared gate machinery."""
    return set()
