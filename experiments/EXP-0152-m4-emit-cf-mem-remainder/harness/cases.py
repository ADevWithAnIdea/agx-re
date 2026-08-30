#!/usr/bin/env python3
"""EXP-0152 FROZEN case matrix.  Pure, deterministic, no GPU.

`build_cases(facts)` returns the complete ordered list of case descriptors.
`facts` carries each carrier's re-derived `_agc.main` length and the re-derived
instruction sites (harness/baseline.py); nothing here is a hardcoded offset that
was not asserted first.

ARM ORDER IS PART OF THE FROZEN CONTRACT (PRE_REGISTRATION.md section 8): the
cheap, low-risk CF arms and every MEM arm run BEFORE the hang-prone ones, so a
CF-wide safety stop cannot cost the arms that were one capture from done.

Every case carries a HOST-COMPUTED oracle.  Where a case tests INERTNESS the
oracle is the carrier's own host-computed baseline vector and `expect_match` is
null (no prediction).  Where a real prediction exists it is pre-registered here,
before any gated run.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools" / "agx-isa"))
import isadb            # noqa: E402
import isa_helpers as H  # noqa: E402
import carriers as C     # noqa: E402

# ---------------------------------------------------------------- constants
# compiler-natural values of every swept CF field, read off the frozen skeleton
CF_NAT = {
    ("jump", "branch_ctrl"): 0x54,
    ("pop_reconverge", "reserved"): 0x0000,
    ("ret", "linkmode"): 0x04,
    ("ret", "scoreboard"): 0x22,
    ("ret_luse", "linkmode"): 0x04,
    ("ret_luse", "tail"): 0x22,
    ("if_push_pred", "level"): 0x01,
    ("jump_cond", "cf_scope"): 0x54,
    ("jump_cond", "reserved"): 0x00,
    ("jump_cond", "offset"): 0x40,
    ("mask_op", "mask_bank"): 0x04,
    ("mask_op", "scope_kind"): 0x19,
}

# KNOWN-HANG EXCLUSIONS -- values another experiment observed as REPRODUCED GPU
# hangs.  They are dispatched as `skipped` records carrying the reason, never
# silently dropped, and they are reported as documented do-not-emit holes.
EXCLUDE = {
    ("jump", "branch_ctrl"): ({0, 1},
        "EXP-0140 run03 reproduced HANG at 0 and 1 (its run02 saw both inert); "
        "unstable, excluded on safety"),
    ("if_push_pred", "level"): ({62, 63, 180, 181},
        "EXP-0140 run02 reproduced HANG at 62,63 and run03 at 180,181"),
    ("ret", "scoreboard"): ({8, 12},
        "EXP-0140 run02 reproduced HANG at 8 and 12"),
    ("ret_luse", "tail"): ({8, 12},
        "same byte position as ret.scoreboard, which hung at 8 and 12 "
        "(EXP-0140 run02)"),
    ("atomic_tg", "op_desc"): ({0x7E, 0x7F},
        "EXP-0141 reproduced GPU HANG at 0x7E and 0x7F and published DO NOT EMIT"),
}

# jump_cond poison offsets (PRE_REGISTRATION.md H7).  Both are forward targets
# inside the program's post-loop tail.
P1, P2 = 0x5C, 0x52
JC_NATURAL = 0x40
# dense forward displacement window: every value whose target is at or after the
# first post-loop instruction start, through one past the end of `_agc.main`.
JC_DENSE = list(range(58, 111))
JC_FAR = [128, 192, 256]          # deliberately last inside the arm
# NO negative and no 0/1/2 displacement is dispatched: with the branch genuinely
# taken those are infinite loops (EXP-0128 hung the GPU exactly that way).


def wide16():
    """Protocol section 3.3 coverage for a 16-bit field: boundaries, every power
    of two, and >= 16 asymmetric interior samples."""
    v = {0, 1, 2, 3, 0xFFFE, 0xFFFF}
    v |= {1 << i for i in range(16)}
    v |= {0x00FF, 0x0100, 0x0101, 0x1234, 0x5A5A, 0xA5A5, 0x7FFF, 0x8001,
          0xCCCC, 0x3333, 0x0F0F, 0xF0F0, 0xBEEF, 0xDEAD, 0x2468, 0x1357}
    return sorted(v)


# ------------------------------------------------------------------ helpers
def _c(group, arm, instr, field, value, carrier, oracle, ibytes, note,
       expect=None, prog=None, patch=None, skip=None):
    d = dict(group=group, arm=arm, instr=instr, field=field, value=value,
             carrier=carrier, oracle=oracle, bytes=ibytes, note=note,
             expect_match=expect)
    if skip:
        d["skip"] = skip
    elif prog is not None:
        d["prog"] = bytes(prog)
    elif patch is not None:
        d["patch"] = [(o, bytes(b)) for (o, b) in patch]
    else:
        raise ValueError("case needs prog, patch or skip")
    return d


def _cf_oracle(nvec):
    return C.cf_oracle_words(nvec, H.cf_oracle)


UNREACHABLE = {"0:%d" % i: C.f32bits(1.0) for i in range(8)}


# =========================================================== CF arms (cfN)
def a01_cf_baseline(ml):
    cs = []
    for car, nvec in (("cfN", C.CF_N_MIXED), ("cf0", C.CF_N_ZERO)):
        prog = H.cf_program_x(carrier_len=ml)
        cs.append(_c("cf.baseline." + car, "cf.baseline", "cf_skeleton", "-", 0,
                     car, _cf_oracle(nvec), "",
                     "unmutated EXP-0090/EXP-0112 CF skeleton", True, prog=prog))
        cs.append(_c("cf.falsifier." + car, "cf.baseline", "cf_skeleton", "-", 0,
                     car, UNREACHABLE, "",
                     "FALSIFIER: unmutated skeleton, unreachable oracle",
                     False, prog=prog))
    return cs


def _cf_field_arm(ml, seq_idx, mnem, field, values, carrier="cfN", nvec=None,
                  extra_over=(), extra_patch=(), arm=None, group=None,
                  expect_for=None, notefn=None):
    nvec = C.CF_N_MIXED if nvec is None else nvec
    orc = _cf_oracle(nvec)
    nat = CF_NAT.get((mnem, field))
    excl, why = EXCLUDE.get((mnem, field), (set(), ""))
    arm = arm or "%s.%s" % (mnem, field)
    group = group or arm
    cs = []
    for v in values:
        if v in excl:
            cs.append(_c(group, arm, mnem, field, v, carrier, orc, "",
                         "EXCLUDED (known reproduced hang): " + why,
                         None, skip="known_hang_excluded"))
            continue
        overs = list(extra_over) + [(seq_idx, field, v)]
        prog = H.cf_program_x(overrides=overs, patches=extra_patch,
                              carrier_len=ml)
        seq = H.cf_sequence()
        f = dict(seq[seq_idx][1])
        for (i, n2, v2) in overs:
            if i == seq_idx:
                f[n2] = v2
        ib = isadb.assemble(seq[seq_idx][0], f).hex()
        if expect_for is not None:
            exp = expect_for(v)
        else:
            exp = True if (nat is not None and v == nat) else None
        note = notefn(v) if notefn else (
            "compiler-natural value" if (nat is not None and v == nat)
            else "exploratory (inertness test)")
        cs.append(_c(group, arm, mnem, field, v, carrier, orc, ib, note, exp,
                     prog=prog))
    return cs


def a02_jump_branch_ctrl(ml):
    return _cf_field_arm(ml, 13, "jump", "branch_ctrl", list(range(256)))


def a03_pop_reserved(ml):
    cs = []
    for seq_idx, tag in ((14, "a"), (15, "b")):
        cs += _cf_field_arm(ml, seq_idx, "pop_reconverge", "reserved", wide16(),
                            arm="pop_reconverge.reserved@%s" % tag,
                            group="pop_reconverge.reserved@%s" % tag)
    return cs


def a04_ret_linkmode(ml):
    return _cf_field_arm(ml, 12, "ret", "linkmode", list(range(256)))


def a05_ret_luse(ml):
    """`ret_luse` is `ret` with byte+2 0x54 -> 0x56 -- the SAME 4-byte length at
    the SAME address, so it is spliced in place with no displacement change."""
    orcN = _cf_oracle(C.CF_N_MIXED)
    ra = H.CF_ADDR["ret"]
    cs = []
    # control: the drop-in claim itself (H4)
    nat = isadb.assemble("ret_luse", {"linkmode": 0x04, "tail": 0x22})
    cs.append(_c("ret_luse.control", "ret_luse.control", "ret_luse", "_byte2_56",
                 0x56, "cfN", orcN, nat.hex(),
                 "CONTROL: ret byte+2 0x54->0x56 alone; pre-registered to still "
                 "run (the drop-in claim). Its failure is H4's refuter.",
                 True, prog=H.cf_program_x(patches=[(ra, nat)], carrier_len=ml)))
    for field, other in (("linkmode", ("tail", 0x22)), ("tail", ("linkmode", 0x04))):
        excl, why = EXCLUDE.get(("ret_luse", field), (set(), ""))
        for v in range(256):
            if v in excl:
                cs.append(_c("ret_luse." + field, "ret_luse." + field, "ret_luse",
                             field, v, "cfN", orcN, "",
                             "EXCLUDED (known reproduced hang): " + why,
                             None, skip="known_hang_excluded"))
                continue
            flds = {field: v, other[0]: other[1]}
            b = isadb.assemble("ret_luse", flds)
            nat_v = CF_NAT[("ret_luse", field)]
            cs.append(_c("ret_luse." + field, "ret_luse." + field, "ret_luse",
                         field, v, "cfN", orcN, b.hex(),
                         "compiler-natural value" if v == nat_v
                         else "exploratory (inertness test)",
                         True if v == nat_v else None,
                         prog=H.cf_program_x(patches=[(ra, b)], carrier_len=ml)))
    return cs


# =========================================================== MEM arms
def _mem_arm(facts, carrier, mnem, boff, values, pin=None, arm=None,
             excl_key=None):
    site_m, off, ln, orig = facts["sites"][carrier]
    orc = {"atdev": C.atdev_oracle, "atdevimm": C.atdevimm_oracle,
           "attg": C.attg_oracle}[carrier]()
    if pin:
        # atomic_rmw = atomic_mem with byte+1 pinned to 0x11
        base_patch = [(off + pin[0], bytes([pin[1]]))]
    else:
        base_patch = []
    excl, why = EXCLUDE.get(excl_key, (set(), "")) if excl_key else (set(), "")
    arm = arm or "%s_%s_b%d" % (carrier, mnem, boff)
    cs = []
    for v in values:
        if v in excl:
            cs.append(_c(arm, arm, mnem, "byte+%d" % boff, v, carrier, orc, "",
                         "EXCLUDED (known reproduced hang): " + why,
                         None, skip="known_hang_excluded"))
            continue
        mut = bytearray(orig)
        if pin:
            mut[pin[0]] = pin[1]
        mut[boff] = v
        cs.append(_c(arm, arm, mnem, "byte+%d" % boff, v, carrier, orc,
                     bytes(mut).hex(),
                     "compiler-natural value" if v == orig[boff]
                     else "exploratory (dense byte sweep)",
                     True if (v == orig[boff] and not pin) else None,
                     patch=base_patch + [(off + boff, bytes([v]))]))
    return cs


def a06_mem(facts):
    cs = []
    for car in ("atdev", "atdevimm", "attg"):
        m, off, ln, orig = facts["sites"][car]
        orc = {"atdev": C.atdev_oracle, "atdevimm": C.atdevimm_oracle,
               "attg": C.attg_oracle}[car]()
        cs.append(_c(car + ".baseline", car + ".baseline", m, "-", 0, car, orc,
                     orig.hex(), "unmutated own-MSL carrier", True,
                     patch=[(off, bytes([orig[0]]))]))
        bad = {k: (v ^ 0x1234) & 0xFFFFFFFF for k, v in orc.items()}
        cs.append(_c(car + ".falsifier", car + ".baseline", m, "-", 0, car, bad,
                     orig.hex(), "FALSIFIER: unmutated carrier, unreachable oracle",
                     False, patch=[(off, bytes([orig[0]]))]))
    # pre-registered op-splice falsifiers (EXP-0141's, reused)
    m, off, ln, orig = facts["sites"]["atdev"]
    cs.append(_c("atdev.opctl", "atdev.baseline", "atomic_mem", "byte+12", 0x22,
                 "atdev", C.atdev_oracle(), "",
                 "FALSIFIER: byte+12 0x20->0x22 turns add into and; the counter "
                 "becomes 0, not a[0]", False,
                 patch=[(off + 12, b"\x22")]))
    m2, off2, ln2, orig2 = facts["sites"]["attg"]
    cs.append(_c("attg.opctl", "attg.baseline", "atomic_tg", "byte+11", 0x05,
                 "attg", C.attg_oracle(), "",
                 "FALSIFIER: byte+11 0x04->0x05 turns add into smax; o[0] "
                 "becomes max(a[0..15]), not the sum", False,
                 patch=[(off2 + 11, b"\x05")]))
    # dense byte sweeps
    cs += _mem_arm(facts, "atdev", "atomic_mem", 12, list(range(256)))
    cs += _mem_arm(facts, "atdevimm", "atomic_mem", 12, list(range(256)))
    # atomic_rmw = the SAME site with byte+1 pinned to 0x11
    cs.append(_c("atdev_rmw.control", "atdev_rmw.control", "atomic_rmw",
                 "_byte1_11", 0x11, "atdev", C.atdev_oracle(), "",
                 "CONTROL: byte+1 0x01->0x11 selects the atomic_rmw form; "
                 "pre-registered to still add (EXP-0141 H7)", True,
                 patch=[(facts["sites"]["atdev"][1] + 1, b"\x11")]))
    cs += _mem_arm(facts, "atdev", "atomic_rmw", 12, list(range(256)),
                   pin=(1, 0x11), arm="atdev_atomic_rmw_b12")
    cs += _mem_arm(facts, "attg", "atomic_tg", 5, list(range(256)),
                   excl_key=("atomic_tg", "op_desc"))
    cs += _mem_arm(facts, "attg", "atomic_tg", 10, list(range(256)))
    cs += _mem_arm(facts, "attg", "atomic_tg", 11, list(range(256)))
    return cs


# =========================================================== jump_cond (cf0)
def a07_jc_liveness(ml):
    """The pre-registered liveness gate (H7).  Same program bytes, two `n`
    inputs; the ONLY thing that changes is whether the guard branch is taken."""
    cs = []
    for pname, pv in (("P1", P1), ("P2", P2), ("NAT", JC_NATURAL)):
        prog = H.cf_program_x(overrides=[(5, "offset", pv)], carrier_len=ml)
        ib = isadb.assemble("jump_cond", dict(H.cf_sequence()[5][1], offset=pv)).hex()
        cs.append(_c("jc.live.cf0." + pname, "jc.liveness", "jump_cond", "offset",
                     pv, "cf0", _cf_oracle(C.CF_N_ZERO), ib,
                     ("GATE: n=0 makes the guard uniformly true, so the branch is "
                      "TAKEN; a poison target must therefore CHANGE the output")
                     if pname != "NAT" else
                     "n=0, natural offset: taken branch lands where the compiler "
                     "intended, so the output must equal the fall-through oracle",
                     (False if pname != "NAT" else True), prog=prog))
        cs.append(_c("jc.live.cfN." + pname, "jc.liveness", "jump_cond", "offset",
                     pv, "cfN", _cf_oracle(C.CF_N_MIXED), ib,
                     "PAIRED CONTROL: identical bytes, mixed n -> guard false -> "
                     "branch NOT taken, so the displacement must be irrelevant",
                     True, prog=prog))
    return cs


def a08_jc_offset(ml):
    return _cf_field_arm(
        ml, 5, "jump_cond", "offset", JC_DENSE + JC_FAR, carrier="cf0",
        nvec=C.CF_N_ZERO,
        expect_for=lambda v: True if v == JC_NATURAL else None,
        notefn=lambda v: ("compiler-natural value" if v == JC_NATURAL else
                          "forward displacement, target = jump_cond_addr(+42) + %d"
                          % v))


def a09_jc_scope(ml):
    cs = []
    for pname, pv in (("P1", P1), ("P2", P2)):
        for field in ("cf_scope", "reserved"):
            nat = CF_NAT[("jump_cond", field)]
            cs += _cf_field_arm(
                ml, 5, "jump_cond", field, list(range(256)), carrier="cf0",
                nvec=C.CF_N_ZERO, extra_over=[(5, "offset", pv)],
                arm="jump_cond.%s@%s" % (field, pname),
                group="jump_cond.%s@%s" % (field, pname),
                expect_for=lambda v, n=nat: False if v == n else None,
                notefn=lambda v, n=nat: (
                    "compiler-natural value at the poison offset: the branch is "
                    "TAKEN, so this MUST differ from the fall-through oracle"
                    if v == n else
                    "taken/not-taken classification against the fall-through oracle"))
    return cs


# =========================================================== hang-prone CF
def a10_if_push_pred_level(ml):
    return _cf_field_arm(ml, 4, "if_push_pred", "level", list(range(256)))


def a11_ret_scoreboard(ml):
    return _cf_field_arm(ml, 12, "ret", "scoreboard", list(range(256)))


def a12_mask_op(ml):
    """`mask_op` (0f 04 <bank> <kind>) is 4 bytes -- exactly the length of the
    skeleton's `if_push` (0f 05 54 1a) at +56 -- so it is spliced in at a real
    execution-mask site with no length and no displacement change."""
    orc = _cf_oracle(C.CF_N_MIXED)
    ia = H.CF_ADDR["if_push"]
    cs = []
    natb = isadb.assemble("mask_op", {"mask_bank": 0x04, "scope_kind": 0x19})
    cs.append(_c("mask_op.liveness", "mask_op.liveness", "mask_op", "_natural",
                 0, "cfN", orc, natb.hex(),
                 "LIVENESS GATE: the compiler-natural mask_op spliced over "
                 "if_push must CHANGE the output, or the site proves nothing",
                 False, prog=H.cf_program_x(patches=[(ia, natb)], carrier_len=ml)))
    for field, other in (("mask_bank", ("scope_kind", 0x19)),
                         ("scope_kind", ("mask_bank", 0x04))):
        for v in range(256):
            b = isadb.assemble("mask_op", {field: v, other[0]: other[1]})
            cs.append(_c("mask_op." + field, "mask_op." + field, "mask_op", field,
                         v, "cfN", orc, b.hex(),
                         "swept at the if_push site; classified against the "
                         "unmutated-skeleton oracle", None,
                         prog=H.cf_program_x(patches=[(ia, b)], carrier_len=ml)))
    return cs


# ================================================================== assembly
def build_cases(facts):
    ml = facts["carriers"]["cfN"]["main_len"]
    cs = []
    cs += a01_cf_baseline(ml)
    cs += a02_jump_branch_ctrl(ml)
    cs += a03_pop_reserved(ml)
    cs += a04_ret_linkmode(ml)
    cs += a05_ret_luse(ml)
    cs += a06_mem(facts)
    cs += a07_jc_liveness(ml)
    cs += a08_jc_offset(ml)
    cs += a09_jc_scope(ml)
    cs += a10_if_push_pred_level(ml)
    cs += a11_ret_scoreboard(ml)
    cs += a12_mask_op(ml)
    for i, c in enumerate(cs):
        c["i"] = i
        spec = C.CARRIERS[c["carrier"]]
        c["dispatch"] = (spec["grid"], spec["tg"])
        c["mode"] = spec["mode"]
        c["sentinel"] = spec["sentinel"]
        c["outs"] = dict(spec["outs"])
    return cs


if __name__ == "__main__":
    import json
    import baseline as B
    facts = B.derive(str(HERE.parent / "work" / "bin"),
                     str(HERE.parent / "work" / "baseline_bin"))
    cs = build_cases(facts)
    from collections import Counter
    print("total cases:", len(cs),
          "| dispatched:", sum(1 for c in cs if "skip" not in c))
    for a, n in Counter(c["arm"] for c in cs).items():
        print("  %-32s %d" % (a, n))
