"""EXP-0130 case matrix -- single source of truth for both official runs.

Every case is (mode, case_id, dst=(r,g,b,a), konst_or_src=(r,g,b,a)).
Values are chosen to be EXACTLY representable in IEEE-754 float32 (integers,
half-integers, and sums of a few power-of-two fractions) so a host oracle
computed in Python float (double) and the GPU's float32 readback can be
compared bit-for-bit with zero rounding ambiguity.
"""

DST_CASES = [
    ("d0_zero",       (0.0, 0.0, 0.0, 0.0)),
    ("d1_small_pos",  (1.0, 2.0, 3.0, 4.0)),
    ("d2_small_neg",  (-1.0, -2.0, -3.0, -4.0)),
    ("d3_large_mixed", (12345.0, -6789.5, 65536.25, -131072.125)),
    # Powers of two (exact in float32 up to the format's full exponent
    # range) rather than a decimal literal like 3.0e38: 3.0e38 is NOT
    # exactly representable in float32 (its nearest float32 differs from
    # the float64 value by a rounding step), which a pilot run of this
    # exact case caught as a false "mismatch" against a naive oracle --
    # see PROGRESS.md. 2**126 stays within float32's representable range
    # (max ~3.4028235e38) while remaining an exact large-magnitude probe.
    ("d4_near_fmax",  (2.0**126, -(2.0**126), 2.0**-120, -(2.0**-120))),
    ("d5_tiny_frac",  (0.0009765625, -0.0009765625, 0.03125, -0.03125)),
    ("d6_asymmetric", (7.5, 0.0, -100000.0, 0.25)),
    ("d7_negzero",    (-0.0, 0.0, 1.0, -1.0)),
]

# CTRL_KONST: fixed sentinel the f_eot_ctrl case writes, unrelated to any
# DST_CASES value, so a mismatch would be obvious.
CTRL_KONST = (111.0, -222.0, 333.5, -444.25)

# COMBINE_CASES: (case_id, dst, src)
COMBINE_CASES = [
    ("c0", (3.0, -4.0, 0.5, 2.0), (1.0, 2.0, 3.0, 4.0)),
    ("c1", (0.0, 0.0, 0.0, 0.0), (-5.0, 5.0, -5.0, 5.0)),
    ("c2", (-10.0, 20.0, -30.0, 40.0), (1.0, 1.0, 1.0, 1.0)),
    ("c3", (1.0e6, -1.0e6, 0.5, -0.5), (2.0, 2.0, 2.0, 2.0)),
]


def oracle_evict(dst):
    return tuple(dst)


def oracle_ctrl(konst):
    return tuple(konst)


def oracle_combine(dst, src):
    return tuple(d * 2.0 + s for d, s in zip(dst, src))


def all_cases():
    """Yield (mode, case_id, dst, konst_or_src, expected) tuples."""
    for cid, dst in DST_CASES:
        yield ("evict", cid, dst, (0.0, 0.0, 0.0, 0.0), oracle_evict(dst))
    for cid, dst in DST_CASES:
        yield ("ctrl", cid, dst, CTRL_KONST, oracle_ctrl(CTRL_KONST))
    for cid, dst, src in COMBINE_CASES:
        yield ("combine", cid, dst, src, oracle_combine(dst, src))
