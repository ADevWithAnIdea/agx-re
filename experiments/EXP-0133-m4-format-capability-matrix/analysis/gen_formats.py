#!/usr/bin/env python3
"""Frozen, deterministic derivation of the EXP-0133 target format matrix from
the public MTLPixelFormat.h enum (PUBLIC source: an Apple SDK header, i.e.
the public API surface a third-party app links against -- not a compiled
Apple binary; no disassembly, no code introspection). Regenerating this file
must reproduce CAPTURE_CONTRACT.json's frozen "formats" list byte-for-byte;
CAPTURE_CONTRACT.json is the source of truth once frozen (this script is
provenance for how it was derived, not re-run to mutate it after freeze).

kind classifies which MSL texture element type a capability-sweep kernel
must use to bind the format at all (an MSL/API fact, not a hardware fact):
  float -> texture2d<float,...> / depth2d<float,...> for pure depth
  uint  -> texture2d<uint,...>
  int   -> texture2d<int,...>
  depthstencil -> both a depth2d<float> view and a texture2d<uint> stencil view
This is derived purely from the MTLPixelFormat name suffix, which is Metal's
own public naming convention (Unorm/Snorm/Float -> float; Uint -> uint;
Sint -> int), not a hardware claim.
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
HEADER = Path("/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk/System/Library/Frameworks/Metal.framework/Versions/A/Headers/MTLPixelFormat.h")

EXCLUDE = {"Invalid", "Unspecialized"}

def classify(name):
    if name in ("Depth16Unorm", "Depth32Float"):
        return "float", "depth"
    if name == "Stencil8":
        return "uint", "stencil"
    if name in ("Depth24Unorm_Stencil8", "Depth32Float_Stencil8"):
        return "float", "depthstencil"
    if name in ("X32_Stencil8", "X24_Stencil8"):
        # View-only stencil-aspect formats (reached via newTextureViewWithPixelFormat:
        # on a parent combined depth-stencil texture, per conv_split_depth_stencil),
        # NOT combined depth+stencil formats themselves -- they carry only a uint8
        # stencil value, matching plain Stencil8's own descriptor code exactly
        # (docs/descriptors/format-table.md: x32_stencil8 byte0/byte1 == stencil8's).
        # Originally misclassified as kind=float/family=depthstencil, which caused
        # run03 (quarantined, provenance/quarantined_attempt2/) to attempt
        # MTLPixelFormatX32_Stencil8 as a depthAttachmentPixelFormat -- correctly
        # rejected by Metal ("is not depth renderable"), but for the wrong
        # underlying reason (a harness classification bug, not new hardware
        # information), and meant every OTHER axis for X32_Stencil8 ran with the
        # wrong MSL binding type (texture2d<float> instead of texture2d<uint>).
        return "uint", "stencil_view"
    if name in ("GBGR422", "BGRG422"):
        return "float", "yuv422"
    if name.startswith("PVRTC_"):
        return "float", "compressed_pvrtc"
    if name.startswith("BC6H"):
        return "float", "compressed_bc"
    if name.startswith("BC"):
        return "float", "compressed_bc"
    if name.startswith("EAC_") or name.startswith("ETC2_"):
        return "float", "compressed_etc"
    if name.startswith("ASTC_") and name.endswith("_HDR"):
        return "float", "compressed_astc_hdr"
    if name.startswith("ASTC_"):
        return "float", "compressed_astc_ldr"
    if name.startswith("BGR10_XR") or name.startswith("BGRA10_XR"):
        return "float", "xr"
    if re.search(r"Uint(_sRGB)?$", name):
        return "uint", "int_norm"
    if re.search(r"Sint(_sRGB)?$", name):
        return "int", "int_norm"
    if re.search(r"Float(_sRGB)?$", name):
        return "float", "float_norm"
    if re.search(r"(Unorm|Snorm)(_sRGB)?$", name):
        return "float", "int_norm"
    raise ValueError("unclassified format name: " + name)

def bpp(name, family):
    """Bytes per texel for uncompressed formats (public, name-derived; None
    for compressed/YUV formats, whose block geometry is handled separately).
    Used only for the LAYOUT axis's alignment-class grouping, not asserted
    as a hardware fact by itself."""
    table = {
        "A8Unorm": 1, "R8Unorm": 1, "R8Unorm_sRGB": 1, "R8Snorm": 1, "R8Uint": 1, "R8Sint": 1,
        "R16Unorm": 2, "R16Snorm": 2, "R16Uint": 2, "R16Sint": 2, "R16Float": 2,
        "RG8Unorm": 2, "RG8Unorm_sRGB": 2, "RG8Snorm": 2, "RG8Uint": 2, "RG8Sint": 2,
        "B5G6R5Unorm": 2, "A1BGR5Unorm": 2, "ABGR4Unorm": 2, "BGR5A1Unorm": 2,
        "R32Uint": 4, "R32Sint": 4, "R32Float": 4,
        "RG16Unorm": 4, "RG16Snorm": 4, "RG16Uint": 4, "RG16Sint": 4, "RG16Float": 4,
        "RGBA8Unorm": 4, "RGBA8Unorm_sRGB": 4, "RGBA8Snorm": 4, "RGBA8Uint": 4, "RGBA8Sint": 4,
        "BGRA8Unorm": 4, "BGRA8Unorm_sRGB": 4,
        "RGB10A2Unorm": 4, "RGB10A2Uint": 4, "RG11B10Float": 4, "RGB9E5Float": 4, "BGR10A2Unorm": 4,
        "BGR10_XR": 4, "BGR10_XR_sRGB": 4,
        "RG32Uint": 8, "RG32Sint": 8, "RG32Float": 8,
        "RGBA16Unorm": 8, "RGBA16Snorm": 8, "RGBA16Uint": 8, "RGBA16Sint": 8, "RGBA16Float": 8,
        "BGRA10_XR": 8, "BGRA10_XR_sRGB": 8,
        "RGBA32Uint": 16, "RGBA32Sint": 16, "RGBA32Float": 16,
        "GBGR422": 4, "BGRG422": 4,  # 4 bytes per 2 texels (macro-pixel)
        "Depth16Unorm": 2, "Depth32Float": 4, "Stencil8": 1,
        "Depth24Unorm_Stencil8": 4, "Depth32Float_Stencil8": 8, "X32_Stencil8": 4, "X24_Stencil8": 4,
    }
    return table.get(name)

def main():
    text = HEADER.read_text()
    pairs = re.findall(r'MTLPixelFormat([A-Za-z0-9_]+)\b.*?=\s*(\d+)\s*,', text)
    seen = {}
    for name, val in pairs:
        seen[int(val)] = name  # last wins if dup; none expected
    out = []
    for val in sorted(seen):
        name = seen[val]
        if name in EXCLUDE:
            continue
        kind, family = classify(name)
        out.append({"id": val, "name": name, "kind": kind, "family": family, "bpp": bpp(name, family)})
    print(json.dumps(out, indent=2))
    import sys
    print("count:", len(out), file=sys.stderr)

if __name__ == "__main__":
    main()
