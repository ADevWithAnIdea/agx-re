#!/usr/bin/env python3
"""EXP-0121 case matrix. Deterministic (seeded) case generation -- run01 and run02
build byte-identical corpora from this same frozen module, so cross-run gating on
functional-case inputs/outputs is meaningful. Pure Python, no GPU access here.
"""
import random
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import oracle as O  # noqa: E402

SEED = 0x0E1210121  # frozen at pre-registration


def f32(x):
    return O.f32_bits(x)


def pack_f32_list(vals):
    return b"".join(struct.pack('<f', v) for v in vals)


def pack_bits_list(bits_list):
    return b"".join(struct.pack('<I', b & 0xFFFFFFFF) for b in bits_list)


def pack_i32_list(vals):
    return b"".join(struct.pack('<i', v) for v in vals)


def pack_u32_list(vals):
    return b"".join(struct.pack('<I', v & 0xFFFFFFFF) for v in vals)


# =============================================================================
# OPT-01: division corpus (bit patterns for a, b)
# =============================================================================

def _div_corpus_bits():
    MINSUB = 0x00000001
    MAXSUB = 0x007FFFFF
    MINNORM = 0x00800000
    MAXNORM = 0x7F7FFFFF
    ONE = 0x3F800000
    TWO = 0x40000000
    THREE = 0x40400000
    HALF = 0x3F000000
    PZERO, NZERO = 0x00000000, 0x80000000
    PINF, NINF = 0x7F800000, 0xFF800000
    QNAN1, QNAN2, NQNAN = 0x7FC12345, 0x7FC54321, 0xFFC12345

    directed = [
        (MINSUB, ONE), (MAXSUB, ONE), (MINSUB, MINSUB), (MAXSUB, MINSUB),
        (MINSUB, 0x00000003), (0x00000002, 0x00000003), (0x00000003, 0x00000002),
        (0x80000001, MINSUB), (0x00000002, THREE), (0x00000003, TWO),
        (0x00000007, TWO), (MINNORM, TWO), (MAXSUB, TWO), (MINSUB, HALF),
        (PZERO, PZERO), (PZERO, NZERO), (NZERO, PZERO), (NZERO, NZERO),
        (ONE, PZERO), (ONE, NZERO), (MINSUB, PZERO),
        (PINF, PINF), (PINF, NINF), (NINF, NINF),
        (ONE, PINF), (ONE, NINF), (PINF, ONE), (NINF, ONE),
        (MAXNORM, 0x3F7FFFFF),  # near-1 divisor, overflow tie region
        (0x7F7FFFFE, HALF),     # overflow: maxfloat-ish / 0.5
        (MINNORM, 0x40800000),  # min normal / 4 -> subnormal result
        (QNAN1, ONE), (ONE, QNAN2), (NQNAN, THREE), (QNAN1, QNAN2),
        (PZERO, MINSUB), (NZERO, MINSUB),
        (MAXNORM, MINSUB),  # huge / tiny -> overflow to inf
        (MINSUB, MAXNORM),  # tiny / huge -> underflow to 0
    ]
    rnd = random.Random(SEED)
    random_normal = []
    for _ in range(180):
        a = rnd.getrandbits(32) & 0x7F7FFFFF | (rnd.getrandbits(1) << 31)
        b = rnd.getrandbits(32) & 0x7F7FFFFF | (rnd.getrandbits(1) << 31)
        if O.is_nan_bits(a) or O.is_nan_bits(b):
            continue
        random_normal.append((a, b))
    random_subnormal_heavy = []
    for _ in range(120):
        # force subnormal-ish exponents on one or both operands sometimes
        def mk():
            choice = rnd.random()
            if choice < 0.35:
                e = 0  # subnormal
            elif choice < 0.55:
                e = 1  # smallest normal exponents
            else:
                e = rnd.randint(1, 253)
            m = rnd.getrandbits(23)
            s = rnd.getrandbits(1)
            return (s << 31) | (e << 23) | m
        a, b = mk(), mk()
        if b == 0 or b == 0x80000000:
            continue
        random_subnormal_heavy.append((a, b))
    return directed + random_normal + random_subnormal_heavy


DIV_CORPUS = _div_corpus_bits()


# =============================================================================
# OPT-03: pow edge-case corpus, (x, y, python-float-pairs)
# =============================================================================

POW_CORPUS = [
    (0.0, 0.0), (0.0, 1.0), (0.0, -1.0), (0.0, 2.0), (0.0, 3.0),
    (-0.0, 3.0), (-0.0, 2.0), (-0.0, -1.0), (-0.0, 0.0),
    (-1.0, 2.0), (-1.0, 3.0), (-1.0, -2.0), (-1.0, 0.5),
    (-8.0, 1.0 / 3.0), (-2.0, 3.0), (-2.0, 2.0), (-4.0, 0.5),
    (2.0, 0.0), (float('nan'), 0.0), (float('inf'), 0.0), (float('-inf'), 0.0),
    (1.0, float('nan')), (1.0, float('inf')), (1.0, -5.0), (1.0, 0.0),
    (4.0, 0.5), (2.0, 10.0), (2.0, -10.0), (2.0, 30.0), (10.0, 38.0),
    (0.5, -200.0), (2.0, 1e6), (2.0, -1e6), (float('inf'), 2.0), (float('inf'), -2.0),
    (float('-inf'), 3.0), (float('-inf'), 2.0), (float('-inf'), -3.0), (float('-inf'), -2.0),
    (0.5, float('inf')), (0.5, float('-inf')), (2.0, float('inf')), (2.0, float('-inf')),
    (3.0, 3.0), (3.0, -3.0), (5.5, 2.0), (5.5, -2.0), (0.1, 0.1),
    (100.0, 100.0), (1e-10, 1e10), (float('nan'), float('nan')), (float('nan'), 1.0),
    (2.0, float('nan')),
]


# =============================================================================
# OPT-04: ldexp corpus, (x_bits, n)
# =============================================================================

def _ldexp_corpus():
    xs_bits = [
        f32(1.0), f32(1.5), f32(-1.0), f32(3.0), f32(-3.0),
        0x00000001,  # min subnormal
        0x007FFFFF,  # max subnormal
        0x00800000,  # min normal
        0x7F7FFFFF,  # max normal
        0x00000000, 0x80000000,  # +-0
        0x7F800000, 0xFF800000,  # +-inf
        0x7FC12345,  # NaN
    ]
    ns = [0, 1, -1, 2, -2, 8, -8, 30, -30, 126, 127, 128, -126, -127, -128,
          -149, -150, -160, -300, 300, 1000, -1000, 2147483647, -2147483648,
          254, -254, 24, -24]
    directed = [(x, n) for x in xs_bits for n in ns]
    rnd = random.Random(SEED ^ 0xABCD)
    randoms = []
    for _ in range(60):
        e = rnd.randint(0, 255)
        m = rnd.getrandbits(23)
        s = rnd.getrandbits(1)
        xb = (s << 31) | (e << 23) | m
        n = rnd.randint(-400, 400)
        randoms.append((xb, n))
    return directed + randoms


LDEXP_CORPUS = _ldexp_corpus()
LDEXP_CONST_CORPUS = [f32(1.0), f32(-2.5), f32(100.0), f32(0.001), 0x00000001]


# =============================================================================
# OPT-05/06: compare+select corpus per type
# =============================================================================

def _select_f32_corpus():
    base_pairs = [
        (1.0, 1.0), (1.0, 2.0), (2.0, 1.0), (-1.0, 1.0), (-5.0, -5.0),
        (0.0, -0.0), (-0.0, 0.0), (0.0, 0.0),
        (float('inf'), 1.0), (1.0, float('inf')), (float('-inf'), float('inf')),
        (float('nan'), 1.0), (1.0, float('nan')), (float('nan'), float('nan')),
        (1e30, 1e30), (1e-30, 1e30), (-1e30, 1e30),
    ]
    rnd = random.Random(SEED ^ 0x51EC)
    for _ in range(40):
        base_pairs.append((rnd.uniform(-1e6, 1e6), rnd.uniform(-1e6, 1e6)))
    # A, B sentinels: far apart, never 0/1, distinguishable from booleans
    A, B = 123456.75, -987654.25
    return [(A, B, ca, cb) for ca, cb in base_pairs]


def _select_i32_corpus():
    INT_MIN, INT_MAX = -2147483648, 2147483647
    base_pairs = [
        (0, 0), (1, -1), (-1, 1), (INT_MIN, INT_MAX), (INT_MAX, INT_MIN),
        (INT_MIN, INT_MIN), (INT_MAX, INT_MAX), (-1, 0), (0, -1),
        (-1, -1), (5, 5), (-5, 5), (5, -5),
        # bit pattern 0xFFFFFFFF as signed -1: classic signed vs unsigned divergence case
        (-1, 2147483647), (-2147483648, -1),
    ]
    rnd = random.Random(SEED ^ 0x1132)
    for _ in range(40):
        base_pairs.append((rnd.randint(INT_MIN, INT_MAX), rnd.randint(INT_MIN, INT_MAX)))
    A, B = 111111, -222222
    return [(A, B, ca, cb) for ca, cb in base_pairs]


def _select_u32_corpus():
    UMAX = 4294967295
    base_pairs = [
        (0, 0), (1, 0), (0, 1), (UMAX, 0), (0, UMAX), (UMAX, UMAX),
        (UMAX, UMAX - 1), (2147483648, 2147483647),  # 0x80000000 vs 0x7FFFFFFF
        (4294967295, 2147483648),  # 0xFFFFFFFF vs 0x80000000: unsigned gt, but as signed: -1 vs INT_MIN, still gt
        (5, 5), (10, 20), (20, 10),
    ]
    rnd = random.Random(SEED ^ 0x9A21)
    for _ in range(40):
        base_pairs.append((rnd.randint(0, UMAX), rnd.randint(0, UMAX)))
    A, B = 3000000000, 555555
    return [(A, B, ca, cb) for ca, cb in base_pairs]


SELECT_F32_CORPUS = _select_f32_corpus()
SELECT_I32_CORPUS = _select_i32_corpus()
SELECT_U32_CORPUS = _select_u32_corpus()

SELECT_CONDS = ['eq', 'ne', 'lt', 'le', 'gt', 'ge']


# =============================================================================
# OPT-10/11 concurrency matrix
# =============================================================================

CONC_FUNCS = ["msg_AA_fenced", "msg_AA_unfenced", "msg_PA_fenced", "msg_PA_unfenced",
              "msg_AP_fenced", "msg_AP_unfenced", "msg_PP_fenced", "msg_PP_unfenced"]
CONC_PAIRS = [1, 4, 8, 16]
CONC_ITERATIONS = 300
CONC_SPINBOUND = 300000
CONC_REPEATS = 2


def build_cases():
    """Returns the frozen, ordered list of ALL cases for this experiment. Deterministic."""
    cases = []

    # ---- OPT-01 ----
    div_a = pack_bits_list([p[0] for p in DIV_CORPUS])
    div_b = pack_bits_list([p[1] for p in DIV_CORPUS])
    for cfg in [
        {"id": "opt01_plain_relaxed", "kernel": "opt01_div.metal", "fn": "k_div_plain", "fastmath": True},
        {"id": "opt01_plain_precise", "kernel": "opt01_div.metal", "fn": "k_div_plain", "fastmath": False},
        {"id": "opt01_fastns_precise", "kernel": "opt01_div.metal", "fn": "k_div_fast_ns", "fastmath": False},
        {"id": "opt01_precisens_precise", "kernel": "opt01_div.metal", "fn": "k_div_precise_ns", "fastmath": False},
    ]:
        cases.append({
            "id": cfg["id"], "item": "OPT-01", "kind": "compute",
            "kernel": cfg["kernel"], "function": cfg["fn"], "fastmath": cfg["fastmath"],
            "grid": len(DIV_CORPUS), "tg": 32,
            "buffers": {0: div_a, 1: div_b}, "out": {2: len(DIV_CORPUS)},
            "out_type": "f32", "dump_main": True,
            "n": len(DIV_CORPUS),
        })

    # ---- OPT-03 ----
    pow_x = pack_f32_list([p[0] for p in POW_CORPUS])
    pow_y = pack_f32_list([p[1] for p in POW_CORPUS])
    for fn, cid in [("k_pow_builtin", "opt03_pow_builtin"), ("k_pow_manual", "opt03_pow_manual")]:
        cases.append({
            "id": cid, "item": "OPT-03", "kind": "compute",
            "kernel": "opt03_pow.metal", "function": fn, "fastmath": False,
            "grid": len(POW_CORPUS), "tg": 16,
            "buffers": {0: pow_x, 1: pow_y}, "out": {2: len(POW_CORPUS)},
            "out_type": "f32", "dump_main": True,
            "n": len(POW_CORPUS),
        })

    # ---- OPT-04 ----
    ldexp_x = pack_bits_list([p[0] for p in LDEXP_CORPUS])
    ldexp_n = pack_i32_list([p[1] for p in LDEXP_CORPUS])
    cases.append({
        "id": "opt04_ldexp_dynamic", "item": "OPT-04", "kind": "compute",
        "kernel": "opt04_ldexp.metal", "function": "k_ldexp_dynamic", "fastmath": False,
        "grid": len(LDEXP_CORPUS), "tg": 32,
        "buffers": {0: ldexp_x, 1: ldexp_n}, "out": {2: len(LDEXP_CORPUS)},
        "out_type": "f32", "dump_main": True,
        "n": len(LDEXP_CORPUS),
    })
    cases.append({
        "id": "opt04_ldexp_const3", "item": "OPT-04", "kind": "compute",
        "kernel": "opt04_ldexp.metal", "function": "k_ldexp_const3", "fastmath": False,
        "grid": len(LDEXP_CONST_CORPUS), "tg": 8,
        "buffers": {0: pack_f32_list([O.bits_f32(b) for b in LDEXP_CONST_CORPUS])},
        "out": {1: len(LDEXP_CONST_CORPUS)},
        "out_type": "f32", "dump_main": True,
        "n": len(LDEXP_CONST_CORPUS),
    })

    # ---- OPT-05/06 ----
    def sel_case(typ, cond, corpus, pack_val, pack_cmp):
        A = corpus[0][0]
        B = corpus[0][1]
        cas = [(row[2], row[3]) for row in corpus]
        return {
            "id": f"opt0506_sel_{typ}_{cond}", "item": "OPT-05/06", "kind": "compute",
            "kernel": "opt0506_select.metal", "function": f"k_sel_{typ}_{cond}", "fastmath": False,
            "grid": len(cas), "tg": 16,
            "buffers": {
                0: pack_val([A] * len(cas)), 1: pack_val([B] * len(cas)),
                2: pack_cmp([c[0] for c in cas]), 3: pack_cmp([c[1] for c in cas]),
            },
            "out": {4: len(cas)}, "out_type": typ, "dump_main": True,
            "n": len(cas), "sel_A": A, "sel_B": B, "sel_cond": cond, "sel_type": typ,
            "sel_pairs": cas,
        }
    for cond in SELECT_CONDS:
        cases.append(sel_case("f32", cond, SELECT_F32_CORPUS, pack_f32_list, pack_f32_list))
        cases.append(sel_case("i32", cond, SELECT_I32_CORPUS, pack_i32_list, pack_i32_list))
        cases.append(sel_case("u32", cond, SELECT_U32_CORPUS, pack_u32_list, pack_u32_list))

    # ---- OPT-07/08 (render) ----
    cases.append({
        "id": "opt07_dynin_8way", "item": "OPT-07", "kind": "render",
        "kernel": "opt07_varying_in.metal", "vertex": "v_main", "fragment": "f_main",
        "width": 8, "height": 1, "n": 8,
    })
    cases.append({
        "id": "opt07_staticidx_8", "item": "OPT-07", "kind": "render",
        "kernel": "opt07_varying_in.metal", "vertex": "v_main", "fragment": "f_main_static",
        "width": 8, "height": 1, "n": 8,
    })
    cases.append({
        "id": "opt08_dynout_2way", "item": "OPT-08", "kind": "render",
        "kernel": "opt08_varying_out.metal", "vertex": "v_main", "fragment": "f_main2",
        "width": 4, "height": 1, "n": 4, "rt_count": 2,
    })
    cases.append({
        "id": "opt08_dynout_3way", "item": "OPT-08", "kind": "render",
        "kernel": "opt08_varying_out.metal", "vertex": "v_main", "fragment": "f_main3",
        "width": 6, "height": 1, "n": 6, "rt_count": 3,
    })

    # ---- OPT-10/11 (concurrency) ----
    for fn in CONC_FUNCS:
        for pairs in CONC_PAIRS:
            for rep in range(CONC_REPEATS):
                fenced = "unfenced" not in fn
                cases.append({
                    "id": f"opt1011_{fn}_p{pairs}_r{rep}", "item": "OPT-10/11", "kind": "concurrency",
                    "kernel": "opt1011_ordering.metal", "function": fn, "fastmath": False,
                    "pairs": pairs, "iterations": CONC_ITERATIONS, "spin_bound": CONC_SPINBOUND,
                    "fenced": fenced, "repeat": rep,
                })

    return cases


if __name__ == "__main__":
    cs = build_cases()
    from collections import Counter
    print("total cases:", len(cs))
    print(Counter(c["item"] for c in cs))
    print(Counter(c["kind"] for c in cs))
