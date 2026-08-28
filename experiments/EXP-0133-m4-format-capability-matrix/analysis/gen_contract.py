#!/usr/bin/env python3
"""Assembles the frozen CAPTURE_CONTRACT.json from analysis/formats_generated.json
(the full 138-format target matrix, derived by gen_formats.py from the public
MTLPixelFormat.h enum) plus the hand-authored conversion/layout/sparse case lists.
Run once at pre-registration time; CAPTURE_CONTRACT.json is the frozen artifact
after that -- this script is provenance for its construction, not something the
captured run re-invokes."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

ALL_AXES = ["sampled", "filtered", "storage_read", "storage_write", "atomic", "linear",
            "renderable", "blendable", "msaa", "resolve", "depth_stencil"]

# Full-matrix pre-check (provenance/pre_freeze/precheck/, all 138 formats x 11 axes,
# real subprocess-per-cell) discovered THREE hard-abort classes, none of which is a
# harness bug -- each is a genuine, reproduced, and now fully-mapped hardware/API fact:
#
#  1. Depth24Unorm_Stencil8 (255) and X24_Stencil8 (262) are not valid MTLPixelFormat
#     values AT ALL on this device/OS ("MTLTextureDescriptor has invalid pixelFormat
#     (N)") -- corroborates the prior EXP-M4-08 finding (docs/descriptors/
#     format-table.md). Every axis touching texture creation aborts for these two.
#  2. renderable/msaa/resolve abort for every format whose family is not
#     color-renderable (the 83-format family_render_ineligible set, F1 in
#     PRE_REGISTRATION.md).
#  3. blendable ADDITIONALLY aborts for every integer-kind format (uint/int), even
#     ones that ARE otherwise color-renderable (e.g. R32Uint) -- confirms Metal's
#     documented "integer formats are not blendable" restriction is hardware-enforced,
#     not merely a soft capability flag.
#  4. depth_stencil does NOT abort for X32_Stencil8 (261, family stencil_view) when
#     correctly typed (kind=uint) -- it CAN be used directly as a
#     stencilAttachmentPixelFormat (command buffer completes, status 4). An earlier
#     iteration of this contract assumed the opposite (reasoning from X32_Stencil8's
#     "view-only" documentation) and was refuted by this corrected precheck; see
#     PRE_REGISTRATION.md F3 and provenance/quarantined_attempt2/NOTE.md for the
#     classification bug that produced the wrong prediction. No format is currently
#     known to abort on depth_stencil beyond the two device-unsupported ids.
DEVICE_UNSUPPORTED_FORMAT_IDS = [255, 262]
BLENDABLE_INELIGIBLE_KINDS = ["uint", "int"]
DEPTH_STENCIL_DIRECT_ATTACH_INELIGIBLE_FAMILIES = []

CONVERSION_CASES = [
    "r16unorm_sep_a", "r16unorm_sep_b", "r16unorm_nontie",
    "r16snorm_m100", "r16snorm_p100", "rgba16unorm_sep",
    "srgb8_low", "srgb8_mid", "srgb8_high",
    "int_filter_r32uint",
    "bc1_white_opaque", "bc1_red565_opaque",
    "split_depth_stencil",
]

# Layout representative subset: one format per bpp class (1/2/4/8/16), one compressed
# (BC, expect not_applicable), one ASTC (expect not_applicable), one depth (expect
# not_applicable), one stencil (expect not_applicable), one YUV422 (expect
# not_applicable), one XR (real attempt).
LAYOUT_FORMATS = [
    "R8Unorm", "RG8Unorm", "RGBA8Unorm", "RGBA16Float", "RGBA32Float",
    "BC1_RGBA", "ASTC_4x4_LDR", "Depth32Float", "Stencil8", "GBGR422", "BGR10_XR",
]
LAYOUT_BELOW_MINIMUM_FORMAT = "RGBA8Unorm"

SPARSE_FORMATS = ["RGBA8Unorm", "R32Uint", "BC1_RGBA", "ASTC_4x4_LDR", "Depth32Float"]


def main():
    formats = json.loads((HERE / "formats_generated.json").read_text())
    by_name = {f["name"]: f for f in formats}
    assert len(formats) == 138, len(formats)

    contract = {
        "state": "PRE_GPU",
        "experiment": "EXP-0133-m4-format-capability-matrix",
        "target_matrix_size": len(formats),
        "formats": formats,
        "capability_axes": ALL_AXES,
        "conversion_cases": CONVERSION_CASES,
        "layout_formats": [by_name[n] for n in LAYOUT_FORMATS],
        "layout_below_minimum_format": by_name[LAYOUT_BELOW_MINIMUM_FORMAT],
        "sparse_formats": [by_name[n] for n in SPARSE_FORMATS],
        "family_render_ineligible": [
            "depth", "stencil", "depthstencil", "stencil_view",
            "compressed_bc", "compressed_pvrtc", "compressed_etc",
            "compressed_astc_ldr", "compressed_astc_hdr", "yuv422",
        ],
        "family_linear_ineligible": [
            "depth", "stencil", "depthstencil", "stencil_view",
            "compressed_bc", "compressed_pvrtc", "compressed_etc",
            "compressed_astc_ldr", "compressed_astc_hdr", "yuv422",
        ],
        "device_unsupported_format_ids": DEVICE_UNSUPPORTED_FORMAT_IDS,
        "blendable_ineligible_kinds": BLENDABLE_INELIGIBLE_KINDS,
        "depth_stencil_direct_attach_ineligible_families": DEPTH_STENCIL_DIRECT_ATTACH_INELIGIBLE_FAMILIES,
        "boundary": {
            "accesses": "public Metal API only; 16x16 (4x4 for BC1 conversion case) owned textures; no pattern verification in the capability sweep beyond success/failure and informational readback",
            "apple_binary_archive_bo_inspection": "NONE",
            "private_api_or_trace": "NONE",
        },
        "timeouts_seconds": {
            "environment": 5,
            "host_build": 180,
            "case_process": 60,
        },
        "blob_sha256_files": [
            "kernels/capability.metal", "kernels/conversion.metal",
            "harness/probe.m", "run.py", "analysis.py", "make_manifest.py", "verify.py",
            "analysis/formats_generated.json", "analysis/gen_formats.py", "analysis/gen_contract.py",
        ],
    }
    (ROOT / "CAPTURE_CONTRACT.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    total_cap = len(formats) * len(ALL_AXES)
    total = total_cap + len(CONVERSION_CASES) + len(LAYOUT_FORMATS) + 1 + len(SPARSE_FORMATS)
    print("formats:", len(formats), "capability cases (formats x %d axes):" % len(ALL_AXES), total_cap,
          "conversion:", len(CONVERSION_CASES), "layout:", len(LAYOUT_FORMATS) + 1,
          "sparse:", len(SPARSE_FORMATS), "TOTAL CASES:", total)


if __name__ == "__main__":
    main()
