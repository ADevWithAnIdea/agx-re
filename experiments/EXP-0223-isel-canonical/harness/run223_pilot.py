#!/usr/bin/env python3
"""EXP-0223 pre-freeze generated isel10 pilots."""

import sys
from pathlib import Path

NEW_EXP = Path(__file__).resolve().parent.parent
REPO_EXP = NEW_EXP.parent
OLD_HARNESS = REPO_EXP / "EXP-0220-canonical-recipes" / "harness"
if not OLD_HARNESS.exists():
    OLD_HARNESS = REPO_EXP / "EXP-0220" / "harness"
sys.path.insert(0, str(OLD_HARNESS))

import cases220 as C  # noqa: E402
import prog220 as P  # noqa: E402
import run220 as R  # noqa: E402
import synth220 as S  # noqa: E402


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0223 PRE_REGISTRATION", note)


def packed(reg, packing):
    if packing == "h1":
        return reg
    if packing == "h2":
        return (reg << 1) | 1
    if packing == "h3":
        return reg << 2
    raise ValueError(packing)


def emit_isel(pg, dst, cmp_a, cmp_b, sel_true, sel_false, packing,
              model_cmp_a=None, model_cmp_b=None):
    pg.E.emit("isel10", {
        "dst": fv(dst, "destination GPR candidate"),
        "cmpA": fv(packed(cmp_a, packing), f"{packing} compare-A selector"),
        "opsel": fv(0, "lowest structural ten-byte member"),
        "cmpB": fv(packed(cmp_b, packing), f"{packing} compare-B selector"),
        "cmp_mode": fv(0x81, "signed less-than mode hypothesis"),
        "selTrue": fv(packed(sel_true, packing), f"{packing} true selector"),
        "cc": fv(0x07, "signed less-than condition hypothesis"),
        "flags": fv(0, "canonical lifecycle candidate"),
        "selFalse_file": fv(0, "GPR false-source candidate"),
        "selFalse": fv(packed(sel_false, packing), f"{packing} false selector"),
    })
    pg._pending = None
    ma = cmp_a if model_cmp_a is None else model_cmp_a
    mb = cmp_b if model_cmp_b is None else model_cmp_b
    av, bv = pg.rbits(ma), pg.rbits(mb)
    tv, fv_bits = pg.rbits(sel_true), pg.rbits(sel_false)
    out = None if None in (av, bv, tv, fv_bits) else (tv if av < bv else fv_bits)
    pg.set_reg(dst, out)


def fresh(case, slots):
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.prologue(seed_high=True)
    return pg


ORIG_CASES = C.build_cases
ORIG_BUILD = C.build_program_for


def build_cases(include_hazard=False):
    out = [c for c in ORIG_CASES(False) if c["arm"] == "S0"]
    for packing in ("h1", "h2", "h3"):
        for direction, ca, cb in (("true", 1, 2), ("false", 2, 1)):
            out.append({
                "i": len(out), "name": f"{packing}_{direction}", "arm": packing.upper(),
                "kind": "isel10", "expect_match": True, "predicted_bucket": "exact",
                "op": dict(dst=0, cmp_a=ca, cmp_b=cb, sel_true=3, sel_false=4,
                           packing=packing),
            })
    out.append({
        "i": len(out), "name": "ctl_wrong_predicate", "arm": "CTL", "kind": "isel10",
        "expect_match": False, "predicted_bucket": "refute",
        "op": dict(dst=0, cmp_a=1, cmp_b=2, sel_true=3, sel_false=4,
                   packing="h1", model_cmp_a=2, model_cmp_b=1),
    })
    return out


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIG_BUILD(case, slots, carrier_len)
    pg = fresh(case, slots)
    emit_isel(pg, **case["op"])
    pg.dump()
    return pg, pg.finish(carrier_len)


def main():
    C.build_cases = build_cases
    C.build_program_for = build_program_for
    return R.main()


if __name__ == "__main__":
    raise SystemExit(main())
