"""EXP-0132 authored render-pass configuration matrix.

Single source of truth for the case list. Imported by run.py, verify.py, and
analysis.py -- never restated. Each case is a JSON-serializable dict consumed
directly by harness/probe.m (written to a per-case config file by run.py).

Scope (see PRE_REGISTRATION.md for the falsifiable question each group
answers). Three priorities, in order:

  Group D -- depth/stencil-reuses-MRT-slots re-verification under the FIXED
    (race-free) harness in harness/wtrace.c. Reruns the minimal subset of
    EXP-0108's axis (a1 baseline, d1 format-only negative control, g1 depth,
    h1 stencil, i1 depth+stencil, g2 depth-memoryless) needed to reproduce
    its region-count-delta finding AND its doubly-corroborated-but-not-
    gated k=ncolor/k=ncolor+1 field content, this time under a two-run
    byte-exact gate with no read-timing exclusion needed.

  Group L / M -- array-layer and mip-level SELECTION field mapping for the
    render-target/PBE attachment path. Not exercised by any prior
    experiment (EXP-0048/EXP-0108/EXP-G1b all render into slice 0 / level 0
    of a non-arrayed, non-mipmapped target). Includes one deliberately
    invalid slice and one deliberately invalid level as their own isolated
    subprocess cases (boundary/first-invalid probes), each read back at
    EVERY valid neighbor (slice,level) afterward to distinguish reject /
    clamp / alias / silent-corruption / abort.

  Group R -- one MSAA store+resolve case with full attachment-slot-b and
    color-descriptor capture, to attempt a resolve-descriptor field
    extraction beyond the sample-count bit already established.

  Group B (no separate cases) -- harness/wtrace.c already captures
  attachment-slot-b's full content (it is a "known" role); run.py extracts
  more of it here (than EXP-0108's first64_hex) so its correlation with
  action/format/MRT/MSAA/depth/stencil (a real, reproducible signal
  EXP-0108 found but never field-decoded) can be read directly off the
  Group D/L/M/R cases above without any new render cases.
"""

W, H = 32, 32


def base(name, **kw):
    c = {
        "name": name,
        "ncolor": 1,
        "fmt": ["RGBA8Unorm"],
        "load": ["Clear"],
        "store": ["Store"],
        "memoryless": [False],
        "samples": 1,
        "depth": False, "depthLoad": "Clear",
        "depthStore": "Store", "depthMemoryless": False, "depthWrite": False,
        "stencil": False, "stencilLoad": "Clear", "stencilStore": "Store",
        "stencilWrite": False,
        "draw": True,
        "width": W, "height": H, "instances": 1,
        "arrayLength": 1, "slice": 0,
        "mipCount": 1, "level": 0,
        "readback_slices": None, "readback_levels": None,
        "axis": "unassigned",
        "boundary": False,
    }
    c.update(kw)
    assert len(c["fmt"]) == c["ncolor"] == len(c["load"]) == len(c["store"]) == len(c["memoryless"]), name
    return c


CASES = []


def add(c):
    for x in CASES:
        assert x["name"] != c["name"], "duplicate case name " + c["name"]
    CASES.append(c)


# --- D: depth/stencil slot-reuse re-verification (fixed harness) ---
add(base("a1-clear-store-draw", axis="depth-stencil-reverify"))
add(base("d1-fmt-bgra8-control", axis="depth-stencil-reverify", fmt=["BGRA8Unorm"]))
add(base("g1-depth-write", axis="depth-stencil-reverify", depth=True, depthWrite=True))
add(base("g2-depth-memoryless-write", axis="depth-stencil-reverify", depth=True, depthWrite=True,
         depthMemoryless=True, depthStore="DontCare"))
add(base("h1-stencil-write", axis="depth-stencil-reverify", stencil=True, stencilWrite=True))
add(base("i1-depth-stencil-write", axis="depth-stencil-reverify", depth=True, depthWrite=True,
         stencil=True, stencilWrite=True))
# MRT control on the same axis: EXP-0108 additivity claim was color-only; add one
# MRT2+depth+stencil case to check k-indexing when ncolor=2 (k=2 depth, k=3 stencil
# predicted if the "k=ncolor(+1)" rule generalizes beyond ncolor=1).
add(base("i2-mrt2-depth-stencil-write", axis="depth-stencil-reverify", ncolor=2,
         fmt=["RGBA8Unorm", "R32Float"], load=["Clear"] * 2, store=["Store"] * 2,
         memoryless=[False] * 2, depth=True, depthWrite=True, stencil=True, stencilWrite=True))

# --- L: array-layer selection field mapping (color attachment 0 only) ---
_AL = 4
add(base("l1-array-slice0", axis="array", arrayLength=_AL, slice=0,
         readback_slices=list(range(_AL)), readback_levels=[0]))
add(base("l2-array-slice1", axis="array", arrayLength=_AL, slice=1,
         readback_slices=list(range(_AL)), readback_levels=[0]))
add(base("l3-array-slice-last", axis="array", arrayLength=_AL, slice=_AL - 1,
         readback_slices=list(range(_AL)), readback_levels=[0]))
add(base("l4-array-slice-invalid", axis="array-boundary", boundary=True,
         arrayLength=_AL, slice=_AL,  # first invalid: arrayLength itself
         readback_slices=list(range(_AL)), readback_levels=[0]))

# --- M: mip-level selection field mapping (color attachment 0 only) ---
_MC = 3   # 32x32 supports levels 0,1,2 (16x16, 8x8) cleanly
add(base("m1-mip-level0", axis="mip", mipCount=_MC, level=0,
         readback_slices=[0], readback_levels=list(range(_MC))))
add(base("m2-mip-level-last", axis="mip", mipCount=_MC, level=_MC - 1,
         readback_slices=[0], readback_levels=list(range(_MC))))
add(base("m3-mip-level-invalid", axis="mip-boundary", boundary=True,
         mipCount=_MC, level=_MC,  # first invalid: mipCount itself
         readback_slices=[0], readback_levels=list(range(_MC))))

# --- R: MSAA store+resolve detail (full descriptor capture target) ---
add(base("r1-msaa4-resolve-detail", axis="resolve", samples=4, store=["MultisampleResolve"]))
add(base("r2-msaa4-store-and-resolve", axis="resolve", samples=4,
         store=["StoreAndMultisampleResolve"]))

TOTAL = len(CASES)
BY_NAME = {c["name"]: c for c in CASES}
AXES = sorted(set(c["axis"] for c in CASES))

if __name__ == "__main__":
    print("TOTAL", TOTAL)
    for a in AXES:
        print(" ", a, sum(1 for c in CASES if c["axis"] == a))
