#!/usr/bin/env python3
"""One-shot generator for CAPTURE_CONTRACT.json's frozen "cases" list. Not
part of the gated pipeline itself (run.py/verify.py treat CAPTURE_CONTRACT.json
as static, hash-pinned input, exactly like every other EXP-* contract) --
this script is retained under work/gen/ for transparency/reproducibility of
how the matrix was authored, mirroring kernels/gen_direct128.py's precedent
of committing a generator alongside its deterministic output.
"""
import json, struct

def u32le_hex(v):
    return struct.pack("<I", v & 0xFFFFFFFF).hex()

def texel_pattern_hex(prefix, n, bytes_per=4):
    # n little-endian 32-bit words: prefix|i for i in 0..n-1, packed back-to-back.
    return b"".join(struct.pack("<I", (prefix | i) & 0xFFFFFFFF) for i in range(n)).hex()

def rgba_pattern_hex(prefix, n):
    return b"".join(struct.pack("<4I", (prefix | i) & 0xFFFFFFFF, i, i, i) for i in range(n)).hex()

cases = []

def add(case, family, kernel_file, args, n_outputs, expected, expect_status, rule, rule_note, timeout=60):
    """expected: list of 16 entries; each is an int (exact expected uint32),
    None (unconstrained/observe-only), or the string "SENTINEL" (must stay
    0xEEEEEEEE, i.e. this kernel is not documented to write that word)."""
    assert len(expected) == 16
    cases.append({
        "case": case, "family": family, "kernel_file": kernel_file, "args": args,
        "n_outputs": n_outputs, "expected_out_words": expected,
        "expect_status": expect_status, "rule": rule, "rule_note": rule_note,
        "timeout_seconds": timeout,
    })

SENT = 0xEEEEEEEE
def pad(vals):
    return (vals + [SENT] * 16)[:16]

MF = "kernels/matrix.metal"
DF = "kernels/direct128.metal"

# ============================================================ GLTEX-A05: 1D / 1D-array
W = 16
tex1d_pat = texel_pattern_hex(0xA5000000, W)
def tex1d(usage=("read",)):
    return {"id": "t0", "type": "1d", "format": "r32uint", "width": W, "usage": list(usage),
            "cpu_populate": [{"slice": 0, "bytes_hex": tex1d_pat}]}

add("a05_1d_sample_first", "a05", MF,
    {"textures": [{"id":"t0","type":"1d","format":"r32float","width":W,"usage":["read"],
                   "cpu_populate":[{"slice":0,"bytes_hex": texel_pattern_hex(0, W)}]}],  # r32float zero..15 as raw bits is nonsense; use direct float bytes below
     "samplers": [{"id":"s0","normalized":True,"filter":"nearest"}],
     "buffers": [{"id":"b_u","kind":"f32","values":[0.0]}],
     "dispatches": [{"kernel":"k_a05_1d_sample","textures":{"0":"t0"},"samplers":{"0":"s0"},"buffers":{"1":"b_u","0":"OUT"}}]},
    1, pad([None]), "ok", "c", "implicit-LOD sample at u=0.0 (first texel, nearest, clamp-to-edge address mode)")

add("a05_1d_read_first", "a05", MF, {"textures":[tex1d()], "buffers":[{"id":"b_coord","kind":"u32","values":[0]}],
    "dispatches":[{"kernel":"k_a05_1d_read","textures":{"0":"t0"},"buffers":{"0":"OUT","1":"b_coord"}}]},
    1, pad([0xA5000000]), "ok", "a", "fetch(read) at coord=0, first texel, exact expected value from CPU-populated content")
add("a05_1d_read_last", "a05", MF, {"textures":[tex1d()], "buffers":[{"id":"b_coord","kind":"u32","values":[W-1]}],
    "dispatches":[{"kernel":"k_a05_1d_read","textures":{"0":"t0"},"buffers":{"0":"OUT","1":"b_coord"}}]},
    1, pad([0xA5000000|(W-1)]), "ok", "a", "fetch(read) at coord=width-1, last legal texel")
add("a05_1d_read_oob", "a05", MF, {"textures":[tex1d()], "buffers":[{"id":"b_coord","kind":"u32","values":[W]}],
    "dispatches":[{"kernel":"k_a05_1d_read","textures":{"0":"t0"},"buffers":{"0":"OUT","1":"b_coord"}}]},
    1, pad([None]), "ok", "c", "fetch(read) at coord=width (first invalid coordinate) -- hypothesis: returns 0 (silent-zero pattern), refuted by any nonzero/garbage value")

add("a05_1d_write_probe", "a05", MF,
    {"textures":[{"id":"t0","type":"1d","format":"r32uint","width":W,"usage":["read","write"],
                  "cpu_populate":[{"slice":0,"bytes_hex":tex1d_pat}]}],
     "buffers":[{"id":"b_coord","kind":"u32","values":[3]}, {"id":"b_width","kind":"u32","values":[W]}],
     "dispatches":[{"kernel":"k_a05_1d_write_probe","textures":{"0":"t0"},"buffers":{"1":"b_coord"}},
                    {"kernel":"k_a05_1d_readback","textures":{"0":"t0"},"buffers":{"0":"OUT","1":"b_width"}}]},
    8, pad([0xA5000000,0xA5000001,0xA5000002,0xC0FFEE,0xA5000004,0xA5000005,0xA5000006,0xA5000007]), "ok", "a",
    "write(0xC0FFEE) at coord=3, then readback texels 0..7: only index 3 should change")

add("a05_1d_write_oob", "a05", MF,
    {"textures":[{"id":"t0","type":"1d","format":"r32uint","width":W,"usage":["read","write"],
                  "cpu_populate":[{"slice":0,"bytes_hex":tex1d_pat}]}],
     "buffers":[{"id":"b_coord","kind":"u32","values":[W]}, {"id":"b_width","kind":"u32","values":[W]}],
     "dispatches":[{"kernel":"k_a05_1d_write_probe","textures":{"0":"t0"},"buffers":{"1":"b_coord"}},
                    {"kernel":"k_a05_1d_readback","textures":{"0":"t0"},"buffers":{"0":"OUT","1":"b_width"}}]},
    8, pad([0xA5000000,0xA5000001,0xA5000002,0xA5000003,0xA5000004,0xA5000005,0xA5000006,0xA5000007]), "ok", "c",
    "write at coord=width (first invalid write coordinate); hypothesis: dropped, no texel 0..7 changes (falsified by any changed word)")

add("a05_1d_size", "a05", MF, {"textures":[tex1d()],
    "dispatches":[{"kernel":"k_a05_1d_size","textures":{"0":"t0"},"buffers":{"0":"OUT"}}]},
    2, pad([W,1]), "ok", "a", "get_width()/get_num_mip_levels() on an unmipmapped 1D texture")

L = 4
tex1darr_pat_by_layer = [texel_pattern_hex(0xB6000000 | (l<<8), W) for l in range(L)]
tex1darr_full = "".join(tex1darr_pat_by_layer)
def tex1darr(usage=("read",)):
    return {"id":"t0","type":"1darray","format":"r32uint","width":W,"arrayLength":L,"usage":list(usage),
            "cpu_populate":[{"slice":l,"bytes_hex":tex1darr_pat_by_layer[l]} for l in range(L)]}

add("a05_1darr_read_first_layer", "a05", MF, {"textures":[tex1darr()], "buffers":[{"id":"b_c","kind":"u32","values":[0]},{"id":"b_l","kind":"u32","values":[0]}],
    "dispatches":[{"kernel":"k_a05_1darr_read","textures":{"0":"t0"},"buffers":{"0":"OUT","1":"b_c","2":"b_l"}}]},
    1, pad([0xB6000000]), "ok", "a", "1D-array fetch at coord=0, layer=0")
add("a05_1darr_read_last_layer", "a05", MF, {"textures":[tex1darr()], "buffers":[{"id":"b_c","kind":"u32","values":[0]},{"id":"b_l","kind":"u32","values":[L-1]}],
    "dispatches":[{"kernel":"k_a05_1darr_read","textures":{"0":"t0"},"buffers":{"0":"OUT","1":"b_c","2":"b_l"}}]},
    1, pad([0xB6000000|((L-1)<<8)]), "ok", "a", "1D-array fetch at coord=0, last legal layer")
add("a05_1darr_read_illegal_layer", "a05", MF, {"textures":[tex1darr()], "buffers":[{"id":"b_c","kind":"u32","values":[0]},{"id":"b_l","kind":"u32","values":[L]}],
    "dispatches":[{"kernel":"k_a05_1darr_read","textures":{"0":"t0"},"buffers":{"0":"OUT","1":"b_c","2":"b_l"}}]},
    1, pad([None]), "ok", "c", "1D-array fetch at first illegal layer (layer==arrayLength); hypothesis: 0")
add("a05_1darr_sample_layer0", "a05", MF,
    {"textures":[{"id":"t0","type":"1darray","format":"r32float","width":W,"arrayLength":L,"usage":["read"],
                  "cpu_populate":[{"slice":l,"bytes_hex":texel_pattern_hex(0,W)} for l in range(L)]}],
     "samplers":[{"id":"s0","normalized":True,"filter":"nearest"}],
     "buffers":[{"id":"b_u","kind":"f32","values":[0.5]},{"id":"b_l","kind":"u32","values":[0]}],
     "dispatches":[{"kernel":"k_a05_1darr_sample","textures":{"0":"t0"},"samplers":{"0":"s0"},"buffers":{"1":"b_u","2":"b_l","0":"OUT"}}]},
    1, pad([None]), "ok", "c", "1D-array implicit-LOD sample at u=0.5 layer=0")
add("a05_1darr_size", "a05", MF, {"textures":[tex1darr()],
    "dispatches":[{"kernel":"k_a05_1darr_size","textures":{"0":"t0"},"buffers":{"0":"OUT"}}]},
    2, pad([W,L]), "ok", "a", "get_width()/get_array_size() on a 1D-array texture")


# ============================================================ GLTEX-A06: shadow/cube/cube-array
DL = 16
d2darr_pat = [{"slice": l, "bytes_hex": struct.pack("<f", l / DL).hex()} for l in range(DL)]
def d2darr():
    return {"id":"t0","type":"2darray","format":"depth32float","width":1,"height":1,"arrayLength":DL,"usage":["read"],
            "cpu_populate": d2darr_pat}

cmp_samplers = [{"id": f"s_{n}", "compare": n, "normalized": True, "filter": "nearest"}
                for n in ("less","lessequal","greater","greaterequal","equal","notequal","always","never")]
cmp_smap = {str(i): s["id"] for i, s in enumerate(cmp_samplers)}
add("a06_d2darr_compare_suite", "a06", MF,
    {"textures":[d2darr()], "samplers": cmp_samplers,
     "buffers":[{"id":"b_l","kind":"u32","values":[8]},{"id":"b_ref","kind":"f32","values":[0.5]}],
     "dispatches":[{"kernel":"k_a06_d2darr_compare_suite","textures":{"0":"t0"},"samplers":cmp_smap,
                    "buffers":{"1":"b_l","2":"b_ref","0":"OUT"}}]},
    8, pad([struct.unpack("<I", struct.pack("<f", x))[0] for x in (0.0,1.0,0.0,1.0,1.0,0.0,1.0,0.0)]),
    "ok", "b", "layer 8 (depth=0.5) vs ref=0.5, all 8 MTLCompareFunctions; documented rule is `ref COMPARISON storedDepth` (EXP-0034), so at the exact tie ref==depth=0.5: less=0,lessequal=1,greater=0,greaterequal=1,equal=1,notequal=0,always=1,never=0")

add("a06_d2darr_layer_boundary", "a06", MF,
    {"textures":[d2darr()], "samplers":[{"id":"s0","compare":"less","normalized":True,"filter":"nearest"}],
     "buffers":[{"id":"b_ls","kind":"u32","values":[0, DL-1, DL]}, {"id":"b_ref","kind":"f32","values":[0.999]}],
     "dispatches":[{"kernel":"k_a06_d2darr_layer_boundary","textures":{"0":"t0"},"samplers":{"0":"s0"},
                    "buffers":{"1":"b_ls","2":"b_ref","0":"OUT"}}]},
    3, pad([None,None,None]), "ok", "c",
    "compare 'less' ref=0.999 at layer=0 (depth 0.0, expect pass=1.0), layer=DL-1 (depth (DL-1)/DL, expect pass), layer=DL (first illegal layer, hypothesis: 0)")

add("a06_d2darr_forms", "a06", MF,
    {"textures":[d2darr()], "samplers":[{"id":"s0","compare":"less","normalized":True,"filter":"nearest"}],
     "buffers":[{"id":"b_l","kind":"u32","values":[8]},{"id":"b_ref","kind":"f32","values":[0.6]}],
     "dispatches":[{"kernel":"k_a06_d2darr_forms","textures":{"0":"t0"},"samplers":{"0":"s0"},
                    "buffers":{"1":"b_l","2":"b_ref","0":"OUT"}}]},
    6, pad([None]*6), "ok", "c",
    "2D-array depth: implicit/level/bias/gradient/offset sample_compare + gather_compare, same layer/ref, all should agree (depth 0.5 < ref 0.6 => 1.0)")

dcube_pat = [{"slice": f, "bytes_hex": struct.pack("<f", f / 6.0).hex()} for f in range(6)]
def dcube():
    return {"id":"t0","type":"cube","format":"depth32float","width":1,"height":1,"usage":["read"], "cpu_populate": dcube_pat}
add("a06_dcube_faces", "a06", MF,
    {"textures":[dcube()], "samplers":[{"id":"s0","compare":"less","normalized":True,"filter":"nearest"}],
     "buffers":[{"id":"b_ref","kind":"f32","values":[0.5]}],
     "dispatches":[{"kernel":"k_a06_dcube_faces","textures":{"0":"t0"},"samplers":{"0":"s0"},"buffers":{"1":"b_ref","0":"OUT"}}]},
    6, pad([struct.unpack("<I", struct.pack("<f", 1.0 if 0.5 < f/6.0 else 0.0))[0] for f in range(6)]),
    "ok", "b", "all 6 cube faces, distinguishable per-face depth = face/6, compare 'less' ref=0.5 evaluated as ref<storedDepth (EXP-0034 convention): faces 0-3 fail (depth<=0.5), faces 4,5 pass (depth>0.5)")
add("a06_dcube_forms", "a06", MF,
    {"textures":[dcube()], "samplers":[{"id":"s0","compare":"less","normalized":True,"filter":"nearest"}],
     "buffers":[{"id":"b_ref","kind":"f32","values":[0.6]}],
     "dispatches":[{"kernel":"k_a06_dcube_forms","textures":{"0":"t0"},"samplers":{"0":"s0"},"buffers":{"1":"b_ref","0":"OUT"}}]},
    4, pad([None]*4), "ok", "c", "cube face +x (depth 0/6=0.0): implicit/level/bias/gather_compare vs ref=0.6, expect all pass (1.0)")

dcubearr_pat = []
CAL = 2
for l in range(CAL):
    for f in range(6):
        dcubearr_pat.append({"slice": l*6+f, "bytes_hex": struct.pack("<f", (l*6+f)/(CAL*6)).hex()})
def dcubearr():
    return {"id":"t0","type":"cubearray","format":"depth32float","width":1,"height":1,"arrayLength":CAL,"usage":["read"],
            "cpu_populate": dcubearr_pat}
add("a06_dcubearr_faces", "a06", MF,
    {"textures":[dcubearr()], "samplers":[{"id":"s0","compare":"less","normalized":True,"filter":"nearest"}],
     "buffers":[{"id":"b_l","kind":"u32","values":[0]},{"id":"b_ref","kind":"f32","values":[0.5]}],
     "dispatches":[{"kernel":"k_a06_dcubearr_faces","textures":{"0":"t0"},"samplers":{"0":"s0"},"buffers":{"1":"b_l","2":"b_ref","0":"OUT"}}]},
    6, pad([struct.unpack("<I", struct.pack("<f", 1.0 if 0.5 < f/(CAL*6) else 0.0))[0] for f in range(6)]),
    "ok", "b", "cube-array layer=0, all 6 faces vs ref=0.5, ref<storedDepth convention: all 6 faces at layer 0 have depth<0.5, so all fail")
add("a06_dcubearr_layer_boundary", "a06", MF,
    {"textures":[dcubearr()], "samplers":[{"id":"s0","compare":"less","normalized":True,"filter":"nearest"}],
     "buffers":[{"id":"b_ls","kind":"u32","values":[0, CAL-1, CAL]}, {"id":"b_ref","kind":"f32","values":[0.999]}],
     "dispatches":[{"kernel":"k_a06_dcubearr_layer_boundary","textures":{"0":"t0"},"samplers":{"0":"s0"},
                    "buffers":{"1":"b_ls","2":"b_ref","0":"OUT"}}]},
    3, pad([None,None,None]), "ok", "c", "cube-array face +x, layer=0 / layer=CAL-1 / layer=CAL (first illegal), ref=0.999")
add("a06_dcubearr_forms", "a06", MF,
    {"textures":[dcubearr()], "samplers":[{"id":"s0","compare":"less","normalized":True,"filter":"nearest"}],
     "buffers":[{"id":"b_l","kind":"u32","values":[0]},{"id":"b_ref","kind":"f32","values":[0.6]}],
     "dispatches":[{"kernel":"k_a06_dcubearr_forms","textures":{"0":"t0"},"samplers":{"0":"s0"},"buffers":{"1":"b_l","2":"b_ref","0":"OUT"}}]},
    4, pad([None]*4), "ok", "c", "cube-array layer=0 face+x: implicit/level/bias/gather_compare vs ref=0.6")


# ============================================================ GLTEX-A04: array-layer conversion + boundary
AL = 8
a04_2darr_pat = [{"slice": l, "bytes_hex": u32le_hex(0xD4000000 | l)} for l in range(AL)]
def a04_2darr(fmt="r32uint", usage=("read",)):
    return {"id":"t0","type":"2darray","format":fmt,"width":1,"height":1,"arrayLength":AL,"usage":list(usage),
            "cpu_populate": a04_2darr_pat}
conv_inputs = [2.0, 2.5, 2.4, 2.6, -0.5, -0.0, 6.0, 0.0, 3.0]  # last two are placeholders for inf/nan noted in RESULTS
add("a04_2darr_conversion", "a04", MF,
    {"textures":[a04_2darr()], "buffers":[{"id":"b_layers","kind":"f32","values":conv_inputs}],
     "dispatches":[{"kernel":"k_a04_2darr_conversion","textures":{"0":"t0"},"buffers":{"1":"b_layers","0":"OUT"}}]},
    9, pad([None]*9), "ok", "c",
    "software round(layer) then uint cast, 9 candidate float layer inputs {2.0,2.5,2.4,2.6,-0.5,-0.0,6.0(=AL,illegal),0.0,3.0}; observe MSL's own round()+uint() composition, NOT a raw hardware float-coordinate instruction (none exists at the public-Metal level; see PRE_REGISTRATION.md ISA caveat)")
add("a04_2darr_boundary_sample", "a04", MF,
    {"textures":[a04_2darr(fmt="r32float")], "samplers":[{"id":"s0","normalized":True,"filter":"nearest"}],
     "buffers":[{"id":"b_ls","kind":"u32","values":[0, AL-1, AL]}],
     "dispatches":[{"kernel":"k_a04_2darr_boundary_sample","textures":{"0":"t0"},"samplers":{"0":"s0"},"buffers":{"1":"b_ls","0":"OUT"}}]},
    3, pad([None,None,None]), "ok", "c", "sample() at layer 0 / AL-1 / AL(first illegal)")
add("a04_2darr_boundary_fetch", "a04", MF,
    {"textures":[a04_2darr()], "buffers":[{"id":"b_ls","kind":"u32","values":[0, AL-1, AL]}],
     "dispatches":[{"kernel":"k_a04_2darr_boundary_fetch","textures":{"0":"t0"},"buffers":{"1":"b_ls","0":"OUT"}}]},
    3, pad([0xD4000000, 0xD4000000|(AL-1), None]), "ok", "c", "read() at layer 0 / AL-1 (exact) / AL(first illegal, hypothesis 0)")
add("a04_2darr_boundary_gather", "a04", MF,
    {"textures":[a04_2darr(fmt="r32float")], "samplers":[{"id":"s0","normalized":True,"filter":"nearest"}],
     "buffers":[{"id":"b_ls","kind":"u32","values":[0, AL-1, AL]}],
     "dispatches":[{"kernel":"k_a04_2darr_boundary_gather","textures":{"0":"t0"},"samplers":{"0":"s0"},"buffers":{"1":"b_ls","0":"OUT"}}]},
    3, pad([None,None,None]), "ok", "c", "gather() at layer 0 / AL-1 / AL(first illegal)")

a04_cubearr_pat = [{"slice": l*6+f, "bytes_hex": u32le_hex(0xCA000000|(l<<4)|f)} for l in range(2) for f in range(6)]
def a04_cubearr(fmt="r32uint"):
    return {"id":"t0","type":"cubearray","format":fmt,"width":1,"height":1,"arrayLength":2,"usage":["read"], "cpu_populate": a04_cubearr_pat}
add("a04_cubearr_conversion", "a04", MF,
    {"textures":[a04_cubearr()], "buffers":[{"id":"b_layers","kind":"f32","values":conv_inputs}],
     "dispatches":[{"kernel":"k_a04_cubearr_conversion","textures":{"0":"t0"},"buffers":{"1":"b_layers","0":"OUT"}}]},
    9, pad([None]*9), "ok", "c", "cube-array analogue of a04_2darr_conversion (AL replaced by array length 2, illegal candidate is 6.0)")
add("a04_cubearr_boundary_fetch", "a04", MF,
    {"textures":[a04_cubearr()], "buffers":[{"id":"b_ls","kind":"u32","values":[0, 1, 2]}],
     "dispatches":[{"kernel":"k_a04_cubearr_boundary_fetch","textures":{"0":"t0"},"buffers":{"1":"b_ls","0":"OUT"}}]},
    3, pad([0xCA000000, 0xCA000010, None]), "ok", "c", "cube-array read() face+x at layer 0/1(last legal)/2(first illegal)")
add("a04_cubearr_boundary_sample", "a04", MF,
    {"textures":[a04_cubearr(fmt="r32float")], "samplers":[{"id":"s0","normalized":True,"filter":"nearest"}],
     "buffers":[{"id":"b_ls","kind":"u32","values":[0,1,2]}],
     "dispatches":[{"kernel":"k_a04_cubearr_boundary_sample","textures":{"0":"t0"},"samplers":{"0":"s0"},"buffers":{"1":"b_ls","0":"OUT"}}]},
    3, pad([None,None,None]), "ok", "c", "cube-array sample() face+x at layer 0/1/2(illegal)")


# ============================================================ GLTEX-A07: texel-buffer boundary
# Content is built per the ACTUAL per-texel byte layout of each format (R
# channel only, since every a07 kernel reads/writes just .x): r8uint = 1
# byte/texel (the whole value IS the R channel, range 0..255, no room for a
# 0x11-style marker prefix); rg8uint = 2 bytes/texel (R byte + G marker
# byte); rgba8uint = 4 bytes/texel (R byte + G/B/A marker bytes);
# rgba16uint = 8 bytes/texel (R uint16 + 3 marker uint16s); rgba32uint = 16
# bytes/texel (R uint32 + 3 marker uint32s, the only format where a full
# 32-bit marked value like 0xAA0000xx fits in the R channel itself).
TN = 64
def texel_row(fmt, i):
    if fmt == "r8uint":
        return struct.pack("<B", i & 0xFF)
    if fmt == "rg8uint":
        return struct.pack("<BB", i & 0xFF, 0x22)
    if fmt == "rgba8uint":
        return struct.pack("<BBBB", i & 0xFF, 0x44, 0x44, 0x44)
    if fmt == "rgba16uint":
        return struct.pack("<HHHH", i & 0xFFFF, 0x8888, 0x8888, 0x8888)
    if fmt == "rgba32uint":
        return struct.pack("<IIII", (0xAA000000 | i) & 0xFFFFFFFF, 0xAAAAAAAA, 0xAAAAAAAA, 0xAAAAAAAA)
    raise ValueError(fmt)
def expected_r(fmt, i):
    if fmt == "r8uint": return i & 0xFF
    if fmt == "rg8uint": return i & 0xFF
    if fmt == "rgba8uint": return i & 0xFF
    if fmt == "rgba16uint": return i & 0xFFFF
    if fmt == "rgba32uint": return (0xAA000000 | i) & 0xFFFFFFFF
    raise ValueError(fmt)
def tb(fmt):
    n = TN
    pat = b"".join(texel_row(fmt, i) for i in range(n)).hex()
    return {"id":"t0","type":"buffer","format":fmt,"width":n,"usage":["read","write"],"init_hex":pat}

texel_formats = [("r8uint", "r8"), ("rg8uint", "rg8"), ("rgba8uint", "rgba8"),
                 ("rgba16uint", "rgba16"), ("rgba32uint", "rgba32")]
for fmt, tag in texel_formats:
    kread = f"k_a07_tb_read3_{tag}"
    kwrite = f"k_a07_tb_write3_{tag}"
    add(f"a07_tb_{tag}_read3", "a07", MF,
        {"textures":[tb(fmt)], "buffers":[{"id":"b_idx","kind":"u32","values":[0, TN-1, TN]}],
         "dispatches":[{"kernel":kread,"textures":{"0":"t0"},"buffers":{"1":"b_idx","0":"OUT"}}]},
        3, pad([expected_r(fmt,0), expected_r(fmt,TN-1), None]), "ok", "c",
        f"{tag} texel-buffer read at element 0 / {TN-1}(last legal) / {TN}(first invalid); last-legal exact, first-invalid hypothesis 0")
    add(f"a07_tb_{tag}_write3", "a07", MF,
        {"textures":[tb(fmt)], "buffers":[{"id":"b_idx","kind":"u32","values":[0, TN-1, TN]}],
         "dispatches":[{"kernel":kwrite,"textures":{"0":"t0"},"buffers":{"1":"b_idx"}},
                        {"kernel":kread, "textures":{"0":"t0"},"buffers":{"1":"b_idx","0":"OUT"}}]},
        3, pad([0xFF if fmt in ("r8uint","rg8uint","rgba8uint") else 0xFFFF if fmt == "rgba16uint" else 0xC0FFEE, None, None]), "ok", "c",
        f"{tag} texel-buffer write(0xC0FFEE) at element 0 / {TN-1} / {TN}(OOB); readback via read3 at the same three indices to see what actually landed")

add("a07_tb_size", "a07", MF, {"textures":[tb("r8uint")],
    "dispatches":[{"kernel":"k_a07_tb_size","textures":{"0":"t0"},"buffers":{"0":"OUT"}}]},
    1, pad([TN]), "ok", "a", "get_width() on a texture_buffer equals the declared element count")


WMAX = 268435456
for fmt, tag in (("r8uint", "1B"), ("rgba32uint", "16B")):
    add(f"a07_descriptor_ok_{tag}", "a07_descriptor", MF, {"format": fmt, "width": WMAX},
        0, pad([]), "ok", "a", f"{tag}-texel texture_buffer at the exact width ceiling 2^28={WMAX}: descriptor accepted")
    add(f"a07_descriptor_over_{tag}", "a07_descriptor", MF, {"format": fmt, "width": WMAX + 1},
        0, pad([]), "abort", "a", f"{tag}-texel texture_buffer at width 2^28+1: MTLTextureDescriptor validation aborts the process (SIGABRT) before any GPU submission, uniformly across texel size -- pre-established by pre-freeze exploration, re-confirmed here as frozen evidence")

# ============================================================ GLIMG-A01: image op x dimension matrix
def a01_case(dim, kernel, expected3, note, extra_textures=None, extra_buffers=None, extra_dispatch=None, n_out=3):
    tex = {"id":"t0"}
    tex.update(dim)
    dispatches = [{"kernel": kernel, "textures": {"0": "t0"}, "buffers": {"0": "OUT"}}]
    args = {"textures": [tex] + (extra_textures or []), "buffers": extra_buffers or [], "dispatches": extra_dispatch or dispatches}
    add(f"a01_{kernel[6:]}", "a01", MF, args, n_out, pad(expected3), "ok", "c", note)

a01_dims = [
    ({"type":"1d","format":"r32uint","width":4,"usage":["read","write"]}, "k_a01_1d", [0x1D000001, 4, 1]),
    ({"type":"1darray","format":"r32uint","width":4,"arrayLength":2,"usage":["read","write"]}, "k_a01_1darr", [0x1D000002, 4, 2]),
    ({"type":"2d","format":"r32uint","width":4,"height":4,"usage":["read","write"]}, "k_a01_2d", [0x2D000001, 4, 4]),
    ({"type":"2darray","format":"r32uint","width":4,"height":4,"arrayLength":2,"usage":["read","write"]}, "k_a01_2darr", [0x2D000002, 4, 2]),
    ({"type":"3d","format":"r32uint","width":4,"height":4,"depth":2,"usage":["read","write"]}, "k_a01_3d", [0x3D000001, 4, 2]),
    ({"type":"cube","format":"r32uint","width":4,"height":4,"usage":["read","write"]}, "k_a01_cube", [0xCB000001, 4, None]),
    ({"type":"cubearray","format":"r32uint","width":4,"height":4,"arrayLength":2,"usage":["read","write"]}, "k_a01_cubearr", [0xCB000002, 4, 2]),
    ({"type":"buffer","format":"r8uint","width":8,"usage":["read","write"]}, "k_a01_buffer", [0xFF, 8, None]),  # 0xB0000001 clamps to the r8uint channel max (255)
]
for dim, kernel, expected in a01_dims:
    a01_case(dim, kernel, expected, f"image store+load+size round trip on {dim['type']} (r32uint canary 0x{expected[0]:08X})")

add("a01_2dms_read", "a01", MF,
    {"textures":[{"id":"t0","type":"2dms","format":"r32uint","width":4,"height":4,"sampleCount":4,"usage":["read"]}],
     "dispatches":[{"kernel":"k_a01_2dms_read","textures":{"0":"t0"},"buffers":{"0":"OUT"}}]},
    3, pad([None,4,4]), "ok", "c", "2D multisample image read+size+sample-count query (no access::write path exists for MS in MSL; content left at storage default, only whether the pipeline/dispatch itself succeeds is under test)")
add("a01_2dmsarr_read", "a01", MF,
    {"textures":[{"id":"t0","type":"2dmsarray","format":"r32uint","width":4,"height":4,"arrayLength":2,"sampleCount":4,"usage":["read"]}],
     "dispatches":[{"kernel":"k_a01_2dmsarr_read","textures":{"0":"t0"},"buffers":{"0":"OUT"}}]},
    4, pad([None,4,4,2]), "ok", "c", "2D multisample-array image read+size+sample-count+array-size query")

fmt_cases = [
    ("k_a01_fmt_r32float", "r32float", [struct.unpack("<I", struct.pack("<f", 0.25))[0]], "float32 image store/load round trip"),
    ("k_a01_fmt_r8unorm", "r8unorm", [None], "r8unorm image store(0.5)/load round trip -- conversion rule is DRV-FMT-01's domain, this only tests the image path exists"),
    ("k_a01_fmt_r8snorm", "r8snorm", [None], "r8snorm image store(-0.5)/load round trip"),
    ("k_a01_fmt_r16uint", "r16uint", [4321], "r16uint image store/load round trip, exact integer"),
    ("k_a01_fmt_r16sint", "r16sint", [struct.unpack("<I", struct.pack("<i", -1234))[0]], "r16sint image store/load round trip, exact integer (bit pattern of -1234)"),
    ("k_a01_fmt_rgb10a2unorm", "rgb10a2unorm", [None, None], "rgb10a2unorm packed-format image store/load round trip (R and A channels)"),
]
for kernel, fmt, expected, note in fmt_cases:
    n = len(expected)
    add(f"a01_{kernel[6:]}", "a01", MF,
        {"textures":[{"id":"t0","type":"2d","format":fmt,"width":1,"height":1,"usage":["read","write"]}],
         "dispatches":[{"kernel":kernel,"textures":{"0":"t0"},"buffers":{"0":"OUT"}}]},
        n, pad(expected), "ok", "c" if any(e is None for e in expected) else "b", note)

add("a01_2d_oob_read", "a01", MF,
    {"textures":[{"id":"t0","type":"2d","format":"r32uint","width":4,"height":4,"usage":["read","write"]}],
     "buffers":[{"id":"b_wh","kind":"u32","values":[4,4]}],
     "dispatches":[{"kernel":"k_a01_2d_oob_read","textures":{"0":"t0"},"buffers":{"1":"b_wh","0":"OUT"}}]},
    3, pad([None,None,None]), "ok", "c", "2D image read at (width,0)/(0,height)/(width,height) -- first invalid coordinate on each axis and both; hypothesis: 0")
add("a01_2d_oob_write", "a01", MF,
    {"textures":[{"id":"t0","type":"2d","format":"r32uint","width":4,"height":4,"usage":["read","write"]}],
     "buffers":[{"id":"b_wh","kind":"u32","values":[4,4]}],
     "dispatches":[{"kernel":"k_a01_2d_oob_write","textures":{"0":"t0"},"buffers":{"1":"b_wh"}},
                    {"kernel":"k_a01_2d_oob_readback","textures":{"0":"t0"},"buffers":{"1":"b_wh","0":"OUT"}}]},
    16, pad([0]*16), "ok", "c", "2D image OOB write at (width,0) and (0,height) [both never-written, texture default-initialized to 0], then full in-bounds readback (16 texels) to detect aliasing into legal texels")
add("a01_cube_oob_read", "a01", MF,
    {"textures":[{"id":"t0","type":"cube","format":"r32uint","width":4,"height":4,"usage":["read","write"]}],
     "buffers":[{"id":"b_w","kind":"u32","values":[4]}],
     "dispatches":[{"kernel":"k_a01_cube_oob_read","textures":{"0":"t0"},"buffers":{"1":"b_w","0":"OUT"}}]},
    2, pad([None,None]), "ok", "c", "cube image OOB x-coordinate within a valid face, and face index 6 (first invalid face); hypothesis: 0")
add("a01_partial_write", "a01", MF,
    {"textures":[{"id":"t0","type":"2d","format":"r32uint","width":1,"height":1,"usage":["read","write"]}],
     "dispatches":[{"kernel":"k_a01_partial_write","textures":{"0":"t0"},"buffers":{"0":"OUT"}}]},
    4, pad([0x99999999, None, None, None]), "ok", "c",
    "write(uint4) to a single-channel r32uint image, then read .x/.y/.z/.w -- does a single-channel format silently drop the other 3 written components on readback (hypothesis: yes, .x only)")
add("a01_unbound_read", "a01", MF,
    {"textures":[], "dispatches":[{"kernel":"k_a01_unbound_read","textures":{},"buffers":{"0":"OUT"}}]},
    1, pad([None]), "ok", "c", "texture argument declared but never bound at dispatch (no debug/validation layer); hypothesis: read returns 0")
add("a01_unbound_write", "a01", MF,
    {"textures":[], "dispatches":[{"kernel":"k_a01_unbound_write","textures":{},"buffers":{}}]},
    0, pad([]), "ok", "c", "write to an unbound texture argument; hypothesis: silently dropped, command buffer still completes")
add("a01_alias", "a01", MF,
    {"textures":[{"id":"t0","type":"2d","format":"r32uint","width":1,"height":1,"usage":["read","write"]}],
     "dispatches":[{"kernel":"k_a01_alias","textures":{"0":"t0","1":"t0"},"buffers":{"0":"OUT"}}]},
    1, pad([0xA11A5000]), "ok", "c", "same underlying MTLTexture bound simultaneously read_write at slot0 and read-only at slot1 in one kernel invocation, write-then-read with no explicit barrier -- same-thread same-invocation visibility")


# ============================================================ GLIMG-A02: image-descriptor capacity census
# Direct-binding path (128-entry [[texture(N)]] table established by
# pre-freeze exploration; access::read_write capped at 8 regardless).
def direct_textures(n, fmt="r32uint", usage=("read",)):
    out = []
    for i in range(n):
        v = 0xD00D0000 | i
        out.append({"id": f"t{i}", "type": "2d", "format": fmt, "width": 1, "height": 1, "usage": list(usage),
                    "cpu_populate": [{"slice": 0, "bytes_hex": u32le_hex(v)}]})
    return out

direct_texmap = {str(i): f"t{i}" for i in range(128)}
add("a02_direct_read_boundary", "a02_direct", DF,
    {"textures": direct_textures(128), "buffers": [{"id":"b_idx","kind":"u32","values":[0, 63, 127, 4294967295]}],
     "dispatches": [{"kernel":"k_a02_direct_read","textures":direct_texmap,"buffers":{"0":"b_idx","1":"OUT"}}]},
    4, pad([0xD00D0000, 0xD00D0000|63, 0xD00D0000|127, None]), "ok", "a",
    "128 direct [[texture(N)]] read-access slots (the exact ceiling from pre-freeze exploration), read at index 0/63/127 (exact) and idx=UINT32_MAX (no compile-time branch matches, kernel's own 0xFFFFFFFF sentinel expected -- NOT a hardware runtime-selector overflow, since the direct index is chosen at COMPILE time, not runtime; see RESULTS for this distinction from EXP-0083's runtime byte-splice census)",
    timeout=90)

direct_texmap_w = {str(i): f"t{i}" for i in range(128)}
add("a02_direct_write_and_readback", "a02_direct", DF,
    {"textures": direct_textures(128, usage=("read","write")), "buffers": [{"id":"b_idx","kind":"u32","values":[5]}],
     "dispatches": [{"kernel":"k_a02_direct_write","textures":direct_texmap_w,"buffers":{"0":"b_idx"}},
                     {"kernel":"k_a02_direct_readback8","textures":{str(i): f"t{i}" for i in range(8)},"buffers":{"0":"OUT"}}]},
    8, pad([0xD00D0000,0xD00D0001,0xD00D0002,0xD00D0003,0xD00D0004,0xC0FFEE,0xD00D0006,0xD00D0007]), "ok", "b",
    "128 direct write-access slots (access::write is NOT subject to the 8-slot read_write ceiling, per pre-freeze exploration), write at index 5, readback first 8 canaries -- only index 5 should change",
    timeout=90)

def direct_texture_buffers(n, fmt="r8uint"):
    out = []
    for i in range(n):
        out.append({"id": f"t{i}", "type": "buffer", "format": fmt, "width": 1, "usage": ["read", "write"],
                    "init_hex": ("%02x" % (i & 0xFF))})
    return out
rw8_texmap = {str(i): f"t{i}" for i in range(8)}
add("a02_direct_atomic_boundary", "a02_direct", DF,
    {"textures": direct_texture_buffers(8),
     "buffers": [{"id":"b_idx","kind":"u32","values":[7]}],
     "dispatches": [{"kernel":"k_a02_direct_atomic","textures":rw8_texmap,"buffers":{"0":"b_idx","1":"OUT"}}]},
    1, pad([7]), "ok", "a",
    "the read_write (atomic) ceiling is 8, not 128 (pre-freeze exploration: MSL rejects a 9th access::read_write texture argument at compile time). atomic_fetch_add(+1) at the last legal read_write slot (index 7, texture_buffer<uint> -- fixed from an earlier draft that mismatched the kernel's declared texture_buffer argument type with a plain texture2d resource); out[0] = the value atomic_fetch_add returns (the PRE-add value, 7, since slot i was CPU-populated with content i)",
    timeout=90)
add("a02_direct_atomic_illegal", "a02_direct", DF,
    {"textures": direct_texture_buffers(8),
     "buffers": [{"id":"b_idx","kind":"u32","values":[8]}],
     "dispatches": [{"kernel":"k_a02_direct_atomic","textures":rw8_texmap,"buffers":{"0":"b_idx","1":"OUT"}}]},
    1, pad([0xFFFFFFFF]), "ok", "a",
    "atomic_fetch_add with idx=8: no compile-time branch matches any of the 8 declared read_write slots (there is no 9th slot to select -- this is the direct path's structural ceiling, not a runtime OOB read); kernel's own not-matched sentinel expected",
    timeout=90)

# Bindless (argument-buffer) path: CAP=256 array entries, K=8 populated canaries.
CAP = 256
K = 8
def canary_textures(prefix, fmt="r32uint", usage=("read",), ttype="2d"):
    out = []
    for i in range(K):
        if ttype == "buffer":
            out.append({"id": f"c{i}", "type": "buffer", "format": fmt, "width": 1, "usage": list(usage),
                        "init_hex": u32le_hex(prefix | i)})
        else:
            out.append({"id": f"c{i}", "type": ttype, "format": fmt, "width": 1, "height": 1, "usage": list(usage),
                        "cpu_populate": [{"slice": 0, "bytes_hex": u32le_hex(prefix | i)}]})
    return out
def ab_entries():
    return [{"index": i, "texture": f"c{i}"} for i in range(K)]

for idx, tag, rule, note in [
    (0, "first_populated", "a", "first populated (canary 0)"),
    (K-1, "last_populated", "a", "last populated canary (index K-1)"),
    (K, "first_hole", "c", "first in-array, never-encoded hole (index K, < CAP); hypothesis: 0 (guard-fill 0xDE...DE does not decode to a valid resource)"),
    (CAP-1, "last_hole", "c", "last in-array hole (index CAP-1)"),
    (CAP, "first_oob", "c", "first index beyond the declared array bound (index == CAP); C++-style array OOB, real hardware behavior under test"),
    (CAP*2-1, "oob_2x_minus1", "c", "OOB stress point just below 2*CAP"),
    (CAP*2, "mirror_probe", "c", "OOB at exactly 2*CAP -- mirroring probe in the EXP-0083 tradition (that experiment found the buffer base-slot selector mirrors at a power-of-two period); hypothesis: either 0 (no mirroring) or equals index-0's content (period-CAP mirroring)"),
    (4294967295, "uint_max", "c", "UINT32_MAX, the most extreme out-of-range selector"),
]:
    add(f"a02_bindless_read_{tag}", "a02_bindless", MF,
        {"textures": canary_textures(0xB0000000), "buffers": [{"id":"b_idx","kind":"u32","values":[idx]}],
         "argument_buffers": [{"id":"ab0","struct":"AB_Read","entries": ab_entries()}],
         "dispatches": [{"kernel":"k_a02_bindless_read","textures":{},"buffers":{"0":"ARGBUF:ab0","1":"b_idx","2":"OUT"}}]},
        1, pad([0xB0000000|idx if idx < K else None]), "ok", rule, f"bindless read at index={idx}: {note}", timeout=90)

for idx, tag in [(0,"first_populated"), (K,"first_hole"), (CAP,"first_oob"), (CAP*2,"mirror_probe")]:
    add(f"a02_bindless_write_{tag}", "a02_bindless", MF,
        {"textures": canary_textures(0xB1000000, usage=("read","write")), "buffers": [{"id":"b_idx","kind":"u32","values":[idx]}],
         "argument_buffers": [{"id":"ab0","struct":"AB_Write","entries": ab_entries()}],
         "dispatches": [{"kernel":"k_a02_bindless_write","textures":{},"buffers":{"0":"ARGBUF:ab0","1":"b_idx"}},
                         {"kernel":"k_a02_canary_readback8","textures":{str(i): f"c{i}" for i in range(K)},"buffers":{"0":"OUT"}}]},
        8, pad([(0xC0FFEE if i == idx else 0xB1000000 | i) for i in range(K)]),
        "ok", "a" if idx == 0 else "c",
        f"bindless write(0xC0FFEE) at index={idx} ({tag}), then CPU-independent readback of all K=8 canary textures to detect aliasing/corruption",
        timeout=90)

for idx, tag in [(0,"first_populated"), (K,"first_hole"), (CAP,"first_oob"), (CAP*2,"mirror_probe")]:
    add(f"a02_bindless_atomic_{tag}", "a02_bindless", MF,
        {"textures": canary_textures(0xB2000000, fmt="r8uint", usage=("read","write"), ttype="buffer"),
         "buffers": [{"id":"b_idx","kind":"u32","values":[idx]}],
         "argument_buffers": [{"id":"ab0","struct":"AB_Atomic","entries": ab_entries()}],
         "dispatches": [{"kernel":"k_a02_bindless_atomic","textures":{},"buffers":{"0":"ARGBUF:ab0","1":"b_idx","2":"OUT"}},
                         {"kernel":"k_a02_canary_readback8_tb","textures":{str(i): f"c{i}" for i in range(K)},"buffers":{"0":"OUT"}}]},
        8, pad([None]*8), "ok", "c" if idx else "b",
        f"bindless atomic_fetch_add at index={idx} ({tag}), then a SECOND dispatch (canary readback) that reuses the same OUT buffer -- out[] in the frozen record is the K=8 canary texture_buffer readback ONLY; the atomic's own previous-value output from the first dispatch is overwritten by the second dispatch's writes to the same buffer offsets (a known design limitation, not a claim about the atomic's return value; the readback still validly answers 'did the OOB/hole atomic corrupt a real entry')",
        timeout=90)


# ---------------------------------------------------------------- emit
if __name__ == "__main__":
    print("total cases:", len(cases))
    by_family = {}
    for c in cases:
        by_family.setdefault(c["family"], 0)
        by_family[c["family"]] += 1
    for f, n in sorted(by_family.items()):
        print(f"  {f}: {n}")
    ids = [c["case"] for c in cases]
    dupes = set(x for x in ids if ids.count(x) > 1)
    if dupes:
        raise SystemExit("DUPLICATE CASE IDS: " + str(dupes))
    import pathlib
    out = pathlib.Path(__file__).resolve().parent / "cases_generated.json"
    out.write_text(json.dumps(cases, indent=2, sort_keys=True) + "\n")
    print("wrote", out)
