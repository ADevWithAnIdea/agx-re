#!/usr/bin/env python3
"""EXP-0222 pre-freeze pilot for the independently generated iadd2 H1 recipe.

This intentionally reuses EXP-0220's already-audited carrier, runner, complete-state
oracle, actual-byte ledger, and archive splicer.  EXP-0222 supplies only a new generated
instruction recipe and case matrix.  Pilot output goes under work/pilot and is never
promotion evidence.
"""

import sys
from pathlib import Path

NEW_EXP = Path(__file__).resolve().parent.parent
REPO_EXP = NEW_EXP.parent
OLD_HARNESS = REPO_EXP / "EXP-0220-canonical-recipes" / "harness"
if not OLD_HARNESS.exists():
    # The Neo push layout used the short directory name.
    OLD_HARNESS = REPO_EXP / "EXP-0220" / "harness"
sys.path.insert(0, str(OLD_HARNESS))

import cases220 as C  # noqa: E402
import prog220 as P  # noqa: E402
import run220 as R  # noqa: E402
import synth220 as S  # noqa: E402


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0222 PRE_REGISTRATION H1", note)


def emit_iadd(pg, dst, src_a, src_b, add=True, model_a=None, model_b=None,
              packing="h1", opmode=2, src_a_desc=0, srca_ctl=0xA8,
              opc_tail=0x17, opc_tail2=0x05, logical_order=False,
              release_a=None, release_b=None):
    """Emit one complete no-donor iadd2 and advance the independent host model."""
    phys_a, phys_b = src_a, src_b
    subtract_swapped = logical_order and not add
    if subtract_swapped:
        # The hardware subtraction observed in pilot01 is second - first.
        phys_a, phys_b = src_b, src_a

    if packing == "h1":
        ea, eb = (phys_a << 2) | src_a_desc, phys_b << 2
    elif packing == "h2":
        ea, eb = (phys_a << 1) | 1, (phys_b << 1) | 1
    elif packing == "h3":
        ea, eb = src_b << 2, src_a << 2
    else:
        raise ValueError(packing)

    if release_a is not None or release_b is not None:
        if release_a is None or release_b is None:
            raise ValueError("release_a and release_b must be specified together")
        release_first, release_second = release_a, release_b
        if subtract_swapped:
            release_first, release_second = release_b, release_a
        opc_tail = 0x11 | (int(release_second) << 1) | (int(release_first) << 2)

    pg.E.emit("iadd2", {
        "addsub": fv(1 if add else 0, "1 add; 0 subtract"),
        "lenbit": fv(1, "canonical ten-byte form"),
        "srcB_reg_hi": fv(0, "canonical register form"),
        "b2_bit0": fv(0, "canonical accepted point"),
        "store_en": fv(1, "publish destination"),
        "b2_fmt": fv(0x15, "canonical accepted format point"),
        "dst": fv((dst << 1) | 1, "32-bit destination descriptor"),
        "opmode": fv(opmode, "canonical register mode plus nominated lifecycle bit"),
        "srcB_imm": fv(eb, "H1 second source selector"),
        "srcB_imm_hi": fv(0, "canonical register form"),
        "srcB_ext": fv(ea, "H1 first source selector"),
        "srcA": fv(srca_ctl, "canonical operand-control point plus nominated lifecycle bit"),
        "opc_tail": fv(opc_tail, "canonical accepted tail plus nominated lifecycle bits"),
        "opc_tail2": fv(opc_tail2, "canonical accepted tail 2"),
    })

    # Any pending load is deliberately outside this pilot's envelope.
    pg._pending = None
    ma = src_a if model_a is None else model_a
    mb = src_b if model_b is None else model_b
    av, bv = pg.rbits(ma), pg.rbits(mb)
    if av is None or bv is None:
        out = None
    elif add:
        out = (av + bv) & 0xFFFFFFFF
    else:
        out = (av - bv) & 0xFFFFFFFF
    # L1 observes source release before destination publication for aliases:
    # an aliased destination contains the arithmetic result, not zero.
    if release_a:
        pg.set_reg(src_a, 0)
    if release_b:
        pg.set_reg(src_b, 0)
    pg.set_reg(dst, out)


def fresh(case, slots):
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.prologue(seed_high=True)
    return pg


def build_iadd(case, slots, carrier_len):
    pg = fresh(case, slots)
    for op in case["ops"]:
        emit_iadd(pg, **op)
    return pg


ORIG_CASES = C.build_cases
ORIG_BUILD = C.build_program_for


def build_cases(include_hazard=False):
    # Keep EXP-0220's hardware-measured slot probe as carrier plumbing only.
    out = [c for c in ORIG_CASES(False) if c["arm"] == "S0"]
    specs = [
        ("h1_add_1_2_to_0", [dict(dst=0, src_a=1, src_b=2, add=True)]),
        ("h1_sub_4_5_to_3", [dict(dst=3, src_a=4, src_b=5, add=False)]),
        ("h1_add_alias_a", [dict(dst=6, src_a=6, src_b=7, add=True)]),
        ("h1_sub_alias_b", [dict(dst=8, src_a=9, src_b=8, add=False)]),
        ("h1_add_same_src", [dict(dst=10, src_a=11, src_b=11, add=True)]),
        ("h1_chain_immediate", [
            dict(dst=10, src_a=1, src_b=2, add=True),
            dict(dst=11, src_a=10, src_b=3, add=False),
        ]),
        ("h1_reuse_destination", [
            dict(dst=4, src_a=1, src_b=2, add=True),
            dict(dst=4, src_a=4, src_b=3, add=True),
            dict(dst=5, src_a=4, src_b=2, add=False),
        ]),
        ("h1_cross_low", [dict(dst=14, src_a=0, src_b=13, add=True)]),
        ("h1_cross_high", [dict(dst=0, src_a=13, src_b=14, add=False)]),
        # The two alternatives frozen in PRE_REGISTRATION section 3. They are
        # dispatched only after pilot01 refuted H1's full lifecycle contract.
        ("h2_pair_packing_add", [dict(dst=0, src_a=1, src_b=2, add=True,
                                            packing="h2")]),
        ("h2_pair_packing_sub", [dict(dst=3, src_a=4, src_b=5, add=False,
                                            packing="h2")]),
        ("h3_swapped_fields_sub", [dict(dst=3, src_a=4, src_b=5, add=False,
                                              packing="h3")]),
        # Gate-B arithmetic falsifier: encode r2+r2 while the host deliberately
        # predicts r1+r2. It must NOT match the complete-state oracle.
        ("ctl_wrong_src_selector", [dict(dst=0, src_a=1, src_b=2, add=True,
                                               model_a=1, model_b=2,
                                               packing="h1")]),
    ]
    for name, ops in specs:
        c = {
            "i": len(out), "name": name, "arm": "H1", "kind": "iadd",
            "ops": ops, "expect_match": name != "ctl_wrong_src_selector",
            "predicted_bucket": "exact" if name != "ctl_wrong_src_selector" else "refute",
        }
        if name == "ctl_wrong_src_selector":
            # Change only the encoded first selector, while keeping the oracle's
            # model_a at r1. This is not one of H2/H3; it is a detection control.
            c["ops"] = [dict(dst=0, src_a=2, src_b=2, add=True,
                             model_a=1, model_b=2, packing="h1")]
        out.append(c)

    # AMENDMENT-03 L1: exhaustive cross of the five bits nominated by the
    # authored-MSL differential.  The host state deliberately predicts both
    # inputs survive; released inputs therefore appear as explicit diffs.
    for o in (0, 1):
        for a in (0, 1):
            for b in (0, 1):
                for t1 in (0, 1):
                    for t2 in (0, 1):
                        name = f"l1_o{o}_a{a}_b{b}_t{t1}{t2}"
                        ops = [dict(
                            dst=0, src_a=1, src_b=2, add=True,
                            opmode=2 | o,
                            src_a_desc=a,
                            srca_ctl=0xA8 | (b << 2),
                            opc_tail=0x11 | (t1 << 1) | (t2 << 2),
                        )]
                        out.append({
                            "i": len(out), "name": name, "arm": "L1", "kind": "iadd",
                            "ops": ops, "expect_match": True,
                            "predicted_bucket": "discovery",
                        })

    v1_specs = [
        ("v1_add_retain", [dict(dst=0, src_a=1, src_b=2, add=True)]),
        ("v1_sub_retain", [dict(dst=3, src_a=4, src_b=5, add=False)]),
        ("v1_add_alias_a", [dict(dst=6, src_a=6, src_b=7, add=True)]),
        ("v1_sub_alias_b", [dict(dst=8, src_a=9, src_b=8, add=False)]),
        ("v1_add_same_src", [dict(dst=10, src_a=11, src_b=11, add=True)]),
        ("v1_repeat_sources", [
            dict(dst=10, src_a=1, src_b=2, add=True),
            dict(dst=11, src_a=1, src_b=2, add=True),
            dict(dst=12, src_a=10, src_b=11, add=False),
        ]),
        ("v1_rel_add_none", [dict(dst=0, src_a=1, src_b=2, add=True)]),
        ("v1_rel_add_a", [dict(dst=0, src_a=1, src_b=2, add=True,
                                    release_a=True, release_b=False)]),
        ("v1_rel_add_b", [dict(dst=0, src_a=1, src_b=2, add=True,
                                    release_a=False, release_b=True)]),
        ("v1_rel_add_both", [dict(dst=0, src_a=1, src_b=2, add=True,
                                       release_a=True, release_b=True)]),
        ("v1_rel_sub_a", [dict(dst=3, src_a=4, src_b=5, add=False,
                                    release_a=True, release_b=False)]),
        ("v1_rel_sub_b", [dict(dst=3, src_a=4, src_b=5, add=False,
                                    release_a=False, release_b=True)]),
        ("v1_rel_alias_a", [dict(dst=6, src_a=6, src_b=7, add=True,
                                      release_a=True, release_b=False)]),
        ("v1_rel_alias_b", [dict(dst=8, src_a=9, src_b=8, add=False,
                                      release_a=False, release_b=True)]),
        ("v1_last_use_chain", [
            dict(dst=10, src_a=1, src_b=2, add=True,
                 release_a=True, release_b=True),
            dict(dst=11, src_a=10, src_b=3, add=True,
                 release_a=True, release_b=True),
            dict(dst=12, src_a=11, src_b=4, add=False,
                 release_a=True, release_b=True),
        ]),
    ]
    for name, raw_ops in v1_specs:
        ops = []
        for op in raw_ops:
            op = dict(op)
            op.setdefault("logical_order", True)
            op.setdefault("release_a", False)
            op.setdefault("release_b", False)
            ops.append(op)
        out.append({
            "i": len(out), "name": name, "arm": "V1", "kind": "iadd",
            "ops": ops, "expect_match": True, "predicted_bucket": "exact",
        })

    dag_ops = []
    for i in range(64):
        dag_ops.append(dict(
            dst=(i * 11 + 3) % 15,
            src_a=(i * 5 + 1) % 15,
            src_b=(i * 7 + 2) % 15,
            add=(i % 3 != 0),
            logical_order=True,
            release_a=False,
            release_b=False,
        ))
    out.append({
        "i": len(out), "name": "v1_dag64_reuse", "arm": "V1", "kind": "iadd",
        "ops": dag_ops, "expect_match": True, "predicted_bucket": "exact",
    })
    return out


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIG_BUILD(case, slots, carrier_len)
    pg = build_iadd(case, slots, carrier_len)
    pg.dump()
    return pg, pg.finish(carrier_len)


def main():
    C.build_cases = build_cases
    C.build_program_for = build_program_for
    # run220 keeps its audited carrier/tool root. The caller supplies an absolute
    # --outroot pointing to EXP-0222/work/pilot, so no EXP-0220 raw is touched.
    return R.main()


if __name__ == "__main__":
    raise SystemExit(main())
