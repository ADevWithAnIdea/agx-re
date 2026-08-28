#!/usr/bin/env python3
"""matrix.py -- EXP-0115 frozen case list, closing EXP-0104's 7 deferred items.

Kinds:
  compute         -- kernels/*.metal compute kernel via agxtest.py
  locate_splice   -- 2-step: compile+tokenize to find an instruction's offset,
                      THEN run with a computed splice. `locate_target` selects
                      which locator (see harness/run.py):
                        reach_jump_offset       (item 1: branch-reach map)
                        predtest_dstpred_ifpush (item 3: dst_pred / if_push_pred)
                        static_shuffle_lane     (item 4: static shuffle OOB)
  compile_limit   -- attempt to compile a kernel ONLY (no dispatch unless it
                      compiles); used for the CF-03 exact nesting ceiling
                      (item 2), where a Clang front-end diagnostic at the
                      boundary IS the expected/desired result.
  structural_pair / structural_group -- compile-only byte comparison (item 7).
  render          -- kernels/*.metal vertex+fragment via shdump --render +
                      agxrender (items 5, 6).

I32_MASK wraps int32 arithmetic for host oracles, matching EXP-0104's convention.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EXP_ROOT = os.path.dirname(HERE)
KERNELS = os.path.join(EXP_ROOT, "kernels")
KERNELS_DEEP = os.path.join(KERNELS, "deep")

REACH = os.path.join(KERNELS, "reach.metal")
CF_PRED = os.path.join(KERNELS, "cf_pred.metal")
SHUF_STATIC = os.path.join(KERNELS, "shuf_static.metal")
VOTE_FRAG = os.path.join(KERNELS, "vote_frag.metal")
WIDTH_FRAG = os.path.join(KERNELS, "width_frag.metal")
SGBAR_ADV = os.path.join(KERNELS, "sgbar_adv.metal")

I32_MASK = 0xffffffff


def i32(x):
    x &= I32_MASK
    return x - 0x100000000 if x & 0x80000000 else x


def oracle_expect(expected, out_idx=0):
    def fn(res):
        out = res["compute"]["results"].get(out_idx)
        return (out == expected), {"expected": expected, "got": out}
    return fn


# =============================================================================
# ITEM 1 -- exact branch-reach fault/silent-zero/correct boundary map.
# =============================================================================
REACH_A = [0, 1, 2, 3, 4, 5, 6, 7]


def _s3(v):
    s = 1
    for _ in range(v):
        s = i32(s * 3 + 1)
    return s


REACH_BASELINE_EXPECTED = [_s3(v) for v in REACH_A]

# Deltas frozen from this experiment's own reconnaissance (work/pilot/bisect_reach.py,
# real M4 dispatches, documented in PRE_REGISTRATION.md): a fine +/-1..32 sweep
# (baseline has ZERO slack -- delta=+1 already faults), a dense 128-step
# checkerboard sweep out to +/-4096 (forward is a genuine MIXED fault/silent-OK
# region, not a single sharp boundary; backward is uniformly fault/hang), extra
# fine detail around the 896..1024 forward transition, far geometric points out
# to the true 48-bit-field extreme.
REACH_FWD_FINE = list(range(1, 33))
REACH_FWD_CHECKER = list(range(128, 4097, 128))
REACH_FWD_DETAIL = [912, 928, 944, 960, 976, 992, 1008]
REACH_FWD_FAR = [8192, 16384, 32768, 65536, 131072, 262144, 524288,
                 1048576, 2097152, 3145728, 3670016, 4194304]
REACH_FWD_EXTREME = [0x7FFFFFFFFFFF]

REACH_BWD_FINE = list(range(1, 33))
REACH_BWD_CHECKER = list(range(128, 4097, 128))
REACH_BWD_FAR = [8192, 16384, 32768, 65536, 131072, 262144, 524288,
                 1048576, 2097152, 3145728, 3670016, 4194304]
REACH_BWD_EXTREME = [0x800000000000]


def gen_reach_cases():
    cases = []
    cases.append({
        "id": "reach_baseline", "item": "branch-reach", "kind": "compute",
        "source": REACH, "function": "reach_loop", "grid": 8, "tg": 8,
        "bufs": {1: REACH_A}, "outs": {0: 8},
        "oracle": oracle_expect(REACH_BASELINE_EXPECTED), "gated": True,
        "note": "real backward-jump loop baseline, no splice",
    })
    seen = set()
    for delta in (REACH_FWD_FINE + REACH_FWD_CHECKER + REACH_FWD_DETAIL +
                  REACH_FWD_FAR + REACH_FWD_EXTREME):
        if delta in seen:
            continue
        seen.add(delta)
        cases.append({
            "id": f"reach_fwd_{delta}", "item": "branch-reach", "kind": "locate_splice",
            "locate_target": "reach_jump_offset", "offset_delta": delta,
            "source": REACH, "function": "reach_loop", "grid": 8, "tg": 8,
            "bufs": {1: REACH_A}, "outs": {0: 8}, "oracle": None, "gated": True,
            "note": f"forward perturb loop back-edge offset by +{delta} bytes",
        })
    seen = set()
    for delta in (REACH_BWD_FINE + REACH_BWD_CHECKER + REACH_BWD_FAR + REACH_BWD_EXTREME):
        if delta in seen:
            continue
        seen.add(delta)
        cases.append({
            "id": f"reach_bwd_{delta}", "item": "branch-reach", "kind": "locate_splice",
            "locate_target": "reach_jump_offset", "offset_delta": -delta,
            "source": REACH, "function": "reach_loop", "grid": 8, "tg": 8,
            "bufs": {1: REACH_A}, "outs": {0: 8}, "oracle": None, "gated": True,
            "note": f"backward perturb loop back-edge offset by -{delta} bytes",
        })
    return cases


# =============================================================================
# ITEM 2 -- exact CF-03 nesting ceiling (push until it actually breaks).
# =============================================================================
IFNEST_DEPTHS = [128, 192, 224, 240, 248, 252, 254, 255]
LOOPNEST1_DEPTHS = [64, 160, 208, 232, 244, 250, 253, 255, 256]
LOOPNESTD2_DEPTHS = [12, 64, 128, 192, 224, 240, 252, 254, 255, 256]


def oracle_ifnest2(depth):
    def fn(res):
        out = res["compute"]["results"].get(0)
        if out is None:
            return False, {"reason": "no output"}
        a = res["case"]["bufs"][1]
        exp = []
        for v in a:
            hit = None
            for j in range(1, depth + 1):
                if v <= j:
                    hit = j
                    break
            exp.append(i32(-(1000 + hit)) if hit is not None else i32(v * v))
        return (exp == out), {"expected": exp, "got": out}
    return fn


def oracle_loopnest1b(depth):
    def fn(res):
        out = res["compute"]["results"].get(0)
        exp = [depth] * len(res["case"]["bufs"][1])
        return (out == exp), {"expected": exp, "got": out}
    return fn


def oracle_loopnestD2(depth):
    def fn(res):
        out = res["compute"]["results"].get(0)
        a = res["case"]["bufs"][1]
        exp = []
        for v in a:
            acc = 0
            for j in range(1, depth + 1):
                bit = (j - 1) % 32
                acc += 1 + ((v >> bit) & 1)
            exp.append(i32(acc))
        return (out == exp), {"expected": exp, "got": out}
    return fn


def gen_deep_cases():
    cases = []
    for d in IFNEST_DEPTHS:
        name = f"ifnest2_{d:03d}"
        src = os.path.join(KERNELS_DEEP, f"{name}.metal")
        vals = sorted(set([0, 1, max(1, d // 2), max(0, d - 1), d, d + 1, d + 50, d * 3 + 7]))
        while len(vals) < 8:
            vals.append(vals[-1] + 1)
        vals = vals[:8]
        cases.append({
            "id": f"deep_ifnest_{d:03d}", "item": "CF-03", "kind": "compile_limit",
            "source": src, "function": name, "grid": 8, "tg": 8,
            "bufs": {1: vals}, "outs": {0: 8},
            "oracle": oracle_ifnest2(d), "gated": True,
            "note": f"nested-if divergent-return depth={d}, expect compile OK "
                    f"({'toolchain bracket-depth FIRST_FAIL expected' if d == 255 else 'HW dispatch verified'})",
        })
    for d in LOOPNEST1_DEPTHS:
        name = f"loopnest1b_{d:03d}"
        src = os.path.join(KERNELS_DEEP, f"{name}.metal")
        cases.append({
            "id": f"deep_loopnest1_{d:03d}", "item": "CF-03", "kind": "compile_limit",
            "source": src, "function": name, "grid": 8, "tg": 8,
            "bufs": {1: [1] * 8}, "outs": {0: 8},
            "oracle": oracle_loopnest1b(d), "gated": True,
            "note": f"pure nested-loop structural depth={d}, v=1 "
                    f"({'toolchain bracket-depth FIRST_FAIL expected' if d == 256 else 'HW dispatch verified'})",
        })
    for d in LOOPNESTD2_DEPTHS:
        name = f"loopnestD2_{d:03d}"
        src = os.path.join(KERNELS_DEEP, f"{name}.metal")
        cases.append({
            "id": f"deep_loopnestD2_{d:03d}", "item": "CF-03", "kind": "compile_limit",
            "source": src, "function": name, "grid": 8, "tg": 8,
            "bufs": {1: [0, 1, 2, 3, 4, 5, 6, 7]}, "outs": {0: 8},
            "oracle": oracle_loopnestD2(d), "gated": True,
            "note": f"linear-work genuinely-divergent nested loop depth={d} "
                    f"({'toolchain bracket-depth FIRST_FAIL expected' if d == 256 else 'HW dispatch verified'})",
        })
    return cases


# =============================================================================
# ITEM 3 -- the dst_pred=1 mechanism: icmp_pred.dst_pred x if_push_pred.pred.
# =============================================================================
PREDTEST_A = [0, 1, 2, 3, 4, 5, 50, 200]
PREDTEST_BASELINE_EXPECTED = [-1001, -1001, -1002, -1003, -1004, 25, 2500, 40000]

# (dst_pred, if_push_pred_pred) pairs. Diagonal (matched) 0..15, plus
# off-diagonal cross-talk points, reconnaissance-confirmed (work/pilot) that
# output depends ONLY on dst_pred, never on the if_push pred nibble -- this
# formal matrix re-derives that independently in the gated capture.
PRED_MATRIX_PAIRS = (
    [(n, n) for n in range(16)] +
    [(1, 0), (1, 2), (1, 5), (1, 0xf), (0, 1), (0, 0xf),
     (2, 1), (5, 1), (0xf, 1), (5, 0xf), (0xf, 5)]
)


def gen_pred_cases():
    cases = []
    for dst, pred in PRED_MATRIX_PAIRS:
        cases.append({
            "id": f"pred_dst{dst:x}_ifp{pred:x}", "item": "CF-05-dstpred-mechanism",
            "kind": "locate_splice", "locate_target": "predtest_dstpred_ifpush",
            "dst_pred": dst, "ifpush_pred": pred,
            "source": CF_PRED, "function": "predtest_004", "grid": 8, "tg": 8,
            "bufs": {1: PREDTEST_A}, "outs": {0: 8}, "oracle": None, "gated": True,
            "note": f"icmp_pred.dst_pred={dst:#x}, if_push byte+1 hi nibble (pred)={pred:#x}",
        })
    return cases


# =============================================================================
# ITEM 4 -- static/immediate-index shuffle family out-of-range.
# =============================================================================
SHUF_GRID = 32

SIMD_SHUFFLE_RAW = sorted(set(
    [0, 2, 30, 62] +
    list(range(64, 125, 4)) +
    [128, 140, 150, 160, 168, 240, 250, 254] +
    [1, 65, 127, 255]
))
SHUFFLEXOR_RAW = sorted(set([0, 2, 62, 64, 66, 80, 126, 128, 254, 1, 65, 127, 255]))
QUADSHUFFLE_RAW = sorted(set([0, 2, 4, 6, 8, 10, 14, 30, 60, 126, 254, 1, 3, 5, 255]))


def gen_static_shuffle_cases():
    cases = []
    for raw in SIMD_SHUFFLE_RAW:
        cases.append({
            "id": f"sshuf_raw_{raw:03d}", "item": "SIMD-03-static", "kind": "locate_splice",
            "locate_target": "static_shuffle_lane", "shuffle_fn": "shuffle_static",
            "lane_raw": raw,
            "source": SHUF_STATIC, "function": "shuffle_static", "grid": SHUF_GRID, "tg": SHUF_GRID,
            "bufs": {}, "outs": {0: SHUF_GRID}, "oracle": None, "gated": True,
            "note": f"simd_shuffle static form: lane byte spliced to raw={raw:#x} (idx={raw>>1}{'*' if raw & 1 else ''})",
        })
    for raw in SHUFFLEXOR_RAW:
        cases.append({
            "id": f"sxor_raw_{raw:03d}", "item": "SIMD-03-static", "kind": "locate_splice",
            "locate_target": "static_shuffle_lane", "shuffle_fn": "shufflexor_static",
            "lane_raw": raw,
            "source": SHUF_STATIC, "function": "shufflexor_static", "grid": SHUF_GRID, "tg": SHUF_GRID,
            "bufs": {}, "outs": {0: SHUF_GRID}, "oracle": None, "gated": True,
            "note": f"simd_shuffle_xor static form: lane byte spliced to raw={raw:#x} (mask={raw>>1}{'*' if raw & 1 else ''})",
        })
    for raw in QUADSHUFFLE_RAW:
        cases.append({
            "id": f"squad_raw_{raw:03d}", "item": "SIMD-03-static", "kind": "locate_splice",
            "locate_target": "static_shuffle_lane", "shuffle_fn": "quadshuffle_static",
            "lane_raw": raw,
            "source": SHUF_STATIC, "function": "quadshuffle_static", "grid": SHUF_GRID, "tg": SHUF_GRID,
            "bufs": {}, "outs": {0: SHUF_GRID}, "oracle": None, "gated": True,
            "note": f"quad_shuffle static form: lane byte spliced to raw={raw:#x} (idx={raw>>1}{'*' if raw & 1 else ''})",
        })
    return cases


# =============================================================================
# ITEM 5 -- full vote family under discard + the popcount 16->24 puzzle.
# =============================================================================
def gen_vote_cases():
    cases = []
    fns_pc = ["f_mask_baseline_pc", "f_mask_1discard_pc", "f_mask_1return_pc",
              "f_mask_2discard_pc", "f_mask_discard11_pc",
              "f_ballotpred_baseline_pc", "f_ballotpred_1discard_pc"]
    fns_raw = ["f_mask_baseline_raw", "f_mask_1discard_raw"]
    fns_bool = ["f_all_baseline", "f_all_1discard", "f_any_baseline", "f_any_1discard"]
    for fn in fns_pc + fns_raw + fns_bool:
        cases.append({
            "id": f"vote_{fn}", "item": "SIMD-07-vote-family", "kind": "render",
            "source": VOTE_FRAG, "vertex": "v_main", "fragment": fn,
            "width": 4, "height": 4, "oracle": None, "gated": True,
            "note": f"vote-family probe {fn}, 4x4 target",
        })
    return cases


# =============================================================================
# ITEM 6 -- fragment-stage SIMD width sweep across sizes crossing the fixed
# 32x32 AGX tile boundary (docs/pipeline/README.md).
# =============================================================================
WIDTH_SIZES = [(1, 1), (2, 2), (3, 3), (4, 4), (8, 8), (16, 16),
               (31, 31), (32, 32), (33, 33), (40, 24), (48, 48), (64, 64)]


def gen_width_cases():
    cases = []
    for w, h in WIDTH_SIZES:
        cases.append({
            "id": f"width_{w}x{h}", "item": "SIMD-01-fragment-width", "kind": "render",
            "source": WIDTH_FRAG, "vertex": "v_main", "fragment": "f_width_report",
            "width": w, "height": h, "oracle": None, "gated": True,
            "note": f"fragment threads_per_simdgroup / thread_index_in_simdgroup at {w}x{h}",
        })
    return cases


# =============================================================================
# ITEM 7 -- SIMD-06 structural vs functional independence (adversarial shapes).
# =============================================================================
SGBAR_PAIRS = ["sgbar_loop", "sgbar_ifdiv", "sgbar_highreg", "sgbar_double", "sgbar_nested"]


def gen_sgbar_cases():
    cases = []
    for base in SGBAR_PAIRS:
        cases.append({
            "id": f"sg_struct_{base}", "item": "SIMD-06-adversarial", "kind": "structural_pair",
            "source": SGBAR_ADV, "function_a": f"{base}_bar", "function_b": f"{base}_nobar",
            "oracle": None, "gated": True,
            "note": f"compile-only byte-shape comparison: {base} WITH vs WITHOUT simdgroup_barrier",
        })
    # functional correctness + deadlock-risk runs for the two riskiest shapes
    # (divergent CALL COUNT and divergent CALL PRESENCE) -- hard-timeout guarded.
    loop_a = [0, 1, 2, 3, 5, 8, 13, 21]

    def loop_oracle(res):
        out = res["compute"]["results"].get(0)
        exp = [i32(sum(range(v))) for v in loop_a]
        return (out == exp), {"expected": exp, "got": out}
    cases.append({
        "id": "sg_func_loop_bar", "item": "SIMD-06-adversarial", "kind": "compute",
        "source": SGBAR_ADV, "function": "sgbar_loop_bar", "grid": 8, "tg": 8,
        "bufs": {1: loop_a}, "outs": {0: 8}, "oracle": loop_oracle, "gated": True,
        "run_timeout": 10.0,
        "note": "DEADLOCK-RISK: divergent per-lane barrier call COUNT, hard 10s timeout",
    })
    ifdiv_a = [0, 1, 2, 3, 4, 5, 6, 7]

    def ifdiv_oracle(res):
        out = res["compute"]["results"].get(0)
        exp = [i32(v * 2) for v in ifdiv_a]
        return (out == exp), {"expected": exp, "got": out}
    cases.append({
        "id": "sg_func_ifdiv_bar", "item": "SIMD-06-adversarial", "kind": "compute",
        "source": SGBAR_ADV, "function": "sgbar_ifdiv_bar", "grid": 8, "tg": 8,
        "bufs": {1: ifdiv_a}, "outs": {0: 8}, "oracle": ifdiv_oracle, "gated": True,
        "run_timeout": 10.0,
        "note": "DEADLOCK-RISK: divergent per-lane barrier call PRESENCE, hard 10s timeout",
    })
    return cases


def build_matrix():
    cases = []
    cases += gen_reach_cases()
    cases += gen_deep_cases()
    cases += gen_pred_cases()
    cases += gen_static_shuffle_cases()
    cases += gen_vote_cases()
    cases += gen_width_cases()
    cases += gen_sgbar_cases()
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case id"
    return cases


if __name__ == "__main__":
    import json
    m = build_matrix()
    by_item = {}
    for c in m:
        by_item.setdefault(c["item"], 0)
        by_item[c["item"]] += 1
    print(f"total cases: {len(m)}")
    print(json.dumps(by_item, indent=2, sort_keys=True))
