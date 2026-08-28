#!/usr/bin/env python3
"""EXP-0102 case matrix -- pure data + host-side oracle computation. No GPU
access happens in this module; harness/case_exec.py is the only place that
shells out to tools/agxtest/agxtest.py. Every oracle value here is computed
by analysis/oracle.py from the operation's PUBLIC definition, never from a
prior GPU run.

Each case = one compiled kernel FUNCTION, one dispatch shape, one set of
input buffers (all built here, byte-exact), one set of output buffers to
read back, and one or more oracle "models" the observed values are checked
against (recorded, not force-matched -- a model can and does lose).
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oracle as O  # noqa: E402

KDIR = os.path.join(HERE, "..", "kernels")


def u32b(vals):
    return b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in vals)


def i32b(vals):
    return b"".join(struct.pack("<i", O.s32(v)) for v in vals)


def f32b(vals):
    return b"".join(struct.pack("<f", v) for v in vals)


def f32x2b(pairs):
    return b"".join(struct.pack("<ff", x, y) for x, y in pairs)


def f32x4b(quads):
    return b"".join(struct.pack("<ffff", *q) for q in quads)


def u64b(vals):
    return b"".join(struct.pack("<Q", v & 0xFFFFFFFFFFFFFFFF) for v in vals)


def half2_bits_b(pairs):
    return b"".join(struct.pack("<HH", lo & 0xFFFF, hi & 0xFFFF) for lo, hi in pairs)


def short2b(pairs):
    def s16(v):
        v &= 0xFFFF
        return v - 0x10000 if v & 0x8000 else v
    return b"".join(struct.pack("<hh", s16(x), s16(y)) for x, y in pairs)


def dec_u32(raw):
    return [struct.unpack_from("<I", raw, i)[0] for i in range(0, len(raw) - 3, 4)]


def dec_i32(raw):
    return [struct.unpack_from("<i", raw, i)[0] for i in range(0, len(raw) - 3, 4)]


def dec_f32(raw):
    return [struct.unpack_from("<f", raw, i)[0] for i in range(0, len(raw) - 3, 4)]


def dec_f32x2(raw):
    return [struct.unpack_from("<ff", raw, i) for i in range(0, len(raw) - 7, 8)]


def dec_f32x4(raw):
    return [struct.unpack_from("<ffff", raw, i) for i in range(0, len(raw) - 15, 16)]


def dec_u64(raw):
    return [struct.unpack_from("<Q", raw, i)[0] for i in range(0, len(raw) - 7, 8)]


def dec_half2_bits(raw):
    return [struct.unpack_from("<HH", raw, i) for i in range(0, len(raw) - 3, 4)]


def dec_short2(raw):
    return [struct.unpack_from("<hh", raw, i) for i in range(0, len(raw) - 3, 4)]


CASES = []


def add(**kw):
    kw.setdefault("no_fast_math", True)
    kw.setdefault("structural", False)
    kw.setdefault("tg", min(kw.get("grid", 1), 256))
    CASES.append(kw)


# =====================================================================
# INT-01 / INT-02: unsigned bitfield extract (width==0, offset/width at
# and beyond the 32-bit boundary)
# =====================================================================
_a_vals_w0 = [0xFFFFFFFF, 0x00000000, 0xDEADBEEF, 0x12345678, 0x80000000, 0x00000001]
_off_vals_w0 = [0, 5, 16, 31]
rows = []
for a in _a_vals_w0:
    for off in _off_vals_w0:
        rows.append((a, off, 0))
_off_boundary = [0, 1, 16, 28, 31, 32, 33, 40, 63, 64, 1000, 4294967295]
for off in _off_boundary:
    for cnt in (1, 8, 31, 32, 33, 40):
        rows.append((0xFFFFFFFF, off, cnt))
_cnt_boundary = [0, 1, 2, 4, 8, 16, 24, 28, 30, 31, 32, 33, 40, 63, 64, 255, 4294967295]
for cnt in _cnt_boundary:
    rows.append((0xFFFFFFFF, 0, cnt))
for off in (4, 8, 12):
    for cnt in (4, 8, 16):
        rows.append((0x12345678, off, cnt))
EXTRACT_ROWS = rows
a_arr = [r[0] for r in EXTRACT_ROWS]
off_arr = [r[1] for r in EXTRACT_ROWS]
cnt_arr = [r[2] for r in EXTRACT_ROWS]
model_a_vals = [O.ubfe_model_a(a, o, c) for a, o, c in EXTRACT_ROWS]
model_b_vals = [O.ubfe_model_b_unmasked_offset(a, o, c) for a, o, c in EXTRACT_ROWS]
model_d_vals = [O.ubfe_model_d_width32_bypasses_offset(a, o, c) for a, o, c in EXTRACT_ROWS]
add(id="int0102_extract_unsigned", items=["INT-01", "INT-02"],
    kernel="k_int_extract.metal", function="extru", grid=len(EXTRACT_ROWS),
    buffers={0: u32b(a_arr), 1: u32b(off_arr), 2: u32b(cnt_arr)},
    out={3: len(EXTRACT_ROWS)}, out_kind="u32",
    rows=EXTRACT_ROWS, oracle={"model_a_masked_shift": model_a_vals,
                                "model_b_unmasked_offset": model_b_vals,
                                "model_d_width32_bypasses_offset": model_d_vals},
    structural=True, dump_symbol="_agc.main",
    notes="width==0 rows (cnt=0) answer INT-01; the off/cnt boundary rows "
          "(>=32, >32, off+cnt>32) answer INT-02. Three competing models "
          "recorded (pilot-phase MODEL D was added after an early dry run "
          "showed cnt>=32 bypasses the offset entirely -- see PROGRESS.md); "
          "OBSERVED decides which (if any) matches on the frozen capture.")

# INT-03: signed extract, same (a,off,cnt) rows reinterpreted as int32, plus
# the sign-extension oracle derived from each unsigned model's result.
model_a_signed = [O.sbfe_from_ubfe(u, c) for u, (_, _, c) in zip(model_a_vals, EXTRACT_ROWS)]
model_d_signed = [O.sbfe_from_ubfe(u, c) for u, (_, _, c) in zip(model_d_vals, EXTRACT_ROWS)]
add(id="int03_extract_signed", items=["INT-03"],
    kernel="k_int_extract.metal", function="extrs", grid=len(EXTRACT_ROWS),
    buffers={0: i32b(a_arr), 1: u32b(off_arr), 2: u32b(cnt_arr)},
    out={3: len(EXTRACT_ROWS)}, out_kind="i32",
    rows=EXTRACT_ROWS, oracle={"model_a_extract_then_sign_extend": model_a_signed,
                                "model_d_extract_then_sign_extend": model_d_signed},
    structural=True, dump_symbol="_agc.main",
    notes="Same rows as extract_unsigned, reinterpreted signed; oracle = "
          "each competing unsigned model's extract then explicit two's-"
          "complement sign extension over the low min(cnt,32) bits (testing "
          "for a hidden signed mode vs a uniform post-hoc sign extend).")

# =====================================================================
# INT-11: bitfield insert
# =====================================================================
ins_rows = []
for base, ins in [(0x00000000, 0xFFFFFFFF), (0xFFFFFFFF, 0x00000000),
                   (0xAAAAAAAA, 0x55555555), (0x12345678, 0x9ABCDEF0)]:
    for off in (0, 4, 16, 28, 31, 32, 33, 63):
        for cnt in (0, 1, 4, 8, 16, 31, 32, 33):
            ins_rows.append((base, ins, off, cnt))
ins_oracle_a = [O.insert_bits(b, v, o, c) for b, v, o, c in ins_rows]
ins_oracle_d = [O.insert_bits_model_d(b, v, o, c) for b, v, o, c in ins_rows]
add(id="int11_insert_bits", items=["INT-11"],
    kernel="k_int_insert.metal", function="ins", grid=len(ins_rows),
    buffers={0: u32b([r[0] for r in ins_rows]), 1: u32b([r[1] for r in ins_rows]),
             2: u32b([r[2] for r in ins_rows]), 3: u32b([r[3] for r in ins_rows])},
    out={4: len(ins_rows)}, out_kind="u32",
    rows=ins_rows, oracle={"model_a_masked_shift": ins_oracle_a,
                           "model_d_width32_bypasses_offset": ins_oracle_d},
    structural=True, dump_symbol="_agc.main",
    notes="insert_bits(base,val,off,cnt) full boundary sweep incl. off/cnt "
          "at/over 32 and cnt==0 (no-op expected). MODEL D mirrors the "
          "extract_bits pilot-phase finding (cnt==32 EXACTLY bypasses "
          "offset, returning `val` verbatim; off literal/unmasked otherwise).")

# =====================================================================
# INT-04: rotate by IMMEDIATE (six kernels, one const amount each)
# =====================================================================
_rot_a = [0x12345678, 0x00000001, 0x80000000, 0xFFFFFFFF]
for K in (0, 1, 31, 32, 33, 63, 64):
    add(id=f"int04_rotate_imm{K}", items=["INT-04"],
        kernel=f"k_int_rotate_imm{K}.metal", function="k", grid=len(_rot_a),
        buffers={0: u32b(_rot_a)}, out={1: len(_rot_a)}, out_kind="u32",
        rows=[(a, K) for a in _rot_a],
        oracle={"rotl_mod32": [O.rotl32(a, K) for a in _rot_a]},
        structural=True, dump_symbol="_agc.main",
        notes=f"rotate(a, {K}u), compile-time-constant amount.")

# =====================================================================
# INT-05 / INT-06: rotate by RUNTIME amount (also gives the multi-instr
# structural contrast against INT-04's single funnel op)
# =====================================================================
_n_vals = [0, 1, 16, 31, 32, 33, 63, 64, 65, 127, 128, 255, 256, 1000, 0xFFFFFFFF, 0x80000000]
rot_var_rows = [(a, n) for a in _rot_a for n in _n_vals]
add(id="int0506_rotate_var", items=["INT-05", "INT-06"],
    kernel="k_int_rotate_var.metal", function="k", grid=len(rot_var_rows),
    buffers={0: u32b([r[0] for r in rot_var_rows]), 1: u32b([r[1] for r in rot_var_rows])},
    out={2: len(rot_var_rows)}, out_kind="u32",
    rows=rot_var_rows, oracle={"rotl_mod32": [O.rotl32(a, n) for a, n in rot_var_rows]},
    structural=True, dump_symbol="_agc.main",
    notes="Runtime rotate amount, boundary/representative sweep incl. 0,31,32,"
          "33,63,64,65,127,128,255,256,1000,0xFFFFFFFF,0x80000000. INT-06 answered "
          "by comparing this kernel's _agc.main instruction count/length to the "
          "INT-04 immediate-rotate kernels' (single 12B funnel op).")

# =====================================================================
# INT-07 / INT-08: IMAD wrap + register-pressure best-effort
# =====================================================================
imad_rows_u = [(0xFFFFFFFF, 2, 1), (0xFFFFFFFF, 0xFFFFFFFF, 1), (0x80000000, 2, 0),
               (0x7FFFFFFF, 1, 1), (0x00000000, 0xFFFFFFFF, 5), (12345, 6789, 42),
               (0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF), (1, 1, 0xFFFFFFFF)]
add(id="int0708_imad_wrap_u", items=["INT-07"],
    kernel="k_int_imad.metal", function="imadu", grid=len(imad_rows_u),
    buffers={0: u32b([r[0] for r in imad_rows_u]), 1: u32b([r[1] for r in imad_rows_u]),
             2: u32b([r[2] for r in imad_rows_u])},
    out={3: len(imad_rows_u)}, out_kind="u32",
    rows=imad_rows_u, oracle={"wrap_mod_2_32": [O.imad_u32(*r) for r in imad_rows_u]},
    notes="a*b+c, unsigned, boundary triples chosen to force 2^32 wraparound.")

imad_rows_s = [(-1, 2, 1), (2147483647, 1, 1), (-2147483648, 2, 0),
               (-1, -1, -1), (1000000, 1000000, 1), (-2147483648, -1, 0)]
add(id="int0708_imad_wrap_s", items=["INT-07"],
    kernel="k_int_imad.metal", function="imads", grid=len(imad_rows_s),
    buffers={0: i32b([r[0] for r in imad_rows_s]), 1: i32b([r[1] for r in imad_rows_s]),
             2: i32b([r[2] for r in imad_rows_s])},
    out={3: len(imad_rows_s)}, out_kind="i32",
    rows=imad_rows_s, oracle={"wrap_mod_2_32_signed": [O.imad_s32(*r) for r in imad_rows_s]},
    notes="a*b+c, signed, boundary triples incl. INT32_MIN/MAX.")

_pin = list(range(40))
_pmb, _pmc = [7], [3]
pressure_oracle = None  # computed in the harness against the SAME expression, see notes
add(id="int08_imad_register_pressure", items=["INT-08"],
    kernel="k_int_imad_pressure.metal", function="k", grid=1,
    buffers={0: u32b(_pin), 1: u32b(_pmb), 2: u32b(_pmc)},
    out={3: 1}, out_kind="u32",
    rows=[("register-pressure IMAD, 40 live temporaries feeding one mad")],
    oracle={"host_recomputed_expression": None},  # filled in below
    structural=True, dump_symbol="_agc.main",
    notes="BEST-EFFORT/PARTIAL: forces heavy register pressure ahead of the "
          "final a*b+c to see whether the compiler is pushed into "
          "higher-numbered GPRs; does NOT independently prove the full "
          "0-95 range is reachable by IMAD (that requires solving the "
          "still-open register>=64 addressing blocker noted in "
          "docs/isa/register-move-and-liveness.md, out of this "
          "experiment's scope). gid==0 fixed (grid=1).")


def _pressure_host_oracle():
    gid = 0
    ins = _pin
    ts = []
    for i in range(40):
        ts.append((ins[i] ^ (ins[i] << ((i % 13) + 1))) + gid & O.MASK32 if False else None)
    # exact operator precedence as authored: (in[i] ^ (in[i] << s)) + gid
    ts = []
    for i in range(40):
        s = (i % 13) + 1
        v = O.u32(ins[i] ^ O.u32(ins[i] << s))
        v = O.u32(v + gid)
        ts.append(v)
    acc = 0
    for t in ts:
        acc = O.u32(acc + t)
    return O.imad_u32(acc, _pmb[0], _pmc[0])


for c in CASES:
    if c["id"] == "int08_imad_register_pressure":
        c["oracle"]["host_recomputed_expression"] = [_pressure_host_oracle()]

# =====================================================================
# INT-09 / INT-10: clz (+ popcount single-op baseline for the structural
# "compound sequence" contrast)
# =====================================================================
_clz_vals = [0, 1, 2, 3, 0xFFFFFFFF, 0x80000000, 0x80000001, 0x7FFFFFFF,
             0x00008000, 0x00000100, 0x40000000, 0x55555555, 0xAAAAAAAA]
add(id="int0910_clz", items=["INT-09", "INT-10"],
    kernel="k_int_clz.metal", function="clzu", grid=len(_clz_vals),
    buffers={0: u32b(_clz_vals)}, out={1: len(_clz_vals)}, out_kind="u32",
    rows=[(v,) for v in _clz_vals], oracle={"clz32": [O.clz32(v) for v in _clz_vals]},
    structural=True, dump_symbol="_agc.main",
    notes="clz boundary sweep. find-MSB (INT-09) is DERIVED as 31-clz(x) for "
          "x!=0 under the EXP-0033 byte-level decomposition (find-MSB then "
          "31-minus then clamp), cross-checked here on M4 by re-confirming "
          "the byte pattern; INT-10 (compound vs single-instr) answered by "
          "comparing this kernel's instruction length to popc's (single 8B op).")
add(id="int0910_popcount_baseline", items=["INT-10"],
    kernel="k_int_clz.metal", function="popc", grid=len(_clz_vals),
    buffers={0: u32b(_clz_vals)}, out={1: len(_clz_vals)}, out_kind="u32",
    rows=[(v,) for v in _clz_vals], oracle={"popcount32": [O.popcount32(v) for v in _clz_vals]},
    structural=True, dump_symbol="_agc.main",
    notes="Single-op reference (byte0 0x27/0xa7 family, EXP-0033) for the "
          "clz instruction-count/length comparison.")

# =====================================================================
# INT-12: 16 two-input Boolean logic functions
# =====================================================================
_lut_ab = [(0xFFFFFFFF, 0x00000000), (0xAAAAAAAA, 0x55555555),
           (0x12345678, 0x0F0F0F0F), (0x00000000, 0x00000000),
           (0xFFFFFFFF, 0xFFFFFFFF)]
for idx in range(16):
    add(id=f"int12_logic{idx:02d}", items=["INT-12"],
        kernel="k_int_logic16.metal", function=f"k{idx}", grid=len(_lut_ab),
        buffers={0: u32b([p[0] for p in _lut_ab]), 1: u32b([p[1] for p in _lut_ab])},
        out={2: len(_lut_ab)}, out_kind="u32",
        rows=_lut_ab, oracle={"logic_lut": [O.logic_lut(idx, a, b) for a, b in _lut_ab]},
        structural=True, dump_symbol="_agc.main",
        notes=f"LUT function #{idx}: {O.LOGIC_EXPR[idx]}")

# =====================================================================
# INT-13 / INT-14: u64 carry-generate structural context sweep
# =====================================================================
u64_rows = [(0xFFFFFFFF, 1), (0xFFFFFFFFFFFFFFFF, 1), (0x123456789ABCDEF0, 0x1111111111111111),
            (0, 0), (0xFFFFFFFF00000000, 0xFFFFFFFF), (1, 0xFFFFFFFFFFFFFFFF)]
add(id="int1314_u64add", items=["INT-13", "INT-14"],
    kernel="k_int_u64carry.metal", function="u64add", grid=len(u64_rows),
    buffers={0: u64b([r[0] for r in u64_rows]), 1: u64b([r[1] for r in u64_rows])},
    out={2: len(u64_rows)}, out_kind="u64",
    rows=u64_rows, oracle={"wrap_mod_2_64": [O.u32(a + b) | 0 if False else
                                              ((a + b) & 0xFFFFFFFFFFFFFFFF) for a, b in u64_rows]},
    structural=True, dump_symbol="_agc.main",
    notes="PARTIAL for INT-14 (self-contained explicit-operand emission is "
          "NOT independently probed by splice in this experiment -- see "
          "PRE_REGISTRATION.md scoping). INT-13 answered structurally: in "
          "EVERY compiled instance the carry-gen 0x32 op immediately follows "
          "the specific low-word add whose overflow it tests (re-confirmed "
          "on M4 by byte inspection); a second kernel shape below tests "
          "whether that adjacency survives when the add is embedded in a "
          "larger expression.")
u64_rows2 = [(0xFFFFFFFF, 1, 0), (1, 1, 0xFFFFFFFFFFFFFFFE), (100, 200, 300)]
add(id="int13_u64add_expr", items=["INT-13"],
    kernel="k_int_u64carry.metal", function="u64add_expr", grid=len(u64_rows2),
    buffers={0: u64b([r[0] for r in u64_rows2]), 1: u64b([r[1] for r in u64_rows2]),
             2: u64b([r[2] for r in u64_rows2])},
    out={3: len(u64_rows2)}, out_kind="u64",
    rows=u64_rows2,
    oracle={"wrap_mod_2_64": [((a + b + c) & 0xFFFFFFFFFFFFFFFF) for a, b, c in u64_rows2]},
    structural=True, dump_symbol="_agc.main",
    notes="(a+b)+c shape -- second, independent compiled context for the "
          "INT-13 adjacency claim.")

# =====================================================================
# PACK-01 / PACK-02: pack_half_2x16 / unpack_half_2x16 equivalents
# =====================================================================
_ph_pairs = [(0.0, 1.0), (1.5, 2.25), (-3.5, 7.0), (65504.0, -65504.0),
             (0.000030517578125, -0.000030517578125),  # smallest normal fp16
             (0.0, -0.0), (100000.0, -100000.0)]  # overflow -> +-inf
add(id="pack0102_pack_half2x16", items=["PACK-01"],
    kernel="k_pack_half2x16.metal", function="packh", grid=len(_ph_pairs),
    buffers={0: f32x2b(_ph_pairs)}, out={1: len(_ph_pairs)}, out_kind="u32",
    rows=_ph_pairs, oracle={"f32_to_f16_bits_pack": [O.pack_half_2x16(x, y) for x, y in _ph_pairs]},
    structural=True, dump_symbol="_agc.main",
    notes="float2->half2->as_type<uint>. Byte-diffed vs the generic "
          "insert_bits signature to test 'without generic integer bitfield "
          "lowering'.")
_uh_words = [O.pack_half_2x16(x, y) for x, y in _ph_pairs] + [0x7E000000, 0x00007E00, 0xFC00FC00]
add(id="pack0102_unpack_half2x16", items=["PACK-02"],
    kernel="k_pack_half2x16.metal", function="unpackh", grid=len(_uh_words),
    buffers={0: u32b(_uh_words)}, out={1: len(_uh_words)}, out_kind="f32x2",
    rows=[(w,) for w in _uh_words],
    oracle={"f16_bits_to_f32_unpack": [O.unpack_half_2x16(w) for w in _uh_words]},
    structural=True, dump_symbol="_agc.main",
    notes="uint->as_type<half2>->float2, incl. NaN(0x7E00)/Inf(0x7C00) lanes.")

# =====================================================================
# PACK-03 / PACK-04: snorm 2x16
# =====================================================================
_sn_pairs = [(0.0, 0.0), (1.0, -1.0), (0.5, -0.5), (0.333, -0.333), (2.0, -2.0),
             (0.99998, -0.99998), (0.0000152, -0.0000152)]
add(id="pack0304_pack_snorm2x16", items=["PACK-03"],
    kernel="k_pack_snorm2x16.metal", function="packsn", grid=len(_sn_pairs),
    buffers={0: f32x2b(_sn_pairs)}, out={1: len(_sn_pairs)}, out_kind="u32",
    rows=_sn_pairs, oracle={"pack_snorm2x16_model": [O.pack_snorm2x16(x, y) for x, y in _sn_pairs]},
    structural=True, dump_symbol="_agc.main",
    notes="Functional sweep + byte-diffed vs packun (EXP-0033's confirmed "
          "single 0x97 pack family) to test native-family membership.")
add(id="pack0304_unpack_snorm2x16_exhaustive", items=["PACK-04"],
    kernel="k_pack_unpack_exhaustive.metal", function="unpacksn_exh", grid=65536,
    buffers={}, out={0: 65536}, out_kind="f32", exhaustive_lane=True,
    rows=None,
    oracle={"unpack_snorm16_model": None},  # filled below (65536 values, computed lazily)
    structural=True, dump_symbol="_agc.main", tg=256,
    notes="EXHAUSTIVE over all 65536 16-bit lane bit patterns, one dispatch.")

# =====================================================================
# PACK-05 / PACK-06: unorm 2x16
# =====================================================================
def _tie_x(n, scale):
    return (n + 0.5) / scale


_un_pairs = [(0.0, 1.0), (-1.0, 2.0), (0.5, 0.5), (float("nan"), 0.5),
             (0.5, float("nan")), (float("inf"), float("-inf")),
             (0.0000152, 0.0000152),
             (_tie_x(0, 65535), _tie_x(1, 65535)),
             (_tie_x(32767, 65535), _tie_x(65534, 65535)),
             (_tie_x(2, 65535), _tie_x(65533, 65535))]
add(id="pack0506_pack_unorm2x16_edge", items=["PACK-05"],
    kernel="k_pack_unorm2x16.metal", function="packun", grid=len(_un_pairs),
    buffers={0: f32x2b(_un_pairs)}, out={1: len(_un_pairs)}, out_kind="u32",
    rows=_un_pairs,
    oracle={"round_clamp_65535_rte": [O.pack_unorm2x16(x, y) for x, y in _un_pairs]},
    structural=True, dump_symbol="_agc.main",
    notes="Boundary/exceptional float2 inputs: negative, >1, NaN, +-Inf, "
          "subnormal-magnitude, and three exact .5-tie fractions (x*65535 == "
          "N+0.5) to probe hardware tie-rounding direction.")
add(id="pack0506_unpack_unorm2x16_exhaustive", items=["PACK-06"],
    kernel="k_pack_unpack_exhaustive.metal", function="unpackun_exh", grid=65536,
    buffers={}, out={0: 65536}, out_kind="f32", exhaustive_lane=True,
    rows=None,
    oracle={"unpack_unorm16_model": None},
    structural=True, dump_symbol="_agc.main", tg=256,
    notes="EXHAUSTIVE over all 65536 16-bit lane bit patterns, one dispatch.")

# =====================================================================
# PACK-07 / PACK-08: 4x8 pack/unpack (unorm, snorm, + generic manual idiom)
# =====================================================================
_p4_quads = [(0.0, 0.0, 0.0, 0.0), (1.0, 1.0, 1.0, 1.0), (0.5, 0.25, 0.75, 1.0),
             (-1.0, -0.5, 0.5, 1.0), (2.0, -2.0, 0.999, 0.001)]
add(id="pack0708_pack_unorm4x8", items=["PACK-07"],
    kernel="k_pack_4x8_unorm.metal", function="packu4x8", grid=len(_p4_quads),
    buffers={0: f32x4b(_p4_quads)}, out={1: len(_p4_quads)}, out_kind="u32",
    rows=_p4_quads, oracle={"pack_unorm4x8_model": [O.pack_unorm4x8(q) for q in _p4_quads]},
    structural=True, dump_symbol="_agc.main",
    notes="MSL pack_float_to_unorm4x8 -- confirmed to COMPILE (see PROGRESS.md "
          "compile smoke); this case establishes functional correctness + "
          "single-op family membership by byte length.")
add(id="pack0708_pack_snorm4x8", items=["PACK-07"],
    kernel="k_pack_4x8_snorm.metal", function="packs4x8", grid=len(_p4_quads),
    buffers={0: f32x4b(_p4_quads)}, out={1: len(_p4_quads)}, out_kind="u32",
    rows=_p4_quads, oracle={"pack_snorm4x8_model": [O.pack_snorm4x8(q) for q in _p4_quads]},
    structural=True, dump_symbol="_agc.main", notes="MSL pack_float_to_snorm4x8.")
_manual_rows = [(0x12, 0x34, 0x56, 0x78), (0xFF, 0x00, 0xFF, 0x00), (1, 2, 3, 4)]
add(id="pack07_pack4x8_manual_generic", items=["PACK-07"],
    kernel="k_pack_4x8_manual.metal", function="packu4x8_manual", grid=len(_manual_rows),
    buffers={0: u32b([r[0] for r in _manual_rows]), 1: u32b([r[1] for r in _manual_rows]),
             2: u32b([r[2] for r in _manual_rows]), 3: u32b([r[3] for r in _manual_rows])},
    out={4: len(_manual_rows)}, out_kind="u32",
    rows=_manual_rows,
    oracle={"manual_or_shift_model": [
        (a & 0xFF) | ((b & 0xFF) << 8) | ((c & 0xFF) << 16) | ((d & 0xFF) << 24)
        for a, b, c, d in _manual_rows]},
    structural=True, dump_symbol="_agc.main",
    notes="Hand-written generic (non-normalized) 4x8 integer pack idiom -- "
          "probes whether a GENERIC pack has native support beyond the "
          "float-normalized builtins, via byte-diff against packu4x8/insert_bits.")
_u4_words = [O.pack_unorm4x8(q) for q in _p4_quads] + [0x00000000, 0xFFFFFFFF, 0x80402010]
add(id="pack0708_unpack_unorm4x8", items=["PACK-08"],
    kernel="k_pack_4x8_unorm.metal", function="unpacku4x8", grid=len(_u4_words),
    buffers={0: u32b(_u4_words)}, out={1: len(_u4_words)}, out_kind="f32x4",
    rows=[(w,) for w in _u4_words],
    oracle={"unpack_unorm4x8_model": [O.unpack_unorm4x8(w) for w in _u4_words]},
    structural=True, dump_symbol="_agc.main", notes="MSL unpack_unorm4x8_to_float.")
_s4_words = [O.pack_snorm4x8(q) for q in _p4_quads] + [0x00000000, 0xFFFFFFFF, 0x80402010]
add(id="pack0708_unpack_snorm4x8", items=["PACK-08"],
    kernel="k_pack_4x8_snorm.metal", function="unpacks4x8", grid=len(_s4_words),
    buffers={0: u32b(_s4_words)}, out={1: len(_s4_words)}, out_kind="f32x4",
    rows=[(w,) for w in _s4_words],
    oracle={"unpack_snorm4x8_model": [O.unpack_snorm4x8(w) for w in _s4_words]},
    structural=True, dump_symbol="_agc.main", notes="MSL unpack_snorm4x8_to_float.")

# =====================================================================
# PACK-09 / PACK-10: half2 exceptional-value lane-independence matrix
# =====================================================================
F16 = {
    "zero_p": 0x0000, "zero_n": 0x8000, "one": O.f32_to_f16_bits(1.0),
    "two": O.f32_to_f16_bits(2.0), "half": O.f32_to_f16_bits(0.5),
    "nan_q": 0x7E00, "nan_alt": 0x7E55, "inf_p": 0x7C00, "inf_n": 0xFC00,
    "sub_min": 0x0001, "sub_mid": 0x0200, "neg_one": O.f32_to_f16_bits(-1.0),
}
_h2_pairs_a = [(F16["nan_q"], F16["one"]), (F16["one"], F16["nan_q"]),
               (F16["zero_p"], F16["zero_n"]), (F16["inf_p"], F16["sub_mid"]),
               (F16["sub_min"], F16["inf_n"]), (F16["two"], F16["half"]),
               (F16["inf_p"], F16["inf_n"]), (F16["neg_one"], F16["nan_alt"])]
_h2_pairs_b = [(F16["one"], F16["two"]), (F16["two"], F16["one"]),
               (F16["zero_p"], F16["one"]), (F16["one"], F16["sub_mid"]),
               (F16["sub_min"], F16["half"]), (F16["half"], F16["two"]),
               (F16["one"], F16["neg_one"]), (F16["zero_n"], F16["one"]) ]
add(id="pack0910_half2_add", items=["PACK-09", "PACK-10"],
    kernel="k_pack_half2_alu.metal", function="h2add", grid=len(_h2_pairs_a),
    buffers={0: half2_bits_b(_h2_pairs_a), 1: half2_bits_b(_h2_pairs_b)},
    out={2: len(_h2_pairs_a)}, out_kind="half2_bits",
    rows=list(zip(_h2_pairs_a, _h2_pairs_b)),
    oracle={"f16_add_per_lane_independent": [
        (O.f16_op([la[0], lb[0]], "add2"), O.f16_op([la[1], lb[1]], "add2"))
        for la, lb in zip(_h2_pairs_a, _h2_pairs_b)]},
    notes="Per-lane exceptional pairs incl. NaN, +-0, Inf, subnormal in one "
          "lane crossed against a normal value in the other.")
add(id="pack0910_half2_mul", items=["PACK-09", "PACK-10"],
    kernel="k_pack_half2_alu.metal", function="h2mul", grid=len(_h2_pairs_a),
    buffers={0: half2_bits_b(_h2_pairs_a), 1: half2_bits_b(_h2_pairs_b)},
    out={2: len(_h2_pairs_a)}, out_kind="half2_bits",
    rows=list(zip(_h2_pairs_a, _h2_pairs_b)),
    oracle={"f16_mul_per_lane_independent": [
        (O.f16_op([la[0], lb[0]], "mul2"), O.f16_op([la[1], lb[1]], "mul2"))
        for la, lb in zip(_h2_pairs_a, _h2_pairs_b)]},
    notes="Same matrix, multiply.")
_h2_pairs_c = [(F16["zero_p"], F16["one"]), (F16["zero_n"], F16["one"]),
               (F16["one"], F16["zero_p"]), (F16["half"], F16["one"]),
               (F16["sub_mid"], F16["one"]), (F16["one"], F16["half"]),
               (F16["neg_one"], F16["one"]), (F16["one"], F16["one"])]
add(id="pack0910_half2_fma", items=["PACK-09", "PACK-10"],
    kernel="k_pack_half2_alu.metal", function="h2fma", grid=len(_h2_pairs_a),
    buffers={0: half2_bits_b(_h2_pairs_a), 1: half2_bits_b(_h2_pairs_b),
             2: half2_bits_b(_h2_pairs_c)},
    out={3: len(_h2_pairs_a)}, out_kind="half2_bits",
    rows=list(zip(_h2_pairs_a, _h2_pairs_b, _h2_pairs_c)),
    oracle={"f16_fma_per_lane_independent": [
        (O.f16_op([la[0], lb[0], lc[0]], "fma3"), O.f16_op([la[1], lb[1], lc[1]], "fma3"))
        for la, lb, lc in zip(_h2_pairs_a, _h2_pairs_b, _h2_pairs_c)]},
    notes="fma(a,b,c) packed half2, same exceptional matrix, third operand "
          "added per lane.")

# =====================================================================
# PACK-11: short2 packed-int negative claim (add/mul/and)
# =====================================================================
_s2_a = [(1, -1), (32767, -32768), (100, 200), (0, 0), (-1, 1)]
_s2_b = [(2, 2), (1, 1), (300, 300), (5, -5), (1, -1)]
for opname, fn in (("add", "s2add"), ("mul", "s2mul"), ("and", "s2and")):
    if opname == "add":
        oracle_pairs = [((x0 + x1 + 0x8000) % 0x10000 - 0x8000, (y0 + y1 + 0x8000) % 0x10000 - 0x8000)
                        for (x0, y0), (x1, y1) in zip(_s2_a, _s2_b)]
    elif opname == "mul":
        oracle_pairs = [((x0 * x1 + 0x8000) % 0x10000 - 0x8000, (y0 * y1 + 0x8000) % 0x10000 - 0x8000)
                         for (x0, y0), (x1, y1) in zip(_s2_a, _s2_b)]
    else:
        oracle_pairs = [((x0 & x1), (y0 & y1)) for (x0, y0), (x1, y1) in zip(_s2_a, _s2_b)]
    add(id=f"pack11_short2_{opname}", items=["PACK-11"],
        kernel="k_pack_short2.metal", function=fn, grid=len(_s2_a),
        buffers={0: short2b(_s2_a), 1: short2b(_s2_b)},
        out={2: len(_s2_a)}, out_kind="short2",
        rows=list(zip(_s2_a, _s2_b)), oracle={"scalar16_wrap_model": oracle_pairs},
        structural=True, dump_symbol="_agc.main",
        notes=f"short2 {opname}: functional correctness + byte-diff to confirm "
              f"decomposition into two independent 32-bit ops (EXP-0033 found "
              f"this for add; this case re-checks {opname} on M4).")


def _exhaustive_lane_oracle(kind):
    if kind == "snorm":
        return [O.unpack_snorm16(g) for g in range(65536)]
    if kind == "unorm":
        return [O.unpack_unorm16(g) for g in range(65536)]
    raise ValueError(kind)


for c in CASES:
    if c["id"] == "pack0304_unpack_snorm2x16_exhaustive":
        c["oracle"]["unpack_snorm16_model"] = _exhaustive_lane_oracle("snorm")
    if c["id"] == "pack0506_unpack_unorm2x16_exhaustive":
        c["oracle"]["unpack_unorm16_model"] = _exhaustive_lane_oracle("unorm")


def build_cases():
    return CASES


DECODERS = {
    "u32": dec_u32, "i32": dec_i32, "f32": dec_f32, "f32x2": dec_f32x2,
    "f32x4": dec_f32x4, "u64": dec_u64, "half2_bits": dec_half2_bits,
    "short2": dec_short2,
}

if __name__ == "__main__":
    cs = build_cases()
    print(f"{len(cs)} cases")
    ids = [c["id"] for c in cs]
    dups = set(x for x in ids if ids.count(x) > 1)
    assert not dups, f"duplicate case ids: {dups}"
    for c in cs:
        for k, v in c["oracle"].items():
            assert v is not None, f"{c['id']}: oracle {k} not filled in"
    print("OK: no duplicate ids, all oracles filled")
