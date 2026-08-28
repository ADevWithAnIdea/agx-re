"""EXP-0108 authored render-pass configuration matrix.

Single source of truth for the case list. Imported by run.py, verify.py, and
analysis.py -- never restated. Each case is a JSON-serializable dict consumed
directly by harness/probe.m (written to a per-case config file by run.py).

Axes covered (see PRE_REGISTRATION.md for the falsifiable question each axis
answers): load/store action, attachment count (MRT), mixed per-attachment
format, per-format sweep, MSAA sample count + resolve, memoryless color,
depth (with and without an enabled depth-write pipeline state), stencil
(with and without an enabled stencil-write pipeline state), combined
depth+stencil, empty-tile (no draw) boundary, and a partial-render probe
that isolates target size from instance/primitive count.

Every case renders into a fixed small (32x32) target unless it belongs to
the "partial" axis, which is the one axis that intentionally varies target
size (64x64 control vs 2048x2048) to probe tiler-heap overflow behavior.
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
        "depth": False, "depthFmt": "Depth32Float", "depthLoad": "Clear",
        "depthStore": "Store", "depthMemoryless": False, "depthWrite": False,
        "stencil": False, "stencilLoad": "Clear", "stencilStore": "Store",
        "stencilWrite": False,
        "draw": True,
        "width": W, "height": H, "instances": 1,
        "axis": "unassigned",
    }
    c.update(kw)
    assert len(c["fmt"]) == c["ncolor"] == len(c["load"]) == len(c["store"]) == len(c["memoryless"]), name
    return c


CASES = []


def add(c):
    for x in CASES:
        assert x["name"] != c["name"], "duplicate case name " + c["name"]
    CASES.append(c)


# --- A: load/store action sweep (single RGBA8, samples=1) ---
add(base("a1-clear-store-draw", axis="action"))
add(base("a2-clear-store-empty", axis="action", draw=False))
add(base("a3-load-store-empty", axis="action", load=["Load"], draw=False))
add(base("a4-dontcare-store-draw", axis="action", load=["DontCare"]))
add(base("a5-clear-dontcare-draw", axis="action", store=["DontCare"]))
add(base("a6-load-dontcare-draw", axis="action", load=["Load"], store=["DontCare"]))
add(base("a7-dontcare-dontcare-draw", axis="action", load=["DontCare"], store=["DontCare"]))

# --- B: MRT attachment count (all RGBA8, clear/store, draw) ---
add(base("b2-mrt2", axis="mrt", ncolor=2, fmt=["RGBA8Unorm"] * 2,
         load=["Clear"] * 2, store=["Store"] * 2, memoryless=[False] * 2))
add(base("b3-mrt3", axis="mrt", ncolor=3, fmt=["RGBA8Unorm"] * 3,
         load=["Clear"] * 3, store=["Store"] * 3, memoryless=[False] * 3))
add(base("b4-mrt4", axis="mrt", ncolor=4, fmt=["RGBA8Unorm"] * 4,
         load=["Clear"] * 4, store=["Store"] * 4, memoryless=[False] * 4))

# --- C: mixed-format MRT ---
add(base("c1-mrt2-mixed", axis="mrt-mixed", ncolor=2, fmt=["RGBA8Unorm", "R32Float"],
         load=["Clear"] * 2, store=["Store"] * 2, memoryless=[False] * 2))

# --- D: per-format sweep (single attachment, clear/store, draw) ---
for i, fmt in enumerate(["BGRA8Unorm", "RGBA8Unorm_sRGB", "R32Float", "R32Uint",
                          "RGBA16Float", "R8Unorm", "RG8Unorm"], start=1):
    add(base("d%d-fmt-%s" % (i, fmt), axis="format", fmt=[fmt]))

# --- E: MSAA sample count + resolve (single RGBA8) ---
add(base("e1-msaa2-store", axis="msaa", samples=2))
add(base("e2-msaa4-store", axis="msaa", samples=4))
add(base("e3-msaa4-resolve", axis="msaa", samples=4, store=["MultisampleResolve"]))
add(base("e4-msaa4-store-and-resolve", axis="msaa", samples=4, store=["StoreAndMultisampleResolve"]))
add(base("e5-msaa2-load-store", axis="msaa", samples=2, load=["Load"]))

# --- F: memoryless color ---
add(base("f1-memoryless-color", axis="memoryless", memoryless=[True], store=["DontCare"]))

# --- G: depth ---
add(base("g1-depth-nowrite", axis="depth", depth=True))
add(base("g2-depth-write", axis="depth", depth=True, depthWrite=True))
add(base("g3-depth-memoryless-write", axis="depth", depth=True, depthWrite=True,
         depthMemoryless=True, depthStore="DontCare"))
add(base("g4-depth-load-write", axis="depth", depth=True, depthWrite=True, depthLoad="Load"))
add(base("g5-depth-dontcare-write", axis="depth", depth=True, depthWrite=True, depthStore="DontCare"))

# --- H: stencil ---
add(base("h1-stencil-nowrite", axis="stencil", stencil=True))
add(base("h2-stencil-write", axis="stencil", stencil=True, stencilWrite=True))
add(base("h3-stencil-load-write", axis="stencil", stencil=True, stencilWrite=True, stencilLoad="Load"))

# --- I: combined depth+stencil ---
add(base("i1-depth-stencil-write", axis="depth-stencil", depth=True, depthWrite=True,
         stencil=True, stencilWrite=True))

# --- J: empty-tile boundary on non-baseline shapes ---
add(base("j1-mrt2-empty", axis="empty", ncolor=2, fmt=["RGBA8Unorm"] * 2,
         load=["Clear"] * 2, store=["Store"] * 2, memoryless=[False] * 2, draw=False))
add(base("j2-msaa4-resolve-empty", axis="empty", samples=4, store=["MultisampleResolve"], draw=False))
add(base("j3-depth-write-empty", axis="empty", depth=True, depthWrite=True, draw=False))

# --- K: partial-render probe (isolates target size from instance count) ---
add(base("k1-partial-small-ref", axis="partial", width=64, height=64, instances=1))
add(base("k2-partial-bigtarget-fewinst", axis="partial", width=2048, height=2048, instances=200))
add(base("k3-partial-smalltarget-manyinst", axis="partial", width=64, height=64, instances=200000))
add(base("k4-partial-bigtarget-manyinst", axis="partial", width=2048, height=2048, instances=200000))

TOTAL = len(CASES)
BY_NAME = {c["name"]: c for c in CASES}
AXES = sorted(set(c["axis"] for c in CASES))

if __name__ == "__main__":
    print("TOTAL", TOTAL)
    for a in AXES:
        print(" ", a, sum(1 for c in CASES if c["axis"] == a))
