"""EXP-0134 frozen case matrix (DRV-P2-01 lossless compression). Imported by
run.py (producer) and verify.py (consumer). Pure data + pure functions, no
device/filesystem access at import time.

Every case creates a texture with MTLTextureUsageShaderRead present (see
PRE_REGISTRATION.md scope note: this lets every case use the single established
bind-and-read descriptor-capture method; RT-only/write-only-without-ShaderRead
resource classes are explicitly out of scope). `decode` selects how run.py turns
the raw iotrace dump(s) into the case's OBSERVED dict:
  "descriptor"  -- one dump, decode the sampled texture descriptor + aux (harness/auxdecode.py)
  "descriptor2" -- two dumps (dump_after_write + final dump, IOTRACE_DUMP_PERSIG),
                   decode both and diff (CPU-op before/after cases)
  "replicate"   -- N identical small textures in one process; OBSERVED = base_va deltas
  "stdout"      -- no descriptor decode needed; OBSERVED comes entirely from cprobe's
                   own STATUS/CONFIG/*_OK stdout lines (creation-reject / API-behavior cases)
"""

MATRIX = []


def _add(cid, family, kind, binary_kind, params, decode, note=""):
    MATRIX.append({"id": cid, "family": family, "kind": kind, "binary_kind": binary_kind,
                    "params": params, "decode": decode, "note": note})


# ===========================================================================
# Group ELIG -- eligibility: usage / storage / type / linear / size boundary
# ===========================================================================
_usage_combos = [
    ("read", "read"),
    ("read_rt", "read,rt"),
    ("read_write", "read,write"),
    ("read_rt_write", "read,rt,write"),
    ("read_pfview", "read,pfview"),
    ("read_rt_pfview", "read,rt,pfview"),
]
for name, usage in _usage_combos:
    for sz, tag in ((32, "elig"), (8, "sub")):
        _add(f"e_usage_{name}_{tag}", "elig", "elig_usage", "probe",
             {"fmt": "rgba8unorm", "w": sz, "h": sz, "usage": usage, "pattern": "clear",
              "r": 0.4, "g": 0.4, "b": 0.4, "a": 1.0, "dump": True},
             "descriptor", f"usage={usage} size={sz}")

_storage_combos = [
    ("private_read", "private", "read"),
    ("private_read_write", "private", "read,write"),
    ("memoryless_read", "memoryless", "read"),
    ("memoryless_read_rt", "memoryless", "read,rt"),
]
for name, storage, usage in _storage_combos:
    _add(f"e_storage_{name}", "elig", "elig_storage", "probe",
         {"fmt": "rgba8unorm", "w": 32, "h": 32, "usage": usage, "storage": storage,
          "pattern": "clear", "r": 0.4, "g": 0.4, "b": 0.4, "a": 1.0, "dump": True},
         "descriptor", f"storage={storage} usage={usage}")

_type_cases = [
    ("array_elig", "2darray", 32, 32, 2, 1, "read"),
    ("array_sub",  "2darray", 8,  8,  2, 1, "read"),
    ("cube_elig",  "cube",    32, 32, 1, 1, "read"),
    ("cube_sub",   "cube",    8,  8,  1, 1, "read"),
    ("3d_elig",    "3d",      32, 32, 4, 1, "read"),
    ("3d_sub",     "3d",      8,  8,  4, 1, "read"),
    ("msaa2_elig", "2dms",    64, 64, 1, 2, "read,rt"),
    ("msaa4_elig", "2dms",    64, 64, 1, 4, "read,rt"),
    ("msaa2_sub",  "2dms",    8,  8,  1, 2, "read,rt"),
]
for name, typ, w, h, d, samples, usage in _type_cases:
    _add(f"e_type_{name}", "elig", "elig_type", "probe",
         {"fmt": "rgba8unorm", "w": w, "h": h, "d": d, "type": typ, "samples": samples,
          "usage": usage, "pattern": "clear" if typ in ("2dms",) else "none", "dump": True},
         "descriptor", f"type={typ} {w}x{h}x{d} samples={samples}")

for name, w, h, usage in (("linear_read", 64, 64, "read"), ("linear_read_rt", 64, 64, "read,rt")):
    _add(f"e_linear_{name}", "elig", "elig_linear", "probe",
         {"fmt": "rgba8unorm", "w": w, "h": h, "usage": usage, "linear": True,
          "pattern": "gradient", "dump": True},
         "descriptor", "buffer-backed linear texture must never compress")

for name, w, h in (("15x15", 15, 15), ("16x16", 16, 16), ("16x15", 16, 15), ("15x16", 15, 16)):
    _add(f"e_boundary_{name}", "elig", "elig_boundary", "probe",
         {"fmt": "rgba8unorm", "w": w, "h": h, "usage": "read", "pattern": "clear",
          "r": 0.4, "g": 0.4, "b": 0.4, "a": 1.0, "dump": True},
         "descriptor", f"threshold reconfirm {w}x{h}")

# ===========================================================================
# Group AUX -- geometry: bpp/size formula, MSAA ratio, alloc floor, mips
# ===========================================================================
import math as _math


def _dedicated_bo_size_pow2(bpp):
    """Smallest power-of-two square texture side whose main-image byte count clears
    the empirically-observed ~16KiB (0x4000) dedicated-BO threshold (PROGRESS.md
    milestone 2: below this, compression-eligible textures are suballocated from a
    SHARED heap BO and the BO-size-minus-offset aux measurement is invalid). Chosen
    per-bpp so every aux_bpp_size case gets a clean, directly-measurable dedicated BO."""
    side = 1
    while side * side * bpp < 0x4000:
        side *= 2
    return side


# bpp lookup mirrors the FMTS table in harness/cprobe.m
_BPP = {"r8unorm": 1, "r16float": 2, "rgba8unorm": 4, "r32uint": 4, "rgba8uint": 4,
        "rgba16float": 8, "rgba32float": 16}
_aux_formats = ["r8unorm", "r16float", "rgba8unorm", "rgba16float", "rgba32float", "r32uint", "rgba8uint"]
for fmt in _aux_formats:
    s1 = _dedicated_bo_size_pow2(_BPP[fmt])
    s2 = s1 * 2
    for sz in (s1, s2):
        _add(f"a_bpp_{fmt}_{sz}", "aux", "aux_bpp_size", "probe",
             {"fmt": fmt, "w": sz, "h": sz, "usage": "read", "pattern": "gradient", "dump": True},
             "descriptor", f"numTexels/32 formula check {fmt} {sz}x{sz} (bpp={_BPP[fmt]})")

# Adversarial: a dedicated-BO case whose numTexels/32 formula predicts an aux size
# well under 128 bytes, to pin down the minimum-aux-allocation-floor anomaly found
# during pipeline validation (rgba32float 32x32: formula predicts 32B, measured
# 128B -- see PROGRESS.md). Non-square, different predicted value (64B), to
# distinguish "hard 128B floor" from "always 4x formula".
_add("a_bpp_rgba32float_32x64", "aux", "aux_bpp_size", "probe",
     {"fmt": "rgba32float", "w": 32, "h": 64, "usage": "read", "pattern": "gradient", "dump": True},
     "descriptor", "minimum-aux-floor adversarial probe: formula predicts 64B (non-square, bpp16)")

for fmt in ("rgba8unorm", "r16float"):
    # size chosen so even the N=1 (no-MSAA) baseline clears the dedicated-BO threshold
    # (see _dedicated_bo_size_pow2 above); N=2/4 only grow the per-pixel footprint.
    msz = _dedicated_bo_size_pow2(_BPP[fmt])
    for n in (1, 2, 4):
        typ = "2d" if n == 1 else "2dms"
        _add(f"a_msaa_{fmt}_n{n}", "aux", "aux_msaa_ratio", "probe",
             {"fmt": fmt, "w": msz, "h": msz, "type": typ, "samples": n, "usage": "read,rt",
              "pattern": "clear", "r": 0.3, "g": 0.3, "b": 0.3, "a": 1.0, "dump": True},
             "descriptor", f"MSAA aux ratio {fmt} N={n} size={msz}")

_floor_cases = [
    ("rgba8_16", "rgba8unorm", 16, 16),
    ("rgba8_20", "rgba8unorm", 20, 20),
    ("r8_16", "r8unorm", 16, 16),
    ("rgba32f_16", "rgba32float", 16, 16),
]
for name, fmt, w, h in _floor_cases:
    _add(f"a_floor_{name}", "aux", "aux_alloc_floor", "replicate",
         {"fmt": fmt, "w": w, "h": h, "usage": "read", "count": 8, "dump": True},
         "replicate", f"finite-resource: smallest-eligible allocation footprint {fmt} {w}x{h}")

for mips, tag in ((1, "base"), (4, "chain")):
    _add(f"a_mip_{tag}", "aux", "aux_mip", "probe",
         {"fmt": "rgba8unorm", "w": 64, "h": 64, "mips": mips, "usage": "read",
          "pattern": "gradient", "dump": True},
         "descriptor", f"compression x mipmaps aux extent, mips={mips}")

# ===========================================================================
# Group STATE -- aux state <-> data pattern correlation
# ===========================================================================
_clear_colors = [
    ("black",   0.0, 0.0, 0.0, 0.0),
    ("white",   1.0, 1.0, 1.0, 1.0),
    ("midgray", 0.5, 0.5, 0.5, 1.0),
    ("arb",     0.2, 0.7, 0.4, 1.0),
]
for name, r, g, b, a in _clear_colors:
    _add(f"s_clear_{name}", "state", "state_pattern", "probe",
         {"fmt": "rgba8unorm", "w": 64, "h": 64, "usage": "read", "pattern": "clear",
          "r": r, "g": g, "b": b, "a": a, "dump": True},
         "descriptor", f"uniform clear {name}")

for pat in ("gradient", "noise", "split"):
    _add(f"s_{pat}", "state", "state_pattern", "probe",
         {"fmt": "rgba8unorm", "w": 64, "h": 64, "usage": "read", "pattern": pat, "dump": True},
         "descriptor", f"{pat} content")

_outliers = [
    ("small_delta", 4, 2, 0.5, 0.5, 0.5, 1.0, 0.55, 0.5, 0.5, 1.0),
    ("large_delta", 4, 2, 0.5, 0.5, 0.5, 1.0, 1.0, 0.0, 0.0, 1.0),
    ("corner",      0, 0, 0.5, 0.5, 0.5, 1.0, 1.0, 0.0, 0.0, 1.0),
]
for name, ox, oy, br, bg, bb, ba, orr, og, ob, oa in _outliers:
    _add(f"s_outlier_{name}", "state", "state_pattern", "probe",
         {"fmt": "rgba8unorm", "w": 64, "h": 64, "usage": "read", "pattern": "outlier",
          "ox": ox, "oy": oy, "br": br, "bg": bg, "bb": bb, "ba": ba,
          "orr": orr, "og": og, "ob": ob, "oa": oa, "dump": True},
         "descriptor", f"single-outlier block, {name}")

for fmt in ("r32uint", "rgba16float"):
    for pat, extra in (
        ("clear", {"r": 0.5, "g": 0.5, "b": 0.5, "a": 1.0}),
        ("gradient", {}),
        ("noise", {}),
    ):
        params = {"fmt": fmt, "w": 64, "h": 64, "usage": "read", "pattern": pat, "dump": True}
        params.update(extra)
        _add(f"s_fmt_{fmt}_{pat}", "state", "state_format_repeat", "probe", params,
             "descriptor", f"format-independence of state codes: {fmt}/{pat}")

# ===========================================================================
# Group CPU/PBE -- CPU-visible access + render-target interaction
# ===========================================================================
_add("c_replace_after_gradient", "cpu", "cpu_replace", "probe",
     {"fmt": "rgba8unorm", "w": 64, "h": 64, "usage": "read", "pattern": "gradient",
      "cpuop": "replace", "rx": 0, "ry": 0, "rw": 8, "rh": 8, "fill_byte": 0x11,
      "dump_after_write": True, "dump": True},
     "descriptor2", "replaceRegion on an already-compressed 8x4-block-aligned sub-region")
_add("c_replace_before_write", "cpu", "cpu_replace", "probe",
     {"fmt": "rgba8unorm", "w": 64, "h": 64, "usage": "read", "pattern": "none",
      "cpuop": "replace", "rx": 0, "ry": 0, "rw": 8, "rh": 8, "fill_byte": 0x22,
      "dump": True},
     "descriptor", "replaceRegion before any GPU write (texture never rendered)")
_add("c_replace_full", "cpu", "cpu_replace", "probe",
     {"fmt": "rgba8unorm", "w": 64, "h": 64, "usage": "read", "pattern": "gradient",
      "cpuop": "replace", "rx": 0, "ry": 0, "rw": 64, "rh": 64, "fill_byte": 0x33,
      "dump_after_write": True, "dump": True},
     "descriptor2", "replaceRegion over the FULL compressed image")

_add("c_getbytes_gradient", "cpu", "cpu_getbytes", "probe",
     {"fmt": "rgba8unorm", "w": 64, "h": 64, "usage": "read", "pattern": "gradient",
      "cpuop": "getbytes", "rw": 8, "rh": 8, "dump": True},
     "descriptor", "getBytes decode-correctness on a compressed texture")
_add("c_getbytes_noise", "cpu", "cpu_getbytes", "probe",
     {"fmt": "rgba8unorm", "w": 64, "h": 64, "usage": "read", "pattern": "noise",
      "cpuop": "getbytes", "rw": 8, "rh": 8, "dump": True},
     "descriptor", "getBytes success on incompressible-content block")

_add("c_blit_gradient_64", "cpu", "cpu_blit", "probe",
     {"fmt": "rgba8unorm", "w": 64, "h": 64, "usage": "read", "pattern": "gradient",
      "cpuop": "blit", "dump": True},
     "descriptor", "blit copy between two compression-eligible textures")
_add("c_blit_gradient_8sub", "cpu", "cpu_blit", "probe",
     {"fmt": "rgba8unorm", "w": 8, "h": 8, "usage": "read", "pattern": "gradient",
      "cpuop": "blit", "dump": True},
     "descriptor", "blit copy between two sub-threshold (never-compressed) textures")

_add("c_storeaction_dontcare", "cpu", "cpu_storeaction", "probe",
     {"fmt": "rgba8unorm", "w": 64, "h": 64, "usage": "read,rt", "pattern": "gradient",
      "store_action": "dontcare", "dump": True},
     "descriptor", "MTLStoreActionDontCare on a compression-eligible render target")
_add("c_storeaction_store", "cpu", "cpu_storeaction", "probe",
     {"fmt": "rgba8unorm", "w": 64, "h": 64, "usage": "read,rt", "pattern": "gradient",
      "store_action": "store", "dump": True},
     "descriptor", "MTLStoreActionStore control for the dontcare case above")

TOTAL = len(MATRIX)


def nondeterministic_observed_keys(case):
    """This experiment's cases are all deterministic (fixed HW, fixed pinned
    revision, fixed inputs -- descriptor bits, aux bytes, and BO layout are all
    reproducible run-to-run per EXP-0009/0017/M4-07 precedent). No case family
    here is deliberately racy (unlike EXP-0124's i_icbb_trial), so this always
    returns an empty set; kept as a function (not a constant) to match the
    established verify.py gate (d) contract and so a future racy family can be
    added without changing the gate's shape."""
    return set()
