#!/usr/bin/env python3
"""Deterministic generator for CAPTURE_CONTRACT.json (EXP-0106). Run with no
arguments: `python3 gen_contract.py`. Writes CAPTURE_CONTRACT.json next to
this script. Every case below implements one PRE_REGISTRATION.md family
(b01/b02/b03/b04/b05/b06/b07/b08/b09). expected_out_words entries are the
oracle this pre-registration commits to; `None` marks a genuinely
exploratory (OBSERVED_NO_ORACLE) word -- both are legitimate per CODEX.md,
neither is filled in after the fact.
"""
import hashlib
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = "PRE_GPU"
EXPERIMENT = "EXP-0106-m4-texture-isa-semantics"
MAIN_KERNEL = "kernels/tex_isa.metal"
B07_KERNEL = "kernels/b07_65.metal"
LEVEL_FAIL_KERNEL = "kernels/b04_level_minlod_fail.metal"
GATHER_FAIL_KERNEL = "kernels/b04_gather_minlod_fail.metal"
SAMPLER17_FAIL_KERNEL = "kernels/b08_sampler17_fail.metal"

AUTH = ("PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", MAIN_KERNEL, B07_KERNEL, "kernels/gen_b07.py",
        LEVEL_FAIL_KERNEL, GATHER_FAIL_KERNEL, SAMPLER17_FAIL_KERNEL,
        "harness/probe.m", "run.py", "analysis/analysis.py", "make_manifest.py", "verify.py", "gen_contract.py")

W16 = lambda: [None] * 16
def words(d):
    out = W16()
    for i, v in d.items():
        out[i] = v
    return out

def hx(b): return b.hex()

# ---------------------------------------------------------------- shared populate blobs
def canary_mips(base, count, w0, h0):
    """[{"mip":L,"slice":0,"bytes_hex":...}] with byte value (base+L) filling the whole level."""
    out = []
    for L in range(count):
        w = max(1, w0 >> L); h = max(1, h0 >> L)
        out.append({"mip": L, "slice": 0, "bytes_hex": hx(bytes([base + L]) * (w * h))})
    return out

def depth_mips(count, w0, h0):
    out = []
    for L in range(count):
        w = max(1, w0 >> L); h = max(1, h0 >> L)
        depth = L / (count - 1)
        out.append({"mip": L, "slice": 0, "bytes_hex": hx(struct.pack("<f", depth) * (w * h))})
    return out

VOL32 = hx(b"".join(struct.pack("<I", r * 32 + c) for r in range(32) for c in range(32)))
VOL3D = hx(bytes([z for z in range(4) for _y in range(4) for _x in range(4)]))
GRID2X2 = hx(b"".join(struct.pack("<f", v) for v in (1.0, 2.0, 3.0, 4.0)))

cases = []

def add(case, family, kernel_file, args, n_outputs, expected, expect_status="ok", timeout=60, rule_note=""):
    cases.append({
        "case": case, "family": family, "kernel_file": kernel_file, "args": args,
        "n_outputs": n_outputs, "expected_out_words": expected, "expect_status": expect_status,
        "timeout_seconds": timeout, "rule_note": rule_note,
    })

# ================================================================ b01/b03: descriptor-only creation boundary (TEX-23, TEX-25 create-half)
DESCR = []
def descr(case, kind, extra_args, expect):
    DESCR.append({"case": case, "family": "b_descriptor", "kernel_file": None, "args": extra_args,
                  "n_outputs": 0, "expected_out_words": W16(), "expect_status": expect,
                  "timeout_seconds": 30, "rule_note": "TEX-23/TEX-25 dimension/sample-count creation boundary"})

descr("b01_1d_max", "1d", {"type": "1d", "width": 16384, "height": 1}, "ok")
descr("b01_1d_over", "1d", {"type": "1d", "width": 16385, "height": 1}, "abort")
descr("b01_2d_max", "2d", {"type": "2d", "width": 16384, "height": 1}, "ok")
descr("b01_2d_over", "2d", {"type": "2d", "width": 16385, "height": 1}, "abort")
descr("b01_cube_max", "cube", {"type": "cube", "width": 16384, "height": 16384}, "ok")
descr("b01_cube_over", "cube", {"type": "cube", "width": 16385, "height": 16385}, "abort")
descr("b01_3dw_max", "3d", {"type": "3d", "width": 2048, "height": 4, "depth": 4}, "ok")
descr("b01_3dw_over", "3d", {"type": "3d", "width": 2049, "height": 4, "depth": 4}, "abort")
descr("b01_3dd_max", "3d", {"type": "3d", "width": 4, "height": 4, "depth": 2048}, "ok")
descr("b01_3dd_over", "3d", {"type": "3d", "width": 4, "height": 4, "depth": 2049}, "abort")
descr("b01_arraylen_max", "2darray", {"type": "2darray", "width": 4, "height": 4, "arrayLength": 2048}, "ok")
descr("b01_arraylen_over", "2darray", {"type": "2darray", "width": 4, "height": 4, "arrayLength": 2049}, "abort")
descr("b03_create_1", "2dms", {"type": "2dms", "width": 4, "height": 4, "sampleCount": 1}, "abort")
descr("b03_create_2", "2dms", {"type": "2dms", "width": 4, "height": 4, "sampleCount": 2}, "ok")
descr("b03_create_3", "2dms", {"type": "2dms", "width": 4, "height": 4, "sampleCount": 3}, "abort")
descr("b03_create_4", "2dms", {"type": "2dms", "width": 4, "height": 4, "sampleCount": 4}, "ok")
descr("b03_create_8", "2dms", {"type": "2dms", "width": 4, "height": 4, "sampleCount": 8}, "abort")

QUERY = []
for sc in (1, 2, 3, 4, 8):
    QUERY.append({"case": f"b03_query_{sc}", "family": "b03_query", "kernel_file": None,
                  "args": {"sample_count": sc}, "n_outputs": 0, "expected_out_words": W16(),
                  "expect_status": "ok", "timeout_seconds": 30, "rule_note": "TEX-25 supportsTextureSampleCount query"})

# ================================================================ b02: mip-count ceiling + explicit-level() edges (TEX-24)
DISPATCH = []
def dispatch(case, family, kernel_file, args, expected, expect_status="ok", timeout=60, rule_note="", n_outputs=None):
    if n_outputs is None:
        # infer from the highest non-None index + 1 (every case below writes a contiguous
        # out[0..n) prefix); expect_status != "ok" cases that never dispatch pass n_outputs=0 explicitly.
        idxs = [i for i, v in enumerate(expected) if v is not None]
        n_outputs = (max(idxs) + 1) if idxs else 0
    DISPATCH.append({"case": case, "family": family, "kernel_file": kernel_file, "args": args,
                     "n_outputs": n_outputs, "expected_out_words": expected, "expect_status": expect_status,
                     "timeout_seconds": timeout, "rule_note": rule_note})

mip15_args = {
    "textures": [{"id": "t", "type": "2d", "format": "r8uint", "width": 16384, "height": 1, "mipLevelCount": 15,
                  "usage": ["read"], "cpu_populate": canary_mips(0xC0, 15, 16384, 1)}],
    "dispatches": [{"kernel": "k_b02_mip15", "textures": {"0": "t"}, "buffers": {"0": "OUT"}, "threads": 1}],
}
dispatch("b02_mip15", "b02_mip15", MAIN_KERNEL, mip15_args, words({0: 15, 1: 0xCE, 2: 0}),
          rule_note="TEX-24 15-level mip chain: count, last-legal read, first-illegal (OOB) read")

def levelsweep_args(lod):
    return {
        "textures": [{"id": "t", "type": "2d", "format": "r8uint", "width": 16, "height": 16, "mipLevelCount": 4,
                      "usage": ["read"], "cpu_populate": canary_mips(0xD0, 4, 16, 16)}],
        "samplers": [{"id": "s", "filter": "nearest", "mipFilter": "nearest"}],
        "buffers": [{"id": "lodbuf", "kind": "f32", "values": [lod]}],
        "dispatches": [{"kernel": "k_b02_levelsweep", "textures": {"0": "t"}, "samplers": {"0": "s"},
                        "buffers": {"1": "lodbuf", "0": "OUT"}, "threads": 1}],
    }
# HW-confirmed in pre-freeze exploration (analysis/pilot/); oracle values from that confirmation.
LEVEL_EXPECT = {
    "neg": (levelsweep_args(-5.0), 0xD0), "excess": (levelsweep_args(99.0), 0xD3),
    "posinf": (levelsweep_args("inf"), 0xD3), "neginf": (levelsweep_args("-inf"), 0xD0),
}
for name, (a, exp) in LEVEL_EXPECT.items():
    dispatch(f"b02_level_{name}", "b02_levelsweep", MAIN_KERNEL, a, words({0: exp}),
              rule_note="TEX-24 explicit level() clamp behavior at a boundary/infinite value")
# NaN: no a-priori oracle committed (see PRE_REGISTRATION -- bias/gradient NaN polarity already
# diverge in EXP-0094; level()'s own polarity is the open question this case answers).
dispatch("b02_level_nan", "b02_levelsweep", MAIN_KERNEL, levelsweep_args("nan"), W16(), n_outputs=1,
          rule_note="TEX-24 explicit level(NaN) -- OBSERVED_NO_ORACLE, no a-priori prediction committed")

# ================================================================ b04: dynamic min_lod_clamp() across sample forms (TEX-05)
def minlod_tex_args(minlod, base_hex_char, width=16, height=16, levels=4):
    return {
        "textures": [{"id": "t", "type": "2d", "format": "r8uint", "width": width, "height": height,
                      "mipLevelCount": levels, "usage": ["read"], "cpu_populate": canary_mips(base_hex_char, levels, width, height)}],
        "samplers": [{"id": "s", "filter": "nearest", "mipFilter": "nearest"}],
        "buffers": [{"id": "mlbuf", "kind": "f32", "values": [minlod]}],
    }

# implicit + min_lod_clamp ALONE, and bias(0)+min_lod_clamp, and sample_compare+min_lod_clamp: all
# three deterministically CRASH -[MTLDevice newComputePipelineStateWithFunction:] on this M4/
# macOS 26.6.2/Metal 4 stack (XPC_ERROR_CONNECTION_INTERRUPTED from the AGXMetalG16G compiler
# service) -- confirmed reproducible 6/6 across isolated fresh processes in pre-freeze exploration
# (analysis/pilot/). This is a genuine finding, not a harness defect: the LIBRARY compiles fine
# (S_library_ok=true); only PIPELINE STATE creation for that specific function crashes.
for i, minlod in enumerate((0.0, 2.0)):
    a = minlod_tex_args(minlod, 0xE0)
    a["dispatches"] = [{"kernel": "k_b04_implicit_minlod", "textures": {"0": "t"}, "samplers": {"0": "s"},
                        "buffers": {"1": "mlbuf", "0": "OUT"}, "threads": 1}]
    dispatch(f"b04_implicit_minlod_{i}", "b04_minlod", MAIN_KERNEL, a, W16(), expect_status="pipeline_rejected",
              rule_note="TEX-05 implicit+min_lod_clamp alone: pipeline compile crash (XPC), reproducible")

a = minlod_tex_args(2.0, 0xE0)
a["dispatches"] = [{"kernel": "k_b04_bias_minlod", "textures": {"0": "t"}, "samplers": {"0": "s"},
                    "buffers": {"1": "mlbuf", "0": "OUT"}, "threads": 1}]
dispatch("b04_bias_minlod", "b04_minlod", MAIN_KERNEL, a, W16(), expect_status="pipeline_rejected",
          rule_note="TEX-05 bias(0)+min_lod_clamp: pipeline compile crash (XPC), reproducible")

for i, minlod in enumerate((0.0, 1.0, 2.0, 3.0)):
    a = minlod_tex_args(minlod, 0xE0)
    a["dispatches"] = [{"kernel": "k_b04_grad_minlod", "textures": {"0": "t"}, "samplers": {"0": "s"},
                        "buffers": {"1": "mlbuf", "0": "OUT"}, "threads": 1}]
    dispatch(f"b04_grad_minlod_{i}", "b04_minlod", MAIN_KERNEL, a, words({0: 0xE0 + i}),
              rule_note="TEX-05 gradient2d(0,0)+min_lod_clamp: the one combination that DOES compile+run")

a = {
    "textures": [{"id": "t", "type": "2d", "format": "depth32float", "width": 16, "height": 16, "mipLevelCount": 4,
                  "usage": ["read"], "cpu_populate": depth_mips(4, 16, 16)}],
    "samplers": [{"id": "s", "filter": "nearest", "mipFilter": "nearest", "compare": "less"}],
    "buffers": [{"id": "mlbuf", "kind": "f32", "values": [2.0]}],
    "dispatches": [{"kernel": "k_b04_compare_minlod", "textures": {"0": "t"}, "samplers": {"0": "s"},
                    "buffers": {"1": "mlbuf", "0": "OUT"}, "threads": 1}],
}
dispatch("b04_compare_minlod", "b04_minlod", MAIN_KERNEL, a, W16(), expect_status="pipeline_rejected",
          rule_note="TEX-05 sample_compare+min_lod_clamp: pipeline compile crash (XPC), reproducible")

dispatch("b04_level_minlod_fail", "b04_minlod_fail", LEVEL_FAIL_KERNEL,
          {"textures": [], "dispatches": []}, W16(), expect_status="library_failed",
          rule_note="TEX-05 structural: no sample() overload combines level()+min_lod_clamp() (MSL spec 6.12.3)")
dispatch("b04_gather_minlod_fail", "b04_minlod_fail", GATHER_FAIL_KERNEL,
          {"textures": [], "dispatches": []}, W16(), expect_status="library_failed",
          rule_note="TEX-05 structural: gather() has no lod_options/min_lod_clamp parameter at all (MSL spec 6.12.6)")

# ================================================================ b05: dynamic bindless texture query, non-uniform per-lane (TEX-06)
b05_args = {
    "textures": [
        {"id": "tex0", "type": "2d", "format": "r32uint", "width": 8, "height": 8, "mipLevelCount": 1, "usage": ["read"]},
        {"id": "tex1", "type": "2d", "format": "r32uint", "width": 16, "height": 16, "mipLevelCount": 2, "usage": ["read"]},
        {"id": "tex2", "type": "2d", "format": "r32uint", "width": 32, "height": 32, "mipLevelCount": 3, "usage": ["read"]},
        {"id": "tex3", "type": "2d", "format": "r32uint", "width": 64, "height": 64, "mipLevelCount": 4, "usage": ["read"]},
    ],
    "argument_buffers": [{"id": "ab", "entries": [{"index": i, "texture": f"tex{i}"} for i in range(4)]}],
    "dispatches": [{"kernel": "k_b05_bindless_query", "buffers": {"0": "ARGBUF:ab", "1": "OUT"}, "threads": 4}],
}
dispatch("b05_bindless_query", "b05_query", MAIN_KERNEL, b05_args,
          words({0: 8, 1: 16, 2: 32, 3: 64, 4: 1, 5: 2, 6: 3, 7: 4}),
          rule_note="TEX-06 per-lane non-uniform bindless get_width/get_num_mip_levels")

# ================================================================ b06: OOB remainder -- 3D depth axis (TEX-13)
b06_args = {
    "textures": [{"id": "t", "type": "3d", "format": "r8uint", "width": 4, "height": 4, "depth": 4,
                  "usage": ["read"], "cpu_populate": [{"mip": 0, "slice": 0, "bytes_hex": VOL3D}]}],
    "dispatches": [{"kernel": "k_b06_3d_depth_oob", "textures": {"0": "t"}, "buffers": {"0": "OUT"}, "threads": 1}],
}
dispatch("b06_3d_depth_oob", "b06_oob", MAIN_KERNEL, b06_args, words({0: 3, 1: 0}),
          rule_note="TEX-13 remainder: 3D depth-axis last-legal vs. first-illegal (OOB) read")

# ================================================================ b07: 65-argument direct-texture boundary-pair selectability (TEX-14)
BOUNDARY9 = [0, 7, 8, 15, 16, 31, 32, 63, 64]
b07_textures = [{"id": f"t{i}", "type": "2d", "format": "r32uint", "width": 1, "height": 1, "usage": ["read"],
                 "cpu_populate": [{"mip": 0, "slice": 0, "bytes_hex": hx(struct.pack("<I", 0xD00D0000 + i))}]}
                for i in range(65)]
b07_args = {
    "textures": b07_textures,
    "dispatches": [{"kernel": "k_b07_tex65", "textures": {str(i): f"t{i}" for i in range(65)},
                    "buffers": {"0": "OUT"}, "threads": 1}],
}
dispatch("b07_tex65_boundary", "b07_texsel", B07_KERNEL, b07_args,
          words({w: 0xD00D0000 + idx for w, idx in enumerate(BOUNDARY9)}),
          timeout=90, rule_note="TEX-14 boundary-pair (7/8,15/16,31/32,63/64) simultaneous distinguishability")

# ================================================================ b08: 16 distinguishable direct samplers (TEX-17/18)
b08_samplers = [{"id": f"s{i}", "filter": "nearest", "address": "clamptozero" if i % 2 == 0 else "clamptoedge"}
                for i in range(16)]
b08_args = {
    "textures": [{"id": "t", "type": "2d", "format": "r32float", "width": 2, "height": 2, "usage": ["read"],
                  "cpu_populate": [{"mip": 0, "slice": 0, "bytes_hex": GRID2X2}]}],
    "samplers": b08_samplers,
    "dispatches": [{"kernel": "k_b08_sampler16", "textures": {"0": "t"},
                    "samplers": {str(i): f"s{i}" for i in range(16)}, "buffers": {"0": "OUT"}, "threads": 1}],
}
# HW-confirmed in pre-freeze exploration: even (clampToZero) -> 0.0, odd (clampToEdge) -> 3.0
# (the edge texel at this OOB coordinate), consistently for all 16 slots.
zero_bits = struct.unpack("<I", struct.pack("<f", 0.0))[0]
edge_bits = struct.unpack("<I", struct.pack("<f", 3.0))[0]
dispatch("b08_sampler16", "b08_samplersel", MAIN_KERNEL, b08_args,
          words({i: (zero_bits if i % 2 == 0 else edge_bits) for i in range(16)}),
          rule_note="TEX-17 all 16 direct samplers simultaneously distinguishable by address mode at an OOB coordinate")
dispatch("b08_sampler17_fail", "b08_samplersel_fail", SAMPLER17_FAIL_KERNEL, {"textures": [], "dispatches": []},
          W16(), expect_status="library_failed",
          rule_note="TEX-18 17th [[sampler(16)]] argument: MSL compile-time rejection (0..15 range)")

# ================================================================ b09: offset-pair boundary sweep + dynamic offset (TEX-03/04)
def offset_args(dx, dy):
    return {
        "textures": [{"id": "t", "type": "2d", "format": "r32uint", "width": 32, "height": 32, "usage": ["read"],
                      "cpu_populate": [{"mip": 0, "slice": 0, "bytes_hex": VOL32}]}],
        "samplers": [{"id": "s", "filter": "nearest"}],
        "buffers": [{"id": "offbuf", "kind": "i32", "values": [dx, dy]}],
        "dispatches": [{"kernel": "k_b09_gather_offset", "textures": {"0": "t"}, "samplers": {"0": "s"},
                        "buffers": {"1": "offbuf", "0": "OUT"}, "threads": 1}],
    }
# HW-confirmed in pre-freeze exploration: gather.x tracks (base_col+dx, base_row+dy) with an exact
# affine relationship (result = (16+dy)*32 + (15+dx)); no oracle formula is assumed a priori in
# PRE_REGISTRATION beyond "injective, matches an affine shift" -- these are the literal
# pre-freeze-confirmed values, committed as the frozen oracle.
def expected_offset(dx, dy):
    row = 16 + dy
    col = 15 + dx
    return row * 32 + col
BOUNDARY_OFFSETS = [(0, 0), (7, 0), (-8, 0), (0, 7), (0, -8), (7, 7), (-8, -8), (3, -2), (1, 0), (0, 1), (-8, 7), (7, -8)]
for dx, dy in BOUNDARY_OFFSETS:
    tag = f"{dx}_{dy}".replace("-", "m")
    dispatch(f"b09_offset_{tag}", "b09_offset", MAIN_KERNEL, offset_args(dx, dy), words({0: expected_offset(dx, dy)}),
              rule_note="TEX-03 boundary/corner offset pair -> exact affine footprint shift, no aliasing")

dyn_offs = [(0, 0), (3, -2), (7, 7), (-8, -8)]
flat = [v for pair in dyn_offs for v in pair]
dyn_args = {
    "textures": [{"id": "t", "type": "2d", "format": "r32uint", "width": 32, "height": 32, "usage": ["read"],
                  "cpu_populate": [{"mip": 0, "slice": 0, "bytes_hex": VOL32}]}],
    "samplers": [{"id": "s", "filter": "nearest"}],
    "buffers": [{"id": "offs", "kind": "i32", "values": flat}],
    "dispatches": [{"kernel": "k_b09_gather_offset_dynamic", "textures": {"0": "t"}, "samplers": {"0": "s"},
                    "buffers": {"1": "offs", "0": "OUT"}, "threads": 4}],
}
dispatch("b09_offset_dynamic", "b09_offset_dynamic", MAIN_KERNEL, dyn_args,
          words({i: expected_offset(dx, dy) for i, (dx, dy) in enumerate(dyn_offs)}),
          rule_note="TEX-04 per-lane, runtime-loaded, non-constant offset: each lane its own value, cross-checked against the constant-offset cases")

ALL_CASES = DESCR + QUERY + DISPATCH
SMOKE_CASE = "b09_offset_0_0"  # a cheap, early, positive-outcome dispatch case

# ---------------------------------------------------------------- assemble contract
def sha(p):
    return hashlib.sha256((HERE / p).read_bytes()).hexdigest()

def main():
    ids = [c["case"] for c in ALL_CASES]
    assert len(ids) == len(set(ids)), "duplicate case id"
    contract = {
        "schema": 1,
        "experiment": EXPERIMENT,
        "state": STATE,
        "pinned_git_revision": "75eb840a011ffbfa3fe2eb1721e2acbbcc24c1e7",
        "boundary": "public Metal only; owned in-bounds resources; no binary/archive/BO inspection",
        "cases": ALL_CASES,
        "blob_sha256": {p: sha(p) for p in AUTH if p != "CAPTURE_CONTRACT.json"},
        "capture": {
            "runs": ["m4-20260830-run01", "m4-20260830-run02"],
            "pre_capture_smoke": {"case": SMOKE_CASE},
        },
    }
    (HERE / "CAPTURE_CONTRACT.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    print("wrote CAPTURE_CONTRACT.json:", len(ALL_CASES), "cases")
    fam_counts = {}
    for c in ALL_CASES:
        fam_counts[c["family"]] = fam_counts.get(c["family"], 0) + 1
    for k, v in sorted(fam_counts.items()):
        print(" ", k, v)

if __name__ == "__main__":
    main()
