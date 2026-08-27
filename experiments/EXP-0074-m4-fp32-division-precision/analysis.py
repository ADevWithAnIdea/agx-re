#!/usr/bin/env python3
"""EXP-0074 deterministic analysis: compare captured FP32 division bits against
a correctly-rounded IEEE-754 binary32 division reference.

Reference logic adopted unchanged from the frozen EXP-0073 registration.

The reference is implemented twice, by independent algorithms:
  method A: exact rational quotient (fractions.Fraction) plus exact
            bracket-and-compare round-to-nearest-even to the binary32 format
            (subnormal lattice and overflow threshold handled exactly);
  method B: pure integer long division of the normalized significands with
            64 guard bits and a sticky remainder, one single rounding step.
Neither method ever converts through binary64, so no double rounding can occur.
Any disagreement between the two methods, or any failure of the frozen
hand-computed validation set, is a hard STOP (SystemExit).

NaN policy: cases whose exact IEEE result is NaN are compared by is-NaN only;
the hardware payload is recorded verbatim and never normalized or required to
match any particular bits.
"""
import argparse, hashlib, json
from fractions import Fraction
from pathlib import Path

import run as F

HERE = Path(__file__).resolve().parent

MIN_NORM = Fraction(2) ** -126
MIN_SUB = Fraction(2) ** -149
MAXF = (2 - Fraction(2) ** -23) * Fraction(2) ** 127
OVR_THR = MAXF + Fraction(2) ** 103
NAN = "NAN"


def split(x):
    return (x >> 31) & 1, (x >> 23) & 0xFF, x & 0x7FFFFF


def val(x):
    """Exact rational value of a finite binary32 bit pattern."""
    _, e, m = split(x)
    if e == 0:
        return Fraction(m) * Fraction(2) ** -149
    return Fraction((1 << 23) | m) * Fraction(2) ** (e - 150)


def floor_log2(q):
    e = q.numerator.bit_length() - q.denominator.bit_length()
    while Fraction(2) ** e > q:
        e -= 1
    while Fraction(2) ** (e + 1) <= q:
        e += 1
    return e


def _rNE(lo, rem):  # round nonneg integer lo with exact fractional remainder rem
    half = Fraction(1, 2)
    if rem > half or (rem == half and (lo & 1) == 1):
        return lo + 1
    return lo


def rnd_frac(sign, q):
    """Round exact nonnegative Fraction q to binary32 bits, roundTiesToEven."""
    if q == 0:
        return sign << 31
    if q >= OVR_THR:
        return (sign << 31) | 0x7F800000
    if q >= MIN_NORM:
        E = floor_log2(q)
        m = q / (Fraction(2) ** (E - 23))
        lo = m.numerator // m.denominator
        M = _rNE(lo, m - lo)
        if M == 1 << 24:
            M = 1 << 23
            E += 1
            if E > 127:
                return (sign << 31) | 0x7F800000
        return (sign << 31) | ((E + 127) << 23) | (M - (1 << 23))
    u = q / MIN_SUB
    U = _rNE(u.numerator // u.denominator, u - (u.numerator // u.denominator))
    if U == 1 << 23:
        return (sign << 31) | 0x00800000
    return (sign << 31) | U


def _specials(a, b):
    """Shared IEEE special-class dispatch; returns bits string, or None if both finite."""
    sa, ea, ma = split(a)
    sb, eb, mb = split(b)
    a_nan, a_inf = ea == 255 and ma != 0, ea == 255 and ma == 0
    b_nan, b_inf = eb == 255 and mb != 0, eb == 255 and mb == 0
    az, bz = ea == 0 and ma == 0, eb == 0 and mb == 0
    if a_nan or b_nan or (a_inf and b_inf) or (az and bz):
        return NAN
    if a_inf:
        return (sa ^ sb) << 31 | 0x7F800000
    if b_inf:
        return (sa ^ sb) << 31
    if bz:
        return (sa ^ sb) << 31 | 0x7F800000
    if az:
        return (sa ^ sb) << 31
    return None


def ref_A(a, b):
    """Method A: exact Fraction quotient + exact bracket rounding."""
    s = _specials(a, b)
    if s is not None:
        return s
    sa, _, _ = split(a)
    sb, _, _ = split(b)
    return rnd_frac(sa ^ sb, val(a) / val(b))


def ref_B(a, b):
    """Method B: integer long division, 64 guard bits + sticky, single rounding."""
    s = _specials(a, b)
    if s is not None:
        return s
    sa, ea, ma = split(a)
    sb, eb, mb = split(b)

    def norm(m, e):
        while m < (1 << 23):
            m <<= 1
            e -= 1
        return m, e

    if ea == 0:
        Ma, Ea = norm(ma, -149)
    else:
        Ma, Ea = (1 << 23) | ma, ea - 150
    if eb == 0:
        Mb, Eb = norm(mb, -149)
    else:
        Mb, Eb = (1 << 23) | mb, eb - 150
    sign = (sa ^ sb) << 31
    G = 64
    Q, R = divmod(Ma << G, Mb)          # exact quotient = (Q + R/Mb) * 2^(Ea-Eb-G)
    E = Ea - Eb - G
    if not ((1 << 63) <= Q < (1 << 65)):
        raise SystemExit("reference B normalization out of range")
    sh = 26 - Q.bit_length()            # keep top 26 bits (24 sig + round + guard)
    if sh >= 0:
        Qt, dropped = Q << sh, 0
    else:
        Qt, dropped = Q >> (-sh), Q & ((1 << (-sh)) - 1)
    sticky = dropped != 0 or R != 0
    Ee = E - sh                          # value = (Qt + tail) * 2^Ee, tail in [0,1)
    top = Ee + 25
    if top >= -126:                      # normal target: 24-bit significand
        high24, low2 = Qt >> 2, Qt & 3
        if low2 > 2 or (low2 == 2 and (sticky or (high24 & 1))):
            high24 += 1
        Ef = Ee + 2
        if high24 == 1 << 24:
            high24 >>= 1
            Ef += 1
        E2 = Ef + 23
        if E2 > 127:
            return sign | 0x7F800000
        return sign | ((E2 + 127) << 23) | (high24 - (1 << 23))
    s2 = -149 - Ee                       # subnormal target: single rounding on the 2^-149 lattice
    if s2 < 3:
        raise SystemExit("reference B subnormal shift out of range")
    U, mask = Qt >> s2, Qt & ((1 << s2) - 1)
    half = 1 << (s2 - 1)
    if mask > half or (mask == half and (sticky or (U & 1))):
        U += 1
    if U == 0:
        return sign
    if U == 1 << 23:
        return sign | 0x00800000
    if U > 0x7FFFFF:
        raise SystemExit("reference B subnormal overflow")
    return sign | U


# Frozen hand-computed validation set (name, a, b, expected bits).
HAND = (
    ("1/3", 0x3F800000, 0x40400000, 0x3EAAAAAB),
    ("2/3", 0x40000000, 0x40400000, 0x3F2AAAAB),
    ("1/10", 0x3F800000, 0x41200000, 0x3DCCCCCD),
    ("1/7", 0x3F800000, 0x40E00000, 0x3E124925),
    ("1/1", 0x3F800000, 0x3F800000, 0x3F800000),
    ("(1+eps)/1", 0x3F800001, 0x3F800000, 0x3F800001),
    ("(1-ulp/2)/1", 0x3F7FFFFF, 0x3F800000, 0x3F7FFFFF),
    ("minsub/minsub", 0x00000001, 0x00000001, 0x3F800000),
    ("minsub/sub3", 0x00000001, 0x00000003, 0x3EAAAAAB),
    ("sub2/sub3", 0x00000002, 0x00000003, 0x3F2AAAAB),
    ("sub3/sub2", 0x00000003, 0x00000002, 0x3FC00000),
    ("maxsub/minsub", 0x007FFFFF, 0x00000001, 0x4AFFFFFE),
    ("sub2/minsub", 0x00000002, 0x00000001, 0x40000000),
    ("minsub/3.0", 0x00000001, 0x40400000, 0x00000000),
    ("sub2/3.0", 0x00000002, 0x40400000, 0x00000001),
    ("sub3/2.0", 0x00000003, 0x40000000, 0x00000002),
    ("sub7/2.0", 0x00000007, 0x40000000, 0x00000004),
    ("minnorm/2.0", 0x00800000, 0x40000000, 0x00400000),
    ("maxsub/2.0", 0x007FFFFF, 0x40000000, 0x00400000),
    ("minsub/0.5", 0x00000001, 0x3F000000, 0x00000002),
    ("max/(1-2^-24)", 0x7F7FFFFF, 0x3F7FFFFF, 0x7F800000),
    ("2^127/0.5", 0x7F000000, 0x3F000000, 0x7F800000),
    ("2^127/2.0", 0x7F000000, 0x40000000, 0x7E800000),
    ("1/inf", 0x3F800000, 0x7F800000, 0x00000000),
    ("-1/inf", 0xBF800000, 0x7F800000, 0x80000000),
    ("7/9", 0x40E00000, 0x41100000, 0x3F471C72),
    ("pi/2", 0x40490FDB, 0x40000000, 0x3FC90FDB),
)


def reference_selfcheck():
    fails = []
    for nm, a, b, want in HAND:
        ra, rb = ref_A(a, b), ref_B(a, b)
        if ra != want or rb != want:
            fails.append({"name": nm, "a": "0x%08X" % a, "b": "0x%08X" % b,
                          "ref_A": "0x%08X" % ra if ra != NAN else "NAN",
                          "ref_B": "0x%08X" % rb if rb != NAN else "NAN",
                          "hand_expected": "0x%08X" % want})
    return fails


def fclass(x):
    e, m = (x >> 23) & 0xFF, x & 0x7FFFFF
    if e == 255:
        return "nan" if m else "inf"
    if e == 0:
        return "zero" if m == 0 else "subnormal"
    return "normal"


def ordered(x):  # monotone integer map for ULP distance on non-NaN values
    return x + (1 << 32) if x & (1 << 31) else (x ^ 0x80000000)


def load_run(rid):
    cases = json.loads((HERE / "raw" / rid / "01_cases.json").read_text())
    lines = (HERE / "raw" / rid / "04_results.jsonl").read_text().splitlines()
    if len(lines) != F.TOTAL:
        raise SystemExit("run %s: expected %d result lines, got %d" % (rid, F.TOTAL, len(lines)))
    out = []
    frozen = F.all_cases()
    for i, ln in enumerate(lines):
        r = json.loads(ln)
        if set(r) != {"i", "a", "b", "r"} or r["i"] != i:
            raise SystemExit("run %s: bad result line %d" % (rid, i))
        if int(r["a"], 16) != frozen[i][2] or int(r["b"], 16) != frozen[i][3]:
            raise SystemExit("run %s: result echo mismatch at %d" % (rid, i))
        out.append((r["a"].upper(), r["b"].upper(), r["r"].upper()))
    directed = [{"i": c["i"], "name": c["name"], "a": c["a"].upper(), "b": c["b"].upper()} for c in cases["directed"]]
    randomized = [{"i": c["i"], "a": c["a"].upper(), "b": c["b"].upper()} for c in cases["randomized"]]
    if len(directed) != len(F.DIRECTED) or len(randomized) != F.LCG["pairs"]:
        raise SystemExit("run %s: case counts differ from frozen inputs" % rid)
    return directed, randomized, out


def compare(rid, rows):
    """rows: list of (name, a_int, b_int, observed_int). Returns per-case records."""
    recs = []
    for name, a, b, obs in rows:
        ra, rb = ref_A(a, b), ref_B(a, b)
        if ra != rb:
            raise SystemExit("reference methods disagree at %s (%08x/%08x): A=%s B=%s"
                             % (name, a, b, ra, rb))
        rec = {"name": name, "a": "0x%08X" % a, "b": "0x%08X" % b,
               "a_class": fclass(a), "b_class": fclass(b)}
        if ra == NAN:
            rec.update({"reference": "NAN", "observed": "0x%08X" % obs,
                        "observed_class": fclass(obs),
                        "match": fclass(obs) == "nan"})
            if fclass(obs) == "nan":
                rec["observed_nan_payload_hex"] = "0x%06X" % (obs & 0x7FFFFF)
                rec["observed_nan_quiet"] = bool((obs >> 22) & 1)
        else:
            rec.update({"reference": "0x%08X" % ra, "observed": "0x%08X" % obs,
                        "observed_class": fclass(obs), "match": obs == ra})
            if obs != ra and fclass(obs) not in ("nan",) and fclass(ra) not in ("nan",):
                rec["ulp_delta"] = ordered(obs) - ordered(ra)
        recs.append(rec)
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", required=True)
    ap.add_argument("--run-b", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    hand_fails = reference_selfcheck()
    if hand_fails:
        raise SystemExit("reference hand-validation failed: " + json.dumps(hand_fails))

    runs = {}
    for rid in (a.run_a, a.run_b):
        directed, randomized, res = load_run(rid)
        rows = [(nm, ai, bi, int(res[i][2], 16))
                for i, (k, nm, ai, bi) in enumerate(F.all_cases())]
        runs[rid] = {"directed": compare(rid, rows[:len(F.DIRECTED)]),
                     "randomized": compare(rid, rows[len(F.DIRECTED):])}

    # byte-exact repeat check on raw observed bits
    raw_a = (HERE / "raw" / a.run_a / "04_results.jsonl").read_bytes()
    raw_b = (HERE / "raw" / a.run_b / "04_results.jsonl").read_bytes()
    repeat_exact = raw_a == raw_b

    def summarize(recs):
        mism = [r for r in recs if not r["match"]]
        return len(recs), len(recs) - len(mism), mism

    ds, rs = runs[a.run_a]["directed"], runs[a.run_a]["randomized"]
    d_tot, d_ok, d_mism = summarize(ds)
    r_tot, r_ok, r_mism = summarize(rs)
    out = {
        "runs": [a.run_a, a.run_b],
        "repeat_exact": repeat_exact,
        "reference": {
            "rounding": "IEEE-754 binary32 roundTiesToEven",
            "denormals": "gradual underflow in the reference (no flush)",
            "methods": ["A: exact Fraction quotient + exact bracket rounding",
                        "B: integer long division, 64 guard bits + sticky, single rounding"],
            "binary64_path_used": False,
            "hand_validation_cases": len(HAND),
            "hand_validation_failures": hand_fails,
            "cross_method_disagreements": 0,
        },
        "verdict_counts": {
            "directed": {"total": d_tot, "matches": d_ok, "mismatches": d_mism},
            "randomized": {"total": r_tot, "matches": r_ok, "mismatches": r_mism},
        },
        "directed": ds,
        "randomized_summary": {
            "total": r_tot, "matches": r_ok, "mismatch_count": len(r_mism),
            "mismatch_breakdown": _breakdown(r_mism),
            "mismatches": r_mism,
        },
        "nan_payload_observations": [r for r in ds + rs if r.get("reference") == "NAN"],
    }
    txt = json.dumps(out, indent=2, sort_keys=True) + "\n"
    if a.write:
        (HERE / "analysis.json").write_text(txt)
    print(txt)


def _breakdown(mism):
    d = {}
    for r in mism:
        ref_class = "nan" if r["reference"] == "NAN" else fclass(int(r["reference"], 16))
        k = "a=%s,b=%s,ref=%s,obs=%s" % (r["a_class"], r["b_class"], ref_class, r["observed_class"])
        d[k] = d.get(k, 0) + 1
    return d


if __name__ == "__main__":
    main()
