#!/usr/bin/env python3
"""EXP-0139 gates. `--selftest` runs with NO device present."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(HERE))
import anchors as A, isadb, casematrix as CM   # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def compiled_mains(bindir=None):
    """Compile every NATURAL carrier once and return {function: main_bytes}."""
    import sweeprun as S
    out = {}
    fns = sorted({fn for fn, _, _, _ in CM.NAT_ANCHORS.values()})
    for fn in fns:
        c = S._compile_only(EXP / "kernels" / CM.NAT_SRC, fn, EXP / "work" / "compile")
        out[fn] = c
    return out


def selftest():
    n = 0
    # 1. field bit convention == isadb.assemble, over every target mnemonic
    for mn in ["iadd2", "ibfe", "ibfins", "ibitcount", "iunary", "imad", "iminmax",
               "isel8", "isel10", "isel_reg", "isel10_c", "isel_reg8", "ishift",
               "icmpsel", "icmp_pred"]:
        ins = [i for i in isadb.DB if i["mnemonic"] == mn][0]
        blob = bytes(ins["length"])
        fields = {f["name"]: 0 for f in ins["fields"]}
        for st, w, v in ins["match"]:
            for k in range(w):
                bit = st + k
                blob = blob[:bit // 8] + bytes([blob[bit // 8] | (((v >> k) & 1) << (bit % 8))]) + blob[bit // 8 + 1:]
        for f in ins["fields"]:
            for tv in (0, 1, (1 << f["width"]) - 1):
                b2 = A.set_field(blob, mn, f["name"], tv)
                assert A.get_field(b2, mn, f["name"]) == tv, (mn, f["name"], tv)
                n += 1
    # 2. every _wide_values set honours FIELD-SWEEP-PROTOCOL 3.3
    for w in (9, 24, 40):
        vs = CM._wide_values(w)
        hi = (1 << w) - 1
        assert {0, 1, 2, hi, hi - 1} <= set(vs), w
        assert all((1 << k) in vs for k in range(w)), w
        assert len(vs) >= 16, w
        n += 1
    # 3. oracle models are self-consistent
    assert CM.ibfe_offset_model(4) == CM.baseline_oracle("k_bfe_const")
    assert CM.ibfe_width_model(8) == CM.baseline_oracle("k_bfe_const")
    assert CM.ishift_shamt_model(16) == CM.baseline_oracle("k_ashr")
    assert CM.dst_relocation_oracle(CM.R_DST << 1) == CM.IADD_BASE_SUM
    assert CM.dst_relocation_oracle(0) == CM.SENTINEL
    assert CM.dst_relocation_oracle((CM.R_DST + 64) << 1) == CM.IADD_BASE_SUM, "EXP-0112 alias model"
    n += 6
    # 4. every mov_imm immediate is inside the HW-VALIDATED 0..127 safe range
    for r, v in CM.SEED.items():
        assert 0 <= v <= 127, (r, v)
    for r, v in CM.SEED_POP.items():
        assert 0 <= v <= 127, (r, v)
    n += 1
    # 5. synthesized programs round-trip through isadb
    p = CM.iadd2_prog()
    import isa_helpers as H
    H.assert_round_trip(p)
    H.assert_round_trip(CM.bitcount_prog2())
    H.assert_round_trip(CM.iunary_prog(CM.IUNARY_BASE_OPERAND))
    n += 3
    print("SELFTEST PASS (%d checks)" % n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--between-runs", nargs=2)
    a = ap.parse_args()
    if a.selftest:
        selftest()


if __name__ == "__main__":
    main()
