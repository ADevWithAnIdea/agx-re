#!/usr/bin/env python3
"""EXP-0224 generated FP32 falu3 recipe harness."""

import random
import struct
import sys
from pathlib import Path


EXP = Path(__file__).resolve().parent.parent
EXP_ROOT = EXP.parent
BASE_HARNESS = EXP_ROOT / "EXP-0223-isel-canonical" / "harness"
sys.path.insert(0, str(BASE_HARNESS))
import run223_pilot as B  # noqa: E402


C, P, R, S = B.C, B.P, B.R, B.S
ORIG_CASES = B.ORIG_CASES
ORIG_BUILD = B.ORIG_BUILD


# Three exact binary32 words used by the fused-rounding discriminator.  The
# product (1+2^-23)*(1-2^-23) is 1-2^-46; adding -1 with one rounding produces
# -2^-46 (0xa8800000), while a separately rounded multiply then add produces 0.
SPECIAL_MEM = {
    600: 0x3F800001,
    601: 0x3F7FFFFE,
    602: 0xBF800000,
}
for _word, _bits in SPECIAL_MEM.items():
    P.MEM[_word] = struct.unpack("<f", struct.pack("<I", _bits))[0]


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-0224 PRE_REGISTRATION", note)


def fma_bits(a_bits, b_bits, c_bits):
    if None in (a_bits, b_bits, c_bits):
        return None
    a, b, c = S.bits_f32(a_bits), S.bits_f32(b_bits), S.bits_f32(c_bits)
    # Every H input is an exactly representable small binary32 value.  Its
    # product and sum are exact in binary64, followed by one binary32 rounding.
    return struct.unpack("<I", struct.pack("<f", S.f32(a * b + c)))[0]


def emit_fma(pg, dst, src_a, src_b, src_c, op, ctrl_len,
             ctrl=0x02, srcmods=0xc0,
             model_src_a=None, model_src_b=None, model_src_c=None,
             model_kind="fma"):
    pg.E.emit("falu3", {
        "dst": fv(dst, "destination GPR"),
        "srcA": fv((src_a << 1) | 1, "FP32 source A descriptor"),
        "op": fv(op, "generated FMA operation/lifecycle point"),
        "srcB": fv((src_b << 1) | 1, "FP32 source B descriptor"),
        "ctrl_len": fv(ctrl_len, "eight-byte control/length point"),
        "srcC": fv(src_c << 1, "FP32 source C descriptor"),
        "ctrl": fv(ctrl, "source/control point"),
        "srcmods": fv(srcmods, "source modifier/load-accept point"),
    })
    pg._pending = None
    ma = src_a if model_src_a is None else model_src_a
    mb = src_b if model_src_b is None else model_src_b
    mc = src_c if model_src_c is None else model_src_c
    result = fma_bits(pg.rbits(ma), pg.rbits(mb), pg.rbits(mc))
    if model_kind == "mul_add_a":
        result = fma_bits(pg.rbits(ma), pg.rbits(mb), pg.rbits(ma))
    # AMENDMENT-01: releases happen after all reads; destination publication
    # follows, so a destination/source alias contains the result.
    if op & 0x08:
        pg.set_reg(src_a, 0)
    if op & 0x10:
        pg.set_reg(src_b, 0)
    if ctrl_len & 0x80:
        pg.set_reg(src_c, 0)
    pg.set_reg(dst, result)


def seed_h(pg, mapping):
    # r15 is the load index register.  If it is itself an FMA source, load it
    # last while its old value is still zero.
    for reg, word in sorted(mapping, key=lambda rw: rw[0] == P.R_IDX):
        pg.load_f(reg, word, salt=f"{pg.salt}.seed_r{reg}")


def scratch_not(protected, candidates=(15, 14, 13, 12, 11, 10, 9, 8)):
    for reg in candidates:
        if reg not in protected:
            return reg
    raise AssertionError("no dump scratch register")


def visibility_gap(pg, protected, count=1):
    reg = scratch_not(set(protected))
    for n in range(count):
        pg.movi(reg, 73 + (n & 3))


def dump_preserving(pg, protected):
    """Dump complete state without using a live r15 as the store index."""
    idx = scratch_not(set(protected))
    pg.body_end = pg.E.off
    pg.movi(idx, 0)
    for reg in P.DUMP_REGS:
        pg.store(reg, P.DUMP_BASE + reg, index_reg=idx, tag=f"dump_r{reg}")


def add_v2(out, name, kind="single", cfg=None, loads=None, expect=True,
           predicted=None, **extra):
    cfg = dict(cfg or {})
    case = {
        "i": len(out), "name": name, "arm": "V2", "kind": kind,
        "cfg": cfg, "loads": list(loads or []), "expect_match": expect,
        "predicted_bucket": predicted or ("exact" if expect else "refute"),
    }
    case.update(extra)
    out.append(case)


def ordinary_cfg(dst=0, a=1, b=2, c=3, op=0x06, ctrl_len=0x01, **kw):
    return dict(dst=dst, src_a=a, src_b=b, src_c=c, op=op,
                ctrl_len=ctrl_len, **kw)


def build_cases(include_hazard=False):
    out = [case for case in ORIG_CASES(False) if case["arm"] == "S0"]
    candidates = {
        "h1": (0x1e, 0x81),
        "h2": (0x06, 0x81),
        "h3": (0x06, 0x01),
    }
    variants = [
        ("abc", 0, 1, 2, 3),
        ("perm", 0, 3, 2, 1),
        ("reloc", 5, 6, 7, 8),
        ("alias_a", 1, 1, 2, 3),
    ]
    for name, (op, ctrl_len) in candidates.items():
        for suffix, dst, a, b, c in variants:
            out.append({
                "i": len(out), "name": f"{name}_{suffix}", "arm": name.upper(),
                "kind": "falu3", "expect_match": True, "predicted_bucket": "exact",
                "cfg": dict(dst=dst, src_a=a, src_b=b, src_c=c,
                            op=op, ctrl_len=ctrl_len),
            })
    out.append({
        "i": len(out), "name": "h_ctl_wrong_c", "arm": "HCTL", "kind": "falu3",
        "expect_match": False, "predicted_bucket": "refute",
        "cfg": dict(dst=0, src_a=1, src_b=2, src_c=3, op=0x06, ctrl_len=0x81,
                    model_src_c=4),
    })
    out.append({
        "i": len(out), "name": "h_ctl_wrong_op", "arm": "HCTL", "kind": "falu3",
        "expect_match": False, "predicted_bucket": "refute",
        "cfg": dict(dst=0, src_a=1, src_b=2, src_c=3, op=0x06, ctrl_len=0x81,
                    model_kind="mul_add_a"),
    })

    # ---- V2: compiler promotion matrix -----------------------------------
    standard = [(1, 3), (2, 7), (3, 11)]       # 1.0, 2.0, 3.0

    # Dense compact destinations, using high sources to avoid accidental
    # aliases with every r0..r15 destination.
    for dst in range(16):
        add_v2(out, f"v2_dst_r{dst:02d}", cfg=ordinary_cfg(dst, 20, 21, 22),
               loads=[(20, 3), (21, 7), (22, 11)])

    # Every source role independently reaches every dumped GPR r0..r23.
    for role in ("a", "b", "c"):
        for target in range(24):
            regs = {"a": target if role == "a" else 20,
                    "b": target if role == "b" else 21,
                    "c": target if role == "c" else 22}
            occupied = set(regs.values())
            # If target collided with a fixed role, relocate that fixed role.
            for other in ("a", "b", "c"):
                if other == role:
                    continue
                if regs[other] == target or list(regs.values()).count(regs[other]) > 1:
                    regs[other] = next(r for r in (23, 19, 18, 17, 16)
                                       if r not in set(regs.values()))
            occupied = set(regs.values())
            dst = next(r for r in (0, 14, 13, 12, 11) if r not in occupied)
            words = {regs["a"]: 3, regs["b"]: 7, regs["c"]: 11}
            add_v2(out, f"v2_src{role}_r{target:02d}",
                   cfg=ordinary_cfg(dst, regs["a"], regs["b"], regs["c"]),
                   loads=sorted(words.items()))

    alias_specs = [
        ("dst_a", ordinary_cfg(1, 1, 2, 3), standard),
        ("dst_b", ordinary_cfg(2, 1, 2, 3), standard),
        ("dst_c", ordinary_cfg(3, 1, 2, 3), standard),
        ("a_eq_b", ordinary_cfg(0, 1, 1, 3), [(1, 3), (3, 11)]),
        ("a_eq_c", ordinary_cfg(0, 1, 2, 1), [(1, 3), (2, 7)]),
        ("b_eq_c", ordinary_cfg(0, 1, 2, 2), [(1, 3), (2, 7)]),
        ("all_src", ordinary_cfg(0, 1, 1, 1), [(1, 3)]),
    ]
    for suffix, cfg, loads in alias_specs:
        add_v2(out, f"v2_alias_{suffix}", cfg=cfg, loads=loads)

    # Arithmetic sign cases plus the discriminator that proves fused rather
    # than separately-rounded multiply and add.
    numeric = [
        ("base", standard),
        ("perm", [(1, 11), (2, 7), (3, 3)]),
        ("neg_a", [(1, 515), (2, 7), (3, 11)]),
        ("neg_c", [(1, 3), (2, 7), (3, 515)]),
        ("zero_a", [(1, 512), (2, 7), (3, 11)]),
        ("fused_cancel", [(1, 600), (2, 601), (3, 602)]),
    ]
    for suffix, loads in numeric:
        add_v2(out, f"v2_num_{suffix}", cfg=ordinary_cfg(), loads=loads)

    # Complete post-read release truth table and destination/release aliases.
    for mask in range(8):
        op = 0x06 | (0x08 if mask & 1 else 0) | (0x10 if mask & 2 else 0)
        clen = 0x81 if mask & 4 else 0x01
        add_v2(out, f"v2_life_{mask:01x}", cfg=ordinary_cfg(op=op, ctrl_len=clen),
               loads=standard)
    add_v2(out, "v2_life_op_bit5", cfg=ordinary_cfg(op=0x26), loads=standard)
    add_v2(out, "v2_life_alias_a", cfg=ordinary_cfg(1, 1, 2, 3, op=0x0e),
           loads=standard)
    add_v2(out, "v2_life_alias_b", cfg=ordinary_cfg(2, 1, 2, 3, op=0x16),
           loads=standard)
    add_v2(out, "v2_life_alias_c", cfg=ordinary_cfg(3, 1, 2, 3, ctrl_len=0x81),
           loads=standard)

    # Place each load immediately before the consumer and at short distances.
    for role, final_reg in (("a", 1), ("b", 2), ("c", 3)):
        for gap in (0, 1, 4):
            add_v2(out, f"v2_load_{role}_gap{gap}", kind="load_adj",
                   cfg=ordinary_cfg(), loads=standard, final_reg=final_reg, gap=gap)

    # Deterministic FMA-only DAGs. Multiplication by exactly 1.0 plus small
    # quarter constants keeps every intermediate exactly modelled in binary32.
    for case_i in range(100):
        rng = random.Random(0x224000 + case_i)
        initialized = [1, 2, 3, 4]
        ops = []
        for _ in range(2 + ((case_i * 37) % 63)):
            prev = rng.choice(initialized)
            dst = rng.choice(range(5, 12))
            c = rng.choice((2, 3, 4))
            if rng.randrange(2):
                cfg = ordinary_cfg(dst, prev, 1, c)
            else:
                cfg = ordinary_cfg(dst, 1, prev, c)
            ops.append(cfg)
            if dst not in initialized:
                initialized.append(dst)
        add_v2(out, f"v2_dag_{case_i:03d}", kind="dag", cfg={},
               loads=[(1, 3), (2, 0), (3, 1), (4, 2)], ops=ops)

    add_v2(out, "v2_ctl_wrong_c", cfg=ordinary_cfg(model_src_c=4),
           loads=standard + [(4, 15)], expect=False)
    add_v2(out, "v2_ctl_wrong_op", cfg=ordinary_cfg(model_kind="mul_add_a"),
           loads=standard, expect=False)

    # ---- P2: diagnose V2's high-source-only failures ---------------------
    def add_p2(name, cfg, loads, gap):
        out.append({
            "i": len(out), "name": name, "arm": "P2", "kind": "p2",
            "cfg": cfg, "loads": list(loads), "gap": gap,
            "expect_match": True, "predicted_bucket": "exact",
        })

    for role in ("a", "b", "c"):
        for target in range(16):
            regs = {"a": target if role == "a" else 1,
                    "b": target if role == "b" else 2,
                    "c": target if role == "c" else 3}
            # Avoid accidental role aliases except in the dedicated alias suite.
            used = {target}
            for other in ("a", "b", "c"):
                if other == role:
                    continue
                if regs[other] in used:
                    regs[other] = next(r for r in (4, 5, 6, 7) if r not in used)
                used.add(regs[other])
            dst = next(r for r in (0, 14, 13, 12, 11) if r not in used)
            words = {regs["a"]: 3, regs["b"]: 7, regs["c"]: 11}
            add_p2(f"p2_low_{role}_r{target:02d}",
                   ordinary_cfg(dst, regs["a"], regs["b"], regs["c"]),
                   sorted(words.items()), 1)

        for target in range(16, 24):
            regs = {"a": target if role == "a" else 1,
                    "b": target if role == "b" else 2,
                    "c": target if role == "c" else 3}
            words = {regs["a"]: 3, regs["b"]: 7, regs["c"]: 11}
            for gap in (1, 64):
                add_p2(f"p2_high_{role}_r{target:02d}_gap{gap}",
                       ordinary_cfg(0, regs["a"], regs["b"], regs["c"]),
                       sorted(words.items()), gap)

    for gap in (1, 16, 64):
        add_p2(f"p2_three_high_gap{gap}", ordinary_cfg(0, 20, 21, 22),
               [(20, 3), (21, 7), (22, 11)], gap)
    return out


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIG_BUILD(case, slots, carrier_len)
    pg = B.fresh(case, slots)
    if case["arm"] in ("V2", "P2"):
        cfg = case["cfg"]
        if case["kind"] == "p2":
            seed_h(pg, case["loads"])
            protected = {r for r, _ in case["loads"]} | {
                cfg["dst"], cfg["src_a"], cfg["src_b"], cfg["src_c"]}
            visibility_gap(pg, protected, case["gap"])
            emit_fma(pg, **cfg)
        elif case["kind"] == "load_adj":
            final_reg = case["final_reg"]
            early = [rw for rw in case["loads"] if rw[0] != final_reg]
            final = [rw for rw in case["loads"] if rw[0] == final_reg]
            seed_h(pg, early)
            visibility_gap(pg, set(r for r, _ in case["loads"]) | {cfg["dst"]})
            seed_h(pg, final)
            if case["gap"]:
                visibility_gap(pg, set(r for r, _ in case["loads"]) | {cfg["dst"]},
                               case["gap"])
            emit_fma(pg, **cfg)
            protected = {cfg["dst"], cfg["src_a"], cfg["src_b"], cfg["src_c"]}
        elif case["kind"] == "dag":
            seed_h(pg, case["loads"])
            visibility_gap(pg, {r for r, _ in case["loads"]})
            protected = {r for r, _ in case["loads"]}
            for op in case["ops"]:
                emit_fma(pg, **op)
                protected.update((op["dst"], op["src_a"], op["src_b"], op["src_c"]))
        else:
            seed_h(pg, case["loads"])
            protected = {r for r, _ in case["loads"]} | {
                cfg["dst"], cfg["src_a"], cfg["src_b"], cfg["src_c"]}
            visibility_gap(pg, protected)
            emit_fma(pg, **cfg)
        dump_preserving(pg, protected)
    else:
        seed_h(pg, [(1, 3), (2, 7), (3, 11), (4, 15),
                    (6, 19), (7, 23), (8, 27)])
        visibility_gap(pg, {1, 2, 3, 4, 6, 7, 8})
        emit_fma(pg, **case["cfg"])
        pg.dump()
    return pg, pg.finish(carrier_len)


def main():
    C.build_cases = build_cases
    C.build_program_for = build_program_for
    return R.main()


if __name__ == "__main__":
    raise SystemExit(main())
